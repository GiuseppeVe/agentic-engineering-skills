from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

_FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "user_journeys"


class _CountingAdapter:
    """Test-only adapter proxy proving evidence gaps cannot dispatch an action."""

    def __init__(self, adapter: object) -> None:
        self._adapter = adapter
        self.action_count = 0

    def fixture_snapshot(self) -> object:
        return self._adapter.fixture_snapshot()  # type: ignore[attr-defined]

    def fixture_is_active(self) -> bool:
        return self._adapter.fixture_is_active()  # type: ignore[attr-defined]

    def reset_fixture(self, snapshot: object) -> object:
        return self._adapter.reset_fixture(snapshot)  # type: ignore[attr-defined]

    def observe(self, *, anchor_id: str, run_head_digest: str) -> object:
        return self._adapter.observe(  # type: ignore[attr-defined]
            anchor_id=anchor_id, run_head_digest=run_head_digest
        )

    def observe_readonly(self, *, anchor_id: str, run_head_digest: str) -> object:
        return self._adapter.observe_readonly(  # type: ignore[attr-defined]
            anchor_id=anchor_id, run_head_digest=run_head_digest
        )

    def act(self, node: object, *, run_head_digest: str) -> object:
        self.action_count += 1
        return self._adapter.act(node, run_head_digest=run_head_digest)  # type: ignore[attr-defined]


class _FailOnceActionAdapter(_CountingAdapter):
    def __init__(self, adapter: object) -> None:
        super().__init__(adapter)
        self._failed = False

    def act(self, node: object, *, run_head_digest: str) -> object:
        if not self._failed:
            self._failed = True
            raise ValueError("simulated crash after durable seal")
        return super().act(node, run_head_digest=run_head_digest)


class _ObserveFailureAdapter(_CountingAdapter):
    def __init__(self, adapter: object) -> None:
        super().__init__(adapter)
        self.reset_count = 0

    def observe(self, *, anchor_id: str, run_head_digest: str) -> object:
        raise ValueError("observation unavailable")

    def observe_readonly(self, *, anchor_id: str, run_head_digest: str) -> object:
        raise ValueError("observation unavailable")

    def reset_fixture(self, snapshot: object) -> object:
        self.reset_count += 1
        return super().reset_fixture(snapshot)


class _EvidenceGapDeriver:
    def derive_next(self, trajectory: object, spine: object, entry_observation: object) -> object:
        from scripts.graph_v5.models import EvidenceGap

        return EvidenceGap(
            target_landmark_id=spine.frontier.target_landmark_id,
            observation_refs=entry_observation.evidence_refs,
            evidence_gap="Current observation does not identify a safe next action.",
            smallest_needed_input="One in-envelope read-only observation of available controls.",
            exhausted_safe_probes=("probe:visible-controls",),
        )


class _OnboardingDeriver:
    def derive_next(self, trajectory: object, spine: object, entry_observation: object) -> object:
        from scripts.graph_v5.models import NodeProposal

        target = spine.frontier.target_landmark_id
        if target == "L1":
            action = "Choose a valid discipline"
            expected = "Discipline selection is visible."
        else:
            action = "Save valid onboarding"
            expected = "Profile summary is visible."
        return NodeProposal(
            node_id=f"runtime:{target}:{len(spine.nodes) + 1}",
            source_anchor_id=("START" if not spine.nodes else spine.nodes[-1].target_landmark_id),
            target_landmark_id=target,
            action_kind="act",
            action_or_probe=action,
            expected_before=(entry_observation.observed_state,),
            expected_after=(expected,),
            derivation_reason="Persisted frontier observation exposes one catalog action.",
            authority_refs=(
                "trajectory:start_state"
                if not spine.nodes
                else f"trajectory:landmarks:{spine.nodes[-1].target_landmark_id}",
                f"trajectory:landmarks:{target}",
            ),
            execution_scope="onboarding",
            side_effect="fixture:user_journey_action",
            target_systems=("fixture:onboarding",),
        )


