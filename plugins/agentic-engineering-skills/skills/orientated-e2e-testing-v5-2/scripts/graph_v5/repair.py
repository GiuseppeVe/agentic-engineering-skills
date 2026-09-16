"""Single-patch repair and local proof invalidation for closed V5 cones."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from threading import RLock

from .causality import CausalityError, ClosedCausalCone, MutationLease
from .models import Observation, ProofResult, ProofSpec, RepairAttempt


class RepairError(ValueError):
    """A repair candidate or local revalidation plan is unsafe."""


def _require_bound_proof_authority(proof_spec: ProofSpec) -> None:
    """Standalone repair needs all authority digests; runtime compares exact values."""

    bindings = (
        proof_spec.trajectory_digest,
        proof_spec.derived_spine_digest,
        proof_spec.landmark_mapping_digest,
    )
    if any(re.fullmatch(r"[0-9a-f]{64}", value) is None for value in bindings):
        raise RepairError("requested ProofSpec requires trajectory/spine/landmark authority binding")


@dataclass(frozen=True, slots=True)
class FailedRepairEvidence:
    """Immutable failed-repair evidence consumed by bounded runtime recovery."""

    repair: RepairAttempt
    proof_spec: ProofSpec
    proof_result: ProofResult

    def __post_init__(self) -> None:
        if self.repair.status not in {"red", "rejected"}:
            raise RepairError("failed repair evidence requires a non-green repair")
        if (
            self.proof_result.proof_spec_id != self.proof_spec.proof_spec_id
            or self.proof_result.proof_spec_digest != self.proof_spec.digest
            or self.proof_result.node_id != self.proof_spec.node_id
        ):
            raise RepairError("failed repair proof result must bind requested ProofSpec")
        if self.proof_result.proof_class != "deterministic_execution_proof":
            raise RepairError("failed repair evidence requires deterministic proof result")
        if self.proof_result.result == "green":
            raise RepairError("green proof result is not a failed repair")


@dataclass(frozen=True, slots=True)
class CandidatePatch:
    cone_id: str
    node_id: str
    root_lead_id: str
    patch: str
    changed_files: tuple[str, ...]
    changed_dependencies: tuple[str, ...]
    local_validation_receipt: str
    requested_proof: ProofSpec
    preserved_observations: tuple[Observation, ...]
    derived_neighbor_node_ids: frozenset[str]
    mutation_lease: MutationLease = field(repr=False, compare=False)

    @property
    def changed_facts(self) -> frozenset[str]:
        return frozenset((*self.changed_files, *self.changed_dependencies))


_candidate_lock = RLock()
_issued_candidate: CandidatePatch | None = None


def _register_issued_candidate(candidate: CandidatePatch) -> None:
    global _issued_candidate
    with _candidate_lock:
        if _issued_candidate is not None:
            try:
                _issued_candidate.mutation_lease.assert_active()
            except CausalityError:
                _issued_candidate = None
            else:
                raise RepairError("active mutation lease already has an issued candidate")
        _issued_candidate = candidate


@dataclass(frozen=True, slots=True)
class ProofFact:
    proof_id: str
    node_id: str
    dynamic_trace: tuple[str, ...] = ()
    declared_dependencies: tuple[str, ...] = ()
    ownership_seams: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.proof_id.strip() or not self.node_id.strip():
            raise RepairError("proof fact id and node id are required")


@dataclass(frozen=True, slots=True)
class RevalidationPlan:
    invalidated_proof_ids: tuple[str, ...]
    revalidation_node_ids: tuple[str, ...]


def propose_repair(
    cone: ClosedCausalCone | object,
    *,
    lease: MutationLease,
    patch: str,
    changed_files: tuple[str, ...],
    changed_dependencies: tuple[str, ...],
    local_validation_receipt: str,
    requested_proof: ProofSpec,
) -> CandidatePatch:
    """Produce exactly one repair candidate from an already closed local cone."""

    if not isinstance(cone, ClosedCausalCone):
        raise RepairError("repairs require a closed cone")
    try:
        cone.cone.close(cone.frozen_expansion)
    except CausalityError as error:
        raise RepairError(f"repairs require a closed cone: {error}") from error
    if not isinstance(lease, MutationLease):
        raise RepairError("exact active mutation lease is required")
    if lease.cone_id != cone.cone_id:
        raise RepairError("active mutation lease belongs to another cone")
    try:
        lease.assert_active()
    except CausalityError as error:
        raise RepairError(str(error)) from error
    if not patch.strip():
        raise RepairError("candidate patch is required")
    if not changed_files or not changed_dependencies:
        raise RepairError("candidate patch requires changed-file/dependency set")
    if not local_validation_receipt.strip():
        raise RepairError("local validation receipt is required")
    if requested_proof.node_id != cone.node_id or not requested_proof.command:
        raise RepairError("requested ProofSpec must target current Behavioral Node")
    _require_bound_proof_authority(requested_proof)
    root_lead_id = cone.frozen_expansion.selected_lead_id
    if root_lead_id is None:
        raise RepairError("closed cone requires a selected frozen root")
    candidate = CandidatePatch(
        cone_id=cone.cone_id,
        node_id=cone.node_id,
        root_lead_id=root_lead_id,
        patch=patch,
        changed_files=tuple(changed_files),
        changed_dependencies=tuple(changed_dependencies),
        local_validation_receipt=local_validation_receipt,
        requested_proof=requested_proof,
        preserved_observations=cone.cone.observations,
        derived_neighbor_node_ids=_derived_neighbor_node_ids(cone, root_lead_id),
        mutation_lease=lease,
    )
    _register_issued_candidate(candidate)
    return candidate


def _derived_neighbor_node_ids(
    cone: ClosedCausalCone,
    root_lead_id: str,
) -> frozenset[str]:
    """Return source nodes for leads directly incident to selected causal root."""

    related_lead_ids = {root_lead_id}
    for edge in cone.cone.edges:
        if root_lead_id in (edge.from_lead_id, edge.to_lead_id):
            related_lead_ids.update((edge.from_lead_id, edge.to_lead_id))
    observation_by_id = {
        observation.observation_id: observation for observation in cone.cone.observations
    }
    return frozenset(
        observation_by_id[lead.source_observation_id].node_id
        for lead in cone.cone.leads
        if lead.lead_id in related_lead_ids
        and lead.source_observation_id in observation_by_id
        and observation_by_id[lead.source_observation_id].node_id != cone.node_id
    )


def integrate_repair(
    candidate: CandidatePatch,
    *,
    lease: MutationLease | object | None = None,
    proofs: tuple[ProofFact, ...],
    changed_ownership_seams: tuple[str, ...],
    direct_affected_neighbors: tuple[str, ...],
) -> RevalidationPlan:
    """Conservatively stale intersecting proofs; revalidate only current local surface."""

    global _issued_candidate
    with _candidate_lock:
        if not isinstance(candidate, CandidatePatch):
            raise RepairError("candidate patch is required")
        if not isinstance(lease, MutationLease) or candidate.mutation_lease is not lease:
            raise RepairError("exact active mutation lease is required")
        try:
            lease.assert_active()
        except CausalityError as error:
            raise RepairError(str(error)) from error
        if _issued_candidate is not candidate:
            raise RepairError("exact issued candidate is required")
        changed_facts = candidate.changed_facts | frozenset(changed_ownership_seams)
        invalidated_proofs = tuple(
            proof
            for proof in proofs
            if changed_facts.intersection(
                (*proof.dynamic_trace, *proof.declared_dependencies, *proof.ownership_seams)
            )
        )
        nodes = [candidate.node_id]
        for neighbor in sorted(candidate.derived_neighbor_node_ids):
            if not neighbor.strip():
                raise RepairError("derived affected neighbor id is required")
            if neighbor not in nodes:
                nodes.append(neighbor)
        for proof in invalidated_proofs:
            if proof.node_id not in nodes:
                nodes.append(proof.node_id)
        for neighbor in direct_affected_neighbors:
            if not neighbor.strip():
                raise RepairError("direct affected neighbor id is required")
            if neighbor not in nodes:
                nodes.append(neighbor)
        plan = RevalidationPlan(
            invalidated_proof_ids=tuple(proof.proof_id for proof in invalidated_proofs),
            revalidation_node_ids=tuple(nodes),
        )
        _issued_candidate = None
        return plan
