from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.graph_v5.environment import (
    EnvironmentPreflightError,
    HostPreflightConfig,
    HostPreflightProbe,
    LocalHostPreflightProbe,
    host_preflight,
)
from scripts.graph_v5.models import BootstrapIntent


class FixtureHostProbe(HostPreflightProbe):
    """Deterministic host boundary; production preflight code stays real."""

    def __init__(self, profile: dict[str, object]) -> None:
        self.profile = profile
        self.git_calls: list[tuple[str, ...]] = []

    def executable_version(self, executable: str) -> tuple[str, str]:
        versions = self.profile["executables"]
        assert isinstance(versions, dict)
        value = versions.get(executable)
        if not isinstance(value, dict):
            raise EnvironmentPreflightError(f"missing executable: {executable}")
        return str(value["path"]), str(value["version"])

    def git(self, repository_root: Path, *args: str) -> str:
        self.git_calls.append(args)
        values = self.profile["git"]
        assert isinstance(values, dict)
        key = " ".join(args)
        value = values.get(key)
        if value is None:
            raise AssertionError(f"unconfigured git query: {key}")
        return str(value)

    def long_paths_enabled(self) -> bool:
        return bool(self.profile["long_paths_enabled"])

    def branch_exists(self, repository_root: Path, branch: str) -> bool:
        branches = self.profile["branches"]
        assert isinstance(branches, list)
        return branch in branches

    def registered_worktree_paths(self, repository_root: Path) -> tuple[Path, ...]:
        worktrees = self.profile["worktrees"]
        assert isinstance(worktrees, list)
        return tuple(Path(value) for value in worktrees)

    def platform_name(self) -> str:
        return str(self.profile["platform"])

    def host_values(self) -> tuple[str, str, str]:
        return ("Windows", "11", "AMD64")


def _profile(name: str) -> dict[str, object]:
    root = Path(__file__).resolve().parents[2] / "fixtures" / "host_profiles"
    return json.loads((root / name).read_text(encoding="utf-8"))


def _intent(worktree: Path) -> BootstrapIntent:
    return BootstrapIntent(
        run_id="run-host-preflight",
        transaction_id="transaction-host-preflight",
        requested_base_revision="a" * 40,
        candidate_branch="graph-run/run-host-preflight",
        candidate_worktree_path=str(worktree),
        compensation_plan=("remove-exact-worktree", "delete-exact-branch"),
    )


