from __future__ import annotations

import json
import unittest
from pathlib import Path

from pydantic import ValidationError

from scripts.graph_v5.canonical import digest_for
from scripts.graph_v5.models import (
    BaselineNodeProposal,
    BaselineSpineAuthority,
    BudgetReservation,
    DerivedBehavioralNode,
    EnvironmentIdentity,
    ExplorationDelta,
    ExternalOperationIntent,
    ExternalOperationReceipt,
    ExecutionEnvelope,
    LimitValue,
    HealthReceipt,
    NodeProposal,
    NodeBudgetProposal,
    PendingRealSystemDecision,
    RealExecutionEnvelope,
    RealSystemDecision,
    ResourceLease,
    RuntimeNote,
    ServiceReceipt,
    SupervisorAuthorityReceipt,
    V52TrajectoryBrief,
    V52TrajectoryConfirmation,
    V52RunState,
    RunLimits,
    RunState,
    TrajectoryBrief,
    VersionedLimits,
    legacy_run_immutable_projection,
    load_run_limits_profile,
)
from tests.support.trajectory import valid_trajectory_brief, valid_trajectory_payload


def valid_limits() -> VersionedLimits:
    profile = load_run_limits_profile(
        Path(__file__).resolve().parents[2]
        / "config"
        / "policy-fixtures"
        / "run-limits.test.v1.json"
    )
    return VersionedLimits(
        versions=(profile,),
        active_version=1,
    )


class TrajectoryModelTests(unittest.TestCase):
    def test_trajectory_brief_is_frozen(self) -> None:
        brief = valid_trajectory_brief()

        with self.assertRaises(ValidationError):
            brief.goal = "Mutated authority"  # type: ignore[misc]

    def test_execution_envelope_rejects_external_effects(self) -> None:
        payload = valid_trajectory_payload()
        payload["execution_envelope"]["allowed_side_effects"] = ["external:payment"]

        with self.assertRaises(ValidationError):
            TrajectoryBrief.model_validate(payload)


class RealTrajectoryAuthorityTests(unittest.TestCase):
    def test_real_execution_envelope_requires_matching_manifest_digest(self) -> None:
        with self.assertRaisesRegex(ValidationError, "adapter_manifest_digest"):
            RealExecutionEnvelope.model_validate(
                {
                    "mode": "remote_nonprod",
                    "target_identity_digest": "a" * 64,
                    "adapter_manifest_digest": None,
                }
            )

    def test_v52_confirmation_binds_real_brief_and_manifest(self) -> None:
        envelope = RealExecutionEnvelope(
            mode="remote_nonprod",
            target_identity_digest="a" * 64,
            adapter_manifest_digest="b" * 64,
        )
        brief = V52TrajectoryBrief(
            schema_version="graph-v5.trajectory-brief.v2",
            run_id="run-real-v2",
            brief_id="brief-real-v2",
            created_at="2026-09-09T09:30:00Z",
            goal="Verify synthetic non-production journey.",
            execution_envelope=envelope,
            adapter_manifest_digest="b" * 64,
        )
        confirmation = V52TrajectoryConfirmation(
            schema_version="graph-v5.trajectory-confirmation.v2",
            run_id=brief.run_id,
            brief_id=brief.brief_id,
            trajectory_digest=brief.digest,
            adapter_manifest_digest=brief.adapter_manifest_digest,
            confirmed_by="user:aleda",
            confirmed_at="2026-09-09T09:31:00Z",
            confirmation_evidence_ref="conversation:explicit-confirmation:2",
        )
        state = V52RunState(
            schema_version="graph-v5.run-state.v2",
            run_id=brief.run_id,
            mode="boot",
            trajectory=brief,
            confirmation=confirmation,
        )
        self.assertEqual(state.adapter_manifest_digest, "b" * 64)

    def test_v5_store_projects_as_immutable_legacy_run(self) -> None:
        projection = legacy_run_immutable_projection({"schema_version": "v5", "run_id": "legacy-run"})
        self.assertEqual(projection.status, "legacy_run_immutable")
        self.assertEqual(projection.run_id, "legacy-run")


