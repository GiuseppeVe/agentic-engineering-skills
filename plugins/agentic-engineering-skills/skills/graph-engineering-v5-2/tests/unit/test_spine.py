from __future__ import annotations

import unittest


class DerivedSpineTests(unittest.TestCase):
    def setUp(self) -> None:
        from scripts.graph_v5.models import DerivedSpine, RunHead, SpineFrontier
        from scripts.graph_v5.spine import ObservableSpine
        from tests.support.trajectory import valid_trajectory_brief

        self.brief = valid_trajectory_brief()
        self.spine = DerivedSpine(
            schema_version="graph-v5.derived-spine.v1",
            run_id=self.brief.run_id,
            trajectory_digest=self.brief.digest,
            landmark_order=("L1", "L2"),
            frontier=SpineFrontier(
                last_reached_landmark_id=None, target_landmark_id="L1"
            ),
        )
        self.run_head = RunHead(
            revision="review-head",
            environment_digest="environment-v1",
            fixture_digest="fixture-v1",
        )
        self.entry = self._entry(run_head_digest=self.run_head.digest)
        self.observable = ObservableSpine(
            self.brief,
            self.spine,
            current_run_head=self.run_head,
            accepted_observations=(self.entry,),
        )

    @staticmethod
    def _entry(
        state: str = "Onboarding form is visible.",
        *,
        node_id: str = "START",
        kind: str = "behavioral",
        evidence_refs: tuple[str, ...] = ("fixture:onboarding-form",),
        run_head_digest: str = "h" * 64,
    ) -> object:
        from scripts.graph_v5.models import Observation

        return Observation(
            observation_id=f"observation-{node_id.lower()}",
            node_id=node_id,
            kind=kind,
            observed_state=state,
            evidence_refs=evidence_refs,
            run_head_digest=run_head_digest,
        )

    @staticmethod
    def _proposal(target: str = "L1") -> object:
        from scripts.graph_v5.models import NodeProposal

        return NodeProposal(
            node_id=f"node-{target.lower()}",
            source_anchor_id="START",
            target_landmark_id=target,
            action_kind="act",
            action_or_probe="Choose a valid discipline",
            expected_before=("Onboarding form is visible.",),
            expected_after=("Discipline selection is visible.",),
            derivation_reason="Entry observation shows empty onboarding form.",
            authority_refs=("trajectory:start_state", f"trajectory:landmarks:{target}"),
            execution_scope="onboarding",
            side_effect="fixture:user_journey_action",
            target_systems=("fixture:onboarding",),
        )

    def test_first_node_requires_start_state_evidence(self) -> None:
        from scripts.graph_v5.spine import TraversalError

        with self.assertRaisesRegex(TraversalError, "entry observation"):
            self.observable.seal_next(entry_observation=None, proposal=self._proposal())

    def test_derives_and_seals_only_one_frontier_node(self) -> None:
        from scripts.graph_v5.spine import ObservableSpine, TraversalError

        sealed = self.observable.seal_next(
            entry_observation=self.entry, proposal=self._proposal()
        )
        self.assertEqual(sealed.target_landmark_id, "L1")
        updated = self.spine.with_node(sealed)
        self.assertEqual(len(updated.unexecuted_nodes), 1)
        with self.assertRaisesRegex(TraversalError, "frontier"):
            ObservableSpine(
                self.brief,
                updated,
                current_run_head=self.run_head,
                accepted_observations=(self.entry,),
            ).seal_next(entry_observation=self.entry, proposal=self._proposal())

    def test_already_satisfied_landmark_records_verification_node(self) -> None:
        from scripts.graph_v5.models import LandmarkVerification
        from scripts.graph_v5.spine import ObservableSpine

        satisfied = self._entry(
            "Discipline selection is visible.",
            evidence_refs=("fixture:discipline-selected",),
            run_head_digest=self.run_head.digest,
        )
        proposal = LandmarkVerification(
            node_id="verify-l1",
            source_anchor_id="START",
            target_landmark_id="L1",
            action_or_probe="Record current-run-head proof that discipline selection is visible.",
            expected_before=("Discipline selection is visible.",),
            expected_after=("Discipline selection is visible.",),
            derivation_reason="Current observation already satisfies L1.",
            authority_refs=("trajectory:start_state", "trajectory:landmarks:L1"),
            execution_scope="onboarding",
            side_effect=None,
            target_systems=("fixture:onboarding",),
            current_run_head_proof_ref="fixture:discipline-selected",
        )
        result = ObservableSpine(
            self.brief,
            self.spine,
            current_run_head=self.run_head,
            accepted_observations=(satisfied,),
        ).seal_next(entry_observation=satisfied, proposal=proposal)
        self.assertEqual(result.action_kind, "verify_only")
        self.assertEqual(result.target_landmark_id, "L1")
        self.assertEqual(
            result.current_run_head_proof_ref, "fixture:discipline-selected"
        )
        from scripts.graph_v5.models import AcceptedNodeResult

        contradictory = AcceptedNodeResult.create(
            node=result,
            observation_refs=("fixture:discipline-selected",),
            run_head_digest=self.run_head.digest,
            landmark_satisfied=False,
            current_run_head_proof_ref=None,
        )
        with self.assertRaisesRegex(ValueError, "verification|landmark"):
            self.spine.with_node(result).with_accepted_result(contradictory)

    def test_landmark_reorder_skip_or_substitution_is_rejected(self) -> None:
        from scripts.graph_v5.spine import TraversalError

        for target in ("L2", "FOREIGN"):
            with self.subTest(target=target), self.assertRaises(TraversalError):
                self.observable.seal_next(
                    entry_observation=self.entry, proposal=self._proposal(target)
                )

    def test_sealed_node_rejects_intent_tampering(self) -> None:
        from pydantic import ValidationError

        node = self.observable.seal_next(
            entry_observation=self.entry, proposal=self._proposal()
        )
        with self.assertRaises(ValidationError):
            type(node).model_validate(
                {**node.model_dump(), "action_or_probe": "Mutated action"}
            )

    def test_seal_requires_accepted_behavioral_current_head_observation(self) -> None:
        from scripts.graph_v5.spine import ObservableSpine, TraversalError

        cases = (
            self._entry(kind="operational", run_head_digest=self.run_head.digest),
            self._entry(run_head_digest="foreign-head"),
            self._entry(
                evidence_refs=("unaccepted:evidence",),
                run_head_digest=self.run_head.digest,
            ),
        )
        for observation in cases:
            with self.subTest(observation=observation), self.assertRaises(TraversalError):
                ObservableSpine(
                    self.brief,
                    self.spine,
                    current_run_head=self.run_head,
                    accepted_observations=(self.entry,),
                ).seal_next(entry_observation=observation, proposal=self._proposal())

    def test_sealed_node_binds_exact_authority_head_and_execution_envelope(self) -> None:
        from scripts.graph_v5.spine import TraversalError

        sealed = self.observable.seal_next(
            entry_observation=self.entry, proposal=self._proposal()
        )
        self.assertEqual(sealed.run_id, self.brief.run_id)
        self.assertEqual(sealed.trajectory_digest, self.brief.digest)
        self.assertEqual(sealed.run_head_digest, self.run_head.digest)
        self.assertEqual(
            sealed.execution_envelope_digest, self.brief.execution_envelope.digest
        )
        forbidden = self._proposal().model_copy(
            update={
                "authority_refs": (
                    "trajectory:start_state",
                    "trajectory:landmarks:L1",
                    "trajectory:author_signals:S1",
                )
            }
        )
        with self.assertRaisesRegex(TraversalError, "authority"):
            self.observable.seal_next(entry_observation=self.entry, proposal=forbidden)
        outside = self._proposal().model_copy(
            update={"execution_scope": "payments", "target_systems": ("payments",)}
        )
        with self.assertRaisesRegex(TraversalError, "Execution Envelope"):
            self.observable.seal_next(entry_observation=self.entry, proposal=outside)
        mislabeled = self._proposal().model_copy(
            update={
                "action_or_probe": "Delete repository",
                "target_systems": ("repository",),
            }
        )
        with self.assertRaisesRegex(TraversalError, "Execution Envelope"):
            self.observable.seal_next(
                entry_observation=self.entry,
                proposal=mislabeled,
            )

    def test_foreign_spine_cannot_reuse_sealed_node(self) -> None:
        from scripts.graph_v5.models import DerivedSpine, SpineFrontier

        sealed = self.observable.seal_next(
            entry_observation=self.entry, proposal=self._proposal()
        )
        foreign = DerivedSpine(
            schema_version="graph-v5.derived-spine.v1",
            run_id="foreign-run",
            trajectory_digest="foreign-trajectory",
            landmark_order=("L1", "L2"),
            frontier=SpineFrontier(
                last_reached_landmark_id=None, target_landmark_id="L1"
            ),
        )
        with self.assertRaisesRegex(ValueError, "run|trajectory"):
            foreign.with_node(sealed)

    def test_frontier_advances_only_after_accepted_current_head_result(self) -> None:
        from scripts.graph_v5.models import AcceptedNodeResult

        sealed = self.observable.seal_next(
            entry_observation=self.entry, proposal=self._proposal()
        )
        waiting = self.spine.with_node(sealed)
        accepted = AcceptedNodeResult.create(
            node=sealed,
            observation_refs=("fixture:discipline-selected",),
            run_head_digest=self.run_head.digest,
            landmark_satisfied=True,
            current_run_head_proof_ref="fixture:discipline-selected",
        )
        advanced = waiting.with_accepted_result(accepted)
        self.assertEqual(advanced.frontier.last_reached_landmark_id, "L1")
        self.assertEqual(advanced.frontier.target_landmark_id, "L2")
        self.assertIsNone(advanced.frontier.unexecuted_node_id)
        self.assertEqual(advanced.results, (accepted,))
        stale = accepted.model_copy(update={"run_head_digest": "foreign-head"})
        with self.assertRaises(ValueError):
            waiting.with_accepted_result(stale)

    def test_replay_rejects_action_receipt_from_foreign_fixture_before_proof(self) -> None:
        from scripts.graph_v5.adapters.user_journey import ActionReceipt
        from scripts.graph_v5.spine import NodeVerified, ObservedFailure

        sealed = self.observable.seal_next(
            entry_observation=self.entry, proposal=self._proposal()
        )
        replay_spine = self.spine.with_node(sealed)

        class ForeignFixtureAdapter:
            def act(self, node: object, *, run_head_digest: str) -> ActionReceipt:
                return ActionReceipt(
                    node_id=node.node_id,
                    variant_id="sealed",
                    outcome="accepted",
                    observed_state="Discipline selection is visible.",
                    evidence_refs=("fixture:discipline-selected",),
                    run_head_digest=run_head_digest,
                    snapshot_digest="foreign-fixture",
                )

        replay = self.observable.__class__(
            self.brief,
            replay_spine,
            current_run_head=self.run_head,
            accepted_observations=(),
        )
        outcome = replay.advance(
            adapter=ForeignFixtureAdapter(), node_index=0, previous=None
        )

        self.assertIsInstance(outcome, ObservedFailure)
        self.assertNotIsInstance(outcome, NodeVerified)
        self.assertEqual(outcome.failure_code, "replay_fixture_mismatch")
        self.assertEqual(outcome.action_receipts[0].snapshot_digest, "foreign-fixture")
        self.assertEqual(outcome.observations, ())

    def test_replay_rejects_foreign_node_or_stale_head_receipt_before_observation(self) -> None:
        from scripts.graph_v5.adapters.user_journey import ActionReceipt
        from scripts.graph_v5.spine import ObservedFailure, NodeVerified

        sealed = self.observable.seal_next(
            entry_observation=self.entry, proposal=self._proposal()
        )
        replay_spine = self.spine.with_node(sealed)

        class MismatchedReceiptAdapter:
            def __init__(self, *, node_id: str, run_head_digest: str, fixture_digest: str) -> None:
                self.node_id = node_id
                self.run_head_digest = run_head_digest
                self.fixture_digest = fixture_digest

            def act(self, node: object, *, run_head_digest: str) -> ActionReceipt:
                del node, run_head_digest
                return ActionReceipt(
                    node_id=self.node_id,
                    variant_id="sealed",
                    outcome="accepted",
                    observed_state="Discipline selection is visible.",
                    evidence_refs=("fixture:discipline-selected",),
                    run_head_digest=self.run_head_digest,
                    # Same fixture digest: only receipt identity fields differ.
                    snapshot_digest=self.fixture_digest,
                )

        # Use the actual fixture digest in both receipts so fixture validation
        # cannot mask node/head identity validation.
        cases = (
            ("foreign-node", self.run_head.digest),
            (sealed.node_id, "stale-head"),
        )
        for node_id, run_head_digest in cases:
            with self.subTest(node_id=node_id, run_head_digest=run_head_digest):
                adapter = MismatchedReceiptAdapter(
                    node_id=node_id,
                    run_head_digest=run_head_digest,
                    fixture_digest=self.run_head.fixture_digest,
                )
                replay = self.observable.__class__(
                    self.brief,
                    replay_spine,
                    current_run_head=self.run_head,
                    accepted_observations=(),
                )
                outcome = replay.advance(
                    adapter=adapter, node_index=0, previous=None
                )
                self.assertIsInstance(outcome, ObservedFailure)
                self.assertNotIsInstance(outcome, NodeVerified)
                self.assertEqual(outcome.failure_code, "replay_receipt_mismatch")
                self.assertEqual(outcome.action_receipts[0].snapshot_digest, self.run_head.fixture_digest)
                self.assertEqual(outcome.observations, ())

    def test_intermediate_split_keeps_same_landmark_and_anchors_next_node(self) -> None:
        from scripts.graph_v5.models import AcceptedNodeResult
        from scripts.graph_v5.spine import ObservableSpine

        sealed = self.observable.seal_next(
            entry_observation=self.entry, proposal=self._proposal()
        )
        waiting = self.spine.with_node(sealed)
        intermediate = AcceptedNodeResult.create(
            node=sealed,
            observation_refs=("fixture:discipline-form-open",),
            run_head_digest=self.run_head.digest,
            landmark_satisfied=False,
            current_run_head_proof_ref=None,
        )
        continued = waiting.with_accepted_result(intermediate)
        followup_observation = self._entry(
            "Discipline form is open.",
            node_id=sealed.node_id,
            evidence_refs=("fixture:discipline-form-open",),
            run_head_digest=self.run_head.digest,
        )
        followup = self._proposal().model_copy(
            update={
                "node_id": "confirm-discipline",
                "source_anchor_id": sealed.node_id,
                "expected_before": ("Discipline form is open.",),
                "authority_refs": (
                    f"derived-spine:nodes:{sealed.node_id}",
                    "trajectory:landmarks:L1",
                ),
            }
        )
        second = ObservableSpine(
            self.brief,
            continued,
            current_run_head=self.run_head,
            accepted_observations=(followup_observation,),
        ).seal_next(entry_observation=followup_observation, proposal=followup)
        self.assertEqual(second.target_landmark_id, "L1")
        self.assertEqual(second.source_anchor_id, sealed.node_id)

    def test_terminal_spine_requires_proven_final_landmark(self) -> None:
        from pydantic import ValidationError
        from scripts.graph_v5.models import DerivedSpine, SpineFrontier

        with self.assertRaisesRegex(ValidationError, "proof|result|complete"):
            DerivedSpine(
                schema_version="graph-v5.derived-spine.v1",
                run_id=self.brief.run_id,
                trajectory_digest=self.brief.digest,
                landmark_order=("L1", "L2"),
                frontier=SpineFrontier(
                    last_reached_landmark_id="L2", target_landmark_id=None
                ),
            )

        with self.assertRaisesRegex(ValidationError, "proof|result|complete"):
            DerivedSpine(
                schema_version="graph-v5.derived-spine.v1",
                run_id=self.brief.run_id,
                trajectory_digest=self.brief.digest,
                landmark_order=("L1", "L2"),
                frontier=SpineFrontier(
                    last_reached_landmark_id="L1", target_landmark_id=None
                ),
            )


class DerivedSpineStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile
        from pathlib import Path

        from scripts.graph_v5.models import (
            FactIndex,
            RunHead,
            RunState,
            VersionedLimits,
            load_run_limits_profile,
        )
        from scripts.graph_v5.spine import ObservableSpine
        from scripts.graph_v5.store import StoreCapability, TransactionalRunStore
        from tests.support.trajectory import valid_trajectory_brief

        self.brief = valid_trajectory_brief()
        limits = load_run_limits_profile(
            Path(__file__).resolve().parents[2]
            / "config"
            / "policy-fixtures"
            / "run-limits.test.v1.json"
        )
        self.run_head = RunHead(
            revision="store-review-head",
            environment_digest="environment-v1",
            fixture_digest="fixture-v1",
        )
        self.start_observation = DerivedSpineTests._entry(
            run_head_digest=self.run_head.digest
        )
        self.l1_observation = DerivedSpineTests._entry(
            "Discipline selection is visible.",
            node_id="L1",
            evidence_refs=("fixture:discipline-selected",),
            run_head_digest=self.run_head.digest,
        )
        self.state = RunState(
            schema_version="v5",
            run_id=self.brief.run_id,
            mode="running",
            trajectory=self.brief,
            facts=FactIndex(
                run_head=self.run_head,
                observations=(self.start_observation, self.l1_observation),
            ),
            limits=VersionedLimits(versions=(limits,), active_version=1),
        )
        self.spine = self._spine_for_store(self.brief)
        self.sealed_l1 = ObservableSpine(
            self.brief,
            self.spine,
            current_run_head=self.run_head,
            accepted_observations=(self.start_observation,),
        ).seal_next(
            entry_observation=self.start_observation,
            proposal=DerivedSpineTests._proposal(),
        )
        self.persisted_l1 = self.spine.with_node(self.sealed_l1)
        self._temporary = tempfile.TemporaryDirectory()
        root = Path(self._temporary.name) / "store"
        self.store = TransactionalRunStore.open(
            root,
            StoreCapability._issue_for_runtime(root, self.brief.run_id),
        )
        self.store.initialize(self.state)

    def tearDown(self) -> None:
        self._temporary.cleanup()

    def _successor(self, spine: object) -> object:
        current = self.store.read_state()
        return current.model_copy(
            update={
                "facts": current.facts.model_copy(
                    update={"derived_spine": spine}
                )
            }
        )

    def _accepted_l1(self) -> object:
        from scripts.graph_v5.models import AcceptedNodeResult

        return AcceptedNodeResult.create(
            node=self.sealed_l1,
            observation_refs=self.l1_observation.evidence_refs,
            run_head_digest=self.run_head.digest,
            landmark_satisfied=True,
            current_run_head_proof_ref=self.l1_observation.evidence_refs[0],
        )

    def _persist_l1_and_result(self) -> object:
        self.store.record_derived_spine(
            self.persisted_l1,
            self._successor(self.persisted_l1),
        )
        advanced = self.persisted_l1.with_accepted_result(self._accepted_l1())
        self.store.record_derived_spine_result(advanced, self._successor(advanced))
        return advanced

    def _sealed_l2(self, advanced: object) -> object:
        from scripts.graph_v5.models import NodeProposal
        from scripts.graph_v5.spine import ObservableSpine

        proposal = NodeProposal(
            node_id="node-l2",
            source_anchor_id="L1",
            target_landmark_id="L2",
            action_kind="act",
            action_or_probe="Save valid onboarding",
            expected_before=(self.l1_observation.observed_state,),
            expected_after=("Profile summary is visible.",),
            derivation_reason="Accepted L1 evidence exposes profile save.",
            authority_refs=("trajectory:landmarks:L1", "trajectory:landmarks:L2"),
            execution_scope="onboarding",
            side_effect="fixture:user_journey_action",
            target_systems=("fixture:onboarding",),
        )
        return ObservableSpine(
            self.brief,
            advanced,
            current_run_head=self.run_head,
            accepted_observations=(self.l1_observation,),
        ).seal_next(entry_observation=self.l1_observation, proposal=proposal)

    def test_store_persists_each_historical_spine_projection_and_replays(self) -> None:
        advanced = self._persist_l1_and_result()
        persisted_l2 = advanced.with_node(self._sealed_l2(advanced))
        self.store.record_derived_spine(
            persisted_l2,
            self._successor(persisted_l2),
        )
        self.assertEqual(self.store.read_state().facts.derived_spine, persisted_l2)
        self.assertEqual(
            tuple(event.kind for event in self.store.read_events()),
            (
                "derived_spine_sealed",
                "derived_spine_result_recorded",
                "derived_spine_sealed",
            ),
        )

    def test_first_spine_event_rejects_precomputed_multiple_nodes(self) -> None:
        from scripts.graph_v5.store import StoreError

        advanced = self.persisted_l1.with_accepted_result(self._accepted_l1())
        precomputed = advanced.with_node(self._sealed_l2(advanced))
        with self.assertRaisesRegex(StoreError, "exactly one|precomputed|frontier"):
            self.store.record_derived_spine(precomputed, self._successor(precomputed))

    def test_next_seal_requires_separate_accepted_result_event(self) -> None:
        from scripts.graph_v5.store import StoreError

        self.store.record_derived_spine(
            self.persisted_l1,
            self._successor(self.persisted_l1),
        )
        advanced = self.persisted_l1.with_accepted_result(self._accepted_l1())
        illicit_l2 = advanced.with_node(self._sealed_l2(advanced))
        with self.assertRaisesRegex(StoreError, "result|unexecuted|frontier"):
            self.store.record_derived_spine(illicit_l2, self._successor(illicit_l2))

    def test_landmark_result_rejects_unrelated_current_head_evidence(self) -> None:
        from scripts.graph_v5.models import AcceptedNodeResult
        from scripts.graph_v5.store import StoreError

        self.store.record_derived_spine(
            self.persisted_l1,
            self._successor(self.persisted_l1),
        )
        unrelated = AcceptedNodeResult.create(
            node=self.sealed_l1,
            observation_refs=self.start_observation.evidence_refs,
            run_head_digest=self.run_head.digest,
            landmark_satisfied=True,
            current_run_head_proof_ref=self.start_observation.evidence_refs[0],
        )
        invalid = self.persisted_l1.with_accepted_result(unrelated)
        with self.assertRaisesRegex(StoreError, "landmark|expected|result"):
            self.store.record_derived_spine_result(
                invalid,
                self._successor(invalid),
            )

    def test_intermediate_result_rejects_evidence_that_proves_target_landmark(self) -> None:
        from scripts.graph_v5.models import AcceptedNodeResult
        from scripts.graph_v5.store import StoreError

        self.store.record_derived_spine(
            self.persisted_l1,
            self._successor(self.persisted_l1),
        )
        contradictory = AcceptedNodeResult.create(
            node=self.sealed_l1,
            observation_refs=self.l1_observation.evidence_refs,
            run_head_digest=self.run_head.digest,
            landmark_satisfied=False,
            current_run_head_proof_ref=None,
        )
        invalid = self.persisted_l1.with_accepted_result(contradictory)
        with self.assertRaisesRegex(StoreError, "contradict|landmark|result"):
            self.store.record_derived_spine_result(
                invalid,
                self._successor(invalid),
            )

    def test_store_revalidates_sealed_context_against_envelope_and_observation(self) -> None:
        from scripts.graph_v5.models import DerivedBehavioralNode
        from scripts.graph_v5.store import StoreError

        forged_proposal = DerivedSpineTests._proposal().model_copy(
            update={
                "action_or_probe": "Delete repository",
                "expected_before": ("Fabricated state",),
                "execution_scope": "payments",
                "target_systems": ("payments",),
            }
        )
        forged = DerivedBehavioralNode.seal(
            forged_proposal,
            entry_observation_refs=self.start_observation.evidence_refs,
            run_id=self.brief.run_id,
            trajectory_digest=self.brief.digest,
            run_head_digest=self.run_head.digest,
            execution_envelope_digest=self.brief.execution_envelope.digest,
        )
        persisted = self.spine.with_node(forged)
        with self.assertRaisesRegex(
            StoreError, "Envelope|authority|observation|context|sealed|frontier"
        ):
            self.store.record_derived_spine(
                persisted,
                self._successor(persisted),
            )

    def test_confirmed_genesis_rejects_presealed_derived_spine(self) -> None:
        import tempfile
        from pathlib import Path

        from scripts.graph_v5.models import FactIndex
        from scripts.graph_v5.store import StoreCapability, StoreError, TransactionalRunStore
        from scripts.graph_v5.trajectory import (
            render_trajectory_markdown,
            validate_confirmed_trajectory,
        )
        from tests.support.trajectory import confirmation_for

        presealed = self.state.model_copy(
            update={
                "mode": "boot",
                "facts": FactIndex(
                    run_head=self.run_head,
                    observations=(self.start_observation,),
                    derived_spine=self.persisted_l1,
                ),
            }
        )
        confirmed = validate_confirmed_trajectory(
            self.brief,
            render_trajectory_markdown(self.brief),
            confirmation_for(self.brief),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "confirmed-store"
            store = TransactionalRunStore.open(
                root,
                StoreCapability._issue_for_runtime(root, self.brief.run_id),
            )
            with self.assertRaisesRegex(StoreError, "genesis|Derived Spine|initial"):
                store.initialize_confirmed_run(presealed, confirmed=confirmed)

    @staticmethod
    def _spine_for_store(brief: object) -> object:
        from scripts.graph_v5.models import DerivedSpine, SpineFrontier

        return DerivedSpine(
            schema_version="graph-v5.derived-spine.v1",
            run_id=brief.run_id,
            trajectory_digest=brief.digest,
            landmark_order=("L1", "L2"),
            frontier=SpineFrontier(
                last_reached_landmark_id=None, target_landmark_id="L1"
            ),
        )
