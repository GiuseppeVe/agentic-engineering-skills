from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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


def snapshot_bytes(*roots: Path) -> dict[str, bytes]:
    snapshot: dict[str, bytes] = {}
    for root in roots:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                snapshot[f"{root.name}/{path.relative_to(root).as_posix()}"] = path.read_bytes()
    return snapshot


def provider_budget_exhaustion_fixture() -> tuple[object, object]:
    """Build five native V5.2 actions: only fifth exceeds provider cap four."""

    from tests.unit.test_real_admission import valid_bundle, valid_manifest

    bundle = valid_bundle()
    source_manifest = valid_manifest()
    manifest = source_manifest.model_copy(
        update={
            "budgets": source_manifest.budgets.model_copy(
                update={
                    "max_user_actions": 5,
                    "max_provider_requests": 4,
                    "max_cost_micros": 5,
                    "max_requests": 5,
                    "max_persistence_writes": 5,
                    "max_duration_ms": 50_000,
                }
            )
        }
    )
    brief = bundle.brief.model_copy(
        update={
            "adapter_manifest_digest": manifest.digest,
            "execution_envelope": bundle.brief.execution_envelope.model_copy(
                update={"adapter_manifest_digest": manifest.digest}
            ),
        }
    )
    confirmation = bundle.confirmation.model_copy(
        update={
            "trajectory_digest": brief.digest,
            "adapter_manifest_digest": manifest.digest,
        }
    )
    baseline = tuple(
        bundle.baseline[0].model_copy(
            update={
                "proposal": bundle.baseline[0].proposal.model_copy(
                    update={
                        "node_id": f"provider-budget-action-{index}",
                        "target_landmark_id": f"provider-budget-target-{index}",
                    }
                )
            }
        )
        for index in range(1, 6)
    )
    return (
        bundle.model_copy(
            update={
                "brief": brief,
                "confirmation": confirmation,
                "baseline": baseline,
            }
        ),
        manifest,
    )


