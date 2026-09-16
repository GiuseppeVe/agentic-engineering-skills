"""V5 append-only artifact store and recoverable hash-chain ledger."""

from __future__ import annotations

import base64
import json
import os
import re
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, ValidationError, field_validator, model_validator

from .artifacts import ArtifactRecord
from .canonical import canonical_json_bytes, digest_bytes, digest_for
from .models import (
    AdmittedProviderAuthority,
    BaselineNodeProposal,
    BaselineSpineAuthority,
    BudgetReservation,
    BootstrapIntent,
    CleanupDecision,
    ConfirmedTrajectoryBinding,
    ConfirmedTrajectoryBundle,
    DerivedSpine,
    DerivedSpineSeal,
    DerivedBehavioralNode,
    EgressGateReceipt,
    FrozenDerivedSpine,
    EnvironmentIdentity,
    ExplorationDelta,
    ExternalOperationIntent,
    ExternalOperationReceipt,
    ManifestBudgetExhaustion,
    FactIndex,
    GitTransaction,
    HostPreflightReceipt,
    IterationFact,
    Observation,
    PendingDecision,
    PendingTrajectoryDecision,
    PauseReport,
    ProductWorkReceipt,
    ReplayReopen,
    RunHead,
    RunState,
    RuntimeNote,
    V52RunState,
    RealSystemFactIndex,
    RealNodeCompletion,
    PendingRealSystemDecision,
    PersistedNodeExecutionAuthority,
    RealSystemDecision,
    RealSystemDecisionConsumption,
    RealSystemRunHead,
    NodeAuthority,
    SpineFrontier,
    StrictModel,
    SupervisorAuthorityReceipt,
    TrajectoryPause,
    TrajectoryBrief,
    TrajectoryConfirmation,
    TrajectorySuccessor,
    UserDecision,
    UserAuthorizationConsumption,
    WorkAuthorization,
    real_system_decision_target_key,
    validate_pending_real_system_decision_amendment,
    validate_node_budget_against_manifest,
    validate_accepted_result_context,
    validate_sealed_node_context,
)


class StoreError(RuntimeError):
    """Base error for durable V5 store violations."""


class BudgetReservationExceeded(StoreError):
    """Typed aggregate-cap exhaustion detected before any adapter dispatch."""

    def __init__(self, exhausted_budget_names: tuple[str, ...]) -> None:
        self.exhausted_budget_names = exhausted_budget_names
        super().__init__(
            "budget reservation exceeds admitted "
            + ", ".join(exhausted_budget_names)
        )


class CapabilityError(StoreError):
    """Caller capability does not own this exact run store."""


class RecoveryError(StoreError):
    """Journal cannot be replayed safely."""


class SimulatedCrash(StoreError):
    """Crash-injection seam for deterministic recovery tests."""


EventKind = Literal[
    "trajectory_confirmed",
    "derived_spine_initialized",
    "derived_spine_sealed",
    "derived_spine_result_recorded",
    "derived_spine_frozen",
    "trajectory_pause_recorded",
    "trajectory_pause_resumed",
    "trajectory_decision_requested",
    "trajectory_successor_confirmed",
    "bootstrap_intended",
    "host_preflighted",
    "git_transaction_recorded",
    "environment_sealed",
    "initial_run_head_recorded",
    "run_started",
    "observed",
    "lead_opened",
    "cone_closed",
    "repair_attempted",
    "proof_imported",
    "run_head_advanced",
    "paused",
    "decision_applied",
    "terminalized",
    "runtime_iteration_recorded",
    "product_work_accounted",
    "diagnostic_stall_paused",
    "user_decision_applied",
    "escalation_requested",
    "run_head_advanced",
    "final_replay_started",
    "final_replay_succeeded",
    "final_replay_reopened",
    "review_infrastructure_paused",
]
_EVENT_KINDS = frozenset(EventKind.__args__)
_GENESIS_DIGEST = "0" * 64
_SHA256_HEX = re.compile(r"[0-9a-f]{64}")
_RUNTIME_CAPABILITY_TOKEN = object()
_APPEND_ONLY_FACT_FIELDS = (
    "frozen_derived_spines",
    "observations",
    "leads",
    "edges",
    "repairs",
    "proof_specs",
    "proof_results",
    "role_manifests",
    "duration_deltas",
    "iteration_facts",
    "cone_identity_bindings",
    "work_authorizations",
    "product_work",
    "change_classification_artifacts",
    "user_decisions",
    "user_authorization_consumptions",
    "pending_decision_history",
    "pause_reports",
    "trajectory_pauses",
    "pending_trajectory_decisions",
    "trajectory_successors",
)
_TASK4_EVENT_ARTIFACTS: dict[
    str, tuple[str, type[StrictModel]]
] = {
    "trajectory_confirmed": ("confirmed-trajectory-binding", ConfirmedTrajectoryBinding),
    "derived_spine_initialized": ("derived-spine", DerivedSpine),
    "observed": ("observation", Observation),
    "derived_spine_sealed": ("derived-spine", DerivedSpine),
    "derived_spine_result_recorded": ("derived-spine", DerivedSpine),
    "derived_spine_frozen": ("frozen-derived-spine", FrozenDerivedSpine),
    "trajectory_pause_recorded": ("trajectory-pause", TrajectoryPause),
    "trajectory_pause_resumed": ("trajectory-pause", TrajectoryPause),
    "trajectory_decision_requested": (
        "pending-trajectory-decision", PendingTrajectoryDecision
    ),
    "trajectory_successor_confirmed": ("trajectory-successor", TrajectorySuccessor),
    "bootstrap_intended": ("bootstrap-intent", BootstrapIntent),
    "host_preflighted": ("host-preflight", HostPreflightReceipt),
    "git_transaction_recorded": ("git-transaction", GitTransaction),
    "environment_sealed": ("environment-identity", EnvironmentIdentity),
    "initial_run_head_recorded": ("run-head", RunHead),
    "run_started": ("run-head", RunHead),
    "runtime_iteration_recorded": ("runtime-iteration", IterationFact),
    "product_work_accounted": ("product-work", ProductWorkReceipt),
    "diagnostic_stall_paused": ("pause-report", PauseReport),
    "user_decision_applied": ("user-decision", UserDecision),
    "escalation_requested": ("pending-decision", PendingDecision),
    "run_head_advanced": ("run-head", RunHead),
    "final_replay_started": ("run-head", RunHead),
    "final_replay_succeeded": ("runtime-iteration", IterationFact),
    "final_replay_reopened": ("runtime-iteration", IterationFact),
    "review_infrastructure_paused": ("pause-report", PauseReport),
}


@dataclass(frozen=True, slots=True)
class StoreCapability:
    root: Path
    run_id: str
    _authority_token: object = field(repr=False, compare=False)

    @classmethod
    def issue(cls, root: str | Path, run_id: str) -> "StoreCapability":
        raise CapabilityError("store capabilities may only be issued by the V5 runtime")

    @classmethod
    def _issue_for_runtime(cls, root: str | Path, run_id: str) -> "StoreCapability":
        return cls(
            Path(root).resolve(strict=False),
            run_id,
            _RUNTIME_CAPABILITY_TOKEN,
        )


class EventFactReference(StrictModel):
    """Typed ledger payload: event points at one canonical fact or proof."""

    fact_id: str
    fact_digest: str

    @model_validator(mode="after")
    def _validate_reference(self) -> "EventFactReference":
        if not self.fact_id.strip():
            raise ValueError("event fact_id must be non-empty")
        if not _SHA256_HEX.fullmatch(self.fact_digest):
            raise ValueError("event fact_digest must be a SHA-256 hexadecimal string")
        return self


class LedgerEvent(StrictModel):
    sequence: int = Field(ge=1)
    kind: EventKind
    payload: EventFactReference
    payload_digest: str
    previous_digest: str
    state_digest: str
    event_digest: str

    @model_validator(mode="after")
    def _verify_digest(self) -> "LedgerEvent":
        material = {
            "sequence": self.sequence,
            "kind": self.kind,
            "payload": self.payload,
            "payload_digest": self.payload_digest,
            "previous_digest": self.previous_digest,
            "state_digest": self.state_digest,
        }
        if self.payload_digest != digest_for("graph-v5-event-payload", self.payload):
            raise ValueError("ledger event payload digest mismatch")
        if self.event_digest != digest_for("graph-v5-ledger-event", material):
            raise ValueError("ledger event digest mismatch")
        return self

    @classmethod
    def create(
        cls,
        *,
        sequence: int,
        kind: EventKind,
        payload: StrictModel,
        previous_digest: str,
        state_digest: str,
    ) -> "LedgerEvent":
        if not isinstance(payload, StrictModel):
            raise StoreError("ledger event payload must be a typed V5 fact reference")
        try:
            normalized_payload = EventFactReference.model_validate(payload.model_dump())
        except ValidationError as exc:
            raise StoreError("ledger event payload must be a typed V5 fact reference") from exc
        payload_digest = digest_for("graph-v5-event-payload", normalized_payload)
        material = {
            "sequence": sequence,
            "kind": kind,
            "payload": normalized_payload,
            "payload_digest": payload_digest,
            "previous_digest": previous_digest,
            "state_digest": state_digest,
        }
        return cls(
            **material,
            event_digest=digest_for("graph-v5-ledger-event", material),
        )


