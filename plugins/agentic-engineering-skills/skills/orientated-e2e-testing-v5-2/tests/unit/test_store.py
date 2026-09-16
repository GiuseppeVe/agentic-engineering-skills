from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from scripts.graph_v5.models import (
    BootstrapIntent,
    EnvironmentIdentity,
    FactIndex,
    GitTransaction,
    HostPreflightReceipt,
    RunHead,
    RunState,
    StrictModel,
    VersionedLimits,
    load_run_limits_profile,
)
from scripts.graph_v5.store import (
    CapabilityError,
    SimulatedCrash,
    StoreCapability,
    StoreError,
    TransactionalRunStore,
)
from tests.support.trajectory import valid_trajectory_brief


class TestEventFactReference(StrictModel):
    fact_id: str
    fact_digest: str


class IncompleteHostPreflightReceipt(StrictModel):
    transaction_id: str


def event_payload() -> TestEventFactReference:
    return TestEventFactReference(fact_id="environment", fact_digest="e" * 64)


def issue_capability(root: Path, run_id: str) -> StoreCapability:
    issuer = getattr(StoreCapability, "_issue_for_runtime", StoreCapability.issue)
    return issuer(root, run_id)


def sample_state() -> RunState:
    limits = load_run_limits_profile(
        Path(__file__).resolve().parents[2]
        / "config"
        / "policy-fixtures"
        / "run-limits.test.v1.json"
    )
    trajectory = valid_trajectory_brief().model_copy(update={"run_id": "run-test-001"})
    return RunState(
        schema_version="v5",
        run_id="run-test-001",
        mode="boot",
        trajectory=trajectory,
        facts=FactIndex(),
        limits=VersionedLimits(
            versions=(limits,),
            active_version=1,
        ),
    )