class JitUserJourneyTraversalTests(unittest.TestCase):
    def setUp(self) -> None:
        from scripts.graph_v5.adapters.user_journey import FixtureUserJourneyAdapter
        from scripts.graph_v5.models import DerivedSpine, RunHead, SpineFrontier
        from tests.support.trajectory import valid_trajectory_brief

        self.brief = valid_trajectory_brief()
        path = _FIXTURE_ROOT / "trajectory-jit.v1.json"
        self.adapter = FixtureUserJourneyAdapter.from_fixture_file(
            path, "trajectory-jit-healthy"
        )
        self.snapshot = self.adapter.fixture_snapshot()
        self.adapter.reset_fixture(self.snapshot)
        self.run_head = RunHead(
            revision="jit-review-head",
            environment_digest="environment-v1",
            fixture_digest=self.snapshot.snapshot_digest,
        )
        self.spine = DerivedSpine(
            schema_version="graph-v5.derived-spine.v1",
            run_id=self.brief.run_id,
            trajectory_digest=self.brief.digest,
            landmark_order=("L1", "L2"),
            frontier=SpineFrontier(
                last_reached_landmark_id=None, target_landmark_id="L1"
            ),
        )

    def _sealed_action(self) -> object:
        from scripts.graph_v5.models import NodeProposal
        from scripts.graph_v5.spine import ObservableSpine

        entry = self.adapter.observe(
            anchor_id="START", run_head_digest=self.run_head.digest
        )
        proposal = NodeProposal(
            node_id="select-discipline",
            source_anchor_id="START",
            target_landmark_id="L1",
            action_kind="act",
            action_or_probe="Choose a valid discipline",
            expected_before=(entry.observed_state,),
            expected_after=("Discipline selection is visible.",),
            derivation_reason="Observed empty onboarding form.",
            authority_refs=("trajectory:start_state", "trajectory:landmarks:L1"),
            execution_scope="onboarding",
            side_effect="fixture:user_journey_action",
            target_systems=("fixture:onboarding",),
        )
        return ObservableSpine(
            self.brief,
            self.spine,
            current_run_head=self.run_head,
            accepted_observations=(entry,),
        ).seal_next(
            entry_observation=entry,
            proposal=proposal,
        )

    def test_fixture_resolves_only_sealed_catalog_action(self) -> None:
        sealed = self._sealed_action()
        receipt = self.adapter.act(sealed, run_head_digest=self.run_head.digest)
        self.assertEqual(receipt.outcome, "accepted")
        self.assertEqual(receipt.observed_state, "Discipline selection is visible.")

    def test_real_adapter_cannot_act_without_issued_intent(self) -> None:
        """Deleting persisted-intent enforcement must make this contract fail."""

        from scripts.graph_v5.adapters.manifest import AdapterManifest
        from scripts.graph_v5.adapters.service_journey import (
            AdapterError,
            ServiceJourneyAdapter,
        )
        from scripts.graph_v5.canonical import digest_for
        from scripts.graph_v5.environment import EnvironmentSnapshot
        from scripts.graph_v5.models import EgressGateReceipt
        from tests.unit.test_adapter_manifest import manifest_payload

        class _NeverCalledBridge:
            def environment_snapshot(self) -> object:
                raise AssertionError("missing intent must block before bridge access")

        manifest = AdapterManifest.model_validate(manifest_payload())
        egress = EgressGateReceipt(
            run_id="run-real-adapter",
            adapter_manifest_digest=manifest.digest,
            target_identity_digest="a" * 64,
            allowed_hosts=manifest.egress.hosts,
            allowed_protocols=("https",),
            issued_receipt_digest=digest_for(
                "egress-enforcement-receipt", manifest.egress.enforcement_receipt
            ),
        )
        adapter = ServiceJourneyAdapter(
            manifest,
            _NeverCalledBridge(),
            sealed_environment_snapshot=EnvironmentSnapshot.from_admitted_authority(
                manifest=manifest,
                target_identity_digest="a" * 64,
                supervisor_receipts=(),
                egress_receipt=egress,
            ),
        )

        with self.assertRaisesRegex(AdapterError, "ExternalOperationIntent"):
            adapter.act(self._sealed_action(), operation_intent=None)

    def test_fixture_rejects_unsealed_or_forged_action(self) -> None:
        from scripts.graph_v5.adapters.user_journey import AdapterContractError

        with self.assertRaisesRegex(AdapterContractError, "sealed DerivedBehavioralNode"):
            self.adapter.act(object(), run_head_digest=self.run_head.digest)

        forged = self._sealed_action().model_copy(
            update={"target_landmark_id": "L2"}
        )
        with self.assertRaisesRegex(AdapterContractError, "sealed intent"):
            self.adapter.act(forged, run_head_digest=self.run_head.digest)

    def test_adapter_requires_reset_and_satisfies_capability_protocol(self) -> None:
        from scripts.graph_v5.adapters.user_journey import (
            AdapterContractError,
            FixtureUserJourneyAdapter,
            UserJourneyAdapter,
        )

        fresh = FixtureUserJourneyAdapter.from_fixture_file(
            _FIXTURE_ROOT / "trajectory-jit.v1.json", "trajectory-jit-healthy"
        )
        self.assertIsInstance(fresh, UserJourneyAdapter)
        with self.assertRaisesRegex(AdapterContractError, "reset"):
            fresh.observe(anchor_id="START", run_head_digest=self.run_head.digest)
        with self.assertRaisesRegex(AdapterContractError, "reset"):
            fresh.act(self._sealed_action(), run_head_digest=self.run_head.digest)

    def test_adapter_is_static_capability_boundary_not_spine_authority(self) -> None:
        from dataclasses import FrozenInstanceError
        from pathlib import Path

        from scripts.graph_v5.adapters import user_journey

        source = Path(user_journey.__file__).read_text(encoding="utf-8")
        self.assertNotIn("from ..store", source)
        self.assertNotIn("from ..spine", source)
        self.assertFalse(hasattr(self.adapter, "record_derived_spine"))
        import json

        fixture = json.loads(
            (_FIXTURE_ROOT / "trajectory-jit.v1.json").read_text(encoding="utf-8")
        )
        for capability in fixture["scenarios"][0]["action_catalog"]:
            self.assertNotIn("source_anchor_id", capability)
            self.assertNotIn("target_landmark_id", capability)
            self.assertIn("required_observed_state", capability)
        with self.assertRaises(FrozenInstanceError):
            self.snapshot.fixture_id = "mutated"  # type: ignore[misc]

    def test_adapter_rejects_node_sealed_for_foreign_run_head(self) -> None:
        from scripts.graph_v5.adapters.user_journey import AdapterContractError

        sealed = self._sealed_action()
        with self.assertRaisesRegex(AdapterContractError, "Run Head"):
            self.adapter.act(sealed, run_head_digest="foreign-head")

    def test_two_landmarks_expand_and_execute_one_frontier_at_a_time(self) -> None:
        from scripts.graph_v5.models import AcceptedNodeResult, NodeProposal
        from scripts.graph_v5.spine import ObservableSpine

        sealed_l1 = self._sealed_action()
        waiting_l1 = self.spine.with_node(sealed_l1)
        receipt_l1 = self.adapter.act(
            sealed_l1, run_head_digest=self.run_head.digest
        )
        result_l1 = AcceptedNodeResult.create(
            node=sealed_l1,
            observation_refs=receipt_l1.evidence_refs,
            run_head_digest=self.run_head.digest,
            landmark_satisfied=True,
            current_run_head_proof_ref=receipt_l1.evidence_refs[0],
        )
        advanced = waiting_l1.with_accepted_result(result_l1)
        self.assertEqual(advanced.unexecuted_nodes, ())
        entry_l2 = self.adapter.observe(
            anchor_id="L1", run_head_digest=self.run_head.digest
        )
        proposal_l2 = NodeProposal(
            node_id="save-onboarding",
            source_anchor_id="L1",
            target_landmark_id="L2",
            action_kind="act",
            action_or_probe="Save valid onboarding",
            expected_before=(entry_l2.observed_state,),
            expected_after=("Profile summary is visible.",),
            derivation_reason="Accepted L1 evidence exposes save action.",
            authority_refs=("trajectory:landmarks:L1", "trajectory:landmarks:L2"),
            execution_scope="onboarding",
            side_effect="fixture:user_journey_action",
            target_systems=("fixture:onboarding",),
        )
        sealed_l2 = ObservableSpine(
            self.brief,
            advanced,
            current_run_head=self.run_head,
            accepted_observations=(entry_l2,),
        ).seal_next(entry_observation=entry_l2, proposal=proposal_l2)
        waiting_l2 = advanced.with_node(sealed_l2)
        self.assertEqual(waiting_l2.unexecuted_nodes, (sealed_l2,))
        receipt_l2 = self.adapter.act(
            sealed_l2, run_head_digest=self.run_head.digest
        )
        self.assertEqual(receipt_l2.outcome, "accepted")
        self.assertEqual(receipt_l2.observed_state, "Profile summary is visible.")

    def test_adapter_executes_two_intermediate_nodes_toward_same_landmark(self) -> None:
        from scripts.graph_v5.adapters.user_journey import FixtureUserJourneyAdapter
        from scripts.graph_v5.canonical import digest_for
        from scripts.graph_v5.models import (
            AcceptedNodeResult,
            DerivedSpine,
            NodeProposal,
            RunHead,
            SpineFrontier,
        )
        from scripts.graph_v5.spine import ObservableSpine

        scenario = {
            "scenario_id": "intermediate-split",
            "fixture": {"fixture_id": "onboarding-split", "snapshot_digest": "pending"},
            "observations": {
                "START": {
                    "observed_state": "Onboarding form is visible.",
                    "evidence_refs": ["fixture:onboarding-form"],
                },
                "open-discipline-form": {
                    "observed_state": "Discipline form is open.",
                    "evidence_refs": ["fixture:discipline-form-open"],
                },
                "L1": {
                    "observed_state": "Discipline selection is visible.",
                    "evidence_refs": ["fixture:discipline-selected"],
                },
            },
            "action_catalog": [
                {
                    "required_observed_state": "Onboarding form is visible.",
                    "action_kind": "act",
                    "action_or_probe": "Open discipline form",
                    "outcome": "accepted",
                    "observed_state": "Discipline form is open.",
                    "evidence_refs": ["fixture:discipline-form-open"],
                },
                {
                    "required_observed_state": "Discipline form is open.",
                    "action_kind": "act",
                    "action_or_probe": "Choose a valid discipline",
                    "outcome": "accepted",
                    "observed_state": "Discipline selection is visible.",
                    "evidence_refs": ["fixture:discipline-selected"],
                },
            ],
        }
        digest_payload = dict(scenario)
        digest_payload["fixture"] = {"fixture_id": "onboarding-split"}
        scenario["fixture"]["snapshot_digest"] = digest_for(
            "trajectory-jit-fixture-snapshot", digest_payload
        )
        adapter = FixtureUserJourneyAdapter(scenario)
        snapshot = adapter.fixture_snapshot()
        adapter.reset_fixture(snapshot)
        run_head = RunHead(
            revision="split-head",
            environment_digest="environment-v1",
            fixture_digest=snapshot.snapshot_digest,
        )
        spine = DerivedSpine(
            schema_version="graph-v5.derived-spine.v1",
            run_id=self.brief.run_id,
            trajectory_digest=self.brief.digest,
            landmark_order=("L1", "L2"),
            frontier=SpineFrontier(
                last_reached_landmark_id=None,
                target_landmark_id="L1",
            ),
        )
        start = adapter.observe(anchor_id="START", run_head_digest=run_head.digest)
        first_proposal = NodeProposal(
            node_id="runtime-node-1",
            source_anchor_id="START",
            target_landmark_id="L1",
            action_kind="act",
            action_or_probe="Open discipline form",
            expected_before=(start.observed_state,),
            expected_after=("Discipline form is open.",),
            derivation_reason="Entry state exposes discipline form control.",
            authority_refs=("trajectory:start_state", "trajectory:landmarks:L1"),
            execution_scope="onboarding",
            side_effect="fixture:user_journey_action",
            target_systems=("fixture:onboarding",),
        )
        first = ObservableSpine(
            self.brief,
            spine,
            current_run_head=run_head,
            accepted_observations=(start,),
        ).seal_next(entry_observation=start, proposal=first_proposal)
        first_receipt = adapter.act(first, run_head_digest=run_head.digest)
        intermediate = AcceptedNodeResult.create(
            node=first,
            observation_refs=first_receipt.evidence_refs,
            run_head_digest=run_head.digest,
            landmark_satisfied=False,
            current_run_head_proof_ref=None,
        )
        continued = spine.with_node(first).with_accepted_result(intermediate)
        next_entry = adapter.observe(
            anchor_id=first.node_id,
            run_head_digest=run_head.digest,
        )
        second_proposal = NodeProposal(
            node_id="choose-discipline",
            source_anchor_id=first.node_id,
            target_landmark_id="L1",
            action_kind="act",
            action_or_probe="Choose a valid discipline",
            expected_before=(next_entry.observed_state,),
            expected_after=("Discipline selection is visible.",),
            derivation_reason="Intermediate observation exposes valid selection.",
            authority_refs=(
                f"derived-spine:nodes:{first.node_id}",
                "trajectory:landmarks:L1",
            ),
            execution_scope="onboarding",
            side_effect="fixture:user_journey_action",
            target_systems=("fixture:onboarding",),
        )
        second = ObservableSpine(
            self.brief,
            continued,
            current_run_head=run_head,
            accepted_observations=(next_entry,),
        ).seal_next(entry_observation=next_entry, proposal=second_proposal)
        receipt = adapter.act(second, run_head_digest=run_head.digest)
        self.assertEqual(receipt.observed_state, "Discipline selection is visible.")

    def test_verification_only_node_is_explicit_and_never_executes_action(self) -> None:
        from scripts.graph_v5.adapters.user_journey import AdapterContractError
        from scripts.graph_v5.models import LandmarkVerification, Observation
        from scripts.graph_v5.spine import ObservableSpine

        proof = Observation(
            observation_id="proof-l1",
            node_id="START",
            kind="behavioral",
            observed_state="Discipline selection is visible.",
            evidence_refs=("proof:discipline-selection",),
            run_head_digest=self.run_head.digest,
        )
        proposal = LandmarkVerification(
            node_id="verify-l1",
            source_anchor_id="START",
            target_landmark_id="L1",
            action_or_probe="Record already-satisfied L1 proof",
            expected_before=(proof.observed_state,),
            expected_after=(proof.observed_state,),
            derivation_reason="Accepted current-head observation proves L1.",
            authority_refs=("trajectory:start_state", "trajectory:landmarks:L1"),
            execution_scope="onboarding",
            side_effect=None,
            target_systems=("fixture:onboarding",),
            current_run_head_proof_ref=proof.evidence_refs[0],
        )
        sealed = ObservableSpine(
            self.brief,
            self.spine,
            current_run_head=self.run_head,
            accepted_observations=(proof,),
        ).seal_next(entry_observation=proof, proposal=proposal)
        self.assertEqual(sealed.action_kind, "verify_only")
        with self.assertRaisesRegex(AdapterContractError, "verification-only"):
            self.adapter.act(sealed, run_head_digest=self.run_head.digest)

    def test_fixture_catalog_and_snapshot_are_content_addressed_and_unique(self) -> None:
        from copy import deepcopy
        import json
        import tempfile

        from scripts.graph_v5.adapters.user_journey import (
            AdapterContractError,
            FixtureUserJourneyAdapter,
        )

        payload = json.loads(
            (_FIXTURE_ROOT / "trajectory-jit.v1.json").read_text(encoding="utf-8")
        )
        duplicate = deepcopy(payload["scenarios"][0])
        payload["scenarios"].append(duplicate)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "duplicate.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(AdapterContractError, "ambiguous"):
                FixtureUserJourneyAdapter.from_fixture_file(
                    path, "trajectory-jit-healthy"
                )

        scenario = deepcopy(payload["scenarios"][0])
        scenario["action_catalog"].append(deepcopy(scenario["action_catalog"][0]))
        with self.assertRaisesRegex(AdapterContractError, "duplicate"):
            FixtureUserJourneyAdapter(scenario)