class ExplorationAuthorityModelTests(unittest.TestCase):
    @staticmethod
    def _proposal(
        node_id: str,
    ) -> NodeProposal:
        return NodeProposal(
            node_id=node_id,
            source_anchor_id="start",
            target_landmark_id="checkout",
            action_kind="act",
            action_or_probe="Submit synthetic checkout form",
            expected_before=("Synthetic checkout form is visible",),
            expected_after=("Synthetic checkout result is visible",),
            derivation_reason="Confirmed checkout trajectory",
            authority_refs=("trajectory:checkout",),
            execution_scope="synthetic checkout fixture",
            side_effect="bridge:act",
            target_systems=("service.example.test",),
        )

    @classmethod
    def _node(
        cls,
        node_id: str,
        *,
        run_head_digest: str = "b" * 64,
    ) -> DerivedBehavioralNode:
        return DerivedBehavioralNode.seal(
            cls._proposal(node_id),
            entry_observation_refs=("observation:checkout-entry",),
            run_id="run-real-v2",
            trajectory_digest="c" * 64,
            run_head_digest=run_head_digest,
            execution_envelope_digest="d" * 64,
        )

    @classmethod
    def _baseline_proposal(cls, node_id: str) -> BaselineNodeProposal:
        return BaselineNodeProposal(
            proposal=cls._proposal(node_id),
            entry_observation_refs=("observation:checkout-entry",),
            budget=NodeBudgetProposal(
                max_user_actions=1,
                max_provider_requests=1,
                max_cost_micros=1,
                max_requests=1,
                max_bytes=1_024,
                max_wall_seconds=10,
            ),
        )

    def _baseline(self) -> BaselineSpineAuthority:
        node = self._node("baseline-checkout")
        proposal = self._baseline_proposal("baseline-checkout")
        return BaselineSpineAuthority(
            schema_version="graph-v5.baseline-spine-authority.v1",
            run_id="run-real-v2",
            run_head_digest="b" * 64,
            adapter_manifest_digest="a" * 64,
            environment_snapshot_digest="e" * 64,
            nodes=(node,),
            node_digests=(node.digest,),
            baseline_proposals=(proposal,),
            proposal_digests=(proposal.proposal_digest,),
            budget_digests=(proposal.budget_digest,),
        )

    def test_exploration_delta_requires_parent_evidence_and_exact_real_authority(self) -> None:
        baseline = self._baseline()

        with self.assertRaisesRegex(ValidationError, "evidence"):
            ExplorationDelta.from_node(
                node=self._node("explore-coupon"),
                parent_node_id="baseline-checkout",
                evidence_refs=(),
                authority=baseline,
            )

    def test_exploration_delta_accepts_exact_earlier_delta_as_parent_authority(self) -> None:
        baseline = self._baseline()
        first = ExplorationDelta.from_node(
            node=self._node("explore-coupon"),
            parent_node_id="baseline-checkout",
            evidence_refs=("observation:checkout-copy",),
            authority=baseline,
            proposal=self._baseline_proposal("explore-coupon"),
        )

        second = ExplorationDelta.from_node(
            node=self._node("explore-shipping"),
            parent_node_id=first.node.node_id,
            evidence_refs=("observation:shipping-copy",),
            authority=first,
            proposal=self._baseline_proposal("explore-shipping"),
        )

        self.assertEqual(second.parent_node_id, first.node.node_id)
        self.assertEqual(second.run_head_digest, baseline.run_head_digest)

        with self.assertRaisesRegex(ValidationError, "run head"):
            ExplorationDelta.from_node(
                node=self._node("explore-coupon", run_head_digest="f" * 64),
                parent_node_id="baseline-checkout",
                evidence_refs=("observation:checkout-copy",),
                authority=baseline,
                proposal=self._baseline_proposal("explore-coupon"),
            )


class ResourceLeaseTests(unittest.TestCase):
    def test_lease_persists_only_token_digest_and_rechecks_ownership_after_reload(self) -> None:
        lease = ResourceLease.issue(
            run_id="run-real-v2",
            resource="port:4317",
        )
        token = lease.issued_ownership_token

        self.assertTrue(lease.ownership_matches(token))
        self.assertFalse(lease.ownership_matches("wrong-token"))
        self.assertNotIn(token, lease.model_dump_json())
        reloaded = ResourceLease.model_validate(lease.model_dump(mode="python"))
        self.assertTrue(reloaded.ownership_matches(token))
        with self.assertRaisesRegex(ValueError, "unavailable"):
            _ = reloaded.issued_ownership_token


