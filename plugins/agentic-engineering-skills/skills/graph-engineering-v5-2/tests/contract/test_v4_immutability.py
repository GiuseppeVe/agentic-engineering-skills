from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from scripts.graph_v5.models import RunState, import_v4_replacement_brief


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


class V4ImmutabilityContractTests(unittest.TestCase):
    def test_v4_payload_becomes_untrusted_replacement_brief_not_v5_state(self) -> None:
        predecessor = {
            "schema_version": "v4",
            "run_id": "v4-run-17",
            "phase": "planning",
            "findings": [{"id": "finding-1", "status": "open"}],
        }

        brief = import_v4_replacement_brief(predecessor, provenance="fixture:v4-run-17")

        self.assertEqual(brief.predecessor_schema, "v4")
        self.assertEqual(brief.trust, "untrusted_predecessor_observation")
        self.assertEqual(brief.original_bytes, json.dumps(predecessor, sort_keys=True, separators=(",", ":")))
        with self.assertRaises(ValidationError):
            RunState.model_validate(predecessor)

    def test_v4_replacement_brief_cannot_be_recast_as_active_run(self) -> None:
        brief = import_v4_replacement_brief(
            {"schema_version": "v4", "run_id": "v4-run-17", "capsules": []},
            provenance="fixture:v4-run-17",
        )

        with self.assertRaises(ValidationError):
            RunState.model_validate(brief.model_dump())

    def test_public_status_projects_v4_history_but_mutators_return_replacement_brief(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            predecessor = temporary_root / "v4-terminal.json"
            predecessor.write_text(
                json.dumps(
                    {
                        "schema_version": "v4",
                        "run_id": "v4-run-17",
                        "phase": "succeeded",
                        "terminal_history": ["verified"],
                    }
                ),
                encoding="utf-8",
            )
            before = predecessor.read_bytes()

            status = invoke_graphctl(
                "status", "--v4-reference", str(predecessor), cwd=temporary_root
            )
            self.assertEqual(status.returncode, 0, msg=status.stderr)
            self.assertEqual(json.loads(status.stdout)["status"], "succeeded")

            for command in ("start", "run", "decision"):
                with self.subTest(command=command):
                    result = invoke_graphctl(
                        command,
                        "--v4-reference",
                        str(predecessor),
                        cwd=temporary_root,
                    )
                    payload = json.loads(result.stdout)
                    self.assertEqual(result.returncode, 0, msg=result.stderr)
                    self.assertEqual(payload["error_code"], "v4_immutable")
                    self.assertIn("replacement", payload["summary"].lower())
                    self.assertEqual(predecessor.read_bytes(), before)

    def test_public_parser_rejects_raw_v4_state_and_environment_routes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            for raw_route in ("--environment", "--event", "--state"):
                with self.subTest(raw_route=raw_route):
                    result = invoke_graphctl("status", raw_route, "{}", cwd=temporary_root)
                    self.assertEqual(result.returncode, 2)
