from __future__ import annotations

import hashlib
import http.client
import json
import socket
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = PACKAGE_ROOT / "fixtures" / "user_journeys" / "local-system.v1.json"
WORKER_PATH = PACKAGE_ROOT / "fixtures" / "processes" / "local_system_worker.py"


@dataclass(frozen=True, slots=True)
class LocalSystemJourneyResult:
    mode: str
    stop_reason: str | None
    redacted_evidence_refs: tuple[str, ...]
    provider_dispatches: int
    adapter_snapshot_reads: int
    persisted_external_intents: int
    manifest_budget_exhaustions: int
    evidence_redacted: bool


class _FakeProvider:
    """In-process fake. Receipt binds admitted egress; no network is opened."""

    def __init__(self, *, egress_receipt: object) -> None:
        self._egress_receipt = egress_receipt
        self._by_idempotency_key: dict[str, object] = {}
        self.dispatches = 0

    def dispatch(self, intent: object, *, evidence_refs: tuple[str, ...]) -> object:
        from scripts.graph_v5.models import ExternalOperationIntent, ExternalOperationReceipt

        if not isinstance(intent, ExternalOperationIntent):
            raise AssertionError("fake provider requires a sealed operation intent")
        if not getattr(self._egress_receipt, "allowed_hosts", ()):
            raise AssertionError("fake provider requires admitted egress receipt")
        replay = self._by_idempotency_key.get(intent.idempotency_key)
        if replay is not None:
            return replay
        self.dispatches += 1
        receipt = ExternalOperationReceipt(
            receipt_id=f"fake-provider:{intent.operation_id}",
            operation_id=intent.operation_id,
            run_id=intent.run_id,
            manifest_digest=intent.manifest_digest,
            run_head_digest=intent.run_head_digest,
            idempotency_key=intent.idempotency_key,
            status="succeeded",
            evidence_refs=evidence_refs,
        )
        self._by_idempotency_key[intent.idempotency_key] = receipt
        return receipt


