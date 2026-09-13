"""Bounded V5 runtime progress, limits, stalls, and user authority."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from .canonical import digest_bytes, digest_for
from .causality import CausalCone
from .models import (
    AdmittedProviderAuthority,
    BaselineNodeProposal,
    ChangeClassificationArtifact,
    ConfirmedTrajectoryBinding,
    ConfirmedTrajectoryBundle,
    CausalLead,
    ConeIdentityBinding,
    DerivedSpine,
    FrozenDerivedSpine,
    EvidenceGap,
    FactIndex,
    IterationFact,
    LimitConsumption,
    PauseReport,
    PendingTrajectoryDecision,
    ProductWorkReceipt,
    ReplayConeClosure,
    ReplayReopen,
    RoleManifest,
    RunHead,
    ProofResult,
    ProofSpec,
    RepairAttempt,
    RunState,
    StallFingerprint,
    UserDecision,
    UserAuthorizationConsumption,
    VersionedLimits,
    WorkAuthorization,
    AcceptedNodeResult,
    LandmarkVerification,
    NodeProposal,
    Observation,
    DerivedBehavioralNode,
    EgressGateReceipt,
    ExplorationDelta,
    ExternalOperationIntent,
    ExternalOperationReceipt,
    TrajectoryPause,
    TrajectorySuccessor,
    SupervisorAuthorityReceipt,
    V52RunState,
)
from .proof import (
    FinalReplaySnapshot,
    RealFinalReplaySnapshot,
    ImportedRoleOutput,
    ProofLadder,
    ProofLadderError,
    consume_issuer_registered_output,
    final_replay_context_id,
    require_exact_issuer_output,
)
from .review import require_independent_decision
from .repair import FailedRepairEvidence, RepairError
from .store import (
    BudgetReservationExceeded,
    RealSystemRunStore,
    RecoveryError,
    StoreCapability,
    StoreError,
    TransactionalRunStore,
)
from .trajectory import (
    TrajectoryValidationError,
    operational_authority_projection,
    validate_confirmed_trajectory,
)


class RuntimeError(ValueError):
    """Runtime action would exceed authority, limits, or finite progress."""


@dataclass(frozen=True, slots=True)
class RuntimeProgress:
    state: RunState
    fact: IterationFact


@dataclass(frozen=True, slots=True)
class RuntimeStatus:
    mode: str
    trajectory_digest: str
    derived_spine_digest: str | None
    landmark_mapping_digest: str | None
    current_run_head_digest: str | None
    progress_fact_count: int
    pending_decision_digest: str | None
    current_node_id: str | None
    current_cone_id: str | None
    current_cone_digest: str | None
    graph_run_branch: str | None
    graph_run_worktree: str | None
    sealed_environment_digest: str | None
    open_defect_ids: tuple[str, ...]
    remaining_limits: tuple[LimitConsumption, ...]
    next_automatic_step: str


@dataclass(frozen=True, slots=True)
class RuntimeSliceResult:
    """Public-safe outcome of one bounded observable traversal slice."""

    state: RunState
    outcome: Literal[
        "node_changed",
        "observed_failure",
        "awaiting_cone_closure",
        "final_replay_required",
        "evidence_paused",
        "stopped",
    ]
    node_id: str | None
    summary: str
    stop_condition: str | None
    safe_retry: bool


@dataclass(frozen=True, slots=True)
class FinalReplayResult:
    state: RunState
    snapshot: FinalReplaySnapshot
    node_proofs: tuple[ProofResult, ...]
    reopened_cone: CausalCone | None = None
    proven_landmark_ids: tuple[str, ...] = ()
    terminal_outcome_proven: bool = False


@dataclass(frozen=True, slots=True)
class RealRuntimeSliceResult:
    """One persisted-authority V5.2 slice and any durable action receipt."""

    state: V52RunState
    receipt: ExternalOperationReceipt | None
    node_id: str


@dataclass(frozen=True, slots=True)
class ExplorationStatus:
    """Durable exploration context; not a public mode or policy transition."""

    node_id: str
    parent_node_id: str
    reason: str
    completed: bool


@dataclass(frozen=True, slots=True)
class RealRunStatusProjection:
    """Pure V5.2 status data for later public-command formatting."""

    mode: str
    recommended_baseline_node_id: str | None
    next_executable_node_id: str | None
    active_explorations: tuple[ExplorationStatus, ...]
    remaining_budget: tuple[tuple[str, int], ...]
    pending_decision_kind: str | None


@dataclass(frozen=True, slots=True)
class RealFinalReplayResult:
    """V5.2 replay projection bound to persisted environment authority."""

    state: V52RunState
    snapshot: RealFinalReplaySnapshot
    stop_reason: str | None = None

    @property
    def mode(self) -> str:
        return self.state.mode


@dataclass(frozen=True, slots=True)
class _IssuedWorkReceipt:
    authorization: WorkAuthorization
    receipt: ProductWorkReceipt


class _WorkReceiptIssuer:
    """In-memory issuer. Only this runtime instance may import its receipts."""

    def __init__(self) -> None:
        self._authorizations: dict[int, WorkAuthorization] = {}
        self._receipts: dict[str, _IssuedWorkReceipt] = {}

    def authorize(self, authorization: WorkAuthorization) -> WorkAuthorization:
        self._authorizations[id(authorization)] = authorization
        return authorization

    def issue(self, authorization: WorkAuthorization) -> ProductWorkReceipt:
        if self._authorizations.get(id(authorization)) is not authorization:
            raise RuntimeError("exact issued work authorization is required")
        receipt = ProductWorkReceipt(
            work_id=f"work-receipt:{authorization.authorization_id}",
            kind=authorization.kind,
            node_id=authorization.node_id,
            cone_id=authorization.cone_id,
            cone_digest=authorization.cone_digest,
            authorization_id=authorization.authorization_id,
            authorization_digest=authorization.digest,
            operation_id=authorization.operation_id,
            **authorization.expected_counters.model_dump(mode="python"),
        )
        self._receipts[receipt.work_id] = _IssuedWorkReceipt(authorization, receipt)
        return receipt

    def resolve(self, receipt_id: str, receipt_digest: str) -> _IssuedWorkReceipt:
        issued = self._receipts.get(receipt_id)
        if issued is None or issued.receipt.digest != receipt_digest:
            raise RuntimeError("issued product work receipt identity or digest is invalid")
        return issued


@dataclass(frozen=True, slots=True)
class _IssuedClassificationReceipt:
    manifest: RoleManifest
    artifact: ChangeClassificationArtifact


class _ClassificationReceiptIssuer:
    """Fresh reviewer receipts; shape-compatible caller JSON is never admitted."""

    def __init__(self) -> None:
        self._receipts: dict[str, _IssuedClassificationReceipt] = {}
        self._consumed_manifest_ids: set[str] = set()

    def issue(
        self, manifest: RoleManifest, artifact: ChangeClassificationArtifact
    ) -> ChangeClassificationArtifact:
        if manifest.manifest_id in self._consumed_manifest_ids:
            raise RuntimeError("fresh reviewer manifest is already consumed")
        self._receipts[artifact.artifact_id] = _IssuedClassificationReceipt(
            manifest, artifact
        )
        self._consumed_manifest_ids.add(manifest.manifest_id)
        return artifact

    def resolve(
        self, artifact_id: str, artifact_digest: str
    ) -> _IssuedClassificationReceipt:
        issued = self._receipts.get(artifact_id)
        if issued is None or issued.artifact.digest != artifact_digest:
            raise RuntimeError(
                "issued independent classification receipt identity or digest is invalid"
            )
        return issued


class _ReviewerManifestIssuer:
    """Fresh reviewer manifests exist only as issuer-registered identities."""

    def __init__(self) -> None:
        self._manifests: dict[str, RoleManifest] = {}

    def issue(self, manifest: RoleManifest) -> RoleManifest:
        if manifest.manifest_id in self._manifests:
            raise RuntimeError("fresh reviewer manifest authority is already issued")
        self._manifests[manifest.manifest_id] = manifest
        return manifest

    def resolve(self, manifest_id: str, manifest_digest: str) -> RoleManifest:
        manifest = self._manifests.get(manifest_id)
        if manifest is None or manifest.digest != manifest_digest:
            raise RuntimeError(
                "issued fresh reviewer manifest identity or digest is invalid"
            )
        return manifest


class RuntimeController:
    """Only mutation seam for V5 product-work and pause/decision transitions."""

    def __init__(self, store: TransactionalRunStore) -> None:
        self._store = store
        self._frozen_cache: FrozenDerivedSpine | None = None
        self._work_receipts = _WorkReceiptIssuer()
        self._reviewer_manifests = _ReviewerManifestIssuer()
        self._classification_receipts = _ClassificationReceiptIssuer()

    @classmethod
    def create(cls, *, root: str | Path, initial_state: RunState) -> "RuntimeController":
        """Removed write-first constructor. New runs require confirmed genesis."""

        del root, initial_state
        raise RuntimeError("RuntimeController.create is removed; use RuntimeController.start")

    @classmethod
    def open(cls, *, root: str | Path, run_id: str) -> "RuntimeController":
        state_path = Path(root) / "state.json"
        try:
            candidate = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            candidate = None
        if isinstance(candidate, dict) and candidate.get("schema_version") == "graph-v5.run-state.v2":
            return RealRuntimeController.open(root=root, run_id=run_id)  # type: ignore[return-value]
        capability = StoreCapability._issue_for_runtime(root, run_id)
        store = TransactionalRunStore.open(root, capability)
        if store.read_state().facts.trajectory_binding is None:
            raise StoreError("resume requires confirmed trajectory binding")
        return cls(store)

    @classmethod
    def start(
        cls,
        *,
        root: str | Path,
        confirmed: ConfirmedTrajectoryBundle,
        limits: VersionedLimits,
        request: object,
    ) -> tuple["RuntimeController", object]:
        """Validate confirmation before first durable run-store write."""

        from .environment import StartRequest, start_new_run

        if not isinstance(confirmed, ConfirmedTrajectoryBundle):
            raise TrajectoryValidationError("start requires a ConfirmedTrajectoryBundle")
        validated = validate_confirmed_trajectory(
            confirmed.brief,
            confirmed.markdown_utf8,
            confirmed.confirmation,
        )
        if not isinstance(limits, VersionedLimits):
            raise RuntimeError("start requires strict VersionedLimits")
        if not isinstance(request, StartRequest):
            raise RuntimeError("start requires a strict crash-safe StartRequest")
        state = RunState(
            schema_version="v5",
            run_id=validated.brief.run_id,
            mode="boot",
            trajectory=validated.brief,
            facts=FactIndex(),
            limits=limits,
        )
        store = TransactionalRunStore.open_for_confirmed_genesis(root, state.run_id)
        store.initialize_confirmed_run(state, confirmed=validated)
        controller = cls(store)
        return controller, start_new_run(request, controller._store)

    @classmethod
    def read_only_status(cls, *, root: str | Path, run_id: str) -> RuntimeStatus:
        """Project one explicit run without recovery, locks, or filesystem writes."""

        store = TransactionalRunStore.open_readonly(root, run_id)
        state = store.read_state_readonly()
        if state.facts.trajectory_binding is None:
            raise StoreError("status requires confirmed trajectory binding")
        return cls._project_status(state)

    @property
    def state(self) -> RunState:
        return self._store.read_state()

    def status(self) -> RuntimeStatus:
        """Pure read-only state summary; status does not create product work."""

        return self._project_status(self.state)

    def freeze_derived_spine(self, *, adapter: object | None = None) -> FrozenDerivedSpine:
        """Persist one complete, append-only replay authority snapshot."""

        current = self.state
        if self._open_replay_reopens(current.facts):
            raise RuntimeError("cannot freeze Derived Spine with open replay reopen")
        spine = current.facts.derived_spine
        if spine is None:
            raise RuntimeError("cannot freeze missing Derived Spine")
        run_head = current.facts.run_head
        environment = current.facts.environment
        if run_head is None or environment is None:
            raise RuntimeError("cannot freeze Derived Spine without sealed Run Head and environment")
        event_count = len(self._store.read_events())
        existing = next(
            (
                candidate
                for candidate in reversed(current.facts.frozen_derived_spines)
                if candidate.derived_spine_digest == spine.digest
                and candidate.trajectory_digest == current.trajectory_digest
                and candidate.landmark_mapping_digest == spine.landmark_mapping_digest
                and candidate.landmark_order == spine.landmark_order
                and candidate.frontier == spine.frontier
                and candidate.nodes == spine.nodes
                and candidate.results == spine.results
                and candidate.run_head == run_head
                and candidate.environment == environment
                and candidate.fixture_digest == current.fixture_intent_digest
                and candidate.graph_revision == event_count
            ),
            None,
        )
        if existing is not None:
            self._frozen_cache = existing
            return existing
        fixture_id: str | None = None
        fixture_adapter_id: str | None = None
        if current.facts.frozen_derived_spines:
            prior_freeze = current.facts.frozen_derived_spines[-1]
            fixture_id = prior_freeze.fixture_id
            fixture_adapter_id = prior_freeze.fixture_adapter_id
        if adapter is not None:
            from .adapters.user_journey import FixtureSnapshot

            try:
                fixture_snapshot = adapter.fixture_snapshot()  # type: ignore[attr-defined]
            except (AttributeError, TypeError, ValueError) as error:
                raise RuntimeError("freeze requires sealed fixture snapshot identity") from error
            if (
                not isinstance(fixture_snapshot, FixtureSnapshot)
                or not fixture_snapshot.sealed
                or fixture_snapshot.snapshot_digest != current.fixture_intent_digest
                or fixture_snapshot.snapshot_digest != run_head.fixture_digest
            ):
                raise RuntimeError("freeze requires sealed fixture snapshot identity")
            if (
                fixture_id is not None
                and (
                    fixture_snapshot.fixture_id != fixture_id
                    or fixture_snapshot.adapter_id != fixture_adapter_id
                )
            ):
                raise RuntimeError("freeze fixture identity differs from prior frozen authority")
            fixture_id = fixture_snapshot.fixture_id
            fixture_adapter_id = fixture_snapshot.adapter_id
        if fixture_id is None or fixture_adapter_id is None:
            raise RuntimeError("first Derived Spine freeze requires fixture adapter identity")
        try:
            spine.bind_trajectory(current.trajectory)
            frozen = FrozenDerivedSpine.from_spine(
                spine,
                run_head=run_head,
                environment=environment,
                fixture_digest=current.fixture_intent_digest,
                fixture_id=fixture_id,
                fixture_adapter_id=fixture_adapter_id,
                # Freeze event is next durable graph/ledger record.
                graph_revision=event_count + 1,
            )
        except ValueError as error:
            raise RuntimeError("cannot freeze incomplete or invalid Derived Spine") from error
        # Content-addressed store makes repeated freezes idempotent while an
        # extension naturally receives a distinct digest. No prior artifact
        # bytes are replaced.
        self._store.record_derived_spine_frozen(frozen)
        self._frozen_cache = frozen
        return frozen

    def _load_frozen_derived_spine(self, current: RunState) -> FrozenDerivedSpine:
        spine = current.facts.derived_spine
        if spine is None:
            raise RuntimeError("final replay requires persisted Derived Spine")
        run_head = current.facts.run_head
        environment = current.facts.environment
        if run_head is None or environment is None:
            raise RuntimeError("final replay requires sealed Run Head and environment")
        frozen = next(
            (
                candidate
                for candidate in reversed(current.facts.frozen_derived_spines)
                if candidate.derived_spine_digest == spine.digest
            ),
            None,
        )
        if frozen is None:
            raise RuntimeError("final replay requires persisted frozen Derived Spine")
        self._frozen_cache = frozen
        if (
            frozen.run_id != spine.run_id
            or frozen.trajectory_digest != current.trajectory_digest
            or frozen.derived_spine_digest != spine.digest
            or frozen.landmark_mapping_digest != spine.landmark_mapping_digest
            or frozen.landmark_order != spine.landmark_order
            or frozen.frontier != spine.frontier
            or frozen.nodes != spine.nodes
            or frozen.landmark_mapping != spine.landmark_mapping
            or frozen.results != spine.results
            or frozen.run_head != run_head
            or frozen.environment != environment
            or frozen.fixture_digest != current.fixture_intent_digest
            or frozen.graph_revision != len(self._store.read_events())
        ):
            raise RuntimeError("frozen replay authority drift or substitution")
        return frozen

    @staticmethod
    def _project_status(state: RunState) -> RuntimeStatus:
        """Render durable facts only; no observation, limit, or artifact mutation."""

        run_head = state.facts.run_head
        run_head_digest = run_head.digest if run_head is not None else None
        spine = state.facts.derived_spine
        current_node_id = spine.frontier.unexecuted_node_id if spine is not None else None
        target_landmark_id = spine.frontier.target_landmark_id if spine is not None else (
            state.trajectory.landmarks[0].landmark_id if state.trajectory.landmarks else None
        )
        pending_trajectory = state.pending_trajectory_decision
        if state.pending_decision is not None:
            current_node_id = state.pending_decision.cone_id.removeprefix("spine:")
        bindings = tuple(
            binding
            for binding in state.facts.cone_identity_bindings
            if binding.run_id == state.run_id
            and binding.node_id == current_node_id
        )
        current_cone_id = bindings[0].cone_id if len(bindings) == 1 else None
        persisted_cone_digest = next(
            (
                fact.cone_digest
                for fact in reversed(state.facts.iteration_facts)
                if fact.node_id == current_node_id
                and fact.cone_id == current_cone_id
                and (run_head_digest is None or fact.run_head_digest == run_head_digest)
            ),
            None,
        )
        current_cone_digest = (
            persisted_cone_digest
            if persisted_cone_digest is not None
            else CausalCone(cone_id=current_cone_id, node_id=current_node_id).digest
            if current_cone_id is not None and current_node_id is not None
            else None
        )
        open_defect_ids = tuple(
            lead.lead_id
            for lead in state.facts.leads
            if lead.disposition in {"open", "supported_cause", "supported_symptom"}
        )
        transaction = state.facts.git_transaction
        if pending_trajectory is not None:
            next_step = "Await digest-bound trajectory decision."
        elif state.trajectory_pause is not None:
            next_step = "Await smallest safe evidence input for persisted frontier."
        elif state.pending_decision is not None:
            next_step = "Await digest-bound user decision."
        elif state.mode in {"succeeded", "inconclusive", "blocked", "failed", "cancelled"}:
            next_step = "No automatic step: run is terminal."
        elif open_defect_ids:
            next_step = "Close current local Causal Cone before repair."
        elif target_landmark_id is not None:
            next_step = f"Derive next Behavioral Node toward landmark {target_landmark_id}."
        else:
            next_step = "Run sealed final replay with independent semantic review."
        return RuntimeStatus(
            mode=state.mode,
            trajectory_digest=state.trajectory_digest,
            derived_spine_digest=spine.digest if spine is not None else None,
            landmark_mapping_digest=(
                spine.landmark_mapping_digest if spine is not None else None
            ),
            current_run_head_digest=run_head_digest,
            progress_fact_count=len(state.facts.iteration_facts),
            pending_decision_digest=(
                pending_trajectory.digest
                if pending_trajectory is not None
                else state.pending_decision.digest if state.pending_decision is not None else None
            ),
            current_node_id=current_node_id,
            current_cone_id=current_cone_id,
            current_cone_digest=current_cone_digest,
            graph_run_branch=transaction.branch if transaction is not None else None,
            graph_run_worktree=transaction.worktree_path if transaction is not None else None,
            sealed_environment_digest=(
                state.facts.environment.digest if state.facts.environment is not None else None
            ),
            open_defect_ids=open_defect_ids,
            remaining_limits=RuntimeController._remaining_limits(state, current_cone_id),
            next_automatic_step=next_step,
        )

    @staticmethod
    def _remaining_limits(
        state: RunState, current_cone_id: str | None
    ) -> tuple[LimitConsumption, ...]:
        """Project conservative remaining counters from durable product-work facts."""

        receipts = state.facts.product_work
        cone_receipts = tuple(
            receipt for receipt in receipts if receipt.cone_id == current_cone_id
        )
        iterations = tuple(
            fact for fact in state.facts.iteration_facts if fact.cone_id == current_cone_id
        )

        def total(values: tuple[ProductWorkReceipt, ...], field: str) -> int:
            return sum(getattr(value, field) for value in values)

        consumed = {
            "causal_radius": max((item.causal_radius for item in cone_receipts), default=0),
            "failed_repair_cycles": sum(
                item.cone_id == current_cone_id for item in state.facts.repairs
            ),
            "diagnostic_widening": total(cone_receipts, "widening_allowance"),
            "reasoning_escalation": max((item.reasoning_tier for item in iterations), default=0),
            "discovery_commands": sum(
                item.command_count for item in cone_receipts if item.kind == "discovery"
            ),
            "discovery_duration": sum(
                item.completed_duration_ms for item in cone_receipts if item.kind == "discovery"
            ),
            "repair_attempts": total(cone_receipts, "repair_attempts"),
            "repair_commands": sum(
                item.command_count for item in cone_receipts if item.kind == "repair"
            ),
            "repair_duration": sum(
                item.completed_duration_ms for item in cone_receipts if item.kind == "repair"
            ),
            "artifact_output_per_command": max(
                (output for item in receipts for output in item.command_output_bytes), default=0
            ),
            "artifact_output_per_run": total(receipts, "output_bytes"),
            "agent_dispatches_per_cone": total(cone_receipts, "agent_dispatches"),
            "agent_dispatches_per_run": total(receipts, "agent_dispatches"),
            "model_calls_per_cone": total(cone_receipts, "model_calls"),
            "model_calls_per_run": total(receipts, "model_calls"),
            "model_reasoning_tokens_per_cone": total(cone_receipts, "reasoning_tokens"),
            "model_reasoning_tokens_per_run": total(receipts, "reasoning_tokens"),
            "model_reasoning_cost_per_cone": total(cone_receipts, "normalized_provider_cost"),
            "model_reasoning_cost_per_run": total(receipts, "normalized_provider_cost"),
            "global_work_commands": total(receipts, "command_count"),
            "global_work_duration": state.facts.completed_duration_ms,
        }
        return tuple(
            LimitConsumption(
                limit_name=value.name,
                consumed=max(value.amount - consumed[value.name], 0),
            )
            for value in state.limits.active.values
        )

    def run_bounded_slice(
        self, *, adapter: object, deriver: object, max_nodes: int = 1
    ) -> RuntimeSliceResult:
        """Derive, seal, and execute at most one evidence-supported frontier node."""

        if type(max_nodes) is not int or max_nodes != 1:
            raise RuntimeError("run slice derives exactly one frontier node")
        current = self.state
        if current.mode == "paused":
            if current.trajectory_pause is not None and current.pending_trajectory_decision is None:
                current = self._resume_trajectory_pause(current)
            else:
                return RuntimeSliceResult(
                    state=current,
                    outcome="stopped",
                    node_id=None,
                    summary="Run is paused; explicit authority decision is required.",
                    stop_condition="paused",
                    safe_retry=False,
                )
        if current.mode in {"succeeded", "inconclusive", "blocked", "failed", "cancelled"}:
            return RuntimeSliceResult(
                state=current,
                outcome="stopped",
                node_id=None,
                summary=f"Run is {current.mode}; no autonomous traversal occurs.",
                stop_condition=current.mode,
                safe_retry=current.mode == "paused",
            )
        self._require_active(current)
        run_head = current.facts.run_head
        if run_head is None:
            raise RuntimeError("run slice requires a sealed Run Head")
        if any(lead.disposition == "open" for lead in current.facts.leads):
            return RuntimeSliceResult(
                state=current,
                outcome="awaiting_cone_closure",
                node_id=self._project_status(current).current_node_id,
                summary="Observed failure awaits bounded local Causal Cone closure.",
                stop_condition="Open causal lead blocks repair and further traversal.",
                safe_retry=False,
            )

        current, spine = self._ensure_persisted_spine(current)
        extension_spine = spine
        if spine.frontier.target_landmark_id is None:
            # A complete spine may reopen only at a durable replay regression.
            # Derivation then sees a transient final-landmark repair frontier;
            # the persisted spine remains append-only and old freezes remain.
            if self._replay_repair_ready(current):
                try:
                    extension_spine = spine.for_repair_extension()
                except ValueError as error:
                    raise RuntimeError("replay repair requires complete Derived Spine") from error
            else:
                if self._open_replay_reopens(current.facts):
                    raise RuntimeError(
                        "replay repair requires exact closure and fresh current-head proof"
                    )
                return RuntimeSliceResult(
                    state=current,
                    outcome="final_replay_required",
                    node_id=None,
                    summary="Persisted Derived Spine proves every confirmed landmark.",
                    stop_condition="Final replay freeze and replay belong to Task 7.",
                    safe_retry=True,
                )
        if spine.frontier.unexecuted_node_id is not None:
            return self._execute_sealed_frontier(current, spine, adapter, run_head)

        try:
            entry = adapter.observe_readonly(  # type: ignore[attr-defined]
                anchor_id=self._frontier_anchor(extension_spine), run_head_digest=run_head.digest
            )
        except (AttributeError, ValueError) as error:
            raise RuntimeError("run slice fixture observation failed") from error
        if not isinstance(entry, Observation):
            raise RuntimeError("adapter observation must be a strict immutable Observation")
        current = self._record_runtime_observation(current, entry)

        try:
            proposal = deriver.derive_next(current.trajectory, extension_spine, entry)  # type: ignore[attr-defined]
        except AttributeError as error:
            raise RuntimeError("run slice requires a NodeDeriver") from error
        if isinstance(proposal, EvidenceGap):
            return self._pause_for_evidence_gap(current, extension_spine, entry, proposal)
        if not isinstance(proposal, (NodeProposal, LandmarkVerification)):
            raise RuntimeError("NodeDeriver returned unsupported next-node result")
        self._require_operational_node_authority(current, proposal)

        from .spine import ObservableSpine, TraversalError

        try:
            sealed = ObservableSpine(
                current.trajectory,
                extension_spine,
                current_run_head=run_head,
                accepted_observations=current.facts.observations,
            ).seal_next(entry_observation=entry, proposal=proposal)
        except (TraversalError, ValueError) as error:
            raise RuntimeError("next node is not supported by current frontier evidence") from error
        sealed_spine = extension_spine.with_node(sealed)
        sealed_state = self._with_facts(
            current,
            current.facts.model_copy(update={"derived_spine": sealed_spine}),
        )
        self._store.record_derived_spine(sealed_spine, sealed_state)

        return self._execute_sealed_frontier(
            sealed_state,
            sealed_spine,
            adapter,
            run_head,
        )

    def _execute_sealed_frontier(
        self,
        current: RunState,
        spine: DerivedSpine,
        adapter: object,
        run_head: RunHead,
    ) -> RuntimeSliceResult:
        """Execute exactly one already-durable frontier intent, including restart retry."""

        if spine.frontier.unexecuted_node_id is None or not spine.nodes:
            raise RuntimeError("sealed frontier execution requires one unexecuted node")
        sealed = spine.nodes[-1]

        if sealed.action_kind == "verify_only":
            observation_refs = sealed.entry_observation_refs
            satisfied = True
            proof_ref = sealed.current_run_head_proof_ref
            result_state = current
        else:
            try:
                if not adapter.fixture_is_active():  # type: ignore[attr-defined]
                    snapshot = adapter.fixture_snapshot()  # type: ignore[attr-defined]
                    adapter.reset_fixture(snapshot)  # type: ignore[attr-defined]
                receipt = adapter.act(sealed, run_head_digest=run_head.digest)  # type: ignore[attr-defined]
            except (AttributeError, ValueError) as error:
                raise RuntimeError("sealed node execution failed") from error
            observation_refs = tuple(receipt.evidence_refs)
            result_observation = Observation(
                observation_id=f"node-result:{sealed.node_id}:{len(current.facts.observations)}",
                node_id=sealed.node_id,
                kind="behavioral",
                observed_state=receipt.observed_state,
                evidence_refs=observation_refs,
                run_head_digest=run_head.digest,
            )
            result_state = self._record_runtime_observation(current, result_observation)
            landmark = next(
                item
                for item in result_state.trajectory.landmarks
                if item.landmark_id == sealed.target_landmark_id
            )
            satisfied = receipt.observed_state in {
                landmark.description,
                *landmark.acceptance,
            }
            proof_ref = observation_refs[0] if satisfied else None

        accepted = AcceptedNodeResult.create(
            node=sealed,
            observation_refs=observation_refs,
            run_head_digest=run_head.digest,
            landmark_satisfied=satisfied,
            current_run_head_proof_ref=proof_ref,
        )
        completed_spine = spine.with_accepted_result(accepted)
        completed_state = self._with_facts(
            result_state,
            result_state.facts.model_copy(update={"derived_spine": completed_spine}),
        )
        self._store.record_derived_spine_result(completed_spine, completed_state)
        return RuntimeSliceResult(
            state=completed_state,
            outcome="node_changed",
            node_id=sealed.node_id,
            summary=f"Sealed and recorded one frontier node toward {sealed.target_landmark_id}.",
            stop_condition=None,
            safe_retry=True,
        )

    def _ensure_persisted_spine(self, current: RunState) -> tuple[RunState, DerivedSpine]:
        spine = current.facts.derived_spine
        if spine is not None:
            spine.bind_trajectory(current.trajectory)
            return current, spine
        spine = DerivedSpine(
            schema_version="graph-v5.derived-spine.v1",
            run_id=current.run_id,
            trajectory_digest=current.trajectory_digest,
            landmark_order=tuple(item.landmark_id for item in current.trajectory.landmarks),
            frontier={"last_reached_landmark_id": None, "target_landmark_id": current.trajectory.landmarks[0].landmark_id},
        )
        successor = self._with_facts(
            current,
            current.facts.model_copy(update={"derived_spine": spine}),
        )
        self._store.record_initial_derived_spine(spine, successor)
        return successor, spine

    @staticmethod
    def _frontier_anchor(spine: DerivedSpine) -> str:
        if not spine.nodes:
            return "START"
        last_node = spine.nodes[-1]
        last_result = spine.results[-1] if spine.results else None
        return (
            last_node.target_landmark_id
            if last_result is not None and last_result.landmark_satisfied
            else last_node.node_id
        )

    def _record_runtime_observation(self, current: RunState, observation: Observation) -> RunState:
        successor = self._with_facts(
            current,
            current.facts.model_copy(
                update={"observations": current.facts.observations + (observation,)}
            ),
        )
        self._store.record_observation(observation, successor)
        return successor

    def _resume_trajectory_pause(self, current: RunState) -> RunState:
        pause = current.trajectory_pause
        if pause is None or current.pending_trajectory_decision is not None:
            raise RuntimeError("evidence pause resume requires no pending authority decision")
        successor = current.with_mode("running")
        self._store.record_trajectory_pause_resumed(pause, successor)
        return successor

    def _pause_for_evidence_gap(
        self, current: RunState, spine: DerivedSpine, entry: Observation, gap: EvidenceGap
    ) -> RuntimeSliceResult:
        if gap.target_landmark_id != spine.frontier.target_landmark_id:
            raise RuntimeError("EvidenceGap must name current persisted target landmark")
        pause = TrajectoryPause(
            reason="insufficient_next_node_evidence",
            trajectory_digest=current.trajectory_digest,
            frontier_digest=spine.digest,
            frontier_anchor_id=self._frontier_anchor(spine),
            target_landmark_id=gap.target_landmark_id,
            observation_refs=tuple(
                dict.fromkeys(
                    reference
                    for observation in current.facts.observations
                    for reference in observation.evidence_refs
                )
            ),
            evidence_gap=gap.evidence_gap,
            smallest_needed_input=gap.smallest_needed_input,
            exhausted_safe_probe_refs=gap.exhausted_safe_probes,
        )
        facts = current.facts.model_copy(
            update={"trajectory_pauses": current.facts.trajectory_pauses + (pause,)}
        )
        successor = self._with_facts(current.with_mode("paused"), facts)
        self._store.record_trajectory_pause(pause, successor)
        return RuntimeSliceResult(
            state=successor,
            outcome="evidence_paused",
            node_id=None,
            summary="Paused: insufficient_next_node_evidence.",
            stop_condition="Current evidence cannot justify a sealed action.",
            safe_retry=True,
        )

    def request_trajectory_decision(
        self,
        *,
        proposed_departure: str,
        impact: str,
        alternatives: tuple[str, ...],
        evidence_refs: tuple[str, ...],
        question: str | None = None,
    ) -> RunState:
        """Pause only for a material authority departure; ordinary repair stays autonomous."""

        current = self.state
        if current.mode != "running":
            raise RuntimeError("trajectory decision requires active running traversal")
        current, spine = self._ensure_persisted_spine(current)
        normalized = f"{proposed_departure} {impact}".casefold()
        autonomous = ("node split", "variant", "causal cone", "conformance repair")
        material = (
            "goal", "outcome", "landmark", "actor", "fixture", "behavior",
            "scope", "forbidden", "side effect", "non-goal", "non goal",
            "external", "persistent", "financial", "payment", "billing", "privacy",
        )
        is_material = any(term in normalized for term in material)
        if not is_material and any(term in normalized for term in autonomous):
            raise RuntimeError("ordinary node variants and in-envelope conformance repair stay autonomous")
        if not is_material:
            raise RuntimeError("trajectory decision requires a material authority departure")
        decision = PendingTrajectoryDecision(
            decision_id=(
                f"trajectory-decision:{current.run_id}:"
                f"{len(current.facts.pending_trajectory_decisions) + 1}"
            ),
            run_id=current.run_id,
            trajectory_digest=current.trajectory_digest,
            frontier_digest=spine.digest,
            evidence_refs=evidence_refs,
            proposed_departure=proposed_departure,
            impact=impact,
            alternatives=alternatives,
            question=question or "Approve a new confirmed successor trajectory or keep current authority?",
        )
        facts = current.facts.model_copy(
            update={
                "pending_trajectory_decisions": (
                    current.facts.pending_trajectory_decisions + (decision,)
                )
            }
        )
        successor = self._with_facts(current.with_mode("paused"), facts)
        self._store.record_pending_trajectory_decision(decision, successor)
        return successor

    def approve_trajectory_decision(
        self,
        *,
        decision_id: str,
        confirmed_successor: ConfirmedTrajectoryBundle,
    ) -> RunState:
        """Append a confirmed successor authority without rewriting predecessor bytes."""

        current = self.state
        decision = next(
            (
                item
                for item in current.facts.pending_trajectory_decisions
                if item.decision_id == decision_id
            ),
            None,
        )
        if decision is None:
            raise RuntimeError("unknown pending trajectory decision")
        if any(
            link.decision_digest == decision.digest
            for link in current.facts.trajectory_successors
        ):
            raise RuntimeError("trajectory decision already has a confirmed successor")
        if current.mode != "paused":
            raise RuntimeError("trajectory successor requires a paused material decision")
        validated = validate_confirmed_trajectory(
            confirmed_successor.brief,
            confirmed_successor.markdown_utf8,
            confirmed_successor.confirmation,
        )
        if (
            validated.brief.run_id != current.run_id
            or decision.trajectory_digest != current.trajectory_digest
            or validated.brief.digest == current.trajectory_digest
        ):
            raise RuntimeError("confirmed successor must be a distinct authority for current decision")
        successor_spine = DerivedSpine(
            schema_version="graph-v5.derived-spine.v1",
            run_id=current.run_id,
            trajectory_digest=validated.brief.digest,
            landmark_order=tuple(
                landmark.landmark_id for landmark in validated.brief.landmarks
            ),
            frontier={
                "last_reached_landmark_id": None,
                "target_landmark_id": validated.brief.landmarks[0].landmark_id,
            },
        )
        binding = ConfirmedTrajectoryBinding(
            run_id=current.run_id,
            trajectory_digest=validated.brief.digest,
            markdown_digest=digest_bytes(
                "trajectory-markdown", validated.markdown_utf8
            ),
            confirmation_digest=digest_for(
                "trajectory-confirmation", validated.confirmation
            ),
        )
        link = TrajectorySuccessor(
            decision_digest=decision.digest,
            predecessor_trajectory_digest=current.trajectory_digest,
            successor_trajectory_digest=validated.brief.digest,
            successor_markdown_digest=binding.markdown_digest,
            successor_confirmation_digest=binding.confirmation_digest,
            successor_spine_digest=successor_spine.digest,
        )
        facts = current.facts.model_copy(
            update={
                "trajectory_successors": current.facts.trajectory_successors + (link,),
                "trajectory_binding": binding,
                "derived_spine": successor_spine,
            }
        )
        successor = RunState.model_validate(
            {
                **current.model_dump(),
                "trajectory": validated.brief,
                "facts": facts,
                "mode": "running",
            }
        )
        self._store.record_trajectory_successor(
            link,
            successor,
            confirmed=validated,
        )
        return successor

    @staticmethod
    def _require_operational_node_authority(current: RunState, proposal: NodeProposal) -> None:
        operational = operational_authority_projection(current.trajectory)
        forbidden = ("author-signal", "author_signal", "test_philosophy", "run_rationale", "philosophy", "rationale")
        if not operational or any(
            any(term in reference.casefold() for term in forbidden)
            for reference in proposal.authority_refs
        ):
            raise RuntimeError("Author Signals, philosophy, and rationale cannot authorize a node")

    @staticmethod
    def _authority_digests(current: RunState) -> tuple[str, str, str]:
        spine = current.facts.derived_spine
        if spine is None:
            raise RuntimeError("operational authority requires persisted Derived Spine")
        spine.bind_trajectory(current.trajectory)
        return current.trajectory_digest, spine.digest, spine.landmark_mapping_digest

    def _record_verified_node(self, current: RunState, outcome: object) -> RuntimeSliceResult:
        from .spine import NodeVerified

        if not isinstance(outcome, NodeVerified):
            raise RuntimeError("only NodeVerified may advance observable progress")
        run_head = current.facts.run_head
        if run_head is None:
            raise RuntimeError("verified node requires current Run Head")
        cone = CausalCone(cone_id=f"spine:{outcome.node_id}", node_id=outcome.node_id)
        facts = FactIndex.model_validate(
            {
                **current.facts.model_dump(),
                "observations": current.facts.observations + outcome.observations,
            }
        )
        fact = IterationFact(
            fact_id=f"verified-node:{run_head.digest[:16]}:{outcome.node_id}",
            fact_class="verified_node",
            node_id=outcome.node_id,
            run_head_digest=run_head.digest,
            subject_id=outcome.snapshot_digest,
            cone_id=cone.cone_id,
            cone_digest=cone.digest,
        )
        facts = self._append_iteration_fact(current, facts, fact)
        successor = self._with_facts(current, facts)
        self._store.record_runtime_iteration(fact, successor)
        return RuntimeSliceResult(
            state=successor,
            outcome="node_changed",
            node_id=outcome.node_id,
            summary=f"Verified Behavioral Node {outcome.node_id} on current Run Head.",
            stop_condition="Behavioral Node changed.",
            safe_retry=True,
        )

    def _record_observed_failure(
        self, current: RunState, outcome: object
    ) -> RuntimeSliceResult:
        from .spine import ObservedFailure

        if not isinstance(outcome, ObservedFailure):
            raise RuntimeError("only ObservedFailure may open a causal lead")
        run_head = current.facts.run_head
        if run_head is None or not outcome.observations:
            raise RuntimeError("observed failure requires evidence and current Run Head")
        cone = CausalCone(cone_id=f"spine:{outcome.node_id}", node_id=outcome.node_id)
        source = outcome.observations[-1]
        if self._observation_uses_author_signal(current, source):
            raise RuntimeError(
                "Author Signals cannot open causal leads without independent observation"
            )
        lead = CausalLead(
            lead_id=f"observed-failure:{run_head.digest[:16]}:{outcome.node_id}:{outcome.failure_code}",
            source_observation_id=source.observation_id,
            subject=outcome.failure_code,
            disposition="open",
            evidence_refs=source.evidence_refs,
        )
        facts = FactIndex.model_validate(
            {
                **current.facts.model_dump(),
                "observations": current.facts.observations + outcome.observations,
                "leads": current.facts.leads + (lead,),
            }
        )
        fact = IterationFact(
            fact_id=f"new-hop:{lead.lead_id}",
            fact_class="new_hop",
            node_id=outcome.node_id,
            run_head_digest=run_head.digest,
            subject_id=lead.lead_id,
            cone_id=cone.cone_id,
            cone_digest=cone.digest,
        )
        facts = self._append_iteration_fact(current, facts, fact)
        successor = self._with_facts(current, facts)
        self._store.record_runtime_iteration(fact, successor)
        return RuntimeSliceResult(
            state=successor,
            outcome="observed_failure",
            node_id=outcome.node_id,
            summary=f"Observed failure at Behavioral Node {outcome.node_id}.",
            stop_condition="Local Causal Cone closure is required before repair.",
            safe_retry=False,
        )

    @staticmethod
    def _observation_uses_author_signal(
        current: RunState,
        observation: Observation,
    ) -> bool:
        signal_tokens: set[str] = set()
        for signal in current.trajectory.author_signals:
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

    def record_iteration(self, fact: IterationFact) -> RunState:
        current = self.state
        self._require_active(current)
        facts = self._append_iteration_fact(current, current.facts, fact)
        successor = self._with_facts(current, facts)
        self._store.record_runtime_iteration(fact, successor)
        return successor

    def close_replay_reopened_cone(
        self,
        *,
        cone: CausalCone,
        proof_spec: ProofSpec,
        proof_result: ProofResult,
    ) -> RunState:
        """Close one replay reopen with a fresh current-head proof.

        Replay invalidation is durable. Closure therefore records both the
        replacement verification and its exact reopen relation in one
        append-only runtime transition; the final replay guard remains the
        consumer-side fail-closed check.
        """

        current = self.state
        self._require_active(current)
        run_head = current.facts.run_head
        spine = current.facts.derived_spine
        if run_head is None or spine is None:
            raise RuntimeError("replay closure requires sealed Run Head and Derived Spine")
        matching = tuple(
            reopen
            for reopen in self._open_replay_reopens(current.facts)
            if reopen.node_id == cone.node_id
            and reopen.cone_id == cone.cone_id
            and reopen.cone_digest == cone.digest
            and reopen.run_head_digest == run_head.digest
        )
        if len(matching) != 1:
            raise RuntimeError("replay closure requires one exact open replay cone")
        reopen = matching[0]
        if cone.node_id not in {node.node_id for node in spine.nodes}:
            raise RuntimeError("replay closure must bind a node on the pre-extension spine")
        authority = (current.trajectory_digest, spine.digest, spine.landmark_mapping_digest)
        if (
            proof_spec.node_id != cone.node_id
            or (proof_spec.trajectory_digest, proof_spec.derived_spine_digest, proof_spec.landmark_mapping_digest)
            != authority
        ):
            raise RuntimeError("replay closure ProofSpec does not bind current trajectory authority")
        if (
            proof_result.proof_spec_id != proof_spec.proof_spec_id
            or proof_result.proof_spec_digest != proof_spec.digest
            or proof_result.node_id != cone.node_id
            or proof_result.proof_class != "deterministic_execution_proof"
            or proof_result.result != "green"
            or proof_result.run_head_digest != run_head.digest
        ):
            raise RuntimeError("replay closure proof result must be fresh GREEN current-head evidence")
        if any(item.proof_result_id == proof_result.proof_result_id for item in current.facts.proof_results):
            raise RuntimeError("replay closure proof result is already recorded")
        if any(item.proof_spec_id == proof_spec.proof_spec_id for item in current.facts.proof_specs):
            raise RuntimeError("replay closure ProofSpec is already recorded")
        fresh_fact = IterationFact(
            fact_id=f"replay-closure-verified:{reopen.replay_id}:{proof_result.proof_result_id}",
            fact_class="verified_node",
            node_id=cone.node_id,
            run_head_digest=run_head.digest,
            subject_id=proof_result.proof_result_id,
            cone_id=cone.cone_id,
            cone_digest=cone.digest,
        )
        facts = self._append_iteration_fact(current, current.facts, fresh_fact)
        closure = ReplayConeClosure(
            replay_id=reopen.replay_id,
            closed_cone_digest=cone.digest,
            run_head_digest=run_head.digest,
            proof_spec_digest=proof_spec.digest,
            proof_result_ids=(proof_result.proof_result_id,),
        )
        facts = FactIndex.model_validate(
            {
                **facts.model_dump(),
                "proof_specs": facts.proof_specs + (proof_spec,),
                "proof_results": facts.proof_results + (proof_result,),
                "replay_cone_closures": facts.replay_cone_closures + (closure,),
            }
        )
        successor = self._with_facts(current, facts)
        self._store.record_runtime_iteration(fresh_fact, successor)
        return successor

    def authorize_repair_work(
        self,
        *,
        cone: CausalCone,
        repair: RepairAttempt,
        expected_work: ProductWorkReceipt,
    ) -> WorkAuthorization:
        """Bind repair counters to exact repair attempt; caller supplies no kind."""

        current = self.state
        self._require_active(current)
        if repair.cone_id != cone.cone_id or repair.cone_digest != cone.digest:
            raise RuntimeError("repair work authorization does not bind current causal cone")
        return self._issue_work_authorization(
            current,
            kind="repair",
            operation_id=repair.attempt_id,
            operation_digest=digest_for("repair-attempt", repair),
            node_id=cone.node_id,
            cone_id=cone.cone_id,
            cone_digest=cone.digest,
            expected_work=expected_work,
        )

    def authorize_proof_work(
        self, *, proof_spec: ProofSpec, expected_work: ProductWorkReceipt
    ) -> WorkAuthorization:
        """Bind proof counters to ProofSpec; proof authority cannot debit repairs."""

        current = self.state
        self._require_active(current)
        if (
            proof_spec.trajectory_digest,
            proof_spec.derived_spine_digest,
            proof_spec.landmark_mapping_digest,
        ) != self._authority_digests(current):
            raise RuntimeError("ProofSpec does not bind current trajectory authority")
        return self._issue_work_authorization(
            current,
            kind="proof",
            operation_id=proof_spec.proof_spec_id,
            operation_digest=proof_spec.digest,
            node_id=proof_spec.node_id,
            cone_id=expected_work.cone_id,
            cone_digest=expected_work.cone_digest,
            expected_work=expected_work,
        )

    def issue_product_work_receipt(
        self, authorization: WorkAuthorization
    ) -> ProductWorkReceipt:
        return self._work_receipts.issue(authorization)

    def account_product_work(
        self,
        receipt_id: str | ProductWorkReceipt,
        receipt_digest: str | None = None,
    ) -> RunState:
        """Import only an issuer-registered receipt identity plus exact digest."""

        if not isinstance(receipt_id, str) or not isinstance(receipt_digest, str):
            if isinstance(receipt_id, ProductWorkReceipt):
                try:
                    ProductWorkReceipt.model_validate(receipt_id.model_dump())
                except ValidationError as error:
                    raise RuntimeError(f"invalid product work receipt: {error}") from error
            raise RuntimeError(
                "issued product work receipt identity and digest are required"
            )
        current = self.state
        self._require_active(current)
        existing = next(
            (item for item in current.facts.product_work if item.work_id == receipt_id),
            None,
        )
        if existing is not None:
            if existing.digest != receipt_digest:
                raise RuntimeError("product work id already records different completed work")
            return current
        issued = self._work_receipts.resolve(receipt_id, receipt_digest)
        return self._account_issued_product_work(current, issued)

    def _account_issued_product_work(
        self, current: RunState, issued: _IssuedWorkReceipt
    ) -> RunState:
        authorization = issued.authorization
        receipt = issued.receipt
        if (
            authorization.run_id != current.run_id
            or authorization.node_id != receipt.node_id
            or authorization.cone_id != receipt.cone_id
            or authorization.cone_digest != receipt.cone_digest
            or authorization.kind != receipt.kind
            or authorization.expected_counters != receipt.counters
        ):
            raise RuntimeError("issued product work receipt does not bind authorization")
        bound_facts = self._bind_canonical_cone_identity(
            current, current.facts, receipt.node_id, receipt.cone_id
        )
        current = self._with_facts(current, bound_facts)
        self._enforce_work_limits(current, receipt)
        facts = current.facts.record_product_work(authorization, receipt)
        successor = self._with_facts(current, facts)
        self._store.record_product_work(receipt.work_id, receipt.digest, successor)
        return successor

    def issue_independent_reviewer_manifest(
        self,
        *,
        reviewer_identity: str,
        cone: CausalCone,
    ) -> RoleManifest:
        """Issue fresh reviewer authority from current manifest facts, never caller role."""

        current = self.state
        self._require_active(current)
        run_head = current.facts.run_head
        if run_head is None:
            raise RuntimeError("independent classification requires current Run Head")
        normalized_identity = (
            reviewer_identity.strip().casefold()
            if isinstance(reviewer_identity, str)
            else ""
        )
        if (
            not isinstance(reviewer_identity, str)
            or not normalized_identity
            or normalized_identity == "controller"
            or normalized_identity == "patch_executor"
            or normalized_identity == "self"
            or normalized_identity.startswith(
                ("controller:", "patch_executor:", "self:")
            )
        ):
            raise RuntimeError("patch executor, controller, or self identity cannot classify")
        environment = current.facts.environment
        if environment is None:
            raise RuntimeError("independent classification requires sealed EnvironmentIdentity")
        trajectory_digest, derived_spine_digest, landmark_mapping_digest = self._authority_digests(current)
        manifest = RoleManifest(
            manifest_id=digest_for(
                "independent-reviewer-manifest-id",
                {
                    "run_id": current.run_id,
                    "reviewer_identity": reviewer_identity,
                    "cone_digest": cone.digest,
                    "run_head_digest": run_head.digest,
                },
            ),
            role="independent_change_reviewer",
            identity=reviewer_identity,
            attempt=1,
            goal_digest=trajectory_digest,
            cone_digest=cone.digest,
            base_revision=run_head.revision,
            run_head_digest=run_head.digest,
            environment_digest=environment.digest,
            fixture_digest=current.fixture_intent_digest,
            proof_spec_digest=digest_for(
                "independent-classification-output-schema",
                "change-classification-v1",
            ),
            permitted_output_schema="change-classification-v1",
            trajectory_digest=trajectory_digest,
            derived_spine_digest=derived_spine_digest,
            landmark_mapping_digest=landmark_mapping_digest,
        )
        if any(item.digest == manifest.digest for item in current.facts.role_manifests):
            raise RuntimeError("fresh reviewer manifest is already consumed")
        return self._reviewer_manifests.issue(manifest)

    def issue_independent_classification(
        self,
        *,
        reviewer_manifest_id: str,
        reviewer_manifest_digest: str,
        cone: CausalCone,
        repair: RepairAttempt,
    ) -> ChangeClassificationArtifact:
        """Issue classification only from one fresh reviewer manifest identity."""

        current = self.state
        self._require_active(current)
        run_head = current.facts.run_head
        if run_head is None:
            raise RuntimeError("independent classification requires current Run Head")
        manifest = self._reviewer_manifests.resolve(
            reviewer_manifest_id, reviewer_manifest_digest
        )
        trajectory_digest, derived_spine_digest, landmark_mapping_digest = self._authority_digests(current)
        if (
            manifest.goal_digest != trajectory_digest
            or manifest.cone_digest != cone.digest
            or manifest.base_revision != run_head.revision
            or manifest.run_head_digest != run_head.digest
            or manifest.environment_digest
            != (current.facts.environment.digest if current.facts.environment else "")
            or manifest.permitted_output_schema != "change-classification-v1"
            or manifest.trajectory_digest != trajectory_digest
            or manifest.derived_spine_digest != derived_spine_digest
            or manifest.landmark_mapping_digest != landmark_mapping_digest
        ):
            raise RuntimeError("fresh reviewer manifest does not bind current authority")
        if repair.cone_id != cone.cone_id or repair.cone_digest != cone.digest:
            raise RuntimeError("independent classification does not bind current repair cone")
        artifact = ChangeClassificationArtifact(
            artifact_id=(
                f"classification:{manifest.manifest_id}:"
                f"{digest_for('repair-attempt', repair)[:16]}"
            ),
            reviewer_id=manifest.identity,
            reviewer_role="independent_change_reviewer",
            reviewer_manifest_id=manifest.manifest_id,
            reviewer_manifest_digest=manifest.digest,
            change_kind=repair.change_kind,
            run_id=current.run_id,
            node_id=cone.node_id,
            cone_id=cone.cone_id,
            cone_digest=cone.digest,
            goal_digest=trajectory_digest,
            envelope_digest=current.trajectory.execution_envelope.digest,
            repair_hypothesis=repair.hypothesis,
            changed_dependencies=repair.changed_dependencies,
            changed_files=repair.changed_files,
            trajectory_digest=trajectory_digest,
            derived_spine_digest=derived_spine_digest,
            landmark_mapping_digest=landmark_mapping_digest,
        )
        return self._classification_receipts.issue(manifest, artifact)

    def record_failed_repair(
        self,
        *,
        cone: CausalCone,
        repair: RepairAttempt,
        proof_spec: ProofSpec,
        proof_result: ProofResult,
        classification: ChangeClassificationArtifact | None = None,
        classification_receipt_id: str | None = None,
        classification_receipt_digest: str | None = None,
        diagnostics_implicate_runtime: bool = False,
    ) -> RuntimeProgress:
        """After a failed repair, advance exactly one unseen hop or pause safely."""

        current = self.state
        self._require_active(current)
        bound_facts = self._bind_canonical_cone_identity(
            current, current.facts, cone.node_id, cone.cone_id
        )
        current = self._with_facts(current, bound_facts)
        run_head = current.facts.run_head
        environment = current.facts.environment
        if run_head is None or environment is None:
            raise RuntimeError("failed repair requires sealed Run Head and EnvironmentIdentity")
        try:
            FailedRepairEvidence(repair, proof_spec, proof_result)
        except RepairError as error:
            raise RuntimeError(str(error)) from error
        if repair.cone_id != cone.cone_id or repair.cone_digest != cone.digest:
            raise RuntimeError("repair attempt does not bind current causal cone")
        if proof_spec.node_id != cone.node_id:
            raise RuntimeError("ProofSpec must target current Behavioral Node")
        trajectory_digest, derived_spine_digest, landmark_mapping_digest = self._authority_digests(current)
        if (
            proof_spec.trajectory_digest != trajectory_digest
            or proof_spec.derived_spine_digest != derived_spine_digest
            or proof_spec.landmark_mapping_digest != landmark_mapping_digest
        ):
            raise RuntimeError("ProofSpec does not bind current trajectory authority")
        if proof_result.run_head_digest != run_head.digest:
            raise RuntimeError("deterministic proof result does not bind current Run Head")
        fingerprint = StallFingerprint(
            node_id=cone.node_id,
            run_head_digest=run_head.digest,
            environment_digest=environment.digest,
            fixture_snapshot_digest=current.fixture_intent_digest,
            cone_digest=cone.digest,
            repair_hypothesis=repair.hypothesis,
            proof_spec_digest=proof_spec.digest,
            deterministic_proof_result_digest=proof_result.digest,
        )
        if any(
            item.stall_fingerprint == fingerprint
            for item in current.facts.iteration_facts
        ):
            raise RuntimeError("identical stall fingerprint rejects repeated repair work")

        issued_classification = self._require_issued_classification(
            classification,
            classification_receipt_id,
            classification_receipt_digest,
        )
        classification = issued_classification.artifact
        consumption = self._require_repair_authority(
            current, repair, cone, classification
        )
        evidence_facts = self._append_failure_evidence(
            current.facts,
            repair,
            proof_spec,
            proof_result,
            issued_classification.manifest,
            classification,
            consumption,
        )

        used_hop_ids = frozenset(
            item.subject_id
            for item in current.facts.iteration_facts
            if item.fact_class == "new_hop" and item.cone_id == cone.cone_id
        )
        failed_cycle_count = sum(
            item.cone_id == cone.cone_id for item in current.facts.repairs
        )
        failed_cycle_limit = current.limits.active.value_for(
            "failed_repair_cycles"
        ).amount
        hop = (
            cone.next_unused_ordinary_hop(
                used_hop_ids,
                diagnostics_implicate_runtime=diagnostics_implicate_runtime,
            )
            if failed_cycle_count < failed_cycle_limit
            else None
        )
        widening_used = False
        reasoning_tier = 0
        if hop is None:
            widening_count = sum(
                int(item.widening_used)
                for item in current.facts.iteration_facts
                if item.cone_id == cone.cone_id
            )
            widening_limit = current.limits.active.value_for("diagnostic_widening").amount
            if widening_count < widening_limit:
                hop = cone.next_unused_widened_hop(
                    used_hop_ids,
                    diagnostics_implicate_runtime=diagnostics_implicate_runtime,
                )
                widening_used = hop is not None
                if hop is not None:
                    reasoning_limit = current.limits.active.value_for(
                        "reasoning_escalation"
                    ).amount
                    prior_reasoning_tier = max(
                        (
                            item.reasoning_tier
                            for item in current.facts.iteration_facts
                            if item.cone_id == cone.cone_id
                        ),
                        default=0,
                    )
                    if prior_reasoning_tier >= reasoning_limit:
                        hop = None
                        widening_used = False
                    else:
                        reasoning_tier = prior_reasoning_tier + 1
        if hop is None:
            return self._pause(
                current,
                node_id=cone.node_id,
                cone_id=cone.cone_id,
                cone_digest=cone.digest,
                consumed_limits=(
                    "causal_radius",
                    "failed_repair_cycles",
                    "diagnostic_widening",
                    "reasoning_escalation",
                ),
                fingerprint=fingerprint,
                facts=evidence_facts,
            )

        fact = IterationFact(
            fact_id=f"hop:{cone.cone_id}:{hop.hop_id}:{fingerprint.digest[:16]}",
            fact_class="new_hop",
            node_id=cone.node_id,
            run_head_digest=run_head.digest,
            subject_id=hop.hop_id,
            cone_id=cone.cone_id,
            cone_digest=cone.digest,
            widening_used=widening_used,
            reasoning_tier=reasoning_tier,
            stall_fingerprint=fingerprint,
        )
        expected_charge = ProductWorkReceipt(
            work_id=f"discovery-hop-template:{repair.attempt_id}:{hop.hop_id}",
            kind="discovery",
            node_id=cone.node_id,
            cone_id=cone.cone_id,
            cone_digest=cone.digest,
            command_count=1,
            output_bytes=0,
            command_output_bytes=(0,),
            causal_radius=hop.ring,
            widening_allowance=int(widening_used),
        )
        authorization = self._issue_work_authorization(
            current,
            kind="discovery",
            operation_id=f"discovery-hop:{repair.attempt_id}:{hop.hop_id}",
            operation_digest=digest_for(
                "discovery-hop-operation",
                {"repair": repair, "hop_id": hop.hop_id},
            ),
            node_id=cone.node_id,
            cone_id=cone.cone_id,
            cone_digest=cone.digest,
            expected_work=expected_charge,
        )
        charge = self.issue_product_work_receipt(authorization)
        try:
            self._enforce_work_limits(current, charge)
        except RuntimeError as error:
            if not str(error).startswith("Run Limit exhausted:"):
                raise
            return self._pause(
                current,
                node_id=cone.node_id,
                cone_id=cone.cone_id,
                cone_digest=cone.digest,
                consumed_limits=(
                    "causal_radius",
                    "failed_repair_cycles",
                    "diagnostic_widening",
                    "reasoning_escalation",
                    "discovery_commands",
                    "discovery_duration",
                ),
                fingerprint=fingerprint,
                facts=evidence_facts,
            )
        charged_facts = current.facts.record_product_work(authorization, charge)
        charged_state = self._with_facts(current, charged_facts)
        facts = self._append_failure_evidence(
            charged_facts,
            repair,
            proof_spec,
            proof_result,
            issued_classification.manifest,
            classification,
            consumption,
        )
        facts = self._append_iteration_fact(current, facts, fact)
        successor = self._with_facts(current, facts)
        self._store.record_product_work(charge.work_id, charge.digest, charged_state)
        self._store.record_runtime_iteration(fact, successor)
        return RuntimeProgress(successor, fact)

    def integrate_proof_ladder(
        self,
        *,
        ladder: ProofLadder,
        cone: CausalCone,
    ) -> RunState:
        """Advance only after complete candidate proof and one bound Run Head change."""

        current = self.state
        self._require_active(current)
        if ladder.closed_cone is None or ladder.closed_cone.cone != cone:
            raise RuntimeError("proof ladder must bind exact closed causal cone")
        try:
            new_run_head = ladder.validate(current_state=current)
        except ProofLadderError as error:
            raise RuntimeError(str(error)) from error
        current_head = current.facts.run_head
        if current_head is None or ladder.base_run_head != current_head:
            raise RuntimeError("proof ladder must bind current Run Head")
        if ladder.proof_spec.node_id != cone.node_id:
            raise RuntimeError("proof ladder must target current causal cone")
        bound_facts = self._bind_canonical_cone_identity(
            current, current.facts, cone.node_id, cone.cone_id
        )
        all_specs = (ladder.proof_spec, *ladder.affected_neighbor_specs)
        if any(
            existing.proof_spec_id == spec.proof_spec_id or existing.digest == spec.digest
            for existing in bound_facts.proof_specs
            for spec in all_specs
        ):
            raise RuntimeError("ProofSpec is already recorded")
        results = (
            ladder.red_result,
            ladder.original_node_result,
            *ladder.affected_neighbor_results,
        )
        if any(result is None for result in results):
            raise RuntimeError("complete proof ladder result is required")
        typed_results = tuple(result for result in results if result is not None)
        if any(
            existing.proof_result_id == result.proof_result_id
            for existing in bound_facts.proof_results
            for result in typed_results
        ):
            raise RuntimeError("proof result is already recorded")
        outputs = (
            ladder.executor_output,
            ladder.discovery_output,
            ladder.curator_output,
            ladder.validator_output,
            ladder.semantic_output,
        )
        if any(output is None for output in outputs):
            raise RuntimeError("complete independent role evidence is required")
        typed_outputs = tuple(output for output in outputs if output is not None)
        manifests = tuple(output.dispatch.manifest for output in typed_outputs)
        if any(
            existing.digest == manifest.digest
            for existing in bound_facts.role_manifests
            for manifest in manifests
        ):
            raise RuntimeError("role manifest is already recorded")
        original = ladder.original_node_result
        assert original is not None
        verification_facts = tuple(
            IterationFact(
                fact_id=f"integrated-proof:{result.proof_result_id}",
                fact_class="verified_node",
                node_id=result.node_id,
                run_head_digest=new_run_head.digest,
                subject_id=result.proof_result_id,
                cone_id=cone.cone_id,
                cone_digest=cone.digest,
            )
            for result in (original, *ladder.affected_neighbor_results)
        )
        for fact in verification_facts:
            bound_facts = self._bind_canonical_cone_identity(
                current, bound_facts, fact.node_id, fact.cone_id
            )
        open_replays = self._open_replay_reopens(bound_facts)
        replay_closures = tuple(
            ReplayConeClosure(
                replay_id=reopen.replay_id,
                closed_cone_digest=digest_for(
                    "closed-causal-cone",
                    {
                        "cone_digest": ladder.closed_cone.cone.digest,
                        "frozen_expansion_digest": ladder.closed_cone.frozen_expansion.digest,
                    },
                ),
                run_head_digest=new_run_head.digest,
                proof_spec_digest=ladder.proof_spec.digest,
                proof_result_ids=tuple(result.proof_result_id for result in typed_results),
            )
            for reopen in open_replays
            if reopen.node_id == cone.node_id and reopen.cone_id == cone.cone_id
        )
        facts = FactIndex.model_validate(
            {
                **bound_facts.model_dump(),
                "run_head": new_run_head,
                "proof_specs": bound_facts.proof_specs + all_specs,
                "proof_results": bound_facts.proof_results + typed_results,
                "role_manifests": bound_facts.role_manifests + manifests,
                "iteration_facts": bound_facts.iteration_facts + verification_facts,
                "replay_cone_closures": bound_facts.replay_cone_closures + replay_closures,
            }
        )
        successor = self._with_facts(current, facts)
        from .artifacts import ArtifactRecord
        from .workspace import (
            WorkspaceError,
            commit_lifecycle_integration_reservation,
            reserve_lifecycle_integration_receipt,
            rollback_lifecycle_integration_reservation,
        )

        records = tuple(ArtifactRecord.from_role_output(output) for output in typed_outputs)
        try:
            reservation = reserve_lifecycle_integration_receipt(
                ladder.integration,
                role_outputs=typed_outputs,
            )
        except WorkspaceError as error:
            raise RuntimeError(str(error)) from error
        try:
            self._store.record_run_head_advanced(
                new_run_head,
                successor,
                artifacts=records,
            )
        except BaseException:
            try:
                rollback_lifecycle_integration_reservation(reservation)
            except WorkspaceError as error:
                raise RuntimeError(str(error)) from error
            raise
        try:
            commit_lifecycle_integration_reservation(reservation)
        except WorkspaceError as error:
            raise RuntimeError(str(error)) from error
        return successor

    def pause_for_review_infrastructure(
        self,
        *,
        cone: CausalCone,
        role: str,
        attempts_exhausted: int,
    ) -> RunState:
        """Required role failure is a hard pause; controller substitution is impossible."""

        current = self.state
        self._require_active(current)
        if not isinstance(role, str) or not role.strip() or attempts_exhausted < 1:
            raise RuntimeError("review infrastructure pause requires role and exhausted attempts")
        if current.pending_decision is not None:
            raise RuntimeError("run already has a pending digest-bound user decision")
        run_head = current.facts.run_head
        if run_head is None:
            raise RuntimeError("review infrastructure pause requires current Run Head")
        facts = self._bind_canonical_cone_identity(current, current.facts, cone.node_id, cone.cone_id)
        from .models import PendingDecision

        pending = PendingDecision(
            decision_id=f"review-infrastructure:{cone.digest}:{role}:{attempts_exhausted}",
            cone_id=cone.cone_id,
            cone_digest=cone.digest,
            kind="access",
            question="Provide independent review infrastructure or terminalize this bounded run.",
            evidence_refs=(f"review-role:{role}", f"attempts-exhausted:{attempts_exhausted}"),
            allowed_kinds=("terminalization", "cancellation"),
        )
        report = PauseReport(
            node_id=cone.node_id,
            reason="review_infrastructure",
            cone_id=cone.cone_id,
            cone_digest=cone.digest,
            consumed_limits=("agent_dispatches_per_cone",),
            consumed_limit_values=(LimitConsumption(limit_name="agent_dispatches_per_cone", consumed=attempts_exhausted),),
            expected_behavior=tuple(
                item.statement for item in current.trajectory.expected_behaviors
            ),
            failure_evidence_refs=(f"review-role:{role}",),
            causal_graph_refs=(f"causal-cone:{cone.cone_id}:{cone.digest}",),
            attempted_repair_refs=(f"review-attempts:{attempts_exhausted}",),
            causal_radius=0,
            widening_used=0,
            reasoning_tier=0,
            no_safe_action_rationale=(
                f"Required independent {role} review exhausted {attempts_exhausted} fresh attempts; controller fallback is forbidden."
            ),
            requested_decisions=("access", "terminalization", "cancellation"),
            smallest_decisions=("access", "terminalization", "cancellation"),
        )
        fact = IterationFact(
            fact_id=f"review-infrastructure:{cone.digest}:{role}:{attempts_exhausted}",
            fact_class="pause",
            node_id=cone.node_id,
            run_head_digest=run_head.digest,
            subject_id=role,
            cone_id=cone.cone_id,
            cone_digest=cone.digest,
        )
        facts = self._append_iteration_fact(current, facts, fact)
        facts = FactIndex.model_validate(
            {
                **facts.model_dump(),
                "pending_decision_history": facts.pending_decision_history + (pending,),
                "pause_reports": facts.pause_reports + (report,),
                "pause_report": report,
            }
        )
        successor = current.model_copy(update={"facts": facts, "mode": "paused", "pending_decision": pending})
        self._store.record_review_infrastructure_pause(report, successor)
        return successor

    def run_final_replay(
        self,
        *,
        adapter: object,
        final_semantic: object | None = None,
        final_proof_spec: ProofSpec | None = None,
        final_semantic_output: object | None = None,
    ) -> FinalReplayResult:
        """Reset fixture once, replay persisted frozen Spine, then prove or reopen."""

        current = self.state
        self._require_active(current)
        current_spine = current.facts.derived_spine
        if current_spine is None:
            raise RuntimeError("final replay requires persisted Derived Spine")
        frozen = self._load_frozen_derived_spine(current)
        run_head = current.facts.run_head
        environment = current.facts.environment
        if run_head is None or environment is None:
            raise RuntimeError("final replay requires sealed Run Head and environment")
        if current.pending_decision is not None:
            raise RuntimeError("final replay cannot start with pending escalation")
        if final_semantic is None:
            final_semantic = final_semantic_output
        if not callable(final_semantic):
            raise RuntimeError("final semantic attestation must be issued after replay traversal")
        if self._open_replay_reopens(current.facts):
            raise RuntimeError("final replay requires replay-reopened cone closure and fresh current proofs")
        if final_proof_spec is None:
            raise RuntimeError("final replay requires a digest-bound ProofSpec")
        if not frozen.nodes or final_proof_spec.node_id != frozen.nodes[-1].node_id:
            raise RuntimeError("final replay ProofSpec must bind terminal Spine node")
        # Current spine was checked by _load_frozen_derived_spine only as a
        # drift guard. All replay authority below comes from immutable freeze.
        authority_digests = (
            current.trajectory_digest,
            frozen.derived_spine_digest,
            frozen.landmark_mapping_digest,
        )
        if (
            final_proof_spec.trajectory_digest,
            final_proof_spec.derived_spine_digest,
            final_proof_spec.landmark_mapping_digest,
        ) != authority_digests:
            raise RuntimeError("final replay ProofSpec does not bind current trajectory authority")
        open_lead = self._smallest_open_causal_lead(current)

        from .adapters.user_journey import FixtureReceipt, FixtureSnapshot
        from .spine import NodeVerified, ObservableSpine, ObservedFailure

        # Validate and reset fixture before recording final_replay_started.
        # Failed identity/receipt checks leave durable mode running, allowing
        # a corrected adapter retry. Always invoke reset for a valid snapshot;
        # active adapter state is not evidence that reset receipt was valid.
        try:
            fixture_snapshot = adapter.fixture_snapshot()  # type: ignore[attr-defined]
        except (AttributeError, TypeError, ValueError) as error:
            raise RuntimeError("final replay fixture snapshot failed") from error
        if (
            not isinstance(fixture_snapshot, FixtureSnapshot)
            or not fixture_snapshot.sealed
            or fixture_snapshot.snapshot_digest != frozen.fixture_digest
            or fixture_snapshot.fixture_id != frozen.fixture_id
            or fixture_snapshot.adapter_id != frozen.fixture_adapter_id
            or fixture_snapshot.snapshot_digest != current.fixture_intent_digest
            or fixture_snapshot.snapshot_digest != run_head.fixture_digest
        ):
            raise RuntimeError("final replay fixture does not match sealed snapshot")
        try:
            fixture_receipt = adapter.reset_fixture(fixture_snapshot)  # type: ignore[attr-defined]
        except (AttributeError, TypeError, ValueError) as error:
            raise RuntimeError("final replay fixture reset failed") from error
        expected_receipt = FixtureReceipt(
            fixture_id=frozen.fixture_id,
            snapshot_digest=frozen.fixture_digest,
            adapter_id=frozen.fixture_adapter_id,
        )
        if not isinstance(fixture_receipt, FixtureReceipt) or fixture_receipt != expected_receipt:
            raise RuntimeError(
                "final replay fixture does not match sealed snapshot (reset receipt invalid)"
            )

        snapshot = FinalReplaySnapshot.from_frozen(
            frozen, limits_digest=digest_for("resolved-run-limits", current.limits)
        )
        self._store.put_artifact("final-replay-snapshot", snapshot)
        started = current.model_copy(update={"mode": "final_replay"})
        self._store.record_final_replay_started(run_head, started)
        terminal_cone = CausalCone(
            cone_id=self._known_or_replay_cone_id(
                started, frozen.nodes[-1].node_id
            ),
            node_id=frozen.nodes[-1].node_id,
        )
        replay_spine = frozen.as_replay_projection()
        traversal = ObservableSpine(current.trajectory, replay_spine, current_run_head=frozen.run_head, accepted_observations=())
        previous: NodeVerified | None = None
        node_proofs: list[ProofResult] = []
        node_specs: list[ProofSpec] = []
        replay_observations: list[Observation] = []
        replay_observations_by_node: dict[str, tuple[Observation, ...]] = {}
        for node_index, step in enumerate(frozen.nodes):
            # `advance` is the only replay progression seam. It consumes the
            # frozen node at exact index and lets stateful adapters advance.
            outcome = traversal.advance(adapter=adapter, node_index=node_index, previous=previous)
            if isinstance(outcome, ObservedFailure):
                return self._reopen_final_replay(
                    started=started,
                    snapshot=snapshot,
                    run_head=run_head,
                    node_proofs=tuple(node_proofs),
                    node_id=outcome.node_id,
                    subject_id=f"replay-regression:{outcome.failure_code}",
                )
            if not isinstance(outcome, NodeVerified):
                raise RuntimeError("final replay produced unknown traversal outcome")
            replay_observations.extend(outcome.observations)
            replay_observations_by_node[outcome.node_id] = outcome.observations
            try:
                proof_artifact = self._store.put_artifact(
                    "final-replay-node",
                    {
                        "snapshot_digest": snapshot.digest,
                        "node_id": outcome.node_id,
                        "observations": outcome.observations,
                        "actions": outcome.action_receipts,
                        "seams": outcome.seam_receipts,
                    },
                )
            except Exception:
                return self._reopen_final_replay(
                    started=started,
                    snapshot=snapshot,
                    run_head=run_head,
                    node_proofs=tuple(node_proofs),
                    node_id=outcome.node_id,
                    subject_id="final-replay-artifact-persistence-failure",
                )
            node_spec = (
                final_proof_spec
                if outcome.node_id == final_proof_spec.node_id
                else ProofSpec(
                    proof_spec_id=f"{final_proof_spec.proof_spec_id}:replay:{outcome.node_id}",
                    node_id=outcome.node_id,
                    discriminator=f"final replay node {outcome.node_id}",
                    expected_result="green",
                    command=final_proof_spec.command,
                    trajectory_digest=authority_digests[0],
                    derived_spine_digest=authority_digests[1],
                    landmark_mapping_digest=authority_digests[2],
                )
            )
            node_specs.append(node_spec)
            node_proofs.append(
                ProofResult(
                    proof_result_id=f"final-replay:{snapshot.digest[:16]}:{outcome.node_id}",
                    proof_spec_id=node_spec.proof_spec_id,
                    proof_spec_digest=node_spec.digest,
                    node_id=outcome.node_id,
                    proof_class="deterministic_execution_proof",
                    result="green",
                    artifact_digest=proof_artifact.digest,
                    run_head_digest=run_head.digest,
                )
            )
            previous = outcome
        if open_lead is not None:
            lead, node_id = open_lead
            return self._reopen_final_replay(
                started=started,
                snapshot=snapshot,
                run_head=run_head,
                node_proofs=tuple(node_proofs),
                node_id=node_id,
                subject_id=f"open-causal-lead:{lead.lead_id}",
            )
        from .artifacts import ArtifactRecord

        # Every frozen mapping must be proven by current replay evidence tied
        # to one of its exact mapped node IDs. A green semantic decision alone
        # cannot manufacture landmark proof.
        replay_proof_nodes = {proof.node_id for proof in node_proofs if proof.result == "green"}
        for landmark_id, mapped_node_ids in frozen.landmark_mapping:
            mapped = set(mapped_node_ids)
            if not mapped or not mapped.issubset(replay_proof_nodes):
                return self._reopen_final_replay(
                    started=started,
                    snapshot=snapshot,
                    run_head=run_head,
                    node_proofs=tuple(node_proofs),
                    node_id=(mapped_node_ids[0] if mapped_node_ids else frozen.nodes[-1].node_id),
                    subject_id=f"landmark-proof-gap:{landmark_id}",
                )
            landmark = next(item for item in current.trajectory.landmarks if item.landmark_id == landmark_id)
            landmark_states = {
                observation.observed_state
                for node_id in mapped
                for observation in replay_observations_by_node.get(node_id, ())
                if (
                    observation.run_head_digest == run_head.digest
                    and observation.evidence_refs
                )
            }
            if not landmark_states or any(
                acceptance not in landmark_states
                for acceptance in landmark.acceptance
            ):
                return self._reopen_final_replay(
                    started=started,
                    snapshot=snapshot,
                    run_head=run_head,
                    node_proofs=tuple(node_proofs),
                    node_id=mapped_node_ids[-1],
                    subject_id=f"landmark-proof-gap:{landmark_id}",
                )
        terminal = current.trajectory.terminal_outcome
        terminal_evidence = tuple(
            observation
            for observation in replay_observations
            if observation.run_head_digest == run_head.digest
            and observation.observed_state in {terminal.description, *terminal.acceptance}
            and observation.evidence_refs
        )
        if not terminal_evidence or any(
            acceptance not in {observation.observed_state for observation in terminal_evidence}
            for acceptance in terminal.acceptance
        ):
            return self._reopen_final_replay(
                started=started,
                snapshot=snapshot,
                run_head=run_head,
                node_proofs=tuple(node_proofs),
                node_id=frozen.nodes[-1].node_id,
                subject_id="terminal-outcome-proof-gap",
            )

        replay_result_digest = digest_for(
            "final-replay-result",
            {
                "snapshot_digest": snapshot.digest,
                "node_proof_digests": tuple(proof.digest for proof in node_proofs),
            },
        )
        try:
            replay_bundle = self._store.put_artifact(
                "final-replay-bundle",
                {
                    "snapshot_digest": snapshot.digest,
                    "replay_result_digest": replay_result_digest,
                    "node_proof_digests": tuple(proof.digest for proof in node_proofs),
                },
            )
        except Exception:
            return self._reopen_final_replay(
                started=started,
                snapshot=snapshot,
                run_head=run_head,
                node_proofs=tuple(node_proofs),
                node_id=terminal_cone.node_id,
                subject_id="final-replay-bundle-persistence-failure",
            )

        def semantic_failure(reason: str = "unknown") -> FinalReplayResult:
            """Leave durable final replay through retry-safe cone reopen."""

            return self._reopen_final_replay(
                started=started,
                snapshot=snapshot,
                run_head=run_head,
                node_proofs=tuple(node_proofs),
                node_id=terminal_cone.node_id,
                subject_id=f"final-replay-semantic-failure:{reason}",
            )

        try:
            issued_final_semantic = final_semantic(
                snapshot, tuple(node_proofs), replay_bundle.digest, replay_result_digest
            )
        except Exception:
            return semantic_failure("callback")
        if not isinstance(issued_final_semantic, ImportedRoleOutput):
            return semantic_failure("not-imported")
        try:
            require_exact_issuer_output(
                issued_final_semantic,
                state=started,
                cone=terminal_cone,
                proof_spec=final_proof_spec,
                role="semantic_reviewer",
                permitted_output_schema="final-replay-semantic-output-v1",
                issued_mode="final_replay",
                context_id=final_replay_context_id(
                    snapshot, replay_bundle.digest, replay_result_digest
                ),
            )
        except Exception:
            return semantic_failure("manifest-import")
        manifest = issued_final_semantic.dispatch.manifest
        if (
            manifest.role != "semantic_reviewer"
            or manifest.goal_digest != current.trajectory_digest
            or manifest.cone_digest != terminal_cone.digest
            or manifest.base_revision != run_head.revision
            or manifest.run_head_digest != run_head.digest
            or manifest.environment_digest != environment.digest
            or manifest.fixture_digest != current.fixture_intent_digest
            or manifest.proof_spec_digest != final_proof_spec.digest
            or manifest.permitted_output_schema != "final-replay-semantic-output-v1"
            or issued_final_semantic.dispatch.spine_digest
            != frozen.derived_spine_digest
            or issued_final_semantic.dispatch.context_id
            != final_replay_context_id(snapshot, replay_bundle.digest, replay_result_digest)
            or issued_final_semantic.dispatch.issued_mode != "final_replay"
        ):
            return semantic_failure("manifest-bind")
        try:
            payload = json.loads(issued_final_semantic.raw_payload.decode("utf-8"))
        except Exception:
            return semantic_failure("payload")
        if (
            payload.get("replay_bundle_digest") != replay_bundle.digest
            or payload.get("replay_result_digest") != replay_result_digest
        ):
            return semantic_failure("payload-bind")
        try:
            require_independent_decision(issued_final_semantic, role="semantic_reviewer", decision="approved")
            consume_issuer_registered_output(issued_final_semantic)
        except Exception:
            return semantic_failure("decision")
        try:
            semantic_record = ArtifactRecord.from_role_output(issued_final_semantic)
            self._store.put_artifact_at_digest(semantic_record.domain, semantic_record.digest, semantic_record.payload)
        except Exception:
            return semantic_failure("artifact")
        facts = self._bind_canonical_cone_identity(started, started.facts, terminal_cone.node_id, terminal_cone.cone_id)
        terminal = IterationFact(
            fact_id=f"final-replay-succeeded:{snapshot.digest[:16]}",
            fact_class="terminal",
            node_id=terminal_cone.node_id,
            run_head_digest=run_head.digest,
            subject_id=snapshot.digest,
            cone_id=terminal_cone.cone_id,
            cone_digest=terminal_cone.digest,
        )
        facts = FactIndex.model_validate(
            {
                **facts.model_dump(),
                "proof_specs": facts.proof_specs + tuple(node_specs),
                "proof_results": facts.proof_results + tuple(node_proofs),
                "role_manifests": facts.role_manifests + (manifest,),
                "iteration_facts": facts.iteration_facts + (terminal,),
            }
        )
        successor = started.model_copy(update={"facts": facts, "mode": "succeeded"})
        try:
            self._store.record_final_replay_succeeded(
                terminal,
                successor,
                semantic_output=issued_final_semantic,
            )
        except Exception:
            return semantic_failure("success-persistence")
        proven_landmarks = tuple(landmark_id for landmark_id, _ in frozen.landmark_mapping)
        return FinalReplayResult(
            successor,
            snapshot,
            tuple(node_proofs),
            proven_landmark_ids=proven_landmarks,
            terminal_outcome_proven=bool(terminal_evidence and payload.get("decision") == "approved"),
        )

    @staticmethod
    def _known_or_replay_cone_id(state: RunState, node_id: str) -> str:
        for binding in state.facts.cone_identity_bindings:
            if binding.run_id == state.run_id and binding.node_id == node_id:
                return binding.cone_id
        return f"replay:{node_id}"

    def _reopen_final_replay(
        self,
        *,
        started: RunState,
        snapshot: FinalReplaySnapshot,
        run_head: RunHead,
        node_proofs: tuple[ProofResult, ...],
        node_id: str,
        subject_id: str,
    ) -> FinalReplayResult:
        cone = CausalCone(
            cone_id=self._known_or_replay_cone_id(started, node_id),
            node_id=node_id,
        )
        stale_verified = tuple(
            item
            for item in started.facts.iteration_facts
            if item.fact_class == "verified_node"
            and item.node_id == node_id
            and item.run_head_digest == run_head.digest
        )
        replay_reopen = ReplayReopen(
            replay_id=f"final-replay-reopen:{snapshot.digest[:16]}:{node_id}",
            node_id=node_id,
            cone_id=cone.cone_id,
            cone_digest=cone.digest,
            run_head_digest=run_head.digest,
            stale_verified_fact_ids=tuple(item.fact_id for item in stale_verified),
        )
        facts = FactIndex.model_validate(
            {
                **started.facts.model_dump(),
                "replay_reopens": started.facts.replay_reopens + (replay_reopen,),
            }
        )
        facts = self._bind_canonical_cone_identity(started, facts, cone.node_id, cone.cone_id)
        fact = IterationFact(
            fact_id=f"final-replay-regression:{snapshot.digest[:16]}:{node_id}",
            fact_class="new_hop",
            node_id=node_id,
            run_head_digest=run_head.digest,
            subject_id=subject_id,
            cone_id=cone.cone_id,
            cone_digest=cone.digest,
        )
        facts = self._append_iteration_fact(started, facts, fact)
        successor = started.model_copy(update={"facts": facts, "mode": "running"})
        self._store.record_final_replay_reopened(fact, successor)
        return FinalReplayResult(successor, snapshot, node_proofs, cone)

    @staticmethod
    def _smallest_open_causal_lead(
        state: RunState,
    ) -> tuple[object, str] | None:
        observations = {
            observation.observation_id: observation for observation in state.facts.observations
        }
        spine = state.facts.derived_spine
        journey_order = {
            node.node_id: index
            for index, node in enumerate(spine.nodes if spine is not None else ())
        }
        candidates: list[tuple[int, str, object, str]] = []
        for lead in state.facts.leads:
            if lead.disposition != "open":
                continue
            observation = observations.get(lead.source_observation_id)
            if observation is None or observation.node_id not in journey_order:
                raise RuntimeError("open causal lead must bind an observable Spine node")
            candidates.append((journey_order[observation.node_id], lead.lead_id, lead, observation.node_id))
        if not candidates:
            return None
        _, _, lead, node_id = min(candidates)
        return lead, node_id

    @staticmethod
    def _open_replay_reopens(facts: FactIndex) -> tuple[ReplayReopen, ...]:
        closed_ids = {closure.replay_id for closure in facts.replay_cone_closures}
        return tuple(reopen for reopen in facts.replay_reopens if reopen.replay_id not in closed_ids)

    @classmethod
    def _replay_repair_ready(cls, state: RunState) -> bool:
        """Allow one extension after exact replay closure and fresh proof."""

        spine = state.facts.derived_spine
        run_head = state.facts.run_head
        if (
            spine is None
            or run_head is None
            or spine.frontier.target_landmark_id is not None
            or spine.frontier.unexecuted_node_id is not None
            or not spine.nodes
            or len(spine.results) != len(spine.nodes)
        ):
            return False
        closed = {closure.replay_id: closure for closure in state.facts.replay_cone_closures}
        proof_specs = {spec.digest: spec for spec in state.facts.proof_specs}
        proof_results = {result.proof_result_id: result for result in state.facts.proof_results}
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
            if closure is None or closure.closed_cone_digest != reopen.cone_digest:
                continue
            spec = proof_specs.get(closure.proof_spec_digest)
            if spec is None or (
                spec.trajectory_digest,
                spec.derived_spine_digest,
                spec.landmark_mapping_digest,
            ) != (state.trajectory_digest, spine.digest, spine.landmark_mapping_digest):
                continue
            if (
                closure.run_head_digest != run_head.digest
                or reopen.node_id not in {node.node_id for node in spine.nodes}
                or spec.node_id != reopen.node_id
                or reopen.node_id not in verified
            ):
                continue
            if any(
                (proof_results.get(result_id) is None)
                or proof_results[result_id].result != "green"
                or proof_results[result_id].run_head_digest != run_head.digest
                or proof_results[result_id].proof_spec_digest != spec.digest
                or proof_results[result_id].node_id != reopen.node_id
                for result_id in closure.proof_result_ids
            ):
                continue
            return True
        return False

    def pause_diagnostic_stall(
        self,
        *,
        node_id: str,
        cone_id: str,
        cone_digest: str,
        consumed_limits: tuple[str, ...],
    ) -> RunState:
        current = self.state
        self._require_active(current)
        return self._pause(
            current,
            node_id=node_id,
            cone_id=cone_id,
            cone_digest=cone_digest,
            consumed_limits=consumed_limits,
            fingerprint=None,
        ).state

    def request_escalation(
        self,
        *,
        kind: Literal[
            "scope_authorization",
            "behavior_authorization",
            "architecture_authorization",
            "external_contract_authorization",
            "access",
            "terminalization",
            "cancellation",
        ],
        node_id: str,
        cone_id: str,
        cone_digest: str,
        question: str,
        evidence_refs: tuple[str, ...],
    ) -> RunState:
        """Pause for an explicit behavior/scope/access authority decision."""

        current = self.state
        self._require_active(current)
        if current.pending_decision is not None:
            raise RuntimeError("run already has a pending digest-bound user decision")
        run_head = current.facts.run_head
        if run_head is None:
            raise RuntimeError("escalation requires a current Run Head")
        from .models import PendingDecision

        pending = PendingDecision(
            decision_id=f"escalation:{cone_digest}:{len(current.facts.iteration_facts) + 1}",
            cone_id=cone_id,
            cone_digest=cone_digest,
            kind=kind,
            question=question,
            evidence_refs=evidence_refs,
        )
        fact = IterationFact(
            fact_id=f"escalation:{cone_digest}:{len(current.facts.iteration_facts) + 1}",
            fact_class="escalation",
            node_id=node_id,
            run_head_digest=run_head.digest,
            subject_id=kind,
            cone_id=cone_id,
            cone_digest=cone_digest,
        )
        facts = self._append_iteration_fact(current, current.facts, fact)
        facts = FactIndex.model_validate(
            {
                **facts.model_dump(),
                "pending_decision_history": facts.pending_decision_history + (pending,),
            }
        )
        successor = current.model_copy(
            update={"facts": facts, "mode": "paused", "pending_decision": pending}
        )
        self._store.record_escalation(pending, successor)
        return successor

    def apply_user_decision(self, decision: UserDecision) -> RunState:
        if not isinstance(decision, UserDecision):
            raise RuntimeError("only a digest-bound user decision may mutate a paused run")
        current = self.state
        pending = current.pending_decision
        if current.mode != "paused" or pending is None:
            raise RuntimeError("no pending digest-bound user decision exists")
        if decision.pending_decision_digest != pending.digest:
            raise RuntimeError("user decision pending digest does not match current escalation")
        if decision.kind not in (pending.kind, *pending.allowed_kinds):
            raise RuntimeError("user decision kind is not authorized by pending escalation")
        if any(item.decision_id == decision.decision_id for item in current.facts.user_decisions):
            raise RuntimeError("user decision was already applied")

        limits = current.limits
        mode: Literal["running", "inconclusive", "cancelled"] = "running"
        if decision.kind == "limit_amendment":
            assert decision.limit_name is not None and decision.limit_amount is not None
            limits = limits.append_widening(
                name=decision.limit_name,
                amount=decision.limit_amount,
                approver=decision.actor,
                reason=decision.reason,
                effective_graph_revision=len(self._store.read_events()),
            )
        elif decision.kind == "terminalization":
            mode = "inconclusive"
        elif decision.kind == "cancellation":
            mode = "cancelled"

        facts = FactIndex.model_validate(
            {
                **current.facts.model_dump(),
                "user_decisions": current.facts.user_decisions + (decision,),
            }
        )
        successor = current.model_copy(
            update={
                "facts": facts,
                "limits": limits,
                "pending_decision": None,
                "mode": mode,
            }
        )
        self._store.record_user_decision(decision, successor)
        return successor

    @staticmethod
    def _with_facts(state: RunState, facts: FactIndex) -> RunState:
        return state.model_copy(update={"facts": facts})

    @staticmethod
    def _require_active(state: RunState) -> None:
        if state.mode not in {"running", "final_replay"}:
            raise RuntimeError("product work requires running or final_replay mode")

    def _issue_work_authorization(
        self,
        current: RunState,
        *,
        kind: Literal["discovery", "repair", "proof", "process", "agent"],
        operation_id: str,
        operation_digest: str,
        node_id: str,
        cone_id: str,
        cone_digest: str,
        expected_work: ProductWorkReceipt,
    ) -> WorkAuthorization:
        try:
            expected = ProductWorkReceipt.model_validate(expected_work.model_dump())
        except (AttributeError, ValidationError) as error:
            raise RuntimeError("exact expected product work counters are required") from error
        if any(
            value is not None
            for value in (
                expected.authorization_id,
                expected.authorization_digest,
                expected.operation_id,
            )
        ):
            raise RuntimeError("caller may not recycle an issued product work receipt")
        if (
            expected.kind != kind
            or expected.node_id != node_id
            or expected.cone_id != cone_id
            or expected.cone_digest != cone_digest
        ):
            raise RuntimeError("work kind and cone must be derived from operation authority")
        trajectory_digest, derived_spine_digest, landmark_mapping_digest = (
            self._authority_digests(current)
        )
        authorization = WorkAuthorization(
            authorization_id=digest_for(
                "work-authorization-id",
                {
                    "run_id": current.run_id,
                    "operation_id": operation_id,
                    "operation_digest": operation_digest,
                    "kind": kind,
                    "node_id": node_id,
                    "cone_id": cone_id,
                    "cone_digest": cone_digest,
                    "trajectory_digest": trajectory_digest,
                    "derived_spine_digest": derived_spine_digest,
                    "landmark_mapping_digest": landmark_mapping_digest,
                    "expected_counters": expected.counters,
                },
            ),
            operation_id=operation_id,
            operation_digest=operation_digest,
            kind=kind,
            run_id=current.run_id,
            node_id=node_id,
            cone_id=cone_id,
            cone_digest=cone_digest,
            trajectory_digest=trajectory_digest,
            derived_spine_digest=derived_spine_digest,
            landmark_mapping_digest=landmark_mapping_digest,
            expected_counters=expected.counters,
        )
        return self._work_receipts.authorize(authorization)

    def _append_iteration_fact(
        self, current: RunState, facts: FactIndex, fact: IterationFact
    ) -> FactIndex:
        run_head = current.facts.run_head
        if run_head is None or fact.run_head_digest != run_head.digest:
            raise RuntimeError("progress fact must bind current Run Head")
        facts = self._bind_canonical_cone_identity(
            current, facts, fact.node_id, fact.cone_id
        )
        if any(item.fact_id == fact.fact_id or item.digest == fact.digest for item in facts.iteration_facts):
            raise RuntimeError("repeated progress fact is not active progress")
        if any(
            item.fact_class == fact.fact_class
            and item.node_id == fact.node_id
            and item.run_head_digest == fact.run_head_digest
            and item.subject_id == fact.subject_id
            and item.cone_id == fact.cone_id
            for item in facts.iteration_facts
        ):
            raise RuntimeError("repeated progress fact is not active progress")
        if fact.fact_class == "new_hop" and any(
            item.fact_class == "new_hop"
            and item.cone_id == fact.cone_id
            and item.subject_id == fact.subject_id
            for item in facts.iteration_facts
        ):
            raise RuntimeError("previously examined causal hop cannot count as progress")
        stale_verified_ids = {
            stale_id
            for reopen in self._open_replay_reopens(current.facts)
            for stale_id in reopen.stale_verified_fact_ids
        }
        if fact.fact_class == "verified_node" and any(
            item.fact_class == "verified_node"
            and item.node_id == fact.node_id
            and item.run_head_digest == fact.run_head_digest
            and item.fact_id not in stale_verified_ids
            for item in facts.iteration_facts
        ):
            raise RuntimeError("verified node is already recorded on current Run Head")
        if fact.stall_fingerprint is not None and any(
            item.stall_fingerprint == fact.stall_fingerprint
            for item in facts.iteration_facts
        ):
            raise RuntimeError("identical stall fingerprint rejects repeated repair work")
        return FactIndex.model_validate(
            {
                **facts.model_dump(),
                "iteration_facts": facts.iteration_facts + (fact,),
            }
        )

    @staticmethod
    def _append_failure_evidence(
        facts: FactIndex,
        repair: RepairAttempt,
        proof_spec: ProofSpec,
        proof_result: ProofResult,
        reviewer_manifest: RoleManifest,
        classification: ChangeClassificationArtifact,
        consumption: UserAuthorizationConsumption | None,
    ) -> FactIndex:
        if any(item.attempt_id == repair.attempt_id for item in facts.repairs):
            raise RuntimeError("repair attempt is already recorded")
        if any(item.proof_spec_id == proof_spec.proof_spec_id for item in facts.proof_specs):
            raise RuntimeError("ProofSpec is already recorded")
        if any(item.proof_result_id == proof_result.proof_result_id for item in facts.proof_results):
            raise RuntimeError("proof result is already recorded")
        if any(
            item.artifact_id == classification.artifact_id
            or item.digest == classification.digest
            for item in facts.change_classification_artifacts
        ):
            raise RuntimeError("independent classification artifact is already recorded")
        manifests = facts.role_manifests
        if not any(item.digest == reviewer_manifest.digest for item in manifests):
            manifests += (reviewer_manifest,)
        consumptions = facts.user_authorization_consumptions
        if consumption is not None:
            consumptions += (consumption,)
        return FactIndex.model_validate(
            {
                **facts.model_dump(),
                "repairs": facts.repairs + (repair,),
                "proof_specs": facts.proof_specs + (proof_spec,),
                "proof_results": facts.proof_results + (proof_result,),
                "role_manifests": manifests,
                "change_classification_artifacts": (
                    facts.change_classification_artifacts + (classification,)
                ),
                "user_authorization_consumptions": consumptions,
            }
        )

    def _pause(
        self,
        current: RunState,
        *,
        node_id: str,
        cone_id: str,
        cone_digest: str,
        consumed_limits: tuple[str, ...],
        fingerprint: StallFingerprint | None,
        facts: FactIndex | None = None,
    ) -> RuntimeProgress:
        if current.pending_decision is not None:
            raise RuntimeError("run already has a pending digest-bound user decision")
        run_head = current.facts.run_head
        if run_head is None:
            raise RuntimeError("diagnostic stall requires a current Run Head")
        pause_facts = facts if facts is not None else current.facts
        requested_decisions = (
            "limit_amendment",
            "scope_authorization",
            "access",
            "terminalization",
            "cancellation",
        )
        report = PauseReport(
            node_id=node_id,
            reason="diagnostic_stall",
            cone_id=cone_id,
            cone_digest=cone_digest,
            consumed_limits=consumed_limits,
            consumed_limit_values=self._consumed_limit_values(
                current, pause_facts, cone_id, consumed_limits
            ),
            expected_behavior=tuple(
                item.statement for item in current.trajectory.expected_behaviors
            ),
            failure_evidence_refs=(
                tuple(
                    f"proof-result:{item.proof_result_id}:{item.digest}"
                    for item in pause_facts.proof_results
                )
                or ("failure-evidence:none-recorded",)
            ),
            causal_graph_refs=(f"causal-cone:{cone_id}:{cone_digest}",),
            attempted_repair_refs=(
                tuple(f"repair:{item.attempt_id}" for item in pause_facts.repairs)
                or ("repair:none-recorded",)
            ),
            causal_radius=max(
                (
                    item.causal_radius
                    for item in pause_facts.product_work
                    if item.cone_id == cone_id
                ),
                default=0,
            ),
            widening_used=sum(
                item.widening_allowance
                for item in pause_facts.product_work
                if item.cone_id == cone_id
            ),
            reasoning_tier=max(
                (
                    item.reasoning_tier
                    for item in pause_facts.iteration_facts
                    if item.cone_id == cone_id
                ),
                default=0,
            ),
            no_safe_action_rationale=(
                "No unexamined causal hop remains within current limits and authority."
            ),
            requested_decisions=requested_decisions,
            smallest_decisions=requested_decisions,
        )
        from .models import PendingDecision

        pending = PendingDecision(
            decision_id=f"diagnostic-stall:{cone_digest}:{len(current.facts.iteration_facts) + 1}",
            cone_id=cone_id,
            cone_digest=cone_digest,
            kind="limit_amendment",
            question="Choose a bounded limit amendment, access/scope authorization, terminalization, or cancellation.",
            evidence_refs=(f"pause:{cone_digest}",),
            allowed_kinds=(
                "scope_authorization",
                "access",
                "terminalization",
                "cancellation",
            ),
        )
        fact = IterationFact(
            fact_id=f"pause:{cone_digest}:{len(current.facts.iteration_facts) + 1}",
            fact_class="pause",
            node_id=node_id,
            run_head_digest=run_head.digest,
            subject_id=report.digest,
            cone_id=cone_id,
            cone_digest=cone_digest,
            stall_fingerprint=fingerprint,
        )
        facts = self._append_iteration_fact(current, pause_facts, fact)
        facts = FactIndex.model_validate(
            {
                **facts.model_dump(),
                "pending_decision_history": facts.pending_decision_history + (pending,),
                "pause_reports": facts.pause_reports + (report,),
                "pause_report": report,
            }
        )
        successor = current.model_copy(
            update={"facts": facts, "mode": "paused", "pending_decision": pending}
        )
        self._store.record_diagnostic_stall(report, successor)
        return RuntimeProgress(successor, fact)

    @staticmethod
    def _limit(state: RunState, name: str) -> int:
        return state.limits.active.value_for(name).amount

    def _require_repair_authority(
        self,
        current: RunState,
        repair: RepairAttempt,
        cone: CausalCone,
        classification: ChangeClassificationArtifact,
    ) -> UserAuthorizationConsumption | None:
        expected = {
            "run_id": current.run_id,
            "node_id": cone.node_id,
            "cone_id": cone.cone_id,
            "cone_digest": cone.digest,
            "goal_digest": current.trajectory_digest,
            "envelope_digest": current.trajectory.execution_envelope.digest,
            "repair_hypothesis": repair.hypothesis,
            "changed_dependencies": repair.changed_dependencies,
            "changed_files": repair.changed_files,
            "change_kind": repair.change_kind,
            "trajectory_digest": current.trajectory_digest,
            "derived_spine_digest": self._authority_digests(current)[1],
            "landmark_mapping_digest": self._authority_digests(current)[2],
        }
        if any(getattr(classification, name) != value for name, value in expected.items()):
            raise RuntimeError("independent classification artifact does not bind exact repair")
        if classification.reviewer_role != "independent_change_reviewer":
            raise RuntimeError("independent classification reviewer role is required")
        required_kind = {
            "behavior": "behavior_authorization",
            "architecture": "architecture_authorization",
            "external_contract": "external_contract_authorization",
        }.get(repair.change_kind)
        if required_kind is None:
            return None
        pending_by_digest = {
            pending.digest: pending for pending in current.facts.pending_decision_history
        }
        decisions = tuple(
            item
            for item in current.facts.user_decisions
            if item.classification_digest == classification.digest
            and item.change_digest == classification.change_digest
        )
        decision = decisions[0] if len(decisions) == 1 else None
        if decision is None:
            has_contextual_authorization = any(
                item.kind == required_kind
                and (
                    pending := pending_by_digest.get(item.pending_decision_digest)
                ) is not None
                and pending.cone_id == cone.cone_id
                and pending.cone_digest == cone.digest
                for item in current.facts.user_decisions
            )
            if has_contextual_authorization:
                raise RuntimeError("user authorization does not bind exact classification")
            raise RuntimeError(
                f"{repair.change_kind} change requires explicit user authorization"
            )
        pending = (
            pending_by_digest.get(decision.pending_decision_digest)
            if decision is not None
            else None
        )
        if (
            pending is None
            or decision.kind != required_kind
            or pending.cone_id != cone.cone_id
            or pending.cone_digest != cone.digest
        ):
            raise RuntimeError(
                f"{repair.change_kind} change requires explicit user authorization"
            )
        if (
            decision.classification_digest != classification.digest
            or decision.change_digest != classification.change_digest
        ):
            raise RuntimeError("user authorization does not bind exact classification")
        if any(
            item.decision_digest == decision.digest
            for item in current.facts.user_authorization_consumptions
        ):
            raise RuntimeError("exact user authorization is already consumed")
        return UserAuthorizationConsumption(
            decision_digest=decision.digest,
            classification_digest=classification.digest,
            change_digest=classification.change_digest,
        )

    def _require_issued_classification(
        self,
        classification: ChangeClassificationArtifact | None,
        receipt_id: str | None,
        receipt_digest: str | None,
    ) -> _IssuedClassificationReceipt:
        if classification is not None:
            raise RuntimeError(
                "issued independent classification receipt identity and digest are required"
            )
        if not isinstance(receipt_id, str) or not isinstance(receipt_digest, str):
            raise RuntimeError(
                "issued independent classification receipt identity and digest are required"
            )
        return self._classification_receipts.resolve(receipt_id, receipt_digest)

    def _consumed_limit_values(
        self,
        current: RunState,
        facts: FactIndex,
        cone_id: str,
        names: tuple[str, ...],
    ) -> tuple[LimitConsumption, ...]:
        cone_receipts = tuple(
            item for item in facts.product_work if item.cone_id == cone_id
        )
        cone_iterations = tuple(
            item for item in facts.iteration_facts if item.cone_id == cone_id
        )
        values: dict[str, int] = {
            "causal_radius": max(
                (item.causal_radius for item in cone_receipts), default=0
            ),
            "failed_repair_cycles": sum(
                item.cone_id == cone_id for item in facts.repairs
            ),
            "diagnostic_widening": sum(
                item.widening_allowance for item in cone_receipts
            ),
            "reasoning_escalation": max(
                (item.reasoning_tier for item in cone_iterations), default=0
            ),
            "discovery_commands": sum(
                item.command_count for item in cone_receipts if item.kind == "discovery"
            ),
            "discovery_duration": sum(
                item.completed_duration_ms
                for item in cone_receipts
                if item.kind == "discovery"
            ),
        }
        return tuple(
            LimitConsumption(limit_name=name, consumed=values.get(name, 0))
            for name in names
        )

    def _enforce_work_limits(self, current: RunState, receipt: ProductWorkReceipt) -> None:
        receipts = current.facts.product_work + (receipt,)
        cone_receipts = tuple(
            item for item in receipts if item.cone_id == receipt.cone_id
        )
        kind_cone_receipts = tuple(
            item for item in cone_receipts if item.kind == receipt.kind
        )

        def total(values: tuple[ProductWorkReceipt, ...], field: str) -> int:
            return sum(getattr(item, field) for item in values)

        def require(name: str, value: int) -> None:
            if value > self._limit(current, name):
                raise RuntimeError(f"Run Limit exhausted: {name}")

        require("global_work_commands", total(receipts, "command_count"))
        require(
            "global_work_duration",
            current.facts.completed_duration_ms + receipt.completed_duration_ms,
        )
        for output_bytes in receipt.command_output_bytes:
            require("artifact_output_per_command", output_bytes)
        require("artifact_output_per_run", total(receipts, "output_bytes"))
        require("agent_dispatches_per_run", total(receipts, "agent_dispatches"))
        require("model_calls_per_run", total(receipts, "model_calls"))
        require("model_reasoning_tokens_per_run", total(receipts, "reasoning_tokens"))
        require(
            "model_reasoning_cost_per_run",
            total(receipts, "normalized_provider_cost"),
        )
        require("causal_radius", receipt.causal_radius)
        require("agent_dispatches_per_cone", total(cone_receipts, "agent_dispatches"))
        require("model_calls_per_cone", total(cone_receipts, "model_calls"))
        require(
            "model_reasoning_tokens_per_cone", total(cone_receipts, "reasoning_tokens")
        )
        require(
            "model_reasoning_cost_per_cone",
            total(cone_receipts, "normalized_provider_cost"),
        )
        require(
            "diagnostic_widening", total(cone_receipts, "widening_allowance")
        )
        require("repair_attempts", total(cone_receipts, "repair_attempts"))
        if receipt.kind == "discovery":
            require("discovery_commands", total(kind_cone_receipts, "command_count"))
            require(
                "discovery_duration",
                total(kind_cone_receipts, "completed_duration_ms"),
            )
        if receipt.kind == "repair":
            require("repair_commands", total(kind_cone_receipts, "command_count"))
            require("repair_duration", total(kind_cone_receipts, "completed_duration_ms"))

    @staticmethod
    def _bind_canonical_cone_identity(
        state: RunState,
        facts: FactIndex,
        node_id: str,
        cone_id: str,
    ) -> FactIndex:
        bindings = tuple(
            binding
            for binding in facts.cone_identity_bindings
            if binding.run_id == state.run_id and binding.node_id == node_id
        )
        if bindings:
            if len(bindings) != 1 or bindings[0].cone_id != cone_id:
                raise RuntimeError("canonical cone identity rejects caller alias")
            return facts
        binding = ConeIdentityBinding(
            run_id=state.run_id,
            node_id=node_id,
            cone_id=cone_id,
        )
        return FactIndex.model_validate(
            {
                **facts.model_dump(),
                "cone_identity_bindings": facts.cone_identity_bindings + (binding,),
            }
        )


class RealRuntimeController:
    """V5.2 runtime. Reopens only persisted real-system authority."""

    def __init__(self, store: RealSystemRunStore) -> None:
        self._store = store
        self._registered_adapters: dict[int, object] = {}

    @classmethod
    def _start_admitted(
        cls,
        *,
        root: str | Path,
        initial_state: V52RunState,
        manifest: object,
        baseline_nodes: tuple[DerivedBehavioralNode, ...],
        baseline_proposals: tuple[BaselineNodeProposal, ...] = (),
        provider_authority: AdmittedProviderAuthority | None = None,
        supervisor_receipts: tuple[SupervisorAuthorityReceipt, ...] = (),
        egress_receipt: EgressGateReceipt | None = None,
    ) -> "RealRuntimeController":
        """Atomically admit one manifest and sealed environment before any adapter exists."""

        if not isinstance(initial_state, V52RunState):
            raise RuntimeError("real runtime start requires strict V52RunState")
        if initial_state.mode != "running":
            raise RuntimeError("real runtime start requires a running admitted state")
        store = RealSystemRunStore.open(root, initial_state.run_id)
        store.initialize(
            initial_state,
            manifest=manifest,
            baseline_nodes=baseline_nodes,
            baseline_proposals=baseline_proposals,
            provider_authority=provider_authority,
            supervisor_receipts=supervisor_receipts,
            egress_receipt=egress_receipt,
        )
        return cls(store)

    @classmethod
    def start_from_confirmed_bundle(
        cls,
        *,
        root: Path,
        bundle: "ConfirmedRealTrajectoryBundle",
        manifest: "AdapterManifest",
    ) -> "RealRuntimeController":
        """Admit canonical authority; caller supplies no runtime capability."""

        from .admission import RealAdmissionCoordinator

        return RealAdmissionCoordinator.start(root=root, bundle=bundle, manifest=manifest)

    @classmethod
    def open(cls, *, root: str | Path, run_id: str) -> "RealRuntimeController":
        return cls(RealSystemRunStore.open(root, run_id))

    @classmethod
    def open_readonly(cls, *, root: str | Path, run_id: str) -> "RealRuntimeController":
        """Open a V5.2 status projection without recovery or mutation."""

        return cls(RealSystemRunStore.open_readonly(root, run_id))

    @classmethod
    def read_only_status(
        cls, *, root: Path, run_id: str
    ) -> RealRunStatusProjection:
        """Read persisted V5.2 status without recovery or adapter construction."""

        try:
            return cls.open_readonly(root=root, run_id=run_id).status_projection()
        except RecoveryError:
            return RealRunStatusProjection(
                mode="recovery_pending",
                recommended_baseline_node_id=None,
                next_executable_node_id=None,
                active_explorations=(),
                remaining_budget=(),
                pending_decision_kind=None,
            )

    @property
    def state(self) -> V52RunState:
        return self._store.read_state()

    @property
    def manifest(self) -> object:
        return self._store.admitted_manifest()

    @property
    def environment_snapshot(self) -> object:
        return self._store.environment_snapshot()

    def _construct_adapter_for_test(
        self,
        *,
        service_bridge: object | None = None,
        fixture_adapter: object | None = None,
    ) -> object:
        """Choose a fixed adapter factory from admitted store bytes only."""

        from .adapters import construct_registered_adapter
        from .adapters.manifest import AdapterManifest

        manifest = self._store.admitted_manifest()
        if not isinstance(manifest, AdapterManifest):
            raise RuntimeError("persisted adapter manifest is invalid")
        adapter = construct_registered_adapter(
            manifest,
            service_bridge=service_bridge,
            fixture_adapter=fixture_adapter,
            sealed_environment_snapshot=self._sealed_environment_snapshot(),
        )
        self._registered_adapters[id(adapter)] = adapter
        return adapter

    def run_next_persisted_slice(
        self, *, max_nodes: int = 1
    ) -> RealRuntimeSliceResult:
        """Resolve one sealed store node, then derive every dispatch input locally."""

        if type(max_nodes) is not int or max_nodes != 1:
            raise RuntimeError("real runtime executes exactly one sealed node per bounded slice")
        if self.state.mode != "running":
            raise RuntimeError("real runtime requires a running persisted run")
        authority = self._store.next_executable_authority()
        if authority is None:
            raise RuntimeError("real runtime has no persisted executable node")
        node = authority.node
        if node.action_kind == "verify_only":
            adapter = self._construct_adapter_from_persisted_provider()
            self._require_live_adapter_snapshot(adapter)
            return self._run_verification_slice(adapter, node)
        intent = self._derive_persisted_operation_intent(authority)
        blocked = self._reserve_effectful_intent_or_block(node, intent)
        if blocked is not None:
            return blocked
        try:
            adapter = self._construct_adapter_from_persisted_provider()
            self._require_live_adapter_snapshot(adapter)
        except Exception:
            self._store.reconcile_unsettled_intents()
            raise
        return self._dispatch_reserved_effectful_slice(adapter, node, intent)

    def apply_real_system_decision(self, decision: object) -> V52RunState:
        """Consume one exact V5.2 exceptional decision through runtime seam."""

        try:
            return self._store.apply_real_system_decision(decision)
        except StoreError as exc:
            raise RuntimeError(str(exc)) from exc

    def _construct_adapter_from_persisted_provider(self) -> object:
        """Construct only compiled provider selected by persisted admission facts."""

        from .adapters.host_registry import HostProviderError, resolve_host_provider
        from .adapters.manifest import AdapterManifest
        from .models import AdmittedProviderAuthority

        manifest = self._store.admitted_manifest()
        authority = self.state.facts.provider_authority
        if not isinstance(manifest, AdapterManifest) or not isinstance(
            authority, AdmittedProviderAuthority
        ):
            raise RuntimeError("persisted provider authority is invalid")
        try:
            provider = resolve_host_provider(manifest.adapter_id)
            adapter = provider.construct_adapter(
                manifest=manifest,
                authority=authority,
                snapshot=self._sealed_environment_snapshot(),
            )
        except HostProviderError as exc:
            raise RuntimeError("persisted provider cannot construct admitted adapter") from exc
        self._registered_adapters[id(adapter)] = adapter
        return adapter

    def _derive_persisted_operation_intent(
        self, authority: "PersistedNodeExecutionAuthority"
    ) -> ExternalOperationIntent:
        """Bind one effect to canonical node/proposal/budget bytes only."""
        from .models import derive_persisted_external_operation_intent

        try:
            return derive_persisted_external_operation_intent(self.state, authority)
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc

    def _run_verification_slice(
        self, adapter: object, node: DerivedBehavioralNode
    ) -> RealRuntimeSliceResult:
        """Persist readonly evidence as completion; verification never creates intent."""

        from .models import Observation, RealNodeCompletion

        try:
            observation = adapter.observe_readonly(node)  # type: ignore[attr-defined]
        except Exception as exc:
            raise RuntimeError("registered adapter readonly observation failed") from exc
        if (
            not isinstance(observation, Observation)
            or observation.kind != "behavioral"
            or observation.node_id != node.source_anchor_id
            or observation.run_head_digest != node.run_head_digest
            or not observation.evidence_refs
        ):
            raise RuntimeError("verification observation does not bind sealed node")
        self._store.record_node_completion(
            RealNodeCompletion(
                run_id=node.run_id,
                node_id=node.node_id,
                run_head_digest=node.run_head_digest,
                kind="verification",
                evidence_refs=observation.evidence_refs,
                verification_observation=observation,
            )
        )
        return RealRuntimeSliceResult(
            state=self.state, receipt=None, node_id=node.node_id
        )

    def _run_bounded_slice_for_test(
        self,
        *,
        adapter: object,
        node: DerivedBehavioralNode,
        operation_intent: ExternalOperationIntent,
        max_nodes: int = 1,
    ) -> RealRuntimeSliceResult:
        return self._run_bounded_slice(
            adapter=adapter,
            node=node,
            operation_intent=operation_intent,
            max_nodes=max_nodes,
        )

    def _run_bounded_slice(
        self,
        *,
        adapter: object,
        node: DerivedBehavioralNode,
        operation_intent: ExternalOperationIntent,
        max_nodes: int = 1,
    ) -> RealRuntimeSliceResult:
        """Private supplied-argument primitive retained for focused legacy tests."""

        if type(max_nodes) is not int or max_nodes != 1:
            raise RuntimeError("real runtime executes exactly one sealed node per bounded slice")
        if not isinstance(node, DerivedBehavioralNode):
            raise RuntimeError("real runtime requires a sealed DerivedBehavioralNode")
        if not isinstance(operation_intent, ExternalOperationIntent):
            raise RuntimeError("real runtime requires ExternalOperationIntent")
        blocked = self._reserve_effectful_intent_or_block(node, operation_intent)
        if blocked is not None:
            return blocked
        try:
            self._require_live_adapter_snapshot(adapter)
        except Exception:
            self._store.reconcile_unsettled_intents()
            raise
        return self._dispatch_reserved_effectful_slice(adapter, node, operation_intent)

    def _reserve_effectful_intent_or_block(
        self,
        node: DerivedBehavioralNode,
        operation_intent: ExternalOperationIntent,
    ) -> RealRuntimeSliceResult | None:
        """Persist exact effect authority, or durably block before adapter use."""

        node_authority = self._store.require_authorized_node(node)
        self._store.validate_intent_for_authorized_node(operation_intent, node_authority)
        try:
            self._store.record_external_intent(operation_intent)
        except BudgetReservationExceeded:
            self._store.record_manifest_budget_exhaustion(operation_intent)
            return RealRuntimeSliceResult(
                state=self.state, receipt=None, node_id=node.node_id
            )
        return None

    def _dispatch_reserved_effectful_slice(
        self,
        adapter: object,
        node: DerivedBehavioralNode,
        operation_intent: ExternalOperationIntent,
    ) -> RealRuntimeSliceResult:
        """Dispatch only after persisted reservation and live snapshot validation."""

        try:
            receipt = adapter.act(node, operation_intent=operation_intent)  # type: ignore[attr-defined]
        except Exception:
            self._store.reconcile_unsettled_intents()
            raise
        try:
            if not isinstance(receipt, ExternalOperationReceipt):
                raise RuntimeError("real adapter must return strict ExternalOperationReceipt")
            self._store.record_external_receipt(receipt)
        except Exception:
            self._store.reconcile_unsettled_intents()
            raise
        if receipt.status != "succeeded":
            self._store.reconcile_unsettled_intents()
        return RealRuntimeSliceResult(
            state=self.state, receipt=receipt, node_id=node.node_id
        )

    def register_evidence_led_exploration(
        self,
        *,
        node: DerivedBehavioralNode,
        parent_node_id: str,
        evidence_refs: tuple[str, ...],
        proposal: BaselineNodeProposal,
    ) -> ExplorationDelta:
        """Persist one within-authority evidence-led branch without a user decision."""

        facts = self.state.facts
        baseline = facts.baseline_spine
        if baseline is None:
            raise RuntimeError("evidence-led exploration requires admitted baseline authority")
        authority: object | None = baseline if parent_node_id in baseline.node_ids else None
        if authority is None:
            authority = next(
                (delta for delta in facts.exploration_deltas if delta.node.node_id == parent_node_id),
                None,
            )
        if authority is None:
            raise RuntimeError("evidence-led exploration parent is not persisted authority")
        try:
            delta = ExplorationDelta.from_node(
                node=node,
                parent_node_id=parent_node_id,
                evidence_refs=evidence_refs,
                authority=authority,
                proposal=proposal,
            )
        except (TypeError, ValueError) as exc:
            raise RuntimeError("evidence-led exploration does not bind admitted authority") from exc
        self._store.record_exploration_delta(delta)
        return delta

    def status_projection(self) -> RealRunStatusProjection:
        """Project durable baseline recommendation and exploration context only."""

        state = self.state
        baseline = state.facts.baseline_spine
        if baseline is None:
            raise RuntimeError("real status requires admitted baseline authority")
        completed_node_ids = {
            completion.node_id for completion in state.facts.node_completions
        }
        recommended = next(
            (node.node_id for node in baseline.nodes if node.node_id not in completed_node_ids),
            None,
        )
        pending = next(
            (
                item
                for item in state.facts.pending_real_system_decisions
                if all(
                    consumption.pending_decision_digest != item.digest
                    for consumption in state.facts.real_system_decision_consumptions
                )
            ),
            None,
        )
        next_authority = (
            self._store.next_executable_authority()
            if state.mode == "running" and pending is None
            else None
        )
        manifest = self.manifest
        budget_fields = (
            ("user_actions", "max_user_actions"),
            ("provider_requests", "max_provider_requests"),
            ("cost_micros", "max_cost_micros"),
            ("requests", "max_requests"),
            ("processes", "max_processes"),
            ("persistence_writes", "max_persistence_writes"),
            ("tokens", "max_tokens"),
            ("duration_ms", "max_duration_ms"),
        )
        budgets = getattr(manifest, "budgets", None)
        if budgets is None:
            raise RuntimeError("persisted adapter manifest lacks bounded budgets")
        remaining_budget = tuple(
            (
                reservation_name,
                getattr(budgets, budget_name)
                - sum(
                    getattr(reservation, reservation_name)
                    for reservation in state.facts.budget_reservations
                ),
            )
            for reservation_name, budget_name in budget_fields
        )
        return RealRunStatusProjection(
            mode=state.mode,
            recommended_baseline_node_id=recommended,
            next_executable_node_id=(
                None if next_authority is None else next_authority.node_id
            ),
            active_explorations=tuple(
                ExplorationStatus(
                    node_id=delta.node.node_id,
                    parent_node_id=delta.parent_node_id,
                    reason=delta.node.derivation_reason,
                    completed=delta.node.node_id in completed_node_ids,
                )
                for delta in state.facts.exploration_deltas
                if delta.node.node_id not in completed_node_ids
            ),
            remaining_budget=remaining_budget,
            pending_decision_kind=None if pending is None else pending.kind,
        )

    def _final_replay_for_test(self, adapter: object) -> RealFinalReplayResult:
        """Verify replay environment against admission bytes before any bridge action."""

        expected = self._sealed_environment_snapshot()
        current = self.state
        replay_snapshot = RealFinalReplaySnapshot.from_state(
            current,
            environment_snapshot=expected,
            manifest=self._store.admitted_manifest(),
        )
        observed = self._live_adapter_snapshot(adapter, allow_drift=True)
        if observed != expected:
            paused = self._store.pause_for_environment_snapshot_drift(observed)
            return RealFinalReplayResult(
                state=paused,
                snapshot=replay_snapshot,
                stop_reason="environment_snapshot_drift",
            )
        self._replay_persisted_completions(adapter, current)
        return RealFinalReplayResult(
            state=current,
            snapshot=replay_snapshot,
        )

    @staticmethod
    def _replay_persisted_completions(adapter: object, state: V52RunState) -> None:
        """Replay completed effects and readonly verifications in persisted order."""

        baseline = state.facts.baseline_spine
        if baseline is None:
            raise RuntimeError("real replay requires admitted baseline authority")
        nodes = {node.node_id: node for node in baseline.nodes}
        nodes.update(
            {delta.node.node_id: delta.node for delta in state.facts.exploration_deltas}
        )
        intents = {
            intent.operation_id: intent
            for intent in state.facts.external_operation_intents
        }
        receipts = {
            receipt.operation_id: receipt
            for receipt in state.facts.external_operation_receipts
        }
        for completion in state.facts.node_completions:
            node = nodes.get(completion.node_id)
            if node is None:
                raise RuntimeError("real replay action lacks persisted authority")
            if completion.kind == "verification":
                persisted = completion.verification_observation
                try:
                    observed = adapter.observe_readonly(node)  # type: ignore[attr-defined]
                except Exception as exc:
                    raise RuntimeError("persisted real replay verification failed") from exc
                if (
                    not isinstance(observed, Observation)
                    or persisted is None
                    or observed.kind != "behavioral"
                    or observed.node_id != node.source_anchor_id
                    or observed.run_head_digest != node.run_head_digest
                    or observed.observed_state != persisted.observed_state
                    or observed.evidence_refs != completion.evidence_refs
                ):
                    raise RuntimeError(
                        "persisted real replay verification does not match authority"
                    )
                continue
            intent = intents.get(completion.operation_id or "")
            receipt = None if intent is None else receipts.get(intent.operation_id)
            if intent is None or receipt is None or intent.node_id != node.node_id:
                raise RuntimeError("real replay action lacks persisted authority")
            try:
                replay_receipt = adapter.act(node, operation_intent=intent)  # type: ignore[attr-defined]
            except Exception as exc:
                raise RuntimeError("persisted real replay action failed") from exc
            if not isinstance(replay_receipt, ExternalOperationReceipt) or replay_receipt != receipt:
                raise RuntimeError("persisted real replay action receipt does not match authority")

    def run_final_replay_from_persisted_authority(self) -> RealFinalReplayResult:
        """Replay with static provider selected by persisted admission facts only."""

        if self.state.mode != "running":
            raise RuntimeError("real runtime requires a running persisted run")
        state = self.state
        consumed = {
            item.pending_decision_digest
            for item in state.facts.real_system_decision_consumptions
        }
        if any(
            pending.digest not in consumed
            for pending in state.facts.pending_real_system_decisions
        ):
            raise RuntimeError("real replay is blocked by a pending exceptional decision")
        return self._final_replay_for_test(self._construct_adapter_from_persisted_provider())

    def _require_live_adapter_snapshot(self, adapter: object) -> None:
        expected = self._sealed_environment_snapshot()
        observed = self._live_adapter_snapshot(adapter)
        if observed != expected:
            self._store.pause_for_environment_snapshot_drift(observed)
            raise RuntimeError("environment snapshot drift paused real-system run")

    def _sealed_environment_snapshot(self) -> object:
        from .environment import EnvironmentSnapshot

        snapshot = self._store.environment_snapshot()
        if not isinstance(snapshot, EnvironmentSnapshot):
            raise RuntimeError("persisted real-system EnvironmentSnapshot is invalid")
        return snapshot

    def _live_adapter_snapshot(
        self, adapter: object, *, allow_drift: bool = False
    ) -> object:
        from .adapters.protocol import AdapterError
        from .environment import EnvironmentSnapshot

        if self._registered_adapters.get(id(adapter)) is not adapter:
            raise RuntimeError("real runtime requires an adapter from persisted registered authority")
        current = self.state
        if (
            getattr(adapter, "adapter_id", None) != self._manifest_adapter_id()
            or getattr(adapter, "manifest_digest", None) != current.adapter_manifest_digest
        ):
            raise RuntimeError("registered adapter does not bind persisted manifest")
        try:
            if allow_drift and hasattr(adapter, "observe_environment_snapshot"):
                snapshot = adapter.observe_environment_snapshot()
            else:
                snapshot = adapter.environment_snapshot()
        except AdapterError:
            raise
        except Exception as exc:
            raise RuntimeError("registered adapter cannot read current environment snapshot") from exc
        if not isinstance(snapshot, EnvironmentSnapshot):
            raise RuntimeError("registered adapter returned invalid EnvironmentSnapshot")
        return snapshot

    def _manifest_adapter_id(self) -> str:
        from .adapters.manifest import AdapterManifest

        manifest = self._store.admitted_manifest()
        if not isinstance(manifest, AdapterManifest):
            raise RuntimeError("persisted adapter manifest is invalid")
        return manifest.adapter_id