class TransactionalRunStore:
    """One capability-bound V5 run store. Runtime is sole intended mutator."""

    def __init__(self, root: Path, capability: StoreCapability) -> None:
        resolved_root = root.resolve(strict=False)
        if capability._authority_token is not _RUNTIME_CAPABILITY_TOKEN:
            raise CapabilityError("invalid V5 runtime capability authority")
        if resolved_root != capability.root:
            raise CapabilityError("capability root does not match requested store root")
        self._root = resolved_root
        self._capability = capability

    @staticmethod
    def _open_replay_reopens(facts: FactIndex) -> tuple[ReplayReopen, ...]:
        closed_ids = {closure.replay_id for closure in facts.replay_cone_closures}
        return tuple(
            reopen for reopen in facts.replay_reopens if reopen.replay_id not in closed_ids
        )

    @staticmethod
    def _replay_repair_ready(
        state: RunState, prior_spine: DerivedSpine | None
    ) -> bool:
        """Permit extension only after exact closure on pre-extension spine."""

        run_head = state.facts.run_head
        if (
            prior_spine is None
            or run_head is None
            or prior_spine.frontier.target_landmark_id is not None
            or prior_spine.frontier.unexecuted_node_id is not None
            or not prior_spine.nodes
            or len(prior_spine.results) != len(prior_spine.nodes)
        ):
            return False
        node_ids = {node.node_id for node in prior_spine.nodes}
        closed = {
            closure.replay_id: closure
            for closure in state.facts.replay_cone_closures
        }
        proof_specs = {spec.digest: spec for spec in state.facts.proof_specs}
        proof_results = {
            result.proof_result_id: result
            for result in state.facts.proof_results
        }
        if len(proof_results) != len(state.facts.proof_results):
            return False
        stale_ids = {
            stale_id
            for reopen in state.facts.replay_reopens
            for stale_id in reopen.stale_verified_fact_ids
        }
        verified = {
            fact.node_id
            for fact in state.facts.iteration_facts
            if fact.fact_class == "verified_node"
            and fact.run_head_digest == run_head.digest
            and fact.fact_id not in stale_ids
        }
        for reopen in state.facts.replay_reopens:
            closure = closed.get(reopen.replay_id)
            if (
                closure is None
                or closure.closed_cone_digest != reopen.cone_digest
                or closure.run_head_digest != run_head.digest
                or reopen.run_head_digest != run_head.digest
                or reopen.node_id not in node_ids
                or reopen.node_id not in verified
            ):
                continue
            spec = proof_specs.get(closure.proof_spec_digest)
            if spec is None or (
                spec.node_id != reopen.node_id
                or (
                    spec.trajectory_digest,
                    spec.derived_spine_digest,
                    spec.landmark_mapping_digest,
                )
                != (
                    state.trajectory_digest,
                    prior_spine.digest,
                    prior_spine.landmark_mapping_digest,
                )
            ):
                continue
            if any(
                (
                    (result := proof_results.get(result_id)) is None
                    or result.proof_spec_id != spec.proof_spec_id
                    or result.proof_spec_digest != spec.digest
                    or result.node_id != reopen.node_id
                    or result.proof_class != "deterministic_execution_proof"
                    or result.result != "green"
                    or result.run_head_digest != run_head.digest
                )
                for result_id in closure.proof_result_ids
            ):
                continue
            return True
        return False

    @classmethod
    def open(
        cls, root: str | Path, capability: StoreCapability
    ) -> "TransactionalRunStore":
        store = cls(Path(root), capability)
        if store._journal_path.exists():
            store.recover()
        return store

    @classmethod
    def open_for_confirmed_genesis(
        cls, root: str | Path, run_id: str
    ) -> "TransactionalRunStore":
        """Open a fresh prospective root without recovery or root creation."""

        capability = StoreCapability._issue_for_runtime(root, run_id)
        return cls(Path(root), capability)

    @classmethod
    def open_readonly(cls, root: str | Path, run_id: str) -> "TransactionalRunStore":
        """Open one explicit run root without recovery, locking, or root creation.

        Operator projection must never complete a partially durable transaction.
        A caller needing recovery uses a mutating runtime command instead.
        """

        capability = StoreCapability._issue_for_runtime(root, run_id)
        return cls(Path(root), capability)

    @property
    def root(self) -> Path:
        return self._root

    @property
    def _state_path(self) -> Path:
        return self._root / "state.json"

    @property
    def _ledger_path(self) -> Path:
        return self._root / "ledger.jsonl"

    @property
    def _journal_path(self) -> Path:
        return self._root / "journal.json"

    @property
    def _lock_path(self) -> Path:
        return self._root / ".graph-v5.lock"

    def initialize(self, state: RunState) -> None:
        state = self._revalidate_run_state(state)
        self._require_run(state.run_id)
        with self._lock():
            if self._state_path.exists():
                existing = self._read_state_unrecovered()
                if existing != state:
                    raise StoreError("run store is already initialized with different canonical state")
                return
            self._root.mkdir(parents=True, exist_ok=True)
            self._atomic_write(self._state_path, canonical_json_bytes(state))

    def initialize_confirmed_run(
        self,
        state: RunState,
        *,
        confirmed: ConfirmedTrajectoryBundle,
        interrupt_after: Literal[
            "journal_written",
            "trajectory_artifact_written",
            "markdown_artifact_written",
            "confirmation_artifact_written",
            "binding_artifact_written",
            "state_replaced",
            "ledger_appended",
        ]
        | None = None,
    ) -> ConfirmedTrajectoryBinding:
        """Atomically commit sole validated trajectory authority for a new run."""

        from .trajectory import TrajectoryValidationError, validate_confirmed_trajectory

        state = self._revalidate_run_state(state)
        if not isinstance(confirmed, ConfirmedTrajectoryBundle):
            raise StoreError("confirmed genesis requires a ConfirmedTrajectoryBundle")
        try:
            validated = validate_confirmed_trajectory(
                confirmed.brief,
                confirmed.markdown_utf8,
                confirmed.confirmation,
            )
        except TrajectoryValidationError as exc:
            raise StoreError("confirmed genesis trajectory is invalid") from exc
        self._require_run(state.run_id)
        if (
            state.run_id != validated.brief.run_id
            or state.trajectory != validated.brief
            or state.facts.trajectory_binding is not None
            or state.mode != "boot"
            or state.facts != FactIndex()
            or state.pending_decision is not None
        ):
            raise StoreError(
                "confirmed genesis requires clean initial RunState without Derived Spine"
            )
        binding = ConfirmedTrajectoryBinding(
            run_id=state.run_id,
            trajectory_digest=validated.brief.digest,
            markdown_digest=digest_bytes("trajectory-markdown", validated.markdown_utf8),
            confirmation_digest=digest_for(
                "trajectory-confirmation", validated.confirmation
            ),
        )
        genesis = self._with_facts(state, trajectory_binding=binding)
        artifacts = (
            ArtifactRecord.from_payload("trajectory-brief", validated.brief),
            ArtifactRecord.from_bytes(
                "trajectory-markdown",
                validated.markdown_utf8,
                "text/markdown; charset=utf-8",
            ),
            ArtifactRecord.from_payload(
                "trajectory-confirmation", validated.confirmation
            ),
            ArtifactRecord.from_payload("confirmed-trajectory-binding", binding),
        )
        event = LedgerEvent.create(
            sequence=1,
            kind="trajectory_confirmed",
            payload=EventFactReference(
                fact_id=binding.run_id,
                fact_digest=binding.digest,
            ),
            previous_digest=_GENESIS_DIGEST,
            state_digest=genesis.digest,
        )
        root_existed = self._root.exists()
        lock_existed = self._lock_path.exists()
        lock_bytes = self._lock_path.read_bytes() if lock_existed else b""
        artifacts_directory = self._root / "artifacts"
        artifacts_directory_existed = artifacts_directory.exists()
        try:
            with self._lock():
                if self._state_path.exists() or self._ledger_path.exists() or self._journal_path.exists():
                    raise StoreError("run store already has durable state")
                self._write_confirmed_genesis_transaction(
                    genesis,
                    event,
                    artifacts,
                    root_existed=root_existed,
                    lock_existed=lock_existed,
                    lock_bytes=lock_bytes,
                    artifacts_directory_existed=artifacts_directory_existed,
                    interrupt_after=interrupt_after,
                )
        except (OSError, SimulatedCrash):
            if not artifacts_directory_existed and artifacts_directory.exists():
                artifacts_directory.rmdir()
            self._restore_exact_file(self._lock_path, lock_existed, lock_bytes)
            if not root_existed:
                self._root.rmdir()
            raise
        return binding

    def read_state(self) -> RunState:
        self.recover()
        return self.read_state_readonly()

    def read_state_readonly(self) -> RunState:
        """Validate durable state from bytes only; never recover or write."""

        if self._journal_path.exists():
            raise RecoveryError("V5 recovery is pending; read-only status will not write")
        state = self._read_state_unrecovered()
        events = self._read_events_unrecovered()
        if events and events[-1].state_digest != state.digest:
            raise StoreError("canonical V5 state digest is not bound to ledger head")
        replay_spine: DerivedSpine | None = None
        replay_frozen_spines: list[FrozenDerivedSpine] = []
        for event in events:
            if self._is_preconfirmation_noop_observation(event.kind, state, state):
                continue
            artifact = self._read_task4_event_artifact(event.kind, event.payload)
            self._validate_task4_replay_artifact_binding(
                event.kind,
                event.payload,
                state,
                artifact,
                graph_revision=event.sequence,
                prior_spine=replay_spine,
            )
            if event.kind in {
                "derived_spine_initialized", "derived_spine_sealed", "derived_spine_result_recorded"
            }:
                assert isinstance(artifact, DerivedSpine)
                replay_spine = artifact
            elif event.kind == "derived_spine_frozen":
                assert isinstance(artifact, FrozenDerivedSpine)
                replay_frozen_spines.append(artifact)
            elif event.kind == "trajectory_successor_confirmed":
                assert isinstance(artifact, TrajectorySuccessor)
                replay_spine = self._validate_trajectory_successor_artifacts(artifact)
        if replay_spine != state.facts.derived_spine:
            raise StoreError("canonical Derived Spine is not reconstructed by ledger events")
        if tuple(replay_frozen_spines) != state.facts.frozen_derived_spines:
            raise StoreError("canonical frozen Derived Spine history is not reconstructed by ledger events")
        self._validate_stored_confirmed_trajectory(state)
        return state

    @staticmethod
    def _is_preconfirmation_noop_observation(
        kind: EventKind,
        current: RunState,
        successor: RunState,
    ) -> bool:
        """Allow inert bootstrap-ledger integrity records, never runtime authority."""

        return (
            kind == "observed"
            and current == successor
            and current.mode == "boot"
            and current.facts == FactIndex()
            and current.facts.trajectory_binding is None
            and current.facts.run_head is None
        )

    def _validate_stored_confirmed_trajectory(self, state: RunState) -> None:
        """Resume only from all exact artifacts bound by confirmed genesis."""

        binding = state.facts.trajectory_binding
        if binding is None:
            return
        try:
            brief = TrajectoryBrief.model_validate(
                self.read_artifact("trajectory-brief", binding.trajectory_digest)
            )
            markdown = self.read_artifact_bytes(
                "trajectory-markdown", binding.markdown_digest
            )
            confirmation = TrajectoryConfirmation.model_validate(
                self.read_artifact(
                    "trajectory-confirmation", binding.confirmation_digest
                )
            )
            from .trajectory import validate_confirmed_trajectory

            validated = validate_confirmed_trajectory(brief, markdown, confirmation)
        except (StoreError, ValidationError, ValueError) as exc:
            raise StoreError("stored confirmed trajectory artifacts are invalid") from exc
        if (
            validated.brief != state.trajectory
            or binding.run_id != state.run_id
            or binding.trajectory_digest != state.trajectory_digest
        ):
            raise StoreError("stored confirmed trajectory binding is inconsistent")

    def _validate_trajectory_successor_artifacts(
        self, link: TrajectorySuccessor
    ) -> DerivedSpine:
        """Verify every immutable successor artifact and return its persisted frontier."""

        try:
            brief = TrajectoryBrief.model_validate(
                self.read_artifact("trajectory-brief", link.successor_trajectory_digest)
            )
            markdown = self.read_artifact_bytes(
                "trajectory-markdown", link.successor_markdown_digest
            )
            confirmation = TrajectoryConfirmation.model_validate(
                self.read_artifact(
                    "trajectory-confirmation", link.successor_confirmation_digest
                )
            )
            from .trajectory import validate_confirmed_trajectory

            validated = validate_confirmed_trajectory(brief, markdown, confirmation)
            binding = ConfirmedTrajectoryBinding(
                run_id=brief.run_id,
                trajectory_digest=brief.digest,
                markdown_digest=link.successor_markdown_digest,
                confirmation_digest=link.successor_confirmation_digest,
            )
            stored_binding = ConfirmedTrajectoryBinding.model_validate(
                self.read_artifact("confirmed-trajectory-binding", binding.digest)
            )
            spine = DerivedSpine.model_validate_json(
                canonical_json_bytes(
                    self.read_artifact("derived-spine", link.successor_spine_digest)
                )
            )
            spine.bind_trajectory(validated.brief)
        except (StoreError, ValidationError, ValueError) as exc:
            raise StoreError("stored confirmed trajectory successor artifacts are invalid") from exc
        if (
            stored_binding != binding
            or spine.digest != link.successor_spine_digest
            or spine.nodes
            or spine.results
        ):
            raise StoreError("stored confirmed trajectory successor binding is inconsistent")
        return spine

    def append_event(
        self,
        kind: EventKind,
        payload: StrictModel,
        next_state: RunState,
        *,
        interrupt_after: Literal["journal_written", "state_replaced", "ledger_appended"] | None = None,
    ) -> LedgerEvent:
        if kind not in _EVENT_KINDS:
            raise StoreError(f"unknown V5 event kind: {kind}")
        next_state = self._revalidate_run_state(next_state)
        self._require_run(next_state.run_id)
        self.recover()
        with self._lock():
            events = self._read_events_unrecovered()
            current_state = self._read_state_unrecovered()
            if events and events[-1].state_digest != current_state.digest:
                raise StoreError(
                    "canonical V5 state digest is not bound to ledger head"
                )
            self._validate_successor(current_state, next_state)
            reference = self._event_reference(payload)
            is_preconfirmation_noop = self._is_preconfirmation_noop_observation(
                kind, current_state, next_state
            )
            if (
                kind == "observed"
                and current_state.mode == "boot"
                and current_state.facts.trajectory_binding is None
                and current_state == next_state
                and not is_preconfirmation_noop
            ):
                raise StoreError(
                    "pre-confirmation no-op requires exact pristine boot state"
                )
            if not is_preconfirmation_noop:
                self._validate_task4_event_transition(
                    kind, current_state, next_state, reference
                )
                artifact = self._read_task4_event_artifact(kind, reference)
                self._validate_task4_event_artifact_binding(
                    kind, current_state, next_state, artifact
                )
            event = LedgerEvent.create(
                sequence=len(events) + 1,
                kind=kind,
                payload=payload,
                previous_digest=events[-1].event_digest if events else _GENESIS_DIGEST,
                state_digest=next_state.digest,
            )
            state_bytes = canonical_json_bytes(next_state)
            event_line = canonical_json_bytes(event) + b"\n"
            journal = {
                "schema_version": "v5.transaction-journal.v1",
                "state_bytes_b64": base64.b64encode(state_bytes).decode("ascii"),
                "event_line_b64": base64.b64encode(event_line).decode("ascii"),
                "event_digest": event.event_digest,
            }
            self._atomic_write(self._journal_path, canonical_json_bytes(journal))
            if interrupt_after == "journal_written":
                raise SimulatedCrash("injected crash after journal write")
            self._atomic_write(self._state_path, state_bytes)
            if interrupt_after == "state_replaced":
                raise SimulatedCrash("injected crash after state replacement")
            self._append_bytes(self._ledger_path, event_line)
            if interrupt_after == "ledger_appended":
                raise SimulatedCrash("injected crash after ledger append")
            self._remove_exact_file(self._journal_path)
            return event

    def read_events(self) -> tuple[LedgerEvent, ...]:
        self.recover()
        return self._read_events_unrecovered()

    def record_derived_spine(self, spine: DerivedSpine, successor: RunState) -> None:
        """Append one sealed node projection with its exact immutable spine artifact."""

        if not isinstance(spine, DerivedSpine):
            raise StoreError("Derived Spine must be a strict immutable model")
        current = self.read_state()
        if successor.facts.derived_spine != spine:
            raise StoreError("Derived Spine event must bind successor spine exactly")
        if spine.run_id != current.run_id or spine.trajectory_digest != current.trajectory_digest:
            raise StoreError("Derived Spine does not bind current confirmed trajectory")
        try:
            reference = DerivedSpineSeal.from_spine(spine)
        except ValueError as exc:
            raise StoreError("Derived Spine sealing event requires one appended node") from exc
        record = ArtifactRecord.from_payload("derived-spine", spine)
        if record.digest != reference.fact_digest:
            raise StoreError("Derived Spine artifact digest does not bind sealing event")
        self._append_event_with_artifacts(
            "derived_spine_sealed",
            reference,
            successor,
            artifacts=(record,),
            event_artifact=spine,
        )

    def record_initial_derived_spine(self, spine: DerivedSpine, successor: RunState) -> None:
        """Persist empty frontier before runtime derives its first node."""

        if not isinstance(spine, DerivedSpine):
            raise StoreError("Derived Spine must be a strict immutable model")
        current = self.read_state()
        if current.facts.derived_spine is not None or successor.facts.derived_spine != spine:
            raise StoreError("initial Derived Spine must be persisted exactly once")
        record = ArtifactRecord.from_payload("derived-spine", spine)
        self._append_event_with_artifacts(
            "derived_spine_initialized",
            EventFactReference(fact_id=spine.trajectory_digest, fact_digest=record.digest),
            successor,
            artifacts=(record,),
            event_artifact=spine,
        )

    def record_derived_spine_result(
        self, spine: DerivedSpine, successor: RunState
    ) -> None:
        """Append accepted evidence/result before frontier may seal another node."""

        if not isinstance(spine, DerivedSpine):
            raise StoreError("Derived Spine result must be a strict immutable model")
        current = self.read_state()
        if successor.facts.derived_spine != spine:
            raise StoreError("Derived Spine result event must bind successor spine exactly")
        prior = current.facts.derived_spine
        if prior is None or not prior.nodes or not spine.results:
            raise StoreError("Derived Spine result requires sealed frontier node")
        reference = DerivedSpineSeal.from_spine(spine)
        record = ArtifactRecord.from_payload("derived-spine", spine)
        if record.digest != reference.fact_digest:
            raise StoreError("Derived Spine result artifact does not bind event")
        self._append_event_with_artifacts(
            "derived_spine_result_recorded",
            reference,
            successor,
            artifacts=(record,),
            event_artifact=spine,
        )

    def record_derived_spine_frozen(self, frozen: FrozenDerivedSpine) -> None:
        """Persist immutable final-replay authority without rewriting state.

        Freeze snapshots are content-addressed artifacts. Keeping them outside
        the mutable state projection preserves every prior freeze when a later
        traversal extension receives a new spine digest.
        """

        if not isinstance(frozen, FrozenDerivedSpine):
            raise StoreError("frozen Derived Spine must be a strict immutable model")
        current = self.read_state()
        # Exact persisted authority is already durable; retry must not rerun
        # graph-revision/event-precondition checks after later events append.
        if frozen in current.facts.frozen_derived_spines:
            return
        if self._open_replay_reopens(current.facts):
            raise StoreError("cannot freeze Derived Spine with open replay reopen")
        if frozen.trajectory_digest != current.trajectory_digest:
            raise StoreError("frozen Derived Spine does not bind current trajectory")
        spine = current.facts.derived_spine
        run_head = current.facts.run_head
        environment = current.facts.environment
        if spine is None or frozen.derived_spine_digest != spine.digest:
            raise StoreError("frozen Derived Spine does not bind current spine")
        if run_head is None or environment is None:
            raise StoreError("frozen Derived Spine requires sealed Run Head and environment")
        if (
            frozen.run_id != spine.run_id
            or frozen.landmark_mapping_digest != spine.landmark_mapping_digest
            or frozen.landmark_order != spine.landmark_order
            or frozen.frontier != spine.frontier
            or frozen.nodes != spine.nodes
            or frozen.results != spine.results
            or frozen.run_head != run_head
            or frozen.environment != environment
            or frozen.fixture_digest != current.fixture_intent_digest
            or (
                bool(current.facts.frozen_derived_spines)
                and (
                    frozen.fixture_id
                    != current.facts.frozen_derived_spines[-1].fixture_id
                    or frozen.fixture_adapter_id
                    != current.facts.frozen_derived_spines[-1].fixture_adapter_id
                )
            )
            or frozen.graph_revision != len(self.read_events()) + 1
        ):
            raise StoreError("frozen Derived Spine authority mismatch")
        successor = current.model_copy(
            update={
                "facts": current.facts.model_copy(
                    update={
                        "frozen_derived_spines": current.facts.frozen_derived_spines
                        + (frozen,)
                    }
                )
            }
        )
        record = ArtifactRecord.from_payload("frozen-derived-spine", frozen)
        self._append_event_with_artifacts(
            "derived_spine_frozen",
            EventFactReference(fact_id=frozen.digest, fact_digest=record.digest),
            successor,
            artifacts=(record,),
            event_artifact=frozen,
        )

    def record_observation(self, observation: Observation, successor: RunState) -> None:
        """Persist exactly one current-head observation before it can seal a node."""

        if not isinstance(observation, Observation):
            raise StoreError("observation must be a strict immutable model")
        current = self.read_state()
        if successor.facts.observations != current.facts.observations + (observation,):
            raise StoreError("observation event must append exactly one observation")
        record = ArtifactRecord.from_payload("observation", observation)
        self._append_event_with_artifacts(
            "observed",
            EventFactReference(
                fact_id=observation.observation_id, fact_digest=record.digest
            ),
            successor,
            artifacts=(record,),
            event_artifact=observation,
        )

    def record_trajectory_pause(
        self, pause: TrajectoryPause, successor: RunState
    ) -> None:
        if not isinstance(pause, TrajectoryPause):
            raise StoreError("trajectory pause must be a strict immutable model")
        current = self.read_state()
        if (
            successor.mode != "paused"
            or successor.facts.trajectory_pauses
            != current.facts.trajectory_pauses + (pause,)
        ):
            raise StoreError("trajectory pause must append one pause and enter paused mode")
        record = ArtifactRecord.from_payload("trajectory-pause", pause)
        self._append_event_with_artifacts(
            "trajectory_pause_recorded",
            EventFactReference(fact_id=pause.reason, fact_digest=record.digest),
            successor,
            artifacts=(record,),
            event_artifact=pause,
        )

    def record_trajectory_pause_resumed(
        self, pause: TrajectoryPause, successor: RunState
    ) -> None:
        current = self.read_state()
        if (
            current.mode != "paused"
            or successor.mode != "running"
            or current.trajectory_pause != pause
            or successor.facts != current.facts
        ):
            raise StoreError("trajectory pause resume must preserve immutable pause history")
        record = ArtifactRecord.from_payload("trajectory-pause", pause)
        self._append_event_with_artifacts(
            "trajectory_pause_resumed",
            EventFactReference(fact_id=pause.digest, fact_digest=record.digest),
            successor,
            artifacts=(record,),
            event_artifact=pause,
        )

    def record_pending_trajectory_decision(
        self, decision: PendingTrajectoryDecision, successor: RunState
    ) -> None:
        if not isinstance(decision, PendingTrajectoryDecision):
            raise StoreError("trajectory decision must be a strict immutable model")
        current = self.read_state()
        if (
            successor.mode != "paused"
            or successor.facts.pending_trajectory_decisions
            != current.facts.pending_trajectory_decisions + (decision,)
        ):
            raise StoreError("trajectory decision must append one decision and enter paused mode")
        record = ArtifactRecord.from_payload("pending-trajectory-decision", decision)
        self._append_event_with_artifacts(
            "trajectory_decision_requested",
            EventFactReference(fact_id=decision.decision_id, fact_digest=record.digest),
            successor,
            artifacts=(record,),
            event_artifact=decision,
        )

    def record_trajectory_successor(
        self,
        successor_link: TrajectorySuccessor,
        successor: RunState,
        *,
        confirmed: ConfirmedTrajectoryBundle,
    ) -> None:
        if not isinstance(successor_link, TrajectorySuccessor):
            raise StoreError("trajectory successor must be a strict immutable model")
        current = self.read_state()
        if (
            confirmed.brief.run_id != current.run_id
            or confirmed.brief.digest != successor_link.successor_trajectory_digest
            or digest_bytes("trajectory-markdown", confirmed.markdown_utf8)
            != successor_link.successor_markdown_digest
            or digest_for("trajectory-confirmation", confirmed.confirmation)
            != successor_link.successor_confirmation_digest
            or successor.facts.trajectory_binding is None
            or successor.facts.derived_spine is None
            or successor.facts.derived_spine.digest
            != successor_link.successor_spine_digest
        ):
            raise StoreError("trajectory successor link does not bind confirmed successor artifacts")
        if successor.facts.trajectory_successors != current.facts.trajectory_successors + (
            successor_link,
        ):
            raise StoreError("trajectory successor must append one immutable successor link")
        record = ArtifactRecord.from_payload("trajectory-successor", successor_link)
        artifacts = (
            record,
            ArtifactRecord.from_payload("trajectory-brief", confirmed.brief),
            ArtifactRecord.from_bytes(
                "trajectory-markdown",
                confirmed.markdown_utf8,
                "text/markdown; charset=utf-8",
            ),
            ArtifactRecord.from_payload("trajectory-confirmation", confirmed.confirmation),
            ArtifactRecord.from_payload(
                "confirmed-trajectory-binding", successor.facts.trajectory_binding
            ),
            ArtifactRecord.from_payload(
                "derived-spine", successor.facts.derived_spine
            ),
        )
        self._append_event_with_artifacts(
            "trajectory_successor_confirmed",
            EventFactReference(
                fact_id=successor_link.successor_trajectory_digest,
                fact_digest=record.digest,
            ),
            successor,
            artifacts=artifacts,
            event_artifact=successor_link,
        )

    def record_bootstrap_intent(self, intent: BootstrapIntent) -> BootstrapIntent:
        """Persist exact compensation ownership before every Git side effect."""

        self._require_run(intent.run_id)
        current = self.read_state()
        existing = current.facts.bootstrap_intent
        if existing is not None:
            if existing != intent:
                raise StoreError("run already owns a different Bootstrap Intent")
            return existing
        next_state = self._with_facts(current, bootstrap_intent=intent)
        self._ensure_fact_event(
            "bootstrap_intended",
            intent.transaction_id,
            "bootstrap-intent",
            intent,
            next_state,
        )
        return intent

    def record_host_preflight(
        self, intent: BootstrapIntent, receipt: HostPreflightReceipt
    ) -> None:
        """Durably bind host receipt to Bootstrap Intent before Git preparation."""

        current = self.read_state()
        if current.facts.bootstrap_intent != intent:
            raise StoreError("host preflight must bind recorded Bootstrap Intent")
        self._assert_host_preflight_binding(intent, receipt)
        self._ensure_fact_event(
            "host_preflighted",
            intent.transaction_id,
            "host-preflight",
            receipt,
            current,
        )

    def read_latest_fact(
        self,
        *,
        kind: EventKind,
        fact_id: str,
        domain: str,
        model_type: type[StrictModel],
    ) -> StrictModel | None:
        """Read a strict immutable receipt only through its ledger reference."""

        for event in reversed(self.read_events()):
            if event.kind != kind or event.payload.fact_id != fact_id:
                continue
            payload = self.read_artifact(domain, event.payload.fact_digest)
            try:
                return model_type.model_validate(payload)
            except ValidationError as exc:
                raise StoreError("recorded fact does not satisfy strict V5 schema") from exc
        return None

    def record_git_transaction(self, transaction: GitTransaction) -> GitTransaction:
        current = self.read_state()
        intent = current.facts.bootstrap_intent
        if intent is None:
            raise StoreError("Git transaction requires durable Bootstrap Intent")
        receipt = self.read_latest_fact(
            kind="host_preflighted",
            fact_id=intent.transaction_id,
            domain="host-preflight",
            model_type=HostPreflightReceipt,
        )
        if receipt is None:
            raise StoreError("Git transaction requires durable host preflight proof")
        if not isinstance(receipt, HostPreflightReceipt):
            raise StoreError("Git transaction requires strict host preflight proof")
        self._assert_host_preflight_binding(intent, receipt)
        if (
            transaction.transaction_id != intent.transaction_id
            or transaction.requested_base_revision != intent.requested_base_revision
            or transaction.branch != intent.candidate_branch
            or transaction.worktree_path != intent.candidate_worktree_path
        ):
            raise StoreError("Git transaction is not bound to Bootstrap Intent")
        existing = current.facts.git_transaction
        if existing is not None:
            if existing.transaction_id != transaction.transaction_id:
                raise StoreError("run already owns a different Git transaction")
            return existing
        if transaction.status != "prepared":
            raise StoreError("first Git transaction record must be prepared")
        next_state = self._with_facts(current, git_transaction=transaction)
        self._ensure_fact_event(
            "git_transaction_recorded",
            transaction.transaction_id,
            "git-transaction",
            transaction,
            next_state,
        )
        return transaction

    def _assert_host_preflight_binding(
        self, intent: BootstrapIntent, receipt: HostPreflightReceipt
    ) -> None:
        if not isinstance(receipt, HostPreflightReceipt):
            raise StoreError("host preflight receipt does not satisfy strict V5 schema")
        try:
            receipt = HostPreflightReceipt.model_validate(receipt.model_dump())
        except ValidationError as exc:
            raise StoreError("host preflight receipt does not satisfy strict V5 schema") from exc
        if (
            receipt.transaction_id != intent.transaction_id
            or receipt.requested_base_revision != intent.requested_base_revision
            or receipt.repository_revision != intent.requested_base_revision
            or receipt.candidate_worktree_path != intent.candidate_worktree_path
            or Path(receipt.durable_store_root).resolve(strict=False) != self.root
        ):
            raise StoreError("host preflight receipt is not bound to Bootstrap Intent")

    def record_git_transaction_status(
        self,
        transaction_id: str,
        status: Literal["created", "reconciled", "compensated", "failed"],
    ) -> GitTransaction:
        current = self.read_state()
        transaction = current.facts.git_transaction
        if transaction is None or transaction.transaction_id != transaction_id:
            raise StoreError("no recorded Git transaction matches requested status update")
        if transaction.status == status:
            return transaction
        allowed = {
            "prepared": {"created", "compensated", "failed"},
            "created": {"reconciled", "compensated", "failed"},
            "reconciled": {"compensated", "failed"},
            "compensated": set(),
            "failed": set(),
        }
        if status not in allowed[transaction.status]:
            raise StoreError("Git transaction status transition is not resumable")
        updated = transaction.model_copy(update={"status": status})
        next_state = self._with_facts(current, git_transaction=updated)
        self._ensure_fact_event(
            "git_transaction_recorded",
            transaction_id,
            "git-transaction",
            updated,
            next_state,
        )
        return updated

    def seal_environment(self, run_id: str, environment: EnvironmentIdentity) -> EnvironmentIdentity:
        self._require_run(run_id)
        current = self.read_state()
        transaction = current.facts.git_transaction
        if transaction is None or transaction.status != "reconciled":
            raise StoreError("EnvironmentIdentity requires reconciled Git transaction")
        existing = current.facts.environment
        if existing is not None:
            if existing != environment:
                raise StoreError("sealed EnvironmentIdentity may not be replaced")
            return existing
        next_state = self._with_facts(current, environment=environment)
        self._ensure_fact_event(
            "environment_sealed",
            environment.digest,
            "environment-identity",
            environment,
            next_state,
        )
        return environment

    def enter_running(self, run_id: str) -> RunState:
        self._require_run(run_id)
        current = self.read_state()
        environment = current.facts.environment
        transaction = current.facts.git_transaction
        run_head = current.facts.run_head
        if (
            current.limits.active_version != 1
            or len(current.limits.versions) != 1
            or current.limits.amendments
        ):
            raise StoreError("run_started requires sealed initial Run Limits version 1")
        if environment is None:
            raise StoreError("first product observation requires sealed EnvironmentIdentity")
        if transaction is None or transaction.status != "reconciled":
            raise StoreError("first product observation requires reconciled Git transaction")
        if run_head is None:
            raise StoreError("first product observation requires canonical Run Head")
        if (
            run_head.revision != transaction.requested_base_revision
            or run_head.environment_digest != environment.digest
            or run_head.fixture_digest != current.fixture_intent_digest
        ):
            raise StoreError("canonical Run Head is not bound to start transaction")
        if current.mode == "running":
            return current
        if current.mode != "boot":
            raise StoreError("only boot run may enter running")
        next_state = current.with_mode("running")
        self._ensure_fact_event(
            "run_started",
            run_head.digest,
            "run-head",
            run_head,
            next_state,
        )
        return next_state

    def record_initial_run_head(self, run_id: str, run_head: RunHead) -> RunHead:
        self._require_run(run_id)
        current = self.read_state()
        existing = current.facts.run_head
        if existing is not None:
            if existing != run_head:
                raise StoreError("initial Run Head may not be replaced")
            return existing
        transaction = current.facts.git_transaction
        environment = current.facts.environment
        if current.mode != "boot":
            raise StoreError("initial Run Head must be recorded during boot")
        if transaction is None or transaction.status != "reconciled":
            raise StoreError("initial Run Head requires reconciled Git transaction")
        if environment is None:
            raise StoreError("initial Run Head requires sealed EnvironmentIdentity")
        if run_head.revision != transaction.requested_base_revision:
            raise StoreError("initial Run Head revision does not match Git transaction")
        if run_head.environment_digest != environment.digest:
            raise StoreError("initial Run Head environment does not match sealed identity")
        if run_head.fixture_digest != current.fixture_intent_digest:
            raise StoreError("initial Run Head fixture does not match Trajectory Brief")
        next_state = self._with_facts(current, run_head=run_head)
        self._ensure_fact_event(
            "initial_run_head_recorded",
            run_head.digest,
            "run-head",
            run_head,
            next_state,
        )
        return run_head

    def record_runtime_iteration(
        self, fact: IterationFact, next_state: RunState
    ) -> None:
        """Append one active-progress fact and its exact successor state."""

        self._ensure_fact_event(
            "runtime_iteration_recorded",
            fact.fact_id,
            "runtime-iteration",
            fact,
            next_state,
        )

    def record_product_work(
        self, receipt_id: str, receipt_digest: str, next_state: RunState
    ) -> None:
        """Persist issuer-referenced work; callers import only identity and digest."""

        if not isinstance(receipt_id, str) or not isinstance(receipt_digest, str):
            raise StoreError("product work requires issued receipt identity and digest")
        matches = tuple(
            receipt
            for receipt in next_state.facts.product_work
            if receipt.work_id == receipt_id and receipt.digest == receipt_digest
        )
        if len(matches) != 1:
            raise StoreError("product work requires issued receipt identity and digest")
        receipt = matches[0]
        self._ensure_fact_event(
            "product_work_accounted",
            receipt.work_id,
            "product-work",
            receipt,
            next_state,
        )

    def record_diagnostic_stall(
        self, report: PauseReport, next_state: RunState
    ) -> None:
        """Durably pause a run with one typed diagnostic-stall report."""

        self._ensure_fact_event(
            "diagnostic_stall_paused",
            report.node_id,
            "pause-report",
            report,
            next_state,
        )

    def record_user_decision(
        self, decision: UserDecision, next_state: RunState
    ) -> None:
        """Append exact user authority before resuming or terminalizing."""

        self._ensure_fact_event(
            "user_decision_applied",
            decision.decision_id,
            "user-decision",
            decision,
            next_state,
        )

    def record_escalation(
        self, pending: PendingDecision, next_state: RunState
    ) -> None:
        """Persist an explicit user-authority request before pausing execution."""

        self._ensure_fact_event(
            "escalation_requested",
            pending.decision_id,
            "pending-decision",
            pending,
            next_state,
        )

    def record_run_head_advanced(
        self,
        run_head: RunHead,
        next_state: RunState,
        *,
        artifacts: tuple[ArtifactRecord, ...] = (),
    ) -> None:
        """Persist role attestations and one Run Head transition as one rollback-safe unit."""

        event_record = ArtifactRecord.from_payload("run-head", run_head)
        reference = EventFactReference(
            fact_id=run_head.digest,
            fact_digest=event_record.digest,
        )
        self._append_event_with_artifacts(
            "run_head_advanced",
            reference,
            next_state,
            artifacts=(*artifacts, event_record),
            event_artifact=run_head,
        )

    def record_final_replay_started(self, run_head: RunHead, next_state: RunState) -> None:
        self._ensure_fact_event(
            "final_replay_started", run_head.digest, "run-head", run_head, next_state
        )

    def record_final_replay_succeeded(
        self,
        fact: IterationFact,
        next_state: RunState,
        *,
        semantic_output: object,
    ) -> None:
        from .proof import is_issuer_registered_output

        manifest = getattr(getattr(semantic_output, "dispatch", None), "manifest", None)
        current = self.read_state()
        appended_manifests = next_state.facts.role_manifests[
            len(current.facts.role_manifests) :
        ]
        if (
            not is_issuer_registered_output(semantic_output)
            or len(appended_manifests) != 1
            or appended_manifests[0] is not manifest
        ):
            raise StoreError("final replay success requires exact issuer-registered semantic output")
        self._ensure_fact_event(
            "final_replay_succeeded", fact.fact_id, "runtime-iteration", fact, next_state
        )

    def record_final_replay_reopened(
        self, fact: IterationFact, next_state: RunState
    ) -> None:
        self._ensure_fact_event(
            "final_replay_reopened", fact.fact_id, "runtime-iteration", fact, next_state
        )

    def record_review_infrastructure_pause(
        self, report: PauseReport, next_state: RunState
    ) -> None:
        self._ensure_fact_event(
            "review_infrastructure_paused", report.node_id, "pause-report", report, next_state
        )

    def recover(self) -> None:
        if not self._journal_path.exists():
            return
        if self._journal_declares_confirmed_genesis():
            self._rollback_interrupted_confirmed_genesis()
            return
        with self._lock():
            if not self._journal_path.exists():
                return
            try:
                journal = json.loads(self._journal_path.read_text(encoding="utf-8"))
                if journal.get("schema_version") != "v5.transaction-journal.v1":
                    raise RecoveryError("unsupported V5 transaction journal")
                state_bytes = base64.b64decode(journal["state_bytes_b64"], validate=True)
                event_line = base64.b64decode(journal["event_line_b64"], validate=True)
                state = RunState.model_validate_json(state_bytes)
                event = LedgerEvent.model_validate_json(event_line)
            except (KeyError, TypeError, ValueError, json.JSONDecodeError, ValidationError) as exc:
                raise RecoveryError("invalid V5 transaction journal") from exc
            if canonical_json_bytes(state) != state_bytes:
                raise RecoveryError("journal state is not canonical JSON")
            if canonical_json_bytes(event) + b"\n" != event_line:
                raise RecoveryError("journal event is not canonical JSON")
            self._require_run(state.run_id)
            if event.event_digest != journal.get("event_digest"):
                raise RecoveryError("journal event digest mismatch")
            if event.state_digest != state.digest:
                raise RecoveryError("journal event is not bound to replacement state")
            try:
                artifact_writes = self._journal_artifact_writes(journal)
            except StoreError as exc:
                raise RecoveryError("invalid V5 transaction journal artifacts") from exc
            ledger_bytes = (
                self._ledger_path.read_bytes() if self._ledger_path.exists() else b""
            )
            if ledger_bytes and not ledger_bytes.endswith(b"\n"):
                last_boundary = ledger_bytes.rfind(b"\n") + 1
                complete_ledger = ledger_bytes[:last_boundary]
                incomplete_tail = ledger_bytes[last_boundary:]
                if not event_line.startswith(incomplete_tail):
                    raise RecoveryError(
                        "incomplete ledger tail does not match journal event"
                    )
                events = self._decode_events(complete_ledger)
                if len(events) != event.sequence - 1:
                    raise RecoveryError(
                        "incomplete ledger tail conflicts with journal sequence"
                    )
                expected_previous = (
                    events[-1].event_digest if events else _GENESIS_DIGEST
                )
                if event.previous_digest != expected_previous:
                    raise RecoveryError("journal event does not extend current ledger")
                for record in artifact_writes:
                    self._write_artifact_record_unlocked(record)
                self._atomic_write(self._state_path, state_bytes)
                self._atomic_write(self._ledger_path, complete_ledger + event_line)
                self._remove_exact_file(self._journal_path)
                return
            events = self._decode_events(ledger_bytes)
            if len(events) == event.sequence - 1:
                expected_previous = events[-1].event_digest if events else _GENESIS_DIGEST
                if event.previous_digest != expected_previous:
                    raise RecoveryError("journal event does not extend current ledger")
                for record in artifact_writes:
                    self._write_artifact_record_unlocked(record)
                self._atomic_write(self._state_path, state_bytes)
                self._append_bytes(self._ledger_path, event_line)
            elif len(events) == event.sequence:
                if events[-1].event_digest != event.event_digest:
                    raise RecoveryError("ledger position already contains another event")
                for record in artifact_writes:
                    self._write_artifact_record_unlocked(record)
                if not self._state_path.exists() or self._state_path.read_bytes() != state_bytes:
                    self._atomic_write(self._state_path, state_bytes)
            else:
                raise RecoveryError("journal event sequence conflicts with ledger")
            self._remove_exact_file(self._journal_path)

    def put_artifact(self, domain: str, payload: Any) -> ArtifactRecord:
        self.read_state()
        record = ArtifactRecord.from_payload(domain, payload)
        self.put_artifact_at_digest(
            domain, record.digest, record.payload, media_type=record.media_type
        )
        return record

    def put_artifact_at_digest(
        self,
        domain: str,
        digest: str,
        payload: bytes,
        *,
        media_type: str = "application/json",
    ) -> None:
        self.read_state()
        record = ArtifactRecord(
            domain=domain, digest=digest, payload=payload, media_type=media_type
        )
        self._validate_artifact_record(record)
        with self._lock():
            self._write_artifact_record_unlocked(record)

    def read_artifact_bytes(self, domain: str, digest: str) -> bytes:
        """Read exact content-addressed artifact bytes without JSON coercion."""

        self._validate_artifact_address(domain, digest)
        path = self._root / "artifacts" / f"{digest}.json"
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise StoreError(f"artifact is not readable: {digest}") from exc
        if digest_bytes(domain, payload) != digest:
            raise StoreError("artifact content digest mismatch")
        return payload

    def read_artifact(self, domain: str, digest: str) -> Any:
        try:
            payload = self.read_artifact_bytes(domain, digest)
            decoded = json.loads(payload.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StoreError(f"artifact is not readable: {digest}") from exc
        if canonical_json_bytes(decoded) != payload:
            raise StoreError("artifact payload is not canonical JSON")
        return decoded

    @staticmethod
    def _validate_artifact_address(domain: str, digest: str) -> None:
        if not isinstance(domain, str) or not domain.strip():
            raise StoreError("artifact domain must be a non-empty string")
        if not isinstance(digest, str) or not _SHA256_HEX.fullmatch(digest):
            raise StoreError("artifact digest must be a SHA-256 hexadecimal string")

    def _ensure_fact_event(
        self,
        kind: EventKind,
        fact_id: str,
        domain: str,
        fact: StrictModel,
        next_state: RunState,
    ) -> None:
        record = self.put_artifact(domain, fact)
        reference = EventFactReference(fact_id=fact_id, fact_digest=record.digest)
        for event in self.read_events():
            if event.kind == kind and event.payload == reference and event.state_digest == next_state.digest:
                return
        self.append_event(kind, reference, next_state)

    def _append_event_with_artifacts(
        self,
        kind: EventKind,
        payload: StrictModel,
        next_state: RunState,
        *,
        artifacts: tuple[ArtifactRecord, ...],
        event_artifact: StrictModel,
    ) -> None:
        """Atomically record prerequisite artifacts with one state/ledger transition."""

        if kind not in _EVENT_KINDS:
            raise StoreError(f"unknown V5 event kind: {kind}")
        next_state = self._revalidate_run_state(next_state)
        self._require_run(next_state.run_id)
        reference = self._event_reference(payload)
        self.recover()
        with self._lock():
            events = self._read_events_unrecovered()
            current_state = self._read_state_unrecovered()
            if events and events[-1].state_digest != current_state.digest:
                raise StoreError("canonical V5 state digest is not bound to ledger head")
            if any(
                event.kind == kind
                and event.payload == reference
                and event.state_digest == next_state.digest
                for event in events
            ):
                return
            self._validate_successor(current_state, next_state)
            self._validate_task4_event_transition(
                kind, current_state, next_state, reference
            )
            if kind == "run_head_advanced" and event_artifact != next_state.facts.run_head:
                raise StoreError("run_head_advanced artifact is not bound to canonical state")
            for record in artifacts:
                self._validate_artifact_record(record)
            event = LedgerEvent.create(
                sequence=len(events) + 1,
                kind=kind,
                payload=reference,
                previous_digest=events[-1].event_digest if events else _GENESIS_DIGEST,
                state_digest=next_state.digest,
            )
            state_bytes = canonical_json_bytes(next_state)
            event_line = canonical_json_bytes(event) + b"\n"
            state_before = self._state_path.read_bytes()
            ledger_existed = self._ledger_path.exists()
            ledger_before = self._ledger_path.read_bytes() if ledger_existed else b""
            artifact_paths = {
                self._artifact_path(record): record for record in artifacts
            }
            if len(artifact_paths) != len(artifacts):
                raise StoreError("transaction artifact addresses must be unique")
            created_artifacts = [
                path for path in artifact_paths if not path.exists()
            ]
            journal = {
                "schema_version": "v5.transaction-journal.v1",
                "state_bytes_b64": base64.b64encode(state_bytes).decode("ascii"),
                "event_line_b64": base64.b64encode(event_line).decode("ascii"),
                "event_digest": event.event_digest,
                "artifact_writes": [
                    {
                        "domain": record.domain,
                        "digest": record.digest,
                        "payload_b64": base64.b64encode(record.payload).decode("ascii"),
                        "media_type": record.media_type,
                    }
                    for record in artifacts
                ],
            }
            journal_written = False
            state_replaced = False
            ledger_append_started = False
            written_artifacts: list[Path] = []
            try:
                self._atomic_write(self._journal_path, canonical_json_bytes(journal))
                journal_written = True
                for path, record in artifact_paths.items():
                    self._write_artifact_record_unlocked(record)
                    if path in created_artifacts:
                        written_artifacts.append(path)
                self._atomic_write(self._state_path, state_bytes)
                state_replaced = True
                ledger_append_started = True
                self._append_bytes(self._ledger_path, event_line)
            except OSError:
                if ledger_append_started:
                    self._restore_exact_file(
                        self._ledger_path, ledger_existed, ledger_before
                    )
                if state_replaced:
                    self._atomic_write(self._state_path, state_before)
                for path in reversed(written_artifacts):
                    self._remove_exact_file(path)
                if journal_written:
                    self._remove_exact_file(self._journal_path)
                raise
            try:
                self._remove_exact_file(self._journal_path)
            except OSError:
                # Ledger and state are already durable; recovery can remove this journal.
                pass

    def _write_confirmed_genesis_transaction(
        self,
        state: RunState,
        event: LedgerEvent,
        artifacts: tuple[ArtifactRecord, ...],
        *,
        root_existed: bool,
        lock_existed: bool,
        lock_bytes: bytes,
        artifacts_directory_existed: bool,
        interrupt_after: Literal[
            "journal_written",
            "trajectory_artifact_written",
            "markdown_artifact_written",
            "confirmation_artifact_written",
            "binding_artifact_written",
            "state_replaced",
            "ledger_appended",
        ]
        | None,
    ) -> None:
        """All-or-nothing first durable state. Failure restores prior bytes."""

        if state.facts.trajectory_binding is None:
            raise StoreError("confirmed genesis state requires trajectory binding")
        if event.kind != "trajectory_confirmed" or event.sequence != 1:
            raise StoreError("confirmed genesis requires first trajectory_confirmed event")
        if event.state_digest != state.digest:
            raise StoreError("confirmed genesis event does not bind genesis state")
        for record in artifacts:
            self._validate_artifact_record(record)
        artifact_paths = {self._artifact_path(record): record for record in artifacts}
        if len(artifact_paths) != len(artifacts):
            raise StoreError("confirmed genesis artifact addresses must be unique")
        if any(path.exists() for path in artifact_paths):
            raise StoreError("confirmed genesis artifacts must not already exist")
        state_bytes = canonical_json_bytes(state)
        event_line = canonical_json_bytes(event) + b"\n"
        journal = {
            "schema_version": "v5.transaction-journal.v1",
            "transaction_kind": "confirmed_genesis",
            "state_bytes_b64": base64.b64encode(state_bytes).decode("ascii"),
            "event_line_b64": base64.b64encode(event_line).decode("ascii"),
            "event_digest": event.event_digest,
            "genesis_rollback": {
                "root_existed": root_existed,
                "lock_existed": lock_existed,
                "lock_bytes_b64": base64.b64encode(lock_bytes).decode("ascii"),
                "artifacts_directory_existed": artifacts_directory_existed,
            },
            "artifact_writes": [
                {
                    "domain": record.domain,
                    "digest": record.digest,
                    "payload_b64": base64.b64encode(record.payload).decode("ascii"),
                    "media_type": record.media_type,
                }
                for record in artifacts
            ],
        }
        try:
            self._atomic_write(self._journal_path, canonical_json_bytes(journal))
            if interrupt_after == "journal_written":
                raise SimulatedCrash("injected crash after confirmed genesis journal")
            boundaries = (
                "trajectory_artifact_written",
                "markdown_artifact_written",
                "confirmation_artifact_written",
                "binding_artifact_written",
            )
            for record, boundary in zip(artifacts, boundaries, strict=True):
                path = self._artifact_path(record)
                self._write_artifact_record_unlocked(record)
                if interrupt_after == boundary:
                    raise SimulatedCrash(f"injected crash after {boundary}")
            self._atomic_write(self._state_path, state_bytes)
            if interrupt_after == "state_replaced":
                raise SimulatedCrash("injected crash after confirmed genesis state")
            self._append_bytes(self._ledger_path, event_line)
            if interrupt_after == "ledger_appended":
                raise SimulatedCrash("injected crash after confirmed genesis ledger")
            self._remove_exact_file(self._journal_path)
        except (OSError, SimulatedCrash):
            self._remove_exact_file(self._ledger_path)
            self._remove_exact_file(self._state_path)
            for path in reversed(tuple(artifact_paths)):
                self._remove_exact_file(path)
            self._remove_exact_file(self._journal_path)
            raise

    def _journal_declares_confirmed_genesis(self) -> bool:
        try:
            journal = json.loads(self._journal_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return False
        return (
            isinstance(journal, dict)
            and journal.get("transaction_kind") == "confirmed_genesis"
        )

    def _rollback_interrupted_confirmed_genesis(self) -> None:
        """Recover process death by restoring exact pre-genesis container state."""

        with self._lock():
            try:
                journal = json.loads(self._journal_path.read_text(encoding="utf-8"))
                if (
                    journal.get("schema_version") != "v5.transaction-journal.v1"
                    or journal.get("transaction_kind") != "confirmed_genesis"
                ):
                    raise RecoveryError("invalid confirmed genesis journal")
                state_bytes = base64.b64decode(
                    journal["state_bytes_b64"], validate=True
                )
                event_line = base64.b64decode(
                    journal["event_line_b64"], validate=True
                )
                state = RunState.model_validate_json(state_bytes)
                event = LedgerEvent.model_validate_json(event_line)
                rollback = journal["genesis_rollback"]
                if not isinstance(rollback, dict) or set(rollback) != {
                    "root_existed",
                    "lock_existed",
                    "lock_bytes_b64",
                    "artifacts_directory_existed",
                }:
                    raise RecoveryError("invalid confirmed genesis rollback metadata")
                root_existed = rollback["root_existed"]
                lock_existed = rollback["lock_existed"]
                artifacts_directory_existed = rollback[
                    "artifacts_directory_existed"
                ]
                if not all(
                    isinstance(value, bool)
                    for value in (
                        root_existed,
                        lock_existed,
                        artifacts_directory_existed,
                    )
                ):
                    raise RecoveryError("invalid confirmed genesis rollback metadata")
                lock_bytes = base64.b64decode(
                    rollback["lock_bytes_b64"], validate=True
                )
                artifacts = self._journal_artifact_writes(journal)
            except RecoveryError:
                raise
            except (
                KeyError,
                TypeError,
                ValueError,
                json.JSONDecodeError,
                ValidationError,
            ) as exc:
                raise RecoveryError("invalid confirmed genesis journal") from exc
            if (
                canonical_json_bytes(state) != state_bytes
                or canonical_json_bytes(event) + b"\n" != event_line
                or event.kind != "trajectory_confirmed"
                or event.sequence != 1
                or event.previous_digest != _GENESIS_DIGEST
                or event.state_digest != state.digest
                or event.event_digest != journal.get("event_digest")
            ):
                raise RecoveryError("confirmed genesis journal binding is invalid")
            if self._state_path.exists() and self._state_path.read_bytes() != state_bytes:
                raise RecoveryError("confirmed genesis state rollback bytes conflict")
            ledger_bytes = (
                self._ledger_path.read_bytes() if self._ledger_path.exists() else b""
            )
            if ledger_bytes and not event_line.startswith(ledger_bytes):
                raise RecoveryError("confirmed genesis ledger rollback bytes conflict")
            for record in artifacts:
                path = self._artifact_path(record)
                if path.exists() and path.read_bytes() != record.payload:
                    raise RecoveryError(
                        "confirmed genesis artifact rollback bytes conflict"
                    )
            self._remove_exact_file(self._ledger_path)
            self._remove_exact_file(self._state_path)
            for record in artifacts:
                self._remove_exact_file(self._artifact_path(record))

        self._restore_exact_file(self._lock_path, lock_existed, lock_bytes)
        artifacts_directory = self._root / "artifacts"
        try:
            if not artifacts_directory_existed and artifacts_directory.exists():
                artifacts_directory.rmdir()
            self._remove_exact_file(self._journal_path)
            if not root_existed:
                self._root.rmdir()
        except OSError as exc:
            raise RecoveryError(
                "confirmed genesis recovery could not restore prior container"
            ) from exc

    @staticmethod
    def _restore_exact_file(path: Path, existed: bool, payload: bytes) -> None:
        if existed:
            TransactionalRunStore._atomic_write(path, payload)
        else:
            TransactionalRunStore._remove_exact_file(path)

    def _artifact_path(self, record: ArtifactRecord) -> Path:
        return self._root / "artifacts" / f"{record.digest}.json"

    def _validate_artifact_record(self, record: ArtifactRecord) -> None:
        self._validate_artifact_address(record.domain, record.digest)
        if not isinstance(record.media_type, str) or not record.media_type.strip():
            raise StoreError("artifact media type must be a non-empty string")
        if record.media_type == "application/json":
            try:
                decoded = json.loads(record.payload.decode("utf-8"))
            except (AttributeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise StoreError("artifact payload must be canonical JSON bytes") from exc
            if canonical_json_bytes(decoded) != record.payload:
                raise StoreError("artifact payload must be canonical JSON bytes")
        if digest_bytes(record.domain, record.payload) != record.digest:
            raise StoreError("artifact content digest mismatch")

    def _write_artifact_record_unlocked(self, record: ArtifactRecord) -> None:
        path = self._artifact_path(record)
        if path.exists():
            if path.read_bytes() != record.payload:
                raise StoreError("append-only artifact already exists with different bytes")
            return
        self._atomic_write(path, record.payload)

    def _journal_artifact_writes(
        self, journal: object,
    ) -> tuple[ArtifactRecord, ...]:
        if not isinstance(journal, dict):
            raise StoreError("transaction journal is not an object")
        raw_records = journal.get("artifact_writes", [])
        if not isinstance(raw_records, list):
            raise StoreError("transaction journal artifacts are invalid")
        records: list[ArtifactRecord] = []
        for raw in raw_records:
            if not isinstance(raw, dict) or set(raw) not in (
                {"domain", "digest", "payload_b64"},
                {"domain", "digest", "payload_b64", "media_type"},
            ):
                raise StoreError("transaction journal artifacts are invalid")
            try:
                record = ArtifactRecord(
                    domain=raw["domain"],
                    digest=raw["digest"],
                    payload=base64.b64decode(raw["payload_b64"], validate=True),
                    media_type=raw.get("media_type", "application/json"),
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise StoreError("transaction journal artifacts are invalid") from exc
            self._validate_artifact_record(record)
            records.append(record)
        paths = {self._artifact_path(record) for record in records}
        if len(paths) != len(records):
            raise StoreError("transaction journal artifact addresses must be unique")
        return tuple(records)

    @staticmethod
    def _with_facts(current: RunState, **updates: object) -> RunState:
        facts = current.facts.model_copy(update=updates)
        return current.model_copy(update={"facts": facts})

    def _read_state_unrecovered(self) -> RunState:
        try:
            state = RunState.model_validate_json(self._state_path.read_bytes())
        except (OSError, ValidationError) as exc:
            raise StoreError("canonical V5 state is missing or invalid") from exc
        self._require_run(state.run_id)
        return state

    def _read_events_unrecovered(self) -> tuple[LedgerEvent, ...]:
        if not self._ledger_path.exists():
            return ()
        try:
            payload = self._ledger_path.read_bytes()
        except OSError as exc:
            raise StoreError("V5 ledger is unreadable") from exc
        return self._decode_events(payload)

    @staticmethod
    def _decode_events(payload: bytes) -> tuple[LedgerEvent, ...]:
        if payload and not payload.endswith(b"\n"):
            raise StoreError("V5 ledger must end each record with a newline")
        events: list[LedgerEvent] = []
        try:
            for record in payload.splitlines(keepends=True):
                line = record.removesuffix(b"\n")
                event = LedgerEvent.model_validate_json(line)
                if canonical_json_bytes(event) != line:
                    raise StoreError("V5 ledger event is not canonical JSON")
                events.append(event)
        except ValidationError as exc:
            raise StoreError("V5 ledger is unreadable") from exc
        previous = _GENESIS_DIGEST
        for sequence, event in enumerate(events, start=1):
            if event.sequence != sequence or event.previous_digest != previous:
                raise StoreError("V5 ledger hash chain is discontinuous")
            previous = event.event_digest
        return tuple(events)

    def _require_run(self, run_id: str) -> None:
        if run_id != self._capability.run_id:
            raise CapabilityError("capability does not permit this run")

    @staticmethod
    def _revalidate_run_state(state: RunState) -> RunState:
        if not isinstance(state, RunState):
            raise StoreError("state does not satisfy strict RunState schema")
        try:
            return RunState.model_validate(
                state.model_dump(mode="python", warnings=False)
            )
        except ValidationError as exc:
            raise StoreError("state does not satisfy strict RunState schema") from exc

    @staticmethod
    def _event_reference(payload: StrictModel) -> EventFactReference:
        if not isinstance(payload, StrictModel):
            raise StoreError("ledger event payload must be a typed V5 fact reference")
        try:
            return EventFactReference.model_validate(payload.model_dump())
        except ValidationError as exc:
            raise StoreError("ledger event payload must be a typed V5 fact reference") from exc

    def _read_task4_event_artifact(
        self, kind: EventKind, reference: EventFactReference
    ) -> StrictModel | None:
        specification = _TASK4_EVENT_ARTIFACTS.get(kind)
        if specification is None:
            return None
        domain, model_type = specification
        payload = self.read_artifact(domain, reference.fact_digest)
        try:
            return model_type.model_validate_json(canonical_json_bytes(payload))
        except ValidationError as exc:
            raise StoreError(
                f"{kind} artifact does not satisfy strict V5 schema"
            ) from exc

    def _validate_task4_event_artifact_binding(
        self,
        kind: EventKind,
        current: RunState,
        successor: RunState,
        artifact: StrictModel | None,
    ) -> None:
        if kind == "trajectory_confirmed":
            binding = successor.facts.trajectory_binding
            if artifact != binding or binding is None:
                raise StoreError("trajectory_confirmed artifact is not bound to canonical state")
            return
        if kind in {
            "derived_spine_initialized", "derived_spine_sealed", "derived_spine_result_recorded"
        }:
            spine = successor.facts.derived_spine
            if artifact != spine or spine is None:
                raise StoreError(f"{kind} artifact is not bound to canonical state")
            return
        if kind == "derived_spine_frozen":
            frozen = successor.facts.frozen_derived_spines[-1] if successor.facts.frozen_derived_spines else None
            if (
                not isinstance(artifact, FrozenDerivedSpine)
                or frozen != artifact
                or not successor.facts.frozen_derived_spines
                or successor.facts.frozen_derived_spines[:-1] != current.facts.frozen_derived_spines
                or reference.fact_id != artifact.digest
            ):
                raise StoreError("frozen Derived Spine artifact is not bound to canonical state")
            return
        if kind == "trajectory_pause_resumed":
            pause = current.facts.trajectory_pauses[-1] if current.facts.trajectory_pauses else None
            if artifact != pause or pause is None:
                raise StoreError("trajectory pause resume artifact is not bound to canonical state")
            return
        if kind == "trajectory_successor_confirmed":
            link = (
                successor.facts.trajectory_successors[-1]
                if successor.facts.trajectory_successors
                else None
            )
            if artifact != link or link is None:
                raise StoreError("trajectory successor artifact is not bound to canonical state")
            return
        if kind == "runtime_iteration_recorded":
            if (
                not isinstance(artifact, IterationFact)
                or not successor.facts.iteration_facts
                or artifact != successor.facts.iteration_facts[-1]
            ):
                raise StoreError("runtime iteration artifact is not bound to canonical state")
            return
        if kind == "product_work_accounted":
            if (
                not isinstance(artifact, ProductWorkReceipt)
                or not successor.facts.product_work
                or artifact != successor.facts.product_work[-1]
            ):
                raise StoreError("product work artifact is not bound to canonical state")
            return
        if kind == "diagnostic_stall_paused":
            if (
                not isinstance(artifact, PauseReport)
                or not successor.facts.pause_reports
                or artifact != successor.facts.pause_reports[-1]
                or artifact != successor.facts.pause_report
                or not successor.facts.pending_decision_history
                or successor.pending_decision is None
                or successor.facts.pending_decision_history[-1]
                != successor.pending_decision
            ):
                raise StoreError("diagnostic stall artifact is not bound to canonical state")
            return
        if kind == "user_decision_applied":
            if (
                not isinstance(artifact, UserDecision)
                or not successor.facts.user_decisions
                or artifact != successor.facts.user_decisions[-1]
            ):
                raise StoreError("user decision artifact is not bound to canonical state")
            return
        if kind == "escalation_requested":
            if (
                not isinstance(artifact, PendingDecision)
                or not successor.facts.pending_decision_history
                or artifact != successor.facts.pending_decision_history[-1]
                or artifact != successor.pending_decision
            ):
                raise StoreError("escalation artifact is not bound to canonical state")
            return
        if kind == "bootstrap_intended" and artifact != successor.facts.bootstrap_intent:
            raise StoreError("bootstrap_intended artifact is not bound to canonical state")
        if kind == "host_preflighted":
            intent = current.facts.bootstrap_intent
            if intent is None or not isinstance(artifact, HostPreflightReceipt):
                raise StoreError("host_preflighted artifact is not bound to Bootstrap Intent")
            self._assert_host_preflight_binding(intent, artifact)
        if kind == "git_transaction_recorded" and artifact != successor.facts.git_transaction:
            raise StoreError("git_transaction_recorded artifact is not bound to canonical state")
        if kind == "environment_sealed" and artifact != successor.facts.environment:
            raise StoreError("environment_sealed artifact is not bound to canonical state")
        if kind == "initial_run_head_recorded" and artifact != successor.facts.run_head:
            raise StoreError("initial_run_head_recorded artifact is not bound to canonical state")
        if kind == "run_started" and artifact != current.facts.run_head:
            raise StoreError("run_started artifact is not bound to canonical Run Head")

    def _validate_task4_replay_artifact_binding(
        self,
        kind: EventKind,
        reference: EventFactReference,
        state: RunState,
        artifact: StrictModel | None,
        *,
        graph_revision: int,
        prior_spine: DerivedSpine | None = None,
    ) -> None:
        if kind == "trajectory_confirmed":
            binding = artifact if isinstance(artifact, ConfirmedTrajectoryBinding) else None
            root_trajectory_digest = (
                state.facts.trajectory_successors[0].predecessor_trajectory_digest
                if state.facts.trajectory_successors
                else state.trajectory_digest
            )
            if (
                binding is None
                or reference.fact_id != binding.run_id
                or binding.run_id != state.run_id
                or binding.trajectory_digest != root_trajectory_digest
            ):
                raise StoreError("trajectory_confirmed artifact is not bound on replay")
        elif kind == "derived_spine_initialized":
            if (
                not isinstance(artifact, DerivedSpine)
                or prior_spine is not None
                or artifact.nodes
                or artifact.results
                or reference.fact_id != artifact.trajectory_digest
                or reference.fact_digest != artifact.digest
            ):
                raise StoreError("derived_spine_initialized artifact is not bound on replay")
        elif kind in {"derived_spine_sealed", "derived_spine_result_recorded"}:
            common_invalid = (
                not isinstance(artifact, DerivedSpine)
                or not artifact.nodes
                or reference.fact_id != artifact.nodes[-1].node_id
                or reference.fact_digest != artifact.digest
            )
            if kind == "derived_spine_sealed":
                transition_invalid = (
                    (prior_spine is None and (
                        len(artifact.nodes) != 1 or artifact.results
                    ))
                    or (
                        prior_spine is not None
                        and (
                            prior_spine.frontier.unexecuted_node_id is not None
                            or artifact.nodes[: len(prior_spine.nodes)]
                            != prior_spine.nodes
                            or artifact.results != prior_spine.results
                            or len(artifact.nodes) != len(prior_spine.nodes) + 1
                            or (
                                prior_spine.frontier.target_landmark_id is None
                                and (
                                    not self._replay_repair_ready(state, prior_spine)
                                    or artifact.nodes[-1].target_landmark_id
                                    != prior_spine.landmark_order[-1]
                                )
                            )
                        )
                    )
                )
            else:
                transition_invalid = (
                    prior_spine is None
                    or prior_spine.frontier.unexecuted_node_id is None
                    or artifact.nodes != prior_spine.nodes
                    or artifact.results[: len(prior_spine.results)]
                    != prior_spine.results
                    or len(artifact.results) != len(prior_spine.results) + 1
                )
            if common_invalid or transition_invalid:
                raise StoreError(f"{kind} artifact is not bound on replay")
        elif kind == "derived_spine_frozen":
            spine = prior_spine
            if (
                not isinstance(artifact, FrozenDerivedSpine)
                or spine is None
                or artifact.run_id != spine.run_id
                or artifact.trajectory_digest != spine.trajectory_digest
                or artifact.derived_spine_digest != spine.digest
                or artifact.landmark_mapping_digest != spine.landmark_mapping_digest
                or artifact.landmark_order != spine.landmark_order
                or artifact.frontier != spine.frontier
                or artifact.nodes != spine.nodes
                or artifact.results != spine.results
                or artifact.run_head != state.facts.run_head
                or artifact.environment != state.facts.environment
                or artifact.fixture_digest != state.fixture_intent_digest
                or artifact.graph_revision != graph_revision
                or artifact not in state.facts.frozen_derived_spines
                or reference.fact_id != artifact.digest
                or reference.fact_digest != artifact.digest
            ):
                raise StoreError("frozen Derived Spine artifact is not bound on replay")
        elif kind == "runtime_iteration_recorded":
            if (
                not isinstance(artifact, IterationFact)
                or artifact not in state.facts.iteration_facts
                or reference.fact_id != artifact.fact_id
            ):
                raise StoreError("runtime iteration artifact is not bound on replay")
        elif kind == "observed":
            if (
                not isinstance(artifact, Observation)
                or artifact not in state.facts.observations
                or reference.fact_id != artifact.observation_id
            ):
                raise StoreError("observation artifact is not bound on replay")
        elif kind == "trajectory_pause_recorded":
            if (
                not isinstance(artifact, TrajectoryPause)
                or artifact not in state.facts.trajectory_pauses
                or reference.fact_id != artifact.reason
            ):
                raise StoreError("trajectory pause artifact is not bound on replay")
        elif kind == "trajectory_pause_resumed":
            if (
                not isinstance(artifact, TrajectoryPause)
                or artifact not in state.facts.trajectory_pauses
                or reference.fact_id != artifact.digest
            ):
                raise StoreError("trajectory pause resume artifact is not bound on replay")
        elif kind == "trajectory_decision_requested":
            if (
                not isinstance(artifact, PendingTrajectoryDecision)
                or artifact not in state.facts.pending_trajectory_decisions
                or reference.fact_id != artifact.decision_id
            ):
                raise StoreError("trajectory decision artifact is not bound on replay")
        elif kind == "trajectory_successor_confirmed":
            if (
                not isinstance(artifact, TrajectorySuccessor)
                or artifact not in state.facts.trajectory_successors
                or reference.fact_id != artifact.successor_trajectory_digest
            ):
                raise StoreError("trajectory successor artifact is not bound on replay")
        elif kind == "product_work_accounted":
            if (
                not isinstance(artifact, ProductWorkReceipt)
                or artifact not in state.facts.product_work
                or reference.fact_id != artifact.work_id
            ):
                raise StoreError("product work artifact is not bound on replay")
        elif kind == "diagnostic_stall_paused":
            if (
                not isinstance(artifact, PauseReport)
                or artifact not in state.facts.pause_reports
                or reference.fact_id != artifact.node_id
            ):
                raise StoreError("diagnostic stall artifact is not bound on replay")
        elif kind == "user_decision_applied":
            if (
                not isinstance(artifact, UserDecision)
                or artifact not in state.facts.user_decisions
                or reference.fact_id != artifact.decision_id
            ):
                raise StoreError("user decision artifact is not bound on replay")
        elif kind == "escalation_requested":
            if (
                not isinstance(artifact, PendingDecision)
                or artifact not in state.facts.pending_decision_history
                or reference.fact_id != artifact.decision_id
            ):
                raise StoreError("escalation artifact is not bound on replay")
        elif kind == "bootstrap_intended":
            intent = state.facts.bootstrap_intent
            if artifact != intent or intent is None or reference.fact_id != intent.transaction_id:
                raise StoreError("bootstrap_intended artifact is not bound on replay")
        elif kind == "host_preflighted":
            intent = state.facts.bootstrap_intent
            if intent is None or not isinstance(artifact, HostPreflightReceipt):
                raise StoreError("host_preflighted artifact is not bound on replay")
            if reference.fact_id != intent.transaction_id:
                raise StoreError("host_preflighted artifact is not bound on replay")
            self._assert_host_preflight_binding(intent, artifact)
        elif kind == "git_transaction_recorded":
            final = state.facts.git_transaction
            if not isinstance(artifact, GitTransaction) or final is None:
                raise StoreError("git_transaction_recorded artifact is not bound on replay")
            if (
                reference.fact_id != artifact.transaction_id
                or artifact.transaction_id != final.transaction_id
                or artifact.requested_base_revision != final.requested_base_revision
                or artifact.branch != final.branch
                or artifact.worktree_path != final.worktree_path
            ):
                raise StoreError("git_transaction_recorded artifact is not bound on replay")
        elif kind == "environment_sealed":
            environment = state.facts.environment
            if (
                artifact != environment
                or environment is None
                or reference.fact_id != environment.digest
            ):
                raise StoreError("environment_sealed artifact is not bound on replay")
        elif kind in {"initial_run_head_recorded", "run_started", "run_head_advanced", "final_replay_started"}:
            run_head = state.facts.run_head
            if (
                artifact != run_head
                or run_head is None
                or reference.fact_id != run_head.digest
            ):
                raise StoreError(f"{kind} artifact is not bound on replay")

    @staticmethod
    def _validate_task4_event_transition(
        kind: EventKind,
        current: RunState,
        successor: RunState,
        reference: EventFactReference,
    ) -> None:
        if kind == "derived_spine_initialized":
            spine = successor.facts.derived_spine
            valid = (
                current.facts.derived_spine is None
                and spine is not None
                and current.mode == successor.mode == "running"
                and spine.run_id == current.run_id
                and spine.trajectory_digest == current.trajectory_digest
                and not spine.nodes
                and not spine.results
                and reference.fact_id == spine.trajectory_digest
                and reference.fact_digest == spine.digest
                and successor
                == current.model_copy(
                    update={
                        "facts": current.facts.model_copy(
                            update={"derived_spine": spine}
                        )
                    }
                )
            )
            if not valid:
                raise StoreError("initial Derived Spine must bind confirmed trajectory frontier")
            return
        if kind == "observed":
            if current.mode != successor.mode:
                raise StoreError("observed may not change protected start state without bound transition")
            observation = successor.facts.observations[-1] if successor.facts.observations else None
            run_head = current.facts.run_head
            valid = (
                observation is not None
                and current.mode in {"running", "final_replay"}
                and run_head is not None
                and observation.run_head_digest == run_head.digest
                and not TransactionalRunStore._observation_uses_author_signal(
                    current, observation
                )
                and successor.facts.observations
                == current.facts.observations + (observation,)
                and reference.fact_id == observation.observation_id
                and successor
                == current.model_copy(
                    update={
                        "facts": current.facts.model_copy(
                            update={"observations": current.facts.observations + (observation,)}
                        )
                    }
                )
            )
            if not valid:
                raise StoreError("observed event must append one independent current-head observation")
            return
        if kind == "trajectory_pause_recorded":
            pause = successor.facts.trajectory_pauses[-1] if successor.facts.trajectory_pauses else None
            spine = current.facts.derived_spine
            expected_observation_refs = tuple(
                dict.fromkeys(
                    item
                    for observation in current.facts.observations
                    for item in observation.evidence_refs
                )
            )
            expected_anchor = None
            if spine is not None:
                if not spine.nodes:
                    expected_anchor = "START"
                else:
                    last_result = spine.results[-1] if spine.results else None
                    expected_anchor = (
                        spine.nodes[-1].target_landmark_id
                        if last_result is not None and last_result.landmark_satisfied
                        else spine.nodes[-1].node_id
                    )
            valid = (
                pause is not None
                and current.mode == "running"
                and successor.mode == "paused"
                and spine is not None
                and pause.trajectory_digest == current.trajectory_digest
                and pause.frontier_digest == spine.digest
                and pause.frontier_anchor_id == expected_anchor
                and pause.target_landmark_id == spine.frontier.target_landmark_id
                and pause.observation_refs == expected_observation_refs
                and successor.facts.trajectory_pauses
                == current.facts.trajectory_pauses + (pause,)
                and reference.fact_id == pause.reason
                and successor.facts.model_copy(
                    update={"trajectory_pauses": current.facts.trajectory_pauses + (pause,)}
                )
                == current.facts.model_copy(
                    update={"trajectory_pauses": current.facts.trajectory_pauses + (pause,)}
                )
            )
            if not valid:
                raise StoreError("trajectory pause must bind current persisted frontier")
            return
        if kind == "trajectory_pause_resumed":
            pause = current.trajectory_pause
            valid = (
                pause is not None
                and current.mode == "paused"
                and successor.mode == "running"
                and successor.facts == current.facts
                and successor.trajectory == current.trajectory
                and successor.limits == current.limits
                and successor.pending_decision == current.pending_decision
                and reference.fact_id == pause.digest
                and reference.fact_digest == pause.digest
            )
            if not valid:
                raise StoreError("trajectory pause resume must bind exact persisted pause")
            return
        if kind == "trajectory_decision_requested":
            decision = (
                successor.facts.pending_trajectory_decisions[-1]
                if successor.facts.pending_trajectory_decisions
                else None
            )
            spine = current.facts.derived_spine
            valid = (
                decision is not None
                and current.mode == "running"
                and successor.mode == "paused"
                and spine is not None
                and decision.run_id == current.run_id
                and decision.trajectory_digest == current.trajectory_digest
                and decision.frontier_digest == spine.digest
                and successor.facts.pending_trajectory_decisions
                == current.facts.pending_trajectory_decisions + (decision,)
                and reference.fact_id == decision.decision_id
                and successor.facts.model_copy(
                    update={
                        "pending_trajectory_decisions": (
                            current.facts.pending_trajectory_decisions + (decision,)
                        )
                    }
                )
                == current.facts.model_copy(
                    update={
                        "pending_trajectory_decisions": (
                            current.facts.pending_trajectory_decisions + (decision,)
                        )
                    }
                )
            )
            if not valid:
                raise StoreError("trajectory decision must bind current persisted frontier")
            return
        if kind == "trajectory_successor_confirmed":
            link = successor.facts.trajectory_successors[-1] if successor.facts.trajectory_successors else None
            valid = (
                link is not None
                and link.predecessor_trajectory_digest == current.trajectory_digest
                and current.pending_trajectory_decision is not None
                and current.pending_trajectory_decision.digest == link.decision_digest
                and not any(
                    item.decision_digest == link.decision_digest
                    for item in current.facts.trajectory_successors
                )
                and successor.facts.trajectory_successors
                == current.facts.trajectory_successors + (link,)
                and current.mode == "paused"
                and successor.mode == "running"
                and successor.trajectory_digest == link.successor_trajectory_digest
                and successor.facts.trajectory_binding is not None
                and successor.facts.trajectory_binding.trajectory_digest
                == link.successor_trajectory_digest
                and successor.facts.trajectory_binding.markdown_digest
                == link.successor_markdown_digest
                and successor.facts.trajectory_binding.confirmation_digest
                == link.successor_confirmation_digest
                and successor.facts.derived_spine is not None
                and successor.facts.derived_spine.digest
                == link.successor_spine_digest
                and not successor.facts.derived_spine.nodes
                and not successor.facts.derived_spine.results
                and reference.fact_id == link.successor_trajectory_digest
                and successor.facts
                == current.facts.model_copy(
                    update={
                        "trajectory_successors": current.facts.trajectory_successors + (link,),
                        "trajectory_binding": successor.facts.trajectory_binding,
                        "derived_spine": successor.facts.derived_spine,
                    }
                )
                and successor.pending_decision == current.pending_decision
                and successor.limits == current.limits
            )
            if not valid:
                raise StoreError("trajectory successor must preserve predecessor authority")
            return
        if kind == "derived_spine_sealed":
            prior = current.facts.derived_spine
            sealed = successor.facts.derived_spine
            node = sealed.nodes[-1] if sealed is not None and sealed.nodes else None
            current_head = current.facts.run_head
            context_valid = False
            if sealed is not None and node is not None and current_head is not None:
                base_spine = prior
                if (
                    base_spine is not None
                    and base_spine.frontier.target_landmark_id is None
                    and TransactionalRunStore._replay_repair_ready(current, base_spine)
                ):
                    try:
                        base_spine = base_spine.for_repair_extension()
                    except ValueError:
                        base_spine = None
                if base_spine is None:
                    try:
                        base_spine = DerivedSpine(
                            schema_version=sealed.schema_version,
                            run_id=sealed.run_id,
                            trajectory_digest=sealed.trajectory_digest,
                            landmark_order=sealed.landmark_order,
                            frontier=SpineFrontier(
                                last_reached_landmark_id=(
                                    sealed.frontier.last_reached_landmark_id
                                ),
                                target_landmark_id=sealed.frontier.target_landmark_id,
                            ),
                        )
                    except ValueError:
                        base_spine = None
                if base_spine is not None:
                    try:
                        validate_sealed_node_context(
                            trajectory=current.trajectory,
                            spine=base_spine,
                            node=node,
                            current_run_head=current_head,
                            accepted_observations=current.facts.observations,
                        )
                    except ValueError:
                        pass
                    else:
                        context_valid = True
            valid = (
                sealed is not None
                and sealed.run_id == current.run_id
                and sealed.trajectory_digest == current.trajectory_digest
                and sealed.nodes
                and node is not None
                and current.mode in {"running", "final_replay"}
                and current_head is not None
                and node.run_id == current.run_id
                and node.trajectory_digest == current.trajectory_digest
                and node.run_head_digest == current_head.digest
                and node.execution_envelope_digest
                == current.trajectory.execution_envelope.digest
                and context_valid
                and reference.fact_id == sealed.nodes[-1].node_id
                and reference.fact_digest == sealed.digest
                and successor
                == current.model_copy(
                    update={
                        "facts": current.facts.model_copy(
                            update={"derived_spine": sealed}
                        )
                    }
                )
                and (
                    (
                        prior is None
                        and len(sealed.nodes) == 1
                        and not sealed.results
                    )
                    or (
                        prior is not None
                        and prior.frontier.unexecuted_node_id is None
                        and sealed.schema_version == prior.schema_version
                        and sealed.run_id == prior.run_id
                        and sealed.trajectory_digest == prior.trajectory_digest
                        and sealed.landmark_order == prior.landmark_order
                        and sealed.nodes[: len(prior.nodes)] == prior.nodes
                        and sealed.results == prior.results
                        and len(sealed.nodes) == len(prior.nodes) + 1
                        and (
                            prior.frontier.target_landmark_id is not None
                            or (
                                TransactionalRunStore._replay_repair_ready(current, prior)
                                and sealed.nodes[-1].target_landmark_id
                                == prior.landmark_order[-1]
                            )
                        )
                    )
                )
                and current.mode == successor.mode
                and successor.pending_decision == current.pending_decision
                and successor.limits == current.limits
            )
            if not valid:
                raise StoreError("derived_spine_sealed event must append exactly one sealed frontier node")
            return
        if kind == "derived_spine_result_recorded":
            prior = current.facts.derived_spine
            completed = successor.facts.derived_spine
            result = (
                completed.results[-1]
                if completed is not None and completed.results
                else None
            )
            current_head = current.facts.run_head
            accepted_result = False
            if (
                prior is not None
                and prior.nodes
                and result is not None
                and current_head is not None
            ):
                try:
                    validate_accepted_result_context(
                        trajectory=current.trajectory,
                        node=prior.nodes[-1],
                        result=result,
                        current_run_head=current_head,
                        accepted_observations=current.facts.observations,
                    )
                except ValueError:
                    pass
                else:
                    accepted_result = True
            valid = (
                prior is not None
                and completed is not None
                and result is not None
                and prior.frontier.unexecuted_node_id is not None
                and current.mode in {"running", "final_replay"}
                and current_head is not None
                and result.run_head_digest == current_head.digest
                and accepted_result
                and completed.nodes == prior.nodes
                and completed.results[: len(prior.results)] == prior.results
                and len(completed.results) == len(prior.results) + 1
                and reference.fact_id == result.node_id
                and reference.fact_digest == completed.digest
                and successor
                == current.model_copy(
                    update={
                        "facts": current.facts.model_copy(
                            update={"derived_spine": completed}
                        )
                    }
                )
                and current.mode == successor.mode
                and successor.pending_decision == current.pending_decision
                and successor.limits == current.limits
            )
            if not valid:
                raise StoreError(
                    "derived_spine_result_recorded requires accepted current-head result"
                )
            return
        if kind == "derived_spine_frozen":
            frozen = successor.facts.frozen_derived_spines[-1] if successor.facts.frozen_derived_spines else None
            prior_frozen = current.facts.frozen_derived_spines
            spine = current.facts.derived_spine
            valid = (
                current.mode == successor.mode == "running"
                and not TransactionalRunStore._open_replay_reopens(current.facts)
                and spine is not None
                and isinstance(frozen, FrozenDerivedSpine)
                and frozen.run_id == spine.run_id
                and frozen.trajectory_digest == current.trajectory_digest
                and frozen.derived_spine_digest == spine.digest
                and frozen.landmark_mapping_digest == spine.landmark_mapping_digest
                and frozen.landmark_order == spine.landmark_order
                and frozen.frontier == spine.frontier
                and frozen.nodes == spine.nodes
                and frozen.results == spine.results
                and frozen.run_head == current.facts.run_head
                and frozen.environment == current.facts.environment
                and frozen.fixture_digest == current.fixture_intent_digest
                and successor.facts.frozen_derived_spines == prior_frozen + (frozen,)
                and reference.fact_id == frozen.digest
                and reference.fact_digest == frozen.digest
                and successor
                == current.model_copy(
                    update={
                        "facts": current.facts.model_copy(
                            update={
                                "frozen_derived_spines": prior_frozen + (frozen,)
                            }
                        )
                    }
                )
            )
            if not valid:
                raise StoreError("frozen Derived Spine event must append immutable complete snapshot")
            return
        if current.facts.derived_spine != successor.facts.derived_spine:
            raise StoreError(
                "only Derived Spine seal/result event may change persisted Derived Spine"
            )
        task9_kinds = {
            "run_head_advanced",
            "final_replay_started",
            "final_replay_succeeded",
            "final_replay_reopened",
            "review_infrastructure_paused",
        }
        if kind in task9_kinds:
            current_head = current.facts.run_head
            if current_head is None:
                raise StoreError(f"{kind} requires canonical current Run Head")
            if kind == "run_head_advanced":
                new_head = successor.facts.run_head
                valid = (
                    current.mode == "running"
                    and successor.mode == "running"
                    and new_head is not None
                    and new_head != current_head
                    and new_head.environment_digest == current_head.environment_digest
                    and new_head.fixture_digest == current_head.fixture_digest
                    and reference.fact_id == new_head.digest
                    and successor.pending_decision == current.pending_decision
                    and successor.limits == current.limits
                )
            elif kind == "final_replay_started":
                valid = (
                    current.mode == "running"
                    and successor.mode == "final_replay"
                    and successor.facts == current.facts
                    and successor.limits == current.limits
                    and successor.pending_decision is None
                    and reference.fact_id == current_head.digest
                )
            elif kind == "final_replay_succeeded":
                fact = successor.facts.iteration_facts[-1] if successor.facts.iteration_facts else None
                frozen = (
                    current.facts.frozen_derived_spines[-1]
                    if current.facts.frozen_derived_spines
                    else None
                )
                new_specs = successor.facts.proof_specs[
                    len(current.facts.proof_specs) :
                ]
                new_results = successor.facts.proof_results[
                    len(current.facts.proof_results) :
                ]
                new_manifests = successor.facts.role_manifests[
                    len(current.facts.role_manifests) :
                ]
                expected_node_ids = (
                    tuple(node.node_id for node in frozen.nodes)
                    if frozen is not None
                    else ()
                )
                environment = current.facts.environment
                semantic_manifest = new_manifests[0] if len(new_manifests) == 1 else None
                closed_replays = {
                    closure.replay_id for closure in successor.facts.replay_cone_closures
                }
                valid = (
                    current.mode == "final_replay"
                    and successor.mode == "succeeded"
                    and successor.facts.run_head == current_head
                    and isinstance(fact, IterationFact)
                    and fact.fact_class == "terminal"
                    and fact.run_head_digest == current_head.digest
                    and len(successor.facts.iteration_facts) == len(current.facts.iteration_facts) + 1
                    and reference.fact_id == fact.fact_id
                    and frozen is not None
                    and tuple(spec.node_id for spec in new_specs) == expected_node_ids
                    and len(new_results) == len(new_specs)
                    and all(
                        result.proof_spec_id == spec.proof_spec_id
                        and result.proof_spec_digest == spec.digest
                        and result.node_id == spec.node_id
                        and result.proof_class == "deterministic_execution_proof"
                        and result.result == "green"
                        and result.run_head_digest == current_head.digest
                        for spec, result in zip(new_specs, new_results, strict=True)
                    )
                    and semantic_manifest is not None
                    and environment is not None
                    and semantic_manifest.role == "semantic_reviewer"
                    and semantic_manifest.goal_digest == current.trajectory_digest
                    and semantic_manifest.trajectory_digest == current.trajectory_digest
                    and semantic_manifest.derived_spine_digest == frozen.derived_spine_digest
                    and semantic_manifest.landmark_mapping_digest
                    == frozen.landmark_mapping_digest
                    and semantic_manifest.cone_digest == fact.cone_digest
                    and semantic_manifest.base_revision == current_head.revision
                    and semantic_manifest.run_head_digest == current_head.digest
                    and semantic_manifest.environment_digest == environment.digest
                    and semantic_manifest.fixture_digest == current.fixture_intent_digest
                    and semantic_manifest.proof_spec_digest == new_specs[-1].digest
                    and semantic_manifest.permitted_output_schema
                    == "final-replay-semantic-output-v1"
                    and all(
                        reopen.replay_id in closed_replays
                        for reopen in successor.facts.replay_reopens
                    )
                    and successor.pending_decision is None
                    and successor.limits == current.limits
                )
            elif kind == "final_replay_reopened":
                fact = successor.facts.iteration_facts[-1] if successor.facts.iteration_facts else None
                reopen = successor.facts.replay_reopens[-1] if successor.facts.replay_reopens else None
                stale_ids = set(reopen.stale_verified_fact_ids) if reopen is not None else set()
                valid = (
                    current.mode == "final_replay"
                    and successor.mode == "running"
                    and successor.facts.run_head == current_head
                    and isinstance(fact, IterationFact)
                    and fact.fact_class == "new_hop"
                    and fact.run_head_digest == current_head.digest
                    and isinstance(reopen, ReplayReopen)
                    and reopen.node_id == fact.node_id
                    and reopen.cone_id == fact.cone_id
                    and reopen.run_head_digest == current_head.digest
                    and len(successor.facts.replay_reopens) == len(current.facts.replay_reopens) + 1
                    and len(successor.facts.iteration_facts)
                    == len(current.facts.iteration_facts) + 1
                    and all(
                        any(
                            item.fact_id == stale_id
                            and item.fact_class == "verified_node"
                            and item.node_id == reopen.node_id
                            for item in current.facts.iteration_facts
                        )
                        for stale_id in stale_ids
                    )
                    and reference.fact_id == fact.fact_id
                    and successor.pending_decision is None
                    and successor.limits == current.limits
                )
            else:
                fact = successor.facts.iteration_facts[-1] if successor.facts.iteration_facts else None
                report = successor.facts.pause_report
                valid = (
                    current.mode in {"running", "final_replay"}
                    and successor.mode == "paused"
                    and successor.facts.run_head == current_head
                    and isinstance(report, PauseReport)
                    and report.reason == "review_infrastructure"
                    and isinstance(fact, IterationFact)
                    and fact.fact_class == "pause"
                    and fact.run_head_digest == current_head.digest
                    and len(successor.facts.pause_reports) == len(current.facts.pause_reports) + 1
                    and len(successor.facts.pending_decision_history) == len(current.facts.pending_decision_history) + 1
                    and successor.pending_decision == successor.facts.pending_decision_history[-1]
                    and reference.fact_id == report.node_id
                    and successor.limits == current.limits
                )
            if not valid:
                raise StoreError(f"{kind} event transition does not match canonical state delta")
            return
        task8_kinds = {
            "runtime_iteration_recorded",
            "product_work_accounted",
            "diagnostic_stall_paused",
            "user_decision_applied",
            "escalation_requested",
        }
        if kind in task8_kinds:
            protected = ("bootstrap_intent", "git_transaction", "environment", "run_head")
            if any(
                getattr(current.facts, field_name)
                != getattr(successor.facts, field_name)
                for field_name in protected
            ):
                raise StoreError(f"{kind} may not change protected start state")
            if kind == "runtime_iteration_recorded":
                fact = successor.facts.iteration_facts[-1] if successor.facts.iteration_facts else None
                valid = (
                    current.mode in {"running", "final_replay"}
                    and successor.mode == current.mode
                    and isinstance(fact, IterationFact)
                    and len(successor.facts.iteration_facts)
                    == len(current.facts.iteration_facts) + 1
                    and reference.fact_id == fact.fact_id
                    and fact.run_head_digest
                    == (current.facts.run_head.digest if current.facts.run_head else "")
                    and successor.pending_decision == current.pending_decision
                    and successor.limits == current.limits
                )
            elif kind == "product_work_accounted":
                receipt = successor.facts.product_work[-1] if successor.facts.product_work else None
                expected_duration_count = len(current.facts.duration_deltas) + int(
                    bool(receipt and receipt.completed_duration_ms)
                )
                valid = (
                    current.mode in {"running", "final_replay"}
                    and successor.mode == current.mode
                    and isinstance(receipt, ProductWorkReceipt)
                    and len(successor.facts.product_work)
                    == len(current.facts.product_work) + 1
                    and len(successor.facts.work_authorizations)
                    == len(current.facts.work_authorizations) + 1
                    and len(successor.facts.duration_deltas) == expected_duration_count
                    and reference.fact_id == receipt.work_id
                    and successor.pending_decision == current.pending_decision
                    and successor.limits == current.limits
                )
            elif kind == "diagnostic_stall_paused":
                fact = successor.facts.iteration_facts[-1] if successor.facts.iteration_facts else None
                report = successor.facts.pause_report
                valid = (
                    current.mode in {"running", "final_replay"}
                    and successor.mode == "paused"
                    and isinstance(report, PauseReport)
                    and report.reason == "diagnostic_stall"
                    and len(successor.facts.pause_reports)
                    == len(current.facts.pause_reports) + 1
                    and successor.facts.pause_reports[-1] == report
                    and successor.pending_decision is not None
                    and len(successor.facts.pending_decision_history)
                    == len(current.facts.pending_decision_history) + 1
                    and successor.facts.pending_decision_history[-1]
                    == successor.pending_decision
                    and isinstance(fact, IterationFact)
                    and fact.fact_class == "pause"
                    and fact.node_id == report.node_id
                    and len(successor.facts.iteration_facts)
                    == len(current.facts.iteration_facts) + 1
                    and reference.fact_id == report.node_id
                    and successor.limits == current.limits
                )
            elif kind == "user_decision_applied":
                decision = successor.facts.user_decisions[-1] if successor.facts.user_decisions else None
                limits_valid = False
                if isinstance(decision, UserDecision):
                    if decision.kind != "limit_amendment":
                        limits_valid = successor.limits == current.limits
                    else:
                        amendment = (
                            successor.limits.amendments[-1]
                            if successor.limits.amendments
                            else None
                        )
                        limits_valid = (
                            len(successor.limits.versions)
                            == len(current.limits.versions) + 1
                            and successor.limits.versions[: len(current.limits.versions)]
                            == current.limits.versions
                            and len(successor.limits.amendments)
                            == len(current.limits.amendments) + 1
                            and amendment is not None
                            and amendment.name == decision.limit_name
                            and amendment.new_value.amount == decision.limit_amount
                            and amendment.approver == decision.actor
                            and amendment.reason == decision.reason
                        )
                if not limits_valid:
                    if isinstance(decision, UserDecision) and decision.kind == "limit_amendment":
                        raise StoreError("limit user decision must append a Run Limits version")
                    raise StoreError("non-limit user decision may not widen Run Limits")
                expected_mode = (
                    "inconclusive"
                    if isinstance(decision, UserDecision)
                    and decision.kind == "terminalization"
                    else "cancelled"
                    if isinstance(decision, UserDecision)
                    and decision.kind == "cancellation"
                    else "running"
                )
                valid = (
                    current.mode == "paused"
                    and current.pending_decision is not None
                    and successor.pending_decision is None
                    and isinstance(decision, UserDecision)
                    and decision.pending_decision_digest == current.pending_decision.digest
                    and decision.kind
                    in (current.pending_decision.kind, *current.pending_decision.allowed_kinds)
                    and len(successor.facts.user_decisions)
                    == len(current.facts.user_decisions) + 1
                    and reference.fact_id == decision.decision_id
                    and successor.mode == expected_mode
                )
            else:
                pending = successor.pending_decision
                fact = successor.facts.iteration_facts[-1] if successor.facts.iteration_facts else None
                valid = (
                    current.mode in {"running", "final_replay"}
                    and successor.mode == "paused"
                    and isinstance(pending, PendingDecision)
                    and isinstance(fact, IterationFact)
                    and fact.fact_class == "escalation"
                    and len(successor.facts.iteration_facts)
                    == len(current.facts.iteration_facts) + 1
                    and len(successor.facts.pending_decision_history)
                    == len(current.facts.pending_decision_history) + 1
                    and successor.facts.pending_decision_history[-1] == pending
                    and reference.fact_id == pending.decision_id
                    and successor.limits == current.limits
                )
            if not valid:
                raise StoreError(f"{kind} event transition does not match canonical state delta")
            return
        task4_kinds = {
            "trajectory_confirmed",
            "bootstrap_intended",
            "host_preflighted",
            "git_transaction_recorded",
            "environment_sealed",
            "initial_run_head_recorded",
            "run_started",
        }
        if kind not in task4_kinds:
            protected = (
                "trajectory_binding",
                "bootstrap_intent",
                "git_transaction",
                "environment",
                "run_head",
            )
            if current.mode != successor.mode or any(
                getattr(current.facts, field_name)
                != getattr(successor.facts, field_name)
                for field_name in protected
            ):
                raise StoreError(
                    f"{kind} may not change protected start state without bound transition"
                )
            return

        def only_fact(field_name: str) -> bool:
            expected_facts = current.facts.model_copy(
                update={field_name: getattr(successor.facts, field_name)}
            )
            return successor == current.model_copy(update={"facts": expected_facts})

        valid = False
        if kind == "trajectory_confirmed":
            value = successor.facts.trajectory_binding
            valid = (
                current.facts.trajectory_binding is None
                and value is not None
                and reference.fact_id == value.run_id
                and only_fact("trajectory_binding")
            )
        elif kind == "bootstrap_intended":
            value = successor.facts.bootstrap_intent
            valid = (
                current.facts.bootstrap_intent is None
                and value is not None
                and reference.fact_id == value.transaction_id
                and only_fact("bootstrap_intent")
            )
        elif kind == "host_preflighted":
            intent = current.facts.bootstrap_intent
            valid = (
                intent is not None
                and reference.fact_id == intent.transaction_id
                and successor == current
            )
        elif kind == "git_transaction_recorded":
            value = successor.facts.git_transaction
            valid = (
                value is not None
                and reference.fact_id == value.transaction_id
                and only_fact("git_transaction")
            )
        elif kind == "environment_sealed":
            value = successor.facts.environment
            transaction = successor.facts.git_transaction
            valid = (
                current.facts.environment is None
                and value is not None
                and transaction is not None
                and transaction.status == "reconciled"
                and reference.fact_id == value.digest
                and only_fact("environment")
            )
        elif kind == "initial_run_head_recorded":
            value = successor.facts.run_head
            valid = (
                current.facts.run_head is None
                and value is not None
                and reference.fact_id == value.digest
                and only_fact("run_head")
            )
        elif kind == "run_started":
            run_head = current.facts.run_head
            valid = (
                current.mode == "boot"
                and successor.mode == "running"
                and successor.facts == current.facts
                and successor.limits == current.limits
                and current.limits.active_version == 1
                and len(current.limits.versions) == 1
                and not current.limits.amendments
                and run_head is not None
                and reference.fact_id == run_head.digest
            )
        if not valid:
            raise StoreError(f"{kind} event transition does not match canonical state delta")

    @staticmethod
    def _validate_successor(current: RunState, successor: RunState) -> None:
        successor_link = (
            successor.facts.trajectory_successors[-1]
            if len(successor.facts.trajectory_successors)
            == len(current.facts.trajectory_successors) + 1
            and successor.facts.trajectory_successors[:
                len(current.facts.trajectory_successors)
            ]
            == current.facts.trajectory_successors
            else None
        )
        trajectory_successor_transition = (
            successor_link is not None
            and successor_link.predecessor_trajectory_digest
            == current.trajectory_digest
            and successor_link.successor_trajectory_digest
            == successor.trajectory_digest
            and successor.facts.trajectory_binding is not None
            and successor.facts.trajectory_binding.trajectory_digest
            == successor.trajectory_digest
            and successor.facts.derived_spine is not None
            and successor.facts.derived_spine.digest
            == successor_link.successor_spine_digest
        )
        if successor.trajectory != current.trajectory and not trajectory_successor_transition:
            raise StoreError(
                "successor replaces immutable Trajectory Brief"
            )
        if (
            successor.facts.trajectory_binding != current.facts.trajectory_binding
            and not trajectory_successor_transition
        ):
            raise StoreError("successor replaces confirmed trajectory binding")
        prior_spine = current.facts.derived_spine
        next_spine = successor.facts.derived_spine
        if prior_spine is not None and not trajectory_successor_transition:
            if next_spine is None:
                raise StoreError("successor removes persisted Derived Spine")
            if (
                next_spine.schema_version != prior_spine.schema_version
                or next_spine.run_id != prior_spine.run_id
                or next_spine.trajectory_digest != prior_spine.trajectory_digest
                or next_spine.landmark_order != prior_spine.landmark_order
                or next_spine.nodes[: len(prior_spine.nodes)] != prior_spine.nodes
                or next_spine.results[: len(prior_spine.results)]
                != prior_spine.results
            ):
                raise StoreError("successor rewrites append-only Derived Spine")
        for field_name in _APPEND_ONLY_FACT_FIELDS:
            old_values = getattr(current.facts, field_name)
            new_values = getattr(successor.facts, field_name)
            if new_values[: len(old_values)] != old_values:
                raise StoreError(
                    f"successor rewrites append-only fact history: {field_name}"
                )
        if len(successor.facts.observations) > len(current.facts.observations):
            transaction = successor.facts.git_transaction
            if current.mode not in {"running", "final_replay"}:
                raise StoreError(
                    "product Observation requires durable run_started boundary"
                )
            if successor.facts.environment is None:
                raise StoreError(
                    "product Observation requires sealed EnvironmentIdentity"
                )
            if transaction is None or transaction.status != "reconciled":
                raise StoreError(
                    "product Observation requires reconciled Git transaction"
                )
            run_head = current.facts.run_head
            if run_head is None:
                raise StoreError("product Observation requires canonical Run Head")
            for observation in successor.facts.observations[
                len(current.facts.observations):
            ]:
                if observation.run_head_digest != run_head.digest:
                    raise StoreError(
                        "product Observation does not match current Run Head"
                    )
                if TransactionalRunStore._observation_uses_author_signal(
                    current, observation
                ):
                    raise StoreError(
                        "Author Signals cannot become runtime Observation authority"
                    )
        if (
            current.facts.observations
            and successor.facts.environment != current.facts.environment
        ):
            raise StoreError(
                "successor replaces sealed environment after first Observation"
            )
        old_versions = current.limits.versions
        old_amendments = current.limits.amendments
        if (
            successor.limits.versions[: len(old_versions)] != old_versions
            or successor.limits.amendments[: len(old_amendments)] != old_amendments
        ):
            raise StoreError("successor rewrites append-only Run Limits history")
        authority_fields = (
            "proof_specs",
            "role_manifests",
            "work_authorizations",
            "change_classification_artifacts",
        )
        if any(
            len(getattr(successor.facts, field_name))
            > len(getattr(current.facts, field_name))
            for field_name in authority_fields
        ):
            authority_spine = current.facts.derived_spine
            if authority_spine is None:
                raise StoreError("runtime authority facts require persisted Derived Spine")
            expected_authority = (
                current.trajectory_digest,
                authority_spine.digest,
                authority_spine.landmark_mapping_digest,
            )
            for field_name in authority_fields:
                old_values = getattr(current.facts, field_name)
                for value in getattr(successor.facts, field_name)[len(old_values):]:
                    if (
                        value.trajectory_digest,
                        value.derived_spine_digest,
                        value.landmark_mapping_digest,
                    ) != expected_authority:
                        raise StoreError(
                            f"{field_name} does not bind event-time trajectory authority"
                        )
        TransactionalRunStore._validate_runtime_authority_facts(successor)

    @staticmethod
    def _observation_uses_author_signal(
        state: RunState, observation: Observation
    ) -> bool:
        signal_tokens: set[str] = set()
        for signal in state.trajectory.author_signals:
            signal_id = signal.signal_id.casefold()
            signal_tokens.update(
                {signal_id, f"author-signal:{signal_id}", f"author_signal:{signal_id}"}
            )
            signal_tokens.update(reference.casefold() for reference in signal.evidence_refs)
        values = (
            observation.observation_id.casefold(),
            *(reference.casefold() for reference in observation.evidence_refs),
        )
        return any(
            value in signal_tokens
            or value.startswith("author-signal:")
            or value.startswith("author_signal:")
            for value in values
        )

    @staticmethod
    def _validate_runtime_authority_facts(state: RunState) -> None:
        bindings: dict[tuple[str, str], str] = {}
        for binding in state.facts.cone_identity_bindings:
            if binding.run_id != state.run_id:
                raise StoreError("canonical cone identity belongs to another run")
            key = (binding.run_id, binding.node_id)
            if key in bindings:
                raise StoreError("canonical cone identity binding must be unique")
            bindings[key] = binding.cone_id
        for fact in state.facts.iteration_facts:
            if bindings.get((state.run_id, fact.node_id)) != fact.cone_id:
                raise StoreError("runtime fact is not bound to canonical cone identity")
        for receipt in state.facts.product_work:
            if bindings.get((state.run_id, receipt.node_id)) != receipt.cone_id:
                raise StoreError("product work is not bound to canonical cone identity")

        authorizations = state.facts.work_authorizations
        authorization_by_id = {
            authorization.authorization_id: authorization
            for authorization in authorizations
        }
        if len(authorization_by_id) != len(authorizations):
            raise StoreError("work authorization id must be append-only and unique")
        for receipt in state.facts.product_work:
            authorization = authorization_by_id.get(receipt.authorization_id or "")
            if (
                authorization is None
                or receipt.authorization_digest != authorization.digest
                or receipt.operation_id != authorization.operation_id
                or receipt.kind != authorization.kind
                or receipt.node_id != authorization.node_id
                or receipt.cone_id != authorization.cone_id
                or receipt.cone_digest != authorization.cone_digest
                or receipt.counters != authorization.expected_counters
            ):
                raise StoreError("product work receipt does not bind issued authorization")
            if authorization.run_id != state.run_id:
                raise StoreError("product work authorization belongs to another run")

        expected_goal_digest = state.trajectory_digest
        expected_envelope_digest = digest_for(
            "execution-envelope", state.trajectory.execution_envelope
        )
        artifacts = state.facts.change_classification_artifacts
        artifact_ids = [artifact.artifact_id for artifact in artifacts]
        if len(artifact_ids) != len(set(artifact_ids)):
            raise StoreError("classification artifact id must be append-only and unique")
        decision_by_digest = {
            decision.digest: decision for decision in state.facts.user_decisions
        }
        pending_by_digest = {
            pending.digest: pending for pending in state.facts.pending_decision_history
        }
        for repair in state.facts.repairs:
            candidates = tuple(
                artifact
                for artifact in artifacts
                if artifact.change_kind == repair.change_kind
                and artifact.cone_id == repair.cone_id
                and artifact.cone_digest == repair.cone_digest
                and artifact.repair_hypothesis == repair.hypothesis
                and artifact.changed_dependencies == repair.changed_dependencies
                and artifact.changed_files == repair.changed_files
            )
            if len(candidates) != 1:
                raise StoreError("repair requires one exact independent classification artifact")
        for artifact in artifacts:
            if (
                artifact.run_id != state.run_id
                or artifact.goal_digest != expected_goal_digest
                or artifact.envelope_digest != expected_envelope_digest
                or bindings.get((state.run_id, artifact.node_id)) != artifact.cone_id
                or not any(
                    proof_spec.node_id == artifact.node_id
                    for proof_spec in state.facts.proof_specs
                )
            ):
                raise StoreError("classification artifact does not bind current run context")
            if artifact.change_kind == "conformance":
                continue
            required_kind = {
                "behavior": "behavior_authorization",
                "architecture": "architecture_authorization",
                "external_contract": "external_contract_authorization",
            }[artifact.change_kind]
            decisions = tuple(
                decision
                for decision in state.facts.user_decisions
                if decision.classification_digest == artifact.digest
                and decision.change_digest == artifact.change_digest
            )
            decision = decisions[0] if len(decisions) == 1 else None
            pending = (
                pending_by_digest.get(decision.pending_decision_digest)
                if decision is not None
                else None
            )
            if (
                decision is None
                or pending is None
                or decision.kind != required_kind
                or pending.cone_id != artifact.cone_id
                or pending.cone_digest != artifact.cone_digest
                or decision.classification_digest != artifact.digest
                or decision.change_digest != artifact.change_digest
            ):
                raise StoreError("classification artifact lacks matching user authorization")

        manifests = {manifest.digest: manifest for manifest in state.facts.role_manifests}
        if len(manifests) != len(state.facts.role_manifests):
            raise StoreError("reviewer manifest must be append-only and unique")
        artifact_by_digest = {artifact.digest: artifact for artifact in artifacts}
        for artifact in artifacts:
            manifest = manifests.get(artifact.reviewer_manifest_digest or "")
            if (
                manifest is None
                or manifest.manifest_id != artifact.reviewer_manifest_id
                or manifest.identity != artifact.reviewer_id
                or manifest.role != "independent_change_reviewer"
            ):
                raise StoreError("classification artifact lacks fresh independent reviewer manifest")
        consumptions = state.facts.user_authorization_consumptions
        consumed_decisions = [item.decision_digest for item in consumptions]
        if len(consumed_decisions) != len(set(consumed_decisions)):
            raise StoreError("user authorization may be consumed once")
        for consumption in consumptions:
            decision = decision_by_digest.get(consumption.decision_digest)
            artifact = artifact_by_digest.get(consumption.classification_digest)
            if (
                decision is None
                or artifact is None
                or decision.classification_digest != consumption.classification_digest
                or decision.change_digest != consumption.change_digest
                or artifact.change_digest != consumption.change_digest
            ):
                raise StoreError("user authorization consumption does not bind exact change")
        for artifact in artifacts:
            if artifact.change_kind != "conformance" and not any(
                item.classification_digest == artifact.digest
                and item.change_digest == artifact.change_digest
                and any(
                    decision.digest == item.decision_digest
                    and decision.classification_digest == artifact.digest
                    and decision.change_digest == artifact.change_digest
                    for decision in state.facts.user_decisions
                )
                for item in consumptions
            ):
                raise StoreError("classification artifact user authorization was not consumed")

    @contextmanager
    def _lock(self) -> Iterator[None]:
        self._root.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + 5.0
        handle = self._lock_path.open("a+b")
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        acquired = False
        while not acquired:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError:
                if time.monotonic() >= deadline:
                    handle.close()
                    raise StoreError("timed out waiting for V5 store lock")
                time.sleep(0.02)
        try:
            yield
        finally:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()

    @staticmethod
    def _atomic_write(path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with temporary.open("xb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()

    @staticmethod
    def _append_bytes(path: Path, payload: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("ab") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _remove_exact_file(path: Path) -> None:
        try:
            path.unlink()
        except FileNotFoundError:
            return


RealSystemEventKind = Literal[
    "real_system_admitted",
    "exploration_delta_recorded",
    "resource_lease_recorded",
    "external_operation_intended",
    "manifest_budget_exhausted_blocked",
    "external_operation_receipted",
    "real_node_completed",
    "real_system_decision_pending",
    "real_system_decision_consumed",
    "runtime_note_recorded",
    "unsettled_operation_paused",
    "environment_snapshot_drift_paused",
    "cleanup_authorized",
]
_REAL_SYSTEM_EVENT_KINDS = frozenset(RealSystemEventKind.__args__)


class RealSystemLedgerEvent(StrictModel):
    """Separate V5.2 hash-chain event. Never parse it as a V5.1 ledger."""

    sequence: int = Field(ge=1)
    kind: RealSystemEventKind
    fact_id: str
    fact_digest: str
    previous_digest: str
    state_digest: str
    event_digest: str

    @field_validator("fact_id")
    @classmethod
    def _fact_id_is_nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("real-system ledger fact_id must be non-empty")
        return value

    @field_validator("fact_digest", "previous_digest", "state_digest", "event_digest")
    @classmethod
    def _event_digests_are_exact(cls, value: str) -> str:
        if _SHA256_HEX.fullmatch(value) is None:
            raise ValueError("real-system ledger digests must be lowercase SHA-256 hexadecimal")
        return value

    @model_validator(mode="after")
    def _digest_matches_canonical_event(self) -> "RealSystemLedgerEvent":
        material = {
            "sequence": self.sequence,
            "kind": self.kind,
            "fact_id": self.fact_id,
            "fact_digest": self.fact_digest,
            "previous_digest": self.previous_digest,
            "state_digest": self.state_digest,
        }
        if self.event_digest != digest_for("graph-v5.2-ledger-event", material):
            raise ValueError("real-system ledger event digest mismatch")
        return self

    @classmethod
    def create(
        cls,
        *,
        sequence: int,
        kind: RealSystemEventKind,
        fact_id: str,
        fact_digest: str,
        previous_digest: str,
        state_digest: str,
    ) -> "RealSystemLedgerEvent":
        material = {
            "sequence": sequence,
            "kind": kind,
            "fact_id": fact_id,
            "fact_digest": fact_digest,
            "previous_digest": previous_digest,
            "state_digest": state_digest,
        }
        return cls(**material, event_digest=digest_for("graph-v5.2-ledger-event", material))


class RealSystemRunStore:
    """V5.2 real-system facts with an independent, recoverable store schema.

    ``TransactionalRunStore`` deliberately remains a V5.1 fixture-store
    implementation. This store records only V5.2 admitted authority and will
    never translate a V5.1 ``RunState`` into a real-system run.
    """

    _JOURNAL_SCHEMA = "graph-v5.2.transaction-journal.v2"
    _ADMISSION_JOURNAL_SCHEMA = "graph-v5.2.admission-journal.v1"
    _STATE_FILE = "state.json"
    _LEDGER_FILE = "ledger.jsonl"
    _MANIFEST_FILE = "adapter-manifest.json"
    _SNAPSHOT_FILE = "environment-snapshot.json"
    _NOTES_FILE = "runtime_notes.md"
    _JOURNAL_FILE = "journal.json"
    _LOCK_FILE = ".graph-v5.2.lock"

    def __init__(self, root: str | Path, run_id: str) -> None:
        self._root = Path(root).resolve(strict=False)
        self._read_only = False
        if not isinstance(run_id, str) or not run_id.strip():
            raise StoreError("real-system run_id must be non-empty")
        self._run_id = run_id

    @classmethod
    def open(cls, root: str | Path, run_id: str) -> "RealSystemRunStore":
        store = cls(root, run_id)
        store.recover()
        if store._state_path.exists():
            state = store.read_state()
            if state.mode == "running":
                store.reconcile_unsettled_intents()
        return store

    @classmethod
    def open_readonly(cls, root: str | Path, run_id: str) -> "RealSystemRunStore":
        """Open canonical V5.2 bytes without recovery, locks, or mutation."""

        store = cls(root, run_id)
        store._read_only = True
        if store._journal_path.exists():
            raise RecoveryError("real-system recovery is pending; run a mutating resume")
        store.read_state()
        return store

    @property
    def root(self) -> Path:
        return self._root

    def _require_mutable(self) -> None:
        if self._read_only:
            raise StoreError("read-only real-system store cannot mutate persisted authority")

    def _path(self, name: str) -> Path:
        return self._root / name

    @property
    def _state_path(self) -> Path:
        return self._path(self._STATE_FILE)

    @property
    def _ledger_path(self) -> Path:
        return self._path(self._LEDGER_FILE)

    @property
    def _manifest_path(self) -> Path:
        return self._path(self._MANIFEST_FILE)

    @property
    def _snapshot_path(self) -> Path:
        return self._path(self._SNAPSHOT_FILE)

    @property
    def _notes_path(self) -> Path:
        return self._path(self._NOTES_FILE)

    @property
    def _journal_path(self) -> Path:
        return self._path(self._JOURNAL_FILE)

    @property
    def _lock_path(self) -> Path:
        return self._path(self._LOCK_FILE)

    def initialize(
        self,
        state: V52RunState,
        *,
        manifest: object,
        baseline_nodes: tuple[DerivedBehavioralNode, ...],
        baseline_proposals: tuple[BaselineNodeProposal, ...] = (),
        provider_authority: AdmittedProviderAuthority | None = None,
        supervisor_receipts: tuple[SupervisorAuthorityReceipt, ...] = (),
        egress_receipt: EgressGateReceipt | None = None,
    ) -> V52RunState:
        """Atomically persist all V5.2 admission authority before any execution."""

        self._require_mutable()
        if provider_authority is None:
            raise StoreError("real-system admission requires admitted provider authority")

        from .adapters.manifest import AdapterManifest
        from .adapters.host_registry import HostProviderError, resolve_host_provider
        from .environment import EnvironmentSnapshot
        from .adapters.registry import AdapterManifestError, resolve_descriptor

        try:
            validated_state = V52RunState.model_validate(
                state.model_dump(mode="python") if isinstance(state, V52RunState) else state
            )
            validated_manifest = AdapterManifest.model_validate(
                manifest.model_dump(mode="python") if isinstance(manifest, AdapterManifest) else manifest
            )
            typed_provider = AdmittedProviderAuthority.model_validate(
                provider_authority.model_dump(mode="python")
                if isinstance(provider_authority, AdmittedProviderAuthority)
                else provider_authority
            )
            typed_baseline_proposals = tuple(
                BaselineNodeProposal.model_validate(item.model_dump(mode="python"))
                if isinstance(item, BaselineNodeProposal)
                else item
                for item in baseline_proposals
            )
            if not all(
                isinstance(item, BaselineNodeProposal)
                for item in typed_baseline_proposals
            ):
                raise ValueError("baseline proposals must be strict")
            typed_supervisors = tuple(
                SupervisorAuthorityReceipt.model_validate(item.model_dump(mode="python"))
                if isinstance(item, SupervisorAuthorityReceipt)
                else item
                for item in supervisor_receipts
            )
            if not all(isinstance(item, SupervisorAuthorityReceipt) for item in typed_supervisors):
                raise ValueError("supervisor receipts must be strict")
            typed_egress = (
                None
                if egress_receipt is None
                else EgressGateReceipt.model_validate(egress_receipt.model_dump(mode="python"))
            )
            validated_snapshot = EnvironmentSnapshot.from_admitted_authority(
                manifest=validated_manifest,
                target_identity_digest=validated_state.trajectory.execution_envelope.target_identity_digest,
                supervisor_receipts=typed_supervisors,
                egress_receipt=typed_egress,
            )
            resolve_descriptor(validated_manifest)
            host_provider = resolve_host_provider(validated_manifest.adapter_id)
        except (AdapterManifestError, HostProviderError, AttributeError, TypeError, ValidationError, ValueError) as exc:
            raise StoreError("real-system admission requires strict state, manifest, baseline, and typed receipts") from exc
        self._require_run(validated_state.run_id)
        if validated_state.facts != RealSystemFactIndex():
            raise StoreError("real-system admission requires an empty V5.2 fact index")
        if validated_manifest.digest != validated_state.adapter_manifest_digest:
            raise StoreError("admitted manifest does not match confirmed V5.2 authority")
        if (
            typed_provider.adapter_id != validated_manifest.adapter_id
            or typed_provider.provider_id != host_provider.provider_id
            or typed_provider.source_identity_digest
            != validated_state.trajectory.execution_envelope.target_identity_digest
        ):
            raise StoreError("admitted provider authority does not bind manifest source")
        if validated_snapshot.adapter_manifest_digest != validated_manifest.digest:
            raise StoreError("environment snapshot does not bind admitted manifest")
        if (
            validated_snapshot.target_identity_digest
            != validated_state.trajectory.execution_envelope.target_identity_digest
        ):
            raise StoreError("environment snapshot does not bind confirmed exact target")
        if validated_snapshot.evidence_policy_digest != validated_manifest.evidence.redaction_policy_digest:
            raise StoreError("environment snapshot does not bind admitted evidence policy")
        run_head = RealSystemRunHead(
            run_id=validated_state.run_id,
            manifest_digest=validated_manifest.digest,
            environment_snapshot_digest=validated_snapshot.digest,
        )
        try:
            baseline = BaselineSpineAuthority.from_nodes(
                validated_state,
                run_head,
                validated_manifest,
                validated_snapshot,
                baseline_nodes,
                typed_baseline_proposals,
            )
        except (AttributeError, TypeError, ValidationError, ValueError) as exc:
            raise StoreError("real-system admission requires exact canonical baseline nodes") from exc
        admitted = validated_state.model_copy(
            update={
                "facts": RealSystemFactIndex(
                    environment_snapshot_digest=validated_snapshot.digest,
                    run_head=run_head,
                    provider_authority=typed_provider,
                    baseline_spine=baseline,
                    supervisor_receipts=typed_supervisors,
                    egress_receipt=typed_egress,
                )
            }
        )
        event = RealSystemLedgerEvent.create(
            sequence=1,
            kind="real_system_admitted",
            fact_id=baseline.digest,
            fact_digest=baseline.digest,
            previous_digest=_GENESIS_DIGEST,
            state_digest=admitted.digest,
        )
        manifest_bytes = canonical_json_bytes(validated_manifest)
        snapshot_bytes = canonical_json_bytes(validated_snapshot)
        notes_bytes = b""
        state_bytes = canonical_json_bytes(admitted)
        ledger_bytes = canonical_json_bytes(event) + b"\n"
        with self._lock():
            if any(
                path.exists()
                for path in (
                    self._state_path,
                    self._ledger_path,
                    self._manifest_path,
                    self._snapshot_path,
                    self._notes_path,
                    self._journal_path,
                )
            ):
                raise StoreError("real-system run store is already initialized")
            self._root.mkdir(parents=True, exist_ok=True)
            journal = {
                "schema_version": self._ADMISSION_JOURNAL_SCHEMA,
                "manifest_bytes_b64": base64.b64encode(manifest_bytes).decode("ascii"),
                "snapshot_bytes_b64": base64.b64encode(snapshot_bytes).decode("ascii"),
                "notes_bytes_b64": base64.b64encode(notes_bytes).decode("ascii"),
                "state_bytes_b64": base64.b64encode(state_bytes).decode("ascii"),
                "ledger_bytes_b64": base64.b64encode(ledger_bytes).decode("ascii"),
            }
            TransactionalRunStore._atomic_write(
                self._journal_path, canonical_json_bytes(journal)
            )
            try:
                TransactionalRunStore._atomic_write(self._manifest_path, manifest_bytes)
                TransactionalRunStore._atomic_write(self._snapshot_path, snapshot_bytes)
                TransactionalRunStore._atomic_write(self._notes_path, notes_bytes)
                TransactionalRunStore._atomic_write(self._state_path, state_bytes)
                TransactionalRunStore._atomic_write(self._ledger_path, ledger_bytes)
            finally:
                expected = (
                    (self._manifest_path, manifest_bytes),
                    (self._snapshot_path, snapshot_bytes),
                    (self._notes_path, notes_bytes),
                    (self._state_path, state_bytes),
                    (self._ledger_path, ledger_bytes),
                )
                if all(path.exists() and path.read_bytes() == payload for path, payload in expected):
                    TransactionalRunStore._remove_exact_file(self._journal_path)
        return admitted

    def read_state(self) -> V52RunState:
        if self._read_only:
            if self._journal_path.exists():
                raise RecoveryError("real-system recovery is pending; run a mutating resume")
        else:
            self.recover()
        try:
            state_bytes = self._state_path.read_bytes()
            state = V52RunState.model_validate_json(state_bytes)
        except (OSError, ValidationError, ValueError) as exc:
            raise StoreError("invalid V5.2 real-system run state") from exc
        if canonical_json_bytes(state) != state_bytes:
            raise StoreError("real-system run state must use canonical JSON")
        self._require_run(state.run_id)
        manifest = self._validated_manifest(state)
        snapshot = self._validated_snapshot(state)
        self._validated_baseline_spine(state, manifest, snapshot)
        self._validated_runtime_notes(state)
        events = self._read_events_unrecovered()
        if not events or events[-1].state_digest != state.digest:
            raise StoreError("real-system state digest is not bound to ledger head")
        self._validate_ledger_projection(state, events)
        return state

    def read_events(self) -> tuple[RealSystemLedgerEvent, ...]:
        self.read_state()
        return self._read_events_unrecovered()

    def admitted_manifest(self) -> object:
        """Return only canonical manifest persisted by this real-system store."""

        return self._validated_manifest(self.read_state())

    def environment_snapshot(self) -> object:
        """Return only canonical snapshot persisted at real-system admission."""

        return self._validated_snapshot(self.read_state())

    def resolve_admitted_environment_receipts(
        self,
    ) -> tuple[tuple[SupervisorAuthorityReceipt, ...], EgressGateReceipt | None]:
        """Resolve typed receipt facts only after full durable authority validation."""

        state = self.read_state()
        return state.facts.supervisor_receipts, state.facts.egress_receipt

    def record_exploration_delta(self, delta: object) -> RealSystemLedgerEvent:
        """Append one evidence-led node after validating durable parent authority."""

        if not isinstance(delta, ExplorationDelta):
            raise StoreError("exploration registration requires strict ExplorationDelta")
        try:
            delta = ExplorationDelta.model_validate(delta.model_dump(mode="python"))
        except (ValidationError, ValueError) as exc:
            raise StoreError("exploration registration requires strict ExplorationDelta") from exc
        current = self.read_state()
        self._validate_exploration_delta(current, delta)
        successor = self._with_facts(
            current,
            exploration_deltas=current.facts.exploration_deltas + (delta,),
        )
        return self._append(
            "exploration_delta_recorded", delta.node.node_id, delta.digest, successor
        )

    def next_executable_authority(self) -> PersistedNodeExecutionAuthority | None:
        """Project only persisted executable authority in deterministic order."""

        state = self.read_state()
        if state.mode != "running":
            raise StoreError("next authority requires a running real-system run")
        consumed = {
            item.pending_decision_digest
            for item in state.facts.real_system_decision_consumptions
        }
        if any(
            pending.digest not in consumed
            for pending in state.facts.pending_real_system_decisions
        ):
            raise StoreError(
                "next authority is blocked by a pending exceptional decision"
            )
        baseline = state.facts.baseline_spine
        if baseline is None:
            raise StoreError("next authority requires admitted baseline spine")
        completed = {completion.node_id for completion in state.facts.node_completions}
        for delta in state.facts.exploration_deltas:
            if (
                delta.parent_node_id in completed
                and delta.node.node_id not in completed
            ):
                return PersistedNodeExecutionAuthority.exploration(delta)
        proposals = {
            proposal.proposal.node_id: proposal
            for proposal in baseline.baseline_proposals
        }
        for node in baseline.nodes:
            if node.node_id not in completed:
                return PersistedNodeExecutionAuthority.baseline(
                    node,
                    proposals.get(node.node_id),
                )
        return None

    def require_authorized_node(self, node: DerivedBehavioralNode) -> NodeAuthority:
        """Resolve exact canonical baseline or registered exploration membership."""

        if not isinstance(node, DerivedBehavioralNode):
            raise StoreError("node authority requires strict DerivedBehavioralNode")
        try:
            node = DerivedBehavioralNode.model_validate(node.model_dump(mode="python"))
        except (ValidationError, ValueError) as exc:
            raise StoreError("node authority requires strict DerivedBehavioralNode") from exc
        facts = self.read_state().facts
        baseline = facts.baseline_spine
        if baseline is not None and baseline.contains_exact(node):
            return NodeAuthority.baseline(node)
        for delta in facts.exploration_deltas:
            if delta.node.node_id == node.node_id and delta.node.digest == node.digest:
                return NodeAuthority.exploration(delta)
        raise StoreError("node is not admitted baseline authority or registered exploration")

    def record_node_completion(self, completion: object) -> RealSystemLedgerEvent:
        """Append a verification or already-receipted node completion."""

        if not isinstance(completion, RealNodeCompletion):
            raise StoreError("node completion requires strict RealNodeCompletion")
        try:
            completion = RealNodeCompletion.model_validate(
                completion.model_dump(mode="python")
            )
        except (ValidationError, ValueError) as exc:
            raise StoreError("node completion requires strict RealNodeCompletion") from exc
        current = self.read_state()
        if current.mode != "running":
            raise StoreError("node completion requires a running real-system run")
        head = current.facts.run_head
        node = self._authorized_node_for_id(current, completion.node_id)
        if (
            head is None
            or completion.run_id != current.run_id
            or completion.run_head_digest != head.digest
            or node is None
        ):
            raise StoreError("node completion does not bind admitted node authority")
        if any(item.node_id == completion.node_id for item in current.facts.node_completions):
            raise StoreError("node completion already exists")
        if completion.kind == "verification":
            self._validate_verification_completion(current, completion, node)
        else:
            receipt = next(
                (
                    item
                    for item in current.facts.external_operation_receipts
                    if item.operation_id == completion.operation_id
                ),
                None,
            )
            intent = next(
                (
                    item
                    for item in current.facts.external_operation_intents
                    if item.operation_id == completion.operation_id
                ),
                None,
            )
            if (
                receipt is None
                or intent is None
                or receipt.status != "succeeded"
                or intent.node_id != completion.node_id
                or receipt.evidence_refs != completion.evidence_refs
            ):
                raise StoreError("external node completion requires exact successful receipt")
        successor = self._with_facts(
            current,
            node_completions=current.facts.node_completions + (completion,),
        )
        return self._append(
            "real_node_completed", completion.node_id, completion.digest, successor
        )

    def record_pending_real_system_decision(
        self, pending: object
    ) -> RealSystemLedgerEvent:
        """Persist one exact exceptional gate. In-scope exploration never uses it."""

        if not isinstance(pending, PendingRealSystemDecision):
            raise StoreError("pending real-system decision must be strict")
        try:
            pending = PendingRealSystemDecision.model_validate(
                pending.model_dump(mode="python")
            )
        except (ValidationError, ValueError) as exc:
            raise StoreError("pending real-system decision must be strict") from exc
        current = self.read_state()
        try:
            validate_pending_real_system_decision_amendment(
                current, self._validated_manifest(current), pending
            )
        except ValueError as exc:
            raise StoreError(str(exc)) from exc
        if any(
            item.decision_id == pending.decision_id or item.digest == pending.digest
            for item in current.facts.pending_real_system_decisions
        ):
            raise StoreError("pending real-system decision already exists")
        if any(
            real_system_decision_target_key(item)
            == real_system_decision_target_key(pending)
            for item in current.facts.pending_real_system_decisions
        ):
            raise StoreError("pending real-system decision has a competing target")
        successor = self._with_facts(
            current,
            pending_real_system_decisions=current.facts.pending_real_system_decisions
            + (pending,),
        )
        return self._append(
            "real_system_decision_pending",
            pending.decision_id,
            pending.digest,
            successor,
        )

    def apply_real_system_decision(self, decision: object) -> V52RunState:
        """Consume exactly one matching exceptional decision; never generalize authority."""

        if not isinstance(decision, RealSystemDecision):
            raise StoreError("real-system decision must be strict")
        try:
            decision = RealSystemDecision.model_validate(decision.model_dump(mode="python"))
        except (ValidationError, ValueError) as exc:
            raise StoreError("real-system decision must be strict") from exc
        current = self.read_state()
        pending = next(
            (
                item
                for item in current.facts.pending_real_system_decisions
                if item.digest == decision.pending_decision_digest
            ),
            None,
        )
        if pending is None:
            raise StoreError("real-system decision has no matching pending authority")
        if any(
            item.pending_decision_digest == pending.digest
            for item in current.facts.real_system_decision_consumptions
        ):
            raise StoreError("real-system decision is already consumed")
        try:
            validate_pending_real_system_decision_amendment(
                current, self._validated_manifest(current), pending
            )
        except ValueError as exc:
            raise StoreError("real-system decision is stale against current authority") from exc
        if (
            decision.decision_id != pending.decision_id
            or decision.kind != pending.kind
            or decision.run_id != pending.run_id
            or decision.run_head_digest != pending.run_head_digest
            or decision.authority_digest != pending.authority_digest
            or decision.payload_digest != pending.payload_digest
            or decision.amendment != pending.amendment
        ):
            raise StoreError("real-system decision does not bind exact pending authority")
        consumption = RealSystemDecisionConsumption(
            pending_decision_digest=pending.digest,
            decision=decision,
            amendment=pending.amendment,
        )
        successor = self._with_facts(
            current,
            real_system_decision_consumptions=current.facts.real_system_decision_consumptions
            + (consumption,),
        )
        self._append(
            "real_system_decision_consumed",
            pending.decision_id,
            consumption.digest,
            successor,
        )
        return self.read_state()

    def validate_intent_for_authorized_node(
        self,
        intent: ExternalOperationIntent,
        node_authority: NodeAuthority,
    ) -> None:
        """Bind caller intent to exact store-owned node authority before dispatch."""

        if not isinstance(intent, ExternalOperationIntent) or not isinstance(
            node_authority, NodeAuthority
        ):
            raise StoreError("external operation intent requires strict node authority")
        try:
            authority = NodeAuthority.model_validate(
                node_authority.model_dump(mode="python")
            )
        except (ValidationError, ValueError) as exc:
            raise StoreError("external operation intent requires strict node authority") from exc
        persisted = self.require_authorized_node(authority.node)
        if persisted != authority:
            raise StoreError("external operation intent does not bind persisted node authority")
        if intent.node_id != authority.node.node_id:
            raise StoreError("external operation intent does not bind supplied node authority")
        self._validate_intent_node_authority(self.read_state(), intent)

    def record_resource_lease(self, lease: object) -> RealSystemLedgerEvent:
        from .models import ResourceLease

        if not isinstance(lease, ResourceLease):
            raise StoreError("real-system resource lease must be a strict ResourceLease")
        current = self.read_state()
        if lease.run_id != current.run_id:
            raise StoreError("resource lease belongs to another real-system run")
        manifest = self._validated_manifest(current)
        if (
            lease.resource_kind in {"account", "namespace", "fixture"}
            and lease.resource not in manifest.synthetic_scope.owned_resources
        ):
            raise StoreError("resource lease is outside admitted synthetic scope")
        if any(item.lease_id == lease.lease_id or item.resource == lease.resource for item in current.facts.leases):
            raise StoreError("resource lease collides with an existing real-system lease")
        successor = self._with_facts(current, leases=current.facts.leases + (lease,))
        return self._append(
            "resource_lease_recorded", lease.lease_id, digest_for("resource-lease", lease), successor
        )

    def record_external_intent(
        self, intent: object
    ) -> RealSystemLedgerEvent:
        if not isinstance(intent, ExternalOperationIntent):
            raise StoreError("external operation requires a strict ExternalOperationIntent")
        current = self.read_state()
        if current.mode != "running":
            raise StoreError("external operation intent requires a running real-system run")
        head = current.facts.run_head
        if head is None:
            raise StoreError("external operation intent requires sealed real-system Run Head")
        if any(item.operation_id == intent.operation_id for item in current.facts.external_operation_intents):
            raise StoreError("external operation intent already exists")
        if any(item.idempotency_key == intent.idempotency_key for item in current.facts.external_operation_intents):
            raise StoreError("external operation idempotency key already exists")
        if any(
            item.reservation_id == intent.reserved_budget.reservation_id
            for item in current.facts.budget_reservations
        ):
            raise StoreError("external operation budget reservation already exists")
        manifest = self._validated_manifest(current)
        if intent.effect not in {capability.effect for capability in manifest.capabilities}:
            raise StoreError("external operation effect is not admitted by manifest capability")
        self._validate_intent_node_authority(current, intent)
        self._require_exact_persisted_operation_intent(current, intent)
        self._assert_budget_reservation(current, intent.reserved_budget)
        successor = self._with_facts(
            current,
            budget_reservations=current.facts.budget_reservations + (intent.reserved_budget,),
            external_operation_intents=current.facts.external_operation_intents + (intent,),
        )
        return self._append(
            "external_operation_intended", intent.operation_id, intent.digest, successor
        )

    def record_manifest_budget_exhaustion(
        self, rejected_intent: object
    ) -> RealSystemLedgerEvent:
        """Atomically block a running run after exact aggregate reservation exhaustion."""

        if not isinstance(rejected_intent, ExternalOperationIntent):
            raise StoreError("manifest budget exhaustion requires a strict ExternalOperationIntent")
        current = self.read_state()
        if current.mode != "running":
            raise StoreError("manifest budget exhaustion requires a running real-system run")
        if current.facts.manifest_budget_exhaustions:
            raise StoreError("manifest budget exhaustion is already terminal")
        if any(
            item.operation_id == rejected_intent.operation_id
            or item.idempotency_key == rejected_intent.idempotency_key
            for item in current.facts.external_operation_intents
        ) or any(
            item.reservation_id == rejected_intent.reserved_budget.reservation_id
            for item in current.facts.budget_reservations
        ):
            raise StoreError("manifest budget exhaustion cannot persist an existing operation")
        head = current.facts.run_head
        manifest = self._validated_manifest(current)
        if head is None:
            raise StoreError("manifest budget exhaustion requires sealed real-system Run Head")
        if rejected_intent.effect not in {
            capability.effect for capability in manifest.capabilities
        }:
            raise StoreError("external operation effect is not admitted by manifest capability")
        self._validate_intent_node_authority(current, rejected_intent)
        self._require_exact_persisted_operation_intent(current, rejected_intent)
        try:
            self._assert_budget_reservation(current, rejected_intent.reserved_budget)
        except BudgetReservationExceeded as exc:
            exhausted_budget_names = exc.exhausted_budget_names
        else:
            raise StoreError("manifest budget exhaustion requires an exceeded aggregate budget")
        exhaustion = ManifestBudgetExhaustion(
            run_id=current.run_id,
            run_head_digest=head.digest,
            manifest_digest=current.adapter_manifest_digest,
            rejected_intent=rejected_intent,
            exhausted_budget_names=exhausted_budget_names,
        )
        blocked = current.model_copy(update={"mode": "blocked"})
        successor = self._with_facts(
            blocked,
            manifest_budget_exhaustions=(exhaustion,),
        )
        return self._append(
            "manifest_budget_exhausted_blocked",
            rejected_intent.operation_id,
            exhaustion.digest,
            successor,
        )

    def record_external_receipt(self, receipt: object) -> RealSystemLedgerEvent:
        if not isinstance(receipt, ExternalOperationReceipt):
            raise StoreError("external operation receipt must be a strict ExternalOperationReceipt")
        current = self.read_state()
        intents = tuple(
            item
            for item in current.facts.external_operation_intents
            if item.operation_id == receipt.operation_id
        )
        if len(intents) != 1:
            raise StoreError("external operation receipt requires exactly one prior intent")
        intent = intents[0]
        if any(item.operation_id == receipt.operation_id for item in current.facts.external_operation_receipts):
            raise StoreError("external operation receipt already exists")
        if any(item.receipt_id == receipt.receipt_id for item in current.facts.external_operation_receipts):
            raise StoreError("external operation receipt identity already exists")
        if (
            receipt.run_id != intent.run_id
            or receipt.manifest_digest != intent.manifest_digest
            or receipt.run_head_digest != intent.run_head_digest
            or receipt.idempotency_key != intent.idempotency_key
        ):
            raise StoreError("external operation receipt does not bind exact prior intent")
        completion = (
            RealNodeCompletion(
                run_id=current.run_id,
                node_id=intent.node_id,
                run_head_digest=intent.run_head_digest,
                kind="external_receipt",
                evidence_refs=receipt.evidence_refs,
                operation_id=intent.operation_id,
            )
            if receipt.status == "succeeded"
            else None
        )
        successor = self._with_facts(
            current,
            external_operation_receipts=current.facts.external_operation_receipts + (receipt,),
            node_completions=(
                current.facts.node_completions
                if completion is None
                else current.facts.node_completions + (completion,)
            ),
        )
        return self._append(
            "external_operation_receipted", receipt.receipt_id, receipt.digest, successor
        )

    def record_runtime_note(self, note: object) -> RealSystemLedgerEvent:
        if not isinstance(note, RuntimeNote):
            raise StoreError("runtime note must be a strict RuntimeNote")
        current = self.read_state()
        lease = next((item for item in current.facts.leases if item.lease_id == note.lease_id), None)
        if lease is None or lease.run_id != current.run_id or lease.resource != note.resource_ref:
            raise StoreError("lease/note ownership mismatch")
        if any(item.digest == note.digest for item in current.facts.runtime_notes):
            raise StoreError("runtime note already exists")
        receipt_refs = {
            value.receipt_id for value in current.facts.external_operation_receipts
        } | {value.digest for value in current.facts.external_operation_receipts}
        if note.receipt_ref not in receipt_refs:
            raise StoreError("runtime note must bind an exact persisted operation receipt")
        successor = self._with_facts(
            current, runtime_notes=current.facts.runtime_notes + (note,)
        )
        note_line = self._note_line(note)
        return self._append(
            "runtime_note_recorded", note.lease_id, note.digest, successor, note_line=note_line
        )

    def reconcile_unsettled_intents(self) -> V52RunState:
        """Pause rather than retry when an intent lacks an exact successful receipt."""

        current = self.read_state()
        receipts = {
            receipt.operation_id
            for receipt in current.facts.external_operation_receipts
            if receipt.status == "succeeded"
        }
        unsettled = tuple(
            intent
            for intent in current.facts.external_operation_intents
            if intent.operation_id not in receipts
        )
        if not unsettled:
            return current
        if current.mode == "paused":
            return current
        successor = current.model_copy(update={"mode": "paused"})
        self._append(
            "unsettled_operation_paused",
            unsettled[0].operation_id,
            unsettled[0].digest,
            successor,
        )
        return self.read_state()

    def pause_for_environment_snapshot_drift(self, observed_snapshot: object) -> V52RunState:
        """Fail closed when bridge identity no longer equals sealed admission bytes."""

        from .environment import EnvironmentSnapshot

        if not isinstance(observed_snapshot, EnvironmentSnapshot):
            raise StoreError("environment drift pause requires strict EnvironmentSnapshot")
        current = self.read_state()
        expected = self._validated_snapshot(current)
        if observed_snapshot == expected:
            return current
        if current.mode == "paused":
            return current
        if current.mode != "running":
            raise StoreError("environment snapshot drift can pause only a running real-system run")
        successor = current.model_copy(update={"mode": "paused"})
        self._append(
            "environment_snapshot_drift_paused",
            observed_snapshot.digest,
            digest_for(
                "environment-snapshot-drift",
                {
                    "expected": expected.digest,
                    "observed": observed_snapshot.digest,
                },
            ),
            successor,
        )
        return self.read_state()

    def cleanup(
        self,
        note: object,
        decision: object,
        ownership_token: str,
    ) -> CleanupDecision:
        """Record authority only; adapters perform no deletion without this proof."""

        if not isinstance(note, RuntimeNote) or not isinstance(decision, CleanupDecision):
            raise StoreError("cleanup requires strict runtime note and digest-bound decision")
        try:
            note = RuntimeNote.model_validate(note.model_dump(mode="python"))
            decision = CleanupDecision.model_validate(decision.model_dump(mode="python"))
        except (ValidationError, ValueError) as exc:
            raise StoreError("cleanup requires strict cleanup authority") from exc
        current = self.read_state()
        if note not in current.facts.runtime_notes:
            raise StoreError("cleanup note is not persisted for this real-system run")
        if note.classification != "ephemeral_test_data":
            raise StoreError("fix_or_patch runtime notes always require treatment decision")
        if (
            decision.run_id != current.run_id
            or decision.manifest_digest != current.adapter_manifest_digest
            or decision.runtime_note_digest != note.digest
        ):
            raise StoreError("cleanup decision does not bind exact persisted runtime note")
        lease = next((item for item in current.facts.leases if item.lease_id == note.lease_id), None)
        if (
            lease is None
            or lease.run_id != current.run_id
            or lease.resource != note.resource_ref
            or not lease.ownership_matches(ownership_token)
        ):
            raise StoreError("lease/note ownership mismatch")
        if lease.is_expired():
            raise StoreError("expired resource lease cannot authorize cleanup")
        if current.mode not in {"verified", "blocked", "failed", "cancelled"}:
            raise StoreError("cleanup requires terminal result discussion")
        if decision.digest in current.facts.cleanup_decision_digests:
            return decision
        successor = self._with_facts(
            current,
            cleanup_decision_digests=current.facts.cleanup_decision_digests + (decision.digest,),
        )
        self._append("cleanup_authorized", decision.decision_id, decision.digest, successor)
        return decision

    def _validated_manifest(self, state: V52RunState) -> object:
        from .adapters.manifest import AdapterManifest
        from .adapters.registry import AdapterManifestError, resolve_descriptor
        from .adapters.host_registry import HostProviderError, resolve_host_provider

        try:
            payload = self._manifest_path.read_bytes()
            manifest = AdapterManifest.model_validate_json(payload)
        except (OSError, ValidationError, ValueError) as exc:
            raise StoreError("invalid persisted adapter manifest") from exc
        if canonical_json_bytes(manifest) != payload or manifest.digest != state.adapter_manifest_digest:
            raise StoreError("persisted adapter manifest does not bind V5.2 state")
        try:
            resolve_descriptor(manifest)
        except AdapterManifestError as exc:
            raise StoreError("persisted adapter manifest does not select registered descriptor") from exc
        authority = state.facts.provider_authority
        if authority is not None:
            try:
                provider = resolve_host_provider(manifest.adapter_id)
            except HostProviderError as exc:
                raise StoreError("persisted provider authority does not select registered provider") from exc
            if (
                authority.adapter_id != manifest.adapter_id
                or authority.provider_id != provider.provider_id
            ):
                raise StoreError("persisted provider authority does not bind registered manifest provider")
        return manifest

    def _validated_snapshot(self, state: V52RunState) -> object:
        from .environment import EnvironmentPreflightError, EnvironmentSnapshot

        try:
            payload = self._snapshot_path.read_bytes()
            snapshot = EnvironmentSnapshot.model_validate_json(payload)
        except (OSError, ValidationError, ValueError) as exc:
            raise StoreError("invalid persisted environment snapshot") from exc
        head = state.facts.run_head
        try:
            expected = EnvironmentSnapshot.from_admitted_authority(
                manifest=self._validated_manifest(state),
                target_identity_digest=state.trajectory.execution_envelope.target_identity_digest,
                supervisor_receipts=state.facts.supervisor_receipts,
                egress_receipt=state.facts.egress_receipt,
            )
        except (EnvironmentPreflightError, TypeError, ValueError) as exc:
            raise StoreError("persisted environment receipts do not bind V5.2 authority") from exc
        if (
            canonical_json_bytes(snapshot) != payload
            or head is None
            or state.facts.environment_snapshot_digest != snapshot.digest
            or head.environment_snapshot_digest != snapshot.digest
            or snapshot.adapter_manifest_digest != state.adapter_manifest_digest
            or snapshot.target_identity_digest
            != state.trajectory.execution_envelope.target_identity_digest
            or snapshot != expected
        ):
            raise StoreError("persisted environment snapshot does not bind V5.2 authority")
        return snapshot

    @staticmethod
    def _validated_baseline_spine(
        state: V52RunState, manifest: object, snapshot: object
    ) -> BaselineSpineAuthority:
        from .adapters.manifest import AdapterManifest
        from .environment import EnvironmentSnapshot

        baseline = state.facts.baseline_spine
        head = state.facts.run_head
        if (
            baseline is None
            or head is None
            or not isinstance(manifest, AdapterManifest)
            or not isinstance(snapshot, EnvironmentSnapshot)
        ):
            raise StoreError("persisted baseline spine authority is unavailable")
        try:
            expected = BaselineSpineAuthority.from_nodes(
                state,
                head,
                manifest,
                snapshot,
                baseline.nodes,
                baseline.baseline_proposals,
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise StoreError("persisted baseline spine authority is invalid") from exc
        if baseline != expected:
            raise StoreError("persisted baseline spine authority is invalid")
        return baseline

    @staticmethod
    def _authorized_node_for_id(
        state: V52RunState, node_id: str
    ) -> DerivedBehavioralNode | None:
        baseline = state.facts.baseline_spine
        if baseline is None:
            return None
        for node in baseline.nodes:
            if node.node_id == node_id:
                return node
        return next(
            (
                delta.node
                for delta in state.facts.exploration_deltas
                if delta.node.node_id == node_id
            ),
            None,
        )

    @staticmethod
    def _validate_verification_completion(
        state: V52RunState,
        completion: RealNodeCompletion,
        node: DerivedBehavioralNode,
    ) -> None:
        """Apply one verification-evidence rule to live, recovery, and reads."""

        from .models import Observation

        head = state.facts.run_head
        observation = completion.verification_observation
        if (
            head is None
            or node.action_kind != "verify_only"
            or not isinstance(observation, Observation)
            or observation.kind != "behavioral"
            or observation.node_id != node.source_anchor_id
            or observation.run_head_digest != head.digest
            or observation.evidence_refs != completion.evidence_refs
            or observation.observed_state not in node.expected_after
        ):
            raise StoreError(
                "verification completion requires exact verification observation"
            )

    def _validate_intent_node_authority(
        self, state: V52RunState, intent: ExternalOperationIntent
    ) -> None:
        head = state.facts.run_head
        node = self._authorized_node_for_id(state, intent.node_id)
        if (
            state.mode != "running"
            or head is None
            or intent.run_id != state.run_id
            or intent.manifest_digest != state.adapter_manifest_digest
            or intent.run_head_digest != head.digest
            or node is None
            or node.side_effect is None
            or intent.effect != node.side_effect
        ):
            raise StoreError(
                "external operation intent does not bind persisted node authority"
            )

    @staticmethod
    def _require_exact_persisted_operation_intent(
        state: V52RunState, intent: ExternalOperationIntent
    ) -> None:
        """Admitted-provider runs reject caller-chosen operation or budget bytes."""

        if state.facts.provider_authority is None:
            raise StoreError("external operation intent lacks admitted provider authority")
        from .models import (
            PersistedNodeExecutionAuthority,
            derive_persisted_external_operation_intent,
        )

        baseline = state.facts.baseline_spine
        if baseline is None:
            raise StoreError("external operation intent lacks persisted proposal budget")
        proposal = next(
            (
                item
                for item in baseline.baseline_proposals
                if item.proposal.node_id == intent.node_id
            ),
            None,
        )
        if proposal is not None:
            node = next(
                (item for item in baseline.nodes if item.node_id == intent.node_id),
                None,
            )
            if node is None:
                raise StoreError("external operation intent lacks persisted proposal budget")
            authority = PersistedNodeExecutionAuthority.baseline(node, proposal)
        else:
            delta = next(
                (
                    item
                    for item in state.facts.exploration_deltas
                    if item.node.node_id == intent.node_id
                ),
                None,
            )
            if delta is None:
                raise StoreError("external operation intent lacks persisted proposal budget")
            authority = PersistedNodeExecutionAuthority.exploration(delta)
        try:
            expected = derive_persisted_external_operation_intent(state, authority)
        except ValueError as exc:
            raise StoreError("external operation intent lacks persisted proposal budget") from exc
        if intent != expected:
            raise StoreError(
                "external operation intent does not bind exact proposal budget authority"
            )

    def _validate_exploration_delta(
        self, state: V52RunState, delta: ExplorationDelta
    ) -> None:
        baseline = state.facts.baseline_spine
        head = state.facts.run_head
        if baseline is None or head is None:
            raise StoreError("exploration registration requires persisted baseline authority")
        if (
            delta.run_id != state.run_id
            or delta.run_head_digest != head.digest
            or delta.adapter_manifest_digest != state.adapter_manifest_digest
            or delta.environment_snapshot_digest != state.facts.environment_snapshot_digest
            or delta.node.trajectory_digest != state.trajectory.digest
            or delta.node.execution_envelope_digest != state.trajectory.execution_envelope.digest
        ):
            raise StoreError("exploration delta does not bind exact persisted authority")
        known_nodes = set(baseline.node_ids)
        known_nodes.update(item.node.node_id for item in state.facts.exploration_deltas)
        if delta.parent_node_id not in known_nodes:
            raise StoreError("exploration delta parent is not admitted baseline or earlier exploration")
        if delta.node.node_id in known_nodes:
            raise StoreError("exploration delta node identity already exists")
        parent_node = self._authorized_node_for_id(state, delta.parent_node_id)
        parent_completion = next(
            (
                item
                for item in state.facts.node_completions
                if item.node_id == delta.parent_node_id
            ),
            None,
        )
        persisted_parent_evidence = set(
            () if parent_node is None else parent_node.entry_observation_refs
        )
        if parent_completion is not None:
            persisted_parent_evidence.update(parent_completion.evidence_refs)
        if not set(delta.evidence_refs).issubset(persisted_parent_evidence):
            raise StoreError(
                "exploration delta requires exact persisted parent evidence"
            )
        manifest = self._validated_manifest(state)
        if delta.node.side_effect is not None and delta.node.side_effect not in {
            capability.effect for capability in manifest.capabilities
        }:
            raise StoreError("exploration delta effect is not admitted by manifest capability")
        if any(target != manifest.target.host for target in delta.node.target_systems):
            raise StoreError("exploration delta target is outside admitted exact target scope")
        if delta.node.side_effect is not None:
            budget = None if delta.proposal is None else delta.proposal.budget
            if budget is None:
                raise StoreError(
                    "effectful exploration requires immutable proposal budget authority"
                )
            try:
                validate_node_budget_against_manifest(
                    budget, manifest, authority="exploration proposal"
                )
            except ValueError as exc:
                raise StoreError(str(exc)) from exc

    def _runtime_notes_bytes(self, state: V52RunState) -> bytes:
        return b"".join(self._note_line(note) for note in state.facts.runtime_notes)

    def _validated_runtime_notes(self, state: V52RunState) -> None:
        try:
            payload = self._notes_path.read_bytes()
        except OSError as exc:
            raise StoreError("runtime notes projection is unavailable") from exc
        if payload != self._runtime_notes_bytes(state):
            raise StoreError("runtime notes projection does not match persisted facts")

    def _assert_budget_reservation(
        self, state: V52RunState, reservation: BudgetReservation
    ) -> None:
        manifest = self._validated_manifest(state)
        budgets = manifest.budgets
        fields = (
            ("user_actions", "max_user_actions"),
            ("provider_requests", "max_provider_requests"),
            ("cost_micros", "max_cost_micros"),
            ("requests", "max_requests"),
            ("processes", "max_processes"),
            ("persistence_writes", "max_persistence_writes"),
            ("tokens", "max_tokens"),
            ("duration_ms", "max_duration_ms"),
        )
        exhausted_budget_names = tuple(
            budget_name
            for reservation_name, budget_name in fields
            if (
                sum(
                    getattr(item, reservation_name)
                    for item in state.facts.budget_reservations
                )
                + getattr(reservation, reservation_name)
                > getattr(budgets, budget_name)
            )
        )
        if exhausted_budget_names:
            raise BudgetReservationExceeded(exhausted_budget_names)

    def _with_facts(self, state: V52RunState, **updates: object) -> V52RunState:
        try:
            facts = RealSystemFactIndex.model_validate_json(
                canonical_json_bytes(
                    {**state.facts.model_dump(mode="python"), **updates}
                )
            )
            return V52RunState.model_validate_json(
                canonical_json_bytes(
                    {**state.model_dump(mode="python"), "facts": facts}
                )
            )
        except (ValidationError, ValueError) as exc:
            raise StoreError("real-system store requires a strict V5.2 successor") from exc

    def _append(
        self,
        kind: RealSystemEventKind,
        fact_id: str,
        fact_digest: str,
        successor: V52RunState,
        *,
        note_line: bytes = b"",
    ) -> RealSystemLedgerEvent:
        self._require_mutable()
        if kind not in _REAL_SYSTEM_EVENT_KINDS:
            raise StoreError("unknown real-system event kind")
        if not isinstance(successor, V52RunState) or successor.run_id != self._run_id:
            raise StoreError("real-system successor must bind this exact run")
        if note_line and (not note_line.endswith(b"\n") or b"\0" in note_line):
            raise StoreError("runtime notes projection is invalid")
        self.recover()
        with self._lock():
            current = self._read_state_unrecovered()
            events = self._read_events_unrecovered()
            if not events or events[-1].state_digest != current.digest:
                raise StoreError("real-system state digest is not bound to ledger head")
            self._validate_successor(current, successor)
            event = RealSystemLedgerEvent.create(
                sequence=len(events) + 1,
                kind=kind,
                fact_id=fact_id,
                fact_digest=fact_digest,
                previous_digest=events[-1].event_digest,
                state_digest=successor.digest,
            )
            state_bytes = canonical_json_bytes(successor)
            state_before_bytes = canonical_json_bytes(current)
            event_line = canonical_json_bytes(event) + b"\n"
            ledger_before = self._ledger_path.read_bytes()
            notes_before = self._notes_path.read_bytes()
            journal = {
                "schema_version": self._JOURNAL_SCHEMA,
                "state_before_bytes_b64": base64.b64encode(state_before_bytes).decode("ascii"),
                "state_bytes_b64": base64.b64encode(state_bytes).decode("ascii"),
                "event_line_b64": base64.b64encode(event_line).decode("ascii"),
                "ledger_before_b64": base64.b64encode(ledger_before).decode("ascii"),
                "notes_before_b64": base64.b64encode(notes_before).decode("ascii"),
                "note_line_b64": base64.b64encode(note_line).decode("ascii"),
            }
            TransactionalRunStore._atomic_write(
                self._journal_path, canonical_json_bytes(journal)
            )
            try:
                TransactionalRunStore._atomic_write(self._state_path, state_bytes)
                TransactionalRunStore._append_bytes(self._ledger_path, event_line)
                if note_line:
                    TransactionalRunStore._append_bytes(self._notes_path, note_line)
            except OSError:
                # Journal holds exact prior/next bytes; a fresh open completes safely.
                raise
            finally:
                if (
                    self._state_path.exists()
                    and self._state_path.read_bytes() == state_bytes
                    and self._ledger_path.read_bytes() == ledger_before + event_line
                    and self._notes_path.read_bytes() == notes_before + note_line
                ):
                    TransactionalRunStore._remove_exact_file(self._journal_path)
            return event

    def _read_state_unrecovered(self) -> V52RunState:
        try:
            state_bytes = self._state_path.read_bytes()
            state = V52RunState.model_validate_json(state_bytes)
        except (OSError, ValidationError, ValueError) as exc:
            raise StoreError("invalid V5.2 real-system run state") from exc
        if canonical_json_bytes(state) != state_bytes:
            raise StoreError("real-system run state must use canonical JSON")
        self._require_run(state.run_id)
        return state

    def _read_events_unrecovered(self) -> tuple[RealSystemLedgerEvent, ...]:
        try:
            payload = self._ledger_path.read_bytes()
        except OSError as exc:
            raise StoreError("real-system ledger is unavailable") from exc
        if not payload or not payload.endswith(b"\n"):
            raise StoreError("real-system ledger must contain newline-terminated events")
        events: list[RealSystemLedgerEvent] = []
        previous = _GENESIS_DIGEST
        for sequence, line in enumerate(payload.splitlines(), start=1):
            try:
                event = RealSystemLedgerEvent.model_validate_json(line)
            except (ValidationError, ValueError) as exc:
                raise StoreError("invalid real-system ledger event") from exc
            if canonical_json_bytes(event) != line:
                raise StoreError("real-system ledger event must use canonical JSON")
            if event.sequence != sequence or event.previous_digest != previous:
                raise StoreError("real-system ledger hash chain is invalid")
            previous = event.event_digest
            events.append(event)
        return tuple(events)

    def _validate_ledger_projection(
        self,
        state: V52RunState,
        events: tuple[RealSystemLedgerEvent, ...],
    ) -> None:
        head = state.facts.run_head
        admission_facts = RealSystemFactIndex(
            environment_snapshot_digest=state.facts.environment_snapshot_digest,
            run_head=head,
            provider_authority=state.facts.provider_authority,
            baseline_spine=state.facts.baseline_spine,
            supervisor_receipts=state.facts.supervisor_receipts,
            egress_receipt=state.facts.egress_receipt,
        )
        admitted = state.model_copy(update={"facts": admission_facts})
        if admitted.digest != events[0].state_digest and any(
            event.kind
            in {
                "unsettled_operation_paused",
                "environment_snapshot_drift_paused",
                "manifest_budget_exhausted_blocked",
            }
            for event in events[1:]
        ):
            admitted = admitted.model_copy(update={"mode": "running"})
        if (
            head is None
            or state.facts.baseline_spine is None
            or events[0].kind != "real_system_admitted"
            or events[0].fact_id != state.facts.baseline_spine.digest
            or events[0].fact_digest != state.facts.baseline_spine.digest
            or events[0].state_digest != admitted.digest
        ):
            raise StoreError("real-system ledger projection is invalid")
        (
            delta_index,
            lease_index,
            intent_index,
            exhaustion_index,
            receipt_index,
            completion_index,
            pending_decision_index,
            consumption_index,
            note_index,
            decision_index,
        ) = (0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        current = admitted
        for event in events[1:]:
            if event.kind == "exploration_delta_recorded":
                if delta_index >= len(state.facts.exploration_deltas):
                    raise StoreError("real-system ledger projection is invalid")
                delta = state.facts.exploration_deltas[delta_index]
                delta_index += 1
                successor = self._with_facts(
                    current,
                    exploration_deltas=current.facts.exploration_deltas + (delta,),
                )
            elif event.kind == "resource_lease_recorded":
                if lease_index >= len(state.facts.leases):
                    raise StoreError("real-system ledger projection is invalid")
                lease = state.facts.leases[lease_index]
                lease_index += 1
                successor = self._with_facts(
                    current, leases=current.facts.leases + (lease,)
                )
            elif event.kind == "external_operation_intended":
                if (
                    intent_index >= len(state.facts.external_operation_intents)
                    or intent_index >= len(state.facts.budget_reservations)
                ):
                    raise StoreError("real-system ledger projection is invalid")
                intent = state.facts.external_operation_intents[intent_index]
                reservation = state.facts.budget_reservations[intent_index]
                intent_index += 1
                successor = self._with_facts(
                    current,
                    budget_reservations=current.facts.budget_reservations
                    + (reservation,),
                    external_operation_intents=current.facts.external_operation_intents
                    + (intent,),
                )
            elif event.kind == "manifest_budget_exhausted_blocked":
                if exhaustion_index >= len(state.facts.manifest_budget_exhaustions):
                    raise StoreError("real-system ledger projection is invalid")
                exhaustion = state.facts.manifest_budget_exhaustions[exhaustion_index]
                exhaustion_index += 1
                blocked = current.model_copy(update={"mode": "blocked"})
                successor = self._with_facts(
                    blocked,
                    manifest_budget_exhaustions=(exhaustion,),
                )
            elif event.kind == "external_operation_receipted":
                if receipt_index >= len(state.facts.external_operation_receipts):
                    raise StoreError("real-system ledger projection is invalid")
                receipt = state.facts.external_operation_receipts[receipt_index]
                receipt_index += 1
                completion = None
                if receipt.status == "succeeded":
                    if completion_index >= len(state.facts.node_completions):
                        raise StoreError("real-system ledger projection is invalid")
                    completion = state.facts.node_completions[completion_index]
                    completion_index += 1
                    expected_completion = RealNodeCompletion(
                        run_id=current.run_id,
                        node_id=next(
                            item.node_id
                            for item in current.facts.external_operation_intents
                            if item.operation_id == receipt.operation_id
                        ),
                        run_head_digest=receipt.run_head_digest,
                        kind="external_receipt",
                        evidence_refs=receipt.evidence_refs,
                        operation_id=receipt.operation_id,
                    )
                    if completion != expected_completion:
                        raise StoreError("real-system ledger projection is invalid")
                successor = self._with_facts(
                    current,
                    external_operation_receipts=current.facts.external_operation_receipts
                    + (receipt,),
                    node_completions=(
                        current.facts.node_completions
                        if completion is None
                        else current.facts.node_completions + (completion,)
                    ),
                )
            elif event.kind == "real_node_completed":
                if completion_index >= len(state.facts.node_completions):
                    raise StoreError("real-system ledger projection is invalid")
                completion = state.facts.node_completions[completion_index]
                completion_index += 1
                successor = self._with_facts(
                    current,
                    node_completions=current.facts.node_completions + (completion,),
                )
            elif event.kind == "real_system_decision_pending":
                if pending_decision_index >= len(state.facts.pending_real_system_decisions):
                    raise StoreError("real-system ledger projection is invalid")
                pending = state.facts.pending_real_system_decisions[pending_decision_index]
                pending_decision_index += 1
                successor = self._with_facts(
                    current,
                    pending_real_system_decisions=current.facts.pending_real_system_decisions
                    + (pending,),
                )
            elif event.kind == "real_system_decision_consumed":
                if consumption_index >= len(state.facts.real_system_decision_consumptions):
                    raise StoreError("real-system ledger projection is invalid")
                consumption = state.facts.real_system_decision_consumptions[consumption_index]
                consumption_index += 1
                successor = self._with_facts(
                    current,
                    real_system_decision_consumptions=current.facts.real_system_decision_consumptions
                    + (consumption,),
                )
            elif event.kind == "runtime_note_recorded":
                if note_index >= len(state.facts.runtime_notes):
                    raise StoreError("real-system ledger projection is invalid")
                note = state.facts.runtime_notes[note_index]
                note_index += 1
                successor = self._with_facts(
                    current, runtime_notes=current.facts.runtime_notes + (note,)
                )
            elif event.kind == "cleanup_authorized":
                if decision_index >= len(state.facts.cleanup_decision_digests):
                    raise StoreError("real-system ledger projection is invalid")
                decision_digest = state.facts.cleanup_decision_digests[decision_index]
                decision_index += 1
                successor = self._with_facts(
                    current,
                    cleanup_decision_digests=current.facts.cleanup_decision_digests
                    + (decision_digest,),
                )
            elif event.kind == "unsettled_operation_paused":
                successor = current.model_copy(update={"mode": "paused"})
            elif event.kind == "environment_snapshot_drift_paused":
                successor = current.model_copy(update={"mode": "paused"})
            else:
                raise StoreError("real-system ledger projection is invalid")
            try:
                self._validate_recovered_successor(current, successor, event)
            except StoreError as exc:
                raise StoreError("real-system ledger projection is invalid") from exc
            if event.state_digest != successor.digest:
                raise StoreError("real-system ledger projection state digest is invalid")
            current = successor
        if (
            current != state
            or delta_index != len(state.facts.exploration_deltas)
            or lease_index != len(state.facts.leases)
            or intent_index != len(state.facts.external_operation_intents)
            or intent_index != len(state.facts.budget_reservations)
            or exhaustion_index != len(state.facts.manifest_budget_exhaustions)
            or receipt_index != len(state.facts.external_operation_receipts)
            or completion_index != len(state.facts.node_completions)
            or pending_decision_index != len(state.facts.pending_real_system_decisions)
            or consumption_index != len(state.facts.real_system_decision_consumptions)
            or note_index != len(state.facts.runtime_notes)
            or decision_index != len(state.facts.cleanup_decision_digests)
        ):
            raise StoreError("real-system ledger projection is invalid")

    @staticmethod
    def _validate_successor(current: V52RunState, successor: V52RunState) -> None:
        if (
            successor.schema_version != current.schema_version
            or successor.run_id != current.run_id
            or successor.trajectory != current.trajectory
            or successor.confirmation != current.confirmation
        ):
            raise StoreError("real-system successor rewrites immutable admitted authority")
        fields = (
            "exploration_deltas",
            "leases",
            "budget_reservations",
            "external_operation_intents",
            "manifest_budget_exhaustions",
            "external_operation_receipts",
            "node_completions",
            "pending_real_system_decisions",
            "real_system_decision_consumptions",
            "runtime_notes",
            "cleanup_decision_digests",
        )
        for field_name in fields:
            before = getattr(current.facts, field_name)
            after = getattr(successor.facts, field_name)
            if after[: len(before)] != before:
                raise StoreError(f"real-system successor rewrites append-only facts: {field_name}")
        if (
            successor.facts.environment_snapshot_digest
            != current.facts.environment_snapshot_digest
            or successor.facts.run_head != current.facts.run_head
            or successor.facts.provider_authority != current.facts.provider_authority
            or successor.facts.baseline_spine != current.facts.baseline_spine
            or successor.facts.supervisor_receipts != current.facts.supervisor_receipts
            or successor.facts.egress_receipt != current.facts.egress_receipt
        ):
            raise StoreError("real-system successor replaces sealed environment authority")

    def recover(self) -> None:
        self._require_mutable()
        if not self._journal_path.exists():
            return
        with self._lock():
            if not self._journal_path.exists():
                return
            try:
                journal = json.loads(self._journal_path.read_text(encoding="utf-8"))
                if not isinstance(journal, dict):
                    raise RecoveryError("invalid real-system transaction journal")
                if journal.get("schema_version") == self._ADMISSION_JOURNAL_SCHEMA:
                    self._recover_admission_journal(journal)
                    return
                if journal.get("schema_version") != self._JOURNAL_SCHEMA:
                    raise RecoveryError("invalid real-system transaction journal")
                state_before_bytes = base64.b64decode(
                    journal["state_before_bytes_b64"], validate=True
                )
                state_bytes = base64.b64decode(journal["state_bytes_b64"], validate=True)
                event_line = base64.b64decode(journal["event_line_b64"], validate=True)
                ledger_before = base64.b64decode(journal["ledger_before_b64"], validate=True)
                notes_before = base64.b64decode(journal["notes_before_b64"], validate=True)
                note_line = base64.b64decode(journal["note_line_b64"], validate=True)
                state_before = V52RunState.model_validate_json(state_before_bytes)
                state = V52RunState.model_validate_json(state_bytes)
                event = RealSystemLedgerEvent.model_validate_json(event_line)
            except (KeyError, TypeError, ValueError, ValidationError, json.JSONDecodeError) as exc:
                raise RecoveryError("invalid real-system transaction journal") from exc
            if (
                canonical_json_bytes(state) != state_bytes
                or canonical_json_bytes(state_before) != state_before_bytes
                or canonical_json_bytes(event) + b"\n" != event_line
                or event.state_digest != state.digest
                or not event_line.endswith(b"\n")
            ):
                raise RecoveryError("real-system transaction journal binding is invalid")
            try:
                if not ledger_before or not ledger_before.endswith(b"\n"):
                    raise RecoveryError("real-system transaction journal prior ledger is invalid")
                prior_events: list[RealSystemLedgerEvent] = []
                previous = _GENESIS_DIGEST
                for sequence, line in enumerate(ledger_before.splitlines(), start=1):
                    prior_event = RealSystemLedgerEvent.model_validate_json(line)
                    if (
                        canonical_json_bytes(prior_event) != line
                        or prior_event.sequence != sequence
                        or prior_event.previous_digest != previous
                    ):
                        raise RecoveryError("real-system transaction journal prior ledger is invalid")
                    previous = prior_event.event_digest
                    prior_events.append(prior_event)
                if (
                    event.sequence != len(prior_events) + 1
                    or event.previous_digest != prior_events[-1].event_digest
                    or prior_events[-1].state_digest != state_before.digest
                    or state_before.run_id != self._run_id
                    or notes_before != self._runtime_notes_bytes(state_before)
                    or notes_before + note_line != self._runtime_notes_bytes(state)
                ):
                    raise RecoveryError("real-system transaction journal binding is invalid")
                self._validate_recovered_successor(state_before, state, event)
            except (ValidationError, ValueError, StoreError) as exc:
                raise RecoveryError("real-system transaction journal successor is invalid") from exc
            current_ledger = self._ledger_path.read_bytes() if self._ledger_path.exists() else b""
            current_notes = self._notes_path.read_bytes() if self._notes_path.exists() else b""
            if (
                current_ledger not in (ledger_before, ledger_before + event_line)
                and current_ledger.startswith(ledger_before)
                and event_line.startswith(current_ledger[len(ledger_before) :])
            ):
                TransactionalRunStore._atomic_write(self._ledger_path, ledger_before)
                current_ledger = ledger_before
            if (
                current_notes not in (notes_before, notes_before + note_line)
                and current_notes.startswith(notes_before)
                and note_line.startswith(current_notes[len(notes_before) :])
            ):
                TransactionalRunStore._atomic_write(self._notes_path, notes_before)
                current_notes = notes_before
            if current_ledger not in (ledger_before, ledger_before + event_line):
                raise RecoveryError("real-system ledger recovery bytes conflict")
            if current_notes not in (notes_before, notes_before + note_line):
                raise RecoveryError("runtime notes recovery bytes conflict")
            current_state_bytes = self._state_path.read_bytes() if self._state_path.exists() else b""
            if current_state_bytes not in (state_before_bytes, state_bytes):
                raise RecoveryError("real-system state recovery bytes conflict")
            if current_state_bytes == state_before_bytes and (
                current_ledger != ledger_before or current_notes != notes_before
            ):
                raise RecoveryError("real-system state recovery bytes conflict")
            if current_state_bytes != state_bytes:
                TransactionalRunStore._atomic_write(self._state_path, state_bytes)
            if current_ledger == ledger_before:
                TransactionalRunStore._append_bytes(self._ledger_path, event_line)
            if current_notes == notes_before and note_line:
                TransactionalRunStore._append_bytes(self._notes_path, note_line)
            TransactionalRunStore._remove_exact_file(self._journal_path)

    def _validate_recovered_successor(
        self,
        current: V52RunState,
        successor: V52RunState,
        event: RealSystemLedgerEvent,
    ) -> None:
        self._validate_successor(current, successor)
        deltas = {
            "exploration_delta_recorded": {"exploration_deltas": 1},
            "resource_lease_recorded": {"leases": 1},
            "external_operation_intended": {
                "budget_reservations": 1,
                "external_operation_intents": 1,
            },
            "manifest_budget_exhausted_blocked": {
                "manifest_budget_exhaustions": 1,
            },
            "external_operation_receipted": {
                "external_operation_receipts": 1,
                "node_completions": 0,
            },
            "real_node_completed": {"node_completions": 1},
            "real_system_decision_pending": {"pending_real_system_decisions": 1},
            "real_system_decision_consumed": {"real_system_decision_consumptions": 1},
            "runtime_note_recorded": {"runtime_notes": 1},
            "unsettled_operation_paused": {},
            "environment_snapshot_drift_paused": {},
            "cleanup_authorized": {"cleanup_decision_digests": 1},
        }
        expected = deltas.get(event.kind)
        if expected is None:
            raise StoreError("recovered transaction has invalid event kind")
        expected = dict(expected)
        if (
            event.kind == "external_operation_receipted"
            and successor.facts.external_operation_receipts[-1].status == "succeeded"
        ):
            expected["node_completions"] = 1
        fields = (
            "exploration_deltas",
            "leases",
            "budget_reservations",
            "external_operation_intents",
            "manifest_budget_exhaustions",
            "external_operation_receipts",
            "node_completions",
            "pending_real_system_decisions",
            "real_system_decision_consumptions",
            "runtime_notes",
            "cleanup_decision_digests",
        )
        if any(
            len(getattr(successor.facts, field_name))
            != len(getattr(current.facts, field_name)) + expected.get(field_name, 0)
            for field_name in fields
        ):
            raise StoreError("recovered transaction does not contain one exact fact transition")
        if event.kind == "exploration_delta_recorded":
            delta = successor.facts.exploration_deltas[-1]
            if event.fact_id != delta.node.node_id or event.fact_digest != delta.digest:
                raise StoreError("recovered exploration delta fact is invalid")
            self._validate_exploration_delta(current, delta)
        elif event.kind == "resource_lease_recorded":
            lease = successor.facts.leases[-1]
            manifest = self._validated_manifest(current)
            if (
                event.fact_id != lease.lease_id
                or event.fact_digest != digest_for("resource-lease", lease)
                or lease.run_id != current.run_id
                or (
                    lease.resource_kind in {"account", "namespace", "fixture"}
                    and lease.resource not in manifest.synthetic_scope.owned_resources
                )
                or any(item.resource == lease.resource for item in current.facts.leases)
            ):
                raise StoreError("recovered resource lease fact is invalid")
        elif event.kind == "external_operation_intended":
            reservation = successor.facts.budget_reservations[-1]
            intent = successor.facts.external_operation_intents[-1]
            manifest = self._validated_manifest(current)
            head = current.facts.run_head
            try:
                self._validate_intent_node_authority(current, intent)
                self._require_exact_persisted_operation_intent(current, intent)
            except StoreError as exc:
                raise StoreError("recovered external operation intent fact is invalid") from exc
            if (
                event.fact_id != intent.operation_id
                or event.fact_digest != intent.digest
                or intent.reserved_budget != reservation
                or intent.run_id != current.run_id
                or intent.manifest_digest != current.adapter_manifest_digest
                or head is None
                or intent.run_head_digest != head.digest
                or intent.effect
                not in {capability.effect for capability in manifest.capabilities}
                or any(
                    item.operation_id == intent.operation_id
                    or item.idempotency_key == intent.idempotency_key
                    for item in current.facts.external_operation_intents
                )
                or any(
                    item.reservation_id == reservation.reservation_id
                    for item in current.facts.budget_reservations
                )
            ):
                raise StoreError("recovered external operation intent fact is invalid")
            self._assert_budget_reservation(current, reservation)
        elif event.kind == "manifest_budget_exhausted_blocked":
            exhaustion = successor.facts.manifest_budget_exhaustions[-1]
            rejected_intent = exhaustion.rejected_intent
            try:
                self._validate_intent_node_authority(current, rejected_intent)
                self._require_exact_persisted_operation_intent(current, rejected_intent)
                self._assert_budget_reservation(
                    current, rejected_intent.reserved_budget
                )
            except BudgetReservationExceeded as exc:
                exhausted_budget_names = exc.exhausted_budget_names
            except StoreError as exc:
                raise StoreError("recovered manifest budget exhaustion fact is invalid") from exc
            else:
                raise StoreError("recovered manifest budget exhaustion fact is invalid")
            head = current.facts.run_head
            manifest = self._validated_manifest(current)
            if (
                event.fact_id != rejected_intent.operation_id
                or event.fact_digest != exhaustion.digest
                or current.mode != "running"
                or successor.mode != "blocked"
                or head is None
                or exhaustion.run_id != current.run_id
                or exhaustion.run_head_digest != head.digest
                or exhaustion.manifest_digest != current.adapter_manifest_digest
                or exhaustion.exhausted_budget_names != exhausted_budget_names
                or rejected_intent.effect
                not in {capability.effect for capability in manifest.capabilities}
                or any(
                    item.operation_id == rejected_intent.operation_id
                    or item.idempotency_key == rejected_intent.idempotency_key
                    for item in current.facts.external_operation_intents
                )
                or any(
                    item.reservation_id == rejected_intent.reserved_budget.reservation_id
                    for item in current.facts.budget_reservations
                )
                or current.facts.manifest_budget_exhaustions
            ):
                raise StoreError("recovered manifest budget exhaustion fact is invalid")
        elif event.kind == "external_operation_receipted":
            receipt = successor.facts.external_operation_receipts[-1]
            intents = tuple(
                item
                for item in current.facts.external_operation_intents
                if item.operation_id == receipt.operation_id
            )
            if len(intents) != 1:
                raise StoreError("recovered external operation receipt lacks exact prior intent")
            intent = intents[0]
            if (
                event.fact_id != receipt.receipt_id
                or event.fact_digest != receipt.digest
                or receipt.run_id != intent.run_id
                or receipt.manifest_digest != intent.manifest_digest
                or receipt.run_head_digest != intent.run_head_digest
                or receipt.idempotency_key != intent.idempotency_key
                or any(
                    item.operation_id == receipt.operation_id
                    or item.receipt_id == receipt.receipt_id
                    for item in current.facts.external_operation_receipts
                )
            ):
                raise StoreError("recovered external operation receipt fact is invalid")
            if receipt.status == "succeeded":
                completion = successor.facts.node_completions[-1]
                expected_completion = RealNodeCompletion(
                    run_id=current.run_id,
                    node_id=intent.node_id,
                    run_head_digest=intent.run_head_digest,
                    kind="external_receipt",
                    evidence_refs=receipt.evidence_refs,
                    operation_id=intent.operation_id,
                )
                if completion != expected_completion:
                    raise StoreError("recovered external node completion fact is invalid")
        elif event.kind == "real_node_completed":
            completion = successor.facts.node_completions[-1]
            head = current.facts.run_head
            node = self._authorized_node_for_id(current, completion.node_id)
            if (
                event.fact_id != completion.node_id
                or event.fact_digest != completion.digest
                or head is None
                or completion.run_id != current.run_id
                or completion.run_head_digest != head.digest
                or node is None
                or completion.kind != "verification"
                or node.action_kind != "verify_only"
                or any(
                    item.node_id == completion.node_id
                    for item in current.facts.node_completions
                )
            ):
                raise StoreError("recovered node completion fact is invalid")
            try:
                self._validate_verification_completion(current, completion, node)
            except StoreError as exc:
                raise StoreError("recovered node completion fact is invalid") from exc
        elif event.kind == "real_system_decision_pending":
            pending = successor.facts.pending_real_system_decisions[-1]
            if (
                event.fact_id != pending.decision_id
                or event.fact_digest != pending.digest
                or any(
                    item.decision_id == pending.decision_id or item.digest == pending.digest
                    for item in current.facts.pending_real_system_decisions
                )
                or any(
                    real_system_decision_target_key(item)
                    == real_system_decision_target_key(pending)
                    for item in current.facts.pending_real_system_decisions
                )
            ):
                raise StoreError("recovered pending real-system decision fact is invalid")
            try:
                validate_pending_real_system_decision_amendment(
                    current, self._validated_manifest(current), pending
                )
            except ValueError as exc:
                raise StoreError("recovered pending real-system decision fact is invalid") from exc
        elif event.kind == "real_system_decision_consumed":
            consumption = successor.facts.real_system_decision_consumptions[-1]
            pending = next(
                (
                    item
                    for item in current.facts.pending_real_system_decisions
                    if item.digest == consumption.pending_decision_digest
                ),
                None,
            )
            decision = consumption.decision
            if pending is not None:
                try:
                    validate_pending_real_system_decision_amendment(
                        current, self._validated_manifest(current), pending
                    )
                except ValueError as exc:
                    raise StoreError(
                        "recovered real-system decision consumption fact is invalid"
                    ) from exc
            if (
                pending is None
                or event.fact_id != pending.decision_id
                or event.fact_digest != consumption.digest
                or any(
                    item.pending_decision_digest == pending.digest
                    for item in current.facts.real_system_decision_consumptions
                )
                or decision.decision_id != pending.decision_id
                or decision.kind != pending.kind
                or decision.run_id != pending.run_id
                or decision.run_head_digest != pending.run_head_digest
                or decision.authority_digest != pending.authority_digest
                or decision.payload_digest != pending.payload_digest
            ):
                raise StoreError("recovered real-system decision consumption fact is invalid")
        elif event.kind == "runtime_note_recorded":
            note = successor.facts.runtime_notes[-1]
            lease = next(
                (item for item in current.facts.leases if item.lease_id == note.lease_id),
                None,
            )
            receipt_refs = {
                value.receipt_id for value in current.facts.external_operation_receipts
            } | {value.digest for value in current.facts.external_operation_receipts}
            if (
                event.fact_id != note.lease_id
                or event.fact_digest != note.digest
                or lease is None
                or lease.run_id != current.run_id
                or lease.resource != note.resource_ref
                or note.receipt_ref not in receipt_refs
            ):
                raise StoreError("recovered runtime note fact is invalid")
        elif event.kind == "cleanup_authorized":
            decision_digest = successor.facts.cleanup_decision_digests[-1]
            if event.fact_digest != decision_digest:
                raise StoreError("recovered cleanup decision fact is invalid")
        elif event.kind == "unsettled_operation_paused":
            successful_receipts = {
                receipt.operation_id
                for receipt in current.facts.external_operation_receipts
                if receipt.status == "succeeded"
            }
            unsettled = tuple(
                intent
                for intent in current.facts.external_operation_intents
                if intent.operation_id not in successful_receipts
            )
            if current.mode != "running" or successor.mode != "paused":
                raise StoreError("recovered pause transition is invalid")
            if (
                not unsettled
                or event.fact_id != unsettled[0].operation_id
                or event.fact_digest != unsettled[0].digest
            ):
                raise StoreError("recovered pause fact is invalid")
        elif event.kind == "environment_snapshot_drift_paused":
            expected = self._validated_snapshot(current)
            if (
                current.mode != "running"
                or successor.mode != "paused"
                or event.fact_id == expected.digest
                or event.fact_digest
                != digest_for(
                    "environment-snapshot-drift",
                    {"expected": expected.digest, "observed": event.fact_id},
                )
            ):
                raise StoreError("recovered environment snapshot drift pause is invalid")
        if (
            event.kind
            not in {
                "unsettled_operation_paused",
                "environment_snapshot_drift_paused",
                "manifest_budget_exhausted_blocked",
            }
            and successor.mode != current.mode
        ):
            raise StoreError("recovered fact transition changes run mode")

    def _recover_admission_journal(self, journal: dict[str, object]) -> None:
        from .adapters.manifest import AdapterManifest
        from .environment import EnvironmentPreflightError, EnvironmentSnapshot

        try:
            manifest_bytes = base64.b64decode(journal["manifest_bytes_b64"], validate=True)
            snapshot_bytes = base64.b64decode(journal["snapshot_bytes_b64"], validate=True)
            notes_bytes = base64.b64decode(journal["notes_bytes_b64"], validate=True)
            state_bytes = base64.b64decode(journal["state_bytes_b64"], validate=True)
            ledger_bytes = base64.b64decode(journal["ledger_bytes_b64"], validate=True)
            manifest = AdapterManifest.model_validate_json(manifest_bytes)
            snapshot = EnvironmentSnapshot.model_validate_json(snapshot_bytes)
            state = V52RunState.model_validate_json(state_bytes)
            event = RealSystemLedgerEvent.model_validate_json(ledger_bytes)
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            raise RecoveryError("invalid real-system admission journal") from exc
        head = state.facts.run_head
        baseline = state.facts.baseline_spine
        expected_facts = (
            RealSystemFactIndex(
                environment_snapshot_digest=snapshot.digest,
                run_head=head,
                provider_authority=state.facts.provider_authority,
                baseline_spine=baseline,
                supervisor_receipts=state.facts.supervisor_receipts,
                egress_receipt=state.facts.egress_receipt,
            )
            if head is not None and baseline is not None
            else None
        )
        try:
            expected_snapshot = EnvironmentSnapshot.from_admitted_authority(
                manifest=manifest,
                target_identity_digest=state.trajectory.execution_envelope.target_identity_digest,
                supervisor_receipts=state.facts.supervisor_receipts,
                egress_receipt=state.facts.egress_receipt,
            )
            expected_baseline = (
                None
                if head is None
                else BaselineSpineAuthority.from_nodes(
                    state,
                    head,
                    manifest,
                    snapshot,
                    () if baseline is None else baseline.nodes,
                    () if baseline is None else baseline.baseline_proposals,
                )
            )
        except (EnvironmentPreflightError, TypeError, ValueError, ValidationError) as exc:
            raise RecoveryError("real-system admission authority is invalid") from exc
        if (
            canonical_json_bytes(manifest) != manifest_bytes
            or canonical_json_bytes(snapshot) != snapshot_bytes
            or canonical_json_bytes(state) != state_bytes
            or canonical_json_bytes(event) + b"\n" != ledger_bytes
            or notes_bytes != self._runtime_notes_bytes(state)
            or state.run_id != self._run_id
            or head is None
            or state.facts != expected_facts
            or snapshot != expected_snapshot
            or baseline != expected_baseline
            or manifest.digest != state.adapter_manifest_digest
            or snapshot.digest != state.facts.environment_snapshot_digest
            or snapshot.adapter_manifest_digest != manifest.digest
            or snapshot.target_identity_digest
            != state.trajectory.execution_envelope.target_identity_digest
            or snapshot.evidence_policy_digest != manifest.evidence.redaction_policy_digest
            or event.sequence != 1
            or event.kind != "real_system_admitted"
            or event.previous_digest != _GENESIS_DIGEST
            or baseline is None
            or event.fact_id != baseline.digest
            or event.fact_digest != baseline.digest
            or event.state_digest != state.digest
        ):
            raise RecoveryError("real-system admission journal binding is invalid")
        expected = (
            (self._manifest_path, manifest_bytes),
            (self._snapshot_path, snapshot_bytes),
            (self._notes_path, notes_bytes),
            (self._state_path, state_bytes),
            (self._ledger_path, ledger_bytes),
        )
        for path, payload in expected:
            if path.exists() and path.read_bytes() != payload:
                raise RecoveryError("real-system admission recovery bytes conflict")
        for path, payload in expected:
            if not path.exists():
                TransactionalRunStore._atomic_write(path, payload)
        TransactionalRunStore._remove_exact_file(self._journal_path)

    def _note_line(self, note: RuntimeNote) -> bytes:
        payload = canonical_json_bytes(note)
        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError as exc:  # Defensive; canonical JSON is UTF-8.
            raise StoreError("runtime note projection must be UTF-8") from exc
        if re.search(
            r"(?i)(?:(?:token|secret|password|api[_-]?key)\s*[=:]"
            r"|(?:authorization\s*[=:]\s*)?bearer\s+\S+"
            r"|authorization\s*[=:]\s*\S+)",
            text,
        ):
            raise StoreError("runtime notes projection must be secret-free")
        return f"- {note.digest} {text}\n".encode("utf-8")

    def _require_run(self, run_id: str) -> None:
        if run_id != self._run_id:
            raise StoreError("real-system store capability does not own this run")

    @contextmanager
    def _lock(self) -> Iterator[None]:
        self._root.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + 5.0
        handle = self._lock_path.open("a+b")
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        acquired = False
        while not acquired:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except OSError:
                if time.monotonic() >= deadline:
                    handle.close()
                    raise StoreError("timed out waiting for real-system store lock")
                time.sleep(0.02)
        try:
            yield
        finally:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()
