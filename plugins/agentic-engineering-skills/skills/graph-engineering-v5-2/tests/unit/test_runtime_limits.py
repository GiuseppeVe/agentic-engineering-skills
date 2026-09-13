from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.graph_v5.models import (
    DerivedSpine,
    EnvironmentIdentity,
    FactIndex,
    NodeProposal,
    ProofSpec,
    RunHead,
    RunState,
    SpineFrontier,
    VersionedLimits,
    load_run_limits_profile,
)
from tests.support.trajectory import valid_trajectory_payload


ROOT = Path(__file__).resolve().parents[2]


def _limits() -> VersionedLimits:
    return VersionedLimits(
        versions=(
            load_run_limits_profile(
                ROOT / "config" / "policy-fixtures" / "run-limits.test.v1.json"
            ),
        ),
        active_version=1,
    )


def _state(run_id: str = "runtime-limits-state") -> RunState:
    """V5-only state fixture with persisted Derived Spine authority."""

    from scripts.graph_v5.models import TrajectoryBrief

    payload = valid_trajectory_payload()
    payload["run_id"] = run_id
    payload["brief_id"] = f"brief:{run_id}"
    trajectory = TrajectoryBrief.model_validate(payload)
    environment = EnvironmentIdentity(
        repository_revision="a" * 40,
        runtime="python-3.13",
        package_manager="pip-25",
        lockfile_digest="l" * 64,
        host_fingerprint="h" * 64,
    )
    run_head = RunHead(
        revision="a" * 40,
        environment_digest=environment.digest,
        fixture_digest="fixture-intent-v1",
    )
    spine = DerivedSpine(
        schema_version="graph-v5.derived-spine.v1",
        run_id=run_id,
        trajectory_digest=trajectory.digest,
        landmark_order=tuple(item.landmark_id for item in trajectory.landmarks),
        frontier=SpineFrontier(
            last_reached_landmark_id=None,
            target_landmark_id=trajectory.landmarks[0].landmark_id,
        ),
    )
    return RunState(
        schema_version="v5",
        run_id=run_id,
        mode="running",
        trajectory=trajectory,
        facts=FactIndex(
            environment=environment,
            run_head=run_head,
            derived_spine=spine,
        ),
        limits=_limits(),
    )


def _proof_spec(state: RunState, node_id: str = "save-profile") -> ProofSpec:
    spine = state.facts.derived_spine
    assert spine is not None
    return ProofSpec(
        proof_spec_id=f"proof:{state.run_id}:{node_id}",
        node_id=node_id,
        discriminator="persisted result remains observable",
        expected_result="green",
        command=("python", "-m", "unittest", "tests.profile"),
        trajectory_digest=state.trajectory_digest,
        derived_spine_digest=spine.digest,
        landmark_mapping_digest=spine.landmark_mapping_digest,
    )


class _AuthorSignalDeriver:
    def derive_next(self, trajectory: object, spine: object, entry: object) -> NodeProposal:
        return NodeProposal(
            node_id="forbidden-author-signal-node",
            source_anchor_id="START",
            target_landmark_id="L1",
            action_kind="act",
            action_or_probe="Choose a valid discipline",
            expected_before=(entry.observed_state,),
            expected_after=("Discipline selection is visible.",),
            derivation_reason="Author report claims this action works.",
            authority_refs=("author_signal:S1", "trajectory:landmarks:L1"),
            execution_scope="onboarding",
            side_effect="fixture:user_journey_action",
            target_systems=("fixture:onboarding",),
        )


class _CountingAdapter:
    def __init__(self, adapter: object) -> None:
        self._adapter = adapter
        self.actions = 0

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
        self.actions += 1
        return self._adapter.act(node, run_head_digest=run_head_digest)  # type: ignore[attr-defined]