class RuntimeJitTraversalTests(unittest.TestCase):
    def _running_runtime(self, root: Path) -> tuple[object, _CountingAdapter]:
        from scripts.graph_v5.adapters.user_journey import FixtureUserJourneyAdapter
        from scripts.graph_v5.environment import HostPreflightConfig, StartRequest
        from scripts.graph_v5.runtime import RuntimeController
        from tests.integration.test_start_transaction import (
            FakeWorkspaceLifecycle,
            FixtureHostProbe,
            _profile,
            _repository,
        )
        from tests.integration.test_trajectory_intake import _bundle, _limits

        store_root = root / "run-store"
        request = StartRequest(
            repository_root=_repository(root),
            requested_base_revision="a" * 40,
            candidate_branch="graph-run/runtime-jit-test",
            candidate_worktree_path=root / "runs" / "runtime-jit-test",
            durable_store_root=store_root,
            host_config=HostPreflightConfig(
                path_reserve_chars=32, volatile_environment_roots=()
            ),
            host_probe=FixtureHostProbe(_profile()),
            workspace_lifecycle=FakeWorkspaceLifecycle(),
        )
        runtime, _ = RuntimeController.start(
            root=store_root,
            confirmed=_bundle(),
            limits=_limits(),
            request=request,
        )
        adapter = FixtureUserJourneyAdapter.from_fixture_file(
            _FIXTURE_ROOT / "trajectory-jit.v1.json", "trajectory-jit-healthy"
        )
        return runtime, _CountingAdapter(adapter)

    def test_insufficient_evidence_pauses_without_action(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            runtime, adapter = self._running_runtime(Path(temporary))

            result = runtime.run_bounded_slice(
                adapter=adapter,
                deriver=_EvidenceGapDeriver(),
            )

            self.assertEqual(result.state.mode, "paused")
            self.assertEqual(
                result.state.trajectory_pause.reason,
                "insufficient_next_node_evidence",
            )
            self.assertEqual(adapter.action_count, 0)
            self.assertEqual(
                result.state.trajectory_pause.evidence_gap,
                "Current observation does not identify a safe next action.",
            )

    def test_evidence_pause_report_is_complete_and_retry_resumes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            runtime, adapter = self._running_runtime(Path(temporary))
            first = runtime.run_bounded_slice(adapter=adapter, deriver=_OnboardingDeriver())
            paused = runtime.run_bounded_slice(adapter=adapter, deriver=_EvidenceGapDeriver())
            pause = paused.state.trajectory_pause
            expected_observation_refs = tuple(
                dict.fromkeys(
                    reference
                    for observation in paused.state.facts.observations
                    for reference in observation.evidence_refs
                )
            )

            self.assertEqual(getattr(pause, "target_landmark_id", None), "L2")
            self.assertEqual(getattr(pause, "frontier_anchor_id", None), "L1")
            self.assertEqual(pause.observation_refs, expected_observation_refs)
            self.assertEqual(first.state.facts.derived_spine.frontier.target_landmark_id, "L2")

            resumed = runtime.run_bounded_slice(adapter=adapter, deriver=_OnboardingDeriver())
            self.assertEqual(resumed.state.mode, "running")
            self.assertEqual(resumed.outcome, "node_changed")
            self.assertEqual(adapter.action_count, 2)

    def test_observation_failure_never_resets_fixture_before_evidence_pause(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            runtime, wrapped = self._running_runtime(Path(temporary))
            adapter = _ObserveFailureAdapter(wrapped._adapter)

            from scripts.graph_v5.runtime import RuntimeError

            with self.assertRaisesRegex(RuntimeError, "fixture observation failed"):
                runtime.run_bounded_slice(adapter=adapter, deriver=_EvidenceGapDeriver())

            self.assertEqual(adapter.reset_count, 0)
            self.assertEqual(adapter.action_count, 0)

    def test_restart_executes_persisted_unexecuted_frontier_without_rederiving(self) -> None:
        from scripts.graph_v5.runtime import RuntimeController, RuntimeError

        with tempfile.TemporaryDirectory() as temporary:
            runtime, wrapped = self._running_runtime(Path(temporary))
            adapter = _FailOnceActionAdapter(wrapped._adapter)
            with self.assertRaisesRegex(RuntimeError, "sealed node execution failed"):
                runtime.run_bounded_slice(adapter=adapter, deriver=_OnboardingDeriver())

            sealed = runtime.state.facts.derived_spine
            self.assertIsNotNone(sealed.frontier.unexecuted_node_id)
            resumed = RuntimeController.open(root=runtime._store.root, run_id=runtime.state.run_id)
            try:
                result = resumed.run_bounded_slice(adapter=adapter, deriver=object())
            except RuntimeError as error:
                self.fail(f"persisted sealed frontier did not resume: {error}")

            self.assertEqual(result.outcome, "node_changed")
            self.assertEqual(len(result.state.facts.derived_spine.nodes), 1)
            self.assertEqual(len(result.state.facts.derived_spine.results), 1)
            self.assertEqual(adapter.action_count, 1)

    def test_resume_uses_persisted_frontier_and_derives_one_node_per_slice(self) -> None:
        from scripts.graph_v5.runtime import RuntimeController

        with tempfile.TemporaryDirectory() as temporary:
            runtime, adapter = self._running_runtime(Path(temporary))
            first = runtime.run_bounded_slice(adapter=adapter, deriver=_OnboardingDeriver())
            self.assertEqual(first.state.facts.derived_spine.frontier.target_landmark_id, "L2")
            self.assertEqual(len(first.state.facts.derived_spine.nodes), 1)
            self.assertEqual(len(first.state.facts.derived_spine.results), 1)
            events = runtime._store.read_events()
            self.assertEqual(
                tuple(event.kind for event in events[-5:]),
                (
                    "derived_spine_initialized",
                    "observed",
                    "derived_spine_sealed",
                    "observed",
                    "derived_spine_result_recorded",
                ),
            )

            resumed = RuntimeController.open(root=runtime._store.root, run_id=first.state.run_id)
            second = resumed.run_bounded_slice(adapter=adapter, deriver=_OnboardingDeriver())
            self.assertEqual(second.state.facts.derived_spine.frontier.target_landmark_id, None)
            self.assertEqual(len(second.state.facts.derived_spine.nodes), 2)
            self.assertEqual(adapter.action_count, 2)

    def test_material_drift_is_digest_bound_and_successor_preserves_predecessor_bytes(self) -> None:
        from copy import deepcopy

        from scripts.graph_v5.models import TrajectoryBrief
        from scripts.graph_v5.runtime import RuntimeController
        from scripts.graph_v5.trajectory import render_trajectory_markdown
        from tests.support.trajectory import confirmation_for, valid_trajectory_payload

        with tempfile.TemporaryDirectory() as temporary:
            runtime, _ = self._running_runtime(Path(temporary))
            predecessor = runtime.state.trajectory_digest
            artifacts = runtime._store.root / "artifacts"
            before = {path.name: path.read_bytes() for path in artifacts.iterdir()}

            paused = runtime.request_trajectory_decision(
                proposed_departure="insert L-new before L2",
                impact="changes confirmed landmark order",
                alternatives=("keep confirmed order", "create successor trajectory"),
                evidence_refs=("obs:drift",),
            )
            decision = paused.pending_trajectory_decision
            self.assertEqual(decision.trajectory_digest, predecessor)
            self.assertEqual(decision.frontier_digest, paused.facts.derived_spine.digest)

            payload = deepcopy(valid_trajectory_payload())
            payload["goal"] = "Verify successor authority after material landmark decision."
            successor_brief = TrajectoryBrief.model_validate(payload)
            from scripts.graph_v5.trajectory import validate_confirmed_trajectory

            successor = validate_confirmed_trajectory(
                successor_brief,
                render_trajectory_markdown(successor_brief),
                confirmation_for(successor_brief),
            )
            recorded = runtime.approve_trajectory_decision(
                decision_id=decision.decision_id,
                confirmed_successor=successor,
            )
            self.assertEqual(
                {path.name: path.read_bytes() for path in artifacts.iterdir() if path.name in before},
                before,
            )
            self.assertEqual(recorded.trajectory_digest, successor_brief.digest)
            self.assertEqual(recorded.mode, "running")
            self.assertIsNone(recorded.pending_trajectory_decision)
            self.assertEqual(recorded.facts.derived_spine.trajectory_digest, successor_brief.digest)
            self.assertEqual(recorded.facts.derived_spine.nodes, ())
            self.assertEqual(
                recorded.facts.trajectory_successors[-1].successor_trajectory_digest,
                successor_brief.digest,
            )

            second_payload = deepcopy(valid_trajectory_payload())
            second_payload["goal"] = "Attempt a second authority for one consumed decision."
            second_brief = TrajectoryBrief.model_validate(second_payload)
            second_successor = validate_confirmed_trajectory(
                second_brief,
                render_trajectory_markdown(second_brief),
                confirmation_for(second_brief),
            )
            from scripts.graph_v5.runtime import RuntimeError

            with self.assertRaisesRegex(RuntimeError, "already has a confirmed successor"):
                runtime.approve_trajectory_decision(
                    decision_id=decision.decision_id,
                    confirmed_successor=second_successor,
                )
            self.assertEqual(len(runtime.state.facts.trajectory_successors), 1)

            reopened = RuntimeController.open(
                root=runtime._store.root,
                run_id=recorded.run_id,
            )
            self.assertEqual(reopened.state.trajectory_digest, successor_brief.digest)

            successor_link = recorded.facts.trajectory_successors[-1]
            (artifacts / f"{successor_link.successor_markdown_digest}.json").unlink()
            from scripts.graph_v5.store import StoreError

            with self.assertRaisesRegex(StoreError, "successor artifacts are invalid"):
                RuntimeController.open(
                    root=runtime._store.root,
                    run_id=recorded.run_id,
                )