class SupervisorAuthorityReceiptTests(unittest.TestCase):
    @staticmethod
    def _ready_service() -> tuple[ResourceLease, ResourceLease, HealthReceipt, ServiceReceipt]:
        port_lease = ResourceLease.issue(run_id="run-real-v2", resource="port:4317")
        process_lease = ResourceLease.issue(run_id="run-real-v2", resource="process:4242")
        health = HealthReceipt(
            service_id="checkout",
            lease_id=port_lease.lease_id,
            endpoint="http://127.0.0.1:4317/health",
            status_code=204,
            checked_at="2026-09-09T09:31:00Z",
        )
        service = ServiceReceipt(
            service_id="checkout",
            run_id="run-real-v2",
            lease_id=port_lease.lease_id,
            port_lease_id=port_lease.lease_id,
            process_lease=process_lease,
            port=4317,
            process_id=4242,
            status="ready",
            process_tree_terminated=False,
            started_at="2026-09-09T09:30:00Z",
            health=health,
        )
        return port_lease, process_lease, health, service

    def test_wraps_real_ready_supervisor_receipt_with_distinct_owned_leases(self) -> None:
        port_lease, process_lease, health, service = self._ready_service()

        receipt = SupervisorAuthorityReceipt(
            run_id=service.run_id,
            adapter_manifest_digest="a" * 64,
            target_identity_digest="b" * 64,
            service_receipt=service,
            readiness_receipts=(health,),
            lease_ids=(port_lease.lease_id, process_lease.lease_id),
        )

        self.assertEqual(receipt.lease_ids, (port_lease.lease_id, process_lease.lease_id))

    def test_rejects_forged_ready_service_without_live_process_or_healthy_receipt(self) -> None:
        port_lease, _, health, service = self._ready_service()
        forged_service = service.model_copy(
            update={
                "process_id": None,
                "process_lease": None,
                "process_tree_terminated": True,
                "health": None,
            }
        )
        forged_health = health.model_copy(update={"status_code": None})

        with self.assertRaisesRegex(ValidationError, "ready|process|health"):
            SupervisorAuthorityReceipt(
                run_id=service.run_id,
                adapter_manifest_digest="a" * 64,
                target_identity_digest="b" * 64,
                service_receipt=forged_service,
                readiness_receipts=(forged_health,),
                lease_ids=(port_lease.lease_id,),
            )

    def test_rejects_split_port_lease_or_wrong_readiness_endpoint(self) -> None:
        port_lease, process_lease, health, service = self._ready_service()
        split_service = service.model_copy(update={"lease_id": "lease-forged-service"})

        with self.assertRaisesRegex(ValidationError, "port lease|service lease"):
            SupervisorAuthorityReceipt(
                run_id=service.run_id,
                adapter_manifest_digest="a" * 64,
                target_identity_digest="b" * 64,
                service_receipt=split_service,
                readiness_receipts=(health,),
                lease_ids=(
                    split_service.lease_id,
                    port_lease.lease_id,
                    process_lease.lease_id,
                ),
            )

        wrong_endpoint = health.model_copy(
            update={"endpoint": "http://127.0.0.1:4318/health"}
        )
        wrong_endpoint_service = service.model_copy(update={"health": wrong_endpoint})
        with self.assertRaisesRegex(ValidationError, "readiness endpoint"):
            SupervisorAuthorityReceipt(
                run_id=service.run_id,
                adapter_manifest_digest="a" * 64,
                target_identity_digest="b" * 64,
                service_receipt=wrong_endpoint_service,
                readiness_receipts=(wrong_endpoint,),
                lease_ids=(port_lease.lease_id, process_lease.lease_id),
            )

    def test_rejects_process_and_port_lease_id_collision(self) -> None:
        port_lease, process_lease, health, service = self._ready_service()
        colliding_process_lease = process_lease.model_copy(
            update={"lease_id": port_lease.lease_id}
        )
        colliding_service = service.model_copy(
            update={"process_lease": colliding_process_lease}
        )

        with self.assertRaisesRegex(ValidationError, "distinct.*lease|lease.*distinct"):
            SupervisorAuthorityReceipt(
                run_id=service.run_id,
                adapter_manifest_digest="a" * 64,
                target_identity_digest="b" * 64,
                service_receipt=colliding_service,
                readiness_receipts=(health,),
                lease_ids=(port_lease.lease_id,),
            )


