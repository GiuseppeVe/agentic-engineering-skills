from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.graph_v5.adapters.manifest import AdapterManifest
from scripts.graph_v5.canonical import digest_for
from scripts.graph_v5.environment import EnvironmentSnapshot
from scripts.graph_v5.models import (
    BaselineNodeProposal,
    BudgetReservation,
    DerivedBehavioralNode,
    EgressGateReceipt,
    ExternalOperationIntent,
    NodeProposal,
    NodeBudgetProposal,
    RealSystemRunHead,
    V52RunState,
    V52TrajectoryBrief,
    V52TrajectoryConfirmation,
)
from scripts.graph_v5.store import RealSystemRunStore, StoreError
from tests.unit.test_adapter_manifest import manifest_payload
from tests.unit.test_real_admission import valid_bundle, valid_manifest


class RunnerRecoveryTests(unittest.TestCase):
    def test_replay_snapshot_binds_decision_consumption(self) -> None:
        from scripts.graph_v5.models import (
            BudgetWideningAmendment,
            PendingRealSystemDecision,
            RealSystemDecision,
        )
        from scripts.graph_v5.runtime import RealRuntimeController

        with tempfile.TemporaryDirectory() as temporary:
            runtime = RealRuntimeController.start_from_confirmed_bundle(
                root=Path(temporary) / "store",
                bundle=valid_bundle(),
                manifest=valid_manifest(),
            )
            state = runtime.state
            head = state.facts.run_head
            baseline = state.facts.baseline_spine
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
                    "max_wall_seconds": 10,
                },
            )
            pending = PendingRealSystemDecision(
                decision_id="decision:replay-binding",
                kind="budget_widening",
                run_id=state.run_id,
                run_head_digest=head.digest,
                authority_digest=baseline.digest,
                payload_digest=digest_for("real-system-decision-amendment", amendment),
                amendment=amendment,
            )
            runtime._store.record_pending_real_system_decision(pending)
            runtime.apply_real_system_decision(
                RealSystemDecision(
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
            )
            runtime.run_next_persisted_slice()

            replay = runtime.run_final_replay_from_persisted_authority()
            consumption_digests = tuple(
                item.digest
                for item in runtime.state.facts.real_system_decision_consumptions
            )

        self.assertEqual(
            consumption_digests,
            replay.snapshot.decision_consumption_digests,
        )

    def test_pending_exceptional_decision_blocks_persisted_slice(self) -> None:
        from scripts.graph_v5.models import (
            BudgetWideningAmendment,
            PendingRealSystemDecision,
        )
        from scripts.graph_v5.runtime import RealRuntimeController

        with tempfile.TemporaryDirectory() as temporary:
            runtime = RealRuntimeController.start_from_confirmed_bundle(
                root=Path(temporary) / "store",
                bundle=valid_bundle(),
                manifest=valid_manifest(),
            )
            state = runtime.state
            head = state.facts.run_head
            baseline = state.facts.baseline_spine
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
                    "max_wall_seconds": 10,
                },
            )
            runtime._store.record_pending_real_system_decision(
                PendingRealSystemDecision(
                    decision_id="decision:budget-widening",
                    kind="budget_widening",
                    run_id=state.run_id,
                    run_head_digest=head.digest,
                    authority_digest=baseline.digest,
                    payload_digest=digest_for("real-system-decision-amendment", amendment),
                    amendment=amendment,
                )
            )

            with self.assertRaisesRegex(StoreError, "pending exceptional decision"):
                runtime.run_next_persisted_slice()

            self.assertEqual((), runtime.state.facts.external_operation_intents)

    def test_fixture_action_outcome_comes_from_registered_source(self) -> None:
        """Node expectation cannot make an unsupported fixture outcome succeed."""

        from scripts.graph_v5.runtime import RealRuntimeController

        bundle = valid_bundle()
        proposal = bundle.baseline[0].proposal.model_copy(
            update={"expected_after": ("Caller-authored action result",)}
        )
        bundle = bundle.model_copy(
            update={
                "baseline": (
                    BaselineNodeProposal(
                        proposal=proposal,
                        entry_observation_refs=bundle.baseline[0].entry_observation_refs,
                        budget=bundle.baseline[0].budget,
                    ),
                )
            }
        )
        with tempfile.TemporaryDirectory() as temporary:
            runtime = RealRuntimeController.start_from_confirmed_bundle(
                root=Path(temporary) / "store",
                bundle=bundle,
                manifest=valid_manifest(),
            )

            result = runtime.run_next_persisted_slice()

        assert result.receipt is not None
        self.assertEqual("failed", result.receipt.status)
        self.assertEqual("paused", result.state.mode)
        self.assertEqual((), result.state.facts.node_completions)

    def test_fixture_verification_uses_registered_source_evidence_not_node_expectation(self) -> None:
        """Echoing ``expected_after`` would let admitted node bytes forge proof."""

        from scripts.graph_v5.models import BaselineNodeProposal, NodeProposal
        from scripts.graph_v5.runtime import RealRuntimeController

        bundle = valid_bundle()
        forged_expectation = NodeProposal(
            node_id="baseline-forged-verification",
            source_anchor_id="start",
            target_landmark_id="checkout",
            action_kind="verify_only",
            action_or_probe="Observe synthetic checkout state",
            expected_before=("Synthetic checkout form is visible",),
            expected_after=("Caller-authored state with no fixture evidence",),
            derivation_reason="Verification must consume provider evidence.",
            authority_refs=("trajectory:checkout",),
            execution_scope="fixture:checkout",
            side_effect=None,
            target_systems=("127.0.0.1",),
        )
        bundle = bundle.model_copy(
            update={
                "baseline": (
                    BaselineNodeProposal(
                        proposal=forged_expectation,
                        entry_observation_refs=("observation:fixture-start",),
                        budget=None,
                    ),
                )
            }
        )
        with tempfile.TemporaryDirectory() as temporary:
            runtime = RealRuntimeController.start_from_confirmed_bundle(
                root=Path(temporary) / "store",
                bundle=bundle,
                manifest=valid_manifest(),
            )

            with self.assertRaisesRegex(StoreError, "verification observation"):
                runtime.run_next_persisted_slice()

            self.assertEqual((), runtime.state.facts.node_completions)

    def test_persisted_slice_derives_intent_and_reserves_proposal_budget_before_dispatch(self) -> None:
        """Runtime, not caller, derives persisted effectful slice authority."""

        from scripts.graph_v5.runtime import RealRuntimeController

        with tempfile.TemporaryDirectory() as temporary:
            runtime = RealRuntimeController.start_from_confirmed_bundle(
                root=Path(temporary) / "store",
                bundle=valid_bundle(),
                manifest=valid_manifest(),
            )

            result = runtime.run_next_persisted_slice(max_nodes=1)

        self.assertEqual("baseline-checkout", result.node_id)
        intent = result.state.facts.external_operation_intents[0]
        self.assertEqual("baseline-checkout", intent.node_id)
        self.assertEqual(1, intent.reserved_budget.requests)
        self.assertEqual(1_024, intent.reserved_budget.bytes)
        self.assertEqual(10_000, intent.reserved_budget.duration_ms)
        self.assertEqual(1, len(result.state.facts.external_operation_receipts))

    def test_exhausted_persisted_slice_skips_provider_construction_and_snapshot(self) -> None:
        """Moving cap preflight below provider interaction must fail this fifth-slice gate."""

        from scripts.graph_v5.adapters.fixture_journey import PersistedFixtureAuthorityAdapter
        from scripts.graph_v5.runtime import RealRuntimeController

        manifest_payload = valid_manifest().model_dump(mode="python")
        manifest_payload["budgets"] = {
            **manifest_payload["budgets"],
            "max_user_actions": 5,
            "max_provider_requests": 4,
            "max_cost_micros": 5,
            "max_requests": 5,
            "max_persistence_writes": 5,
            "max_duration_ms": 50_000,
        }
        manifest = AdapterManifest.model_validate(manifest_payload)
        bundle = valid_bundle()
        brief = bundle.brief.model_copy(
            update={
                "adapter_manifest_digest": manifest.digest,
                "execution_envelope": bundle.brief.execution_envelope.model_copy(
                    update={"adapter_manifest_digest": manifest.digest}
                ),
            }
        )
        baseline = tuple(
            BaselineNodeProposal(
                proposal=bundle.baseline[0].proposal.model_copy(
                    update={"node_id": f"provider-cap-{index}"}
                ),
                entry_observation_refs=bundle.baseline[0].entry_observation_refs,
                budget=bundle.baseline[0].budget,
            )
            for index in range(1, 6)
        )
        bundle = bundle.model_copy(
            update={
                "brief": brief,
                "confirmation": bundle.confirmation.model_copy(
                    update={
                        "trajectory_digest": brief.digest,
                        "adapter_manifest_digest": manifest.digest,
                    }
                ),
                "baseline": baseline,
            }
        )
        constructions = 0
        snapshots = 0
        dispatches = 0
        original_construct = RealRuntimeController._construct_adapter_from_persisted_provider
        original_snapshot = PersistedFixtureAuthorityAdapter.environment_snapshot
        original_act = PersistedFixtureAuthorityAdapter.act

        def record_construction(controller: object) -> object:
            nonlocal constructions
            constructions += 1
            return original_construct(controller)  # type: ignore[arg-type]

        def record_snapshot(adapter: object) -> object:
            nonlocal snapshots
            snapshots += 1
            return original_snapshot(adapter)  # type: ignore[arg-type]

        def record_dispatch(
            adapter: object, node: object, /, *, operation_intent: object, **kwargs: object
        ) -> object:
            nonlocal dispatches
            dispatches += 1
            return original_act(
                adapter, node, operation_intent=operation_intent, **kwargs
            )  # type: ignore[arg-type]

        with tempfile.TemporaryDirectory() as temporary:
            runtime = RealRuntimeController.start_from_confirmed_bundle(
                root=Path(temporary) / "store", bundle=bundle, manifest=manifest
            )
            with (
                patch.object(
                    RealRuntimeController,
                    "_construct_adapter_from_persisted_provider",
                    new=record_construction,
                ),
                patch.object(
                    PersistedFixtureAuthorityAdapter,
                    "environment_snapshot",
                    new=record_snapshot,
                ),
                patch.object(
                    PersistedFixtureAuthorityAdapter, "act", new=record_dispatch
                ),
            ):
                for _ in range(4):
                    runtime.run_next_persisted_slice()
                before_exhaustion = (constructions, snapshots, dispatches)
                exhausted = runtime.run_next_persisted_slice()
            state = runtime.state

        self.assertEqual((4, 4, 4), before_exhaustion)
        self.assertEqual(before_exhaustion, (constructions, snapshots, dispatches))
        self.assertIsNone(exhausted.receipt)
        self.assertEqual("blocked", state.mode)
        self.assertEqual(4, len(state.facts.external_operation_intents))
        self.assertEqual(4, len(state.facts.external_operation_receipts))
        self.assertEqual(1, len(state.facts.manifest_budget_exhaustions))

    def test_snapshot_read_failure_pauses_reserved_persisted_slice_before_dispatch(self) -> None:
        """Removing post-reservation recovery leaves a live effect intent unsafe to retry."""

        from scripts.graph_v5.adapters.fixture_journey import PersistedFixtureAuthorityAdapter
        from scripts.graph_v5.runtime import RealRuntimeController, RuntimeError

        dispatches = 0

        def unavailable_snapshot(adapter: object) -> object:
            raise OSError("fixture snapshot unavailable")

        def forbidden_dispatch(*arguments: object, **keywords: object) -> object:
            nonlocal dispatches
            dispatches += 1
            raise AssertionError("snapshot failure must prevent adapter action")

        with tempfile.TemporaryDirectory() as temporary:
            runtime = RealRuntimeController.start_from_confirmed_bundle(
                root=Path(temporary) / "store",
                bundle=valid_bundle(),
                manifest=valid_manifest(),
            )
            with (
                patch.object(
                    PersistedFixtureAuthorityAdapter,
                    "environment_snapshot",
                    new=unavailable_snapshot,
                ),
                patch.object(
                    PersistedFixtureAuthorityAdapter, "act", new=forbidden_dispatch
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "cannot read current environment"):
                    runtime.run_next_persisted_slice()
            state = runtime.state

        self.assertEqual(0, dispatches)
        self.assertEqual("paused", state.mode)
        self.assertEqual(1, len(state.facts.external_operation_intents))
        self.assertEqual((), state.facts.external_operation_receipts)
        self.assertEqual((), state.facts.node_completions)

    def test_legacy_slice_snapshot_read_failure_pauses_reserved_intent(self) -> None:
        """Removing legacy post-reservation recovery leaves its test-only primitive unsafe."""

        from scripts.graph_v5.adapters.fixture_journey import PersistedFixtureAuthorityAdapter
        from scripts.graph_v5.runtime import RealRuntimeController, RuntimeError

        def unavailable_snapshot(adapter: object) -> object:
            raise OSError("fixture snapshot unavailable")

        with tempfile.TemporaryDirectory() as temporary:
            runtime = RealRuntimeController.start_from_confirmed_bundle(
                root=Path(temporary) / "store",
                bundle=valid_bundle(),
                manifest=valid_manifest(),
            )
            adapter = runtime._construct_adapter_from_persisted_provider()
            authority = runtime._store.next_executable_authority()
            assert authority is not None
            intent = runtime._derive_persisted_operation_intent(authority)
            with patch.object(
                PersistedFixtureAuthorityAdapter,
                "environment_snapshot",
                new=unavailable_snapshot,
            ):
                with self.assertRaisesRegex(RuntimeError, "cannot read current environment"):
                    runtime._run_bounded_slice_for_test(
                        adapter=adapter,
                        node=authority.node,
                        operation_intent=intent,
                    )
            state = runtime.state

        self.assertEqual("paused", state.mode)
        self.assertEqual((intent,), state.facts.external_operation_intents)
        self.assertEqual((), state.facts.external_operation_receipts)
        self.assertEqual((), state.facts.node_completions)

    def test_verification_only_persisted_slice_completes_without_intent_or_action(self) -> None:
        """Verification consumes only sealed node plus readonly evidence."""

        from scripts.graph_v5.models import BaselineNodeProposal, NodeProposal
        from scripts.graph_v5.runtime import RealRuntimeController

        bundle = valid_bundle()
        verification = NodeProposal(
            node_id="baseline-verify",
            source_anchor_id="start",
            target_landmark_id="checkout",
            action_kind="verify_only",
            action_or_probe="Observe synthetic checkout state",
            expected_before=("Synthetic checkout form is visible",),
            expected_after=("Synthetic checkout result is visible",),
            derivation_reason="Confirmed fixture verification.",
            authority_refs=("trajectory:checkout",),
            execution_scope="fixture:checkout",
            side_effect=None,
            target_systems=("127.0.0.1",),
        )
        bundle = bundle.model_copy(
            update={
                "baseline": (
                    BaselineNodeProposal(
                        proposal=verification,
                        entry_observation_refs=("observation:fixture-start",),
                        budget=None,
                    ),
                )
            }
        )
        with tempfile.TemporaryDirectory() as temporary:
            runtime = RealRuntimeController.start_from_confirmed_bundle(
                root=Path(temporary) / "store",
                bundle=bundle,
                manifest=valid_manifest(),
            )

            result = runtime.run_next_persisted_slice(max_nodes=1)

        self.assertEqual("baseline-verify", result.node_id)
        self.assertEqual((), result.state.facts.external_operation_intents)
        self.assertEqual((), result.state.facts.external_operation_receipts)
        self.assertEqual("verification", result.state.facts.node_completions[0].kind)

    def test_persisted_final_replay_constructs_same_admitted_provider(self) -> None:
        """Replay never accepts a caller-provided adapter substitution."""

        from scripts.graph_v5.runtime import RealRuntimeController

        with tempfile.TemporaryDirectory() as temporary:
            runtime = RealRuntimeController.start_from_confirmed_bundle(
                root=Path(temporary) / "store",
                bundle=valid_bundle(),
                manifest=valid_manifest(),
            )
            runtime.run_next_persisted_slice()

            replay = runtime.run_final_replay_from_persisted_authority()
            persisted = runtime.state

        self.assertIsNone(replay.stop_reason)
        self.assertEqual(1, len(replay.snapshot.operation_intent_digests))
        assert persisted.facts.provider_authority is not None
        self.assertEqual(
            persisted.facts.provider_authority.digest,
            replay.snapshot.provider_authority_digest,
        )
        self.assertEqual(
            tuple(item.digest for item in persisted.facts.node_completions),
            replay.snapshot.node_completion_digests,
        )

    def test_persisted_final_replay_reissues_each_effect_from_persisted_intent(self) -> None:
        """Replay action derives only from persisted idempotent intent bytes."""

        from scripts.graph_v5.adapters.fixture_journey import PersistedFixtureAuthorityAdapter
        from scripts.graph_v5.runtime import RealRuntimeController

        with tempfile.TemporaryDirectory() as temporary:
            runtime = RealRuntimeController.start_from_confirmed_bundle(
                root=Path(temporary) / "store",
                bundle=valid_bundle(),
                manifest=valid_manifest(),
            )
            runtime.run_next_persisted_slice()
            intent = runtime.state.facts.external_operation_intents[0]
            calls: list[tuple[object, object]] = []
            original_act = PersistedFixtureAuthorityAdapter.act

            def record_replay_action(
                adapter: object, node: object, /, *, operation_intent: object, **kwargs: object
            ) -> object:
                calls.append((node, operation_intent))
                return original_act(
                    adapter, node, operation_intent=operation_intent, **kwargs
                )

            with patch.object(
                PersistedFixtureAuthorityAdapter,
                "act",
                new=record_replay_action,
            ):
                replay = runtime.run_final_replay_from_persisted_authority()

        self.assertIsNone(replay.stop_reason)
        self.assertEqual(("baseline-checkout",), tuple(node.node_id for node, _ in calls))
        self.assertEqual((intent,), tuple(operation for _, operation in calls))

    def test_persisted_final_replay_rejects_live_verification_drift(self) -> None:
        """Replay must re-observe verification nodes and reject changed behavior."""

        from scripts.graph_v5.adapters.fixture_journey import PersistedFixtureAuthorityAdapter
        from scripts.graph_v5.models import BaselineNodeProposal, NodeProposal
        from scripts.graph_v5.runtime import RealRuntimeController, RuntimeError

        bundle = valid_bundle()
        verification = NodeProposal(
            node_id="baseline-replay-verify",
            source_anchor_id="start",
            target_landmark_id="checkout",
            action_kind="verify_only",
            action_or_probe="Re-observe synthetic checkout state",
            expected_before=("Synthetic checkout form is visible",),
            expected_after=("Synthetic checkout result is visible",),
            derivation_reason="Final replay must repeat readonly verification.",
            authority_refs=("trajectory:checkout",),
            execution_scope="fixture:checkout",
            side_effect=None,
            target_systems=("127.0.0.1",),
        )
        bundle = bundle.model_copy(
            update={
                "baseline": (
                    BaselineNodeProposal(
                        proposal=verification,
                        entry_observation_refs=("observation:fixture-start",),
                        budget=None,
                    ),
                )
            }
        )
        with tempfile.TemporaryDirectory() as temporary:
            runtime = RealRuntimeController.start_from_confirmed_bundle(
                root=Path(temporary) / "store",
                bundle=bundle,
                manifest=valid_manifest(),
            )
            runtime.run_next_persisted_slice()
            original_observe = PersistedFixtureAuthorityAdapter.observe_readonly

            def drifted_observation(adapter: object, node: object, /, **kwargs: object) -> object:
                observation = original_observe(adapter, node, **kwargs)
                return observation.model_copy(
                    update={"observed_state": "Synthetic checkout replay drifted"}
                )

            with patch.object(
                PersistedFixtureAuthorityAdapter,
                "observe_readonly",
                new=drifted_observation,
            ):
                with self.assertRaisesRegex(RuntimeError, "verification"):
                    runtime.run_final_replay_from_persisted_authority()

    def test_effectful_exploration_replays_its_persisted_proposal_budget(self) -> None:
        """Removing delta proposal/budget persistence makes next slice reject exploration."""

        from scripts.graph_v5.models import (
            BaselineNodeProposal,
            DerivedBehavioralNode,
            NodeBudgetProposal,
            NodeProposal,
        )
        from scripts.graph_v5.runtime import RealRuntimeController

        manifest_payload = valid_manifest().model_dump(mode="python")
        manifest_payload["budgets"] = {
            **manifest_payload["budgets"],
            "max_user_actions": 2,
            "max_provider_requests": 2,
            "max_cost_micros": 2,
        }
        manifest = AdapterManifest.model_validate(manifest_payload)
        bundle = valid_bundle()
        brief = bundle.brief.model_copy(
            update={
                "adapter_manifest_digest": manifest.digest,
                "execution_envelope": bundle.brief.execution_envelope.model_copy(
                    update={"adapter_manifest_digest": manifest.digest}
                ),
            }
        )
        bundle = bundle.model_copy(
            update={
                "brief": brief,
                "confirmation": bundle.confirmation.model_copy(
                    update={
                        "trajectory_digest": brief.digest,
                        "adapter_manifest_digest": manifest.digest,
                    }
                ),
            }
        )
        bounded = BaselineNodeProposal(
            proposal=bundle.baseline[0].proposal,
            entry_observation_refs=bundle.baseline[0].entry_observation_refs,
            budget=NodeBudgetProposal(
                max_user_actions=1,
                max_provider_requests=1,
                max_cost_micros=1,
                max_requests=1, max_bytes=1_024, max_wall_seconds=1
            ),
        )
        bundle = bundle.model_copy(update={"baseline": (bounded,)})
        with tempfile.TemporaryDirectory() as temporary:
            runtime = RealRuntimeController.start_from_confirmed_bundle(
                root=Path(temporary) / "store",
                bundle=bundle,
                manifest=manifest,
            )
            runtime.run_next_persisted_slice()
            state = runtime.state
            head = state.facts.run_head
            assert head is not None
            proposal = NodeProposal(
                node_id="exploration-checkout",
                source_anchor_id="start",
                target_landmark_id="checkout",
                action_kind="act",
                action_or_probe="Submit explored synthetic checkout form",
                expected_before=("Synthetic checkout form is visible",),
                expected_after=("Synthetic checkout result is visible",),
                derivation_reason="Evidence requires one in-scope explored check.",
                authority_refs=("trajectory:checkout",),
                execution_scope="fixture:checkout",
                side_effect="fixture:user_journey_action",
                target_systems=("127.0.0.1",),
            )
            node = DerivedBehavioralNode.seal(
                proposal,
                entry_observation_refs=("observation:exploration",),
                run_id=state.run_id,
                trajectory_digest=state.trajectory.digest,
                run_head_digest=head.digest,
                execution_envelope_digest=state.trajectory.execution_envelope.digest,
            )
            delta = runtime.register_evidence_led_exploration(
                node=node,
                parent_node_id="baseline-checkout",
                evidence_refs=bundle.baseline[0].entry_observation_refs,
                proposal=BaselineNodeProposal(
                    proposal=proposal,
                    entry_observation_refs=("observation:exploration",),
                    budget=bounded.budget,
                ),
            )

            result = runtime.run_next_persisted_slice()

        self.assertEqual(delta.node.node_id, result.node_id)
        self.assertEqual(2, len(result.state.facts.external_operation_intents))

    def test_real_runtime_exposes_no_caller_owned_action_entrypoints(self) -> None:
        """Restoring public adapter/node/intent APIs reopens authority injection."""

        from scripts.graph_v5.runtime import RealRuntimeController

        for name in (
            "start",
            "construct_adapter_from_persisted_authority",
            "run_bounded_slice_from_persisted_authority",
            "run_bounded_slice",
            "final_replay",
        ):
            self.assertFalse(hasattr(RealRuntimeController, name), name)

    def test_paused_verification_slice_never_observes_or_appends_completion(self) -> None:
        """Removing paused-state gate lets readonly verification mutate authority."""

        from scripts.graph_v5.models import BaselineNodeProposal, NodeProposal
        from scripts.graph_v5.runtime import RealRuntimeController, RuntimeError

        bundle = valid_bundle()
        verification = NodeProposal(
            node_id="paused-verify",
            source_anchor_id="start",
            target_landmark_id="checkout",
            action_kind="verify_only",
            action_or_probe="Observe paused synthetic checkout state",
            expected_before=("Synthetic checkout form is visible",),
            expected_after=("Synthetic checkout result is visible",),
            derivation_reason="Paused verification must remain readonly.",
            authority_refs=("trajectory:checkout",),
            execution_scope="fixture:checkout",
            side_effect=None,
            target_systems=("127.0.0.1",),
        )
        bundle = bundle.model_copy(
            update={
                "baseline": (
                    BaselineNodeProposal(
                        proposal=verification,
                        entry_observation_refs=("observation:fixture-start",),
                        budget=None,
                    ),
                )
            }
        )
        with tempfile.TemporaryDirectory() as temporary:
            runtime = RealRuntimeController.start_from_confirmed_bundle(
                root=Path(temporary) / "store", bundle=bundle, manifest=valid_manifest()
            )
            sealed = runtime.environment_snapshot
            runtime._store.pause_for_environment_snapshot_drift(
                sealed.model_copy(update={"target_identity_digest": "f" * 64})
            )
            constructed = 0

            def unexpected_provider() -> object:
                nonlocal constructed
                constructed += 1
                raise AssertionError("paused runtime must not construct or observe adapter")

            runtime._construct_adapter_from_persisted_provider = unexpected_provider  # type: ignore[method-assign]
            with self.assertRaisesRegex(RuntimeError, "running"):
                runtime.run_next_persisted_slice()
            paused_state = runtime.state

        self.assertEqual(0, constructed)
        self.assertEqual((), paused_state.facts.node_completions)

    def test_v52_persisted_slice_pauses_unsettled_nonidempotent_operation(self) -> None:
        """Paused unsettled intent is never redispatched or replaced by another intent."""

        from scripts.graph_v5.runtime import RealRuntimeController, RuntimeError

        with tempfile.TemporaryDirectory() as temporary:
            runtime = RealRuntimeController.start_from_confirmed_bundle(
                root=Path(temporary) / "store",
                bundle=valid_bundle(),
                manifest=valid_manifest(),
            )
            authority = runtime._store.next_executable_authority()
            assert authority is not None
            intent = runtime._derive_persisted_operation_intent(authority)
            runtime._store.record_external_intent(intent)
            runtime._store.reconcile_unsettled_intents()
            constructed = 0

            def unexpected_provider() -> object:
                nonlocal constructed
                constructed += 1
                raise AssertionError("paused unsettled run must not construct adapter")

            runtime._construct_adapter_from_persisted_provider = unexpected_provider  # type: ignore[method-assign]
            with self.assertRaisesRegex(RuntimeError, "running"):
                runtime.run_next_persisted_slice()
            paused_state = runtime.state

        self.assertEqual(0, constructed)
        self.assertEqual((intent,), paused_state.facts.external_operation_intents)
        self.assertEqual((), paused_state.facts.external_operation_receipts)

    def test_paused_persisted_final_replay_never_constructs_provider(self) -> None:
        """Removing replay gate lets paused runs construct provider capabilities."""

        from scripts.graph_v5.runtime import RealRuntimeController, RuntimeError

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            runtime = RealRuntimeController.start_from_confirmed_bundle(
                root=root, bundle=valid_bundle(), manifest=valid_manifest()
            )
            sealed = runtime.environment_snapshot
            runtime._store.pause_for_environment_snapshot_drift(
                sealed.model_copy(update={"target_identity_digest": "f" * 64})
            )
            constructed = 0

            def unexpected_provider() -> object:
                nonlocal constructed
                constructed += 1
                raise AssertionError("paused replay must not construct provider")

            runtime._construct_adapter_from_persisted_provider = unexpected_provider  # type: ignore[method-assign]
            with self.assertRaisesRegex(RuntimeError, "running"):
                runtime.run_final_replay_from_persisted_authority()

        self.assertEqual(0, constructed)

    def test_read_only_status_projects_paused_run_without_provider_or_action(self) -> None:
        """Paused status must report persisted facts, not request executable authority."""

        from scripts.graph_v5.runtime import RealRuntimeController

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            runtime = RealRuntimeController.start_from_confirmed_bundle(
                root=root, bundle=valid_bundle(), manifest=valid_manifest()
            )
            sealed = runtime.environment_snapshot
            runtime._store.pause_for_environment_snapshot_drift(
                sealed.model_copy(update={"target_identity_digest": "f" * 64})
            )

            status = RealRuntimeController.read_only_status(
                root=root, run_id=runtime.state.run_id
            )

        self.assertEqual("paused", status.mode)
        self.assertIsNone(status.next_executable_node_id)

    def test_read_only_status_projects_recovery_pending_journal_without_writing(self) -> None:
        """Status must report recovery pending instead of invoking mutating recovery."""

        from scripts.graph_v5.runtime import RealRuntimeController

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            runtime = RealRuntimeController.start_from_confirmed_bundle(
                root=root, bundle=valid_bundle(), manifest=valid_manifest()
            )
            run_id = runtime.state.run_id
            before = (root / "state.json").read_bytes()
            (root / "journal.json").write_bytes(b"pending-recovery-test")

            status = RealRuntimeController.read_only_status(
                root=root, run_id=run_id
            )

            self.assertEqual(before, (root / "state.json").read_bytes())
        self.assertEqual("recovery_pending", status.mode)
        self.assertIsNone(status.next_executable_node_id)

    def test_store_rejects_verification_completion_without_persisted_observation(self) -> None:
        """Arbitrary verification evidence must not complete a sealed verify-only node."""

        from scripts.graph_v5.models import (
            BaselineNodeProposal,
            NodeProposal,
            Observation,
            RealNodeCompletion,
        )
        from scripts.graph_v5.runtime import RealRuntimeController
        from scripts.graph_v5.store import StoreError

        bundle = valid_bundle()
        verification = NodeProposal(
            node_id="forged-verify",
            source_anchor_id="start",
            target_landmark_id="checkout",
            action_kind="verify_only",
            action_or_probe="Observe synthetic checkout state",
            expected_before=("Synthetic checkout form is visible",),
            expected_after=("Synthetic checkout result is visible",),
            derivation_reason="Verification completion needs durable observation.",
            authority_refs=("trajectory:checkout",),
            execution_scope="fixture:checkout",
            side_effect=None,
            target_systems=("127.0.0.1",),
        )
        bundle = bundle.model_copy(
            update={
                "baseline": (
                    BaselineNodeProposal(
                        proposal=verification,
                        entry_observation_refs=("observation:fixture-start",),
                        budget=None,
                    ),
                )
            }
        )
        with tempfile.TemporaryDirectory() as temporary:
            runtime = RealRuntimeController.start_from_confirmed_bundle(
                root=Path(temporary) / "store", bundle=bundle, manifest=valid_manifest()
            )
            head = runtime.state.facts.run_head
            assert head is not None
            forged = RealNodeCompletion(
                run_id=runtime.state.run_id,
                node_id="forged-verify",
                run_head_digest=head.digest,
                kind="verification",
                evidence_refs=("evidence:forged",),
                verification_observation=Observation(
                    observation_id="forged-verify-observation",
                    node_id="start",
                    kind="operational",
                    observed_state="Synthetic checkout result is visible",
                    evidence_refs=("evidence:forged",),
                    run_head_digest=head.digest,
                ),
            )

            with self.assertRaisesRegex(StoreError, "verification observation"):
                runtime._store.record_node_completion(forged)

    def test_final_replay_rejects_forged_verification_observation(self) -> None:
        """Replay must reject non-behavioral evidence even when bytes otherwise match."""

        from scripts.graph_v5.models import BaselineNodeProposal, NodeProposal
        from scripts.graph_v5.proof import ProofLadderError, RealFinalReplaySnapshot
        from scripts.graph_v5.runtime import RealRuntimeController

        bundle = valid_bundle()
        verification = NodeProposal(
            node_id="replay-forged-verify",
            source_anchor_id="start",
            target_landmark_id="checkout",
            action_kind="verify_only",
            action_or_probe="Observe synthetic checkout state",
            expected_before=("Synthetic checkout form is visible",),
            expected_after=("Synthetic checkout result is visible",),
            derivation_reason="Replay must bind readonly evidence.",
            authority_refs=("trajectory:checkout",),
            execution_scope="fixture:checkout",
            side_effect=None,
            target_systems=("127.0.0.1",),
        )
        bundle = bundle.model_copy(
            update={
                "baseline": (
                    BaselineNodeProposal(
                        proposal=verification,
                        entry_observation_refs=("observation:fixture-start",),
                        budget=None,
                    ),
                )
            }
        )
        with tempfile.TemporaryDirectory() as temporary:
            runtime = RealRuntimeController.start_from_confirmed_bundle(
                root=Path(temporary) / "store", bundle=bundle, manifest=valid_manifest()
            )
            runtime.run_next_persisted_slice()
            state = runtime.state
            completion = state.facts.node_completions[0]
            observation = completion.verification_observation
            assert observation is not None
            forged = completion.model_copy(
                update={
                    "verification_observation": observation.model_copy(
                        update={"kind": "operational"}
                    )
                }
            )
            forged_state = state.model_copy(
                update={
                    "facts": state.facts.model_copy(
                        update={"node_completions": (forged,)}
                    )
                }
            )

            with self.assertRaisesRegex(ProofLadderError, "verification completion"):
                RealFinalReplaySnapshot.from_state(
                    forged_state,
                    environment_snapshot=runtime.environment_snapshot,
                    manifest=runtime.manifest,
                )

    def test_reopened_unsettled_external_operation_pauses_without_retry(self) -> None:
        manifest = AdapterManifest.model_validate(manifest_payload())
        brief = V52TrajectoryBrief(
            schema_version="graph-v5.trajectory-brief.v2",
            run_id="run-recovery",
            brief_id="brief-recovery",
            created_at="2026-09-12T08:00:00Z",
            goal="Prove restart safety for a real external operation.",
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
            confirmed_at="2026-09-12T08:01:00Z",
            confirmation_evidence_ref="conversation:recovery-test",
        )
        state = V52RunState(
            schema_version="graph-v5.run-state.v2",
            run_id=brief.run_id,
            mode="running",
            trajectory=brief,
            confirmation=confirmation,
        )
        egress = EgressGateReceipt(
            run_id=state.run_id,
            adapter_manifest_digest=manifest.digest,
            target_identity_digest=state.trajectory.execution_envelope.target_identity_digest,
            allowed_hosts=manifest.egress.hosts,
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
        head = RealSystemRunHead(
            run_id=state.run_id,
            manifest_digest=manifest.digest,
            environment_snapshot_digest=snapshot.digest,
        )
        proposal = NodeProposal(
                node_id="node:recovery",
                source_anchor_id="START",
                target_landmark_id="L1",
                action_kind="act",
                action_or_probe="Submit recovery fixture data",
                expected_before=("Fixture ready",),
                expected_after=("Fixture changed",),
                derivation_reason="Admitted recovery operation.",
                authority_refs=("trajectory:start_state",),
                execution_scope="service",
                side_effect="bridge:act",
                target_systems=(manifest.target.host,),
        )
        baseline = DerivedBehavioralNode.seal(
            proposal,
            entry_observation_refs=("evidence:recovery",),
            run_id=state.run_id,
            trajectory_digest=state.trajectory.digest,
            run_head_digest=head.digest,
            execution_envelope_digest=state.trajectory.execution_envelope.digest,
        )
        baseline_proposal = BaselineNodeProposal(
            proposal=proposal,
            entry_observation_refs=("evidence:recovery",),
            budget=NodeBudgetProposal(
                max_user_actions=1,
                max_provider_requests=1,
                max_cost_micros=1,
                max_requests=1, max_bytes=1_024, max_wall_seconds=1
            ),
        )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            store = RealSystemRunStore.open(root, state.run_id)
            with self.assertRaisesRegex(StoreError, "admitted provider authority"):
                store.initialize(
                    state,
                    manifest=manifest,
                    baseline_nodes=(baseline,),
                    baseline_proposals=(baseline_proposal,),
                    egress_receipt=egress,
                )
            store.initialize(
                state,
                manifest=manifest,
                baseline_nodes=(baseline,),
                baseline_proposals=(baseline_proposal,),
                provider_authority={
                    "schema_version": "graph-v5.admitted-provider-authority.v1",
                    "adapter_id": manifest.adapter_id,
                    "provider_id": "service-host-provider.v1",
                    "source_identity_digest": state.trajectory.execution_envelope.target_identity_digest,
                },
                egress_receipt=egress,
            )
            admitted = store.read_state()
            assert admitted.facts.run_head is not None
            authority = store.next_executable_authority()
            assert authority is not None
            from scripts.graph_v5.models import derive_persisted_external_operation_intent

            store.record_external_intent(
                derive_persisted_external_operation_intent(admitted, authority)
            )

            resumed = RealSystemRunStore.open(root, state.run_id).read_state()

            self.assertEqual(resumed.mode, "paused")
            self.assertEqual(len(resumed.facts.external_operation_intents), 1)
            self.assertEqual(resumed.facts.external_operation_receipts, ())
