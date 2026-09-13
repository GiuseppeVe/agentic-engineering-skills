"""Confirmed Trajectory genesis must precede every writable start effect."""

from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.graph_v5.models import FactIndex, RunState, VersionedLimits, load_run_limits_profile
from scripts.graph_v5.runtime import RuntimeController
from scripts.graph_v5.store import SimulatedCrash, StoreCapability, StoreError, TransactionalRunStore
from scripts.graph_v5.trajectory import TrajectoryValidationError, validate_confirmed_trajectory
from scripts.graph_v5.environment import HostPreflightConfig, SimulatedStartCrash, StartRequest
from tests.integration.test_start_transaction import (
    FakeWorkspaceLifecycle,
    FixtureHostProbe,
    _profile,
    _repository,
)
from tests.support.trajectory import confirmation_for, valid_trajectory_brief


CONFIRMATION_WRITE_BOUNDARIES = (
    "journal_written",
    "trajectory_artifact_written",
    "markdown_artifact_written",
    "confirmation_artifact_written",
    "binding_artifact_written",
    "state_replaced",
    "ledger_appended",
)


def _limits() -> VersionedLimits:
    profile = load_run_limits_profile(
        Path(__file__).resolve().parents[2]
        / "config"
        / "policy-fixtures"
        / "run-limits.test.v1.json"
    )
    return VersionedLimits(versions=(profile,), active_version=1)


def _bundle():
    brief = valid_trajectory_brief()
    from scripts.graph_v5.trajectory import render_trajectory_markdown

    return validate_confirmed_trajectory(
        brief,
        render_trajectory_markdown(brief),
        confirmation_for(brief),
    )


def _state() -> RunState:
    brief = valid_trajectory_brief()
    return RunState(
        schema_version="v5",
        run_id=brief.run_id,
        mode="boot",
        trajectory=brief,
        facts=FactIndex(),
        limits=_limits(),
    )