class RealSystemFactTests(unittest.TestCase):
    def test_node_budget_requires_positive_typed_effect_bounds(self) -> None:
        base = {
            "max_requests": 1,
            "max_bytes": 1_024,
            "max_wall_seconds": 10,
        }
        with self.assertRaisesRegex(ValidationError, "max_user_actions"):
            NodeBudgetProposal(**base)

        for field in (
            "max_user_actions",
            "max_provider_requests",
            "max_cost_micros",
        ):
            with self.subTest(field=field), self.assertRaisesRegex(
                ValidationError, field
            ):
                NodeBudgetProposal(
                    **{
                        **base,
                        "max_user_actions": 1,
                        "max_provider_requests": 1,
                        "max_cost_micros": 1,
                        field: 0,
                    }
                )

    def test_pending_real_system_decision_rejects_general_authority(self) -> None:
        with self.assertRaisesRegex(ValidationError, "kind"):
            PendingRealSystemDecision(
                decision_id="decision:general",
                kind="general",  # type: ignore[arg-type]
                run_id="run-real-v2",
                run_head_digest="a" * 64,
                authority_digest="b" * 64,
                payload_digest="c" * 64,
            )

    def test_real_system_decision_binds_one_exact_pending_fact(self) -> None:
        from scripts.graph_v5.models import BudgetWideningAmendment

        amendment = BudgetWideningAmendment(
            kind="budget_widening",
            node_id="node-1",
            node_authority_digest="c" * 64,
            prior_budget_digest="d" * 64,
            requested_budget={
                "max_user_actions": 1,
                "max_provider_requests": 1,
                "max_cost_micros": 1,
                "max_requests": 2,
                "max_bytes": 2_048,
                "max_wall_seconds": 20,
            },
        )
        pending = PendingRealSystemDecision(
            decision_id="decision:budget",
            kind="budget_widening",
            run_id="run-real-v2",
            run_head_digest="a" * 64,
            authority_digest="b" * 64,
            payload_digest=digest_for("real-system-decision-amendment", amendment),
            amendment=amendment,
        )
        decision = RealSystemDecision(
            decision_id=pending.decision_id,
            pending_decision_digest=pending.digest,
            kind=pending.kind,
            run_id=pending.run_id,
            run_head_digest=pending.run_head_digest,
            authority_digest=pending.authority_digest,
            payload_digest=pending.payload_digest,
            amendment=amendment,
            actor="user:aleda",
        )

        self.assertEqual(decision.pending_decision_digest, pending.digest)
        self.assertEqual(decision.amendment, amendment)

    def test_real_system_decision_rejects_mismatched_kind_specific_amendment(self) -> None:
        from scripts.graph_v5.models import FixOrPatchAmendment

        amendment = FixOrPatchAmendment(
            kind="fix_or_patch",
            runtime_note_digest="e" * 64,
            treatment="patch",
        )
        with self.assertRaisesRegex(ValidationError, "amendment"):
            PendingRealSystemDecision(
                decision_id="decision:wrong-amendment",
                kind="budget_widening",
                run_id="run-real-v2",
                run_head_digest="a" * 64,
                authority_digest="b" * 64,
                payload_digest=digest_for("real-system-decision-amendment", amendment),
                amendment=amendment,
            )

    def test_external_intent_binds_reservation_and_runtime_note_stays_secret_free(self) -> None:
        reservation = BudgetReservation(
            reservation_id="reservation:op-1",
            run_id="run-real-v2",
            operation_id="op-1",
            user_actions=1,
            provider_requests=0,
            cost_micros=0,
            requests=1,
            processes=0,
            persistence_writes=1,
            tokens=0,
            duration_ms=1,
        )
        intent = ExternalOperationIntent(
            operation_id="op-1",
            run_id="run-real-v2",
            node_id="node-1",
            manifest_digest="a" * 64,
            run_head_digest="b" * 64,
            idempotency_key="provider:op-1",
            effect="bridge:act",
            reserved_budget=reservation,
        )

        self.assertEqual(intent.reserved_budget.operation_id, intent.operation_id)
        with self.assertRaisesRegex(ValidationError, "secret-free"):
            RuntimeNote(
                resource_ref="account:synthetic-1",
                lease_id="lease-1",
                classification="ephemeral_test_data",
                receipt_ref="receipt-1",
                cleanup_intent="token=must-not-persist",
            )

    def test_external_receipt_rejects_bearer_credential_in_evidence_reference(self) -> None:
        with self.assertRaisesRegex(ValidationError, "secret-free"):
            ExternalOperationReceipt(
                receipt_id="receipt:op-1",
                operation_id="op-1",
                run_id="run-real-v2",
                manifest_digest="a" * 64,
                run_head_digest="b" * 64,
                idempotency_key="provider:op-1",
                status="succeeded",
                evidence_refs=("Authorization: Bearer cleartext-credential",),
            )


class ImmutableFactsTests(unittest.TestCase):
    def test_environment_identity_is_frozen_after_observation_boundary(self) -> None:
        identity = EnvironmentIdentity(
            repository_revision="a" * 40,
            runtime="node-22.12.0",
            package_manager="npm-10.9.0",
            lockfile_digest="lock-sha256",
            host_fingerprint="host-sha256",
        )

        with self.assertRaises(ValidationError):
            identity.runtime = "node-24.0.0"  # type: ignore[misc]

    def test_rejects_v4_shaped_state_at_canonical_boundary(self) -> None:
        payload = {
            "schema_version": "v4",
            "run_id": "legacy-run",
            "goal": {"goal_id": "legacy-goal"},
            "findings": [],
        }

        with self.assertRaises(ValidationError):
            RunState.model_validate(payload)


