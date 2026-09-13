from __future__ import annotations

import hashlib
import os
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from fixtures.repo_templates.git_repository import create_node22_repository, git_revision
from scripts.graph_v5.environment import (
    HostPreflightConfig,
    HostPreflightProbe,
    SimulatedStartCrash,
    StartRequest,
    start_new_run,
)
from scripts.graph_v5.models import GitTransaction
from scripts.graph_v5.store import TransactionalRunStore
from scripts.graph_v5.workspace import (
    GraphWorkspaceLifecycle,
    LocalWorkspaceToolchainProbe,
    WorktreePreflightConfig,
    WorkspaceError,
)
from tests.unit.test_store import issue_capability, sample_state


def _snapshot(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(root).parts
    }


class _ToolchainProbe:
    def __init__(self, versions: dict[Path, str]) -> None:
        self.versions = {path.resolve(): version for path, version in versions.items()}

    def executable_version(self, executable: Path) -> str:
        resolved = executable.resolve()
        if resolved in self.versions:
            return self.versions[resolved]
        return LocalWorkspaceToolchainProbe().executable_version(resolved)


class _HostProbe(HostPreflightProbe):
    def __init__(self, node: Path, npm: Path) -> None:
        self.node = node
        self.npm = npm

    def executable_version(self, executable: str) -> tuple[str, str]:
        if executable == "node":
            return str(self.node), "v22.12.0"
        if executable == "npm":
            return str(self.npm), "10.9.0"
        raise AssertionError(executable)

    def git(self, repository_root: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=repository_root,
            env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull},
            capture_output=True,
            check=True,
        )
        return result.stdout.decode("utf-8").strip()

    def branch_exists(self, repository_root: Path, branch: str) -> bool:
        result = subprocess.run(
            ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
            cwd=repository_root,
            env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull},
            capture_output=True,
            check=False,
        )
        return result.returncode == 0

    def registered_worktree_paths(self, repository_root: Path) -> tuple[Path, ...]:
        output = self.git(repository_root, "worktree", "list", "--porcelain")
        return tuple(
            Path(line.removeprefix("worktree ")).resolve(strict=False)
            for line in output.splitlines()
            if line.startswith("worktree ")
        )

    def long_paths_enabled(self) -> bool:
        return True

    def platform_name(self) -> str:
        return "Windows"

    def host_values(self) -> tuple[str, str, str]:
        return ("Windows", "11", "AMD64")


class IsolatedWorktreeTests(unittest.TestCase):
    def test_start_protocol_recovers_real_owned_worktree_without_main_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = create_node22_repository(root / "repository")
            tools = root / "tools"
            tools.mkdir()
            node = tools / "node.exe"
            npm = tools / "npm.CMD"
            node.write_text("node", encoding="ascii")
            npm.write_text("npm", encoding="ascii")
            lifecycle = GraphWorkspaceLifecycle(
                repository,
                preflight=WorktreePreflightConfig(
                    fixture_relative_path=".graph-v5-fixture",
                    validator_relative_path=".graph-v5-validator",
                    required_package_binaries=("fixture-validator",),
                    executable_search_path=(tools,),
                    pathext=".COM;.EXE;.BAT;.CMD",
                    platform_name="Windows",
                ),
                toolchain_probe=_ToolchainProbe({node: "v22.12.0", npm: "10.9.0"}),
            )
            state = sample_state()
            store_root = root / "store"
            store = TransactionalRunStore.open(store_root, issue_capability(store_root, state.run_id))
            store.initialize(state)
            request = StartRequest(
                repository_root=repository,
                requested_base_revision=git_revision(repository),
                candidate_branch="graph-run/start-recovery-001",
                candidate_worktree_path=root / "runs" / "start-recovery-001",
                durable_store_root=store.root,
                host_config=HostPreflightConfig(path_reserve_chars=32, volatile_environment_roots=()),
                host_probe=_HostProbe(node, npm),
                workspace_lifecycle=lifecycle,
                crash_after="workspace_created",
            )
            before = _snapshot(repository)

            with self.assertRaises(SimulatedStartCrash):
                start_new_run(request, store)
            self.assertTrue(request.candidate_worktree_path.is_dir())
            recovered = start_new_run(replace(request, crash_after=None), store)

            self.assertEqual(recovered.transaction.status, "reconciled")
            self.assertTrue(request.candidate_worktree_path.is_dir())
            self.assertEqual(before, _snapshot(repository))
    def test_main_bytes_stay_identical_across_success_pause_failure_and_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = create_node22_repository(root / "repository")
            before = _snapshot(repository)
            transaction = GitTransaction(
                transaction_id="transaction-isolation-001",
                requested_base_revision=git_revision(repository),
                branch="graph-run/isolation-001",
                worktree_path=str(root / "runs" / "isolation-001"),
                status="prepared",
            )
            preflight = WorktreePreflightConfig(
                fixture_relative_path=".graph-v5-fixture",
                validator_relative_path=".graph-v5-validator",
                required_package_binaries=("fixture-validator",),
            )
            lifecycle = GraphWorkspaceLifecycle(repository, preflight=preflight)

            success = lifecycle.create_or_reconcile_graph_run_workspace(transaction)
            self.assertEqual(before, _snapshot(repository))

            # Pause is deliberately zero-cleanup: persistent Graph-run evidence stays.
            self.assertTrue(Path(success.worktree_path).is_dir())
            self.assertEqual(before, _snapshot(repository))

            # An invalid candidate is a real failure path and may not mutate main.
            with self.assertRaisesRegex(WorkspaceError, "V5-owned child"):
                lifecycle.create_repair_candidate(
                    success,
                    branch="unowned/failure",
                    worktree_path=root / "candidates" / "failure",
                )
            self.assertTrue(Path(success.worktree_path).is_dir())
            self.assertEqual(before, _snapshot(repository))

            # A fresh lifecycle instance exercises restart reconciliation.
            recovered = GraphWorkspaceLifecycle(
                repository, preflight=preflight
            ).create_or_reconcile_graph_run_workspace(transaction)

            self.assertEqual(success, recovered)
            self.assertTrue(Path(recovered.worktree_path).is_dir())
            self.assertEqual(before, _snapshot(repository))
            branch = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=repository,
                capture_output=True,
                check=True,
                text=True,
                encoding="utf-8",
            ).stdout.strip()
            self.assertEqual(branch, "main")
