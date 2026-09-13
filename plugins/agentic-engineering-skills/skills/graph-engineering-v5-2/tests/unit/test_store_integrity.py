from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.graph_v5.canonical import canonical_json_bytes, digest_for
from scripts.graph_v5.models import (
    AdmittedProviderAuthority,
    BaselineNodeProposal,
    BaselineSpineAuthority,
    BudgetReservation,
    CleanupDecision,
    DurationDelta,
    EnvironmentIdentity,
    EgressGateReceipt,
    ExplorationDelta,
    HealthReceipt,
    NodeProposal,
    NodeBudgetProposal,
    PersistedNodeExecutionAuthority,
    DerivedBehavioralNode,
    ExternalOperationIntent,
    ExternalOperationReceipt,
    FactIndex,
    LimitValue,
    LandmarkVerification,
    Observation,
    RunLimits,
    ResourceLease,
    RealSystemFactIndex,
    PendingRealSystemDecision,
    RealSystemDecision,
    RealSystemRunHead,
    RealNodeCompletion,
    RuntimeNote,
    ServiceReceipt,
    SupervisorAuthorityReceipt,
    V52RunState,
    V52TrajectoryBrief,
    V52TrajectoryConfirmation,
    VersionedLimits,
    derive_persisted_external_operation_intent,
)
from scripts.graph_v5.store import (
    BudgetReservationExceeded,
    RealSystemLedgerEvent,
    RealSystemRunStore,
    RecoveryError,
    SimulatedCrash,
    StoreError,
    TransactionalRunStore,
)
from scripts.graph_v5.adapters.manifest import AdapterManifest
from scripts.graph_v5.environment import EnvironmentPreflightError, EnvironmentSnapshot
from tests.unit.test_adapter_manifest import manifest_payload
from tests.unit.test_store import event_payload, issue_capability, sample_state


