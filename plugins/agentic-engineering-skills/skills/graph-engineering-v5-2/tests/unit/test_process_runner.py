from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

from scripts.graph_v5.policy import EvidenceRedactionPolicy, PolicyError
from scripts.graph_v5.process_runner import (
    EnvironmentPolicy,
    ProcessCommand,
    ProcessRunner,
)


class ProcessRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.worktree = root / "worktree"
        self.fixture_root = root / "fixtures"
        self.worktree.mkdir()
        self.fixture_root.mkdir()
        self.runner = ProcessRunner(
            admitted_worktree=self.worktree,
            admitted_fixture_root=self.fixture_root,
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _command(self, source: str, **kwargs: object) -> ProcessCommand:
        return ProcessCommand(
            argv=(sys.executable, "-c", source),
            cwd=self.worktree,
            **kwargs,
        )

    def test_child_does_not_inherit_parent_environment(self) -> None:
        command = self._command(
            "import os; print(os.environ.get('PARENT_SECRET', 'missing'))"
        )
        environment = {"PATH": os.environ["PATH"], "PARENT_SECRET": "not-for-child"}

        result = self.runner.run(
            command,
            env_policy=EnvironmentPolicy.empty(),
            parent_environment=environment,
        )

        self.assertEqual(result.stdout.splitlines(), ["missing"])
        self.assertNotIn("PARENT_SECRET", result.stdout)
        self.assertNotIn("not-for-child", result.stdout)

    def test_resolved_secret_is_redacted_before_process_result_is_returned(self) -> None:
        command = self._command(
            "import os; print('token=' + os.environ['SERVICE_TEST_TOKEN'])",
            secret_references=("SERVICE_TEST_TOKEN",),
        )
        environment = {"PATH": os.environ["PATH"]}

        result = self.runner.run(
            command,
            env_policy=EnvironmentPolicy(secret_references=("SERVICE_TEST_TOKEN",)),
            parent_environment=environment,
            secret_resolver=lambda reference: "resolved-only-during-spawn",
        )

        self.assertEqual(result.stdout.splitlines(), ["token="])
        self.assertNotIn("resolved-only-during-spawn", repr(result.receipt))
        self.assertEqual(
            result.receipt.stdout_redaction.policy_digest,
            result.receipt.redaction_policy_digest,
        )

    def test_resolved_secret_literal_in_argv_is_rejected_before_spawn(self) -> None:
        command = ProcessCommand(
            argv=(sys.executable, "-c", "import sys; print(sys.argv[1])", "resolved-only-during-spawn"),
            cwd=self.worktree,
            secret_references=("SERVICE_TEST_TOKEN",),
        )
        environment = {"PATH": os.environ["PATH"]}

        with self.assertRaisesRegex(PolicyError, "argv"):
            self.runner.run(
                command,
                env_policy=EnvironmentPolicy(secret_references=("SERVICE_TEST_TOKEN",)),
                parent_environment=environment,
                secret_resolver=lambda reference: "resolved-only-during-spawn",
            )

    def test_split_or_encoded_resolved_secret_in_argv_is_rejected_before_spawn(self) -> None:
        for literal in (
            ("resolved-only", "-during-spawn"),
            ("cmVzb2x2ZWQtb25seS1kdXJpbmctc3Bhd24=",),
            ("cmVzb2x2ZWQtb25seS1kdXJpbmctc3Bhd24",),
            ("7265736F6C7665642D6F6E6C792D647572696E672D737061776E",),
            ("cm Vz b2x2 ZWQt b25s eS1k dXJp bmct c3Bh d24=",),
        ):
            with self.subTest(literal=literal):
                command = ProcessCommand(
                    argv=(
                        sys.executable,
                        "-c",
                        "import sys; print(''.join(sys.argv[1:]))",
                        *literal,
                    ),
                    cwd=self.worktree,
                    secret_references=("SERVICE_TEST_TOKEN",),
                )
                environment = {"PATH": os.environ["PATH"]}

                with self.assertRaisesRegex(PolicyError, "argv"):
                    self.runner.run(
                        command,
                        env_policy=EnvironmentPolicy(
                            secret_references=("SERVICE_TEST_TOKEN",)
                        ),
                        parent_environment=environment,
                        secret_resolver=lambda reference: "resolved-only-during-spawn",
                    )

    def test_rejects_cwd_outside_admitted_worktree_and_fixture_roots(self) -> None:
        command = ProcessCommand(
            argv=(sys.executable, "-c", "print('should not run')"),
            cwd=Path(self.temporary_directory.name),
        )

        with self.assertRaisesRegex(PolicyError, "cwd"):
            self.runner.run(command, env_policy=EnvironmentPolicy.empty())

    def test_output_cap_blocks_unpersisted_oversized_output(self) -> None:
        command = self._command("print('x' * 32)")
        policy = EvidenceRedactionPolicy(
            redaction_policy_digest="a" * 64,
            max_output_bytes=16,
        )

        with self.assertRaisesRegex(PolicyError, "output cap"):
            self.runner.run(
                command,
                env_policy=EnvironmentPolicy.empty(),
                evidence_policy=policy,
            )

    def test_output_cap_terminates_process_before_delayed_completion(self) -> None:
        command = self._command(
            "import sys, time; print('x' * 32, flush=True); time.sleep(4)"
        )
        policy = EvidenceRedactionPolicy(
            redaction_policy_digest="d" * 64,
            max_output_bytes=16,
        )

        started = time.monotonic()
        with self.assertRaisesRegex(PolicyError, "output cap"):
            self.runner.run(
                command,
                env_policy=EnvironmentPolicy.empty(),
                evidence_policy=policy,
            )

        self.assertLess(time.monotonic() - started, 2.0)

    def test_output_cap_is_shared_by_stdout_and_stderr(self) -> None:
        command = self._command(
            "import sys; print('x' * 9); print('y' * 9, file=sys.stderr)"
        )
        policy = EvidenceRedactionPolicy(
            redaction_policy_digest="e" * 64,
            max_output_bytes=16,
        )

        with self.assertRaisesRegex(PolicyError, "output cap"):
            self.runner.run(
                command,
                env_policy=EnvironmentPolicy.empty(),
                evidence_policy=policy,
            )

    def test_timeout_terminates_child_after_it_closes_output_pipes(self) -> None:
        command = self._command(
            "import os, time; os.close(1); os.close(2); time.sleep(4)",
            timeout_seconds=0.1,
        )

        started = time.monotonic()
        with self.assertRaisesRegex(PolicyError, "timed out"):
            self.runner.run(command, env_policy=EnvironmentPolicy.empty())

        self.assertLess(time.monotonic() - started, 2.0)

    def test_output_cap_terminates_descendant_holding_output_pipes(self) -> None:
        command = self._command(
            "import subprocess, sys; "
            "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(4)']); "
            "print('x' * 32, flush=True)"
        )
        policy = EvidenceRedactionPolicy(
            redaction_policy_digest="f" * 64,
            max_output_bytes=16,
        )

        started = time.monotonic()
        with self.assertRaisesRegex(PolicyError, "output cap"):
            self.runner.run(
                command,
                env_policy=EnvironmentPolicy.empty(),
                evidence_policy=policy,
            )

        self.assertLess(time.monotonic() - started, 2.0)


if __name__ == "__main__":
    unittest.main()
