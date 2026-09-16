from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import dataclass, field, replace
from pathlib import Path

from scripts.graph_v5.canonical import canonical_json_bytes
from scripts.graph_v5.environment import (
    EnvironmentPreflightError,
    HostPreflightConfig,
    HostPreflightProbe,
    SimulatedStartCrash,
    StartRequest,
    StartTransactionError,
    WorkspaceReceipt,
    start_new_run,
)
from scripts.graph_v5.models import EnvironmentIdentity, GitTransaction, Observation, RunHead
from scripts.graph_v5.store import (
    EventFactReference,
    LedgerEvent,
    StoreError,
    TransactionalRunStore,
)
from tests.unit.test_store import event_payload, issue_capability, sample_state


class FixtureHostProbe(HostPreflightProbe):
    def __init__(self, profile: dict[str, object]) -> None:
        self.profile = profile

    def executable_version(self, executable: str) -> tuple[str, str]:
        values = self.profile["executables"]
        assert isinstance(values, dict)
        value = values[executable]
        assert isinstance(value, dict)
        return str(value["path"]), str(value["version"])

    def git(self, repository_root: Path, *args: str) -> str:
        values = self.profile["git"]
        assert isinstance(values, dict)
        return str(values[" ".join(args)])

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


@dataclass
class FakeWorkspaceLifecycle:
    created: set[tuple[str, str]] = field(default_factory=set)
    compensated: list[GitTransaction] = field(default_factory=list)
    fail_environment_preflight: bool = False
    run_head_revision: str | None = None
    environment_override: EnvironmentIdentity | None = None
    fail_compensation: bool = False

    def create_or_reconcile_graph_run_workspace(
        self, transaction: GitTransaction
    ) -> WorkspaceReceipt:
        self.created.add((transaction.branch, transaction.worktree_path))
        return WorkspaceReceipt(
            transaction_id=transaction.transaction_id,
            branch=transaction.branch,
            worktree_path=transaction.worktree_path,
            run_head_revision=self.run_head_revision or transaction.requested_base_revision,
        )

    def worktree_preflight_and_seal(
        self,
        workspace: WorkspaceReceipt,
        request: StartRequest,
        host_receipt: object,
    ) -> EnvironmentIdentity:
        if self.fail_environment_preflight:
            raise EnvironmentPreflightError("fixture preflight failed")
        return self.environment_override or host_receipt.environment  # type: ignore[union-attr]

    def compensate_graph_run_workspace(self, transaction: GitTransaction) -> None:
        if self.fail_compensation:
            raise OSError("fixture compensation failed")
        self.compensated.append(transaction)
        self.created.discard((transaction.branch, transaction.worktree_path))


