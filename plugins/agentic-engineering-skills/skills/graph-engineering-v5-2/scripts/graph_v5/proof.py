"""Proof ladder and isolated-role contracts for V5 repairs."""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from threading import RLock
from typing import Literal

from .canonical import canonical_json_bytes, digest_bytes, digest_for
from .causality import CausalCone, ClosedCausalCone
from .models import (
    FrozenDerivedSpine,
    ProofResult,
    ProofSpec,
    RoleManifest,
    RunHead,
    RunState,
    V52RunState,
)


class ProofLadderError(ValueError):
    """A required independent proof or binding is absent or unsafe."""


def _authority_digests(state: RunState) -> tuple[str, str, str]:
    spine = state.facts.derived_spine
    if spine is None:
        raise ProofLadderError("proof authority requires persisted Derived Spine")
    spine.bind_trajectory(state.trajectory)
    return state.trajectory_digest, spine.digest, spine.landmark_mapping_digest


RoleName = Literal[
    "patch_executor", "discovery_reviewer", "proof_curator", "validator", "semantic_reviewer"
]


@dataclass(frozen=True, slots=True)
class _IssuedRoleProvenance:
    """Immutable issuer snapshot; never trust mutable dispatched objects after issuance."""

    manifest_id: str
    manifest_digest: str
    run_id: str
    role: str
    goal_digest: str
    cone_digest: str
    base_revision: str
    run_head_digest: str
    environment_digest: str
    fixture_digest: str
    proof_spec_digest: str
    permitted_output_schema: str
    spine_digest: str
    context_id: str
    issued_mode: str
    trajectory_digest: str
    derived_spine_digest: str
    landmark_mapping_digest: str
    controller_capability: Literal[False]
    curator_oracle_digest: None
    manifest: object
    manifest_snapshot: bytes
    dispatch_snapshot: tuple[tuple[str, object], ...]


@dataclass(frozen=True, slots=True)
class _IssuedRoleOutputProvenance:
    """Immutable import snapshot; mutable output objects never carry authority."""

    output: object
    dispatch: object
    manifest: RoleManifest
    manifest_id: str
    manifest_digest: str
    raw_payload: bytes
    raw_digest: str
    environment_digest: str
    permitted_output_schema: str
    output_snapshot: tuple[tuple[str, object], ...]
    dispatch_snapshot: tuple[tuple[str, object], ...]
    manifest_snapshot: bytes


_ISSUED_ROLE_OUTPUTS: dict[int, "ImportedRoleOutput"] = {}
_ISSUED_ROLE_OUTPUT_PROVENANCE: dict[int, _IssuedRoleOutputProvenance] = {}
_ISSUED_ROLE_DISPATCHES: dict[str, RoleDispatch] = {}
_ISSUED_ROLE_DISPATCHES_BY_ID: dict[int, RoleDispatch] = {}
_ISSUED_ROLE_RUNS: dict[str, str] = {}
_ISSUED_ROLE_PROVENANCE: dict[str, _IssuedRoleProvenance] = {}
_ISSUED_ROLE_PROVENANCE_BY_DISPATCH_ID: dict[int, _IssuedRoleProvenance] = {}
_ISSUED_ROLE_IDENTITIES: set[tuple[str, str]] = set()
_ISSUED_ROLE_CONTEXTS: set[tuple[str, str]] = set()
_IMPORTED_ROLE_MANIFEST_IDS: set[str] = set()
_CONSUMED_ROLE_OUTPUT_IDS: set[int] = set()
_RESERVED_ROLE_OUTPUT_IDS: set[int] = set()
_ROLE_ISSUER_LOCK = RLock()


def _snapshot_dataclass_fields(value: object) -> tuple[tuple[str, object], ...]:
    """Snapshot every dataclass field without retaining mutable authority values."""

    snapshot: list[tuple[str, object]] = []
    for field in fields(value):
        field_value = getattr(value, field.name)
        if isinstance(field_value, (str, int, bool, bytes, type(None))):
            snapshot.append((field.name, field_value))
        else:
            snapshot.append((field.name, ("identity", id(field_value))))
    return tuple(snapshot)


def _snapshot_manifest(manifest: RoleManifest) -> bytes:
    """Canonical immutable copy of every current RoleManifest field."""

    return canonical_json_bytes(manifest.model_dump(mode="json"))


def _require_unchanged_issued_dispatch(dispatch: "RoleDispatch") -> _IssuedRoleProvenance:
    """Reject any post-issuance mutation before importing a role output."""

    if not isinstance(dispatch.manifest, RoleManifest):
        raise ProofLadderError("role output must bind exact issued role dispatch")
    with _ROLE_ISSUER_LOCK:
        issued_dispatch = _ISSUED_ROLE_DISPATCHES_BY_ID.get(id(dispatch))
        provenance = _ISSUED_ROLE_PROVENANCE_BY_DISPATCH_ID.get(id(dispatch))
    if (
        issued_dispatch is not dispatch
        or provenance is None
        or provenance.manifest is not dispatch.manifest
        or provenance.dispatch_snapshot != _snapshot_dataclass_fields(dispatch)
        or provenance.manifest_snapshot != _snapshot_manifest(dispatch.manifest)
    ):
        raise ProofLadderError("role output must bind exact issued role dispatch")
    return provenance


def is_issuer_registered_output(output: object) -> bool:
    with _ROLE_ISSUER_LOCK:
        return isinstance(output, ImportedRoleOutput) and _ISSUED_ROLE_OUTPUTS.get(id(output)) is output


def consume_issuer_registered_output(output: "ImportedRoleOutput") -> None:
    """Consume one role output where a later lifecycle stage requires one-shot authority."""

    consume_issuer_registered_outputs((output,))