class RuntimeLimitsTests(unittest.TestCase):
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
        from tests.integration.test_trajectory_intake import _bundle

        store_root = root / "run-store"
        request = StartRequest(
            repository_root=_repository(root),
            requested_base_revision="a" * 40,
            candidate_branch="graph-run/runtime-limits",
            candidate_worktree_path=root / "runs" / "runtime-limits",
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
        fixture = ROOT / "fixtures" / "user_journeys" / "trajectory-jit.v1.json"
        adapter = FixtureUserJourneyAdapter.from_fixture_file(fixture, "trajectory-jit-healthy")
        return runtime, _CountingAdapter(adapter)

    def test_slice_limit_is_exactly_one(self) -> None:
        from scripts.graph_v5.runtime import RuntimeError

        with tempfile.TemporaryDirectory() as temporary:
            runtime, adapter = self._running_runtime(Path(temporary))
            with self.assertRaisesRegex(RuntimeError, "exactly one frontier node"):
                runtime.run_bounded_slice(  # type: ignore[attr-defined]
                    adapter=adapter,
                    deriver=_AuthorSignalDeriver(),
                    max_nodes=2,
                )
            self.assertEqual(adapter.actions, 0)

    def test_author_signal_cannot_authorize_next_node_or_action(self) -> None:
        from scripts.graph_v5.runtime import RuntimeError

        with tempfile.TemporaryDirectory() as temporary:
            runtime, adapter = self._running_runtime(Path(temporary))
            with self.assertRaisesRegex(RuntimeError, "Author Signals, philosophy, and rationale"):
                runtime.run_bounded_slice(  # type: ignore[attr-defined]
                    adapter=adapter,
                    deriver=_AuthorSignalDeriver(),
                )
            self.assertEqual(adapter.actions, 0)
            self.assertEqual(runtime.state.facts.derived_spine.nodes, ())  # type: ignore[attr-defined]
            self.assertEqual(len(runtime.state.facts.observations), 1)  # type: ignore[attr-defined]

    def test_author_signal_cannot_open_causal_lead_without_independent_observation(self) -> None:
        from scripts.graph_v5.models import Observation
        from scripts.graph_v5.spine import ObservedFailure
        from scripts.graph_v5.runtime import RuntimeError

        with tempfile.TemporaryDirectory() as temporary:
            cases = (
                ("author-signal:S1", ("author-signal:S1",)),
                ("S1", ("S1",)),
                ("obs:runtime:S1", ("author_signal:S1",)),
            )
            for index, (observation_id, evidence_refs) in enumerate(cases):
                with self.subTest(observation_id=observation_id):
                    case_root = Path(temporary) / str(index)
                    case_root.mkdir()
                    runtime, _ = self._running_runtime(case_root)
                    run_head = runtime.state.facts.run_head  # type: ignore[attr-defined]
                    assert run_head is not None
                    failure = ObservedFailure(
                        node_id="L1",
                        node_index=0,
                        failure_code="author-report-only",
                        observations=(
                            Observation(
                                observation_id=observation_id,
                                node_id="L1",
                                kind="behavioral",
                                observed_state="Author reported an unverified failure.",
                                evidence_refs=evidence_refs,
                                run_head_digest=run_head.digest,
                            ),
                        ),
                        action_receipts=(),
                        seam_receipts=(),
                        selected_variant_ids=(),
                        run_head_digest=run_head.digest,
                        snapshot_digest="fixture-snapshot",
                    )
                    with self.assertRaisesRegex(
                        RuntimeError,
                        "Author Signals cannot open causal leads",
                    ):
                        runtime._record_observed_failure(runtime.state, failure)  # type: ignore[attr-defined]
                    self.assertFalse(runtime.state.facts.leads)  # type: ignore[attr-defined]

    def test_ordinary_node_split_or_variant_cannot_escalate_trajectory(self) -> None:
        from scripts.graph_v5.runtime import RuntimeError

        with tempfile.TemporaryDirectory() as temporary:
            runtime, _ = self._running_runtime(Path(temporary))
            with self.assertRaisesRegex(RuntimeError, "stay autonomous"):
                runtime.request_trajectory_decision(  # type: ignore[attr-defined]
                    proposed_departure="ordinary node split for flaky UI variant",
                    impact="in-envelope conformance repair only",
                    alternatives=("continue autonomous repair",),
                    evidence_refs=("observation:flaky-ui",),
                )
            self.assertFalse(runtime.state.facts.pending_trajectory_decisions)  # type: ignore[attr-defined]

    def test_material_departure_matrix_creates_digest_bound_decision(self) -> None:
        from scripts.graph_v5.runtime import RuntimeError

        cases = (
            ("change goal", "changes confirmed goal"),
            ("change outcome", "changes terminal outcome"),
            ("insert landmark", "changes landmark order"),
            ("change actor", "changes seeded actor identity"),
            ("change fixture", "changes confirmed fixture intent"),
            ("change behavior", "changes expected behavior"),
            ("change scope", "changes allowed scope"),
            ("change forbidden system", "changes forbidden system boundary"),
            ("change side effect", "changes allowed side effect"),
            ("change non-goal", "changes declared non-goal"),
            ("connect payment provider", "introduces external financial authority"),
            ("retain user export", "introduces persistent privacy handling"),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index, (departure, impact) in enumerate(cases, start=1):
                with self.subTest(departure=departure):
                    case_root = root / str(index)
                    case_root.mkdir()
                    runtime, _ = self._running_runtime(case_root)
                    try:
                        state = runtime.request_trajectory_decision(  # type: ignore[attr-defined]
                            proposed_departure=departure,
                            impact=impact,
                            alternatives=("keep confirmed authority", "confirm successor"),
                            evidence_refs=(f"observation:drift:{index}",),
                        )
                    except RuntimeError as error:
                        self.fail(f"material departure was not paused: {error}")
                    decision = state.pending_trajectory_decision
                    self.assertIsNotNone(decision)
                    self.assertEqual(decision.trajectory_digest, state.trajectory_digest)
                    self.assertEqual(decision.frontier_digest, state.facts.derived_spine.digest)

    def test_material_departure_precedes_autonomous_node_mechanics(self) -> None:
        from scripts.graph_v5.runtime import RuntimeError

        with tempfile.TemporaryDirectory() as temporary:
            runtime, _ = self._running_runtime(Path(temporary))
            try:
                state = runtime.request_trajectory_decision(  # type: ignore[attr-defined]
                    proposed_departure="node split that inserts L-new before L2",
                    impact="changes confirmed landmark order",
                    alternatives=("keep confirmed authority", "confirm successor"),
                    evidence_refs=("observation:mixed-drift",),
                )
            except RuntimeError as error:
                self.fail(f"material departure was misclassified autonomous: {error}")
            self.assertIsNotNone(state.pending_trajectory_decision)

    def test_work_authority_binds_current_triple_and_rejects_substituted_proof(self) -> None:
        from scripts.graph_v5.causality import CausalCone
        from scripts.graph_v5.models import ProductWorkReceipt, RepairAttempt
        from scripts.graph_v5.runtime import RuntimeError

        with tempfile.TemporaryDirectory() as temporary:
            runtime, _ = self._running_runtime(Path(temporary))
            current, spine = runtime._ensure_persisted_spine(runtime.state)  # type: ignore[attr-defined]
            cone = CausalCone(cone_id="authority-cone", node_id="save-profile")
            repair_work = ProductWorkReceipt(
                work_id="repair-authority-template",
                kind="repair",
                node_id=cone.node_id,
                cone_id=cone.cone_id,
                cone_digest=cone.digest,
                command_count=1,
                repair_attempts=1,
                command_output_bytes=(0,),
            )
            authorization = runtime.authorize_repair_work(  # type: ignore[attr-defined]
                cone=cone,
                repair=RepairAttempt(
                    attempt_id="repair-authority",
                    cone_id=cone.cone_id,
                    cone_digest=cone.digest,
                    hypothesis="repair current trajectory",
                    changed_dependencies=("profile-store",),
                    changed_files=("profile_store.py",),
                    status="prepared",
                    change_kind="conformance",
                ),
                expected_work=repair_work,
            )
            self.assertEqual(
                (
                    getattr(authorization, "trajectory_digest", None),
                    getattr(authorization, "derived_spine_digest", None),
                    getattr(authorization, "landmark_mapping_digest", None),
                ),
                (
                    current.trajectory_digest,
                    spine.digest,
                    spine.landmark_mapping_digest,
                ),
            )

            proof_work = ProductWorkReceipt(
                work_id="proof-authority-template",
                kind="proof",
                node_id="save-profile",
                cone_id=cone.cone_id,
                cone_digest=cone.digest,
                command_count=1,
                command_output_bytes=(0,),
            )
            proof_spec = _proof_spec(current)
            for field_name in (
                "trajectory_digest",
                "derived_spine_digest",
                "landmark_mapping_digest",
            ):
                with self.subTest(field_name=field_name):
                    forged = proof_spec.model_copy(update={field_name: "f" * 64})
                    with self.assertRaisesRegex(RuntimeError, "trajectory authority"):
                        runtime.authorize_proof_work(  # type: ignore[attr-defined]
                            proof_spec=forged,
                            expected_work=proof_work,
                        )

    def test_status_projects_persisted_frontier_without_authored_journey_scan(self) -> None:
        state = _state("runtime-status-projection")
        from scripts.graph_v5.runtime import RuntimeController

        status = RuntimeController._project_status(state)
        spine = state.facts.derived_spine
        assert spine is not None
        self.assertEqual(getattr(status, "trajectory_digest", None), state.trajectory_digest)
        self.assertEqual(getattr(status, "derived_spine_digest", None), spine.digest)
        self.assertEqual(
            getattr(status, "landmark_mapping_digest", None),
            spine.landmark_mapping_digest,
        )
        self.assertEqual(status.current_node_id, None)
        self.assertEqual(
            status.next_automatic_step,
            "Derive next Behavioral Node toward landmark L1.",
        )
        self.assertEqual(status.progress_fact_count, 0)


if __name__ == "__main__":
    unittest.main()
