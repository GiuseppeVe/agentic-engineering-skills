"""Bounded V5 causal-cone closure and single-mutation coordination."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from threading import RLock
from typing import ClassVar, Literal
from uuid import uuid4

from .canonical import digest_for
from .models import CausalEdge, CausalLead, Observation


class CausalityError(ValueError):
    """A cone cannot safely close, expand, or mutate."""


_HopKind = Literal[
    "failure_action",
    "state_owner",
    "downstream_consumer",
    "adjacent_behavior",
    "config_runtime",
]
_HOP_ORDER: dict[_HopKind, int] = {
    "failure_action": 0,
    "state_owner": 1,
    "downstream_consumer": 2,
    "adjacent_behavior": 3,
    "config_runtime": 4,
}
_DETERMINISTIC_RELATIONS = {
    "provenance",
    "recorded_dependency",
    "exact_invalidation",
}
_SEMANTIC_RELATIONS = {"supports_cause", "supports_symptom"}


@dataclass(frozen=True, slots=True)
class DiscoveryReview:
    reviewer_id: str
    attests_no_material_omission: bool

    def __post_init__(self) -> None:
        if not self.reviewer_id.strip():
            raise CausalityError("Discovery Reviewer identity is required")


@dataclass(frozen=True, slots=True)
class ConeHop:
    hop_id: str
    kind: _HopKind
    lead_id: str | None = None
    edge_id: str | None = None
    ring: int = 0

    def __post_init__(self) -> None:
        if not self.hop_id.strip():
            raise CausalityError("cone hop id is required")
        if type(self.ring) is not int or self.ring < 0:
            raise CausalityError("cone hop ring must be a nonnegative integer")


@dataclass(frozen=True, slots=True)
class FrozenExpansion:
    cone_id: str
    cone_digest: str
    diagnostics_implicate_runtime: bool
    ordered_candidates: tuple[ConeHop, ...]
    selected_hop_id: str | None
    selected_edge_id: str | None
    selected_lead_id: str | None

    def __post_init__(self) -> None:
        if not self.cone_id.strip() or not self.cone_digest.strip():
            raise CausalityError("frozen expansion requires cone identity and digest")

    @property
    def digest(self) -> str:
        return digest_for("graph-v5-frozen-expansion", self)


@dataclass(frozen=True, slots=True)
class MaterialSeamReceipt:
    """Immutable evidence that one required material seam was observed in this cone."""

    seam_id: str
    cone_id: str
    node_id: str
    before_observation_id: str
    after_observation_id: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not all(
            (
                self.seam_id.strip(),
                self.cone_id.strip(),
                self.node_id.strip(),
                self.before_observation_id.strip(),
                self.after_observation_id.strip(),
            )
        ):
            raise CausalityError("material seam receipt requires seam, cone, node, and observation ids")
        if self.before_observation_id == self.after_observation_id:
            raise CausalityError("material seam receipt requires distinct before/after Observation ids")
        if not self.evidence_refs or any(not reference.strip() for reference in self.evidence_refs):
            raise CausalityError("material seam receipt requires nonempty evidence")


@dataclass(frozen=True, slots=True)
class ProbeIsolationReceipt:
    probe_id: str
    cone_id: str
    cone_digest: str
    frozen_expansion_digest: str
    frozen_hop_id: str
    frozen_hop_index: int
    fixture_id: str
    process_id: str
    read_only: bool
    fixture_isolated: bool
    process_isolated: bool
    non_interference_attested: bool

    def __post_init__(self) -> None:
        if not all(
            (
                self.probe_id.strip(),
                self.cone_id.strip(),
                self.cone_digest.strip(),
                self.frozen_expansion_digest.strip(),
                self.frozen_hop_id.strip(),
                self.fixture_id.strip(),
                self.process_id.strip(),
            )
        ):
            raise CausalityError("probe isolation receipt requires ids")
        if type(self.frozen_hop_index) is not int or self.frozen_hop_index < 0:
            raise CausalityError("probe isolation receipt requires a frozen hop index")
        if any(
            type(value) is not bool
            for value in (
                self.read_only,
                self.fixture_isolated,
                self.process_isolated,
                self.non_interference_attested,
            )
        ):
            raise CausalityError("probe isolation receipt scope must be boolean")


@dataclass(frozen=True, slots=True)
class ClosedCausalCone:
    """Marker object. Repair accepts only a cone that passed operational closure."""

    cone: "CausalCone"
    frozen_expansion: FrozenExpansion

    def __post_init__(self) -> None:
        self.cone._validate_closed_handoff(self.frozen_expansion)

    @property
    def cone_id(self) -> str:
        return self.cone.cone_id

    @property
    def node_id(self) -> str:
        return self.cone.node_id


@dataclass(frozen=True, slots=True)
class CausalCone:
    cone_id: str
    node_id: str
    observations: tuple[Observation, ...] = ()
    leads: tuple[CausalLead, ...] = ()
    edges: tuple[CausalEdge, ...] = ()
    required_variant_ids: tuple[str, ...] = ()
    completed_variant_ids: tuple[str, ...] = ()
    required_material_seam_ids: tuple[str, ...] = ()
    material_seam_receipts: tuple[MaterialSeamReceipt, ...] = ()
    discovery_limit_remaining: int = 0
    discovery_review: DiscoveryReview | None = None
    candidates: tuple[ConeHop, ...] = ()

    def __post_init__(self) -> None:
        if not self.cone_id.strip() or not self.node_id.strip():
            raise CausalityError("cone id and Behavioral Node are required")
        if self.discovery_limit_remaining < 0:
            raise CausalityError("discovery limit remaining cannot be negative")

    def with_leads(self, leads: tuple[CausalLead, ...]) -> "CausalCone":
        return replace(self, leads=leads)

    def next_unused_ordinary_hop(
        self,
        examined_hop_ids: frozenset[str],
        *,
        diagnostics_implicate_runtime: bool = False,
    ) -> ConeHop | None:
        """Return one deterministic, unexamined ordinary evidence hop."""

        return next(
            (
                hop
                for hop in self._ordered_hops()
                if (
                    hop.ring == 0
                    and hop.hop_id not in examined_hop_ids
                    and (hop.kind != "config_runtime" or diagnostics_implicate_runtime)
                )
            ),
            None,
        )

    def next_unused_widened_hop(
        self,
        examined_hop_ids: frozenset[str],
        *,
        diagnostics_implicate_runtime: bool = False,
    ) -> ConeHop | None:
        """Return one next-ring hop; never permit arbitrary farther expansion."""

        widened = tuple(
            hop
            for hop in self._ordered_hops()
            if (
                hop.ring > 0
                and hop.hop_id not in examined_hop_ids
                and (hop.kind != "config_runtime" or diagnostics_implicate_runtime)
            )
        )
        if not widened:
            return None
        next_ring = min(hop.ring for hop in widened)
        return next(hop for hop in widened if hop.ring == next_ring)

    def _ordered_hops(self) -> tuple[ConeHop, ...]:
        seen_hop_ids: set[str] = set()
        values: list[ConeHop] = []
        for hop in self.candidates:
            if hop.hop_id in seen_hop_ids:
                raise CausalityError("cone hop ids must be unique")
            seen_hop_ids.add(hop.hop_id)
            values.append(hop)
        return tuple(
            sorted(values, key=lambda hop: (hop.ring, _HOP_ORDER[hop.kind], hop.hop_id))
        )

    @property
    def digest(self) -> str:
        """Digest every immutable fact that can influence causal closure or repair."""

        return digest_for("graph-v5-causal-cone", self)

    def validate_graph(self) -> None:
        observation_ids = {observation.observation_id for observation in self.observations}
        lead_ids = {lead.lead_id for lead in self.leads}
        if len(lead_ids) != len(self.leads):
            raise CausalityError("causal lead ids must be unique")
        for lead in self.leads:
            if lead.source_observation_id not in observation_ids:
                raise CausalityError("every causal lead requires source Observation")
            if lead.disposition != "open" and (
                not lead.evidence_refs
                or any(not reference.strip() for reference in lead.evidence_refs)
            ):
                raise CausalityError("terminal causal lead requires proof-backed disposition")
        for edge in self.edges:
            if edge.from_lead_id not in lead_ids or edge.to_lead_id not in lead_ids:
                raise CausalityError("causal edge references unknown lead")
            if edge.relation in _DETERMINISTIC_RELATIONS and not (edge.basis or "").strip():
                raise CausalityError("deterministic causal edge requires exact basis")
            if edge.relation in _SEMANTIC_RELATIONS and (
                not edge.evidence_refs
                or edge.confidence is None
                or edge.risk is None
                or not edge.requires_independent_attestation
            ):
                raise CausalityError(
                    "semantic causal edge requires evidence, confidence, risk, and independent attestation"
                )

    def close(self, frozen_expansion: FrozenExpansion | object | None = None) -> ClosedCausalCone:
        self._validate_closure()
        if not isinstance(frozen_expansion, FrozenExpansion):
            raise CausalityError("frozen expansion is required for closed causal handoff")
        return ClosedCausalCone(self, frozen_expansion)

    def _validate_closure(self) -> None:
        self.validate_graph()
        missing_variants = set(self.required_variant_ids) - set(self.completed_variant_ids)
        if missing_variants:
            raise CausalityError("required variants are incomplete")
        if any(lead.disposition == "open" for lead in self.leads):
            raise CausalityError("observed-lead queue is not empty")
        self._validate_material_seam_receipts()
        if self.discovery_limit_remaining <= 0:
            raise CausalityError("relevant discovery limit is unavailable")
        if self.discovery_review is None or not self.discovery_review.attests_no_material_omission:
            raise CausalityError("Discovery Reviewer attestation is required")

    def _validate_material_seam_receipts(self) -> None:
        required_seams = set(self.required_material_seam_ids)
        if not required_seams or any(not seam_id.strip() for seam_id in self.required_material_seam_ids):
            raise CausalityError("required material seam identities are required")
        if len(required_seams) != len(self.required_material_seam_ids):
            raise CausalityError("required material seam identities must be unique")
        if not self.material_seam_receipts:
            raise CausalityError("material seam receipts are required")
        observation_by_id = {observation.observation_id: observation for observation in self.observations}
        seen_seams: set[str] = set()
        for receipt in self.material_seam_receipts:
            if not isinstance(receipt, MaterialSeamReceipt):
                raise CausalityError("material seam receipt must be typed")
            if receipt.cone_id != self.cone_id or receipt.node_id != self.node_id:
                raise CausalityError("material seam receipt must bind current cone and Behavioral Node")
            if receipt.seam_id not in required_seams:
                raise CausalityError("material seam receipt does not match a required material seam")
            if receipt.seam_id in seen_seams:
                raise CausalityError("material seam receipt must be unique per required seam")
            seen_seams.add(receipt.seam_id)
            before = observation_by_id.get(receipt.before_observation_id)
            after = observation_by_id.get(receipt.after_observation_id)
            if before is None or after is None:
                raise CausalityError("material seam receipt requires before/after Observation ids present in cone")
            if (
                not before.evidence_refs
                or not after.evidence_refs
                or any(not reference.strip() for reference in (*before.evidence_refs, *after.evidence_refs))
            ):
                raise CausalityError("material seam receipt requires complete before/after Observation evidence")
        if seen_seams != required_seams:
            raise CausalityError("required material seam receipts are incomplete")

    def freeze_expansion(self, *, diagnostics_implicate_runtime: bool) -> FrozenExpansion:
        self.validate_graph()
        candidates: list[ConeHop] = []
        for hop in self._ordered_hops():
            if hop.kind == "config_runtime" and not diagnostics_implicate_runtime:
                continue
            candidates.append(hop)
        ordered = tuple(candidates)
        lead_by_id = {lead.lead_id: lead for lead in self.leads}
        semantic_edges = {
            edge.edge_id: edge for edge in self.edges if edge.relation in _SEMANTIC_RELATIONS
        }
        semantic_incoming = {edge.to_lead_id for edge in semantic_edges.values()}
        semantic_outgoing = {edge.from_lead_id for edge in semantic_edges.values()}
        supported_root_ids = {
            lead.lead_id
            for lead in self.leads
            if lead.disposition == "supported_cause"
            and lead.lead_id in semantic_outgoing
            and lead.lead_id not in semantic_incoming
        }
        if not supported_root_ids:
            supported_root_ids = {
                lead.lead_id
                for lead in self.leads
                if lead.disposition == "supported_cause"
                and lead.lead_id not in semantic_incoming
            }
        selected = next(
            (
                hop
                for hop in ordered
                if hop.lead_id is not None
                and hop.lead_id in supported_root_ids
            ),
            None,
        )
        selected_edge_id = selected.edge_id if selected and selected.edge_id in semantic_edges else None
        return FrozenExpansion(
            cone_id=self.cone_id,
            cone_digest=self.digest,
            diagnostics_implicate_runtime=diagnostics_implicate_runtime,
            ordered_candidates=ordered,
            selected_hop_id=selected.hop_id if selected else None,
            selected_edge_id=selected_edge_id,
            selected_lead_id=selected.lead_id if selected else None,
        )

    def _validate_closed_handoff(self, frozen_expansion: FrozenExpansion | object) -> None:
        self._validate_closure()
        self._validate_frozen_expansion(frozen_expansion, require_supported_root=True)

    def _validate_frozen_expansion(
        self,
        frozen_expansion: FrozenExpansion | object,
        *,
        require_supported_root: bool,
    ) -> None:
        if not isinstance(frozen_expansion, FrozenExpansion):
            raise CausalityError("frozen expansion is required")
        if frozen_expansion.cone_id != self.cone_id:
            raise CausalityError("frozen expansion belongs to another causal cone")
        expected = self.freeze_expansion(
            diagnostics_implicate_runtime=frozen_expansion.diagnostics_implicate_runtime
        )
        if frozen_expansion != expected:
            raise CausalityError("frozen expansion does not match current causal cone")
        if require_supported_root:
            selected_lead_id = frozen_expansion.selected_lead_id
            lead_by_id = {lead.lead_id: lead for lead in self.leads}
            selected = lead_by_id.get(selected_lead_id or "")
            if selected is None or selected.disposition != "supported_cause":
                raise CausalityError("frozen expansion requires a selected supported upstream root")
            selected_hop = next(
                (
                    hop
                    for hop in frozen_expansion.ordered_candidates
                    if hop.hop_id == frozen_expansion.selected_hop_id
                ),
                None,
            )
            semantic_edges = {
                edge.edge_id: edge for edge in self.edges if edge.relation in _SEMANTIC_RELATIONS
            }
            selected_edge = semantic_edges.get(frozen_expansion.selected_edge_id or "")
            if (
                selected_hop is None
                or selected_hop.lead_id != selected_lead_id
                or selected_hop.edge_id != frozen_expansion.selected_edge_id
                or selected_edge is None
                or selected_edge.from_lead_id != selected_lead_id
            ):
                raise CausalityError(
                    "frozen expansion requires a selected semantic edge bound to selected upstream root"
                )

    def authorize_parallel_read_only_probes(
        self,
        frozen_expansion: FrozenExpansion | object,
        receipts: tuple[ProbeIsolationReceipt, ...],
    ) -> None:
        self._validate_frozen_expansion(frozen_expansion, require_supported_root=False)
        assert isinstance(frozen_expansion, FrozenExpansion)
        frozen_hop_indexes = {
            hop.hop_id: index for index, hop in enumerate(frozen_expansion.ordered_candidates)
        }
        probe_ids: set[str] = set()
        fixture_ids: set[str] = set()
        process_ids: set[str] = set()
        for receipt in receipts:
            if not isinstance(receipt, ProbeIsolationReceipt):
                raise CausalityError("parallel probes require typed isolation receipts")
            if receipt.probe_id in probe_ids:
                raise CausalityError("probe ids must be unique")
            probe_ids.add(receipt.probe_id)
            if receipt.fixture_id in fixture_ids or receipt.process_id in process_ids:
                raise CausalityError(
                    "parallel probes require distinct fixture/process isolation"
                )
            fixture_ids.add(receipt.fixture_id)
            process_ids.add(receipt.process_id)
            if receipt.cone_id != self.cone_id:
                raise CausalityError("probe receipt does not bind the frozen causal cone")
            if receipt.cone_digest != self.digest:
                raise CausalityError("probe receipt does not bind immutable causal cone")
            if receipt.frozen_expansion_digest != frozen_expansion.digest:
                raise CausalityError("probe receipt does not bind immutable frozen expansion")
            if frozen_hop_indexes.get(receipt.frozen_hop_id) != receipt.frozen_hop_index:
                raise CausalityError("probe receipt does not bind an ordered frozen hop")
            if not (
                receipt.read_only
                and receipt.fixture_isolated
                and receipt.process_isolated
                and receipt.non_interference_attested
            ):
                raise CausalityError("parallel read-only probes require fixture/process isolation receipt")


@dataclass(frozen=True, slots=True)
class MutationLease:
    cone_id: str
    token: str
    _manager: "MutationLeaseManager" = field(repr=False, compare=False)

    def assert_active(self) -> None:
        self._manager.assert_active(self)


class MutationLeaseManager:
    """One process-local mutation stream; probes remain separate and read-only."""

    _lock: ClassVar[RLock] = RLock()
    _active: ClassVar[MutationLease | None] = None

    def acquire(self, cone_id: str) -> MutationLease:
        if not cone_id.strip():
            raise CausalityError("mutation lease cone id is required")
        with MutationLeaseManager._lock:
            if MutationLeaseManager._active is not None:
                raise CausalityError("active mutation lease already exists")
            lease = MutationLease(cone_id=cone_id, token=uuid4().hex, _manager=self)
            MutationLeaseManager._active = lease
            return lease

    def assert_active(self, lease: MutationLease) -> None:
        with MutationLeaseManager._lock:
            if lease._manager is not self or MutationLeaseManager._active is not lease:
                raise CausalityError("active mutation lease is required")

    def release(self, lease: MutationLease) -> None:
        with MutationLeaseManager._lock:
            self.assert_active(lease)
            MutationLeaseManager._active = None