def consume_issuer_registered_outputs(outputs: tuple["ImportedRoleOutput", ...]) -> None:
    """Atomically consume exactly one complete set of validated role outputs."""

    with _ROLE_ISSUER_LOCK:
        output_ids = tuple(id(output) for output in outputs)
        if len(output_ids) != len(set(output_ids)):
            raise ProofLadderError("proof ladder reuses role output authority")
        for output in outputs:
            if _ISSUED_ROLE_OUTPUTS.get(id(output)) is not output:
                raise ProofLadderError("role output must be issuer-registered, not controller-generated")
            if id(output) in _CONSUMED_ROLE_OUTPUT_IDS:
                raise ProofLadderError("fresh role output is already consumed")
            if id(output) in _RESERVED_ROLE_OUTPUT_IDS:
                raise ProofLadderError("fresh role output authority is reserved")
        _CONSUMED_ROLE_OUTPUT_IDS.update(output_ids)


def reserve_issuer_registered_outputs(
    outputs: tuple["ImportedRoleOutput", ...],
) -> tuple[int, ...]:
    """Claim fresh role authority until its matching durable transaction resolves."""

    with _ROLE_ISSUER_LOCK:
        output_ids = tuple(id(output) for output in outputs)
        if len(output_ids) != len(set(output_ids)):
            raise ProofLadderError("proof ladder reuses role output authority")
        for output in outputs:
            output_id = id(output)
            if _ISSUED_ROLE_OUTPUTS.get(output_id) is not output:
                raise ProofLadderError("role output must be issuer-registered, not controller-generated")
            if output_id in _CONSUMED_ROLE_OUTPUT_IDS:
                raise ProofLadderError("fresh role output is already consumed")
            if output_id in _RESERVED_ROLE_OUTPUT_IDS:
                raise ProofLadderError("fresh role output authority is reserved")
        _RESERVED_ROLE_OUTPUT_IDS.update(output_ids)
        return output_ids


def commit_issuer_registered_output_reservation(output_ids: tuple[int, ...]) -> None:
    """Finalize a previously reserved complete role-output authority set."""

    with _ROLE_ISSUER_LOCK:
        if not output_ids or len(output_ids) != len(set(output_ids)):
            raise ProofLadderError("proof ladder reservation is invalid")
        if any(output_id not in _RESERVED_ROLE_OUTPUT_IDS for output_id in output_ids):
            raise ProofLadderError("proof ladder reservation is not active")
        _RESERVED_ROLE_OUTPUT_IDS.difference_update(output_ids)
        _CONSUMED_ROLE_OUTPUT_IDS.update(output_ids)


def rollback_issuer_registered_output_reservation(output_ids: tuple[int, ...]) -> None:
    """Release a failed durable transaction without consuming role authority."""

    with _ROLE_ISSUER_LOCK:
        if any(output_id not in _RESERVED_ROLE_OUTPUT_IDS for output_id in output_ids):
            raise ProofLadderError("proof ladder reservation is not active")
        _RESERVED_ROLE_OUTPUT_IDS.difference_update(output_ids)


def require_exact_issuer_output(
    output: "ImportedRoleOutput",
    *,
    state: RunState,
    cone: CausalCone,
    proof_spec: ProofSpec,
    role: RoleName,
    permitted_output_schema: str,
    issued_mode: str,
    context_id: str | None = None,
) -> None:
    """Require one process-issued output bound to this exact runtime authority context."""

    run_head = state.facts.run_head
    environment = state.facts.environment
    if run_head is None or environment is None:
        raise ProofLadderError("exact role output requires sealed Run Head and environment")
    if not is_issuer_registered_output(output):
        raise ProofLadderError("role output must be issuer-registered, not controller-generated")
    trajectory_digest, derived_spine_digest, landmark_mapping_digest = _authority_digests(state)
    with _ROLE_ISSUER_LOCK:
        output_provenance = _ISSUED_ROLE_OUTPUT_PROVENANCE.get(id(output))
        consumed = id(output) in _CONSUMED_ROLE_OUTPUT_IDS
    if (
        output_provenance is None
        or output_provenance.output is not output
        or not isinstance(output.dispatch, RoleDispatch)
        or output_provenance.dispatch is not output.dispatch
        or not isinstance(output.dispatch.manifest, RoleManifest)
        or output_provenance.manifest is not output.dispatch.manifest
    ):
        raise ProofLadderError("role output manifest issuer provenance does not bind exact current proof context")
    manifest = output.dispatch.manifest
    with _ROLE_ISSUER_LOCK:
        issued_dispatch = _ISSUED_ROLE_DISPATCHES_BY_ID.get(id(output_provenance.dispatch))
        issued_run_id = _ISSUED_ROLE_RUNS.get(output_provenance.manifest_id)
        provenance = _ISSUED_ROLE_PROVENANCE_BY_DISPATCH_ID.get(id(output_provenance.dispatch))
    if (
        issued_dispatch is not output.dispatch
        or issued_run_id != state.run_id
        or provenance is None
        or consumed
        or output_provenance.output_snapshot != _snapshot_dataclass_fields(output)
        or output_provenance.dispatch_snapshot != _snapshot_dataclass_fields(output.dispatch)
        or output_provenance.manifest_snapshot != _snapshot_manifest(manifest)
        or provenance.dispatch_snapshot != _snapshot_dataclass_fields(output.dispatch)
        or provenance.manifest_snapshot != _snapshot_manifest(manifest)
        or provenance.manifest is not manifest
        or output_provenance.manifest_id != manifest.manifest_id
        or output_provenance.manifest_digest != output.issued_manifest_digest
        or output_provenance.manifest_digest != manifest.digest
        or output.issued_manifest_digest != manifest.digest
        or output_provenance.raw_payload != output.raw_payload
        or output_provenance.raw_digest != output.raw_digest
        or digest_bytes("role-output", output.raw_payload) != output.raw_digest
        or output_provenance.environment_digest != output.environment_digest
        or output_provenance.permitted_output_schema != manifest.permitted_output_schema
        or output.dispatch.controller_capability is not provenance.controller_capability
        or output.dispatch.curator_oracle_digest != provenance.curator_oracle_digest
        or provenance.manifest_id != output_provenance.manifest_id
        or provenance.manifest_digest != output_provenance.manifest_digest
        or provenance.role != role
        or provenance.goal_digest != trajectory_digest
        or provenance.cone_digest != cone.digest
        or provenance.base_revision != run_head.revision
        or provenance.run_head_digest != run_head.digest
        or provenance.environment_digest != environment.digest
        or provenance.fixture_digest != state.fixture_intent_digest
        or provenance.proof_spec_digest != proof_spec.digest
        or provenance.permitted_output_schema != permitted_output_schema
        or provenance.spine_digest != derived_spine_digest
        or provenance.trajectory_digest != trajectory_digest
        or provenance.derived_spine_digest != derived_spine_digest
        or provenance.landmark_mapping_digest != landmark_mapping_digest
        or proof_spec.trajectory_digest != trajectory_digest
        or proof_spec.derived_spine_digest != derived_spine_digest
        or proof_spec.landmark_mapping_digest != landmark_mapping_digest
        or (context_id is not None and provenance.context_id != context_id)
        or provenance.issued_mode != issued_mode
    ):
        raise ProofLadderError("role output manifest issuer provenance does not bind exact current proof context")
    decoded = _decode_canonical_role_payload(output.raw_payload)
    _validate_permitted_output_schema(output_provenance.permitted_output_schema, decoded)