class TransactionalRunStoreTests(unittest.TestCase):
    def test_preconfirmation_noop_requires_exact_pristine_boot_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            state = sample_state()
            intent = BootstrapIntent(
                run_id=state.run_id,
                transaction_id="preconfirmation-dirty-boot",
                requested_base_revision="a" * 40,
                candidate_branch="graph-run/preconfirmation-dirty-boot",
                candidate_worktree_path=str(root.parent / "worktree"),
                compensation_plan=("remove-exact-worktree", "delete-exact-branch"),
            )
            dirty = state.model_copy(
                update={
                    "facts": state.facts.model_copy(update={"bootstrap_intent": intent})
                }
            )
            store = TransactionalRunStore.open(root, issue_capability(root, state.run_id))
            store.initialize(dirty)

            with self.assertRaisesRegex(StoreError, "pre-confirmation"):
                store.append_event("observed", event_payload(), dirty)

    def test_preconfirmation_store_cannot_project_runtime_status(self) -> None:
        from scripts.graph_v5.runtime import RuntimeController

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            state = sample_state()
            store = TransactionalRunStore.open(root, issue_capability(root, state.run_id))
            store.initialize(state)

            with self.assertRaisesRegex(StoreError, "confirmed trajectory binding"):
                RuntimeController.read_only_status(root=root, run_id=state.run_id)

    def test_host_preflight_receipt_rejects_runtime_and_package_manager_contradiction(self) -> None:
        with self.assertRaisesRegex(ValidationError, "runtime"):
            HostPreflightReceipt(
                transaction_id="transaction-test",
                repository_root="C:\\repository",
                repository_revision="a" * 40,
                requested_base_revision="a" * 40,
                candidate_worktree_path="C:\\worktree",
                durable_store_root="C:\\store",
                required_node_major=22,
                node_executable="C:\\node.exe",
                node_version="22.12.0",
                npm_executable="C:\\npm.cmd",
                npm_version="10.9.0",
                package_manager="npm",
                lockfile_path="C:\\repository\\package-lock.json",
                lockfile_digest="b" * 64,
                projected_path_length=200,
                path_reserve_chars=32,
                long_paths_enabled=True,
                git_filemode="false",
                host_fingerprint="c" * 64,
                environment=EnvironmentIdentity(
                    repository_revision="a" * 40,
                    runtime="node-24.0.0",
                    package_manager="npm-11.0.0",
                    lockfile_digest="b" * 64,
                    host_fingerprint="c" * 64,
                ),
            )

    def test_run_started_requires_existing_typed_run_head_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            state = sample_state()
            run_head = RunHead(
                revision="a" * 40,
                environment_digest="e" * 64,
                fixture_digest=state.fixture_intent_digest,
            )
            state = state.model_copy(
                update={"facts": state.facts.model_copy(update={"run_head": run_head})}
            )
            store = TransactionalRunStore.open(root, issue_capability(root, state.run_id))
            store.initialize(state)

            with self.assertRaisesRegex(StoreError, "artifact"):
                store.append_event(
                    "run_started",
                    TestEventFactReference(
                        fact_id=run_head.digest,
                        fact_digest="f" * 64,
                    ),
                    state.with_mode("running"),
                )

    def test_run_started_cannot_append_a_limits_widening(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            state = sample_state()
            run_head = RunHead(
                revision="a" * 40,
                environment_digest="e" * 64,
                fixture_digest=state.fixture_intent_digest,
            )
            state = state.model_copy(
                update={"facts": state.facts.model_copy(update={"run_head": run_head})}
            )
            store = TransactionalRunStore.open(root, issue_capability(root, state.run_id))
            store.initialize(state)
            artifact = store.put_artifact("run-head", run_head)
            old_limit = state.limits.active.value_for("causal_radius")
            widened = state.limits.append_widening(
                name="causal_radius",
                amount=old_limit.amount + 1,
                approver="test",
                reason="test-only widening",
                effective_graph_revision=0,
            )
            successor = state.model_copy(
                update={"mode": "running", "limits": widened}
            )

            with self.assertRaisesRegex(StoreError, "run_started"):
                store.append_event(
                    "run_started",
                    TestEventFactReference(
                        fact_id=run_head.digest,
                        fact_digest=artifact.digest,
                    ),
                    successor,
                )

    def test_host_preflight_receipt_must_satisfy_strict_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            state = sample_state()
            store = TransactionalRunStore.open(root, issue_capability(root, state.run_id))
            store.initialize(state)
            intent = BootstrapIntent(
                run_id=state.run_id,
                transaction_id="transaction-test",
                requested_base_revision="a" * 40,
                candidate_branch="graph-run/run-test-001",
                candidate_worktree_path=str(root.parent / "worktree"),
                compensation_plan=("remove-exact-worktree", "delete-exact-branch"),
            )
            store.record_bootstrap_intent(intent)

            with self.assertRaisesRegex(StoreError, "host preflight"):
                store.record_host_preflight(
                    intent,
                    IncompleteHostPreflightReceipt(transaction_id=intent.transaction_id),
                )

    def test_git_transaction_requires_durable_host_preflight_event(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            state = sample_state()
            store = TransactionalRunStore.open(root, issue_capability(root, state.run_id))
            store.initialize(state)
            intent = BootstrapIntent(
                run_id=state.run_id,
                transaction_id="transaction-test",
                requested_base_revision="a" * 40,
                candidate_branch="graph-run/run-test-001",
                candidate_worktree_path=str(root.parent / "worktree"),
                compensation_plan=("remove-exact-worktree", "delete-exact-branch"),
            )
            store.record_bootstrap_intent(intent)
            transaction = GitTransaction(
                transaction_id=intent.transaction_id,
                requested_base_revision=intent.requested_base_revision,
                branch=intent.candidate_branch,
                worktree_path=intent.candidate_worktree_path,
                status="prepared",
            )
            with self.assertRaisesRegex(StoreError, "host preflight"):
                store.record_git_transaction(transaction)

    def test_non_task4_event_cannot_change_protected_start_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            state = sample_state()
            store = TransactionalRunStore.open(root, issue_capability(root, state.run_id))
            store.initialize(state)
            with self.assertRaisesRegex(StoreError, "protected start state"):
                store.append_event("observed", event_payload(), state.with_mode("running"))

    def test_task4_event_kinds_reject_unrelated_state_delta(self) -> None:
        cases = (
            "bootstrap_intended",
            "host_preflighted",
            "git_transaction_recorded",
            "environment_sealed",
            "initial_run_head_recorded",
            "run_started",
        )
        for kind in cases:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "store"
                state = sample_state()
                store = TransactionalRunStore.open(
                    root, issue_capability(root, state.run_id)
                )
                store.initialize(state)
                with self.assertRaisesRegex(StoreError, "event transition"):
                    store.append_event(kind, event_payload(), state.with_mode("running"))

    def test_appends_hash_chained_event_and_preserves_canonical_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            state = sample_state()
            store = TransactionalRunStore.open(root, issue_capability(root, state.run_id))
            store.initialize(state)
            running = state

            event = store.append_event(
                "observed",
                event_payload(),
                running,
            )

            self.assertEqual(event.sequence, 1)
            self.assertEqual(event.previous_digest, "0" * 64)
            self.assertEqual(store.read_state().mode, "boot")
            self.assertEqual(store.read_events()[0].event_digest, event.event_digest)

    def test_recovers_interrupted_journal_without_losing_event_or_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            state = sample_state()
            capability = issue_capability(root, state.run_id)
            store = TransactionalRunStore.open(root, capability)
            store.initialize(state)

            with self.assertRaises(SimulatedCrash):
                store.append_event(
                    "observed",
                    event_payload(),
                    state,
                    interrupt_after="state_replaced",
                )

            recovered = TransactionalRunStore.open(root, capability)
            self.assertEqual(recovered.read_state().mode, "boot")
            self.assertEqual(len(recovered.read_events()), 1)
            self.assertFalse((root / "journal.json").exists())

    def test_artifact_address_prevents_mutation_of_prior_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            state = sample_state()
            store = TransactionalRunStore.open(root, issue_capability(root, state.run_id))
            store.initialize(state)

            artifact = store.put_artifact("proof", {"result": "red", "exit_code": 1})
            artifact_path = root / "artifacts" / f"{artifact.digest}.json"

            self.assertTrue(artifact_path.exists())
            self.assertEqual(
                store.read_artifact("proof", artifact.digest),
                {"exit_code": 1, "result": "red"},
            )
            with self.assertRaises(StoreError):
                store.put_artifact_at_digest(
                    "proof", artifact.digest, b'{"tampered":true}'
                )

    def test_rejects_capability_for_another_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            store = TransactionalRunStore.open(
                root, issue_capability(root, "other-run")
            )

            with self.assertRaises(CapabilityError):
                store.initialize(sample_state())

    def test_public_caller_cannot_issue_store_capability(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(CapabilityError):
                StoreCapability.issue(Path(temporary) / "store", "run-test-001")

    def test_rejects_dictionary_event_payload_before_state_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "store"
            state = sample_state()
            store = TransactionalRunStore.open(
                root, issue_capability(root, state.run_id)
            )
            store.initialize(state)
            before = (root / "state.json").read_bytes()

            with self.assertRaises(StoreError):
                store.append_event(
                    "observed",
                    {"environment_digest": "env-sha256"},
                    state.with_mode("running"),
                )

            self.assertEqual((root / "state.json").read_bytes(), before)
            self.assertFalse((root / "ledger.jsonl").exists())