class ConfirmedTrajectoryIntakeTests(unittest.TestCase):
    def test_start_rejects_missing_or_mismatched_confirmation_before_any_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run-store"
            before = _snapshot(root)
            parameters = inspect.signature(RuntimeController.start).parameters
            self.assertIn("confirmed", parameters)

            with self.assertRaises(TrajectoryValidationError):
                RuntimeController.start(
                    root=root,
                    confirmed=valid_trajectory_brief(),
                    limits=_limits(),
                    request=object(),
                )

            self.assertEqual(_snapshot(root), before)

    def test_atomic_confirmation_failure_leaves_no_run_store(self) -> None:
        for boundary in CONFIRMATION_WRITE_BOUNDARIES:
            with self.subTest(boundary=boundary), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "run-store"
                store = TransactionalRunStore.open(
                    root,
                    StoreCapability._issue_for_runtime(root, _state().run_id),
                )
                initializer = getattr(store, "initialize_confirmed_run", None)
                self.assertIsNotNone(initializer, "confirmed genesis API is required")

                with self.assertRaises(SimulatedCrash):
                    initializer(_state(), confirmed=_bundle(), interrupt_after=boundary)

                self.assertFalse(root.exists())

    def test_atomic_confirmation_write_then_error_restores_exact_existing_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run-store"
            root.mkdir()
            marker = root / "operator-marker.txt"
            marker.write_bytes(b"preserve-exactly\n")
            before = _snapshot(root)
            state = _state()
            store = TransactionalRunStore.open_for_confirmed_genesis(
                root, state.run_id
            )
            real_append = store._append_bytes

            def append_then_fail(path: Path, payload: bytes) -> None:
                real_append(path, payload[: len(payload) // 2])
                raise OSError("injected write-then-error")

            with (
                patch.object(store, "_append_bytes", append_then_fail),
                self.assertRaisesRegex(OSError, "injected write-then-error"),
            ):
                store.initialize_confirmed_run(state, confirmed=_bundle())

            self.assertEqual(_snapshot(root), before)

    def test_interrupted_process_recovery_rolls_back_confirmed_genesis(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run-store"
            state = _state()
            capability = StoreCapability._issue_for_runtime(root, state.run_id)
            store = TransactionalRunStore.open_for_confirmed_genesis(
                root, state.run_id
            )
            real_write = store._write_artifact_record_unlocked

            def write_then_terminate(record) -> None:
                real_write(record)
                raise KeyboardInterrupt("injected process interruption")

            with (
                patch.object(
                    store,
                    "_write_artifact_record_unlocked",
                    write_then_terminate,
                ),
                self.assertRaisesRegex(
                    KeyboardInterrupt, "injected process interruption"
                ),
            ):
                store.initialize_confirmed_run(state, confirmed=_bundle())

            self.assertTrue((root / "journal.json").exists())
            TransactionalRunStore.open(root, capability)
            self.assertFalse(root.exists())

    def test_confirmed_genesis_is_first_event_before_bootstrap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run-store"
            store = TransactionalRunStore.open(
                root,
                StoreCapability._issue_for_runtime(root, _state().run_id),
            )
            initializer = getattr(store, "initialize_confirmed_run", None)
            self.assertIsNotNone(initializer, "confirmed genesis API is required")
            initializer(_state(), confirmed=_bundle())

            from scripts.graph_v5.models import BootstrapIntent

            intent = BootstrapIntent(
                run_id=_state().run_id,
                transaction_id="transaction-trajectory-v1",
                requested_base_revision="a" * 40,
                candidate_branch="graph-run/run-trajectory-v1",
                candidate_worktree_path=str(root.parent / "worktree"),
                compensation_plan=("remove-exact-worktree", "delete-exact-branch"),
            )
            store.record_bootstrap_intent(intent)

            self.assertEqual(
                tuple(event.kind for event in store.read_events()),
                ("trajectory_confirmed", "bootstrap_intended"),
            )

    def test_runtime_start_records_confirmed_genesis_before_git_preparation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store_root = root / "run-store"
            lifecycle = FakeWorkspaceLifecycle()
            request = StartRequest(
                repository_root=_repository(root),
                requested_base_revision="a" * 40,
                candidate_branch="graph-run/run-trajectory-v1",
                candidate_worktree_path=root / "runs" / "run-trajectory-v1",
                durable_store_root=store_root,
                host_config=HostPreflightConfig(
                    path_reserve_chars=32, volatile_environment_roots=()
                ),
                host_probe=FixtureHostProbe(_profile()),
                workspace_lifecycle=lifecycle,
                crash_after="git_transaction",
            )

            with self.assertRaises(SimulatedStartCrash):
                RuntimeController.start(
                    root=store_root,
                    confirmed=_bundle(),
                    limits=_limits(),
                    request=request,
                )

            events = RuntimeController.open(
                root=store_root, run_id=_bundle().brief.run_id
            )._store.read_events()
            self.assertEqual(
                tuple(event.kind for event in events),
                (
                    "trajectory_confirmed",
                    "bootstrap_intended",
                    "host_preflighted",
                    "git_transaction_recorded",
                ),
            )
            self.assertEqual(lifecycle.created, set())

    def test_resume_loads_confirmed_trajectory_without_intake(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run-store"
            state = _state()
            store = TransactionalRunStore.open(
                root,
                StoreCapability._issue_for_runtime(root, state.run_id),
            )
            initializer = getattr(store, "initialize_confirmed_run", None)
            self.assertIsNotNone(initializer, "confirmed genesis API is required")
            binding = initializer(state, confirmed=_bundle())

            resumed = RuntimeController.open(root=root, run_id=state.run_id)
            self.assertEqual(resumed.state.trajectory_digest, binding.trajectory_digest)
            self.assertEqual(resumed.state.trajectory.digest, _bundle().brief.digest)

    def test_resume_rejects_tampered_confirmed_trajectory_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run-store"
            state = _state()
            store = TransactionalRunStore.open(
                root,
                StoreCapability._issue_for_runtime(root, state.run_id),
            )
            binding = store.initialize_confirmed_run(state, confirmed=_bundle())
            markdown_path = root / "artifacts" / f"{binding.markdown_digest}.json"
            markdown_path.write_bytes(b"tampered\n")

            with self.assertRaisesRegex(StoreError, "stored confirmed trajectory artifacts"):
                RuntimeController.open(root=root, run_id=state.run_id)

    def test_resume_rejects_state_without_confirmed_trajectory_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "run-store"
            state = _state()
            store = TransactionalRunStore.open(
                root,
                StoreCapability._issue_for_runtime(root, state.run_id),
            )
            store.initialize(state)

            with self.assertRaisesRegex(StoreError, "confirmed trajectory binding"):
                RuntimeController.open(root=root, run_id=state.run_id)


def _snapshot(root: Path) -> dict[str, bytes]:
    if not root.exists():
        return {}
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


if __name__ == "__main__":
    unittest.main()