def _decode_canonical_role_payload(raw_payload: bytes) -> dict[str, object]:
    try:
        decoded = json.loads(raw_payload.decode("utf-8"))
    except (AttributeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProofLadderError("role output must be canonical JSON") from exc
    if not isinstance(decoded, dict) or canonical_json_bytes(decoded) != raw_payload:
        raise ProofLadderError("role output must be canonical JSON")
    return decoded


def _validate_permitted_output_schema(schema: str, payload: dict[str, object]) -> None:
    if schema == "proof-role-output-v1":
        if set(payload) - {"decision", "scope"}:
            raise ProofLadderError("role output does not satisfy permitted output schema")
        if not isinstance(payload.get("decision"), str) or not payload["decision"].strip():
            raise ProofLadderError("role output does not satisfy permitted output schema")
        if "scope" in payload and (
            not isinstance(payload["scope"], str) or not payload["scope"].strip()
        ):
            raise ProofLadderError("role output does not satisfy permitted output schema")
        return
    if schema == "final-replay-semantic-output-v1":
        required = {"decision", "scope", "replay_bundle_digest", "replay_result_digest"}
        if set(payload) != required or payload.get("decision") != "approved":
            raise ProofLadderError("role output does not satisfy permitted output schema")
        if any(not isinstance(payload[name], str) or not payload[name].strip() for name in required - {"decision"}):
            raise ProofLadderError("role output does not satisfy permitted output schema")
        return
    raise ProofLadderError("role manifest has unknown permitted output schema")


@dataclass(frozen=True, slots=True)
class RoleDispatch:
    """One fresh, capability-free role context bound to current Run Head."""

    manifest: RoleManifest
    spine_digest: str
    context_id: str
    issued_mode: str
    controller_capability: Literal[False] = False
    curator_oracle_digest: None = None

    def __post_init__(self) -> None:
        if self.controller_capability is not False:
            raise ProofLadderError("role dispatch may not receive controller capability")
        if not self.context_id.strip():
            raise ProofLadderError("fresh role context is required")
        if not self.issued_mode.strip():
            raise ProofLadderError("role dispatch must bind issued runtime mode")
        if self.manifest.role == "patch_executor" and self.curator_oracle_digest is not None:
            raise ProofLadderError("executor may not access Curator oracle")


@dataclass(frozen=True, slots=True)
class ImportedRoleOutput:
    """Exact role bytes plus manifest and environment attestations."""

    dispatch: RoleDispatch
    raw_payload: bytes
    raw_digest: str
    environment_digest: str
    issued_manifest_digest: str

    def __post_init__(self) -> None:
        if digest_bytes("role-output", self.raw_payload) != self.raw_digest:
            raise ProofLadderError("role output bytes do not match imported digest")
        if self.issued_manifest_digest != self.dispatch.manifest.digest:
            raise ProofLadderError("role output manifest binding changed after import")
        if self.environment_digest != self.dispatch.manifest.environment_digest:
            raise ProofLadderError("role output environment attestation does not match manifest")
        decoded = _decode_canonical_role_payload(self.raw_payload)
        _validate_permitted_output_schema(self.dispatch.manifest.permitted_output_schema, decoded)

    @property
    def manifest_digest(self) -> str:
        return self.issued_manifest_digest

    @property
    def decision(self) -> str:
        value = json.loads(self.raw_payload.decode("utf-8")).get("decision")
        if not isinstance(value, str) or not value:
            raise ProofLadderError("role output requires a decision")
        return value


class RoleRegistry:
    """Issues one fresh identity/context pair and imports unmodified role bytes."""

    def __init__(self) -> None:
        pass

    def issue(
        self,
        *,
        state: RunState,
        cone: CausalCone,
        proof_spec: ProofSpec,
        role: RoleName,
        identity: str,
        context_id: str,
        attempt: int,
        permitted_output_schema: str,
    ) -> RoleDispatch:
        if role not in {
            "patch_executor", "discovery_reviewer", "proof_curator", "validator", "semantic_reviewer"
        }:
            raise ProofLadderError("controller capability cannot issue or satisfy independent role")
        normalized_identity = identity.strip().casefold() if isinstance(identity, str) else ""
        if not normalized_identity or normalized_identity.startswith(("controller", "self")):
            raise ProofLadderError("controller capability cannot issue or satisfy independent role")
        normalized_context = context_id.strip() if isinstance(context_id, str) else ""
        if not normalized_context:
            raise ProofLadderError("fresh role context is required for every role attempt")
        if attempt < 1 or not permitted_output_schema.strip():
            raise ProofLadderError("role attempt and permitted output schema are required")
        run_head = state.facts.run_head
        environment = state.facts.environment
        if run_head is None or environment is None:
            raise ProofLadderError("independent role requires sealed Run Head and environment")
        if proof_spec.node_id != cone.node_id:
            raise ProofLadderError("role manifest ProofSpec must target current Behavioral Node")
        trajectory_digest, derived_spine_digest, landmark_mapping_digest = _authority_digests(state)
        if (
            proof_spec.trajectory_digest != trajectory_digest
            or proof_spec.derived_spine_digest != derived_spine_digest
            or proof_spec.landmark_mapping_digest != landmark_mapping_digest
        ):
            raise ProofLadderError("ProofSpec does not bind current trajectory authority")
        manifest = RoleManifest(
            manifest_id=digest_for(
                "proof-role-manifest-id",
                {
                    "run_id": state.run_id,
                    "role": role,
                    "identity": identity,
                    "context_id": context_id,
                    "attempt": attempt,
                    "cone_digest": cone.digest,
                    "proof_spec_digest": proof_spec.digest,
                    "run_head_digest": run_head.digest,
                },
            ),
            role=role,
            identity=identity,
            attempt=attempt,
            goal_digest=trajectory_digest,
            cone_digest=cone.digest,
            base_revision=run_head.revision,
            run_head_digest=run_head.digest,
            environment_digest=environment.digest,
            fixture_digest=state.fixture_intent_digest,
            proof_spec_digest=proof_spec.digest,
            permitted_output_schema=permitted_output_schema,
            trajectory_digest=trajectory_digest,
            derived_spine_digest=derived_spine_digest,
            landmark_mapping_digest=landmark_mapping_digest,
        )
        dispatch = RoleDispatch(
            manifest=manifest,
            spine_digest=derived_spine_digest,
            context_id=context_id,
            issued_mode=state.mode,
        )
        provenance = _IssuedRoleProvenance(
            manifest_id=manifest.manifest_id,
            manifest_digest=manifest.digest,
            run_id=state.run_id,
            role=manifest.role,
            goal_digest=manifest.goal_digest,
            cone_digest=manifest.cone_digest,
            base_revision=manifest.base_revision,
            run_head_digest=manifest.run_head_digest,
            environment_digest=manifest.environment_digest,
            fixture_digest=manifest.fixture_digest,
            proof_spec_digest=manifest.proof_spec_digest,
            permitted_output_schema=manifest.permitted_output_schema,
            spine_digest=dispatch.spine_digest,
            context_id=dispatch.context_id,
            issued_mode=dispatch.issued_mode,
            trajectory_digest=trajectory_digest,
            derived_spine_digest=derived_spine_digest,
            landmark_mapping_digest=landmark_mapping_digest,
            controller_capability=dispatch.controller_capability,
            curator_oracle_digest=dispatch.curator_oracle_digest,
            manifest=manifest,
            manifest_snapshot=_snapshot_manifest(manifest),
            dispatch_snapshot=_snapshot_dataclass_fields(dispatch),
        )
        with _ROLE_ISSUER_LOCK:
            identity_key = (state.run_id, normalized_identity)
            context_key = (state.run_id, normalized_context)
            if identity_key in _ISSUED_ROLE_IDENTITIES:
                raise ProofLadderError("fresh role identity is required for every role attempt")
            if context_key in _ISSUED_ROLE_CONTEXTS:
                raise ProofLadderError("fresh role context is required for every role attempt")
            if manifest.manifest_id in _ISSUED_ROLE_DISPATCHES:
                raise ProofLadderError("fresh role manifest is already issued")
            _ISSUED_ROLE_IDENTITIES.add(identity_key)
            _ISSUED_ROLE_CONTEXTS.add(context_key)
            _ISSUED_ROLE_DISPATCHES[manifest.manifest_id] = dispatch
            _ISSUED_ROLE_DISPATCHES_BY_ID[id(dispatch)] = dispatch
            _ISSUED_ROLE_RUNS[manifest.manifest_id] = state.run_id
            _ISSUED_ROLE_PROVENANCE[manifest.manifest_id] = provenance
            _ISSUED_ROLE_PROVENANCE_BY_DISPATCH_ID[id(dispatch)] = provenance
        return dispatch

    def import_unchanged(
        self,
        dispatch: RoleDispatch,
        raw_payload: bytes,
        *,
        environment_digest: str,
    ) -> ImportedRoleOutput:
        if not isinstance(dispatch, RoleDispatch) or dispatch.controller_capability is not False:
            raise ProofLadderError("controller-generated role result is forbidden")
        provenance = _require_unchanged_issued_dispatch(dispatch)
        with _ROLE_ISSUER_LOCK:
            if provenance.manifest_id in _IMPORTED_ROLE_MANIFEST_IDS:
                raise ProofLadderError("role manifest may import one unchanged output")
        decoded = _decode_canonical_role_payload(raw_payload)
        _validate_permitted_output_schema(dispatch.manifest.permitted_output_schema, decoded)
        result = ImportedRoleOutput(
            dispatch=dispatch,
            raw_payload=raw_payload,
            raw_digest=digest_bytes("role-output", raw_payload),
            environment_digest=environment_digest,
            issued_manifest_digest=dispatch.manifest.digest,
        )
        output_provenance = _IssuedRoleOutputProvenance(
            output=result,
            dispatch=dispatch,
            manifest=dispatch.manifest,
            manifest_id=dispatch.manifest.manifest_id,
            manifest_digest=dispatch.manifest.digest,
            raw_payload=raw_payload,
            raw_digest=result.raw_digest,
            environment_digest=environment_digest,
            permitted_output_schema=dispatch.manifest.permitted_output_schema,
            output_snapshot=_snapshot_dataclass_fields(result),
            dispatch_snapshot=_snapshot_dataclass_fields(dispatch),
            manifest_snapshot=_snapshot_manifest(dispatch.manifest),
        )
        with _ROLE_ISSUER_LOCK:
            if provenance.manifest_id in _IMPORTED_ROLE_MANIFEST_IDS:
                raise ProofLadderError("role manifest may import one unchanged output")
            _ISSUED_ROLE_OUTPUTS[id(result)] = result
            _ISSUED_ROLE_OUTPUT_PROVENANCE[id(result)] = output_provenance
            _IMPORTED_ROLE_MANIFEST_IDS.add(provenance.manifest_id)
        return result


@dataclass(frozen=True, slots=True)
class FinalReplaySnapshot:
    goal_digest: str
    spine_digest: str
    trajectory_digest: str
    derived_spine_digest: str
    landmark_mapping_digest: str
    run_head_revision: str
    run_head_digest: str
    environment_digest: str
    fixture_digest: str
    limits_digest: str
    graph_revision: int
    fixture_id: str = ""
    fixture_adapter_id: str = ""

    @classmethod
    def from_state(cls, state: RunState, *, graph_revision: int) -> "FinalReplaySnapshot":
        run_head = state.facts.run_head
        environment = state.facts.environment
        if run_head is None or environment is None:
            raise ProofLadderError("final replay requires sealed Run Head and environment")
        trajectory_digest, derived_spine_digest, landmark_mapping_digest = _authority_digests(state)
        return cls(
            goal_digest=trajectory_digest,
            spine_digest=derived_spine_digest,
            trajectory_digest=trajectory_digest,
            derived_spine_digest=derived_spine_digest,
            landmark_mapping_digest=landmark_mapping_digest,
            run_head_revision=run_head.revision,
            run_head_digest=run_head.digest,
            environment_digest=environment.digest,
            fixture_digest=state.fixture_intent_digest,
            limits_digest=digest_for("resolved-run-limits", state.limits),
            graph_revision=graph_revision,
        )

    @classmethod
    def from_frozen(
        cls,
        frozen: FrozenDerivedSpine,
        *,
        limits_digest: str,
    ) -> "FinalReplaySnapshot":
        """Project replay inputs from immutable freeze, never mutable state."""

        return cls(
            goal_digest=frozen.trajectory_digest,
            spine_digest=frozen.derived_spine_digest,
            trajectory_digest=frozen.trajectory_digest,
            derived_spine_digest=frozen.derived_spine_digest,
            landmark_mapping_digest=frozen.landmark_mapping_digest,
            run_head_revision=frozen.run_head.revision,
            run_head_digest=frozen.run_head.digest,
            environment_digest=frozen.environment.digest,
            fixture_digest=frozen.fixture_digest,
            limits_digest=limits_digest,
            graph_revision=frozen.graph_revision,
            fixture_id=frozen.fixture_id,
            fixture_adapter_id=frozen.fixture_adapter_id,
        )

    @property
    def digest(self) -> str:
        return digest_for("final-replay-snapshot", self)


@dataclass(frozen=True, slots=True)
class RealFinalReplaySnapshot:
    """Immutable V5.2 replay authority; live bridge state never replaces it."""

    run_id: str
    adapter_manifest_digest: str
    provider_authority_digest: str
    run_head_digest: str
    environment_snapshot_digest: str
    target_identity_digest: str
    lease_receipt_digests: tuple[str, ...]
    egress_receipt_digest: str | None
    evidence_policy_digest: str
    baseline_spine_digest: str
    baseline_node_digests: tuple[str, ...]
    exploration_delta_digests: tuple[str, ...]
    node_completion_digests: tuple[str, ...]
    decision_consumption_digests: tuple[str, ...]
    executed_node_digests: tuple[str, ...]
    supervisor_receipt_digests: tuple[str, ...]
    adapter_interface_digest: str
    operation_intent_digests: tuple[str, ...]
    operation_receipt_digests: tuple[str, ...]

    @classmethod
    def from_state(
        cls,
        state: V52RunState,
        *,
        environment_snapshot: object,
        manifest: object | None = None,
    ) -> "RealFinalReplaySnapshot":
        """Build replay authority from store bytes after exact receipt reconciliation."""

        from .environment import EnvironmentSnapshot

        if not isinstance(environment_snapshot, EnvironmentSnapshot):
            raise ProofLadderError("real final replay requires sealed EnvironmentSnapshot")
        from .adapters.manifest import AdapterManifest
        from .adapters.host_registry import HostProviderError, resolve_host_provider
        from .adapters.registry import AdapterManifestError, resolve_descriptor
        from .environment import EnvironmentPreflightError
        from .models import (
            AdmittedProviderAuthority,
            BaselineSpineAuthority,
            ExplorationDelta,
            Observation,
            PersistedNodeExecutionAuthority,
            RealNodeCompletion,
            RealSystemDecisionConsumption,
            derive_persisted_external_operation_intent,
            real_system_decision_target_key,
            validate_pending_real_system_decision_amendment,
        )

        head = state.facts.run_head
        baseline = state.facts.baseline_spine
        if (
            head is None
            or state.facts.environment_snapshot_digest != environment_snapshot.digest
            or head.environment_snapshot_digest != environment_snapshot.digest
            or head.manifest_digest != state.adapter_manifest_digest
            or environment_snapshot.adapter_manifest_digest != state.adapter_manifest_digest
            or environment_snapshot.target_identity_digest
            != state.trajectory.execution_envelope.target_identity_digest
        ):
            raise ProofLadderError("real final replay authority does not bind sealed environment")
        if baseline is None:
            raise ProofLadderError("real final replay requires immutable baseline spine")
        try:
            canonical_baseline = BaselineSpineAuthority.from_nodes(
                state,
                head,
                manifest,
                environment_snapshot,
                baseline.nodes,
                baseline.baseline_proposals,
            )
        except (TypeError, ValueError) as exc:
            raise ProofLadderError("real final replay baseline spine is invalid") from exc
        if canonical_baseline != baseline or tuple(node.digest for node in baseline.nodes) != baseline.node_digests:
            raise ProofLadderError("real final replay baseline spine bytes drifted")
        known_nodes = {node.node_id: node for node in baseline.nodes}
        prior_deltas: dict[str, ExplorationDelta] = {}
        for delta in state.facts.exploration_deltas:
            authority = (
                baseline
                if delta.parent_node_id in baseline.node_ids
                else prior_deltas.get(delta.parent_node_id)
            )
            if authority is None:
                raise ProofLadderError("real final replay exploration parent is invalid")
            try:
                canonical_delta = ExplorationDelta.from_node(
                    node=delta.node,
                    parent_node_id=delta.parent_node_id,
                    evidence_refs=delta.evidence_refs,
                    authority=authority,
                    proposal=delta.proposal,
                )
            except (TypeError, ValueError) as exc:
                raise ProofLadderError("real final replay exploration authority is invalid") from exc
            if canonical_delta != delta or delta.node.node_id in known_nodes:
                raise ProofLadderError("real final replay exploration authority drifted")
            known_nodes[delta.node.node_id] = delta.node
            prior_deltas[delta.node.node_id] = delta
        if not isinstance(manifest, AdapterManifest):
            raise ProofLadderError("real final replay requires admitted AdapterManifest")
        provider = state.facts.provider_authority
        if not isinstance(provider, AdmittedProviderAuthority):
            raise ProofLadderError("real final replay provider authority is invalid")
        try:
            descriptor = resolve_descriptor(manifest)
            host_provider = resolve_host_provider(manifest.adapter_id)
            admitted_snapshot = EnvironmentSnapshot.from_admitted_authority(
                manifest=manifest,
                target_identity_digest=state.trajectory.execution_envelope.target_identity_digest,
                supervisor_receipts=state.facts.supervisor_receipts,
                egress_receipt=state.facts.egress_receipt,
            )
        except (
            AdapterManifestError,
            EnvironmentPreflightError,
            HostProviderError,
            TypeError,
            ValueError,
        ) as exc:
            raise ProofLadderError("real final replay receipt or registry authority is invalid") from exc
        if (
            manifest.digest != state.adapter_manifest_digest
            or admitted_snapshot != environment_snapshot
            or descriptor.interface_digest != manifest.adapter_interface_digest
            or provider.adapter_id != manifest.adapter_id
            or provider.provider_id != host_provider.provider_id
            or provider.source_identity_digest
            != state.trajectory.execution_envelope.target_identity_digest
        ):
            raise ProofLadderError("real final replay receipt or registry authority drifted")
        receipts = {
            receipt.operation_id: receipt
            for receipt in state.facts.external_operation_receipts
            if receipt.status != "unknown"
        }
        unresolved = tuple(
            intent.operation_id
            for intent in state.facts.external_operation_intents
            if intent.operation_id not in receipts
            or receipts[intent.operation_id].status == "unknown"
        )
        if unresolved:
            raise ProofLadderError("real final replay requires settled ExternalOperationIntent receipts")
        if any(intent.node_id not in known_nodes for intent in state.facts.external_operation_intents):
            raise ProofLadderError("real final replay executed node is outside authority")
        intents_by_operation = {
            intent.operation_id: intent for intent in state.facts.external_operation_intents
        }
        if any(
            (intent := intents_by_operation.get(receipt.operation_id)) is None
            or receipt.run_id != intent.run_id
            or receipt.manifest_digest != intent.manifest_digest
            or receipt.run_head_digest != intent.run_head_digest
            or receipt.idempotency_key != intent.idempotency_key
            for receipt in state.facts.external_operation_receipts
        ):
            raise ProofLadderError("real final replay receipt does not bind executed authority")
        baseline_proposals = {
            item.proposal.node_id: item for item in baseline.baseline_proposals
        }
        exploration_by_node = {
            item.node.node_id: item for item in state.facts.exploration_deltas
        }
        for intent in state.facts.external_operation_intents:
            if intent.node_id in known_nodes and intent.node_id in baseline_proposals:
                authority = PersistedNodeExecutionAuthority.baseline(
                    known_nodes[intent.node_id],
                    baseline_proposals[intent.node_id],
                )
            elif intent.node_id in exploration_by_node:
                authority = PersistedNodeExecutionAuthority.exploration(
                    exploration_by_node[intent.node_id]
                )
            else:
                raise ProofLadderError("real final replay intent lacks persisted proposal budget")
            try:
                expected_intent = derive_persisted_external_operation_intent(
                    state, authority
                )
            except ValueError as exc:
                raise ProofLadderError(
                    "real final replay intent lacks persisted proposal budget"
                ) from exc
            if intent != expected_intent:
                raise ProofLadderError(
                    "real final replay intent does not bind exact proposal budget authority"
                )
        completions = state.facts.node_completions
        if any(not isinstance(item, RealNodeCompletion) for item in completions):
            raise ProofLadderError("real final replay node completion is invalid")
        completed_node_ids = {item.node_id for item in completions}
        if len(completed_node_ids) != len(completions) or any(
            item.node_id not in known_nodes
            or item.run_id != state.run_id
            or item.run_head_digest != head.digest
            for item in completions
        ):
            raise ProofLadderError("real final replay completion does not bind sealed node")
        for completion in completions:
            node = known_nodes[completion.node_id]
            if completion.kind == "verification":
                observation = completion.verification_observation
                if (
                    node.action_kind != "verify_only"
                    or not isinstance(observation, Observation)
                    or observation.kind != "behavioral"
                    or observation.node_id != node.source_anchor_id
                    or observation.run_head_digest != head.digest
                    or observation.evidence_refs != completion.evidence_refs
                    or observation.observed_state not in node.expected_after
                ):
                    raise ProofLadderError("real final replay verification completion is forged")
            else:
                receipt = receipts.get(completion.operation_id or "")
                if (
                    node.action_kind == "verify_only"
                    or receipt is None
                    or receipt.status != "succeeded"
                    or receipt.evidence_refs != completion.evidence_refs
                ):
                    raise ProofLadderError("real final replay external completion is forged")
        pending_by_digest = {
            pending.digest: pending
            for pending in state.facts.pending_real_system_decisions
        }
        pending_target_keys = tuple(
            real_system_decision_target_key(pending)
            for pending in pending_by_digest.values()
        )
        if len(pending_target_keys) != len(set(pending_target_keys)):
            raise ProofLadderError("real final replay pending decision targets conflict")
        if any(
            pending.run_id != state.run_id
            or pending.run_head_digest != head.digest
            or pending.authority_digest != baseline.digest
            for pending in pending_by_digest.values()
        ):
            raise ProofLadderError("real final replay pending decision does not bind current authority")
        try:
            for pending in pending_by_digest.values():
                validate_pending_real_system_decision_amendment(
                    state, manifest, pending
                )
        except ValueError as exc:
            raise ProofLadderError(
                "real final replay pending decision amendment is invalid"
            ) from exc
        consumptions = state.facts.real_system_decision_consumptions
        if any(not isinstance(item, RealSystemDecisionConsumption) for item in consumptions):
            raise ProofLadderError("real final replay decision consumption is invalid")
        if len({item.pending_decision_digest for item in consumptions}) != len(consumptions):
            raise ProofLadderError("real final replay decision is consumed more than once")
        for consumption in consumptions:
            pending = pending_by_digest.get(consumption.pending_decision_digest)
            decision = consumption.decision
            if (
                pending is None
                or decision.pending_decision_digest != consumption.pending_decision_digest
                or decision.decision_id != pending.decision_id
                or decision.kind != pending.kind
                or decision.run_id != pending.run_id
                or decision.run_head_digest != pending.run_head_digest
                or decision.authority_digest != pending.authority_digest
                or decision.payload_digest != pending.payload_digest
                or decision.amendment != pending.amendment
                or consumption.amendment != decision.amendment
            ):
                raise ProofLadderError(
                    "real final replay decision consumption does not bind pending authority"
                )
        return cls(
            run_id=state.run_id,
            adapter_manifest_digest=state.adapter_manifest_digest,
            provider_authority_digest=provider.digest,
            run_head_digest=head.digest,
            environment_snapshot_digest=environment_snapshot.digest,
            target_identity_digest=environment_snapshot.target_identity_digest,
            lease_receipt_digests=environment_snapshot.lease_receipt_digests,
            egress_receipt_digest=environment_snapshot.egress_receipt_digest,
            evidence_policy_digest=environment_snapshot.evidence_policy_digest,
            baseline_spine_digest=baseline.digest,
            baseline_node_digests=baseline.node_digests,
            exploration_delta_digests=tuple(
                delta.digest for delta in state.facts.exploration_deltas
            ),
            node_completion_digests=tuple(
                completion.digest for completion in completions
            ),
            decision_consumption_digests=tuple(
                consumption.digest for consumption in consumptions
            ),
            executed_node_digests=tuple(
                known_nodes[intent.node_id].digest
                for intent in state.facts.external_operation_intents
            ),
            supervisor_receipt_digests=tuple(
                receipt.digest for receipt in state.facts.supervisor_receipts
            ),
            adapter_interface_digest=descriptor.interface_digest,
            operation_intent_digests=tuple(
                intent.digest for intent in state.facts.external_operation_intents
            ),
            operation_receipt_digests=tuple(
                receipt.digest for receipt in state.facts.external_operation_receipts
            ),
        )

    @property
    def digest(self) -> str:
        return digest_for("real-final-replay-snapshot", self)


def final_replay_context_id(
    snapshot: FinalReplaySnapshot,
    replay_bundle_digest: str,
    replay_result_digest: str,
) -> str:
    """Exact post-traversal context Semantic Reviewer must receive."""

    return (
        f"final-replay:{snapshot.digest}:{replay_bundle_digest}:"
        f"{replay_result_digest}"
    )


@dataclass(frozen=True, slots=True)
class ProofLadder:
    base_run_head: RunHead
    closed_cone: ClosedCausalCone | None
    proof_spec: ProofSpec
    red_result: ProofResult | None
    executor_output: ImportedRoleOutput | None
    discovery_output: ImportedRoleOutput | None
    curator_output: ImportedRoleOutput | None
    candidate_workspace: object | None
    validator_output: ImportedRoleOutput | None
    semantic_output: ImportedRoleOutput | None
    integration: object | None
    original_node_result: ProofResult | None
    affected_neighbor_specs: tuple[ProofSpec, ...]
    affected_neighbor_results: tuple[ProofResult, ...]

    def validate(self, *, current_state: RunState) -> RunHead:
        for field_name in (
            "red_result",
            "closed_cone",
            "executor_output",
            "discovery_output",
            "curator_output",
            "candidate_workspace",
            "validator_output",
            "semantic_output",
            "integration",
            "original_node_result",
        ):
            if getattr(self, field_name) is None:
                raise ProofLadderError(f"missing proof ladder rung: {field_name}")
        if not isinstance(self.closed_cone, ClosedCausalCone):
            raise ProofLadderError("proof ladder requires a closed causal cone")
        try:
            self.closed_cone.cone.close(self.closed_cone.frozen_expansion)
        except Exception as error:
            raise ProofLadderError("proof ladder requires a closed causal cone") from error
        if self.proof_spec.node_id != self.closed_cone.node_id:
            raise ProofLadderError("ProofSpec must bind closed causal cone Behavioral Node")
        current_run_head = current_state.facts.run_head
        current_environment = current_state.facts.environment
        if current_run_head is None or current_environment is None:
            raise ProofLadderError("proof ladder requires current sealed Run Head and environment")
        if self.base_run_head != current_run_head:
            raise ProofLadderError("proof ladder must bind current Run Head")
        if (
            current_run_head.environment_digest != current_environment.digest
            or current_run_head.fixture_digest != current_state.fixture_intent_digest
        ):
            raise ProofLadderError("current Run Head does not bind current environment and fixture")
        expected_neighbor_nodes = _direct_neighbor_node_ids(self.closed_cone)
        if not expected_neighbor_nodes:
            raise ProofLadderError("closed causal cone requires directly affected neighbor proof")
        actual_neighbor_nodes = {spec.node_id for spec in self.affected_neighbor_specs}
        if actual_neighbor_nodes != expected_neighbor_nodes or len(actual_neighbor_nodes) != len(self.affected_neighbor_specs):
            raise ProofLadderError("affected neighbor ProofSpecs must match exact graph-derived neighbors")
        if len(self.affected_neighbor_results) != len(self.affected_neighbor_specs):
            raise ProofLadderError("affected neighbor proof results must match exact graph-derived neighbors")
        spine = current_state.facts.derived_spine
        if spine is None:
            raise ProofLadderError("proof ladder requires persisted Derived Spine authority")
        authority = (
            current_state.trajectory_digest,
            spine.digest,
            spine.landmark_mapping_digest,
        )
        for proof_spec in (self.proof_spec, *self.affected_neighbor_specs):
            if (
                proof_spec.trajectory_digest,
                proof_spec.derived_spine_digest,
                proof_spec.landmark_mapping_digest,
            ) != authority:
                raise ProofLadderError(
                    "ProofSpec does not bind current trajectory/spine/landmark authority"
                )
        assert self.red_result is not None
        if (
            self.red_result.proof_spec_id != self.proof_spec.proof_spec_id
            or self.red_result.proof_spec_digest != self.proof_spec.digest
            or self.red_result.node_id != self.proof_spec.node_id
            or self.red_result.proof_class != "deterministic_execution_proof"
            or self.red_result.result != "red"
            or self.red_result.run_head_digest != self.base_run_head.digest
        ):
            raise ProofLadderError("recorded RED must bind pre-patch Run Head and ProofSpec")
        outputs = (
            ("patch_executor", self.executor_output),
            ("discovery_reviewer", self.discovery_output),
            ("proof_curator", self.curator_output),
            ("validator", self.validator_output),
            ("semantic_reviewer", self.semantic_output),
        )
        identities: set[str] = set()
        contexts: set[str] = set()
        spine_digests: set[str] = set()
        for role, output in outputs:
            assert output is not None
            require_exact_issuer_output(
                output,
                state=current_state,
                cone=self.closed_cone.cone,
                proof_spec=self.proof_spec,
                role=role,  # type: ignore[arg-type]
                permitted_output_schema="proof-role-output-v1",
                issued_mode=current_state.mode,
            )
            manifest = output.dispatch.manifest
            identity = manifest.identity.casefold()
            if identity in identities:
                raise ProofLadderError("proof ladder reuses role identity")
            if output.dispatch.context_id in contexts:
                raise ProofLadderError("proof ladder reuses role context")
            identities.add(identity)
            contexts.add(output.dispatch.context_id)
            spine_digests.add(output.dispatch.spine_digest)
        if len(spine_digests) != 1 or not next(iter(spine_digests)).strip():
            raise ProofLadderError("role outputs do not bind one immutable Spine digest")
        assert self.executor_output is not None
        assert self.discovery_output is not None
        assert self.curator_output is not None
        assert self.validator_output is not None
        assert self.semantic_output is not None
        if self.executor_output.dispatch.curator_oracle_digest is not None:
            raise ProofLadderError("executor access to Curator oracle is forbidden")
        if self.discovery_output.decision != "approved":
            raise ProofLadderError("independent Discovery Reviewer closure attestation is required")
        if self.curator_output.decision != "approved":
            raise ProofLadderError("Curator-approved discriminating ProofSpec is required")
        if self.validator_output.decision != "green":
            raise ProofLadderError("independent Validator GREEN is required")
        if self.semantic_output.decision != "approved":
            raise ProofLadderError("fresh Semantic Reviewer attestation is required")
        candidate = self.candidate_workspace
        integration = self.integration
        assert candidate is not None and integration is not None
        from .workspace import WorkspaceError, validate_lifecycle_integration_receipts

        try:
            new_head = validate_lifecycle_integration_receipts(
                candidate,
                integration,
                base_run_head=self.base_run_head,
                closed_cone=self.closed_cone,
            )
        except WorkspaceError as error:
            raise ProofLadderError(str(error)) from error
        assert self.original_node_result is not None
        all_specs = (self.proof_spec, *self.affected_neighbor_specs)
        all_results = (self.original_node_result, *self.affected_neighbor_results)
        if len({result.proof_result_id for result in all_results}) != len(all_results):
            raise ProofLadderError("original and neighbor proof result ids must be unique")
        for index, (spec, result) in enumerate(zip(all_specs, all_results, strict=True)):
            if (
                result.proof_class != "deterministic_execution_proof"
                or result.result != "green"
                or result.run_head_digest != new_head.digest
                or result.proof_spec_id != spec.proof_spec_id
                or result.proof_spec_digest != spec.digest
                or result.node_id != spec.node_id
            ):
                if index:
                    raise ProofLadderError("affected neighbor proof must bind its exact graph-derived ProofSpec")
                raise ProofLadderError("post-integration original proof must bind its exact ProofSpec")
        return new_head


def _direct_neighbor_node_ids(closed_cone: ClosedCausalCone) -> set[str]:
    """Derive direct predecessor/successor nodes from frozen causal graph, never caller input."""

    root_lead_id = closed_cone.frozen_expansion.selected_lead_id
    if root_lead_id is None:
        return set()
    adjacent_leads = {root_lead_id}
    for edge in closed_cone.cone.edges:
        if root_lead_id in (edge.from_lead_id, edge.to_lead_id):
            adjacent_leads.update((edge.from_lead_id, edge.to_lead_id))
    observations = {
        observation.observation_id: observation for observation in closed_cone.cone.observations
    }
    return {
        observations[lead.source_observation_id].node_id
        for lead in closed_cone.cone.leads
        if lead.lead_id in adjacent_leads
        and lead.source_observation_id in observations
        and observations[lead.source_observation_id].node_id != closed_cone.node_id
    }