class ReadOnlyCliContractTests(unittest.TestCase):

    def test_run_verifies_persisted_authority_before_creating_fixture_adapter(self) -> None:
        from scripts import graphctl
        from scripts.graph_v5.adapters.user_journey import FixtureUserJourneyAdapter
        from scripts.graph_v5.store import StoreError

        arguments = graphctl.build_parser().parse_args(
            (
                "run",
                "--run-store-root", "missing-store",
                "--run-id", "missing-run",
                "--fixture-file", "missing-fixture.json",
                "--fixture-scenario", "missing-scenario",
            )
        )
        with (
            patch.object(graphctl.RuntimeController, "open", side_effect=StoreError("invalid stored authority")),
            patch.object(
                FixtureUserJourneyAdapter,
                "from_fixture_file",
                side_effect=AssertionError("fixture adapter must not be created"),
            ),
        ):
            result = graphctl.continue_run(arguments)
        self.assertEqual(result.error_code, "run_rejected")
        self.assertIn("invalid stored authority", result.root_cause_hint or "")

    def test_v52_status_is_byte_for_byte_read_only(self) -> None:
        from scripts.graph_v5.admission import RealAdmissionCoordinator
        from tests.unit.test_real_admission import valid_bundle, valid_manifest

        bundle = valid_bundle()
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            run_store_root = temporary_root / "run-store"
            RealAdmissionCoordinator.start(
                root=run_store_root,
                bundle=bundle,
                manifest=valid_manifest(),
            )
            before = snapshot_bytes(run_store_root)

            result = invoke_graphctl(
                "status",
                "--run-store-root", str(run_store_root),
                "--run-id", bundle.brief.run_id,
                cwd=temporary_root,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "running")
            self.assertEqual(snapshot_bytes(run_store_root), before)

    def test_v52_status_projects_persisted_manifest_budget_block_without_mutation_or_adapter(
        self,
    ) -> None:
        """Removing durable-block projection leaves retry advice or a next node visible."""

        from scripts import graphctl
        from scripts.graph_v5.admission import RealAdmissionCoordinator
        from scripts.graph_v5.runtime import RealRuntimeController

        bundle, manifest = provider_budget_exhaustion_fixture()
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            run_store_root = temporary_root / "run-store"
            runtime = RealAdmissionCoordinator.start(
                root=run_store_root,
                bundle=bundle,
                manifest=manifest,
            )
            for _ in range(5):
                if runtime.state.mode != "running":
                    break
                runtime.run_next_persisted_slice()
            state = runtime.state
            self.assertEqual("blocked", state.mode)
            self.assertEqual(4, len(state.facts.external_operation_intents))
            self.assertEqual(
                ("max_provider_requests",),
                state.facts.manifest_budget_exhaustions[-1].exhausted_budget_names,
            )
            before = snapshot_bytes(run_store_root)
            arguments = graphctl.build_parser().parse_args(
                (
                    "status",
                    "--run-store-root",
                    str(run_store_root),
                    "--run-id",
                    bundle.brief.run_id,
                )
            )

            with (
                patch.object(
                    RealRuntimeController,
                    "_construct_adapter_from_persisted_provider",
                    side_effect=AssertionError("status must not construct an adapter"),
                ),
                patch.object(
                    RealRuntimeController,
                    "_dispatch_reserved_effectful_slice",
                    side_effect=AssertionError("status must not dispatch an action"),
                ),
            ):
                projected = graphctl.project_status(arguments).as_dict()

            result = invoke_graphctl(
                "status",
                "--run-store-root",
                str(run_store_root),
                "--run-id",
                bundle.brief.run_id,
                cwd=temporary_root,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(projected, payload)
            self.assertEqual("blocked", payload["status"])
            self.assertEqual(
                "Manifest budget exhausted: max_provider_requests.",
                payload["stop_condition"],
            )
            self.assertFalse(payload["safe_retry"])
            self.assertIn("remaining-budget:provider_requests=0", payload["artifacts"])
            self.assertFalse(
                any(
                    item.startswith(("recommended-baseline:", "next-step:"))
                    for item in payload["artifacts"]
                )
            )
            self.assertEqual(snapshot_bytes(run_store_root), before)

    def test_v52_status_projects_pending_recovery_without_mutating_journal_or_lock(self) -> None:
        from scripts.graph_v5.admission import RealAdmissionCoordinator
        from tests.unit.test_real_admission import valid_bundle, valid_manifest

        bundle = valid_bundle()
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            run_store_root = temporary_root / "run-store"
            RealAdmissionCoordinator.start(
                root=run_store_root,
                bundle=bundle,
                manifest=valid_manifest(),
            )
            (run_store_root / "journal.json").write_bytes(b'{"pending":true}')
            (run_store_root / ".graph-v5.2.lock").write_bytes(b"locked")
            before = snapshot_bytes(run_store_root)

            result = invoke_graphctl(
                "status",
                "--run-store-root", str(run_store_root),
                "--run-id", bundle.brief.run_id,
                cwd=temporary_root,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "recovery_pending")
            self.assertEqual(payload["error_code"], "recovery_pending")
            self.assertEqual(snapshot_bytes(run_store_root), before)

    def test_validation_rejection_creates_no_repository_bytecode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            source_root = temporary_root / "source"
            source_scripts = source_root / "scripts"
            source_scripts.mkdir(parents=True)
            shutil.copy2(GRAPHCTL, source_scripts / "graphctl.py")
            package_marker = ROOT / "scripts" / "__init__.py"
            if package_marker.exists():
                shutil.copy2(package_marker, source_scripts / "__init__.py")
            shutil.copytree(
                ROOT / "scripts" / "graph_v5",
                source_scripts / "graph_v5",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
            bare_brief = temporary_root / "bare-brief.json"
            bare_brief.write_text("{}", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(source_scripts / "graphctl.py"),
                    "start",
                    "--trajectory-brief",
                    str(bare_brief),
                ],
                cwd=temporary_root,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(
                list(source_root.rglob("*.pyc")),
                [],
                msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
            )

    def test_read_only_and_parser_paths_preserve_every_watched_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            run_store_root = temporary_root / "run-store"
            artifact_root = temporary_root / "artifacts"
            benchmark_root = temporary_root / "benchmarks"
            for root in (run_store_root, artifact_root, benchmark_root):
                root.mkdir()
                (root / "sentinel.bin").write_bytes(root.name.encode("utf-8"))
            before = snapshot_bytes(run_store_root, artifact_root, benchmark_root)
            watched = (
                "--run-store-root", str(run_store_root),
                "--artifact-root", str(artifact_root),
                "--benchmark-root", str(benchmark_root),
            )

            for arguments, expected_returncode in (
                (("--help",), 0),
                (("status", *watched, "--run-id", "missing"), 0),
                (("start", "--preview", *watched), 0),
                (("start", "--dry-run", *watched), 0),
                (("start", "--goal-brief", "old.json", *watched), 2),
                (("run", "--preview", *watched, "--run-id", "missing"), 0),
                (("run", "--dry-run", *watched, "--run-id", "missing"), 0),
                (("status", *watched, "--unknown-route"), 2),
                (("raw-state-edit", *watched), 2),
            ):
                with self.subTest(arguments=arguments):
                    result = invoke_graphctl(*arguments, cwd=temporary_root)
                    self.assertEqual(result.returncode, expected_returncode, msg=result.stderr)
                    self.assertEqual(
                        snapshot_bytes(run_store_root, artifact_root, benchmark_root),
                        before,
                    )

if __name__ == "__main__":
    unittest.main()