class StoreIntegrityTests(unittest.TestCase):
    def test_initialize_revalidates_constructed_run_state_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            state = sample_state()
            invalid = state.model_copy(update={"pending_decision": 123})
            store = TransactionalRunStore.open(
                root, issue_capability(root, state.run_id)
            )

            with self.assertRaisesRegex(StoreError, "strict RunState schema"):
                store.initialize(invalid)

            self.assertFalse((root / "state.json").exists())
            self.assertFalse((root / "ledger.jsonl").exists())

    def test_append_revalidates_constructed_run_state_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            state = sample_state()
            store = TransactionalRunStore.open(
                root, issue_capability(root, state.run_id)
            )
            store.initialize(state)
            state_before = (root / "state.json").read_bytes()
            invalid = state.model_copy(update={"pending_decision": 123})

            with self.assertRaisesRegex(StoreError, "strict RunState schema"):
                store.append_event("observed", event_payload(), invalid)

            self.assertEqual((root / "state.json").read_bytes(), state_before)
            self.assertFalse((root / "ledger.jsonl").exists())

    def test_rejects_ledger_event_without_record_terminator(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            state = sample_state()
            store = TransactionalRunStore.open(
                root, issue_capability(root, state.run_id)
            )
            store.initialize(state)
            store.append_event(
                "observed",
                event_payload(),
                state,
            )
            ledger_path = root / "ledger.jsonl"
            ledger_path.write_bytes(ledger_path.read_bytes().removesuffix(b"\n"))

            with self.assertRaisesRegex(StoreError, "newline"):
                store.read_events()

    def test_rejects_noncanonical_ledger_event_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            state = sample_state()
            store = TransactionalRunStore.open(
                root, issue_capability(root, state.run_id)
            )
            store.initialize(state)
            store.append_event(
                "observed",
                event_payload(),
                state,
            )
            ledger_path = root / "ledger.jsonl"
            event = json.loads(ledger_path.read_text(encoding="utf-8"))
            ledger_path.write_bytes(json.dumps(event).encode("utf-8") + b"\n")

            with self.assertRaisesRegex(StoreError, "canonical JSON"):
                store.read_events()

    def test_rejects_replacement_of_confirmed_trajectory_brief(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            state = sample_state()
            changed_trajectory = state.trajectory.model_copy(
                update={
                    "terminal_outcome": state.trajectory.terminal_outcome.model_copy(
                        update={"description": "Different product behavior"}
                    )
                }
            )
            successor = state.model_copy(update={"trajectory": changed_trajectory})
            store = TransactionalRunStore.open(
                root, issue_capability(root, state.run_id)
            )
            store.initialize(state)
            state_before = (root / "state.json").read_bytes()

            with self.assertRaisesRegex(StoreError, "Trajectory Brief"):
                store.append_event("decision_applied", event_payload(), successor)

            self.assertEqual((root / "state.json").read_bytes(), state_before)
            self.assertFalse((root / "ledger.jsonl").exists())

    def test_rejects_removal_of_recorded_duration_delta(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            state = sample_state()
            recorded = state.model_copy(
                update={
                    "facts": FactIndex(
                        duration_deltas=(
                            DurationDelta(
                                kind="command",
                                completed_duration_ms=125,
                            ),
                        )
                    )
                }
            )
            successor = recorded.model_copy(update={"facts": FactIndex()})
            store = TransactionalRunStore.open(
                root, issue_capability(root, state.run_id)
            )
            store.initialize(recorded)
            state_before = (root / "state.json").read_bytes()

            with self.assertRaisesRegex(StoreError, "append-only fact history"):
                store.append_event("observed", event_payload(), successor)

            self.assertEqual((root / "state.json").read_bytes(), state_before)
            self.assertFalse((root / "ledger.jsonl").exists())

    def test_rejects_environment_replacement_after_observation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            state = sample_state()
            sealed_environment = EnvironmentIdentity(
                repository_revision="a" * 40,
                runtime="node-22.12.0",
                package_manager="npm-10.9.0",
                lockfile_digest="l" * 64,
                host_fingerprint="h" * 64,
            )
            observed_facts = FactIndex(
                environment=sealed_environment,
                observations=(
                    Observation(
                        observation_id="observation-1",
                        node_id="choose-discipline",
                        kind="behavioral",
                        observed_state="Onboarding form is visible",
                        evidence_refs=("artifact-1",),
                        run_head_digest="r" * 64,
                    ),
                ),
            )
            observed = state.model_copy(update={"facts": observed_facts})
            changed_environment = sealed_environment.model_copy(
                update={"runtime": "node-24.0.0"}
            )
            successor = observed.model_copy(
                update={
                    "facts": observed_facts.model_copy(
                        update={"environment": changed_environment}
                    )
                }
            )
            store = TransactionalRunStore.open(
                root, issue_capability(root, state.run_id)
            )
            store.initialize(observed)
            state_before = (root / "state.json").read_bytes()

            with self.assertRaisesRegex(StoreError, "sealed environment"):
                store.append_event("observed", event_payload(), successor)

            self.assertEqual((root / "state.json").read_bytes(), state_before)
            self.assertFalse((root / "ledger.jsonl").exists())

    def test_rejects_replacement_of_append_only_limits_history(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            state = sample_state()
            active = state.limits.active
            replacement_values = tuple(
                LimitValue(
                    name=value.name,
                    amount=3 if value.name == "causal_radius" else value.amount,
                    unit=value.unit,
                )
                for value in active.values
            )
            replacement = VersionedLimits(
                versions=(
                    RunLimits(
                        version=1,
                        source_profile=active.source_profile,
                        source_digest=active.source_digest,
                        values=replacement_values,
                    ),
                ),
                active_version=1,
            )
            successor = state.model_copy(update={"limits": replacement})
            store = TransactionalRunStore.open(
                root, issue_capability(root, state.run_id)
            )
            store.initialize(state)
            state_before = (root / "state.json").read_bytes()

            with self.assertRaisesRegex(StoreError, "Run Limits history"):
                store.append_event("decision_applied", event_payload(), successor)

            self.assertEqual((root / "state.json").read_bytes(), state_before)
            self.assertFalse((root / "ledger.jsonl").exists())

    def test_rejects_append_when_current_state_is_not_bound_to_ledger_head(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            state = sample_state()
            store = TransactionalRunStore.open(
                root, issue_capability(root, state.run_id)
            )
            store.initialize(state)
            store.append_event(
                "observed",
                event_payload(),
                state,
            )
            ledger_before = (root / "ledger.jsonl").read_bytes()
            tampered = state.with_mode("paused")
            (root / "state.json").write_bytes(canonical_json_bytes(tampered))

            with self.assertRaisesRegex(
                StoreError, "canonical V5 state digest is not bound to ledger head"
            ):
                store.append_event(
                    "paused",
                    event_payload(),
                    tampered,
                )

            self.assertEqual((root / "state.json").read_bytes(), canonical_json_bytes(tampered))
            self.assertEqual((root / "ledger.jsonl").read_bytes(), ledger_before)

    def test_recovers_event_after_partial_ledger_append(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            state = sample_state()
            capability = issue_capability(root, state.run_id)
            store = TransactionalRunStore.open(root, capability)
            store.initialize(state)
            real_append = store._append_bytes

            def append_prefix_then_fail(path: Path, payload: bytes) -> None:
                real_append(path, payload[: len(payload) // 2])
                raise OSError("injected partial ledger write")

            with (
                patch.object(store, "_append_bytes", append_prefix_then_fail),
                self.assertRaisesRegex(OSError, "injected partial ledger write"),
            ):
                store.append_event(
                    "observed",
                    event_payload(),
                    state,
                )

            recovered = TransactionalRunStore.open(root, capability)

            self.assertEqual(recovered.read_state().mode, "boot")
            self.assertEqual(len(recovered.read_events()), 1)
            self.assertFalse((root / "journal.json").exists())

    def test_rejects_schema_valid_state_tampered_after_ledger_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            state = sample_state()
            store = TransactionalRunStore.open(root, issue_capability(root, state.run_id))
            store.initialize(state)
            store.append_event(
                "observed",
                event_payload(),
                state,
            )
            tampered = json.loads((root / "state.json").read_text(encoding="utf-8"))
            tampered["mode"] = "paused"
            (root / "state.json").write_text(
                json.dumps(tampered, sort_keys=True, separators=(",", ":")), encoding="utf-8"
            )

            with self.assertRaises(StoreError):
                store.read_state()

    def test_rejects_tampered_event_digest_before_projecting_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            state = sample_state()
            store = TransactionalRunStore.open(root, issue_capability(root, state.run_id))
            store.initialize(state)
            store.append_event(
                "observed",
                event_payload(),
                state,
            )
            event = json.loads((root / "ledger.jsonl").read_text(encoding="utf-8"))
            event["event_digest"] = "f" * 64
            (root / "ledger.jsonl").write_text(
                json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
            )

            with self.assertRaises(StoreError):
                store.read_events()

    def test_rejects_journal_state_not_bound_to_event_before_state_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            state = sample_state()
            capability = issue_capability(root, state.run_id)
            store = TransactionalRunStore.open(root, capability)
            store.initialize(state)
            before = (root / "state.json").read_bytes()

            with self.assertRaises(SimulatedCrash):
                store.append_event(
                    "observed",
                    event_payload(),
                    state,
                    interrupt_after="journal_written",
                )

            journal_path = root / "journal.json"
            journal = json.loads(journal_path.read_text(encoding="utf-8"))
            journal["state_bytes_b64"] = base64.b64encode(
                canonical_json_bytes(state.with_mode("paused"))
            ).decode("ascii")
            journal_path.write_bytes(canonical_json_bytes(journal))

            with self.assertRaises(RecoveryError):
                TransactionalRunStore.open(root, capability)

            self.assertEqual((root / "state.json").read_bytes(), before)
            self.assertFalse((root / "ledger.jsonl").exists())

    def test_stale_lock_file_does_not_block_new_process(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            root.mkdir(parents=True)
            (root / ".graph-v5.lock").write_text("stale", encoding="ascii")
            state = sample_state()
            store = TransactionalRunStore.open(
                root, issue_capability(root, state.run_id)
            )

            try:
                with (
                    patch(
                        "scripts.graph_v5.store.time.monotonic",
                        side_effect=(0.0, 6.0),
                    ),
                    patch("scripts.graph_v5.store.time.sleep"),
                ):
                    store.initialize(state)
            except StoreError as exc:
                self.fail(f"stale lock file blocked recovery: {exc}")

            self.assertEqual(store.read_state(), state)

    def test_rejects_artifact_not_bound_to_domain_and_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            state = sample_state()
            store = TransactionalRunStore.open(
                root, issue_capability(root, state.run_id)
            )
            store.initialize(state)

            try:
                with self.assertRaisesRegex(StoreError, "content digest mismatch"):
                    store.put_artifact_at_digest("proof", "f" * 64, b"{}")
            except TypeError:
                self.fail("artifact writer lacks domain binding")

    def test_rejects_non_hex_artifact_address_before_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            state = sample_state()
            store = TransactionalRunStore.open(
                root, issue_capability(root, state.run_id)
            )
            store.initialize(state)

            try:
                with self.assertRaisesRegex(
                    StoreError, "SHA-256 hexadecimal string"
                ):
                    store.read_artifact("proof", "g" * 64)
            except TypeError:
                self.fail("artifact reader lacks domain binding")


class RealSystemStoreIntegrityTests(unittest.TestCase):
    @staticmethod
    def _node_proposal(
        manifest: AdapterManifest,
        *,
        node_id: str = "node-1",
        action: str = "Submit synthetic checkout form",
    ) -> NodeProposal:
        return NodeProposal(
            node_id=node_id,
            source_anchor_id="start",
            target_landmark_id="checkout",
            action_kind="act",
            action_or_probe=action,
            expected_before=("Synthetic checkout form is visible",),
            expected_after=("Synthetic checkout result is visible",),
            derivation_reason="Confirmed checkout trajectory",
            authority_refs=("trajectory:checkout",),
            execution_scope="synthetic checkout fixture",
            side_effect="bridge:act",
            target_systems=(manifest.target.host,),
        )

    @classmethod
    def _baseline_node(
        cls,
        state: V52RunState,
        manifest: AdapterManifest,
        snapshot: EnvironmentSnapshot,
        *,
        node_id: str = "node-1",
        action: str = "Submit synthetic checkout form",
    ) -> DerivedBehavioralNode:
        run_head = RealSystemRunHead(
            run_id=state.run_id,
            manifest_digest=manifest.digest,
            environment_snapshot_digest=snapshot.digest,
        )
        return DerivedBehavioralNode.seal(
            cls._node_proposal(manifest, node_id=node_id, action=action),
            entry_observation_refs=("observation:checkout-entry",),
            run_id=state.run_id,
            trajectory_digest=state.trajectory.digest,
            run_head_digest=run_head.digest,
            execution_envelope_digest=state.trajectory.execution_envelope.digest,
        )

    @classmethod
    def _baseline_proposal(
        cls,
        manifest: AdapterManifest,
        *,
        node_id: str = "node-1",
        action: str = "Submit synthetic checkout form",
    ) -> BaselineNodeProposal:
        return BaselineNodeProposal(
            proposal=cls._node_proposal(manifest, node_id=node_id, action=action),
            entry_observation_refs=("observation:checkout-entry",),
            budget=NodeBudgetProposal(
                max_user_actions=1,
                max_provider_requests=1,
                max_cost_micros=1,
                max_requests=1,
                max_bytes=1_024,
                max_wall_seconds=10,
            ),
        )

    @staticmethod
    def _egress_receipt(
        state: V52RunState, manifest: AdapterManifest
    ) -> EgressGateReceipt:
        return EgressGateReceipt(
            run_id=state.run_id,
            adapter_manifest_digest=manifest.digest,
            target_identity_digest=state.trajectory.execution_envelope.target_identity_digest,
            allowed_hosts=manifest.egress.hosts,
            allowed_protocols=("https",),
            issued_receipt_digest=digest_for(
                "egress-enforcement-receipt", manifest.egress.enforcement_receipt
            ),
        )

    @staticmethod
    def _provider_authority(
        state: V52RunState, manifest: AdapterManifest
    ) -> AdmittedProviderAuthority:
        return AdmittedProviderAuthority(
            schema_version="graph-v5.admitted-provider-authority.v1",
            adapter_id=manifest.adapter_id,
            provider_id="service-host-provider.v1",
            source_identity_digest=(
                state.trajectory.execution_envelope.target_identity_digest
            ),
        )

    def _initialize(
        self,
        store: RealSystemRunStore,
        state: V52RunState,
        manifest: AdapterManifest,
        *,
        baseline_proposal: BaselineNodeProposal | None = None,
    ) -> V52RunState:
        egress = self._egress_receipt(state, manifest)
        snapshot = EnvironmentSnapshot.from_admitted_authority(
            manifest=manifest,
            target_identity_digest=state.trajectory.execution_envelope.target_identity_digest,
            supervisor_receipts=(),
            egress_receipt=egress,
        )
        node = self._baseline_node(state, manifest, snapshot)
        return store.initialize(
            state,
            manifest=manifest,
            baseline_nodes=(node,),
            baseline_proposals=(
                self._baseline_proposal(manifest)
                if baseline_proposal is None
                else baseline_proposal,
            ),
            provider_authority=self._provider_authority(state, manifest),
            egress_receipt=egress,
        )

    def _state_and_manifest(self) -> tuple[V52RunState, AdapterManifest, EnvironmentSnapshot]:
        manifest = AdapterManifest.model_validate(manifest_payload())
        brief = V52TrajectoryBrief(
            schema_version="graph-v5.trajectory-brief.v2",
            run_id="run-real-store",
            brief_id="brief-real-store",
            created_at="2026-09-09T09:30:00Z",
            goal="Verify real-system durable facts.",
            execution_envelope={
                "mode": "remote_nonprod",
                "target_identity_digest": "a" * 64,
                "adapter_manifest_digest": manifest.digest,
            },
            adapter_manifest_digest=manifest.digest,
        )
        confirmation = V52TrajectoryConfirmation(
            schema_version="graph-v5.trajectory-confirmation.v2",
            run_id=brief.run_id,
            brief_id=brief.brief_id,
            trajectory_digest=brief.digest,
            adapter_manifest_digest=manifest.digest,
            confirmed_by="user:aleda",
            confirmed_at="2026-09-09T09:31:00Z",
            confirmation_evidence_ref="conversation:explicit-confirmation:task-5",
        )
        snapshot = EnvironmentSnapshot(
            adapter_manifest_digest=manifest.digest,
            target_identity_digest="a" * 64,
            lease_receipt_digests=(),
            egress_receipt_digest="b" * 64,
            evidence_policy_digest=manifest.evidence.redaction_policy_digest,
        )
        return (
            V52RunState(
                schema_version="graph-v5.run-state.v2",
                run_id=brief.run_id,
                mode="running",
                trajectory=brief,
                confirmation=confirmation,
            ),
            manifest,
            snapshot,
        )

    @staticmethod
    def _state_for_manifest(
        state: V52RunState, manifest: AdapterManifest
    ) -> V52RunState:
        trajectory = V52TrajectoryBrief.model_validate(
            {
                **state.trajectory.model_dump(mode="python"),
                "execution_envelope": {
                    **state.trajectory.execution_envelope.model_dump(mode="python"),
                    "adapter_manifest_digest": manifest.digest,
                },
                "adapter_manifest_digest": manifest.digest,
            }
        )
        confirmation = V52TrajectoryConfirmation.model_validate(
            {
                **state.confirmation.model_dump(mode="python"),
                "trajectory_digest": trajectory.digest,
                "adapter_manifest_digest": manifest.digest,
            }
        )
        return V52RunState.model_validate(
            {
                **state.model_dump(mode="python"),
                "trajectory": trajectory,
                "confirmation": confirmation,
            }
        )

    @staticmethod
    def _reservation(*, operation_id: str, cost_micros: int = 1) -> BudgetReservation:
        return BudgetReservation(
            reservation_id=f"reservation:{operation_id}",
            run_id="run-real-store",
            operation_id=operation_id,
            user_actions=1,
            provider_requests=1,
            cost_micros=cost_micros,
            requests=1,
            processes=0,
            persistence_writes=1,
            tokens=1,
            duration_ms=1,
        )

    def _intent(
        self, store: RealSystemRunStore, *, node_id: str | None = None
    ) -> ExternalOperationIntent:
        state = store.read_state()
        authority = store.next_executable_authority()
        if node_id is not None:
            baseline = state.facts.baseline_spine
            assert baseline is not None
            for node, proposal in zip(
                baseline.nodes, baseline.baseline_proposals, strict=True
            ):
                if node.node_id == node_id:
                    authority = PersistedNodeExecutionAuthority.baseline(node, proposal)
                    break
            else:
                delta = next(
                    (
                        item
                        for item in state.facts.exploration_deltas
                        if item.node.node_id == node_id
                    ),
                    None,
                )
                assert delta is not None
                authority = PersistedNodeExecutionAuthority.exploration(delta)
        assert authority is not None
        return derive_persisted_external_operation_intent(state, authority)

    def test_derived_intent_preserves_typed_node_budget(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, _ = self._state_and_manifest()
            store = RealSystemRunStore.open(Path(temporary) / "store", state.run_id)
            proposal = self._baseline_proposal(manifest).model_copy(
                update={
                    "budget": NodeBudgetProposal(
                        max_user_actions=2,
                        max_provider_requests=3,
                        max_cost_micros=7,
                        max_requests=5,
                        max_bytes=1_024,
                        max_wall_seconds=10,
                    )
                }
            )
            self._initialize(
                store, state, manifest, baseline_proposal=proposal
            )

            intent = self._intent(store)

            self.assertEqual(2, intent.reserved_budget.user_actions)
            self.assertEqual(3, intent.reserved_budget.provider_requests)
            self.assertEqual(7, intent.reserved_budget.cost_micros)

    def test_direct_admission_rejects_typed_node_budget_above_manifest_ceiling(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, _ = self._state_and_manifest()
            store = RealSystemRunStore.open(Path(temporary) / "store", state.run_id)
            proposal = self._baseline_proposal(manifest).model_copy(
                update={
                    "budget": NodeBudgetProposal(
                        max_user_actions=manifest.budgets.max_user_actions + 1,
                        max_provider_requests=1,
                        max_cost_micros=1,
                        max_requests=1,
                        max_bytes=1_024,
                        max_wall_seconds=10,
                    )
                }
            )

            with self.assertRaisesRegex(StoreError, "canonical baseline"):
                self._initialize(
                    store, state, manifest, baseline_proposal=proposal
                )

    def test_exploration_rejects_typed_node_budget_above_manifest_ceiling(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, _ = self._state_and_manifest()
            store = RealSystemRunStore.open(Path(temporary) / "store", state.run_id)
            admitted = self._initialize(store, state, manifest)
            baseline = admitted.facts.baseline_spine
            assert baseline is not None
            node_id = "explore-over-provider-cap"
            delta = ExplorationDelta.from_node(
                node=self._baseline_node(
                    state,
                    manifest,
                    store.environment_snapshot(),
                    node_id=node_id,
                ),
                parent_node_id=baseline.nodes[0].node_id,
                evidence_refs=baseline.nodes[0].entry_observation_refs,
                authority=baseline,
                proposal=self._baseline_proposal(
                    manifest, node_id=node_id
                ).model_copy(
                    update={
                        "budget": NodeBudgetProposal(
                            max_user_actions=1,
                            max_provider_requests=(
                                manifest.budgets.max_provider_requests + 1
                            ),
                            max_cost_micros=1,
                            max_requests=1,
                            max_bytes=1_024,
                            max_wall_seconds=10,
                        )
                    }
                ),
            )

            with self.assertRaisesRegex(StoreError, "provider-request budget exceeds"):
                store.record_exploration_delta(delta)

    def test_budget_widening_cannot_narrow_typed_node_budget(self) -> None:
        from scripts.graph_v5.models import BudgetWideningAmendment

        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, _ = self._state_and_manifest()
            store = RealSystemRunStore.open(Path(temporary) / "store", state.run_id)
            baseline_proposal = self._baseline_proposal(manifest).model_copy(
                update={
                    "budget": NodeBudgetProposal(
                        max_user_actions=2,
                        max_provider_requests=2,
                        max_cost_micros=2,
                        max_requests=1,
                        max_bytes=1_024,
                        max_wall_seconds=10,
                    )
                }
            )
            admitted = self._initialize(
                store, state, manifest, baseline_proposal=baseline_proposal
            )
            head = admitted.facts.run_head
            baseline = admitted.facts.baseline_spine
            assert head is not None and baseline is not None
            proposal = baseline.baseline_proposals[0]
            assert proposal.budget is not None
            amendment = BudgetWideningAmendment(
                kind="budget_widening",
                node_id=proposal.proposal.node_id,
                node_authority_digest=proposal.digest,
                prior_budget_digest=proposal.budget.digest,
                requested_budget={
                    "max_user_actions": 1,
                    "max_provider_requests": 2,
                    "max_cost_micros": 2,
                    "max_requests": 2,
                    "max_bytes": 2_048,
                    "max_wall_seconds": 20,
                },
            )
            pending = PendingRealSystemDecision(
                decision_id="decision:narrow-typed-budget",
                kind="budget_widening",
                run_id=admitted.run_id,
                run_head_digest=head.digest,
                authority_digest=baseline.digest,
                payload_digest=digest_for("real-system-decision-amendment", amendment),
                amendment=amendment,
            )

            with self.assertRaisesRegex(StoreError, "cannot narrow"):
                store.record_pending_real_system_decision(pending)

    def test_budget_widening_rejects_typed_bound_above_manifest_ceiling(self) -> None:
        from scripts.graph_v5.models import BudgetWideningAmendment

        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, _ = self._state_and_manifest()
            store = RealSystemRunStore.open(Path(temporary) / "store", state.run_id)
            admitted = self._initialize(store, state, manifest)
            head = admitted.facts.run_head
            baseline = admitted.facts.baseline_spine
            assert head is not None and baseline is not None
            proposal = baseline.baseline_proposals[0]
            assert proposal.budget is not None
            amendment = BudgetWideningAmendment(
                kind="budget_widening",
                node_id=proposal.proposal.node_id,
                node_authority_digest=proposal.digest,
                prior_budget_digest=proposal.budget.digest,
                requested_budget={
                    "max_user_actions": 1,
                    "max_provider_requests": (
                        manifest.budgets.max_provider_requests + 1
                    ),
                    "max_cost_micros": 1,
                    "max_requests": 2,
                    "max_bytes": 2_048,
                    "max_wall_seconds": 20,
                },
            )
            pending = PendingRealSystemDecision(
                decision_id="decision:over-provider-budget",
                kind="budget_widening",
                run_id=admitted.run_id,
                run_head_digest=head.digest,
                authority_digest=baseline.digest,
                payload_digest=digest_for("real-system-decision-amendment", amendment),
                amendment=amendment,
            )

            with self.assertRaisesRegex(StoreError, "provider-request budget exceeds"):
                store.record_pending_real_system_decision(pending)

    @staticmethod
    def _tree_bytes(root: Path) -> tuple[tuple[str, bytes], ...]:
        return tuple(
            (path.relative_to(root).as_posix(), path.read_bytes())
            for path in sorted(root.rglob("*"))
            if path.is_file()
        )

    @staticmethod
    def _receipt(intent: ExternalOperationIntent) -> ExternalOperationReceipt:
        return ExternalOperationReceipt(
            receipt_id=f"receipt:{intent.operation_id}",
            operation_id=intent.operation_id,
            run_id=intent.run_id,
            manifest_digest=intent.manifest_digest,
            run_head_digest=intent.run_head_digest,
            idempotency_key=intent.idempotency_key,
            status="succeeded",
            evidence_refs=(f"evidence:{intent.operation_id}",),
        )

    def test_next_authority_prefers_current_exploration_after_completed_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, _ = self._state_and_manifest()
            root = Path(temporary) / "store"
            store = RealSystemRunStore.open(root, state.run_id)
            egress = self._egress_receipt(state, manifest)
            snapshot = EnvironmentSnapshot.from_admitted_authority(
                manifest=manifest,
                target_identity_digest=state.trajectory.execution_envelope.target_identity_digest,
                supervisor_receipts=(),
                egress_receipt=egress,
            )
            first = self._baseline_node(state, manifest, snapshot)
            second = self._baseline_node(
                state,
                manifest,
                snapshot,
                node_id="node-2",
                action="Submit alternate synthetic checkout form",
            )
            store.initialize(
                state,
                manifest=manifest,
                baseline_nodes=(first, second),
                baseline_proposals=(
                    self._baseline_proposal(manifest),
                    self._baseline_proposal(
                        manifest,
                        node_id="node-2",
                        action="Submit alternate synthetic checkout form",
                    ),
                ),
                provider_authority=self._provider_authority(state, manifest),
                egress_receipt=egress,
            )

            self.assertEqual("node-1", store.next_executable_authority().node_id)
            intent = self._intent(store)
            store.record_external_intent(intent)
            parent_receipt = self._receipt(intent)
            store.record_external_receipt(parent_receipt)

            exploration_node = self._baseline_node(
                state,
                manifest,
                snapshot,
                node_id="explore-coupon",
                action="Verify unexpected synthetic coupon behavior",
            )
            baseline = store.read_state().facts.baseline_spine
            assert baseline is not None
            exploration = ExplorationDelta.from_node(
                node=exploration_node,
                parent_node_id=first.node_id,
                evidence_refs=parent_receipt.evidence_refs,
                authority=baseline,
                proposal=self._baseline_proposal(
                    manifest,
                    node_id="explore-coupon",
                    action="Verify unexpected synthetic coupon behavior",
                ),
            )
            store.record_exploration_delta(exploration)

            self.assertEqual("explore-coupon", store.next_executable_authority().node_id)

    def test_exploration_rejects_evidence_not_persisted_by_completed_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, _ = self._state_and_manifest()
            root = Path(temporary) / "store"
            store = RealSystemRunStore.open(root, state.run_id)
            egress = self._egress_receipt(state, manifest)
            snapshot = EnvironmentSnapshot.from_admitted_authority(
                manifest=manifest,
                target_identity_digest=state.trajectory.execution_envelope.target_identity_digest,
                supervisor_receipts=(),
                egress_receipt=egress,
            )
            parent = self._baseline_node(state, manifest, snapshot)
            store.initialize(
                state,
                manifest=manifest,
                baseline_nodes=(parent,),
                baseline_proposals=(self._baseline_proposal(manifest),),
                provider_authority=self._provider_authority(state, manifest),
                egress_receipt=egress,
            )
            intent = self._intent(store)
            store.record_external_intent(intent)
            store.record_external_receipt(self._receipt(intent))
            exploration_node = self._baseline_node(
                state,
                manifest,
                snapshot,
                node_id="explore-unrelated-evidence",
                action="Inspect unrelated evidence",
            )
            baseline = store.read_state().facts.baseline_spine
            assert baseline is not None
            exploration = ExplorationDelta.from_node(
                node=exploration_node,
                parent_node_id=parent.node_id,
                evidence_refs=("evidence:not-from-parent",),
                authority=baseline,
                proposal=self._baseline_proposal(
                    manifest,
                    node_id="explore-unrelated-evidence",
                    action="Inspect unrelated evidence",
                ),
            )

            with self.assertRaisesRegex(StoreError, "persisted parent evidence"):
                store.record_exploration_delta(exploration)

    def test_open_readonly_keeps_bytes_and_rejects_pending_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, _ = self._state_and_manifest()
            root = Path(temporary) / "store"
            store = RealSystemRunStore.open(root, state.run_id)
            self._initialize(store, state, manifest)
            before = self._tree_bytes(root)

            readonly = RealSystemRunStore.open_readonly(root, state.run_id)

            self.assertEqual(state.run_id, readonly.read_state().run_id)
            self.assertEqual(before, self._tree_bytes(root))

            lease = ResourceLease.issue(
                run_id=state.run_id,
                resource="account:synthetic-01",
            )
            real_append = TransactionalRunStore._append_bytes

            def crash_before_ledger_append(path: Path, payload: bytes) -> None:
                if path == root / "ledger.jsonl":
                    raise OSError("simulated crash before ledger append")
                real_append(path, payload)

            with patch.object(
                TransactionalRunStore,
                "_append_bytes",
                side_effect=crash_before_ledger_append,
            ):
                with self.assertRaisesRegex(OSError, "simulated crash"):
                    store.record_resource_lease(lease)

            pending_before = self._tree_bytes(root)
            with self.assertRaisesRegex(RecoveryError, "recovery"):
                RealSystemRunStore.open_readonly(root, state.run_id)
            self.assertEqual(pending_before, self._tree_bytes(root))

    def test_real_system_decision_consumes_exact_pending_fact_once(self) -> None:
        from scripts.graph_v5.models import BudgetWideningAmendment

        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, _ = self._state_and_manifest()
            store = RealSystemRunStore.open(Path(temporary) / "store", state.run_id)
            self._initialize(store, state, manifest)
            admitted = store.read_state()
            head = admitted.facts.run_head
            baseline = admitted.facts.baseline_spine
            assert head is not None
            assert baseline is not None
            proposal = baseline.baseline_proposals[0]
            assert proposal.budget is not None
            authority = store.next_executable_authority()
            assert authority is not None
            original_intent = derive_persisted_external_operation_intent(
                admitted, authority
            )
            amendment = BudgetWideningAmendment(
                kind="budget_widening",
                node_id=proposal.proposal.node_id,
                node_authority_digest=proposal.digest,
                prior_budget_digest=proposal.budget.digest,
                requested_budget={
                    "max_user_actions": 1,
                    "max_provider_requests": 1,
                    "max_cost_micros": 1,
                    "max_requests": 2,
                    "max_bytes": 2_048,
                    "max_wall_seconds": 20,
                },
            )
            pending = PendingRealSystemDecision(
                decision_id="decision:budget-widening",
                kind="budget_widening",
                run_id=admitted.run_id,
                run_head_digest=head.digest,
                authority_digest=baseline.digest,
                payload_digest=digest_for("real-system-decision-amendment", amendment),
                amendment=amendment,
            )
            store.record_pending_real_system_decision(pending)
            decision = RealSystemDecision(
                decision_id=pending.decision_id,
                pending_decision_digest=pending.digest,
                kind=pending.kind,
                run_id=pending.run_id,
                run_head_digest=pending.run_head_digest,
                authority_digest=pending.authority_digest,
                payload_digest=pending.payload_digest,
                amendment=amendment,
                actor="user:aleda",
            )

            applied = store.apply_real_system_decision(decision)

            self.assertEqual(
                amendment,
                applied.facts.real_system_decision_consumptions[0].amendment,
            )
            widened_intent = derive_persisted_external_operation_intent(
                applied, authority
            )
            self.assertEqual(original_intent.operation_id, widened_intent.operation_id)
            self.assertEqual(
                original_intent.idempotency_key, widened_intent.idempotency_key
            )
            self.assertEqual(2, widened_intent.reserved_budget.requests)
            self.assertEqual(2_048, widened_intent.reserved_budget.bytes)
            self.assertEqual(20_000, widened_intent.reserved_budget.duration_ms)

            with self.assertRaisesRegex(StoreError, "consumed"):
                store.apply_real_system_decision(decision)

    def test_real_system_decision_rejects_pending_fact_stale_against_current_authority(self) -> None:
        from scripts.graph_v5.models import BudgetWideningAmendment

        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, _ = self._state_and_manifest()
            store = RealSystemRunStore.open(Path(temporary) / "store", state.run_id)
            self._initialize(store, state, manifest)
            admitted = store.read_state()
            head = admitted.facts.run_head
            baseline = admitted.facts.baseline_spine
            assert head is not None and baseline is not None
            proposal = baseline.baseline_proposals[0]
            assert proposal.budget is not None
            amendment = BudgetWideningAmendment(
                kind="budget_widening",
                node_id=proposal.proposal.node_id,
                node_authority_digest=proposal.digest,
                prior_budget_digest=proposal.budget.digest,
                requested_budget={
                    "max_user_actions": 1,
                    "max_provider_requests": 1,
                    "max_cost_micros": 1,
                    "max_requests": 2,
                    "max_bytes": 2_048,
                    "max_wall_seconds": 20,
                },
            )
            pending = PendingRealSystemDecision(
                decision_id="decision:stale-authority",
                kind="budget_widening",
                run_id=admitted.run_id,
                run_head_digest=head.digest,
                authority_digest=baseline.digest,
                payload_digest=digest_for("real-system-decision-amendment", amendment),
                amendment=amendment,
            )
            store.record_pending_real_system_decision(pending)
            decision = RealSystemDecision(
                decision_id=pending.decision_id,
                pending_decision_digest=pending.digest,
                kind=pending.kind,
                run_id=pending.run_id,
                run_head_digest=pending.run_head_digest,
                authority_digest=pending.authority_digest,
                payload_digest=pending.payload_digest,
                amendment=amendment,
                actor="user:aleda",
            )
            stale_state = store.read_state().model_copy(
                update={
                    "facts": store.read_state().facts.model_copy(
                        update={
                            "baseline_spine": baseline.model_copy(
                                update={"node_digests": ("f" * 64,)}
                            )
                        }
                    )
                }
            )

            with patch.object(store, "read_state", return_value=stale_state):
                with self.assertRaisesRegex(StoreError, "stale"):
                    store.apply_real_system_decision(decision)

    def test_pending_real_system_decisions_reject_unadmitted_amendments(self) -> None:
        from scripts.graph_v5.models import (
            BudgetWideningAmendment,
            CleanupAmendment,
            FixOrPatchAmendment,
            ProductionWriteConfirmationAmendment,
        )

        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, _ = self._state_and_manifest()
            store = RealSystemRunStore.open(Path(temporary) / "store", state.run_id)
            self._initialize(store, state, manifest)
            admitted = store.read_state()
            head = admitted.facts.run_head
            baseline = admitted.facts.baseline_spine
            assert head is not None and baseline is not None
            proposal = baseline.baseline_proposals[0]
            assert proposal.budget is not None
            cases = (
                (
                    "budget_widening",
                    BudgetWideningAmendment(
                        kind="budget_widening",
                        node_id=proposal.proposal.node_id,
                        node_authority_digest="0" * 64,
                        prior_budget_digest=proposal.budget.digest,
                        requested_budget={
                            "max_user_actions": 1,
                            "max_provider_requests": 1,
                            "max_cost_micros": 1,
                            "max_requests": 2,
                            "max_bytes": 2_048,
                            "max_wall_seconds": 20,
                        },
                    ),
                    "node budget",
                ),
                (
                    "budget_widening",
                    BudgetWideningAmendment(
                        kind="budget_widening",
                        node_id=proposal.proposal.node_id,
                        node_authority_digest=proposal.digest,
                        prior_budget_digest=proposal.budget.digest,
                        requested_budget={
                            "max_user_actions": 1,
                            "max_provider_requests": 1,
                            "max_cost_micros": 1,
                            "max_requests": manifest.budgets.max_requests + 1,
                            "max_bytes": 2_048,
                            "max_wall_seconds": 20,
                        },
                    ),
                    "budget",
                ),
                (
                    "production_write_confirmation",
                    ProductionWriteConfirmationAmendment(
                        kind="production_write_confirmation",
                        production_write_plan_digest="d" * 64,
                    ),
                    "production write plan",
                ),
                (
                    "cleanup",
                    CleanupAmendment(
                        kind="cleanup",
                        runtime_note_digest="e" * 64,
                    ),
                    "runtime note",
                ),
                (
                    "fix_or_patch",
                    FixOrPatchAmendment(
                        kind="fix_or_patch",
                        runtime_note_digest="f" * 64,
                        treatment="patch",
                    ),
                    "runtime note",
                ),
            )

            for index, (kind, amendment, message) in enumerate(cases):
                with self.subTest(kind=kind):
                    pending = PendingRealSystemDecision(
                        decision_id=f"decision:unadmitted:{index}",
                        kind=kind,
                        run_id=admitted.run_id,
                        run_head_digest=head.digest,
                        authority_digest=baseline.digest,
                        payload_digest=digest_for(
                            "real-system-decision-amendment", amendment
                        ),
                        amendment=amendment,
                    )
                    with self.assertRaisesRegex(StoreError, message):
                        store.record_pending_real_system_decision(pending)

            self.assertEqual((), store.read_state().facts.pending_real_system_decisions)

    def test_pending_real_system_decisions_reject_competing_same_target(self) -> None:
        from scripts.graph_v5.models import BudgetWideningAmendment

        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, _ = self._state_and_manifest()
            store = RealSystemRunStore.open(Path(temporary) / "store", state.run_id)
            self._initialize(store, state, manifest)
            admitted = store.read_state()
            head = admitted.facts.run_head
            baseline = admitted.facts.baseline_spine
            assert head is not None and baseline is not None
            proposal = baseline.baseline_proposals[0]
            assert proposal.budget is not None

            def pending(decision_id: str, *, max_requests: int) -> PendingRealSystemDecision:
                amendment = BudgetWideningAmendment(
                    kind="budget_widening",
                    node_id=proposal.proposal.node_id,
                    node_authority_digest=proposal.digest,
                    prior_budget_digest=proposal.budget.digest,
                    requested_budget={
                        "max_user_actions": 1,
                        "max_provider_requests": 1,
                        "max_cost_micros": 1,
                        "max_requests": max_requests,
                        "max_bytes": 2_048,
                        "max_wall_seconds": 20,
                    },
                )
                return PendingRealSystemDecision(
                    decision_id=decision_id,
                    kind="budget_widening",
                    run_id=admitted.run_id,
                    run_head_digest=head.digest,
                    authority_digest=baseline.digest,
                    payload_digest=digest_for(
                        "real-system-decision-amendment", amendment
                    ),
                    amendment=amendment,
                )

            store.record_pending_real_system_decision(
                pending("decision:widening-a", max_requests=2)
            )
            with self.assertRaisesRegex(StoreError, "target|competing"):
                store.record_pending_real_system_decision(
                    pending("decision:widening-b", max_requests=3)
                )

    def test_aggregate_exhaustion_blocks_with_exact_multi_cap_names(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, _ = self._state_and_manifest()
            payload = manifest_payload()
            payload["budgets"] = {
                **payload["budgets"],
                "max_user_actions": 1,
                "max_provider_requests": 1,
            }
            manifest = AdapterManifest.model_validate(payload)
            state = self._state_for_manifest(state, manifest)
            root = Path(temporary) / "store"
            store = RealSystemRunStore.open(root, state.run_id)
            admitted = self._initialize(store, state, manifest)
            baseline = admitted.facts.baseline_spine
            assert baseline is not None
            node = self._baseline_node(
                state,
                manifest,
                store.environment_snapshot(),
                node_id="node-2",
                action="Submit alternate synthetic checkout form",
            )
            delta = ExplorationDelta.from_node(
                node=node,
                parent_node_id=baseline.nodes[0].node_id,
                evidence_refs=baseline.nodes[0].entry_observation_refs,
                authority=baseline,
                proposal=self._baseline_proposal(
                    manifest,
                    node_id="node-2",
                    action="Submit alternate synthetic checkout form",
                ),
            )
            store.record_exploration_delta(delta)
            store.record_external_intent(self._intent(store))
            rejected_intent = self._intent(store, node_id="node-2")

            with self.assertRaises(BudgetReservationExceeded) as raised:
                store.record_external_intent(rejected_intent)

            self.assertEqual(
                ("max_user_actions", "max_provider_requests"),
                raised.exception.exhausted_budget_names,
            )
            event = store.record_manifest_budget_exhaustion(rejected_intent)
            blocked = store.read_state()
            exhaustion = blocked.facts.manifest_budget_exhaustions[0]

            self.assertEqual("manifest_budget_exhausted_blocked", event.kind)
            self.assertEqual("blocked", blocked.mode)
            self.assertEqual(rejected_intent, exhaustion.rejected_intent)
            self.assertEqual(
                ("max_user_actions", "max_provider_requests"),
                exhaustion.exhausted_budget_names,
            )
            self.assertEqual(1, len(blocked.facts.external_operation_intents))
            self.assertEqual(1, len(blocked.facts.budget_reservations))
            self.assertEqual(1, len(blocked.facts.manifest_budget_exhaustions))
            with self.assertRaisesRegex(StoreError, "requires a running"):
                store.record_manifest_budget_exhaustion(rejected_intent)
            reopened = RealSystemRunStore.open(root, state.run_id)
            self.assertEqual(blocked, reopened.read_state())

    def test_external_intent_precedes_real_effect_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, snapshot = self._state_and_manifest()
            store = RealSystemRunStore.open(Path(temporary) / "store", state.run_id)
            self._initialize(store, state, manifest)
            intent = self._intent(store)

            intent_event = store.record_external_intent(intent)
            receipt_event = store.record_external_receipt(
                ExternalOperationReceipt(
                    receipt_id="receipt:op-1",
                    operation_id=intent.operation_id,
                    run_id=intent.run_id,
                    manifest_digest=intent.manifest_digest,
                    run_head_digest=intent.run_head_digest,
                    idempotency_key=intent.idempotency_key,
                    status="succeeded",
                    evidence_refs=("evidence:op-1",),
                )
            )

            self.assertLess(intent_event.sequence, receipt_event.sequence)

    def test_real_admission_persists_v52_baseline_spine_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, _ = self._state_and_manifest()
            egress = EgressGateReceipt(
                run_id=state.run_id,
                adapter_manifest_digest=manifest.digest,
                target_identity_digest=state.trajectory.execution_envelope.target_identity_digest,
                allowed_hosts=(manifest.target.host,),
                allowed_protocols=("https",),
                issued_receipt_digest=digest_for(
                    "egress-enforcement-receipt", manifest.egress.enforcement_receipt
                ),
            )
            snapshot = EnvironmentSnapshot.from_admitted_authority(
                manifest=manifest,
                target_identity_digest=state.trajectory.execution_envelope.target_identity_digest,
                supervisor_receipts=(),
                egress_receipt=egress,
            )
            baseline_node = self._baseline_node(state, manifest, snapshot)
            store = RealSystemRunStore.open(Path(temporary) / "store", state.run_id)

            store.initialize(
                state,
                manifest=manifest,
                baseline_nodes=(baseline_node,),
                baseline_proposals=(self._baseline_proposal(manifest),),
                provider_authority=self._provider_authority(state, manifest),
                egress_receipt=egress,
            )

            reopened = RealSystemRunStore.open(store.root, state.run_id)
            self.assertEqual(
                reopened.read_state().facts.baseline_spine.digest,
                store.read_state().facts.baseline_spine.digest,
            )

    def test_real_admission_persists_genuine_supervisor_authority_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, _ = self._state_and_manifest()
            egress = self._egress_receipt(state, manifest)
            port_lease = ResourceLease.issue(run_id=state.run_id, resource="port:4317")
            process_lease = ResourceLease.issue(run_id=state.run_id, resource="process:4242")
            health = HealthReceipt(
                service_id="checkout",
                lease_id=port_lease.lease_id,
                endpoint="http://127.0.0.1:4317/health",
                status_code=204,
                checked_at="2026-09-09T09:31:00Z",
            )
            service = ServiceReceipt(
                service_id="checkout",
                run_id=state.run_id,
                lease_id=port_lease.lease_id,
                port_lease_id=port_lease.lease_id,
                process_lease=process_lease,
                port=4317,
                process_id=4242,
                status="ready",
                process_tree_terminated=False,
                started_at="2026-09-09T09:30:00Z",
                health=health,
            )
            supervisor = SupervisorAuthorityReceipt(
                run_id=state.run_id,
                adapter_manifest_digest=manifest.digest,
                target_identity_digest=state.trajectory.execution_envelope.target_identity_digest,
                service_receipt=service,
                readiness_receipts=(health,),
                lease_ids=(port_lease.lease_id, process_lease.lease_id),
            )
            snapshot = EnvironmentSnapshot.from_admitted_authority(
                manifest=manifest,
                target_identity_digest=state.trajectory.execution_envelope.target_identity_digest,
                supervisor_receipts=(supervisor,),
                egress_receipt=egress,
            )
            root = Path(temporary) / "store"
            store = RealSystemRunStore.open(root, state.run_id)

            store.initialize(
                state,
                manifest=manifest,
                baseline_nodes=(self._baseline_node(state, manifest, snapshot),),
                baseline_proposals=(self._baseline_proposal(manifest),),
                provider_authority=self._provider_authority(state, manifest),
                supervisor_receipts=(supervisor,),
                egress_receipt=egress,
            )

            reopened = RealSystemRunStore.open(root, state.run_id)
            supervisors, _ = reopened.resolve_admitted_environment_receipts()
            self.assertEqual(tuple(item.digest for item in supervisors), (supervisor.digest,))
            self.assertEqual(
                reopened.environment_snapshot().lease_receipt_digests,
                (supervisor.digest,),
            )

    def test_registered_exploration_requires_exact_canonical_node_membership(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, _ = self._state_and_manifest()
            egress = EgressGateReceipt(
                run_id=state.run_id,
                adapter_manifest_digest=manifest.digest,
                target_identity_digest=state.trajectory.execution_envelope.target_identity_digest,
                allowed_hosts=(manifest.target.host,),
                allowed_protocols=("https",),
                issued_receipt_digest=digest_for(
                    "egress-enforcement-receipt", manifest.egress.enforcement_receipt
                ),
            )
            snapshot = EnvironmentSnapshot.from_admitted_authority(
                manifest=manifest,
                target_identity_digest=state.trajectory.execution_envelope.target_identity_digest,
                supervisor_receipts=(),
                egress_receipt=egress,
            )
            baseline_node = self._baseline_node(state, manifest, snapshot)
            store = RealSystemRunStore.open(Path(temporary) / "store", state.run_id)
            store.initialize(
                state,
                manifest=manifest,
                baseline_nodes=(baseline_node,),
                baseline_proposals=(self._baseline_proposal(manifest),),
                provider_authority=self._provider_authority(state, manifest),
                egress_receipt=egress,
            )
            delta_node = self._baseline_node(
                state, manifest, snapshot, node_id="node-explore-coupon"
            )
            delta = ExplorationDelta.from_node(
                node=delta_node,
                parent_node_id=baseline_node.node_id,
                evidence_refs=baseline_node.entry_observation_refs,
                authority=store.read_state().facts.baseline_spine,
                proposal=self._baseline_proposal(
                    manifest, node_id="node-explore-coupon"
                ),
            )

            store.record_exploration_delta(delta)

            self.assertEqual("exploration", store.require_authorized_node(delta_node).kind)
            substituted = self._baseline_node(
                state,
                manifest,
                snapshot,
                node_id=delta_node.node_id,
                action="Submit a different synthetic checkout form",
            )
            with self.assertRaisesRegex(StoreError, "registered exploration"):
                store.require_authorized_node(substituted)

    def test_store_validates_intent_against_exact_persisted_node_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, snapshot = self._state_and_manifest()
            store = RealSystemRunStore.open(Path(temporary) / "store", state.run_id)
            admitted = self._initialize(store, state, manifest)
            baseline = admitted.facts.baseline_spine
            assert baseline is not None
            authority = store.require_authorized_node(baseline.nodes[0])
            intent = self._intent(store)

            store.validate_intent_for_authorized_node(intent, authority)

            forged = intent.model_copy(update={"effect": "bridge:observe"})
            with self.assertRaisesRegex(StoreError, "node authority"):
                store.validate_intent_for_authorized_node(forged, authority)

    def test_store_rejects_cross_node_intent_authority_substitution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, _ = self._state_and_manifest()
            store = RealSystemRunStore.open(Path(temporary) / "store", state.run_id)
            admitted = self._initialize(store, state, manifest)
            snapshot = store.environment_snapshot()
            baseline = admitted.facts.baseline_spine
            assert baseline is not None
            baseline_authority = store.require_authorized_node(baseline.nodes[0])
            second_node = self._baseline_node(
                state,
                manifest,
                snapshot,
                node_id="node-2",
                action="Submit alternate synthetic checkout form",
            )
            delta = ExplorationDelta.from_node(
                node=second_node,
                parent_node_id=baseline.nodes[0].node_id,
                evidence_refs=baseline.nodes[0].entry_observation_refs,
                authority=baseline,
                proposal=self._baseline_proposal(
                    manifest,
                    node_id="node-2",
                    action="Submit alternate synthetic checkout form",
                ),
            )
            store.record_exploration_delta(delta)
            second_intent = self._intent(store, node_id=second_node.node_id)
            store.record_external_intent(second_intent)

            with self.assertRaisesRegex(StoreError, "node authority"):
                store.validate_intent_for_authorized_node(
                    second_intent, baseline_authority
                )

    def test_store_resolves_only_persisted_typed_environment_receipts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, _ = self._state_and_manifest()
            store = RealSystemRunStore.open(Path(temporary) / "store", state.run_id)
            admitted = self._initialize(store, state, manifest)

            supervisors, egress = store.resolve_admitted_environment_receipts()

            self.assertEqual(supervisors, admitted.facts.supervisor_receipts)
            self.assertEqual(egress, admitted.facts.egress_receipt)

    def test_admission_rejects_foreign_receipt_before_store_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, _ = self._state_and_manifest()
            admitted_egress = self._egress_receipt(state, manifest)
            snapshot = EnvironmentSnapshot.from_admitted_authority(
                manifest=manifest,
                target_identity_digest=state.trajectory.execution_envelope.target_identity_digest,
                supervisor_receipts=(),
                egress_receipt=admitted_egress,
            )
            foreign_egress = admitted_egress.model_copy(update={"run_id": "foreign-run"})
            root = Path(temporary) / "store"
            store = RealSystemRunStore.open(root, state.run_id)

            with self.assertRaisesRegex(StoreError, "baseline|typed receipts"):
                store.initialize(
                    state,
                    manifest=manifest,
                    baseline_nodes=(self._baseline_node(state, manifest, snapshot),),
                    provider_authority=self._provider_authority(state, manifest),
                    egress_receipt=foreign_egress,
                )

            self.assertFalse((root / "state.json").exists())
            self.assertFalse((root / "ledger.jsonl").exists())

    def test_admission_rejects_forged_egress_digest_before_store_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, _ = self._state_and_manifest()
            valid_egress = self._egress_receipt(state, manifest)
            forged_egress = valid_egress.model_copy(update={"issued_receipt_digest": "f" * 64})
            root = Path(temporary) / "store"
            store = RealSystemRunStore.open(root, state.run_id)

            with self.assertRaisesRegex(EnvironmentPreflightError, "receipt digest"):
                snapshot = EnvironmentSnapshot.from_admitted_authority(
                    manifest=manifest,
                    target_identity_digest=state.trajectory.execution_envelope.target_identity_digest,
                    supervisor_receipts=(),
                    egress_receipt=forged_egress,
                )
                store.initialize(
                    state,
                    manifest=manifest,
                    baseline_nodes=(self._baseline_node(state, manifest, snapshot),),
                    egress_receipt=forged_egress,
                )

            self.assertFalse((root / "state.json").exists())
            self.assertFalse((root / "ledger.jsonl").exists())

    def test_forged_exploration_delta_ledger_event_fails_closed_on_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, _ = self._state_and_manifest()
            egress = EgressGateReceipt(
                run_id=state.run_id,
                adapter_manifest_digest=manifest.digest,
                target_identity_digest=state.trajectory.execution_envelope.target_identity_digest,
                allowed_hosts=(manifest.target.host,),
                allowed_protocols=("https",),
                issued_receipt_digest=digest_for(
                    "egress-enforcement-receipt", manifest.egress.enforcement_receipt
                ),
            )
            snapshot = EnvironmentSnapshot.from_admitted_authority(
                manifest=manifest,
                target_identity_digest=state.trajectory.execution_envelope.target_identity_digest,
                supervisor_receipts=(),
                egress_receipt=egress,
            )
            baseline_node = self._baseline_node(state, manifest, snapshot)
            root = Path(temporary) / "store"
            store = RealSystemRunStore.open(root, state.run_id)
            store.initialize(
                state,
                manifest=manifest,
                baseline_nodes=(baseline_node,),
                baseline_proposals=(self._baseline_proposal(manifest),),
                provider_authority=self._provider_authority(state, manifest),
                egress_receipt=egress,
            )
            delta = ExplorationDelta.from_node(
                node=self._baseline_node(state, manifest, snapshot, node_id="node-explore-coupon"),
                parent_node_id=baseline_node.node_id,
                evidence_refs=baseline_node.entry_observation_refs,
                authority=store.read_state().facts.baseline_spine,
                proposal=self._baseline_proposal(
                    manifest, node_id="node-explore-coupon"
                ),
            )
            store.record_exploration_delta(delta)
            events = list(store.read_events())
            event = events[-1]
            events[-1] = RealSystemLedgerEvent.create(
                sequence=event.sequence,
                kind=event.kind,
                fact_id=event.fact_id,
                fact_digest="f" * 64,
                previous_digest=event.previous_digest,
                state_digest=event.state_digest,
            )
            (root / "ledger.jsonl").write_bytes(
                b"".join(canonical_json_bytes(item) + b"\n" for item in events)
            )

            with self.assertRaisesRegex(StoreError, "ledger projection"):
                RealSystemRunStore.open(root, state.run_id)

    def test_exploration_delta_recovers_after_state_write_before_ledger_append(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, _ = self._state_and_manifest()
            root = Path(temporary) / "store"
            store = RealSystemRunStore.open(root, state.run_id)
            admitted = self._initialize(store, state, manifest)
            baseline = admitted.facts.baseline_spine
            assert baseline is not None
            snapshot = store.environment_snapshot()
            delta_node = self._baseline_node(
                state, manifest, snapshot, node_id="node-explore-recovery"
            )
            delta = ExplorationDelta.from_node(
                node=delta_node,
                parent_node_id=baseline.nodes[0].node_id,
                evidence_refs=baseline.nodes[0].entry_observation_refs,
                authority=baseline,
                proposal=self._baseline_proposal(
                    manifest, node_id="node-explore-recovery"
                ),
            )
            real_append = TransactionalRunStore._append_bytes

            def crash_before_ledger_append(path: Path, payload: bytes) -> None:
                if path == root / "ledger.jsonl":
                    raise OSError("simulated crash before ledger append")
                real_append(path, payload)

            with patch.object(
                TransactionalRunStore,
                "_append_bytes",
                side_effect=crash_before_ledger_append,
            ):
                with self.assertRaisesRegex(OSError, "simulated crash"):
                    store.record_exploration_delta(delta)

            reopened = RealSystemRunStore.open(root, state.run_id)
            self.assertEqual(reopened.read_state().facts.exploration_deltas, (delta,))

    def test_reopen_rejects_rehashed_baseline_with_foreign_trajectory_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, _ = self._state_and_manifest()
            root = Path(temporary) / "store"
            store = RealSystemRunStore.open(root, state.run_id)
            admitted = self._initialize(store, state, manifest)
            baseline = admitted.facts.baseline_spine
            assert baseline is not None
            node_payload = baseline.nodes[0].model_dump(
                exclude={"sealed_intent_digest"}, mode="python"
            )
            node_payload["trajectory_digest"] = "f" * 64
            forged_node = DerivedBehavioralNode(
                **node_payload,
                sealed_intent_digest=digest_for(
                    "derived-behavioral-node-intent", node_payload
                ),
            )
            forged_baseline = BaselineSpineAuthority(
                **{
                    **baseline.model_dump(
                        exclude={"nodes", "node_digests"}, mode="python"
                    ),
                    "nodes": (forged_node,),
                    "node_digests": (forged_node.digest,),
                }
            )
            forged_facts = RealSystemFactIndex.model_validate(
                {
                    **admitted.facts.model_dump(mode="python"),
                    "baseline_spine": forged_baseline,
                }
            )
            forged_state = V52RunState.model_validate(
                {**admitted.model_dump(mode="python"), "facts": forged_facts}
            )
            forged_event = RealSystemLedgerEvent.create(
                sequence=1,
                kind="real_system_admitted",
                fact_id=forged_baseline.digest,
                fact_digest=forged_baseline.digest,
                previous_digest="0" * 64,
                state_digest=forged_state.digest,
            )
            (root / "state.json").write_bytes(canonical_json_bytes(forged_state))
            (root / "ledger.jsonl").write_bytes(
                canonical_json_bytes(forged_event) + b"\n"
            )

            with self.assertRaisesRegex(StoreError, "baseline spine"):
                RealSystemRunStore.open(root, state.run_id)

    def test_persisted_intent_rejects_budget_substitution_before_manifest_cap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, snapshot = self._state_and_manifest()
            store = RealSystemRunStore.open(Path(temporary) / "store", state.run_id)
            self._initialize(store, state, manifest)
            admitted = self._intent(store)
            intent = admitted.model_copy(
                update={
                    "reserved_budget": admitted.reserved_budget.model_copy(
                        update={"cost_micros": manifest.budgets.max_cost_micros + 1}
                    )
                }
            )

            with self.assertRaisesRegex(StoreError, "exact proposal budget authority"):
                store.record_external_intent(intent)

    def test_manifest_rejects_undeclared_typed_effect_before_intent_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, snapshot = self._state_and_manifest()
            store = RealSystemRunStore.open(Path(temporary) / "store", state.run_id)
            self._initialize(store, state, manifest)
            admitted = self._intent(store)
            unadmitted = ExternalOperationIntent(
                operation_id="op-unadmitted",
                run_id=admitted.run_id,
                node_id=admitted.node_id,
                manifest_digest=admitted.manifest_digest,
                run_head_digest=admitted.run_head_digest,
                idempotency_key="provider:op-unadmitted",
                effect="provider:billable_request",
                reserved_budget=self._reservation(operation_id="op-unadmitted"),
            )

            with self.assertRaisesRegex(StoreError, "manifest capability"):
                store.record_external_intent(unadmitted)

    def test_cleanup_rejects_foreign_runtime_note(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, snapshot = self._state_and_manifest()
            store = RealSystemRunStore.open(Path(temporary) / "store", state.run_id)
            self._initialize(store, state, manifest)
            foreign = ResourceLease.issue(run_id="other-run", resource="account:synthetic-1")
            note = RuntimeNote(
                resource_ref=foreign.resource,
                lease_id=foreign.lease_id,
                classification="ephemeral_test_data",
                receipt_ref="receipt:other-run",
                cleanup_intent="remove after explicit cleanup decision",
            )

            with self.assertRaisesRegex(StoreError, "lease/note ownership mismatch"):
                store.record_runtime_note(note)

    def test_unsettled_intent_pauses_on_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, snapshot = self._state_and_manifest()
            root = Path(temporary) / "store"
            store = RealSystemRunStore.open(root, state.run_id)
            self._initialize(store, state, manifest)
            store.record_external_intent(self._intent(store))

            resumed = RealSystemRunStore.open(root, state.run_id)
            self.assertEqual("paused", resumed.read_state().mode)

    def test_unknown_receipt_pauses_instead_of_retrying(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, snapshot = self._state_and_manifest()
            root = Path(temporary) / "store"
            store = RealSystemRunStore.open(root, state.run_id)
            self._initialize(store, state, manifest)
            intent = self._intent(store)
            store.record_external_intent(intent)
            store.record_external_receipt(
                ExternalOperationReceipt(
                    receipt_id="receipt:op-unknown",
                    operation_id=intent.operation_id,
                    run_id=intent.run_id,
                    manifest_digest=intent.manifest_digest,
                    run_head_digest=intent.run_head_digest,
                    idempotency_key=intent.idempotency_key,
                    status="unknown",
                    evidence_refs=("evidence:unknown",),
                )
            )

            resumed = RealSystemRunStore.open(root, state.run_id)
            self.assertEqual("paused", resumed.read_state().mode)

    def test_runtime_notes_project_only_persisted_owned_redacted_facts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, snapshot = self._state_and_manifest()
            root = Path(temporary) / "store"
            store = RealSystemRunStore.open(root, state.run_id)
            self._initialize(store, state, manifest)
            lease = ResourceLease.issue(run_id=state.run_id, resource="account:synthetic-01")
            store.record_resource_lease(lease)
            intent = self._intent(store)
            store.record_external_intent(intent)
            receipt = ExternalOperationReceipt(
                receipt_id="receipt:op-1",
                operation_id=intent.operation_id,
                run_id=intent.run_id,
                manifest_digest=intent.manifest_digest,
                run_head_digest=intent.run_head_digest,
                idempotency_key=intent.idempotency_key,
                status="succeeded",
                evidence_refs=("evidence:op-1",),
            )
            store.record_external_receipt(receipt)
            note = RuntimeNote(
                resource_ref=lease.resource,
                lease_id=lease.lease_id,
                classification="ephemeral_test_data",
                receipt_ref=receipt.receipt_id,
                cleanup_intent="remove after explicit cleanup decision",
            )

            store.record_runtime_note(note)

            notes = (root / "runtime_notes.md").read_text(encoding="utf-8")
            self.assertIn(note.digest, notes)
            self.assertNotIn(lease.issued_ownership_token, notes)

    def test_recovers_real_system_event_when_crash_leaves_old_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, snapshot = self._state_and_manifest()
            root = Path(temporary) / "store"
            store = RealSystemRunStore.open(root, state.run_id)
            self._initialize(store, state, manifest)
            lease = ResourceLease.issue(run_id=state.run_id, resource="account:synthetic-01")
            real_atomic_write = TransactionalRunStore._atomic_write

            def crash_before_state_replace(path: Path, payload: bytes) -> None:
                if path == root / "state.json":
                    raise OSError("simulated crash before state replace")
                real_atomic_write(path, payload)

            with patch.object(
                TransactionalRunStore,
                "_atomic_write",
                side_effect=crash_before_state_replace,
            ):
                with self.assertRaisesRegex(OSError, "simulated crash"):
                    store.record_resource_lease(lease)

            recovered = RealSystemRunStore.open(root, state.run_id)
            recovered_lease = recovered.read_state().facts.leases[0]
            self.assertEqual(lease.model_dump(), recovered_lease.model_dump())

    def test_recovers_torn_real_system_ledger_append(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, snapshot = self._state_and_manifest()
            root = Path(temporary) / "store"
            store = RealSystemRunStore.open(root, state.run_id)
            self._initialize(store, state, manifest)
            lease = ResourceLease.issue(
                run_id=state.run_id,
                resource="account:synthetic-01",
            )
            real_append = TransactionalRunStore._append_bytes

            def tear_ledger_append(path: Path, payload: bytes) -> None:
                if path == root / "ledger.jsonl":
                    with path.open("ab") as handle:
                        handle.write(payload[: len(payload) // 2])
                        handle.flush()
                    raise OSError("simulated torn ledger append")
                real_append(path, payload)

            with patch.object(
                TransactionalRunStore,
                "_append_bytes",
                side_effect=tear_ledger_append,
            ):
                with self.assertRaisesRegex(OSError, "torn ledger"):
                    store.record_resource_lease(lease)

            recovered = RealSystemRunStore.open(root, state.run_id)
            self.assertEqual(lease.lease_id, recovered.read_state().facts.leases[0].lease_id)

    def test_recovers_torn_runtime_notes_append(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, snapshot = self._state_and_manifest()
            root = Path(temporary) / "store"
            store = RealSystemRunStore.open(root, state.run_id)
            self._initialize(store, state, manifest)
            lease = ResourceLease.issue(
                run_id=state.run_id,
                resource="account:synthetic-01",
            )
            store.record_resource_lease(lease)
            intent = self._intent(store)
            store.record_external_intent(intent)
            receipt = ExternalOperationReceipt(
                receipt_id="receipt:op-1",
                operation_id=intent.operation_id,
                run_id=intent.run_id,
                manifest_digest=intent.manifest_digest,
                run_head_digest=intent.run_head_digest,
                idempotency_key=intent.idempotency_key,
                status="succeeded",
                evidence_refs=("evidence:op-1",),
            )
            store.record_external_receipt(receipt)
            note = RuntimeNote(
                resource_ref=lease.resource,
                lease_id=lease.lease_id,
                classification="ephemeral_test_data",
                receipt_ref=receipt.receipt_id,
                cleanup_intent="remove after explicit cleanup decision",
            )
            real_append = TransactionalRunStore._append_bytes

            def tear_notes_append(path: Path, payload: bytes) -> None:
                if path == root / "runtime_notes.md":
                    with path.open("ab") as handle:
                        handle.write(payload[: len(payload) // 2])
                        handle.flush()
                    raise OSError("simulated torn notes append")
                real_append(path, payload)

            with patch.object(
                TransactionalRunStore,
                "_append_bytes",
                side_effect=tear_notes_append,
            ):
                with self.assertRaisesRegex(OSError, "torn notes"):
                    store.record_runtime_note(note)

            recovered = RealSystemRunStore.open(root, state.run_id)
            self.assertEqual(note, recovered.read_state().facts.runtime_notes[0])

    def test_rejects_runtime_notes_projection_missing_persisted_note(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, snapshot = self._state_and_manifest()
            root = Path(temporary) / "store"
            store = RealSystemRunStore.open(root, state.run_id)
            self._initialize(store, state, manifest)
            lease = ResourceLease.issue(run_id=state.run_id, resource="account:synthetic-01")
            store.record_resource_lease(lease)
            intent = self._intent(store)
            store.record_external_intent(intent)
            receipt = ExternalOperationReceipt(
                receipt_id="receipt:op-1",
                operation_id=intent.operation_id,
                run_id=intent.run_id,
                manifest_digest=intent.manifest_digest,
                run_head_digest=intent.run_head_digest,
                idempotency_key=intent.idempotency_key,
                status="succeeded",
                evidence_refs=("evidence:op-1",),
            )
            store.record_external_receipt(receipt)
            note = RuntimeNote(
                resource_ref=lease.resource,
                lease_id=lease.lease_id,
                classification="ephemeral_test_data",
                receipt_ref=receipt.receipt_id,
                cleanup_intent="remove after explicit cleanup decision",
            )
            store.record_runtime_note(note)
            (root / "runtime_notes.md").write_bytes(b"")

            with self.assertRaisesRegex(StoreError, "runtime notes projection"):
                RealSystemRunStore.open(root, state.run_id)

    def test_initialization_recovers_after_partial_authority_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, snapshot = self._state_and_manifest()
            root = Path(temporary) / "store"
            store = RealSystemRunStore.open(root, state.run_id)
            real_atomic_write = TransactionalRunStore._atomic_write

            def crash_before_snapshot_write(path: Path, payload: bytes) -> None:
                if path == root / "environment-snapshot.json":
                    raise OSError("simulated crash before snapshot write")
                real_atomic_write(path, payload)

            with patch.object(
                TransactionalRunStore,
                "_atomic_write",
                side_effect=crash_before_snapshot_write,
            ):
                with self.assertRaisesRegex(OSError, "simulated crash"):
                    self._initialize(store, state, manifest)

            recovered = RealSystemRunStore.open(root, state.run_id)
            self.assertEqual(state.run_id, recovered.read_state().run_id)

    def test_rejects_lease_outside_manifest_synthetic_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, snapshot = self._state_and_manifest()
            store = RealSystemRunStore.open(Path(temporary) / "store", state.run_id)
            self._initialize(store, state, manifest)
            lease = ResourceLease.issue(
                run_id=state.run_id,
                resource="account:not-admitted",
            )

            with self.assertRaisesRegex(StoreError, "synthetic scope"):
                store.record_resource_lease(lease)

    def test_cleanup_rejects_expired_resource_lease(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, snapshot = self._state_and_manifest()
            store = RealSystemRunStore.open(Path(temporary) / "store", state.run_id)
            self._initialize(store, state, manifest)
            lease = ResourceLease.issue(
                run_id=state.run_id,
                resource="account:synthetic-01",
                expires_at="2020-01-01T00:00:00Z",
            )
            ownership_token = lease.issued_ownership_token
            store.record_resource_lease(lease)
            intent = self._intent(store)
            store.record_external_intent(intent)
            receipt = ExternalOperationReceipt(
                receipt_id="receipt:op-1",
                operation_id=intent.operation_id,
                run_id=intent.run_id,
                manifest_digest=intent.manifest_digest,
                run_head_digest=intent.run_head_digest,
                idempotency_key=intent.idempotency_key,
                status="succeeded",
                evidence_refs=("evidence:op-1",),
            )
            store.record_external_receipt(receipt)
            note = RuntimeNote(
                resource_ref=lease.resource,
                lease_id=lease.lease_id,
                classification="ephemeral_test_data",
                receipt_ref=receipt.receipt_id,
                cleanup_intent="remove after explicit cleanup decision",
            )
            store.record_runtime_note(note)
            decision = CleanupDecision(
                decision_id="cleanup:expired-lease",
                run_id=state.run_id,
                manifest_digest=manifest.digest,
                runtime_note_digest=note.digest,
                actor="user:aleda",
            )

            with self.assertRaisesRegex(StoreError, "expired"):
                store.cleanup(note, decision, ownership_token)

    def test_cleanup_rejects_running_run_before_terminal_result_discussion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, snapshot = self._state_and_manifest()
            store = RealSystemRunStore.open(Path(temporary) / "store", state.run_id)
            self._initialize(store, state, manifest)
            lease = ResourceLease.issue(
                run_id=state.run_id,
                resource="account:synthetic-01",
                expires_at="2099-01-01T00:00:00Z",
            )
            ownership_token = lease.issued_ownership_token
            store.record_resource_lease(lease)
            intent = self._intent(store)
            store.record_external_intent(intent)
            receipt = ExternalOperationReceipt(
                receipt_id="receipt:op-1",
                operation_id=intent.operation_id,
                run_id=intent.run_id,
                manifest_digest=intent.manifest_digest,
                run_head_digest=intent.run_head_digest,
                idempotency_key=intent.idempotency_key,
                status="succeeded",
                evidence_refs=("evidence:op-1",),
            )
            store.record_external_receipt(receipt)
            note = RuntimeNote(
                resource_ref=lease.resource,
                lease_id=lease.lease_id,
                classification="ephemeral_test_data",
                receipt_ref=receipt.receipt_id,
                cleanup_intent="remove after explicit cleanup decision",
            )
            store.record_runtime_note(note)
            decision = CleanupDecision(
                decision_id="cleanup:too-early",
                run_id=state.run_id,
                manifest_digest=manifest.digest,
                runtime_note_digest=note.digest,
                actor="user:aleda",
            )

            with self.assertRaisesRegex(StoreError, "terminal result discussion"):
                store.cleanup(note, decision, ownership_token)
            self.assertEqual((), store.read_state().facts.cleanup_decision_digests)

    def test_rejects_constructed_invalid_fact_before_store_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, snapshot = self._state_and_manifest()
            store = RealSystemRunStore.open(Path(temporary) / "store", state.run_id)
            self._initialize(store, state, manifest)
            lease = ResourceLease.issue(
                run_id=state.run_id,
                resource="account:synthetic-01",
            ).model_copy(update={"ownership_token_digest": "not-a-digest"})

            with self.assertRaisesRegex(StoreError, "strict V5.2 successor"):
                store.record_resource_lease(lease)

            self.assertEqual((), store.read_state().facts.leases)

    def test_cleanup_rejects_constructed_decision_with_non_user_actor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, snapshot = self._state_and_manifest()
            store = RealSystemRunStore.open(Path(temporary) / "store", state.run_id)
            self._initialize(store, state, manifest)
            lease = ResourceLease.issue(
                run_id=state.run_id,
                resource="account:synthetic-01",
                expires_at="2099-01-01T00:00:00Z",
            )
            ownership_token = lease.issued_ownership_token
            store.record_resource_lease(lease)
            intent = self._intent(store)
            store.record_external_intent(intent)
            receipt = ExternalOperationReceipt(
                receipt_id="receipt:op-1",
                operation_id=intent.operation_id,
                run_id=intent.run_id,
                manifest_digest=intent.manifest_digest,
                run_head_digest=intent.run_head_digest,
                idempotency_key=intent.idempotency_key,
                status="succeeded",
                evidence_refs=("evidence:op-1",),
            )
            store.record_external_receipt(receipt)
            note = RuntimeNote(
                resource_ref=lease.resource,
                lease_id=lease.lease_id,
                classification="ephemeral_test_data",
                receipt_ref=receipt.receipt_id,
                cleanup_intent="remove after explicit cleanup decision",
            )
            store.record_runtime_note(note)
            decision = CleanupDecision(
                decision_id="cleanup:forged-actor",
                run_id=state.run_id,
                manifest_digest=manifest.digest,
                runtime_note_digest=note.digest,
                actor="user:aleda",
            ).model_copy(update={"actor": "system:forged"})

            with self.assertRaisesRegex(StoreError, "strict cleanup"):
                store.cleanup(note, decision, ownership_token)

    def test_recovery_rejects_journal_that_rewrites_prior_facts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, snapshot = self._state_and_manifest()
            root = Path(temporary) / "store"
            store = RealSystemRunStore.open(root, state.run_id)
            self._initialize(store, state, manifest)
            first = ResourceLease.issue(
                run_id=state.run_id,
                resource="account:synthetic-01",
            )
            store.record_resource_lease(first)
            second = ResourceLease.issue(
                run_id=state.run_id,
                resource="process:worker-2",
            )
            real_atomic_write = TransactionalRunStore._atomic_write

            def crash_before_state_replace(path: Path, payload: bytes) -> None:
                if path == root / "state.json":
                    raise OSError("simulated crash before state replace")
                real_atomic_write(path, payload)

            with patch.object(
                TransactionalRunStore,
                "_atomic_write",
                side_effect=crash_before_state_replace,
            ):
                with self.assertRaisesRegex(OSError, "simulated crash"):
                    store.record_resource_lease(second)

            journal_path = root / "journal.json"
            journal = json.loads(journal_path.read_text(encoding="utf-8"))
            successor = V52RunState.model_validate_json(
                base64.b64decode(journal["state_bytes_b64"], validate=True)
            )
            rewritten_facts = RealSystemFactIndex.model_validate(
                {**successor.facts.model_dump(mode="python"), "leases": (second,)}
            )
            rewritten_state = V52RunState.model_validate(
                {**successor.model_dump(mode="python"), "facts": rewritten_facts}
            )
            event = RealSystemLedgerEvent.model_validate_json(
                base64.b64decode(journal["event_line_b64"], validate=True)
            )
            rewritten_event = RealSystemLedgerEvent.create(
                sequence=event.sequence,
                kind=event.kind,
                fact_id=event.fact_id,
                fact_digest=event.fact_digest,
                previous_digest=event.previous_digest,
                state_digest=rewritten_state.digest,
            )
            journal["state_bytes_b64"] = base64.b64encode(
                canonical_json_bytes(rewritten_state)
            ).decode("ascii")
            journal["event_line_b64"] = base64.b64encode(
                canonical_json_bytes(rewritten_event) + b"\n"
            ).decode("ascii")
            journal_path.write_bytes(canonical_json_bytes(journal))

            with self.assertRaisesRegex(RecoveryError, "successor"):
                RealSystemRunStore.open(root, state.run_id)

    def test_recovery_rejects_journal_with_forged_out_of_scope_appended_lease(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, snapshot = self._state_and_manifest()
            root = Path(temporary) / "store"
            store = RealSystemRunStore.open(root, state.run_id)
            self._initialize(store, state, manifest)
            admitted = ResourceLease.issue(
                run_id=state.run_id,
                resource="account:synthetic-01",
            )
            real_atomic_write = TransactionalRunStore._atomic_write

            def crash_before_state_replace(path: Path, payload: bytes) -> None:
                if path == root / "state.json":
                    raise OSError("simulated crash before state replace")
                real_atomic_write(path, payload)

            with patch.object(
                TransactionalRunStore,
                "_atomic_write",
                side_effect=crash_before_state_replace,
            ):
                with self.assertRaisesRegex(OSError, "simulated crash"):
                    store.record_resource_lease(admitted)

            journal_path = root / "journal.json"
            journal = json.loads(journal_path.read_text(encoding="utf-8"))
            successor = V52RunState.model_validate_json(
                base64.b64decode(journal["state_bytes_b64"], validate=True)
            )
            forged = ResourceLease.issue(
                run_id=state.run_id,
                resource="account:not-admitted",
            )
            forged_facts = RealSystemFactIndex.model_validate(
                {
                    **successor.facts.model_dump(mode="python"),
                    "leases": successor.facts.leases[:-1] + (forged,),
                }
            )
            forged_state = V52RunState.model_validate(
                {**successor.model_dump(mode="python"), "facts": forged_facts}
            )
            event = RealSystemLedgerEvent.model_validate_json(
                base64.b64decode(journal["event_line_b64"], validate=True)
            )
            forged_event = RealSystemLedgerEvent.create(
                sequence=event.sequence,
                kind=event.kind,
                fact_id=forged.lease_id,
                fact_digest=digest_for("resource-lease", forged),
                previous_digest=event.previous_digest,
                state_digest=forged_state.digest,
            )
            journal["state_bytes_b64"] = base64.b64encode(
                canonical_json_bytes(forged_state)
            ).decode("ascii")
            journal["event_line_b64"] = base64.b64encode(
                canonical_json_bytes(forged_event) + b"\n"
            ).decode("ascii")
            journal_path.write_bytes(canonical_json_bytes(journal))

            with self.assertRaisesRegex(RecoveryError, "successor"):
                RealSystemRunStore.open(root, state.run_id)

    def test_recovery_rejects_intent_event_not_bound_to_appended_fact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, snapshot = self._state_and_manifest()
            root = Path(temporary) / "store"
            store = RealSystemRunStore.open(root, state.run_id)
            self._initialize(store, state, manifest)
            intent = self._intent(store)
            real_atomic_write = TransactionalRunStore._atomic_write

            def crash_before_state_replace(path: Path, payload: bytes) -> None:
                if path == root / "state.json":
                    raise OSError("simulated crash before state replace")
                real_atomic_write(path, payload)

            with patch.object(
                TransactionalRunStore,
                "_atomic_write",
                side_effect=crash_before_state_replace,
            ):
                with self.assertRaisesRegex(OSError, "simulated crash"):
                    store.record_external_intent(intent)

            journal_path = root / "journal.json"
            journal = json.loads(journal_path.read_text(encoding="utf-8"))
            event = RealSystemLedgerEvent.model_validate_json(
                base64.b64decode(journal["event_line_b64"], validate=True)
            )
            forged_event = RealSystemLedgerEvent.create(
                sequence=event.sequence,
                kind=event.kind,
                fact_id=event.fact_id,
                fact_digest="f" * 64,
                previous_digest=event.previous_digest,
                state_digest=event.state_digest,
            )
            journal["event_line_b64"] = base64.b64encode(
                canonical_json_bytes(forged_event) + b"\n"
            ).decode("ascii")
            journal_path.write_bytes(canonical_json_bytes(journal))

            with self.assertRaisesRegex(RecoveryError, "successor"):
                RealSystemRunStore.open(root, state.run_id)

    def test_recovery_rejects_forged_manifest_budget_exhaustion_names(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, _ = self._state_and_manifest()
            payload = manifest_payload()
            payload["budgets"] = {
                **payload["budgets"],
                "max_user_actions": 1,
                "max_provider_requests": 1,
            }
            manifest = AdapterManifest.model_validate(payload)
            state = self._state_for_manifest(state, manifest)
            root = Path(temporary) / "store"
            store = RealSystemRunStore.open(root, state.run_id)
            admitted = self._initialize(store, state, manifest)
            baseline = admitted.facts.baseline_spine
            assert baseline is not None
            node = self._baseline_node(
                state,
                manifest,
                store.environment_snapshot(),
                node_id="node-2",
                action="Submit alternate synthetic checkout form",
            )
            store.record_exploration_delta(
                ExplorationDelta.from_node(
                    node=node,
                    parent_node_id=baseline.nodes[0].node_id,
                    evidence_refs=baseline.nodes[0].entry_observation_refs,
                    authority=baseline,
                    proposal=self._baseline_proposal(
                        manifest,
                        node_id="node-2",
                        action="Submit alternate synthetic checkout form",
                    ),
                )
            )
            store.record_external_intent(self._intent(store))
            rejected_intent = self._intent(store, node_id="node-2")
            real_atomic_write = TransactionalRunStore._atomic_write

            def crash_before_state_replace(path: Path, payload: bytes) -> None:
                if path == root / "state.json":
                    raise OSError("simulated crash before state replace")
                real_atomic_write(path, payload)

            with patch.object(
                TransactionalRunStore,
                "_atomic_write",
                side_effect=crash_before_state_replace,
            ):
                with self.assertRaisesRegex(OSError, "simulated crash"):
                    store.record_manifest_budget_exhaustion(rejected_intent)

            journal_path = root / "journal.json"
            journal = json.loads(journal_path.read_text(encoding="utf-8"))
            successor = V52RunState.model_validate_json(
                base64.b64decode(journal["state_bytes_b64"], validate=True)
            )
            exhaustion = successor.facts.manifest_budget_exhaustions[-1]
            forged_exhaustion = exhaustion.model_copy(
                update={"exhausted_budget_names": ("max_provider_requests",)}
            )
            forged_facts = RealSystemFactIndex.model_validate(
                {
                    **successor.facts.model_dump(mode="python"),
                    "manifest_budget_exhaustions": (forged_exhaustion,),
                }
            )
            forged_state = V52RunState.model_validate(
                {**successor.model_dump(mode="python"), "facts": forged_facts}
            )
            event = RealSystemLedgerEvent.model_validate_json(
                base64.b64decode(journal["event_line_b64"], validate=True)
            )
            forged_event = RealSystemLedgerEvent.create(
                sequence=event.sequence,
                kind=event.kind,
                fact_id=event.fact_id,
                fact_digest=forged_exhaustion.digest,
                previous_digest=event.previous_digest,
                state_digest=forged_state.digest,
            )
            journal["state_bytes_b64"] = base64.b64encode(
                canonical_json_bytes(forged_state)
            ).decode("ascii")
            journal["event_line_b64"] = base64.b64encode(
                canonical_json_bytes(forged_event) + b"\n"
            ).decode("ascii")
            journal_path.write_bytes(canonical_json_bytes(journal))

            with self.assertRaisesRegex(RecoveryError, "successor"):
                RealSystemRunStore.open(root, state.run_id)

    def test_recovery_rejects_intent_for_unknown_node_with_rehashed_event(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, _ = self._state_and_manifest()
            root = Path(temporary) / "store"
            store = RealSystemRunStore.open(root, state.run_id)
            self._initialize(store, state, manifest)
            intent = self._intent(store)
            real_atomic_write = TransactionalRunStore._atomic_write

            def crash_before_state_replace(path: Path, payload: bytes) -> None:
                if path == root / "state.json":
                    raise OSError("simulated crash before state replace")
                real_atomic_write(path, payload)

            with patch.object(
                TransactionalRunStore,
                "_atomic_write",
                side_effect=crash_before_state_replace,
            ):
                with self.assertRaisesRegex(OSError, "simulated crash"):
                    store.record_external_intent(intent)

            journal_path = root / "journal.json"
            journal = json.loads(journal_path.read_text(encoding="utf-8"))
            successor = V52RunState.model_validate_json(
                base64.b64decode(journal["state_bytes_b64"], validate=True)
            )
            forged_intent = intent.model_copy(update={"node_id": "unknown-node"})
            forged_facts = RealSystemFactIndex.model_validate(
                {
                    **successor.facts.model_dump(mode="python"),
                    "external_operation_intents": (forged_intent,),
                }
            )
            forged_state = V52RunState.model_validate(
                {**successor.model_dump(mode="python"), "facts": forged_facts}
            )
            event = RealSystemLedgerEvent.model_validate_json(
                base64.b64decode(journal["event_line_b64"], validate=True)
            )
            forged_event = RealSystemLedgerEvent.create(
                sequence=event.sequence,
                kind=event.kind,
                fact_id=event.fact_id,
                fact_digest=forged_intent.digest,
                previous_digest=event.previous_digest,
                state_digest=forged_state.digest,
            )
            journal["state_bytes_b64"] = base64.b64encode(
                canonical_json_bytes(forged_state)
            ).decode("ascii")
            journal["event_line_b64"] = base64.b64encode(
                canonical_json_bytes(forged_event) + b"\n"
            ).decode("ascii")
            journal_path.write_bytes(canonical_json_bytes(journal))

            with self.assertRaisesRegex(RecoveryError, "successor"):
                RealSystemRunStore.open(root, state.run_id)

    def test_recovery_rejects_intent_with_substituted_node_budget(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, _ = self._state_and_manifest()
            root = Path(temporary) / "store"
            store = RealSystemRunStore.open(root, state.run_id)
            self._initialize(store, state, manifest)
            intent = self._intent(store)
            real_atomic_write = TransactionalRunStore._atomic_write

            def crash_before_state_replace(path: Path, payload: bytes) -> None:
                if path == root / "state.json":
                    raise OSError("simulated crash before state replace")
                real_atomic_write(path, payload)

            with patch.object(
                TransactionalRunStore,
                "_atomic_write",
                side_effect=crash_before_state_replace,
            ):
                with self.assertRaisesRegex(OSError, "simulated crash"):
                    store.record_external_intent(intent)

            journal_path = root / "journal.json"
            journal = json.loads(journal_path.read_text(encoding="utf-8"))
            successor = V52RunState.model_validate_json(
                base64.b64decode(journal["state_bytes_b64"], validate=True)
            )
            forged_reservation = intent.reserved_budget.model_copy(
                update={"requests": intent.reserved_budget.requests + 1}
            )
            forged_intent = intent.model_copy(
                update={"reserved_budget": forged_reservation}
            )
            forged_facts = RealSystemFactIndex.model_validate(
                {
                    **successor.facts.model_dump(mode="python"),
                    "budget_reservations": (forged_reservation,),
                    "external_operation_intents": (forged_intent,),
                }
            )
            forged_state = V52RunState.model_validate(
                {**successor.model_dump(mode="python"), "facts": forged_facts}
            )
            event = RealSystemLedgerEvent.model_validate_json(
                base64.b64decode(journal["event_line_b64"], validate=True)
            )
            forged_event = RealSystemLedgerEvent.create(
                sequence=event.sequence,
                kind=event.kind,
                fact_id=event.fact_id,
                fact_digest=forged_intent.digest,
                previous_digest=event.previous_digest,
                state_digest=forged_state.digest,
            )
            journal["state_bytes_b64"] = base64.b64encode(
                canonical_json_bytes(forged_state)
            ).decode("ascii")
            journal["event_line_b64"] = base64.b64encode(
                canonical_json_bytes(forged_event) + b"\n"
            ).decode("ascii")
            journal_path.write_bytes(canonical_json_bytes(journal))

            with self.assertRaisesRegex(RecoveryError, "successor"):
                RealSystemRunStore.open(root, state.run_id)

    def test_recovery_rejects_forged_verification_observation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, _ = self._state_and_manifest()
            root = Path(temporary) / "store"
            store = RealSystemRunStore.open(root, state.run_id)
            egress = self._egress_receipt(state, manifest)
            snapshot = EnvironmentSnapshot.from_admitted_authority(
                manifest=manifest,
                target_identity_digest=state.trajectory.execution_envelope.target_identity_digest,
                supervisor_receipts=(),
                egress_receipt=egress,
            )
            proposal = NodeProposal(
                node_id="verify-recovery",
                source_anchor_id="start",
                target_landmark_id="checkout",
                action_kind="verify_only",
                action_or_probe="Observe checkout result",
                expected_before=("Synthetic checkout form is visible",),
                expected_after=("Synthetic checkout result is visible",),
                derivation_reason="Verify recovered fixture evidence.",
                authority_refs=("trajectory:checkout",),
                execution_scope="synthetic checkout fixture",
                side_effect=None,
                target_systems=(manifest.target.host,),
            )
            head = RealSystemRunHead(
                run_id=state.run_id,
                manifest_digest=manifest.digest,
                environment_snapshot_digest=snapshot.digest,
            )
            proposal = LandmarkVerification.model_validate(
                {
                    **proposal.model_dump(mode="python"),
                    "current_run_head_proof_ref": f"admission:run-head:{head.digest}",
                }
            )
            node = DerivedBehavioralNode.seal(
                proposal,
                entry_observation_refs=("observation:checkout-entry",),
                run_id=state.run_id,
                trajectory_digest=state.trajectory.digest,
                run_head_digest=head.digest,
                execution_envelope_digest=state.trajectory.execution_envelope.digest,
            )
            store.initialize(
                state,
                manifest=manifest,
                baseline_nodes=(node,),
                baseline_proposals=(
                    BaselineNodeProposal(
                        proposal=proposal,
                        entry_observation_refs=("observation:checkout-entry",),
                        budget=None,
                    ),
                ),
                provider_authority=self._provider_authority(state, manifest),
                egress_receipt=egress,
            )
            observation = Observation(
                observation_id="observation:verify-recovery",
                node_id=node.source_anchor_id,
                kind="behavioral",
                observed_state=node.expected_after[0],
                evidence_refs=("evidence:verified-checkout",),
                run_head_digest=node.run_head_digest,
            )
            completion = RealNodeCompletion(
                run_id=state.run_id,
                node_id=node.node_id,
                run_head_digest=node.run_head_digest,
                kind="verification",
                evidence_refs=observation.evidence_refs,
                verification_observation=observation,
            )
            real_atomic_write = TransactionalRunStore._atomic_write

            def crash_before_state_replace(path: Path, payload: bytes) -> None:
                if path == root / "state.json":
                    raise OSError("simulated crash before state replace")
                real_atomic_write(path, payload)

            with patch.object(
                TransactionalRunStore,
                "_atomic_write",
                side_effect=crash_before_state_replace,
            ):
                with self.assertRaisesRegex(OSError, "simulated crash"):
                    store.record_node_completion(completion)

            journal_path = root / "journal.json"
            journal = json.loads(journal_path.read_text(encoding="utf-8"))
            successor = V52RunState.model_validate_json(
                base64.b64decode(journal["state_bytes_b64"], validate=True)
            )
            forged_observation = observation.model_copy(
                update={"observed_state": "Caller-forged verification result"}
            )
            forged_completion = completion.model_copy(
                update={"verification_observation": forged_observation}
            )
            forged_facts = RealSystemFactIndex.model_validate(
                {
                    **successor.facts.model_dump(mode="python"),
                    "node_completions": (forged_completion,),
                }
            )
            forged_state = V52RunState.model_validate(
                {**successor.model_dump(mode="python"), "facts": forged_facts}
            )
            event = RealSystemLedgerEvent.model_validate_json(
                base64.b64decode(journal["event_line_b64"], validate=True)
            )
            forged_event = RealSystemLedgerEvent.create(
                sequence=event.sequence,
                kind=event.kind,
                fact_id=event.fact_id,
                fact_digest=forged_completion.digest,
                previous_digest=event.previous_digest,
                state_digest=forged_state.digest,
            )
            journal["state_bytes_b64"] = base64.b64encode(
                canonical_json_bytes(forged_state)
            ).decode("ascii")
            journal["event_line_b64"] = base64.b64encode(
                canonical_json_bytes(forged_event) + b"\n"
            ).decode("ascii")
            journal_path.write_bytes(canonical_json_bytes(journal))

            with self.assertRaisesRegex(RecoveryError, "successor"):
                RealSystemRunStore.open(root, state.run_id)

    def test_read_rejects_committed_ledger_event_not_bound_to_persisted_fact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, snapshot = self._state_and_manifest()
            root = Path(temporary) / "store"
            store = RealSystemRunStore.open(root, state.run_id)
            self._initialize(store, state, manifest)
            lease = ResourceLease.issue(
                run_id=state.run_id,
                resource="account:synthetic-01",
            )
            store.record_resource_lease(lease)
            events = list(store.read_events())
            committed = events[-1]
            events[-1] = RealSystemLedgerEvent.create(
                sequence=committed.sequence,
                kind=committed.kind,
                fact_id=committed.fact_id,
                fact_digest="f" * 64,
                previous_digest=committed.previous_digest,
                state_digest=committed.state_digest,
            )
            (root / "ledger.jsonl").write_bytes(
                b"".join(canonical_json_bytes(event) + b"\n" for event in events)
            )

            with self.assertRaisesRegex(StoreError, "ledger projection"):
                RealSystemRunStore.open(root, state.run_id)

    def test_recovery_rejects_admission_journal_with_preseeded_facts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, snapshot = self._state_and_manifest()
            root = Path(temporary) / "store"
            store = RealSystemRunStore.open(root, state.run_id)
            real_atomic_write = TransactionalRunStore._atomic_write

            def crash_before_manifest_write(path: Path, payload: bytes) -> None:
                if path == root / "adapter-manifest.json":
                    raise OSError("simulated crash before manifest write")
                real_atomic_write(path, payload)

            with patch.object(
                TransactionalRunStore,
                "_atomic_write",
                side_effect=crash_before_manifest_write,
            ):
                with self.assertRaisesRegex(OSError, "simulated crash"):
                    self._initialize(store, state, manifest)

            journal_path = root / "journal.json"
            journal = json.loads(journal_path.read_text(encoding="utf-8"))
            admitted = V52RunState.model_validate_json(
                base64.b64decode(journal["state_bytes_b64"], validate=True)
            )
            injected = ResourceLease.issue(
                run_id=state.run_id,
                resource="account:synthetic-01",
            )
            injected_facts = RealSystemFactIndex.model_validate(
                {**admitted.facts.model_dump(mode="python"), "leases": (injected,)}
            )
            injected_state = V52RunState.model_validate(
                {**admitted.model_dump(mode="python"), "facts": injected_facts}
            )
            event = RealSystemLedgerEvent.model_validate_json(
                base64.b64decode(journal["ledger_bytes_b64"], validate=True)
            )
            injected_event = RealSystemLedgerEvent.create(
                sequence=event.sequence,
                kind=event.kind,
                fact_id=event.fact_id,
                fact_digest=event.fact_digest,
                previous_digest=event.previous_digest,
                state_digest=injected_state.digest,
            )
            journal["state_bytes_b64"] = base64.b64encode(
                canonical_json_bytes(injected_state)
            ).decode("ascii")
            journal["ledger_bytes_b64"] = base64.b64encode(
                canonical_json_bytes(injected_event) + b"\n"
            ).decode("ascii")
            journal_path.write_bytes(canonical_json_bytes(journal))

            with self.assertRaisesRegex(RecoveryError, "admission journal binding"):
                RealSystemRunStore.open(root, state.run_id)

    def test_recovery_rejects_admission_journal_with_forged_egress_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state, manifest, _ = self._state_and_manifest()
            root = Path(temporary) / "store"
            store = RealSystemRunStore.open(root, state.run_id)
            real_atomic_write = TransactionalRunStore._atomic_write

            def crash_before_manifest_write(path: Path, payload: bytes) -> None:
                if path == root / "adapter-manifest.json":
                    raise OSError("simulated crash before manifest write")
                real_atomic_write(path, payload)

            with patch.object(
                TransactionalRunStore,
                "_atomic_write",
                side_effect=crash_before_manifest_write,
            ):
                with self.assertRaisesRegex(OSError, "simulated crash"):
                    self._initialize(store, state, manifest)

            journal_path = root / "journal.json"
            journal = json.loads(journal_path.read_text(encoding="utf-8"))
            admitted = V52RunState.model_validate_json(
                base64.b64decode(journal["state_bytes_b64"], validate=True)
            )
            assert admitted.facts.egress_receipt is not None
            forged_egress = admitted.facts.egress_receipt.model_copy(
                update={"issued_receipt_digest": "f" * 64}
            )
            forged_facts = RealSystemFactIndex.model_validate(
                {
                    **admitted.facts.model_dump(mode="python"),
                    "egress_receipt": forged_egress,
                }
            )
            forged_state = V52RunState.model_validate(
                {**admitted.model_dump(mode="python"), "facts": forged_facts}
            )
            journal["state_bytes_b64"] = base64.b64encode(
                canonical_json_bytes(forged_state)
            ).decode("ascii")
            journal_path.write_bytes(canonical_json_bytes(journal))

            with self.assertRaisesRegex(RecoveryError, "admission authority"):
                RealSystemRunStore.open(root, state.run_id)
