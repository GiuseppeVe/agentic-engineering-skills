from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.graph_v5.canonical import canonical_json_bytes
from scripts.graph_v5.trajectory import render_trajectory_markdown
from tests.support.trajectory import confirmation_for, valid_trajectory_brief


ROOT = Path(__file__).resolve().parents[2]
GRAPHCTL = ROOT / "scripts" / "graphctl.py"
ALLOWED_COMMANDS = {"start", "run", "status", "decision"}


def invoke_graphctl(*arguments: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(GRAPHCTL), *arguments],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def parse_subcommands(help_output: str) -> set[str]:
    match = re.search(r"usage: .*?\{([^}]+)\}", help_output)
    if match is None:
        raise AssertionError(f"subcommand list absent from help:\n{help_output}")
    return set(match.group(1).split(","))


def write_confirmed_bundle(root: Path) -> tuple[Path, str]:
    brief = valid_trajectory_brief()
    confirmation = confirmation_for(brief)
    bundle_path = root / "confirmed-trajectory"
    bundle_path.mkdir()
    (bundle_path / "trajectory-brief.json").write_bytes(
        canonical_json_bytes(brief.model_dump(mode="json"))
    )
    (bundle_path / "trajectory-brief.md").write_bytes(
        render_trajectory_markdown(brief)
    )
    (bundle_path / "trajectory-confirmation.json").write_bytes(
        canonical_json_bytes(confirmation.model_dump(mode="json"))
    )
    return bundle_path, brief.digest


def snapshot_files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


