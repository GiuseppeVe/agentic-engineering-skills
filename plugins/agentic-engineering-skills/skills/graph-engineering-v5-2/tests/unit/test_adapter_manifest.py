from __future__ import annotations

import unittest
from dataclasses import replace

from pydantic import ValidationError

from scripts.graph_v5.adapters.registry import (
    FIXTURE_JOURNEY_INTERFACE_DIGEST,
    SERVICE_JOURNEY_INTERFACE_DIGEST,
    AdapterManifestError,
    resolve_adapter,
)
from scripts.graph_v5.adapters.host_registry import HostProviderError, resolve_host_provider
from scripts.graph_v5.adapters import registry
from scripts.graph_v5.adapters.manifest import AdapterManifest
from scripts.graph_v5.canonical import digest_for
from scripts.graph_v5.environment import EnvironmentSnapshot
from scripts.graph_v5.models import (
    EgressGateReceipt,
    RealExecutionEnvelope,
    V52RunState,
    V52TrajectoryBrief,
    V52TrajectoryConfirmation,
)
from scripts.graph_v5.policy import ExactTarget


def manifest_payload(*, mode: str = "remote_nonprod") -> dict[str, object]:
    return {
        "schema_version": "graph-v5.adapter-manifest.v1",
        "manifest_id": "manifest-real-system-v1",
        "adapter_id": "service-journey.v1",
        "adapter_interface_digest": SERVICE_JOURNEY_INTERFACE_DIGEST,
        "mode": mode,
        "target": {"https_origin": "https://service.example.test"},
        "synthetic_scope": {
            "namespace": "graph-test-run-01",
            "owned_resources": ["account:synthetic-01", "database:graph_test_01"],
        },
        "capabilities": ["bridge:observe", "bridge:act"],
        "budgets": {
            "max_user_actions": 4,
            "max_provider_requests": 4,
            "max_cost_micros": 1_000_000,
            "max_requests": 12,
            "max_processes": 2,
            "max_persistence_writes": 12,
            "max_tokens": 8_000,
            "max_duration_ms": 60_000,
        },
        "secrets": [{"name": "SERVICE_TEST_TOKEN"}],
        "egress": {"hosts": ["service.example.test"], "enforcement_receipt": "egress-receipt-v1"},
        "evidence": {"redaction_policy_digest": "b" * 64, "allowed_kinds": ["log", "trace"]},
        "teardown": {"policy": "manual_after_terminal_decision", "max_attempts": 1},
        "production_write_plan": None,
    }


def production_write_plan_payload() -> dict[str, object]:
    return {
        "plan_id": "write-plan-v1",
        "write_plan_digest": "c" * 64,
        "operations": ["create synthetic record"],
        "confirmed_by": "user:aleda",
        "confirmation_evidence_ref": "conversation:explicit-production-write-confirmation:1",
    }


def registered_fixture_manifest(
    *,
    adapter_interface_digest: str = FIXTURE_JOURNEY_INTERFACE_DIGEST,
    mode: str = "fixture",
) -> AdapterManifest:
    payload = manifest_payload(mode=mode)
    payload["adapter_id"] = "fixture-user-journey.v1"
    payload["adapter_interface_digest"] = adapter_interface_digest
    if mode == "fixture":
        payload["target"] = {"loopback_origin": "http://127.0.0.1:4317"}
        payload["egress"] = {"hosts": []}
    return AdapterManifest.model_validate(payload)