def _profile() -> dict[str, object]:
    path = (
        Path(__file__).resolve().parents[2]
        / "fixtures"
        / "host_profiles"
        / "node22.v1.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _repository(root: Path) -> Path:
    repository = root / "repository"
    repository.mkdir(exist_ok=True)
    (repository / ".nvmrc").write_text("22\n", encoding="utf-8")
    (repository / "package.json").write_text(
        json.dumps(
            {
                "engines": {"node": ">=22 <23"},
                "packageManager": "npm@10.9.0",
            }
        ),
        encoding="utf-8",
    )
    (repository / "package-lock.json").write_text(
        '{"lockfileVersion":3}\n', encoding="utf-8"
    )
    return repository


class StartTransactionTests(unittest.TestCase):
    def test_replay_rejects_run_started_artifact_for_different_run_head(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = self._store(root)
            result = start_new_run(
                self._request(root, store, FakeWorkspaceLifecycle()), store
            )
            events = list(store.read_events())
            original = events[-1]
            self.assertEqual(original.kind, "run_started")
            wrong_head = RunHead(
                revision="b" * 40,
                environment_digest=result.environment.digest,
                fixture_digest=store.read_state().fixture_intent_digest,
            )
            wrong_artifact = store.put_artifact("run-head", wrong_head)
            events[-1] = LedgerEvent.create(
                sequence=original.sequence,
                kind="run_started",
                payload=EventFactReference(
                    fact_id=wrong_head.digest,
                    fact_digest=wrong_artifact.digest,
                ),
                previous_digest=original.previous_digest,
                state_digest=original.state_digest,
            )
            (store.root / "ledger.jsonl").write_bytes(
                b"".join(canonical_json_bytes(event) + b"\n" for event in events)
            )

            with self.assertRaisesRegex(StoreError, "run_started artifact"):
                store.read_state()

    def test_recovery_rejects_repository_that_differs_from_recorded_host_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = self._store(root)
            lifecycle = FakeWorkspaceLifecycle()
            with self.assertRaises(SimulatedStartCrash):
                start_new_run(
                    self._request(root, store, lifecycle, crash_after="host_preflight"),
                    store,
                )
            alternate_root = root / "alternate"
            alternate_root.mkdir()
            alternate_repository = _repository(alternate_root)
            recovery = replace(
                self._request(root, store, lifecycle),
                repository_root=alternate_repository,
            )

            with self.assertRaisesRegex(StartTransactionError, "repository root"):
                start_new_run(recovery, store)

            self.assertEqual(lifecycle.created, set())

    def test_start_rejects_non_initial_limits_before_git_effect(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store_root = root / "run-store"
            state = sample_state()
            old_limit = state.limits.active.value_for("causal_radius")
            widened = state.limits.append_widening(
                name="causal_radius",
                amount=old_limit.amount + 1,
                approver="test",
                reason="invalid pre-start widening",
                effective_graph_revision=0,
            )
            state = state.model_copy(update={"limits": widened})
            store = TransactionalRunStore.open(
                store_root, issue_capability(store_root, state.run_id)
            )
            store.initialize(state)
            lifecycle = FakeWorkspaceLifecycle()

            with self.assertRaisesRegex(StartTransactionError, "Limits version 1"):
                start_new_run(self._request(root, store, lifecycle), store)

            self.assertEqual(lifecycle.created, set())
            self.assertIsNone(store.read_state().facts.bootstrap_intent)

    def test_request_durable_store_must_match_capability_bound_store(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = self._store(root)
            lifecycle = FakeWorkspaceLifecycle()
            request = replace(
                self._request(root, store, lifecycle),
                durable_store_root=root / "safe-decoy-store",
            )
            request.durable_store_root.mkdir()
            with self.assertRaisesRegex(StartTransactionError, "durable store root"):
                start_new_run(request, store)
            self.assertEqual(lifecycle.created, set())
    def _request(
        self,
        root: Path,
        store: TransactionalRunStore,
        lifecycle: FakeWorkspaceLifecycle,
        *,
        crash_after: str | None = None,
    ) -> StartRequest:
        return StartRequest(
            repository_root=_repository(root),
            requested_base_revision="a" * 40,
            candidate_branch="graph-run/run-test-001",
            candidate_worktree_path=root / "runs" / "run-test-001",
            durable_store_root=store.root,
            host_config=HostPreflightConfig(
                path_reserve_chars=32, volatile_environment_roots=()
            ),
            host_probe=FixtureHostProbe(_profile()),
            workspace_lifecycle=lifecycle,
            crash_after=crash_after,
        )

    def _store(self, root: Path) -> TransactionalRunStore:
        store_root = root / "run-store"
        state = sample_state()
        store = TransactionalRunStore.open(
            store_root, issue_capability(store_root, state.run_id)
        )
        store.initialize(state)
        return store

    def test_every_durable_start_boundary_resumes_to_one_reconciled_workspace(self) -> None:
        boundaries = (
            "bootstrap_intent",
            "host_preflight",
            "git_transaction",
            "workspace_created",
            "git_created",
            "git_reconciled",
            "environment_sealed",
            "run_head_recorded",
            "run_started",
        )
        for boundary in boundaries:
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                store = self._store(root)
                lifecycle = FakeWorkspaceLifecycle()
                request = self._request(root, store, lifecycle, crash_after=boundary)

                with self.assertRaises(SimulatedStartCrash):
                    start_new_run(request, store)

                recovered = start_new_run(
                    self._request(root, store, lifecycle), store
                )
                transaction = store.read_state().facts.git_transaction
                self.assertIsNotNone(transaction)
                assert transaction is not None
                self.assertEqual(transaction.status, "reconciled")
                self.assertEqual(store.read_state().mode, "running")
                self.assertEqual(
                    lifecycle.created,
                    {(transaction.branch, transaction.worktree_path)},
                )
                self.assertEqual(recovered.environment, store.read_state().facts.environment)

    def test_host_failure_creates_no_workspace_or_git_transaction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = self._store(root)
            lifecycle = FakeWorkspaceLifecycle()
            bad_profile = _profile()
            executables = bad_profile["executables"]
            assert isinstance(executables, dict)
            node = executables["node"]
            assert isinstance(node, dict)
            node["version"] = "v24.0.0"
            request = StartRequest(
                repository_root=_repository(root),
                requested_base_revision="a" * 40,
                candidate_branch="graph-run/run-test-001",
                candidate_worktree_path=root / "runs" / "run-test-001",
                durable_store_root=store.root,
                host_config=HostPreflightConfig(
                    path_reserve_chars=32, volatile_environment_roots=()
                ),
                host_probe=FixtureHostProbe(bad_profile),
                workspace_lifecycle=lifecycle,
            )

            with self.assertRaisesRegex(EnvironmentPreflightError, "requires Node 22"):
                start_new_run(request, store)

            state = store.read_state()
            self.assertIsNotNone(state.facts.bootstrap_intent)
            self.assertIsNone(state.facts.git_transaction)
            self.assertEqual(lifecycle.created, set())
            self.assertEqual(state.facts.observations, ())

    def test_store_rejects_observation_before_run_started_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = self._store(root)
            lifecycle = FakeWorkspaceLifecycle()

            with self.assertRaises(SimulatedStartCrash):
                start_new_run(
                    self._request(
                        root,
                        store,
                        lifecycle,
                        crash_after="environment_sealed",
                    ),
                    store,
                )

            boot = store.read_state()
            self.assertEqual(boot.mode, "boot")
            self.assertIsNotNone(boot.facts.environment)
            self.assertIsNotNone(boot.facts.git_transaction)
            observation = Observation(
                observation_id="observation-before-run-started",
                node_id="choose-discipline",
                kind="behavioral",
                observed_state="must remain inadmissible",
                evidence_refs=("fixture",),
                run_head_digest="a" * 64,
            )
            unsafe_state = boot.model_copy(
                update={
                    "facts": boot.facts.model_copy(
                        update={"observations": (observation,)}
                    )
                }
            )

            with self.assertRaisesRegex(StoreError, "run_started"):
                store.append_event("observed", event_payload(), unsafe_state)

            self.assertEqual(store.read_state().facts.observations, ())

    def test_crash_after_physical_workspace_creation_leaves_prepared_transaction_for_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = self._store(root)
            lifecycle = FakeWorkspaceLifecycle()

            with self.assertRaises(SimulatedStartCrash):
                start_new_run(
                    self._request(
                        root,
                        store,
                        lifecycle,
                        crash_after="workspace_created",
                    ),
                    store,
                )

            interrupted = store.read_state().facts.git_transaction
            self.assertIsNotNone(interrupted)
            assert interrupted is not None
            self.assertEqual(interrupted.status, "prepared")
            self.assertEqual(
                lifecycle.created,
                {(interrupted.branch, interrupted.worktree_path)},
            )

            recovered = start_new_run(
                self._request(root, store, lifecycle),
                store,
            )

            final_transaction = store.read_state().facts.git_transaction
            self.assertIsNotNone(final_transaction)
            assert final_transaction is not None
            self.assertEqual(final_transaction.status, "reconciled")
            self.assertEqual(recovered.transaction, final_transaction)
            self.assertEqual(
                lifecycle.created,
                {(final_transaction.branch, final_transaction.worktree_path)},
            )

    def test_start_persists_initial_run_head_before_running(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = self._store(root)
            result = start_new_run(
                self._request(root, store, FakeWorkspaceLifecycle()), store
            )
            state = store.read_state()
            self.assertIsNotNone(state.facts.run_head)
            assert state.facts.run_head is not None
            self.assertEqual(state.facts.run_head.revision, result.workspace.run_head_revision)
            self.assertEqual(state.facts.run_head.environment_digest, result.environment.digest)
            self.assertEqual(
                state.facts.run_head.fixture_digest, state.fixture_intent_digest
            )
            self.assertEqual(state.limits.active_version, 1)
            self.assertEqual(state.limits.active.version, state.limits.active_version)
            kinds = [event.kind for event in store.read_events()]
            self.assertLess(kinds.index("environment_sealed"), kinds.index("initial_run_head_recorded"))
            self.assertLess(kinds.index("initial_run_head_recorded"), kinds.index("run_started"))

    def test_enter_running_requires_canonical_run_head(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = self._store(root)
            with self.assertRaises(SimulatedStartCrash):
                start_new_run(
                    self._request(
                        root, store, FakeWorkspaceLifecycle(), crash_after="environment_sealed"
                    ),
                    store,
                )
            with self.assertRaisesRegex(StoreError, "Run Head"):
                store.enter_running(store.read_state().run_id)

    def test_observation_run_head_digest_must_match_canonical_head(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = self._store(root)
            start_new_run(self._request(root, store, FakeWorkspaceLifecycle()), store)
            state = store.read_state()
            observation = Observation(
                observation_id="observation-wrong-head",
                node_id="choose-discipline",
                kind="behavioral",
                observed_state="visible",
                evidence_refs=("artifact",),
                run_head_digest="f" * 64,
            )
            successor = state.model_copy(
                update={
                    "facts": state.facts.model_copy(
                        update={"observations": (observation,)}
                    )
                }
            )
            with self.assertRaisesRegex(StoreError, "current Run Head"):
                store.append_event("observed", event_payload(), successor)

    def test_worktree_preflight_failure_compensates_only_recorded_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = self._store(root)
            lifecycle = FakeWorkspaceLifecycle(fail_environment_preflight=True)

            with self.assertRaisesRegex(EnvironmentPreflightError, "fixture preflight failed"):
                start_new_run(self._request(root, store, lifecycle), store)

            transaction = store.read_state().facts.git_transaction
            self.assertIsNotNone(transaction)
            assert transaction is not None
            self.assertEqual(transaction.status, "compensated")
            self.assertEqual(lifecycle.created, set())
            self.assertEqual(lifecycle.compensated, [transaction.model_copy(update={"status": "reconciled"})])
            self.assertEqual(store.read_state().facts.observations, ())

            lifecycle.fail_environment_preflight = False
            with self.assertRaisesRegex(StartTransactionError, "cannot start"):
                start_new_run(self._request(root, store, lifecycle), store)
            self.assertEqual(lifecycle.created, set())

    def test_workspace_at_wrong_run_head_is_compensated_before_environment_seal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = self._store(root)
            lifecycle = FakeWorkspaceLifecycle(run_head_revision="b" * 40)

            with self.assertRaisesRegex(StartTransactionError, "Run Head"):
                start_new_run(self._request(root, store, lifecycle), store)

            transaction = store.read_state().facts.git_transaction
            self.assertIsNotNone(transaction)
            assert transaction is not None
            self.assertEqual(transaction.status, "compensated")
            self.assertIsNone(store.read_state().facts.environment)
            self.assertEqual(lifecycle.created, set())

    def test_compensation_failure_records_failed_transaction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = self._store(root)
            lifecycle = FakeWorkspaceLifecycle(
                fail_environment_preflight=True,
                fail_compensation=True,
            )

            with self.assertRaisesRegex(
                StartTransactionError, "exact transaction compensation failed"
            ):
                start_new_run(self._request(root, store, lifecycle), store)

            transaction = store.read_state().facts.git_transaction
            self.assertIsNotNone(transaction)
            assert transaction is not None
            self.assertEqual(transaction.status, "failed")
            self.assertEqual(lifecycle.compensated, [])

    def test_worktree_preflight_cannot_replace_host_derived_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = self._store(root)
            lifecycle = FakeWorkspaceLifecycle(
                environment_override=EnvironmentIdentity(
                    repository_revision="b" * 40,
                    runtime="node-24.0.0",
                    package_manager="npm-11.0.0",
                    lockfile_digest="changed-lockfile",
                    host_fingerprint="changed-host",
                )
            )

            with self.assertRaisesRegex(
                StartTransactionError,
                "does not match host-derived identity",
            ):
                start_new_run(self._request(root, store, lifecycle), store)

            transaction = store.read_state().facts.git_transaction
            self.assertIsNotNone(transaction)
            assert transaction is not None
            self.assertEqual(transaction.status, "compensated")
            self.assertIsNone(store.read_state().facts.environment)
            self.assertEqual(lifecycle.created, set())