class PublicCliContractTests(unittest.TestCase):

    def test_help_exposes_exactly_the_v5_commands_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            result = invoke_graphctl("--help", cwd=temporary_root)

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertEqual(parse_subcommands(result.stdout), ALLOWED_COMMANDS)
            self.assertEqual(list(temporary_root.iterdir()), [])

    def test_start_help_exposes_trajectory_bundle_not_legacy_goal_brief(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = invoke_graphctl("start", "--help", cwd=Path(temporary_directory))

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn("--trajectory-brief", result.stdout)
            self.assertNotIn("--goal-brief", result.stdout)

    def test_preview_and_dry_run_are_read_only_options_not_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)

            for command in ("start", "run"):
                help_result = invoke_graphctl(command, "--help", cwd=temporary_root)
                self.assertEqual(help_result.returncode, 0, msg=help_result.stderr)
                self.assertIn("--preview", help_result.stdout)
                self.assertIn("--dry-run", help_result.stdout)

            self.assertEqual(list(temporary_root.iterdir()), [])

    def test_v52_run_help_excludes_low_level_execution_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = invoke_graphctl("run", "--help", cwd=Path(temporary_directory))

        self.assertEqual(result.returncode, 0, msg=result.stderr)
        for forbidden in (
            "--fixture-file",
            "--fixture-scenario",
            "--node",
            "--intent",
            "--target-url",
        ):
            self.assertNotIn(forbidden, result.stdout)

    def test_preview_and_dry_run_invocations_do_not_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)

            for command in ("start", "run"):
                for option in ("--preview", "--dry-run"):
                    result = invoke_graphctl(command, option, cwd=temporary_root)

                    self.assertEqual(result.returncode, 0, msg=result.stderr)
                    self.assertIn("status", json.loads(result.stdout))
                    self.assertEqual(list(temporary_root.iterdir()), [])

    def test_retired_v4_commands_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)

            for command in ("init-run", "record-finding", "benchmark-candidate"):
                result = invoke_graphctl(command, cwd=temporary_root)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("invalid choice", result.stderr)
                self.assertEqual(list(temporary_root.iterdir()), [])

    def test_status_invocation_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)

            result = invoke_graphctl("status", cwd=temporary_root)

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn("status", json.loads(result.stdout))
            self.assertEqual(list(temporary_root.iterdir()), [])

    def test_decision_reaches_the_public_facade(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            result = invoke_graphctl("decision", cwd=Path(temporary_directory))

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn("status", json.loads(result.stdout))

    def test_goal_brief_is_rejected_with_actionable_migration_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            result = invoke_graphctl(
                "start",
                "--goal-brief",
                "old.json",
                cwd=temporary_root,
            )

            self.assertEqual(result.returncode, 2, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["error_code"], "goal_brief_removed")
            self.assertEqual(
                payload["summary"],
                "--goal-brief is no longer supported by Graph Engineering V5.\n"
                "Create or confirm a graph-v5.trajectory-brief.v1 input and use --trajectory-brief.",
            )
            self.assertEqual(list(temporary_root.iterdir()), [])

    def test_start_accepts_confirmed_trajectory_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            bundle_path, expected_digest = write_confirmed_bundle(temporary_root)

            result = invoke_graphctl(
                "start",
                "--trajectory-brief",
                str(bundle_path),
                "--dry-run",
                cwd=temporary_root,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertEqual(json.loads(result.stdout)["trajectory_digest"], expected_digest)

    def test_start_rejects_bare_trajectory_brief_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            bundle_path, _ = write_confirmed_bundle(temporary_root)
            bare_brief = bundle_path / "trajectory-brief.json"
            before = {
                path.relative_to(temporary_root).as_posix(): path.read_bytes()
                for path in temporary_root.rglob("*")
                if path.is_file()
            }

            result = invoke_graphctl(
                "start",
                "--trajectory-brief",
                str(bare_brief),
                "--dry-run",
                cwd=temporary_root,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertEqual(json.loads(result.stdout)["error_code"], "invalid_trajectory_brief")
            self.assertEqual(
                snapshot_files(temporary_root),
                before,
            )

    def test_start_identifies_missing_confirmation_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            bundle_path, _ = write_confirmed_bundle(temporary_root)
            (bundle_path / "trajectory-confirmation.json").unlink()
            before = snapshot_files(temporary_root)

            result = invoke_graphctl(
                "start", "--trajectory-brief", str(bundle_path), cwd=temporary_root
            )

            payload = json.loads(result.stdout)
            self.assertEqual(payload["error_code"], "invalid_trajectory_brief")
            self.assertEqual(
                payload["root_cause_hint"],
                "confirmed trajectory bundle is missing trajectory-confirmation.json",
            )
            self.assertEqual(snapshot_files(temporary_root), before)

    def test_start_identifies_noncanonical_brief_json_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            bundle_path, _ = write_confirmed_bundle(temporary_root)
            (bundle_path / "trajectory-brief.json").write_bytes(b'{"bad": true}\n')
            before = snapshot_files(temporary_root)

            result = invoke_graphctl(
                "start", "--trajectory-brief", str(bundle_path), cwd=temporary_root
            )

            payload = json.loads(result.stdout)
            self.assertEqual(payload["error_code"], "invalid_trajectory_brief")
            self.assertEqual(
                payload["root_cause_hint"],
                "confirmed trajectory bundle trajectory-brief.json is not canonical JSON",
            )
            self.assertEqual(snapshot_files(temporary_root), before)

    def test_start_identifies_markdown_mismatch_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            bundle_path, _ = write_confirmed_bundle(temporary_root)
            (bundle_path / "trajectory-brief.md").write_bytes(b"tampered\n")
            before = snapshot_files(temporary_root)

            result = invoke_graphctl(
                "start", "--trajectory-brief", str(bundle_path), cwd=temporary_root
            )

            payload = json.loads(result.stdout)
            self.assertEqual(payload["error_code"], "invalid_trajectory_brief")
            self.assertEqual(
                payload["root_cause_hint"],
                "confirmed trajectory bundle trajectory-brief.md invalid: "
                "Markdown differs from canonical trajectory",
            )
            self.assertEqual(snapshot_files(temporary_root), before)


if __name__ == "__main__":
    unittest.main()
