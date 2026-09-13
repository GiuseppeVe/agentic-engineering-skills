from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.graph_v5.canonical import canonical_json_bytes, digest_for
from tests.unit.test_real_admission import valid_bundle, valid_manifest


ROOT = Path(__file__).resolve().parents[2]
GRAPHCTL = ROOT / "scripts" / "graphctl.py"


def invoke_graphctl(*arguments: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(GRAPHCTL), *arguments],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def write_admission_inputs(root: Path, *, bundle: object, manifest: object) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    bundle_path = root / "confirmed-real-trajectory.json"
    manifest_path = root / "adapter-manifest.json"
    bundle_path.write_bytes(canonical_json_bytes(bundle.model_dump(mode="json")))
    manifest_path.write_bytes(canonical_json_bytes(manifest.model_dump(mode="json")))
    return bundle_path, manifest_path


class RealAuthorityCliTests(unittest.TestCase):

    def test_v52_bundle_without_manifest_is_schema_detected_before_store_creation(self) -> None:
        bundle = valid_bundle()
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            run_store_root = temporary_root / "run-store"
            bundle_path, _ = write_admission_inputs(
                temporary_root, bundle=bundle, manifest=valid_manifest()
            )

            result = invoke_graphctl(
                "start",
                "--trajectory-brief", str(bundle_path),
                "--run-store-root", str(run_store_root),
                cwd=temporary_root,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["error_code"], "input_required")
            self.assertIn("--adapter-manifest", payload["summary"])
            self.assertFalse(run_store_root.exists())

    def test_malformed_bundle_rejects_before_creating_real_run_store(self) -> None:
        manifest = valid_manifest()
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            bundle_path = temporary_root / "malformed-real-trajectory.json"
            manifest_path = temporary_root / "adapter-manifest.json"
            run_store_root = temporary_root / "run-store"
            bundle_path.write_bytes(canonical_json_bytes({}))
            manifest_path.write_bytes(canonical_json_bytes(manifest.model_dump(mode="json")))

            result = invoke_graphctl(
                "start",
                "--trajectory-brief", str(bundle_path),
                "--adapter-manifest", str(manifest_path),
                "--run-store-root", str(run_store_root),
                cwd=temporary_root,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertEqual(json.loads(result.stdout)["error_code"], "invalid_trajectory_brief")
            self.assertFalse(run_store_root.exists())

    def test_fixture_bundle_starts_runs_and_statuses_without_runtime_authority_flags(self) -> None:
        bundle = valid_bundle()
        manifest = valid_manifest()
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            run_store_root = temporary_root / "run-store"
            bundle_path, manifest_path = write_admission_inputs(
                temporary_root, bundle=bundle, manifest=manifest
            )

            started = invoke_graphctl(
                "start",
                "--trajectory-brief", str(bundle_path),
                "--adapter-manifest", str(manifest_path),
                "--run-store-root", str(run_store_root),
                cwd=temporary_root,
            )
            self.assertEqual(started.returncode, 0, msg=started.stderr)
            self.assertEqual(json.loads(started.stdout)["status"], "running")

            rejected = invoke_graphctl(
                "run",
                "--run-store-root", str(run_store_root),
                "--run-id", bundle.brief.run_id,
                "--fixture-file", "caller-controlled.json",
                "--fixture-scenario", "caller-controlled",
                cwd=temporary_root,
            )
            self.assertEqual(rejected.returncode, 0, msg=rejected.stderr)
            self.assertEqual(json.loads(rejected.stdout)["error_code"], "run_rejected")

            advanced = invoke_graphctl(
                "run",
                "--run-store-root", str(run_store_root),
                "--run-id", bundle.brief.run_id,
                cwd=temporary_root,
            )
            self.assertEqual(advanced.returncode, 0, msg=advanced.stderr)
            self.assertIn(json.loads(advanced.stdout)["status"], {"running", "verified"})

            status = invoke_graphctl(
                "status",
                "--run-store-root", str(run_store_root),
                "--run-id", bundle.brief.run_id,
                cwd=temporary_root,
            )
            self.assertEqual(status.returncode, 0, msg=status.stderr)
            self.assertEqual(json.loads(status.stdout)["status"], "running")

    def test_verification_only_bundle_completes_without_external_operation_intent(self) -> None:
        from scripts.graph_v5.models import BaselineNodeProposal, NodeProposal
        from scripts.graph_v5.store import RealSystemRunStore

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
        manifest = valid_manifest()
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            run_store_root = temporary_root / "run-store"
            bundle_path, manifest_path = write_admission_inputs(
                temporary_root, bundle=bundle, manifest=manifest
            )
            started = invoke_graphctl(
                "start",
                "--trajectory-brief", str(bundle_path),
                "--adapter-manifest", str(manifest_path),
                "--run-store-root", str(run_store_root),
                cwd=temporary_root,
            )
            self.assertEqual(started.returncode, 0, msg=started.stderr)

            advanced = invoke_graphctl(
                "run",
                "--run-store-root", str(run_store_root),
                "--run-id", bundle.brief.run_id,
                cwd=temporary_root,
            )
            self.assertEqual(advanced.returncode, 0, msg=advanced.stderr)
            state = RealSystemRunStore.open_readonly(
                run_store_root, bundle.brief.run_id
            ).read_state()
            self.assertEqual((), state.facts.external_operation_intents)
            self.assertEqual("verification", state.facts.node_completions[0].kind)

    def test_v52_decision_rejects_stale_authority_then_consumes_exact_pending_fact(self) -> None:
        from scripts.graph_v5.models import (
            BudgetWideningAmendment,
            PendingRealSystemDecision,
            RealSystemDecision,
        )
        from scripts.graph_v5.store import RealSystemRunStore

        bundle = valid_bundle()
        manifest = valid_manifest()
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            run_store_root = temporary_root / "run-store"
            bundle_path, manifest_path = write_admission_inputs(
                temporary_root, bundle=bundle, manifest=manifest
            )
            started = invoke_graphctl(
                "start",
                "--trajectory-brief", str(bundle_path),
                "--adapter-manifest", str(manifest_path),
                "--run-store-root", str(run_store_root),
                cwd=temporary_root,
            )
            self.assertEqual(started.returncode, 0, msg=started.stderr)

            store = RealSystemRunStore.open(run_store_root, bundle.brief.run_id)
            state = store.read_state()
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
                decision_id="decision:cli-budget-widening",
                kind="budget_widening",
                run_id=state.run_id,
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
            decision_path = temporary_root / "real-system-decision.json"
            decision_path.write_bytes(canonical_json_bytes(decision.model_dump(mode="json")))
            stale_path = temporary_root / "stale-real-system-decision.json"
            stale_path.write_bytes(
                canonical_json_bytes(
                    decision.model_copy(update={"pending_decision_digest": "0" * 64}).model_dump(
                        mode="json"
                    )
                )
            )

            stale = invoke_graphctl(
                "decision",
                "--run-store-root", str(run_store_root),
                "--run-id", bundle.brief.run_id,
                "--decision-file", str(stale_path),
                cwd=temporary_root,
            )
            self.assertEqual(stale.returncode, 0, msg=stale.stderr)
            self.assertEqual(json.loads(stale.stdout)["error_code"], "decision_rejected")

            applied = invoke_graphctl(
                "decision",
                "--run-store-root", str(run_store_root),
                "--run-id", bundle.brief.run_id,
                "--decision-file", str(decision_path),
                cwd=temporary_root,
            )
            self.assertEqual(applied.returncode, 0, msg=applied.stderr)
            self.assertEqual(json.loads(applied.stdout)["status"], "running")
            consumed = RealSystemRunStore.open_readonly(
                run_store_root, bundle.brief.run_id
            ).read_state().facts.real_system_decision_consumptions
            self.assertEqual(1, len(consumed))

    def test_registered_exploration_runs_without_user_decision(self) -> None:
        from scripts.graph_v5.models import (
            BaselineNodeProposal,
            DerivedBehavioralNode,
            NodeBudgetProposal,
            NodeProposal,
        )
        from scripts.graph_v5.runtime import RealRuntimeController
        from scripts.graph_v5.store import RealSystemRunStore

        bundle = valid_bundle()
        baseline_verification = NodeProposal(
            node_id="baseline-checkout",
            source_anchor_id="start",
            target_landmark_id="checkout",
            action_kind="verify_only",
            action_or_probe="Observe synthetic checkout state",
            expected_before=("Synthetic checkout form is visible",),
            expected_after=("Synthetic checkout result is visible",),
            derivation_reason="Baseline evidence establishes fixture state.",
            authority_refs=("trajectory:checkout",),
            execution_scope="fixture:checkout",
            side_effect=None,
            target_systems=("127.0.0.1",),
        )
        bundle = bundle.model_copy(
            update={
                "baseline": (
                    BaselineNodeProposal(
                        proposal=baseline_verification,
                        entry_observation_refs=("observation:fixture-start",),
                        budget=None,
                    ),
                )
            }
        )
        manifest = valid_manifest()
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            run_store_root = temporary_root / "run-store"
            bundle_path, manifest_path = write_admission_inputs(
                temporary_root, bundle=bundle, manifest=manifest
            )
            started = invoke_graphctl(
                "start",
                "--trajectory-brief", str(bundle_path),
                "--adapter-manifest", str(manifest_path),
                "--run-store-root", str(run_store_root),
                cwd=temporary_root,
            )
            self.assertEqual(started.returncode, 0, msg=started.stderr)
            baseline = invoke_graphctl(
                "run",
                "--run-store-root", str(run_store_root),
                "--run-id", bundle.brief.run_id,
                cwd=temporary_root,
            )
            self.assertEqual(baseline.returncode, 0, msg=baseline.stderr)

            runtime = RealRuntimeController.open(
                root=run_store_root, run_id=bundle.brief.run_id
            )
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
            runtime.register_evidence_led_exploration(
                node=node,
                parent_node_id="baseline-checkout",
                evidence_refs=bundle.baseline[0].entry_observation_refs,
                proposal=BaselineNodeProposal(
                    proposal=proposal,
                    entry_observation_refs=("observation:exploration",),
                    budget=NodeBudgetProposal(
                        max_user_actions=1,
                        max_provider_requests=1,
                        max_cost_micros=1,
                        max_requests=1,
                        max_bytes=1_024,
                        max_wall_seconds=10,
                    ),
                ),
            )
            self.assertEqual((), runtime.state.facts.pending_real_system_decisions)

            explored = invoke_graphctl(
                "run",
                "--run-store-root", str(run_store_root),
                "--run-id", bundle.brief.run_id,
                cwd=temporary_root,
            )
            self.assertEqual(explored.returncode, 0, msg=explored.stderr)
            self.assertIn(
                "completed-node:exploration-checkout",
                json.loads(explored.stdout)["artifacts"],
                msg=explored.stdout,
            )
            facts = RealSystemRunStore.open_readonly(
                run_store_root, bundle.brief.run_id
            ).read_state().facts
            self.assertEqual((), facts.pending_real_system_decisions)
            self.assertEqual(
                {"baseline-checkout", "exploration-checkout"},
                {item.node_id for item in facts.node_completions},
            )

    def test_cli_reopen_pauses_unsettled_fixture_intent_without_retry(self) -> None:
        from scripts.graph_v5.runtime import RealRuntimeController
        from scripts.graph_v5.store import RealSystemRunStore

        bundle = valid_bundle()
        manifest = valid_manifest()
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            run_store_root = temporary_root / "run-store"
            bundle_path, manifest_path = write_admission_inputs(
                temporary_root, bundle=bundle, manifest=manifest
            )
            started = invoke_graphctl(
                "start",
                "--trajectory-brief", str(bundle_path),
                "--adapter-manifest", str(manifest_path),
                "--run-store-root", str(run_store_root),
                cwd=temporary_root,
            )
            self.assertEqual(started.returncode, 0, msg=started.stderr)

            runtime = RealRuntimeController.open(
                root=run_store_root, run_id=bundle.brief.run_id
            )
            authority = runtime._store.next_executable_authority()
            assert authority is not None
            intent = runtime._derive_persisted_operation_intent(authority)
            runtime._store.record_external_intent(intent)

            resumed = invoke_graphctl(
                "run",
                "--run-store-root", str(run_store_root),
                "--run-id", bundle.brief.run_id,
                cwd=temporary_root,
            )
            self.assertEqual(resumed.returncode, 0, msg=resumed.stderr)
            self.assertEqual(json.loads(resumed.stdout)["error_code"], "run_rejected")
            state = RealSystemRunStore.open_readonly(
                run_store_root, bundle.brief.run_id
            ).read_state()
            self.assertEqual("paused", state.mode)
            self.assertEqual((intent,), state.facts.external_operation_intents)
            self.assertEqual((), state.facts.external_operation_receipts)

    def test_persisted_fixture_replay_succeeds_and_source_drift_pauses_before_action(self) -> None:
        from scripts.graph_v5.adapters.fixture_journey import PersistedFixtureAuthorityAdapter
        from scripts.graph_v5.runtime import RealRuntimeController

        bundle = valid_bundle()
        manifest = valid_manifest()
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            success_root = temporary_root / "success-store"
            success_bundle, success_manifest = write_admission_inputs(
                temporary_root, bundle=bundle, manifest=manifest
            )
            started = invoke_graphctl(
                "start",
                "--trajectory-brief", str(success_bundle),
                "--adapter-manifest", str(success_manifest),
                "--run-store-root", str(success_root),
                cwd=temporary_root,
            )
            self.assertEqual(started.returncode, 0, msg=started.stderr)
            advanced = invoke_graphctl(
                "run",
                "--run-store-root", str(success_root),
                "--run-id", bundle.brief.run_id,
                cwd=temporary_root,
            )
            self.assertEqual(advanced.returncode, 0, msg=advanced.stderr)
            replay = RealRuntimeController.open(
                root=success_root, run_id=bundle.brief.run_id
            ).run_final_replay_from_persisted_authority()
            self.assertIsNone(replay.stop_reason)

            drift_root = temporary_root / "drift-store"
            drift_bundle, drift_manifest = write_admission_inputs(
                temporary_root / "drift-input", bundle=bundle, manifest=manifest
            )
            started = invoke_graphctl(
                "start",
                "--trajectory-brief", str(drift_bundle),
                "--adapter-manifest", str(drift_manifest),
                "--run-store-root", str(drift_root),
                cwd=temporary_root,
            )
            self.assertEqual(started.returncode, 0, msg=started.stderr)
            advanced = invoke_graphctl(
                "run",
                "--run-store-root", str(drift_root),
                "--run-id", bundle.brief.run_id,
                cwd=temporary_root,
            )
            self.assertEqual(advanced.returncode, 0, msg=advanced.stderr)
            runtime = RealRuntimeController.open(root=drift_root, run_id=bundle.brief.run_id)
            sealed = runtime.environment_snapshot
            action_calls: list[object] = []

            def drifted_snapshot(adapter: object) -> object:
                return sealed.model_copy(update={"target_identity_digest": "f" * 64})

            def forbidden_action(*arguments: object, **keywords: object) -> object:
                action_calls.append((arguments, keywords))
                raise AssertionError("source drift must pause before replay action")

            with (
                patch.object(
                    PersistedFixtureAuthorityAdapter,
                    "environment_snapshot",
                    new=drifted_snapshot,
                ),
                patch.object(
                    PersistedFixtureAuthorityAdapter,
                    "act",
                    new=forbidden_action,
                ),
            ):
                drifted = runtime.run_final_replay_from_persisted_authority()

            self.assertEqual("environment_snapshot_drift", drifted.stop_reason)
            self.assertEqual("paused", drifted.state.mode)
            self.assertEqual([], action_calls)


if __name__ == "__main__":
    unittest.main()