class HostPreflightTests(unittest.TestCase):
    def test_local_probe_fails_closed_on_executable_and_git_timeout(self) -> None:
        probe = LocalHostPreflightProbe()
        with (
            patch("scripts.graph_v5.environment.shutil.which", return_value="C:\\tools\\node.exe"),
            patch(
                "scripts.graph_v5.environment.subprocess.run",
                side_effect=subprocess.TimeoutExpired(["node", "--version"], 10.0),
            ),
        ):
            with self.assertRaisesRegex(EnvironmentPreflightError, "timed out"):
                probe.executable_version("node")
        with patch(
            "scripts.graph_v5.environment.subprocess.run",
            side_effect=subprocess.TimeoutExpired(["git", "status"], 10.0),
        ):
            with self.assertRaisesRegex(EnvironmentPreflightError, "timed out"):
                probe.git(Path.cwd(), "status", "--porcelain")

    def test_environment_identity_changes_with_resolved_executable_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = self._repository(root)
            store_root = root / "durable-store"
            store_root.mkdir()
            first_profile = _profile("node22.v1.json")
            second_profile = json.loads(json.dumps(first_profile))
            executables = second_profile["executables"]
            assert isinstance(executables, dict)
            node = executables["node"]
            assert isinstance(node, dict)
            node["path"] = "D:\\alternate\\node.exe"
            first = host_preflight(
                _intent(root / "runs" / "one"),
                repository_root=repository,
                durable_store_root=store_root,
                config=HostPreflightConfig(path_reserve_chars=32, volatile_environment_roots=()),
                probe=FixtureHostProbe(first_profile),
            )
            second = host_preflight(
                _intent(root / "runs" / "two"),
                repository_root=repository,
                durable_store_root=store_root,
                config=HostPreflightConfig(path_reserve_chars=32, volatile_environment_roots=()),
                probe=FixtureHostProbe(second_profile),
            )
            self.assertNotEqual(first.environment.digest, second.environment.digest)

    def _repository(self, root: Path, *, node: str = "22") -> Path:
        repository = root / "repository"
        repository.mkdir()
        (repository / ".nvmrc").write_text(node + "\n", encoding="utf-8")
        (repository / "package.json").write_text(
            json.dumps(
                {
                    "engines": {"node": f">={node} <{int(node) + 1}"},
                    "packageManager": "npm@10.9.0",
                }
            ),
            encoding="utf-8",
        )
        (repository / "package-lock.json").write_text(
            '{"lockfileVersion":3}\n', encoding="utf-8"
        )
        return repository

    def test_derives_sealed_identity_from_repository_and_host_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = self._repository(root)
            store_root = root / "durable-store"
            store_root.mkdir()
            receipt = host_preflight(
                _intent(root / "runs" / "run-host-preflight"),
                repository_root=repository,
                durable_store_root=store_root,
                config=HostPreflightConfig(
                    path_reserve_chars=32, volatile_environment_roots=()
                ),
                probe=FixtureHostProbe(_profile("node22.v1.json")),
            )

            self.assertEqual(receipt.required_node_major, 22)
            self.assertEqual(receipt.environment.runtime, "node-22.12.0")
            self.assertEqual(receipt.environment.package_manager, "npm-10.9.0")
            self.assertEqual(receipt.environment.repository_revision, "a" * 40)
            self.assertEqual(receipt.durable_store_root, str(store_root.resolve()))
            self.assertTrue(receipt.lockfile_digest)

    def test_rejects_node_24_for_node_22_before_any_git_effect(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = self._repository(root)
            store_root = root / "durable-store"
            store_root.mkdir()
            probe = FixtureHostProbe(_profile("node24.v1.json"))

            with self.assertRaisesRegex(EnvironmentPreflightError, "requires Node 22"):
                host_preflight(
                    _intent(root / "runs" / "run-host-preflight"),
                    repository_root=repository,
                    durable_store_root=store_root,
                    config=HostPreflightConfig(
                        path_reserve_chars=32, volatile_environment_roots=()
                    ),
                    probe=probe,
                )

            self.assertEqual(probe.git_calls, [])

    def test_rejects_npm_version_that_disagrees_with_package_manager_metadata_before_git_effect(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = self._repository(root)
            store_root = root / "durable-store"
            store_root.mkdir()
            profile = _profile("node22.v1.json")
            executables = profile["executables"]
            assert isinstance(executables, dict)
            npm = executables["npm"]
            assert isinstance(npm, dict)
            npm["version"] = "9.9.9"
            probe = FixtureHostProbe(profile)

            with self.assertRaisesRegex(
                EnvironmentPreflightError,
                "requires npm 10.9.0; resolved npm 9.9.9",
            ):
                host_preflight(
                    _intent(root / "runs" / "run-host-preflight"),
                    repository_root=repository,
                    durable_store_root=store_root,
                    config=HostPreflightConfig(
                        path_reserve_chars=32, volatile_environment_roots=()
                    ),
                    probe=probe,
                )

            self.assertEqual(probe.git_calls, [])

    def test_rejects_clean_checkout_at_different_head_from_requested_base(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = self._repository(root)
            store_root = root / "durable-store"
            store_root.mkdir()
            profile = _profile("node22.v1.json")
            git = profile["git"]
            assert isinstance(git, dict)
            git["rev-parse --verify HEAD^{commit}"] = "b" * 40

            with self.assertRaisesRegex(
                EnvironmentPreflightError,
                "checkout HEAD does not match requested base revision",
            ):
                host_preflight(
                    _intent(root / "runs" / "run-host-preflight"),
                    repository_root=repository,
                    durable_store_root=store_root,
                    config=HostPreflightConfig(
                        path_reserve_chars=32, volatile_environment_roots=()
                    ),
                    probe=FixtureHostProbe(profile),
                )

    def test_rejects_volatile_store_before_git_effect(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = self._repository(root)
            volatile_store = root / "dsh-session" / "store"
            volatile_store.mkdir(parents=True)
            probe = FixtureHostProbe(_profile("node22.v1.json"))

            with self.assertRaisesRegex(EnvironmentPreflightError, "durable store"):
                host_preflight(
                    _intent(root / "runs" / "run-host-preflight"),
                    repository_root=repository,
                    durable_store_root=volatile_store,
                    config=HostPreflightConfig(
                        path_reserve_chars=32,
                        volatile_roots=(root / "dsh-session",),
                        volatile_environment_roots=(),
                    ),
                    probe=probe,
                )

            self.assertEqual(probe.git_calls, [])

    def test_rejects_unsafe_branch_before_git_effect(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = self._repository(root)
            store_root = root / "durable-store"
            store_root.mkdir()
            bad_intent = _intent(root / "runs" / "run-host-preflight").model_copy(
                update={"candidate_branch": "main"}
            )
            probe = FixtureHostProbe(_profile("node22.v1.json"))

            with self.assertRaisesRegex(EnvironmentPreflightError, "branch is unsafe"):
                host_preflight(
                    bad_intent,
                    repository_root=repository,
                    durable_store_root=store_root,
                    config=HostPreflightConfig(
                        path_reserve_chars=32, volatile_environment_roots=()
                    ),
                    probe=probe,
                )

            self.assertEqual(probe.git_calls, [])

    def test_rejects_git_invalid_branch_components_before_git_effect(self) -> None:
        invalid_branches = (
            "graph-run/.hidden",
            "graph-run/foo.lock/bar",
            "graph-run/foo\tbar",
        )
        for branch in invalid_branches:
            with self.subTest(branch=branch), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                repository = self._repository(root)
                store_root = root / "durable-store"
                store_root.mkdir()
                intent = _intent(root / "runs" / "run-host-preflight").model_copy(
                    update={"candidate_branch": branch}
                )
                probe = FixtureHostProbe(_profile("node22.v1.json"))

                with self.assertRaisesRegex(EnvironmentPreflightError, "branch is unsafe"):
                    host_preflight(
                        intent,
                        repository_root=repository,
                        durable_store_root=store_root,
                        config=HostPreflightConfig(
                            path_reserve_chars=32, volatile_environment_roots=()
                        ),
                        probe=probe,
                    )

                self.assertEqual(probe.git_calls, [])

    def test_rejects_dirty_base_and_windows_filemode_mismatch(self) -> None:
        cases = (
            ("status --porcelain", " M package.json", "repository base is dirty"),
            ("config --get core.filemode", "true", "filemode mismatch"),
        )
        for key, value, message in cases:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                repository = self._repository(root)
                store_root = root / "durable-store"
                store_root.mkdir()
                profile = _profile("node22.v1.json")
                git = profile["git"]
                assert isinstance(git, dict)
                git[key] = value

                with self.assertRaisesRegex(EnvironmentPreflightError, message):
                    host_preflight(
                        _intent(root / "runs" / "run-host-preflight"),
                        repository_root=repository,
                        durable_store_root=store_root,
                        config=HostPreflightConfig(
                            path_reserve_chars=32, volatile_environment_roots=()
                        ),
                        probe=FixtureHostProbe(profile),
                    )

    def test_rejects_registered_or_noncanonical_worktree_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = self._repository(root)
            store_root = root / "durable-store"
            store_root.mkdir()
            candidate = root / "runs" / "run-host-preflight"
            profile = _profile("node22.v1.json")
            profile["worktrees"] = [str(candidate)]

            with self.assertRaisesRegex(EnvironmentPreflightError, "already registered"):
                host_preflight(
                    _intent(candidate),
                    repository_root=repository,
                    durable_store_root=store_root,
                    config=HostPreflightConfig(
                        path_reserve_chars=32, volatile_environment_roots=()
                    ),
                    probe=FixtureHostProbe(profile),
                )

            noncanonical = root / "runs" / "child" / ".." / "run-host-preflight"
            with self.assertRaisesRegex(EnvironmentPreflightError, "may not resolve"):
                host_preflight(
                    _intent(noncanonical),
                    repository_root=repository,
                    durable_store_root=store_root,
                    config=HostPreflightConfig(
                        path_reserve_chars=32, volatile_environment_roots=()
                    ),
                    probe=FixtureHostProbe(_profile("node22.v1.json")),
                )

    def test_rejects_preexisting_graph_branch_before_workspace_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = self._repository(root)
            store_root = root / "durable-store"
            store_root.mkdir()
            profile = _profile("node22.v1.json")
            profile["branches"] = ["graph-run/run-host-preflight"]

            with self.assertRaisesRegex(EnvironmentPreflightError, "branch already exists"):
                host_preflight(
                    _intent(root / "runs" / "run-host-preflight"),
                    repository_root=repository,
                    durable_store_root=store_root,
                    config=HostPreflightConfig(
                        path_reserve_chars=32, volatile_environment_roots=()
                    ),
                    probe=FixtureHostProbe(profile),
                )

    def test_rejects_long_windows_worktree_path_before_git_effect(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = self._repository(root)
            store_root = root / "durable-store"
            store_root.mkdir()
            profile = _profile("node22.v1.json")
            profile["long_paths_enabled"] = False
            probe = FixtureHostProbe(profile)

            with self.assertRaisesRegex(EnvironmentPreflightError, "exceeds Windows path limit"):
                host_preflight(
                    _intent(root / ("x" * 230)),
                    repository_root=repository,
                    durable_store_root=store_root,
                    config=HostPreflightConfig(
                        path_reserve_chars=32,
                        path_limit_chars=260,
                        volatile_environment_roots=(),
                    ),
                    probe=probe,
                )

            self.assertEqual(probe.git_calls, [])

    def test_projects_longest_repository_relative_path_into_candidate_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = self._repository(root)
            deep_directory = repository / ("d" * 60)
            deep_directory.mkdir()
            (deep_directory / ("f" * 60)).write_text("fixture", encoding="utf-8")
            store_root = root / "durable-store"
            store_root.mkdir()
            candidate = root / "runs" / "run-host-preflight"
            reserve = 32
            path_limit = len(str(candidate.resolve(strict=False))) + reserve + 50
            profile = _profile("node22.v1.json")
            profile["long_paths_enabled"] = False
            probe = FixtureHostProbe(profile)

            with self.assertRaisesRegex(EnvironmentPreflightError, "exceeds Windows path limit"):
                host_preflight(
                    _intent(candidate),
                    repository_root=repository,
                    durable_store_root=store_root,
                    config=HostPreflightConfig(
                        path_reserve_chars=reserve,
                        path_limit_chars=path_limit,
                        volatile_environment_roots=(),
                    ),
                    probe=probe,
                )

            self.assertEqual(probe.git_calls, [])