class LimitsContractTests(unittest.TestCase):
    def test_widening_appends_new_version_without_changing_prior_version(self) -> None:
        limits = valid_limits()
        widened = limits.append_widening(
            name="causal_radius",
            amount=3,
            approver="user:aleda",
            reason="Need one evidence-connected ring",
            effective_graph_revision=7,
        )

        self.assertEqual(limits.active.values[0].amount, 2)
        self.assertEqual(widened.active_version, 2)
        self.assertEqual(widened.active.values[0].amount, 3)
        self.assertEqual(widened.amendments[0].old_value.amount, 2)
        self.assertEqual(widened.amendments[0].new_value.amount, 3)

    def test_rejects_missing_or_wrong_explicit_limit_unit(self) -> None:
        with self.assertRaises(ValidationError):
            LimitValue(name="causal_radius", amount=2, unit="count")

        with self.assertRaises(ValidationError):
            RunLimits(
                version=1,
                source_profile="config/policy-fixtures/run-limits.test.v1.json",
                source_digest="policy-sha256",
                values=(LimitValue(name="causal_radius", amount=2, unit="graph_hops"),),
            )

    def test_rejects_incomplete_run_limits_profile(self) -> None:
        active = valid_limits().active
        incomplete = tuple(
            value for value in active.values if value.name != "model_calls_per_run"
        )

        with self.assertRaises(ValidationError):
            RunLimits(
                version=1,
                source_profile=active.source_profile,
                source_digest=active.source_digest,
                values=incomplete,
            )

    def test_run_limits_schema_requires_every_named_unit(self) -> None:
        schema_path = (
            Path(__file__).resolve().parents[2] / "config" / "run-limits.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        values_schema = schema["properties"]["values"]
        expected = {
            "causal_radius": "graph_hops",
            "failed_repair_cycles": "count_per_node",
            "diagnostic_widening": "evidence_connected_ring",
            "reasoning_escalation": "count_per_stall_fingerprint",
            "discovery_commands": "commands_per_cone",
            "discovery_duration": "milliseconds_per_cone",
            "repair_attempts": "patch_attempts_per_cone",
            "repair_commands": "commands_per_cone",
            "repair_duration": "milliseconds_per_cone",
            "artifact_output_per_command": "bytes_per_command",
            "artifact_output_per_run": "bytes_per_run",
            "agent_dispatches_per_cone": "dispatches_per_cone",
            "agent_dispatches_per_run": "dispatches_per_run",
            "model_calls_per_cone": "calls_per_cone",
            "model_calls_per_run": "calls_per_run",
            "model_reasoning_tokens_per_cone": "tokens_per_cone",
            "model_reasoning_tokens_per_run": "tokens_per_run",
            "model_reasoning_cost_per_cone": "normalized_provider_cost_per_cone",
            "model_reasoning_cost_per_run": "normalized_provider_cost_per_run",
            "global_work_commands": "commands_per_run",
            "global_work_duration": "milliseconds_per_run",
        }

        self.assertEqual(values_schema.get("minItems"), len(expected))
        self.assertEqual(values_schema.get("maxItems"), len(expected))
        actual = {
            item["allOf"][1]["properties"]["name"]["const"]:
            item["allOf"][1]["properties"]["unit"]["const"]
            for item in values_schema["prefixItems"]
        }
        self.assertEqual(actual, expected)
        self.assertFalse(values_schema["items"])

    def test_rejects_unrecorded_widening_in_appended_limits_version(self) -> None:
        widened = valid_limits().append_widening(
            name="causal_radius",
            amount=3,
            approver="user:aleda",
            reason="Need one evidence-connected ring",
            effective_graph_revision=7,
        )
        payload = widened.model_dump()
        by_name = {
            item["name"]: item for item in payload["versions"][1]["values"]
        }
        by_name["failed_repair_cycles"]["amount"] = 2

        with self.assertRaises(ValidationError):
            VersionedLimits.model_validate(payload)

    def test_rejects_amendment_whose_old_value_does_not_match_history(self) -> None:
        widened = valid_limits().append_widening(
            name="causal_radius",
            amount=3,
            approver="user:aleda",
            reason="Need one evidence-connected ring",
            effective_graph_revision=7,
        )
        payload = widened.model_dump()
        payload["amendments"][0]["old_value"]["amount"] = 1

        with self.assertRaises(ValidationError):
            VersionedLimits.model_validate(payload)
