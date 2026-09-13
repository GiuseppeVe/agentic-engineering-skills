from __future__ import annotations

import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from fixtures.repo_templates.git_repository import create_node22_repository, git_revision
from scripts.graph_v5.models import EnvironmentIdentity, GitTransaction, HostPreflightReceipt
from scripts.graph_v5.workspace import (
    GraphWorkspaceLifecycle,
    LocalWorkspaceToolchainProbe,
    WorktreePreflightConfig,
    WorktreePreflightReceipt,
    WorkspaceError,
    WorkspaceToolchainProbe,
)


class FixtureToolchainProbe(WorkspaceToolchainProbe):
    def __init__(self, versions: dict[Path, str]) -> None:
        self.versions = {path.resolve(): version for path, version in versions.items()}

    def executable_version(self, executable: Path) -> str:
        resolved = executable.resolve()
        if resolved in self.versions:
            return self.versions[resolved]
        return LocalWorkspaceToolchainProbe().executable_version(resolved)


def _snapshot(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(root).parts
    }


class GraphWorkspaceLifecycleTests(unittest.TestCase):
    def test_workspace_encoding_policy_rejects_empty_values_at_config_and_receipt_boundaries(self) -> None:
        for policy in (("utf-8", ""), ("utf-8", "not-a-real-codec")):
            with self.subTest(config_policy=policy):
                with self.assertRaisesRegex(ValueError, "encoding policy"):
                    WorktreePreflightConfig(
                        fixture_relative_path="fixture",
                        validator_relative_path="validator",
                        encoding_policy=policy,
                    )
        for policy in ((), ("utf-8", ""), ("utf-8", "not-a-real-codec")):
            with self.subTest(receipt_policy=policy):
                with self.assertRaisesRegex(ValidationError, "encoding policy"):
                    WorktreePreflightReceipt(
                        worktree_path="C:\\run",
                        source_repository_root="C:\\source",
                        branch="graph-run/test",
                        run_head_revision="abc123",
                        node_executable="C:\\node.exe",
                        npm_executable="C:\\npm.CMD",
                        package_binaries=(),
                        fixture_path="C:\\fixture",
                        validator_path="C:\\validator",
                        encoding_policy=policy,
                    )

    def test_preflight_executes_package_shim_and_rejects_corrupt_cmd(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = create_node22_repository(root / "repository")
            transaction = self._transaction(root, repository)
            lifecycle = self._lifecycle(repository)
            workspace = lifecycle.create_or_reconcile_graph_run_workspace(transaction)
            host = self._host_receipt(root, repository, transaction)
            shim = Path(
                workspace.worktree_path,
                "node_modules",
                ".bin",
                "fixture-validator.CMD",
            )
            shim.write_text("this-command-does-not-exist\r\n", encoding="ascii")

            with self.assertRaisesRegex(WorkspaceError, "not executable"):
                lifecycle.worktree_preflight_and_seal(workspace, object(), host)

    def test_compensation_refuses_advanced_owned_branch_before_removing_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = create_node22_repository(root / "repository")
            transaction = self._transaction(root, repository)
            lifecycle = self._lifecycle(repository)
            workspace = lifecycle.create_or_reconcile_graph_run_workspace(transaction)
            worktree = Path(workspace.worktree_path)
            (worktree / "advanced.txt").write_text("advanced", encoding="utf-8")
            subprocess.run(
                ["git", "add", "advanced.txt"], cwd=worktree, check=True, capture_output=True
            )
            subprocess.run(
                ["git", "commit", "-m", "advance"], cwd=worktree, check=True, capture_output=True
            )

            with self.assertRaisesRegex(WorkspaceError, "unexpected revision"):
                lifecycle.compensate_graph_run_workspace(transaction)

            self.assertTrue(worktree.is_dir())
            self.assertEqual(
                subprocess.run(
                    ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{transaction.branch}"],
                    cwd=repository,
                ).returncode,
                0,
            )

    def test_creates_and_reconciles_one_persistent_graph_run_workspace_from_verified_base(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = create_node22_repository(root / "repository")
            transaction = self._transaction(root, repository)
            lifecycle = self._lifecycle(repository)
            main_before = _snapshot(repository)

            first = lifecycle.create_or_reconcile_graph_run_workspace(transaction)
            second = lifecycle.create_or_reconcile_graph_run_workspace(transaction)

            self.assertEqual(first, second)
            self.assertEqual(first.run_head_revision, transaction.requested_base_revision)
            self.assertEqual(Path(first.worktree_path), Path(transaction.worktree_path))
            self.assertTrue(Path(first.worktree_path).is_dir())
            self.assertEqual(main_before, _snapshot(repository))
            self.assertNotIn("merge", lifecycle.git_operations)
            self.assertNotIn("push", lifecycle.git_operations)
            self.assertNotIn("rebase", lifecycle.git_operations)
            self.assertNotIn("reset", lifecycle.git_operations)

    def test_candidate_is_transient_v5_owned_child_of_current_run_head(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = create_node22_repository(root / "repository")
            transaction = self._transaction(root, repository)
            lifecycle = self._lifecycle(repository)
            graph_run = lifecycle.create_or_reconcile_graph_run_workspace(transaction)
            candidate = lifecycle.create_repair_candidate(
                graph_run,
                branch="graph-repair/run-test-001/test-001",
                worktree_path=root / "candidates" / "test-001",
            )

            self.assertEqual(candidate.base_run_head_revision, graph_run.run_head_revision)
            self.assertTrue(Path(candidate.worktree_path).is_dir())
            self.assertTrue(candidate.branch.startswith("graph-repair/run-test-001/"))
            lifecycle.discard_repair_candidate(candidate)
            self.assertFalse(Path(candidate.worktree_path).exists())
            self.assertTrue(Path(graph_run.worktree_path).is_dir())

    def test_preflight_fails_closed_for_partial_bin_and_returns_host_derived_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = create_node22_repository(root / "repository")
            transaction = self._transaction(root, repository)
            lifecycle = self._lifecycle(repository)
            workspace = lifecycle.create_or_reconcile_graph_run_workspace(transaction)
            host = self._host_receipt(root, repository, transaction)

            self.assertEqual(
                lifecycle.worktree_preflight_and_seal(workspace, object(), host),
                host.environment,
            )
            Path(workspace.worktree_path, "node_modules", ".bin", "fixture-validator.CMD").unlink()
            Path(workspace.worktree_path, "node_modules", ".bin", "fixture-validator").write_text(
                "plain text is not an executable shim", encoding="utf-8"
            )
            with self.assertRaisesRegex(WorkspaceError, "partial node_modules/.bin"):
                lifecycle.worktree_preflight_and_seal(workspace, object(), host)

    def test_preflight_resolves_npm_cmd_through_pathext_and_requires_node_22_materialization(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = create_node22_repository(root / "repository")
            transaction = self._transaction(root, repository)
            tools = root / "tools"
            tools.mkdir()
            node = tools / "node.exe"
            npm = tools / "npm.CMD"
            node.write_text("node", encoding="ascii")
            npm.write_text("npm", encoding="ascii")
            lifecycle = self._lifecycle(
                repository,
                node=node,
                npm=npm,
                toolchain=FixtureToolchainProbe({node: "v22.12.0", npm: "10.9.0"}),
            )
            workspace = lifecycle.create_or_reconcile_graph_run_workspace(transaction)
            host = self._host_receipt(root, repository, transaction, node=node, npm=npm)

            identity = lifecycle.worktree_preflight_and_seal(workspace, object(), host)

            self.assertEqual(identity.runtime, "node-22.12.0")
            self.assertEqual(lifecycle.last_preflight.npm_executable, str(npm.resolve()))
            bad_node = tools / "node24.exe"
            bad_node.write_text("node", encoding="ascii")
            bad_host = self._host_receipt(
                root,
                repository,
                transaction,
                node=bad_node,
                npm=npm,
                node_version="24.0.0",
                required_node_major=24,
            )
            with self.assertRaisesRegex(WorkspaceError, "requires Node 22"):
                lifecycle.worktree_preflight_and_seal(workspace, object(), bad_host)

    def _transaction(self, root: Path, repository: Path) -> GitTransaction:
        base = git_revision(repository)
        return GitTransaction(
            transaction_id="transaction-test-001",
            requested_base_revision=base,
            branch="graph-run/run-test-001",
            worktree_path=str(root / "runs" / "run-test-001"),
            status="prepared",
        )

    def _lifecycle(
        self,
        repository: Path,
        *,
        node: Path | None = None,
        npm: Path | None = None,
        toolchain: WorkspaceToolchainProbe | None = None,
    ) -> GraphWorkspaceLifecycle:
        node = node or (repository.parent / "tools" / "node.exe")
        npm = npm or (repository.parent / "tools" / "npm.CMD")
        node.parent.mkdir(exist_ok=True)
        node.write_text("node", encoding="ascii")
        npm.write_text("npm", encoding="ascii")
        return GraphWorkspaceLifecycle(
            repository,
            preflight=WorktreePreflightConfig(
                fixture_relative_path=".graph-v5-fixture",
                validator_relative_path=".graph-v5-validator",
                required_package_binaries=("fixture-validator",),
                executable_search_path=(node.parent,),
                pathext=".COM;.EXE;.BAT;.CMD",
                platform_name="Windows",
            ),
            toolchain_probe=toolchain
            or FixtureToolchainProbe({node: "v22.12.0", npm: "10.9.0"}),
        )

    def _host_receipt(
        self,
        root: Path,
        repository: Path,
        transaction: GitTransaction,
        *,
        node: Path | None = None,
        npm: Path | None = None,
        node_version: str = "22.12.0",
        required_node_major: int = 22,
    ) -> HostPreflightReceipt:
        node = node or (root / "tools" / "node.exe")
        npm = npm or (root / "tools" / "npm.CMD")
        base = transaction.requested_base_revision
        lock_digest = hashlib.sha256((repository / "package-lock.json").read_bytes()).hexdigest()
        environment = EnvironmentIdentity(
            repository_revision=base,
            runtime=f"node-{node_version}",
            package_manager="npm-10.9.0",
            lockfile_digest=lock_digest,
            host_fingerprint="host-fingerprint",
        )
        return HostPreflightReceipt(
            transaction_id=transaction.transaction_id,
            repository_root=str(repository.resolve()),
            repository_revision=base,
            requested_base_revision=base,
            candidate_worktree_path=transaction.worktree_path,
            durable_store_root=str((root / "store").resolve()),
            required_node_major=required_node_major,
            node_executable=str(node.resolve()),
            node_version=node_version,
            npm_executable=str(npm.resolve()),
            npm_version="10.9.0",
            package_manager="npm",
            lockfile_path=str((repository / "package-lock.json").resolve()),
            lockfile_digest=lock_digest,
            projected_path_length=120,
            path_reserve_chars=32,
            long_paths_enabled=True,
            git_filemode="false",
            host_fingerprint="host-fingerprint",
            environment=environment,
        )