class _LoopbackServiceBridge:
    """Bridge exercises real loopback UI/worker/data paths and fake provider only."""

    def __init__(
        self,
        *,
        origin: str,
        namespace: Path,
        lease_token: str,
        snapshot: object,
        fake_provider: _FakeProvider,
    ) -> None:
        self._origin = origin
        self._namespace = namespace
        self._lease_token = lease_token
        self._snapshot = snapshot
        self._fake_provider = fake_provider
        self.snapshot_reads = 0

    def environment_snapshot(self) -> object:
        self.snapshot_reads += 1
        return self._snapshot

    def observe_readonly(self, node: object) -> object:
        from scripts.graph_v5.models import DerivedBehavioralNode, Observation

        if not isinstance(node, DerivedBehavioralNode):
            raise AssertionError("bridge needs sealed node")
        status, payload = self._request("GET", "/ui")
        if status != 200 or payload.get("ui") != "local-system-ready":
            raise AssertionError("loopback UI is unavailable")
        return Observation(
            observation_id=f"local-ui:{node.source_anchor_id}",
            node_id=node.source_anchor_id,
            kind="behavioral",
            observed_state="Local synthetic UI is ready.",
            evidence_refs=("evidence:redacted-ui:local-system",),
            run_head_digest=node.run_head_digest,
        )

    def act(self, node: object, operation_intent: object) -> object:
        from scripts.graph_v5.models import DerivedBehavioralNode, ExternalOperationIntent

        if not isinstance(node, DerivedBehavioralNode):
            raise AssertionError("bridge needs sealed node")
        if not isinstance(operation_intent, ExternalOperationIntent):
            raise AssertionError("bridge needs persisted operation intent")
        status, payload = self._request(
            "POST",
            "/action",
            {
                "action_id": node.node_id,
                "namespace": self._namespace.name,
            },
        )
        if status != 200 or payload.get("worker") != "accepted":
            raise AssertionError("loopback worker rejected synthetic action")
        trace = self._namespace / "worker.trace.jsonl"
        if not trace.is_file():
            raise AssertionError("worker trace was not persisted in disposable namespace")
        state = self._namespace / "state.json"
        if not state.is_file() or json.loads(state.read_text(encoding="utf-8")).get(
            "status"
        ) != "synthetic":
            raise AssertionError("worker data was not persisted in disposable namespace")
        return self._fake_provider.dispatch(
            operation_intent,
            evidence_refs=(
                f"evidence:redacted-ui:{node.node_id}",
                f"evidence:redacted-worker:{node.node_id}",
                f"evidence:redacted-data:{node.node_id}",
                f"evidence:redacted-trace:{node.node_id}",
            ),
        )

    def teardown(self) -> object:
        from datetime import datetime, timezone

        from scripts.graph_v5.models import TeardownReceipt

        return TeardownReceipt(
            service_id="local-system-worker",
            run_id="local-system-run",
            lease_id="bridge-local-system",
            status="not_running",
            process_tree_terminated=False,
            completed_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        host_port = self._origin.removeprefix("http://")
        host, port_text = host_port.rsplit(":", 1)
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        connection = http.client.HTTPConnection(host, int(port_text), timeout=2.0)
        try:
            headers = {"X-Graph-Lease-Token": self._lease_token}
            if body is not None:
                headers["Content-Type"] = "application/json"
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            return response.status, json.loads(response.read().decode("utf-8"))
        finally:
            connection.close()


class LocalSystemJourneyTests(unittest.TestCase):
    """Disposable local-only proof. Test fails if budget gate is removed."""

    def test_local_ui_service_worker_data_and_trace_trajectory(self) -> None:
        """Removing loopback action, namespace data, or redaction must fail this test."""

        result = self.run_local_system_fixture(
            max_user_actions=4,
            provider_budget_micros=1_000_000,
        )

        self.assertEqual("verified", result.mode)
        self.assertTrue(result.redacted_evidence_refs)
        self.assertTrue(all("token" not in ref.casefold() for ref in result.redacted_evidence_refs))
        self.assertTrue(result.evidence_redacted)
        self.assertEqual(4, result.provider_dispatches)

    def test_provider_cap_blocks_before_fifth_dispatch_with_request_headroom(self) -> None:
        """Provider exhaustion writes terminal fact without a fifth intent or dispatch."""

        result = self.run_local_system_fixture(
            max_user_actions=5,
            max_provider_requests=4,
            provider_budget_micros=5,
            max_requests=5,
            requested_actions=5,
        )

        self.assertEqual("blocked", result.mode)
        self.assertEqual("max_provider_requests", result.stop_reason)
        self.assertEqual(4, result.provider_dispatches)
        self.assertEqual(8, result.adapter_snapshot_reads)
        self.assertEqual(4, result.persisted_external_intents)
        self.assertEqual(1, result.manifest_budget_exhaustions)
        self.assertTrue(result.evidence_redacted)

    def run_local_system_fixture(
        self,
        *,
        max_user_actions: int | None = None,
        provider_budget_micros: int = 4,
        max_provider_requests: int | None = None,
        max_requests: int | None = None,
        requested_actions: int | None = None,
    ) -> LocalSystemJourneyResult:
        from datetime import datetime, timezone

        from scripts.graph_v5.adapters.manifest import AdapterManifest
        from scripts.graph_v5.adapters.registry import SERVICE_JOURNEY_INTERFACE_DIGEST
        from scripts.graph_v5.canonical import digest_for
        from scripts.graph_v5.environment import EnvironmentSnapshot
        from scripts.graph_v5.models import (
            AdmittedProviderAuthority,
            BaselineNodeProposal,
            EgressGateReceipt,
            NodeBudgetProposal,
            NodeProposal,
            RealExecutionEnvelope,
            RealSystemRunHead,
            SupervisorAuthorityReceipt,
            V52RunState,
            V52TrajectoryBrief,
            V52TrajectoryConfirmation,
        )
        from scripts.graph_v5.runtime import RealRuntimeController
        from scripts.graph_v5.service_supervisor import DeclaredService, ServiceSupervisor
        from scripts.graph_v5.store import StoreError

        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        requested = requested_actions or max_user_actions or 4
        budget = max_provider_requests or max_user_actions or requested
        user_action_budget = max_user_actions or budget
        request_budget = max_requests or budget
        self.assertEqual("graph-v5.local-system-journey.v1", fixture["schema_version"])
        self.assertEqual("local_isolated", fixture["mode"])

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            namespace = temporary_root / fixture["namespace_prefix"]
            namespace.mkdir()
            run_id = "local-system-run"
            port = self._available_port()
            origin = f"http://127.0.0.1:{port}"
            target_identity_digest = digest_for(
                "local-system-loopback-target",
                {"origin": origin, "fixture": fixture["fixture_id"]},
            )
            manifest = AdapterManifest.model_validate(
                {
                    "schema_version": "graph-v5.adapter-manifest.v1",
                    "manifest_id": fixture["manifest_id"],
                    "adapter_id": "service-journey.v1",
                    "adapter_interface_digest": SERVICE_JOURNEY_INTERFACE_DIGEST,
                    "mode": "local_isolated",
                    "target": {"loopback_origin": origin},
                    "synthetic_scope": {
                        "namespace": namespace.name,
                        "owned_resources": [
                            f"namespace:{namespace.name}",
                            "service:local-system-worker",
                        ],
                    },
                    "capabilities": ["service:fake_provider_action"],
                    "budgets": {
                        "max_user_actions": user_action_budget,
                        "max_provider_requests": budget,
                        "max_cost_micros": provider_budget_micros,
                        "max_requests": request_budget,
                        "max_processes": 1,
                        "max_persistence_writes": request_budget,
                        "max_tokens": 1_000,
                        "max_duration_ms": 60_000,
                    },
                    "secrets": [],
                    "egress": {
                        "hosts": [fixture["fake_provider_host"]],
                        "enforcement_receipt": fixture["egress_enforcement_receipt"],
                    },
                    "evidence": {
                        "redaction_policy_digest": "a" * 64,
                        "allowed_kinds": ["ui", "trace", "persistence_assertion"],
                    },
                    "teardown": {"policy": "manual_only", "max_attempts": 1},
                }
            )
            brief = V52TrajectoryBrief(
                schema_version="graph-v5.trajectory-brief.v2",
                run_id=run_id,
                brief_id="local-system-brief",
                created_at="2026-09-13T00:00:00Z",
                goal="Prove disposable local UI, worker, data, trace, and fake provider traversal.",
                execution_envelope=RealExecutionEnvelope(
                    mode="local_isolated",
                    target_identity_digest=target_identity_digest,
                    adapter_manifest_digest=manifest.digest,
                ),
                adapter_manifest_digest=manifest.digest,
            )
            confirmation = V52TrajectoryConfirmation(
                schema_version="graph-v5.trajectory-confirmation.v2",
                run_id=run_id,
                brief_id=brief.brief_id,
                trajectory_digest=brief.digest,
                adapter_manifest_digest=manifest.digest,
                confirmed_by="user:local-system-test",
                confirmed_at="2026-09-13T00:00:01Z",
                confirmation_evidence_ref="test:explicit-local-system-confirmation",
            )
            state = V52RunState(
                schema_version="graph-v5.run-state.v2",
                run_id=run_id,
                mode="running",
                trajectory=brief,
                confirmation=confirmation,
            )
            namespace_lease = self._issue_lease(run_id, f"namespace:{namespace.name}")
            supervisor = ServiceSupervisor(
                admitted_worktree=temporary_root,
                admitted_fixture_root=PACKAGE_ROOT / "fixtures",
                run_id=run_id,
            )
            port_lease = self._issue_lease(run_id, f"port:{port}")
            worker = DeclaredService(
                service_id="local-system-worker",
                command_kind="python_script",
                argv=(
                    sys.executable,
                    str(WORKER_PATH),
                    "--port",
                    str(port),
                    "--mode",
                    "local_journey",
                    "--namespace",
                    str(namespace),
                    "--lease-token-digest",
                    namespace_lease.ownership_token_digest,
                ),
                cwd=temporary_root,
                port=port,
                readiness_path="/health",
                readiness_timeout_seconds=2.0,
                executable_digest=self._sha256_file(Path(sys.executable)),
                executable_root=Path(sys.executable).parent,
                script_digest=self._sha256_file(WORKER_PATH),
            )
            service = supervisor.start(worker, lease=port_lease)
            self.assertEqual("ready", service.status)
            assert service.health is not None
            service_authority = SupervisorAuthorityReceipt(
                run_id=run_id,
                adapter_manifest_digest=manifest.digest,
                target_identity_digest=target_identity_digest,
                service_receipt=service,
                readiness_receipts=(service.health,),
                lease_ids=(service.port_lease_id, service.process_lease.lease_id),
            )
            egress = EgressGateReceipt(
                run_id=run_id,
                adapter_manifest_digest=manifest.digest,
                target_identity_digest=target_identity_digest,
                allowed_hosts=manifest.egress.hosts,
                allowed_protocols=("https",),
                issued_receipt_digest=digest_for(
                    "egress-enforcement-receipt", manifest.egress.enforcement_receipt
                ),
            )
            snapshot = EnvironmentSnapshot.from_admitted_authority(
                manifest=manifest,
                target_identity_digest=target_identity_digest,
                supervisor_receipts=(service_authority,),
                egress_receipt=egress,
            )
            run_head = RealSystemRunHead(
                run_id=run_id,
                manifest_digest=manifest.digest,
                environment_snapshot_digest=snapshot.digest,
            )
            baseline = tuple(
                BaselineNodeProposal(
                    proposal=NodeProposal(
                        node_id=f"local-provider-action-{index}",
                        source_anchor_id="local-ui",
                        target_landmark_id=f"local-provider-landmark-{index}",
                        action_kind="act",
                        action_or_probe="Send synthetic loopback provider action",
                        expected_before=("Local synthetic UI is ready.",),
                        expected_after=("Synthetic provider result is recorded.",),
                        derivation_reason="Local fixture exposes one sealed fake-provider action.",
                        authority_refs=("fixture:local-system",),
                        execution_scope=f"namespace:{namespace.name}",
                        side_effect="service:fake_provider_action",
                        target_systems=("127.0.0.1",),
                    ),
                    entry_observation_refs=(f"evidence:redacted-ui:entry-{index}",),
                    budget=NodeBudgetProposal(
                        max_user_actions=1,
                        max_provider_requests=1,
                        max_cost_micros=1,
                        max_requests=1,
                        max_bytes=1_024,
                        max_wall_seconds=10,
                    ),
                )
                for index in range(1, requested + 1)
            )
            nodes = tuple(
                self._seal_baseline_node(
                    item,
                    state=state,
                    run_head=run_head,
                )
                for item in baseline
            )
            runtime = RealRuntimeController._start_admitted(
                root=temporary_root / "run-store",
                initial_state=state,
                manifest=manifest,
                baseline_nodes=nodes,
                baseline_proposals=baseline,
                provider_authority=AdmittedProviderAuthority(
                    schema_version="graph-v5.admitted-provider-authority.v1",
                    adapter_id=manifest.adapter_id,
                    provider_id="service-host-provider.v1",
                    source_identity_digest=target_identity_digest,
                ),
                supervisor_receipts=(service_authority,),
                egress_receipt=egress,
            )
            runtime._store.record_resource_lease(namespace_lease)
            fake_provider = _FakeProvider(egress_receipt=egress)
            bridge = _LoopbackServiceBridge(
                origin=origin,
                namespace=namespace,
                lease_token=namespace_lease.issued_ownership_token,
                snapshot=snapshot,
                fake_provider=fake_provider,
            )
            adapter = runtime._construct_adapter_for_test(service_bridge=bridge)
            stop_reason = None
            try:
                for _ in range(requested):
                    authority = runtime._store.next_executable_authority()
                    assert authority is not None
                    intent = runtime._derive_persisted_operation_intent(authority)
                    try:
                        runtime._run_bounded_slice_for_test(
                            adapter=adapter,
                            node=authority.node,
                            operation_intent=intent,
                        )
                    except StoreError as exc:
                        if "budget reservation exceeds admitted" not in str(exc):
                            raise
                        stop_reason = "budget_exhausted"
                        break
                exhaustions = runtime.state.facts.manifest_budget_exhaustions
                if exhaustions:
                    stop_reason = exhaustions[-1].exhausted_budget_names[0]
                    mode = runtime.state.mode
                elif stop_reason is None:
                    replay = runtime._final_replay_for_test(adapter)
                    if replay.stop_reason is not None:
                        self.fail(replay.stop_reason)
                    mode = "verified"
                else:
                    mode = "paused"
            finally:
                teardown = supervisor.teardown(
                    port_lease,
                    ownership_token=port_lease.issued_ownership_token,
                )
                self.assertEqual("terminated", teardown.status)
            token = namespace_lease.issued_ownership_token
            evidence_refs = tuple(
                reference
                for receipt in runtime.state.facts.external_operation_receipts
                for reference in receipt.evidence_refs
            )
            return LocalSystemJourneyResult(
                mode=mode,
                stop_reason=stop_reason,
                redacted_evidence_refs=evidence_refs,
                provider_dispatches=fake_provider.dispatches,
                adapter_snapshot_reads=bridge.snapshot_reads,
                persisted_external_intents=len(runtime.state.facts.external_operation_intents),
                manifest_budget_exhaustions=len(
                    runtime.state.facts.manifest_budget_exhaustions
                ),
                evidence_redacted=(
                    token not in "\n".join(evidence_refs)
                    and not self._tree_contains(temporary_root, token)
                ),
            )

    @staticmethod
    def _seal_baseline_node(
        baseline: object,
        *,
        state: object,
        run_head: object,
    ) -> object:
        from scripts.graph_v5.admission import RealAdmissionCoordinator

        return RealAdmissionCoordinator._seal_baseline_node(
            baseline,  # type: ignore[arg-type]
            state=state,  # type: ignore[arg-type]
            run_head=run_head,  # type: ignore[arg-type]
        )

    @staticmethod
    def _issue_lease(run_id: str, resource: str) -> object:
        from scripts.graph_v5.models import ResourceLease

        return ResourceLease.issue(run_id=run_id, resource=resource)

    @staticmethod
    def _available_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            return int(listener.getsockname()[1])

    @staticmethod
    def _sha256_file(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _tree_contains(root: Path, value: str) -> bool:
        return any(
            value in candidate.read_text(encoding="utf-8", errors="ignore")
            for candidate in root.rglob("*")
            if candidate.is_file()
        )


if __name__ == "__main__":
    unittest.main()
