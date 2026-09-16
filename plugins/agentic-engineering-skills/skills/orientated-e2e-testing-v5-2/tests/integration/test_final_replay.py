from __future__ import annotations

"""Final replay consumes only durable frozen Derived Spine authority."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.graph_v5.canonical import digest_for
from scripts.graph_v5.adapters.user_journey import ActionReceipt, FixtureReceipt, FixtureSnapshot
from scripts.graph_v5.causality import CausalCone
from scripts.graph_v5.models import IterationFact, Observation, ProofResult, ProofSpec, TrajectoryBrief
from scripts.graph_v5.proof import RoleRegistry
from tests.integration.test_start_transaction import FakeWorkspaceLifecycle, FixtureHostProbe, _profile, _repository
from tests.integration.test_trajectory_intake import _bundle, _limits


class _ReplayAdapter:
    spine_kind = "user_journey"

    def __init__(self, digest: str, fail: str | None = None) -> None:
        self.snapshot = FixtureSnapshot("final-replay", digest, "final-replay-adapter")
        self.active = False
        self.fail = fail
        self.reset_count = 0
        self.executed: list[str] = []

    def fixture_snapshot(self) -> FixtureSnapshot: return self.snapshot
    def fixture_is_active(self) -> bool: return self.active
    def reset_fixture(self, snapshot: FixtureSnapshot) -> FixtureReceipt:
        if snapshot != self.snapshot: raise ValueError("foreign fixture")
        self.active = True; self.reset_count += 1; self.executed.clear()
        return FixtureReceipt(snapshot.fixture_id, snapshot.snapshot_digest, snapshot.adapter_id)
    def observe_readonly(self, *, anchor_id: str, run_head_digest: str) -> Observation:
        state = {"START": "Onboarding form is visible.", "L1": "Discipline selection is visible.", "L2": "Profile summary is visible."}[anchor_id]
        return Observation(
            observation_id=f"observe:{anchor_id}:{run_head_digest}",
            node_id=anchor_id,
            kind="behavioral",
            observed_state=state,
            evidence_refs=(f"fixture:{anchor_id}",),
            run_head_digest=run_head_digest,
        )
    def act(self, node: object, *, run_head_digest: str) -> ActionReceipt:
        if not self.active: raise ValueError("fixture inactive")
        node_id = getattr(node, "node_id"); self.executed.append(node_id)
        state = "Replay regression" if node_id == self.fail else getattr(node, "expected_after")[-1]
        return ActionReceipt(node_id, "primary", "accepted", state, (f"fixture:{node_id}",), run_head_digest, self.snapshot.snapshot_digest)


class _Deriver:
    def derive_next(self, trajectory: object, spine: object, entry: Observation) -> object:
        from scripts.graph_v5.models import NodeProposal
        target = spine.frontier.target_landmark_id
        landmark = next(
            item for item in trajectory.landmarks if item.landmark_id == target
        )
        return NodeProposal(
            node_id=f"replay:{target}:{len(spine.nodes)+1}",
            source_anchor_id="START" if not spine.nodes else spine.nodes[-1].target_landmark_id,
            target_landmark_id=target, action_kind="act",
            action_or_probe="Choose a valid discipline" if target == "L1" else "Save valid onboarding",
            expected_before=(entry.observed_state,),
            expected_after=(landmark.acceptance[0],),
            derivation_reason="Current frontier yields one sealed fixture action.",
            authority_refs=("trajectory:start_state" if not spine.nodes else f"trajectory:landmarks:{spine.nodes[-1].target_landmark_id}", f"trajectory:landmarks:{target}"),
            execution_scope="onboarding", side_effect="fixture:user_journey_action", target_systems=("fixture:onboarding",),
        )


class FinalReplayIntegrationTests(unittest.TestCase):
    def _runtime(
        self, *, l1_acceptance: list[str] | None = None
    ) -> tuple[object, _ReplayAdapter]:
        from scripts.graph_v5.environment import HostPreflightConfig, StartRequest
        from scripts.graph_v5.runtime import RuntimeController
        from scripts.graph_v5.trajectory import render_trajectory_markdown, validate_confirmed_trajectory
        from tests.support.trajectory import confirmation_for
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup); root = Path(temp.name)
        request = StartRequest(repository_root=_repository(root), requested_base_revision="a"*40,
            candidate_branch=f"graph-run/final-{self._testMethodName}", candidate_worktree_path=root/"runs"/self._testMethodName,
            durable_store_root=root/"store", host_config=HostPreflightConfig(path_reserve_chars=32, volatile_environment_roots=()),
            host_probe=FixtureHostProbe(_profile()), workspace_lifecycle=FakeWorkspaceLifecycle())
        base_bundle = _bundle()
        brief_payload = base_bundle.brief.model_dump(mode="python")
        # RoleRegistry correctly scopes its fresh-context guard by run.  Keep
        # each independently persisted integration fixture in its own run.
        brief_payload["run_id"] = f"run-final-{self._testMethodName}"
        brief_payload["brief_id"] = f"brief-final-{self._testMethodName}"
        brief_payload["terminal_outcome"] = {
            "description": "Profile summary is visible.",
            "acceptance": [brief_payload["landmarks"][1]["acceptance"][0]],
        }
        if l1_acceptance is not None:
            brief_payload["landmarks"][0]["acceptance"] = l1_acceptance
        brief = TrajectoryBrief.model_validate(brief_payload)
        bundle = validate_confirmed_trajectory(
            brief, render_trajectory_markdown(brief), confirmation_for(brief)
        )
        runtime, _ = RuntimeController.start(root=root/"store", confirmed=bundle, limits=_limits(), request=request)
        return runtime, _ReplayAdapter(runtime.state.fixture_intent_digest)

    def _complete(self, runtime: object, adapter: _ReplayAdapter) -> object:
        for _ in range(2): runtime.run_bounded_slice(adapter=adapter, deriver=_Deriver())
        spine = runtime.state.facts.derived_spine
        self.assertIsNone(spine.frontier.target_landmark_id)
        return runtime.freeze_derived_spine(adapter=adapter)

    def _spec(self, runtime: object) -> ProofSpec:
        state = runtime.state; spine = state.facts.derived_spine
        return ProofSpec(
            proof_spec_id="final-replay",
            node_id=spine.nodes[-1].node_id,
            discriminator="terminal frozen replay",
            expected_result="green",
            command=("fixture", "replay"),
            trajectory_digest=state.trajectory_digest,
            derived_spine_digest=spine.digest,
            landmark_mapping_digest=spine.landmark_mapping_digest,
        )

    def _semantic(self, runtime: object, spec: ProofSpec) -> object:
        registry = RoleRegistry()
        def attest(snapshot: object, proofs: object, bundle: str, result: str) -> object:
            del proofs
            state = runtime.state
            dispatch = registry.issue(state=state, cone=CausalCone(cone_id=f"replay:{spec.node_id}", node_id=spec.node_id), proof_spec=spec, role="semantic_reviewer", identity=f"semantic:{self._testMethodName}:{snapshot.digest[:8]}", context_id=f"final-replay:{snapshot.digest}:{bundle}:{result}", attempt=1, permitted_output_schema="final-replay-semantic-output-v1")
            raw = json.dumps({"decision":"approved","scope":"goal-and-non-goals","replay_bundle_digest":bundle,"replay_result_digest":result}, sort_keys=True, separators=(",", ":")).encode()
            return registry.import_unchanged(dispatch, raw, environment_digest=state.facts.environment.digest)
        return attest

    def _close_reopened_terminal_cone(self, runtime: object, frozen: object) -> None:
        state = runtime.state
        spine = state.facts.derived_spine
        head = state.facts.run_head
        node = frozen.nodes[-1]
        cone = CausalCone(cone_id=f"replay:{node.node_id}", node_id=node.node_id)
        spec = ProofSpec(
            proof_spec_id=f"replay-closure:{node.node_id}",
            node_id=node.node_id,
            discriminator="fresh terminal replay closure",
            expected_result="green",
            command=("fixture", "replay-closure"),
            trajectory_digest=state.trajectory_digest,
            derived_spine_digest=spine.digest,
            landmark_mapping_digest=spine.landmark_mapping_digest,
        )
        artifact = runtime._store.put_artifact(
            "final-replay-closure-proof",
            {"node_id": node.node_id, "run_head_digest": head.digest},
        )
        proof = ProofResult(
            proof_result_id=f"replay-closure-proof:{node.node_id}",
            proof_spec_id=spec.proof_spec_id,
            proof_spec_digest=spec.digest,
            node_id=node.node_id,
            proof_class="deterministic_execution_proof",
            result="green",
            artifact_digest=artifact.digest,
            run_head_digest=head.digest,
        )
        runtime.close_replay_reopened_cone(cone=cone, proof_spec=spec, proof_result=proof)
        self.assertEqual(runtime.state.facts.replay_cone_closures[-1].replay_id, runtime.state.facts.replay_reopens[-1].replay_id)
        self.assertEqual(runtime.state.facts.replay_cone_closures[-1].proof_result_ids, (proof.proof_result_id,))

    def test_final_replay_persists_reloads_and_executes_frozen_nodes_once(self) -> None:
        from scripts.graph_v5.runtime import RuntimeController
        runtime, adapter = self._runtime(); frozen = self._complete(runtime, adapter); spec = self._spec(runtime)
        adapter.reset_count = 0; adapter.executed.clear()
        resumed = RuntimeController.open(root=runtime._store.root, run_id=runtime.state.run_id)
        result = resumed.run_final_replay(adapter=adapter, final_semantic=self._semantic(resumed, spec), final_proof_spec=spec)
        self.assertEqual(adapter.reset_count, 1)
        self.assertEqual(adapter.executed, [node.node_id for node in frozen.nodes])
        self.assertEqual(tuple(proof.node_id for proof in result.node_proofs), tuple(node.node_id for node in frozen.nodes))
        self.assertEqual(result.proven_landmark_ids, ("L1", "L2")); self.assertTrue(result.terminal_outcome_proven)
        self.assertEqual(result.state.facts.frozen_derived_spines[-1], frozen)
        self.assertEqual(frozen.run_head, runtime.state.facts.run_head)
        self.assertEqual(frozen.environment, runtime.state.facts.environment)
        self.assertEqual(frozen.fixture_digest, runtime.state.fixture_intent_digest)
        self.assertGreater(frozen.graph_revision, 0)

    def test_repeated_freeze_of_unchanged_spine_returns_existing_record(self) -> None:
        runtime, adapter = self._runtime()
        first = self._complete(runtime, adapter)
        event_count = len(runtime._store.read_events())

        repeated = runtime.freeze_derived_spine()

        self.assertEqual(repeated.digest, first.digest)
        self.assertEqual(repeated, first)
        self.assertEqual(len(runtime._store.read_events()), event_count)

    def test_final_replay_reopens_when_landmark_acceptance_is_incomplete(self) -> None:
        runtime, adapter = self._runtime(
            l1_acceptance=[
                "Discipline selection is visible.",
                "Discipline selection persisted.",
            ]
        )
        frozen = self._complete(runtime, adapter)
        adapter.reset_count = 0

        result = runtime.run_final_replay(
            adapter=adapter,
            final_semantic=self._semantic(runtime, self._spec(runtime)),
            final_proof_spec=self._spec(runtime),
        )

        self.assertEqual(result.state.mode, "running")
        self.assertEqual(result.reopened_cone.node_id, frozen.landmark_mapping[0][1][-1])
        self.assertEqual(adapter.reset_count, 1)

    def test_frozen_spine_rejects_sha_valid_projection_digest_tampering(self) -> None:
        from pydantic import ValidationError
        from scripts.graph_v5.models import FrozenDerivedSpine

        runtime, adapter = self._runtime()
        frozen = self._complete(runtime, adapter)
        payload = frozen.model_dump(mode="python")
        payload["derived_spine_digest"] = "f" * 64

        with self.assertRaisesRegex(ValidationError, "projection digest mismatch"):
            FrozenDerivedSpine.model_validate(payload)

    def test_store_retries_exact_frozen_authority_after_later_events_without_revision_recheck(self) -> None:
        from scripts.graph_v5.store import StoreError

        runtime, adapter = self._runtime()
        first = self._complete(runtime, adapter)
        current = runtime.state
        started = current.model_copy(update={"mode": "final_replay"})
        runtime._store.record_final_replay_started(
            current.facts.run_head, started
        )
        event_count = len(runtime._store.read_events())

        # Existing exact authority must be a no-op even though replay appended
        # events and its original graph revision is now stale.
        runtime._store.record_derived_spine_frozen(first)
        self.assertEqual(len(runtime._store.read_events()), event_count)
        self.assertEqual(runtime.state.facts.frozen_derived_spines, (first,))

        # Different authority remains strict: stale/new content cannot sneak
        # through the idempotence path.
        drifted = first.model_copy(update={"graph_revision": first.graph_revision + 1})
        with self.assertRaisesRegex(StoreError, "authority mismatch"):
            runtime._store.record_derived_spine_frozen(drifted)
        self.assertEqual(len(runtime._store.read_events()), event_count)

    def test_fixture_validation_happens_before_durable_replay_start_and_retry_is_safe(self) -> None:
        from scripts.graph_v5.runtime import RuntimeError as GraphRuntimeError
        from types import SimpleNamespace

        runtime, adapter = self._runtime()
        self._complete(runtime, adapter)
        spec = self._spec(runtime)
        original_snapshot = adapter.snapshot
        original_reset = adapter.reset_fixture

        foreign = FixtureSnapshot("foreign-fixture", "f" * 64, "foreign-adapter")
        adapter.snapshot = foreign
        with self.assertRaisesRegex(GraphRuntimeError, "fixture does not match sealed snapshot"):
            runtime.run_final_replay(
                adapter=adapter,
                final_semantic=self._semantic(runtime, spec),
                final_proof_spec=spec,
            )
        self.assertEqual(runtime.state.mode, "running")
        self.assertNotIn("final_replay_started", [event.kind for event in runtime._store.read_events()])
        adapter.snapshot = original_snapshot

        adapter.snapshot = SimpleNamespace(
            fixture_id=original_snapshot.fixture_id,
            snapshot_digest=original_snapshot.snapshot_digest,
            adapter_id=original_snapshot.adapter_id,
            sealed=False,
        )
        with self.assertRaisesRegex(GraphRuntimeError, "fixture does not match sealed snapshot"):
            runtime.run_final_replay(
                adapter=adapter,
                final_semantic=self._semantic(runtime, spec),
                final_proof_spec=spec,
            )
        self.assertEqual(runtime.state.mode, "running")
        self.assertNotIn("final_replay_started", [event.kind for event in runtime._store.read_events()])
        adapter.snapshot = original_snapshot

        def bad_reset(snapshot: FixtureSnapshot) -> FixtureReceipt:
            del snapshot
            return FixtureReceipt("foreign-fixture", "f" * 64, "foreign-adapter")

        adapter.reset_fixture = bad_reset
        with self.assertRaisesRegex(GraphRuntimeError, "fixture does not match sealed snapshot"):
            runtime.run_final_replay(
                adapter=adapter,
                final_semantic=self._semantic(runtime, spec),
                final_proof_spec=spec,
            )
        self.assertEqual(runtime.state.mode, "running")
        self.assertNotIn("final_replay_started", [event.kind for event in runtime._store.read_events()])

        adapter.reset_fixture = original_reset
        # A subsequent valid attempt can now pass fixture validation and enter
        # normal replay; existing success coverage verifies that full path.
        self.assertEqual(runtime.state.mode, "running")

    def test_final_replay_rejects_frozen_authority_drift_before_start_or_fixture_reset(self) -> None:
        from scripts.graph_v5.runtime import RuntimeError as GraphRuntimeError

        for field in ("run_head", "environment", "fixture_digest", "graph_revision"):
            with self.subTest(field=field):
                runtime, adapter = self._runtime()
                frozen = self._complete(runtime, adapter)
                spec = self._spec(runtime)
                current = runtime.state
                frozen_update = {
                    "run_head": current.facts.run_head.model_copy(update={"revision": "drifted-head"}),
                    "environment": current.facts.environment.model_copy(update={"runtime": "drifted-runtime"}),
                    "fixture_digest": "f" * 64,
                    "graph_revision": len(runtime._store.read_events()) + 1,
                }[field]
                drifted_frozen = frozen.model_copy(update={field: frozen_update})
                drifted = current.model_copy(
                    update={
                        "facts": current.facts.model_copy(
                            update={"frozen_derived_spines": (drifted_frozen,)}
                        )
                    }
                )
                adapter.reset_count = 0
                with patch.object(runtime._store, "read_state", return_value=drifted):
                    with self.assertRaisesRegex(GraphRuntimeError, "frozen replay authority drift"):
                        runtime.run_final_replay(
                            adapter=adapter,
                            final_semantic=self._semantic(runtime, spec),
                            final_proof_spec=spec,
                        )
                self.assertEqual(adapter.reset_count, 0)
                self.assertEqual(runtime.state.mode, "running")

    def test_final_replay_rejects_each_digest_tamper_before_fixture_reset(self) -> None:
        from scripts.graph_v5.runtime import RuntimeError as GraphRuntimeError
        for field in ("trajectory_digest", "derived_spine_digest", "landmark_mapping_digest"):
            with self.subTest(field=field):
                runtime, adapter = self._runtime(); self._complete(runtime, adapter); spec = self._spec(runtime).model_copy(update={field:"f"*64}); adapter.reset_count = 0
                with self.assertRaisesRegex(GraphRuntimeError, "ProofSpec does not bind"):
                    runtime.run_final_replay(adapter=adapter, final_semantic=self._semantic(runtime, spec), final_proof_spec=spec)
                self.assertEqual(adapter.reset_count, 0)

    def test_final_replay_rejects_same_digest_foreign_fixture_identity_before_reset(self) -> None:
        from scripts.graph_v5.runtime import RuntimeError as GraphRuntimeError

        runtime, adapter = self._runtime()
        frozen = self._complete(runtime, adapter)
        spec = self._spec(runtime)
        adapter.snapshot = FixtureSnapshot(
            "foreign-fixture",
            frozen.fixture_digest,
            "foreign-adapter",
        )
        adapter.reset_count = 0

        with self.assertRaisesRegex(GraphRuntimeError, "fixture does not match sealed snapshot"):
            runtime.run_final_replay(
                adapter=adapter,
                final_semantic=self._semantic(runtime, spec),
                final_proof_spec=spec,
            )

        self.assertEqual(adapter.reset_count, 0)
        self.assertEqual(runtime.state.mode, "running")
        self.assertNotIn(
            "final_replay_started",
            [event.kind for event in runtime._store.read_events()],
        )

    def test_adapter_runtime_error_reopens_smallest_cone_after_replay_start(self) -> None:
        runtime, adapter = self._runtime()
        frozen = self._complete(runtime, adapter)
        spec = self._spec(runtime)
        original_act = adapter.act

        def failing_act(node: object, *, run_head_digest: str) -> ActionReceipt:
            del node, run_head_digest
            raise RuntimeError("adapter execution exploded")

        adapter.act = failing_act
        result = runtime.run_final_replay(
            adapter=adapter,
            final_semantic=self._semantic(runtime, spec),
            final_proof_spec=spec,
        )

        self.assertEqual(result.state.mode, "running")
        self.assertIsNotNone(result.reopened_cone)
        self.assertEqual(result.reopened_cone.node_id, frozen.nodes[0].node_id)
        self.assertEqual(runtime.state.mode, "running")
        self.assertIn("final_replay_started", [event.kind for event in runtime._store.read_events()])
        self.assertIn("final_replay_reopened", [event.kind for event in runtime._store.read_events()])
        adapter.act = original_act

    def test_replay_artifact_persistence_error_reopens_instead_of_stranding_final_replay(self) -> None:
        runtime, adapter = self._runtime()
        frozen = self._complete(runtime, adapter)
        spec = self._spec(runtime)
        original_put_artifact = runtime._store.put_artifact
        failed_once = False

        def fail_first_replay_node_artifact(domain: str, payload: object) -> object:
            nonlocal failed_once
            if domain == "final-replay-node" and not failed_once:
                failed_once = True
                raise OSError("transient replay artifact persistence failure")
            return original_put_artifact(domain, payload)

        with patch.object(
            runtime._store,
            "put_artifact",
            side_effect=fail_first_replay_node_artifact,
        ):
            result = runtime.run_final_replay(
                adapter=adapter,
                final_semantic=self._semantic(runtime, spec),
                final_proof_spec=spec,
            )

        self.assertTrue(failed_once)
        self.assertEqual(result.state.mode, "running")
        self.assertEqual(result.reopened_cone.node_id, frozen.nodes[0].node_id)
        self.assertEqual(runtime.state.mode, "running")
        self.assertIn(
            "final_replay_reopened",
            [event.kind for event in runtime._store.read_events()],
        )

    def test_store_rejects_direct_final_replay_success_without_replay_proof_authority(self) -> None:
        from scripts.graph_v5.store import StoreError

        runtime, adapter = self._runtime()
        frozen = self._complete(runtime, adapter)
        current = runtime.state
        started = current.model_copy(update={"mode": "final_replay"})
        runtime._store.record_final_replay_started(current.facts.run_head, started)
        started = runtime.state
        node_id = frozen.nodes[-1].node_id
        cone = CausalCone(cone_id=f"replay:{node_id}", node_id=node_id)
        facts = runtime._bind_canonical_cone_identity(
            started,
            started.facts,
            node_id,
            cone.cone_id,
        )
        forged = IterationFact(
            fact_id="forged-final-replay-success",
            fact_class="terminal",
            node_id=node_id,
            run_head_digest=started.facts.run_head.digest,
            subject_id="forged-no-replay-proof",
            cone_id=cone.cone_id,
            cone_digest=cone.digest,
        )
        facts = runtime._append_iteration_fact(started, facts, forged)
        successor = started.model_copy(update={"facts": facts, "mode": "succeeded"})

        with self.assertRaisesRegex(StoreError, "final replay success"):
            runtime._store.record_final_replay_succeeded(
                forged,
                successor,
                semantic_output=None,
            )

    def test_replay_bundle_persistence_error_reopens_terminal_cone(self) -> None:
        runtime, adapter = self._runtime()
        frozen = self._complete(runtime, adapter)
        spec = self._spec(runtime)
        original_put_artifact = runtime._store.put_artifact
        failed_once = False

        def fail_first_replay_bundle(domain: str, payload: object) -> object:
            nonlocal failed_once
            if domain == "final-replay-bundle" and not failed_once:
                failed_once = True
                raise OSError("transient replay bundle persistence failure")
            return original_put_artifact(domain, payload)

        with patch.object(
            runtime._store,
            "put_artifact",
            side_effect=fail_first_replay_bundle,
        ):
            result = runtime.run_final_replay(
                adapter=adapter,
                final_semantic=self._semantic(runtime, spec),
                final_proof_spec=spec,
            )

        self.assertTrue(failed_once)
        self.assertEqual(result.state.mode, "running")
        self.assertEqual(result.reopened_cone.node_id, frozen.nodes[-1].node_id)

    def test_final_success_persistence_error_reopens_terminal_cone(self) -> None:
        runtime, adapter = self._runtime()
        frozen = self._complete(runtime, adapter)
        spec = self._spec(runtime)
        original_record_success = runtime._store.record_final_replay_succeeded
        failed_once = False

        def fail_first_success(*args: object, **kwargs: object) -> None:
            nonlocal failed_once
            if not failed_once:
                failed_once = True
                raise OSError("transient final success persistence failure")
            original_record_success(*args, **kwargs)

        with patch.object(
            runtime._store,
            "record_final_replay_succeeded",
            side_effect=fail_first_success,
        ):
            result = runtime.run_final_replay(
                adapter=adapter,
                final_semantic=self._semantic(runtime, spec),
                final_proof_spec=spec,
            )

        self.assertTrue(failed_once)
        self.assertEqual(result.state.mode, "running")
        self.assertEqual(result.reopened_cone.node_id, frozen.nodes[-1].node_id)

    def test_semantic_callback_failure_reopens_and_allows_refreeze_retry(self) -> None:
        from scripts.graph_v5.runtime import RuntimeError as GraphRuntimeError

        runtime, adapter = self._runtime()
        first_frozen = self._complete(runtime, adapter)
        first_spec = self._spec(runtime)

        def failing_semantic(snapshot: object, proofs: object, bundle: str, result: str) -> object:
            del snapshot, proofs, bundle, result
            raise RuntimeError("semantic callback exploded")

        failed = runtime.run_final_replay(
            adapter=adapter,
            final_semantic=failing_semantic,
            final_proof_spec=first_spec,
        )
        self.assertEqual(failed.state.mode, "running")
        self.assertEqual(failed.reopened_cone.node_id, first_frozen.nodes[-1].node_id)
        self.assertEqual(runtime.state.facts.frozen_derived_spines, (first_frozen,))

        with self.assertRaisesRegex(GraphRuntimeError, "open replay reopen"):
            runtime.freeze_derived_spine()

        self._close_reopened_terminal_cone(runtime, first_frozen)
        extension = runtime.run_bounded_slice(adapter=adapter, deriver=_Deriver())
        self.assertEqual(extension.outcome, "node_changed")
        second_frozen = runtime.freeze_derived_spine()
        self.assertNotEqual(second_frozen.digest, first_frozen.digest)
        self.assertEqual(runtime.state.facts.frozen_derived_spines[0], first_frozen)

        spec = self._spec(runtime)
        retried = runtime.run_final_replay(
            adapter=adapter,
            final_semantic=self._semantic(runtime, spec),
            final_proof_spec=spec,
        )
        self.assertEqual(retried.state.mode, "succeeded")
        self.assertEqual(retried.state.facts.frozen_derived_spines[0], first_frozen)
        self.assertEqual(retried.state.facts.frozen_derived_spines[-1], second_frozen)

    def test_regression_repairs_smallest_cone_then_freezes_distinct_spine_and_replays(self) -> None:
        from scripts.graph_v5.runtime import RuntimeError as GraphRuntimeError

        runtime, adapter = self._runtime()
        first_frozen = self._complete(runtime, adapter)
        first_spec = self._spec(runtime)

        # Regression reopens only terminal node's smallest replay cone.
        adapter.fail = first_frozen.nodes[-1].node_id
        regression = runtime.run_final_replay(
            adapter=adapter,
            final_semantic=self._semantic(runtime, first_spec),
            final_proof_spec=first_spec,
        )
        self.assertEqual(regression.reopened_cone.node_id, first_frozen.nodes[-1].node_id)
        self.assertEqual(runtime.state.mode, "running")

        with self.assertRaisesRegex(GraphRuntimeError, "replay repair requires exact closure"):
            runtime.run_bounded_slice(adapter=adapter, deriver=_Deriver())
        with self.assertRaisesRegex(GraphRuntimeError, "open replay reopen"):
            runtime.freeze_derived_spine()

        # Close smallest reopened cone with fresh current-head proof before
        # appending one evidence-supported repair extension.
        self._close_reopened_terminal_cone(runtime, first_frozen)
        self.assertEqual(runtime.state.mode, "running")
        self.assertEqual(runtime.state.facts.frozen_derived_spines[0], first_frozen)

        # Clear defect, append one evidence-supported repair extension, then
        # prove that old freeze bytes remain unchanged.
        adapter.fail = None
        extension = runtime.run_bounded_slice(adapter=adapter, deriver=_Deriver())
        self.assertEqual(extension.outcome, "node_changed")
        extended_spine = runtime.state.facts.derived_spine
        self.assertIsNotNone(extended_spine)
        self.assertEqual(extended_spine.nodes[:-1], first_frozen.nodes)
        extension_node = extended_spine.nodes[-1]
        second_frozen = runtime.freeze_derived_spine()
        self.assertNotEqual(second_frozen.digest, first_frozen.digest)
        self.assertEqual(runtime.state.facts.frozen_derived_spines[0], first_frozen)
        self.assertEqual(runtime.state.facts.frozen_derived_spines[-1], second_frozen)

        # Restart must reconstruct extended spine and both immutable freezes
        # from ledger/artifacts before replay starts.
        from scripts.graph_v5.runtime import RuntimeController
        resumed = RuntimeController.open(root=runtime._store.root, run_id=runtime.state.run_id)
        self.assertEqual(resumed.state.facts.derived_spine, extended_spine)
        self.assertEqual(resumed.state.facts.frozen_derived_spines, (first_frozen, second_frozen))

        # Latest freeze is complete authority; replay succeeds only after all
        # current node evidence is present.
        spec = self._spec(resumed)
        result = resumed.run_final_replay(
            adapter=adapter,
            final_semantic=self._semantic(resumed, spec),
            final_proof_spec=spec,
        )
        self.assertEqual(result.state.mode, "succeeded")
        self.assertEqual(result.proven_landmark_ids, ("L1", "L2"))
        self.assertTrue(result.terminal_outcome_proven)


class RealEnvironmentReplayTests(unittest.TestCase):
    """V5.2 replay trusts admitted environment bytes, never live bridge drift."""

    def _admitted_state(self) -> tuple[object, object, object]:
        from scripts.graph_v5.adapters.manifest import AdapterManifest
        from scripts.graph_v5.canonical import digest_for
        from scripts.graph_v5.environment import EnvironmentSnapshot
        from scripts.graph_v5.models import (
            EgressGateReceipt,
            V52RunState,
            V52TrajectoryBrief,
            V52TrajectoryConfirmation,
        )
        from tests.unit.test_adapter_manifest import manifest_payload

        manifest = AdapterManifest.model_validate(manifest_payload())
        brief = V52TrajectoryBrief(
            schema_version="graph-v5.trajectory-brief.v2",
            run_id="run-real-replay",
            brief_id="brief-real-replay",
            created_at="2026-09-12T08:00:00Z",
            goal="Bind final replay to admitted real environment.",
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
            confirmation_evidence_ref="conversation:real-replay-test",
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
        return state, manifest, snapshot

    @staticmethod
    def _sealed_action_authority(
        state: object,
        manifest: object,
        *,
        run_head_digest: str,
        node_id: str,
    ) -> tuple[object, object]:
        from scripts.graph_v5.models import (
            BaselineNodeProposal,
            DerivedBehavioralNode,
            NodeBudgetProposal,
            NodeProposal,
        )

        proposal = NodeProposal(
            node_id=node_id,
            source_anchor_id="START",
            target_landmark_id="L1",
            action_kind="act",
            action_or_probe="Submit isolated data",
            expected_before=("Form ready",),
            expected_after=("Data recorded",),
            derivation_reason="Admitted service bridge exposes one typed action.",
            authority_refs=("trajectory:start_state", "trajectory:landmarks:L1"),
            execution_scope="service",
            side_effect="bridge:act",
            target_systems=("service:isolated",),
        )
        node = DerivedBehavioralNode.seal(
            proposal,
            entry_observation_refs=("evidence:before",),
            run_id=state.run_id,
            trajectory_digest=state.trajectory.digest,
            run_head_digest=run_head_digest,
            execution_envelope_digest=state.trajectory.execution_envelope.digest,
        )
        baseline_proposal = BaselineNodeProposal(
            proposal=proposal,
            entry_observation_refs=("evidence:before",),
            budget=NodeBudgetProposal(
                max_user_actions=1,
                max_provider_requests=1,
                max_cost_micros=1,
                max_requests=1, max_bytes=1_024, max_wall_seconds=1
            ),
        )
        return node, baseline_proposal

    @staticmethod
    def _egress_receipt(state: object, manifest: object) -> object:
        from scripts.graph_v5.canonical import digest_for
        from scripts.graph_v5.models import EgressGateReceipt, V52RunState
        from scripts.graph_v5.adapters.manifest import AdapterManifest

        assert isinstance(state, V52RunState)
        assert isinstance(manifest, AdapterManifest)
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

    def _admit(
        self,
        *,
        root: Path,
        state: object,
        manifest: object,
        snapshot: object,
        node_id: str,
    ) -> tuple[object, object, object]:
        from scripts.graph_v5.models import (
            RealSystemRunHead,
            V52RunState,
            derive_persisted_external_operation_intent,
        )
        from scripts.graph_v5.runtime import RealRuntimeController

        assert isinstance(state, V52RunState)
        egress = self._egress_receipt(state, manifest)
        head = RealSystemRunHead(
            run_id=state.run_id,
            manifest_digest=manifest.digest,
            environment_snapshot_digest=snapshot.digest,
        )
        node, baseline_proposal = self._sealed_action_authority(
            state, manifest, run_head_digest=head.digest, node_id=node_id
        )
        controller = RealRuntimeController._start_admitted(
            root=root,
            initial_state=state,
            manifest=manifest,
            baseline_nodes=(node,),
            baseline_proposals=(baseline_proposal,),
            provider_authority={
                "schema_version": "graph-v5.admitted-provider-authority.v1",
                "adapter_id": manifest.adapter_id,
                "provider_id": "service-host-provider.v1",
                "source_identity_digest": state.trajectory.execution_envelope.target_identity_digest,
            },
            egress_receipt=egress,
        )
        authority = controller._store.next_executable_authority()
        assert authority is not None
        return controller, node, derive_persisted_external_operation_intent(
            controller.state, authority
        )

    def test_final_replay_pauses_for_environment_snapshot_drift(self) -> None:
        """Replacing live target identity must pause before any replay action."""

        from scripts.graph_v5.adapters.service_journey import ServiceJourneyAdapter
        from scripts.graph_v5.runtime import RealRuntimeController, RuntimeController

        state, manifest, snapshot = self._admitted_state()

        class _DriftedBridge:
            def environment_snapshot(self) -> object:
                return snapshot.model_copy(
                    update={"target_identity_digest": "f" * 64}
                )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            controller, _node, _intent = self._admit(
                root=root,
                state=state,
                manifest=manifest,
                snapshot=snapshot,
                node_id="environment-drift",
            )
            resumed = RuntimeController.open(root=root, run_id=state.run_id)
            adapter = resumed._construct_adapter_for_test(
                service_bridge=_DriftedBridge()
            )
            result = resumed._final_replay_for_test(adapter)

        self.assertEqual(result.state.mode, "paused")
        self.assertEqual(result.stop_reason, "environment_snapshot_drift")

    def test_final_replay_pauses_for_every_live_snapshot_field_drift(self) -> None:
        """Manifest, receipt, or policy drift must become one durable pause."""

        state, manifest, snapshot = self._admitted_state()
        drift_cases = (
            {"adapter_manifest_digest": "f" * 64},
            {"lease_receipt_digests": ("f" * 64,)},
            {"egress_receipt_digest": "f" * 64},
            {"evidence_policy_digest": "f" * 64},
        )

        for changes in drift_cases:
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as temporary:
                controller, _node, _intent = self._admit(
                    root=Path(temporary) / "store",
                    state=state,
                    manifest=manifest,
                    snapshot=snapshot,
                    node_id=f"snapshot-drift-{next(iter(changes))}",
                )

                class _DriftedBridge:
                    def environment_snapshot(self) -> object:
                        return snapshot.model_copy(update=changes)

                adapter = controller._construct_adapter_for_test(
                    service_bridge=_DriftedBridge()
                )
                result = controller._final_replay_for_test(adapter)

                self.assertEqual(result.state.mode, "paused")
                self.assertEqual(result.stop_reason, "environment_snapshot_drift")

    def test_real_runtime_rejects_structural_adapter_not_from_registry(self) -> None:
        """Replacing fixed registry construction with duck typing must fail here."""

        from scripts.graph_v5.runtime import (
            RealRuntimeController,
            RuntimeError as GraphRuntimeError,
        )

        state, manifest, snapshot = self._admitted_state()

        class _ForgedAdapter:
            adapter_id = "service-journey.v1"
            manifest_digest = manifest.digest

            def environment_snapshot(self) -> object:
                return snapshot

            def observe_readonly(self, node: object) -> object:
                raise AssertionError("forged adapter must never observe")

            def act(self, node: object, *, operation_intent: object) -> object:
                raise AssertionError("forged adapter must never act")

            def teardown(self) -> object:
                raise AssertionError("forged adapter must never teardown")

        with tempfile.TemporaryDirectory() as temporary:
            controller, _node, _intent = self._admit(
                root=Path(temporary) / "store",
                state=state,
                manifest=manifest,
                snapshot=snapshot,
                node_id="forged-adapter",
            )

            with self.assertRaisesRegex(
                GraphRuntimeError, "persisted registered authority"
            ):
                controller._final_replay_for_test(_ForgedAdapter())

    def test_real_runtime_persists_intent_before_registered_bridge_dispatch(self) -> None:
        """Moving intent persistence after dispatch must make bridge observation fail."""

        from scripts.graph_v5.models import ExternalOperationReceipt
        from scripts.graph_v5.store import RealSystemRunStore

        state, manifest, snapshot = self._admitted_state()

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            controller, node, intent = self._admit(
                root=root,
                state=state,
                manifest=manifest,
                snapshot=snapshot,
                node_id="real-node-1",
            )

            class _PersistedIntentBridge:
                intent_was_persisted = False

                def environment_snapshot(self) -> object:
                    return snapshot

                def act(self, sealed: object, operation_intent: object) -> object:
                    persisted = RealSystemRunStore(root, state.run_id).read_state()
                    self.intent_was_persisted = operation_intent in persisted.facts.external_operation_intents
                    self.assert_true(self.intent_was_persisted)
                    return ExternalOperationReceipt(
                        receipt_id="receipt:real-node-1",
                        operation_id=intent.operation_id,
                        run_id=intent.run_id,
                        manifest_digest=intent.manifest_digest,
                        run_head_digest=intent.run_head_digest,
                        idempotency_key=intent.idempotency_key,
                        status="succeeded",
                        evidence_refs=("evidence:redacted-receipt",),
                    )

                @staticmethod
                def assert_true(value: bool) -> None:
                    if not value:
                        raise AssertionError("external intent was not durable before bridge dispatch")

            bridge = _PersistedIntentBridge()
            adapter = controller._construct_adapter_for_test(
                service_bridge=bridge
            )
            result = controller._run_bounded_slice_for_test(
                adapter=adapter,
                node=node,
                operation_intent=intent,
            )

        self.assertTrue(bridge.intent_was_persisted)
        self.assertEqual(result.receipt.operation_id, intent.operation_id)
        self.assertEqual(len(result.state.facts.external_operation_intents), 1)
        self.assertEqual(len(result.state.facts.external_operation_receipts), 1)

    def test_real_runtime_blocks_snapshot_drift_between_precheck_and_dispatch(self) -> None:
        """Removing adapter-local snapshot binding must expose one forbidden action."""

        from scripts.graph_v5.adapters.protocol import AdapterError
        from scripts.graph_v5.models import ExternalOperationIntent, ExternalOperationReceipt

        state, manifest, snapshot = self._admitted_state()

        class _DriftAfterPrecheckBridge:
            snapshot_reads = 0
            action_dispatched = False

            def environment_snapshot(self) -> object:
                self.snapshot_reads += 1
                if self.snapshot_reads == 1:
                    return snapshot
                return snapshot.model_copy(
                    update={"target_identity_digest": "f" * 64}
                )

            def act(self, sealed: object, operation_intent: object) -> object:
                self.action_dispatched = True
                assert isinstance(operation_intent, ExternalOperationIntent)
                return ExternalOperationReceipt(
                    receipt_id="receipt:drifted-node",
                    operation_id=operation_intent.operation_id,
                    run_id=operation_intent.run_id,
                    manifest_digest=operation_intent.manifest_digest,
                    run_head_digest=operation_intent.run_head_digest,
                    idempotency_key=operation_intent.idempotency_key,
                    status="succeeded",
                    evidence_refs=("evidence:redacted-receipt",),
                )

        with tempfile.TemporaryDirectory() as temporary:
            controller, node, intent = self._admit(
                root=Path(temporary) / "store",
                state=state,
                manifest=manifest,
                snapshot=snapshot,
                node_id="drifted-node",
            )
            bridge = _DriftAfterPrecheckBridge()
            adapter = controller._construct_adapter_for_test(
                service_bridge=bridge
            )

            with self.assertRaisesRegex(AdapterError, "sealed EnvironmentSnapshot"):
                controller._run_bounded_slice_for_test(
                    adapter=adapter,
                    node=node,
                    operation_intent=intent,
                )

            self.assertFalse(bridge.action_dispatched)
            self.assertEqual(controller.state.mode, "paused")

    def test_real_runtime_pauses_after_exact_failed_receipt(self) -> None:
        """Treating a failed receipt as green must leave this run incorrectly running."""

        from scripts.graph_v5.models import ExternalOperationIntent, ExternalOperationReceipt

        state, manifest, snapshot = self._admitted_state()

        class _FailedActionBridge:
            def environment_snapshot(self) -> object:
                return snapshot

            def act(self, sealed: object, operation_intent: object) -> object:
                assert isinstance(operation_intent, ExternalOperationIntent)
                return ExternalOperationReceipt(
                    receipt_id="receipt:failed-node",
                    operation_id=operation_intent.operation_id,
                    run_id=operation_intent.run_id,
                    manifest_digest=operation_intent.manifest_digest,
                    run_head_digest=operation_intent.run_head_digest,
                    idempotency_key=operation_intent.idempotency_key,
                    status="failed",
                    evidence_refs=("evidence:redacted-failure",),
                )

        with tempfile.TemporaryDirectory() as temporary:
            controller, node, intent = self._admit(
                root=Path(temporary) / "store",
                state=state,
                manifest=manifest,
                snapshot=snapshot,
                node_id="failed-node",
            )
            adapter = controller._construct_adapter_for_test(
                service_bridge=_FailedActionBridge()
            )

            result = controller._run_bounded_slice_for_test(
                adapter=adapter,
                node=node,
                operation_intent=intent,
            )

            self.assertEqual(result.receipt.status, "failed")
            self.assertEqual(result.state.mode, "paused")

    def test_real_runtime_pauses_when_receipt_persistence_rejects_collision(self) -> None:
        """A durable intent cannot remain running after receipt-chain rejection."""

        from scripts.graph_v5.models import (
            BaselineNodeProposal,
            DerivedBehavioralNode,
            ExternalOperationIntent,
            ExternalOperationReceipt,
            NodeBudgetProposal,
            NodeProposal,
            PersistedNodeExecutionAuthority,
            derive_persisted_external_operation_intent,
        )
        from scripts.graph_v5.store import StoreError

        state, manifest, snapshot = self._admitted_state()

        class _CollidingReceiptBridge:
            def environment_snapshot(self) -> object:
                return snapshot

            def act(self, sealed: object, operation_intent: object) -> object:
                assert isinstance(operation_intent, ExternalOperationIntent)
                return ExternalOperationReceipt(
                    receipt_id="receipt:shared",
                    operation_id=operation_intent.operation_id,
                    run_id=operation_intent.run_id,
                    manifest_digest=operation_intent.manifest_digest,
                    run_head_digest=operation_intent.run_head_digest,
                    idempotency_key=operation_intent.idempotency_key,
                    status="succeeded",
                    evidence_refs=("evidence:redacted-receipt",),
                )

        with tempfile.TemporaryDirectory() as temporary:
            controller, node, first_intent = self._admit(
                root=Path(temporary) / "store",
                state=state,
                manifest=manifest,
                snapshot=snapshot,
                node_id="receipt-collision",
            )
            adapter = controller._construct_adapter_for_test(
                service_bridge=_CollidingReceiptBridge()
            )
            controller._run_bounded_slice_for_test(
                adapter=adapter,
                node=node,
                operation_intent=first_intent,
            )
            second_proposal = NodeProposal(
                node_id="receipt-collision-exploration",
                source_anchor_id=node.source_anchor_id,
                target_landmark_id=node.target_landmark_id,
                action_kind=node.action_kind,
                action_or_probe=node.action_or_probe,
                expected_before=node.expected_before,
                expected_after=node.expected_after,
                derivation_reason=node.derivation_reason,
                authority_refs=node.authority_refs,
                execution_scope=node.execution_scope,
                side_effect=node.side_effect,
                target_systems=(manifest.target.host,),
            )
            second_node = DerivedBehavioralNode.seal(
                second_proposal,
                entry_observation_refs=node.entry_observation_refs,
                run_id=state.run_id,
                trajectory_digest=state.trajectory.digest,
                run_head_digest=node.run_head_digest,
                execution_envelope_digest=state.trajectory.execution_envelope.digest,
            )
            second_delta = controller.register_evidence_led_exploration(
                node=second_node,
                parent_node_id=node.node_id,
                evidence_refs=node.entry_observation_refs,
                proposal=BaselineNodeProposal(
                    proposal=second_proposal,
                    entry_observation_refs=second_node.entry_observation_refs,
                    budget=NodeBudgetProposal(
                        max_user_actions=1,
                        max_provider_requests=1,
                        max_cost_micros=1,
                        max_requests=1, max_bytes=1_024, max_wall_seconds=1
                    ),
                ),
            )
            second_intent = derive_persisted_external_operation_intent(
                controller.state,
                PersistedNodeExecutionAuthority.exploration(second_delta),
            )

            with self.assertRaisesRegex(StoreError, "receipt identity already exists"):
                controller._run_bounded_slice_for_test(
                    adapter=adapter,
                    node=second_node,
                    operation_intent=second_intent,
                )

            self.assertEqual(controller.state.mode, "paused")
            self.assertEqual(len(controller.state.facts.external_operation_intents), 2)
            self.assertEqual(len(controller.state.facts.external_operation_receipts), 1)


class RealAuthorityClosureTests(unittest.TestCase):
    """Repair 6B uses persisted baseline and exploration authority end-to-end."""

    @staticmethod
    def _reseal_node(node: object, **changes: object) -> object:
        from scripts.graph_v5.canonical import digest_for
        from scripts.graph_v5.models import DerivedBehavioralNode

        assert isinstance(node, DerivedBehavioralNode)
        payload = node.model_dump(exclude={"sealed_intent_digest"}, mode="python")
        payload.update(changes)
        payload["sealed_intent_digest"] = digest_for(
            "derived-behavioral-node-intent", payload
        )
        return DerivedBehavioralNode.model_validate(payload)

    @staticmethod
    def _exploration_proposal(node: object) -> object:
        from scripts.graph_v5.models import BaselineNodeProposal, DerivedBehavioralNode, NodeBudgetProposal, NodeProposal

        assert isinstance(node, DerivedBehavioralNode)
        return BaselineNodeProposal(
            proposal=NodeProposal(
                node_id=node.node_id,
                source_anchor_id=node.source_anchor_id,
                target_landmark_id=node.target_landmark_id,
                action_kind=node.action_kind,
                action_or_probe=node.action_or_probe,
                expected_before=node.expected_before,
                expected_after=node.expected_after,
                derivation_reason=node.derivation_reason,
                authority_refs=node.authority_refs,
                execution_scope=node.execution_scope,
                side_effect=node.side_effect,
                target_systems=node.target_systems,
            ),
            entry_observation_refs=node.entry_observation_refs,
            budget=NodeBudgetProposal(
                max_user_actions=1,
                max_provider_requests=1,
                max_cost_micros=1,
                max_requests=1, max_bytes=1_024, max_wall_seconds=1
            ),
        )

    def _admission(self) -> tuple[object, object, object, object, object, object]:
        from scripts.graph_v5.adapters.manifest import AdapterManifest
        from scripts.graph_v5.canonical import digest_for
        from scripts.graph_v5.environment import EnvironmentSnapshot
        from scripts.graph_v5.models import (
            DerivedBehavioralNode,
            EgressGateReceipt,
            NodeProposal,
            RealSystemRunHead,
            V52RunState,
            V52TrajectoryBrief,
            V52TrajectoryConfirmation,
        )
        from tests.unit.test_adapter_manifest import manifest_payload

        manifest = AdapterManifest.model_validate(manifest_payload())
        brief = V52TrajectoryBrief(
            schema_version="graph-v5.trajectory-brief.v2",
            run_id="run-repair-6b",
            brief_id="brief-repair-6b",
            created_at="2026-09-12T09:00:00Z",
            goal="Seal runtime dispatch to persisted authority.",
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
            confirmed_at="2026-09-12T09:01:00Z",
            confirmation_evidence_ref="conversation:repair-6b",
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
            target_identity_digest=brief.execution_envelope.target_identity_digest,
            allowed_hosts=manifest.egress.hosts,
            allowed_protocols=("https",),
            issued_receipt_digest=digest_for(
                "egress-enforcement-receipt", manifest.egress.enforcement_receipt
            ),
        )
        snapshot = EnvironmentSnapshot.from_admitted_authority(
            manifest=manifest,
            target_identity_digest=brief.execution_envelope.target_identity_digest,
            supervisor_receipts=(),
            egress_receipt=egress,
        )
        head = RealSystemRunHead(
            run_id=state.run_id,
            manifest_digest=manifest.digest,
            environment_snapshot_digest=snapshot.digest,
        )
        node = DerivedBehavioralNode.seal(
            NodeProposal(
                node_id="baseline-node",
                source_anchor_id="START",
                target_landmark_id="L1",
                action_kind="act",
                action_or_probe="Submit isolated data",
                expected_before=("Form ready",),
                expected_after=("Data recorded",),
                derivation_reason="Confirmed service trajectory.",
                authority_refs=("trajectory:start_state", "trajectory:landmarks:L1"),
                execution_scope="service",
                side_effect="bridge:act",
                target_systems=(manifest.target.host,),
            ),
            entry_observation_refs=("evidence:before",),
            run_id=state.run_id,
            trajectory_digest=state.trajectory.digest,
            run_head_digest=head.digest,
            execution_envelope_digest=state.trajectory.execution_envelope.digest,
        )
        return state, manifest, egress, snapshot, head, node

    def _controller(self) -> tuple[object, object, object, object]:
        from scripts.graph_v5.runtime import RealRuntimeController
        from scripts.graph_v5.store import RealSystemRunStore

        state, manifest, egress, snapshot, head, node = self._admission()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name) / "store"
        store = RealSystemRunStore.open(root, state.run_id)
        store.initialize(
            state,
            manifest=manifest,
            baseline_nodes=(node,),
            baseline_proposals=(self._exploration_proposal(node),),
            provider_authority={
                "schema_version": "graph-v5.admitted-provider-authority.v1",
                "adapter_id": manifest.adapter_id,
                "provider_id": "service-host-provider.v1",
                "source_identity_digest": state.trajectory.execution_envelope.target_identity_digest,
            },
            egress_receipt=egress,
        )
        return RealRuntimeController.open(root=root, run_id=state.run_id), manifest, snapshot, node

    def test_unregistered_node_never_reads_snapshot_or_dispatches_bridge(self) -> None:
        from scripts.graph_v5.models import BudgetReservation, ExternalOperationIntent
        from scripts.graph_v5.runtime import RuntimeError as GraphRuntimeError
        from scripts.graph_v5.store import StoreError

        controller, manifest, snapshot, baseline = self._controller()
        substituted = self._reseal_node(
            baseline, action_or_probe="Different caller action"
        )
        intent = ExternalOperationIntent(
            operation_id="op-unregistered",
            run_id=controller.state.run_id,
            node_id=substituted.node_id,
            manifest_digest=manifest.digest,
            run_head_digest=substituted.run_head_digest,
            idempotency_key="bridge:unregistered",
            effect="bridge:act",
            reserved_budget=BudgetReservation(
                reservation_id="reservation-unregistered",
                run_id=controller.state.run_id,
                operation_id="op-unregistered",
                user_actions=1,
                provider_requests=0,
                cost_micros=0,
                requests=1,
                processes=0,
                persistence_writes=1,
                tokens=0,
                duration_ms=1,
            ),
        )

        class _CountingBridge:
            snapshot_reads = 0
            action_calls = 0

            def environment_snapshot(self) -> object:
                self.snapshot_reads += 1
                return snapshot

            def act(self, node: object, operation_intent: object) -> object:
                self.action_calls += 1
                raise AssertionError("unregistered node must never dispatch")

        bridge = _CountingBridge()
        adapter = controller._construct_adapter_for_test(service_bridge=bridge)

        with self.assertRaisesRegex(StoreError, "registered exploration"):
            controller._run_bounded_slice_for_test(
                adapter=adapter,
                node=substituted,
                operation_intent=intent,
            )
        self.assertEqual(bridge.snapshot_reads, 0)
        self.assertEqual(bridge.action_calls, 0)

    def test_status_recommends_baseline_and_projects_registered_exploration(self) -> None:
        controller, _manifest, _snapshot, baseline = self._controller()
        delta = self._reseal_node(baseline, node_id="exploration-node")

        recorded = controller.register_evidence_led_exploration(
            node=delta,
            parent_node_id=baseline.node_id,
            evidence_refs=baseline.entry_observation_refs,
            proposal=self._exploration_proposal(delta),
        )
        status = controller.status_projection()

        self.assertEqual(status.recommended_baseline_node_id, baseline.node_id)
        self.assertEqual(status.active_explorations[0].node_id, recorded.node.node_id)
        self.assertEqual(status.active_explorations[0].parent_node_id, baseline.node_id)
        self.assertEqual(
            status.active_explorations[0].reason,
            recorded.node.derivation_reason,
        )
        self.assertFalse(hasattr(status.active_explorations[0], "evidence_refs"))

    def test_evidence_led_exploration_executes_and_replays_without_user_decision(self) -> None:
        from scripts.graph_v5.models import (
            ExternalOperationIntent,
            ExternalOperationReceipt,
            PersistedNodeExecutionAuthority,
            derive_persisted_external_operation_intent,
        )

        controller, manifest, snapshot, baseline = self._controller()
        exploration_node = self._reseal_node(baseline, node_id="exploration-executed")
        delta = controller.register_evidence_led_exploration(
            node=exploration_node,
            parent_node_id=baseline.node_id,
            evidence_refs=baseline.entry_observation_refs,
            proposal=self._exploration_proposal(exploration_node),
        )
        intent = derive_persisted_external_operation_intent(
            controller.state,
            PersistedNodeExecutionAuthority.exploration(delta),
        )

        class _Bridge:
            def environment_snapshot(self) -> object:
                return snapshot

            def act(self, node: object, operation_intent: object) -> object:
                assert isinstance(operation_intent, ExternalOperationIntent)
                return ExternalOperationReceipt(
                    receipt_id="receipt:exploration",
                    operation_id=operation_intent.operation_id,
                    run_id=operation_intent.run_id,
                    manifest_digest=operation_intent.manifest_digest,
                    run_head_digest=operation_intent.run_head_digest,
                    idempotency_key=operation_intent.idempotency_key,
                    status="succeeded",
                    evidence_refs=("evidence:exploration",),
                )

        adapter = controller._construct_adapter_for_test(service_bridge=_Bridge())
        result = controller._run_bounded_slice_for_test(
            adapter=adapter,
            node=delta.node,
            operation_intent=intent,
        )
        replay = controller._final_replay_for_test(adapter)

        self.assertEqual(result.receipt.operation_id, intent.operation_id)
        self.assertEqual(replay.stop_reason, None)
        self.assertEqual(replay.snapshot.exploration_delta_digests, (delta.digest,))
        self.assertEqual(replay.snapshot.executed_node_digests, (delta.node.digest,))
        self.assertEqual(controller.state.confirmation.confirmed_by, "user:aleda")
        self.assertEqual((), controller.status_projection().active_explorations)

    def test_final_replay_rejects_substituted_baseline_before_live_observation(self) -> None:
        from scripts.graph_v5.proof import ProofLadderError, RealFinalReplaySnapshot

        controller, _manifest, snapshot, _baseline = self._controller()
        state = controller.state
        baseline = state.facts.baseline_spine
        assert baseline is not None
        forged = baseline.model_copy(update={"node_digests": ("f" * 64,)})
        forged_state = state.model_copy(
            update={"facts": state.facts.model_copy(update={"baseline_spine": forged})}
        )

        with self.assertRaisesRegex(ProofLadderError, "baseline spine"):
            RealFinalReplaySnapshot.from_state(
                forged_state, environment_snapshot=snapshot
            )

    def test_final_replay_rejects_provider_source_substitution(self) -> None:
        """Replay must retain provider source identity admitted with fixture bundle."""

        from scripts.graph_v5.proof import ProofLadderError, RealFinalReplaySnapshot
        from scripts.graph_v5.runtime import RealRuntimeController
        from tests.unit.test_real_admission import valid_bundle, valid_manifest

        with tempfile.TemporaryDirectory() as temporary:
            runtime = RealRuntimeController.start_from_confirmed_bundle(
                root=Path(temporary) / "store",
                bundle=valid_bundle(),
                manifest=valid_manifest(),
            )
            state = runtime.state
            provider = state.facts.provider_authority
            assert provider is not None
            forged_state = state.model_copy(
                update={
                    "facts": state.facts.model_copy(
                        update={
                            "provider_authority": provider.model_copy(
                                update={"source_identity_digest": "f" * 64}
                            )
                        }
                    )
                }
            )

            with self.assertRaisesRegex(ProofLadderError, "registry authority drifted"):
                RealFinalReplaySnapshot.from_state(
                    forged_state,
                    environment_snapshot=runtime.environment_snapshot,
                    manifest=valid_manifest(),
                )

    def test_final_replay_rejects_forged_verification_completion(self) -> None:
        """Effectful node cannot be replay-complete through readonly completion bytes."""

        from scripts.graph_v5.models import Observation, RealNodeCompletion
        from scripts.graph_v5.proof import ProofLadderError, RealFinalReplaySnapshot

        controller, manifest, snapshot, baseline = self._controller()
        state = controller.state
        forged = RealNodeCompletion(
            run_id=state.run_id,
            node_id=baseline.node_id,
            run_head_digest=baseline.run_head_digest,
            kind="verification",
            evidence_refs=("evidence:forged",),
            verification_observation=Observation(
                observation_id="forged-verification-observation",
                node_id=baseline.source_anchor_id,
                kind="behavioral",
                observed_state="Forged verification result",
                evidence_refs=("evidence:forged",),
                run_head_digest=baseline.run_head_digest,
            ),
        )
        forged_state = state.model_copy(
            update={
                "facts": state.facts.model_copy(update={"node_completions": (forged,)})
            }
        )

        with self.assertRaisesRegex(ProofLadderError, "verification completion is forged"):
            RealFinalReplaySnapshot.from_state(
                forged_state, environment_snapshot=snapshot, manifest=manifest
            )

    def test_final_replay_rejects_receipted_intent_over_proposal_budget(self) -> None:
        """Receipt identity alone cannot authorize more work than node proposal bound."""

        from scripts.graph_v5.models import BudgetReservation
        from scripts.graph_v5.proof import ProofLadderError, RealFinalReplaySnapshot
        from scripts.graph_v5.runtime import RealRuntimeController
        from tests.unit.test_real_admission import valid_bundle, valid_manifest

        with tempfile.TemporaryDirectory() as temporary:
            runtime = RealRuntimeController.start_from_confirmed_bundle(
                root=Path(temporary) / "store",
                bundle=valid_bundle(),
                manifest=valid_manifest(),
            )
            runtime.run_next_persisted_slice()
            state = runtime.state
            intent = state.facts.external_operation_intents[0]
            forged_intent = intent.model_copy(
                update={
                    "reserved_budget": BudgetReservation(
                        **{
                            **intent.reserved_budget.model_dump(mode="python"),
                            "requests": 2,
                        }
                    )
                }
            )
            forged_state = state.model_copy(
                update={
                    "facts": state.facts.model_copy(
                        update={"external_operation_intents": (forged_intent,)}
                    )
                }
            )

            with self.assertRaisesRegex(ProofLadderError, "proposal budget"):
                RealFinalReplaySnapshot.from_state(
                    forged_state,
                    environment_snapshot=runtime.environment_snapshot,
                    manifest=valid_manifest(),
                )

    def test_final_replay_rejects_forged_real_system_decision_consumption(self) -> None:
        """Changing decision kind after pending issuance must invalidate replay."""

        from scripts.graph_v5.models import (
            BudgetWideningAmendment,
            CleanupAmendment,
            PendingRealSystemDecision,
            RealSystemDecision,
            RealSystemDecisionConsumption,
        )
        from scripts.graph_v5.proof import ProofLadderError, RealFinalReplaySnapshot
        from scripts.graph_v5.runtime import RealRuntimeController
        from tests.unit.test_real_admission import valid_bundle, valid_manifest

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
                decision_id="decision:budget",
                kind="budget_widening",
                run_id=state.run_id,
                run_head_digest=head.digest,
                authority_digest=baseline.digest,
                payload_digest=digest_for("real-system-decision-amendment", amendment),
                amendment=amendment,
            )
            forged_amendment = CleanupAmendment(
                kind="cleanup", runtime_note_digest="c" * 64
            )
            forged = RealSystemDecision(
                decision_id=pending.decision_id,
                pending_decision_digest=pending.digest,
                kind="cleanup",
                run_id=pending.run_id,
                run_head_digest=pending.run_head_digest,
                authority_digest=pending.authority_digest,
                payload_digest=digest_for(
                    "real-system-decision-amendment", forged_amendment
                ),
                amendment=forged_amendment,
                actor="user:aleda",
            )
            forged_state = state.model_copy(
                update={
                    "facts": state.facts.model_copy(
                        update={
                            "pending_real_system_decisions": (pending,),
                            "real_system_decision_consumptions": (
                                RealSystemDecisionConsumption(
                                    pending_decision_digest=pending.digest,
                                    decision=forged,
                                    amendment=forged_amendment,
                                ),
                            ),
                        }
                    )
                }
            )

            with self.assertRaisesRegex(ProofLadderError, "decision consumption"):
                RealFinalReplaySnapshot.from_state(
                    forged_state,
                    environment_snapshot=runtime.environment_snapshot,
                    manifest=valid_manifest(),
                )

    def test_registered_fixture_manifest_constructs_v52_wrapper(self) -> None:
        from scripts.graph_v5.adapters import construct_registered_adapter
        from scripts.graph_v5.adapters.fixture_journey import V52FixtureJourneyAdapter
        from scripts.graph_v5.adapters.user_journey import FixtureUserJourneyAdapter
        from tests.unit.test_adapter_manifest import registered_fixture_manifest

        legacy = FixtureUserJourneyAdapter.from_fixture_file(
            Path(__file__).resolve().parents[2] / "fixtures" / "user_journeys" / "trajectory-jit.v1.json",
            "trajectory-jit-healthy",
        )
        adapter = construct_registered_adapter(
            registered_fixture_manifest(), fixture_adapter=legacy
        )

        self.assertIsInstance(adapter, V52FixtureJourneyAdapter)
        self.assertEqual(adapter.environment_snapshot().target_identity_digest, legacy.fixture_snapshot().snapshot_digest)


if __name__ == "__main__": unittest.main()