class AdapterManifestTests(unittest.TestCase):
    def test_registry_rejects_wrong_digest_or_unsupported_mode_before_store_creation(self) -> None:
        with self.assertRaisesRegex(ValidationError, "interface digest"):
            registered_fixture_manifest(adapter_interface_digest="a" * 64)
        with self.assertRaisesRegex(ValidationError, "does not support mode"):
            registered_fixture_manifest(mode="remote_nonprod")

    def test_static_registry_rejects_runtime_factory_replacement(self) -> None:
        descriptor = resolve_adapter(registered_fixture_manifest())
        replacement = replace(descriptor, factory=lambda manifest, dependencies: object())

        with self.assertRaises(TypeError):
            registry._DESCRIPTORS[descriptor.adapter_id] = replacement

    def test_service_provider_does_not_self_issue_egress_authority_from_manifest_reference(self) -> None:
        manifest = AdapterManifest.model_validate(manifest_payload())
        source_identity_digest = digest_for(
            "service-source-identity", {"origin": manifest.target.origin}
        )
        brief = V52TrajectoryBrief(
            schema_version="graph-v5.trajectory-brief.v2",
            run_id="service-admission-run",
            brief_id="service-admission-brief",
            created_at="2026-09-12T08:00:00Z",
            goal="Exercise admitted service journey.",
            execution_envelope=RealExecutionEnvelope(
                mode="remote_nonprod",
                target_identity_digest=source_identity_digest,
                adapter_manifest_digest=manifest.digest,
            ),
            adapter_manifest_digest=manifest.digest,
        )
        confirmation = V52TrajectoryConfirmation(
            schema_version="graph-v5.trajectory-confirmation.v2",
            run_id=brief.run_id,
            brief_id=brief.brief_id,
            trajectory_digest=brief.digest,
            adapter_manifest_digest=manifest.digest,
            confirmed_by="user:aleda",
            confirmed_at="2026-09-12T08:01:00Z",
            confirmation_evidence_ref="conversation:explicit-confirmation:1",
        )
        state = V52RunState(
            schema_version="graph-v5.run-state.v2",
            run_id=brief.run_id,
            mode="running",
            trajectory=brief,
            confirmation=confirmation,
        )

        with self.assertRaisesRegex(HostProviderError, "compiled enforceable egress"):
            resolve_host_provider(manifest.adapter_id).acquire_environment_authority(
                state, manifest
            )

    def test_manifest_rejects_unknown_adapter_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "registered adapter"):
            AdapterManifest.model_validate({**manifest_payload(), "adapter_id": "import:evil"})

    def test_production_write_requires_exact_confirmed_plan(self) -> None:
        payload = manifest_payload(mode="production_guarded")
        payload["write_policy"] = "synthetic"
        with self.assertRaisesRegex(ValueError, "ProductionWritePlan"):
            AdapterManifest.model_validate(payload)

    def test_write_policy_defaults_follow_target_mode(self) -> None:
        nonprod = AdapterManifest.model_validate(manifest_payload())
        production = AdapterManifest.model_validate(
            manifest_payload(mode="production_guarded")
        )

        self.assertEqual(nonprod.write_policy, "synthetic")
        self.assertEqual(production.write_policy, "read_only")

    def test_production_write_accepts_exact_confirmed_plan(self) -> None:
        payload = manifest_payload(mode="production_guarded")
        payload["write_policy"] = "synthetic"
        payload["production_write_plan"] = production_write_plan_payload()

        manifest = AdapterManifest.model_validate(payload)

        self.assertEqual(manifest.write_policy, "synthetic")
        self.assertEqual(
            manifest.production_write_plan.operations,
            ("create synthetic record",),
        )

    def test_remote_target_requires_matching_egress_gate(self) -> None:
        payload = manifest_payload()
        payload["egress"] = {
            "hosts": ["provider.example.test"],
            "enforcement_receipt": "egress-receipt-v1",
        }

        with self.assertRaisesRegex(ValueError, "target host"):
            AdapterManifest.model_validate(payload)

    def test_remote_target_rejects_deny_all_egress_policy(self) -> None:
        payload = manifest_payload()
        payload["egress"] = {"hosts": []}

        with self.assertRaisesRegex(ValueError, "target host"):
            AdapterManifest.model_validate(payload)

    def test_remote_target_requires_egress_receipt(self) -> None:
        payload = manifest_payload()
        payload["egress"] = {"hosts": ["service.example.test"]}

        with self.assertRaisesRegex(ValueError, "enforcement receipt"):
            AdapterManifest.model_validate(payload)

    def test_local_outbound_egress_requires_receipt(self) -> None:
        payload = manifest_payload(mode="local_isolated")
        payload["target"] = {"loopback_origin": "http://127.0.0.1:4317"}
        payload["egress"] = {"hosts": ["provider.example.test"]}

        with self.assertRaisesRegex(ValueError, "enforcement receipt"):
            AdapterManifest.model_validate(payload)

    def test_local_outbound_egress_accepts_exact_provider_receipt(self) -> None:
        payload = manifest_payload(mode="local_isolated")
        payload["target"] = {"loopback_origin": "http://127.0.0.1:4317"}
        payload["egress"] = {
            "hosts": ["provider.example.test"],
            "enforcement_receipt": "provider-egress-v1",
        }
        manifest = AdapterManifest.model_validate(payload)
        receipt = EgressGateReceipt(
            run_id="run-local-egress",
            adapter_manifest_digest=manifest.digest,
            target_identity_digest="a" * 64,
            allowed_hosts=manifest.egress.hosts,
            allowed_protocols=("https",),
            issued_receipt_digest=digest_for(
                "egress-enforcement-receipt", manifest.egress.enforcement_receipt
            ),
        )

        snapshot = EnvironmentSnapshot.from_admitted_authority(
            manifest=manifest,
            target_identity_digest="a" * 64,
            supervisor_receipts=(),
            egress_receipt=receipt,
        )

        self.assertEqual(snapshot.egress_receipt_digest, receipt.digest)

    def test_exact_target_rejects_wildcard_and_ambiguous_numeric_hosts(self) -> None:
        for origin in (
            "https://*.example.test",
            "https://127.000.000.001",
            "https://2130706433",
        ):
            with self.subTest(origin=origin):
                with self.assertRaisesRegex(ValueError, "host"):
                    ExactTarget.model_validate({"https_origin": origin})

    def test_remote_mode_rejects_https_loopback_alias(self) -> None:
        payload = manifest_payload()
        payload["target"] = {"https_origin": "https://localhost"}
        payload["egress"] = {
            "hosts": ["localhost"],
            "enforcement_receipt": "egress-receipt-v1",
        }

        with self.assertRaisesRegex(ValueError, "remote manifests"):
            AdapterManifest.model_validate(payload)

    def test_digest_binds_real_system_brief_authority(self) -> None:
        manifest = AdapterManifest.model_validate(manifest_payload())
        other_target_payload = manifest_payload()
        other_target_payload["target"] = {"https_origin": "https://other.invalid"}
        other_target_payload["egress"] = {
            "hosts": ["other.invalid"],
            "enforcement_receipt": "other-egress-receipt-v1",
        }
        self.assertNotEqual(
            manifest.digest,
            AdapterManifest.model_validate(other_target_payload).digest,
        )

    def test_remote_target_must_be_exact_https_origin(self) -> None:
        with self.assertRaisesRegex(ValidationError, "HTTPS"):
            AdapterManifest.model_validate(
                {**manifest_payload(), "target": {"https_origin": "http://service.example.test"}}
            )

    def test_local_manifest_accepts_bracketed_ipv6_loopback_origin(self) -> None:
        manifest = AdapterManifest.model_validate(
            {
                **manifest_payload(mode="local_isolated"),
                "target": {"loopback_origin": "http://[::1]:4317"},
            }
        )
        self.assertEqual(manifest.target.origin, "http://[::1]:4317")

    def test_production_write_plan_requires_explicit_confirmation_evidence(self) -> None:
        payload = manifest_payload(mode="production_guarded")
        payload["production_write_plan"] = {
            **production_write_plan_payload(),
            "operations": ["create synthetic record"],
            "confirmation_evidence_ref": "silence",
        }
        with self.assertRaisesRegex(ValidationError, "explicit"):
            AdapterManifest.model_validate(payload)

    def test_manifest_never_accepts_secret_value(self) -> None:
        payload = manifest_payload()
        payload["secrets"] = [{"name": "SERVICE_TEST_TOKEN", "value": "not-permitted"}]
        with self.assertRaises(ValidationError):
            AdapterManifest.model_validate(payload)

    def test_production_write_plan_rejects_duplicate_operations(self) -> None:
        payload = manifest_payload(mode="production_guarded")
        payload["write_policy"] = "synthetic"
        payload["production_write_plan"] = {
            **production_write_plan_payload(),
            "operations": ["create synthetic record", "create synthetic record"],
        }

        with self.assertRaisesRegex(ValidationError, "duplicate"):
            AdapterManifest.model_validate(payload)
