from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from scripts.graph_v5.adapters.manifest import AdapterManifest
from scripts.graph_v5.adapters.registry import (
    FIXTURE_JOURNEY_INTERFACE_DIGEST,
    SERVICE_JOURNEY_INTERFACE_DIGEST,
)
from scripts.graph_v5.admission import AdmissionError, RealAdmissionCoordinator
from scripts.graph_v5.canonical import digest_for
from scripts.graph_v5.environment import EnvironmentSnapshot
from scripts.graph_v5.models import (
    AdmittedProviderAuthority,
    BaselineNodeProposal,
    BaselineSpineAuthority,
    ConfirmedRealTrajectoryBundle,
    DerivedBehavioralNode,
    NodeBudgetProposal,
    NodeProposal,
    RealExecutionEnvelope,
    RealSystemRunHead,
    V52RunState,
    V52TrajectoryBrief,
    V52TrajectoryConfirmation,
)


def valid_manifest() -> AdapterManifest:
    return AdapterManifest.model_validate(
        {
            "schema_version": "graph-v5.adapter-manifest.v1",
            "manifest_id": "fixture-admission-manifest-v1",
            "adapter_id": "fixture-user-journey.v1",
            "adapter_interface_digest": FIXTURE_JOURNEY_INTERFACE_DIGEST,
            "mode": "fixture",
            "target": {"loopback_origin": "http://127.0.0.1:4317"},
            "synthetic_scope": {
                "namespace": "fixture-admission",
                "owned_resources": ["fixture:checkout"],
            },
            "capabilities": ["fixture:user_journey_action"],
            "budgets": {
                "max_user_actions": 1,
                "max_provider_requests": 1,
                "max_cost_micros": 1,
                "max_requests": 2,
                "max_processes": 1,
                "max_persistence_writes": 1,
                "max_tokens": 100,
                "max_duration_ms": 10_000,
            },
            "secrets": [],
            "egress": {"hosts": []},
            "evidence": {"redaction_policy_digest": "a" * 64, "allowed_kinds": ["log"]},
            "teardown": {"policy": "manual_only", "max_attempts": 1},
        }
    )


def valid_bundle() -> ConfirmedRealTrajectoryBundle:
    source_identity_digest = digest_for("fixture-admission-source", {"fixture": "checkout"})
    manifest = valid_manifest()
    brief = V52TrajectoryBrief(
        schema_version="graph-v5.trajectory-brief.v2",
        run_id="real-admission-run",
        brief_id="real-admission-brief",
        created_at="2026-09-12T08:00:00Z",
        goal="Exercise admitted fixture journey.",
        execution_envelope=RealExecutionEnvelope(
            mode="fixture",
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
    proposal = NodeProposal(
        node_id="baseline-checkout",
        source_anchor_id="start",
        target_landmark_id="checkout",
        action_kind="act",
        action_or_probe="Submit synthetic checkout form",
        expected_before=("Synthetic checkout form is visible",),
        expected_after=("Synthetic checkout result is visible",),
        derivation_reason="Confirmed fixture route",
        authority_refs=("trajectory:checkout",),
        execution_scope="fixture:checkout",
        side_effect="fixture:user_journey_action",
        target_systems=("127.0.0.1",),
    )
    return ConfirmedRealTrajectoryBundle(
        schema_version="graph-v5.confirmed-real-trajectory-bundle.v1",
        brief=brief,
        confirmation=confirmation,
        baseline=(
            BaselineNodeProposal(
                proposal=proposal,
                entry_observation_refs=("observation:fixture-start",),
                budget=NodeBudgetProposal(
                    max_user_actions=1,
                    max_provider_requests=1,
                    max_cost_micros=1,
                    max_requests=1,
                    max_bytes=1_024,
                    max_wall_seconds=10,
                ),
            ),
        ),
        provider_authority=AdmittedProviderAuthority(
            schema_version="graph-v5.admitted-provider-authority.v1",
            adapter_id=manifest.adapter_id,
            provider_id="fixture-host-provider.v1",
            source_identity_digest=source_identity_digest,
        ),
    )


def unregistered_local_service_manifest() -> AdapterManifest:
    return AdapterManifest.model_validate(
        {
            "schema_version": "graph-v5.adapter-manifest.v1",
            "manifest_id": "unregistered-local-service-manifest-v1",
            "adapter_id": "service-journey.v1",
            "adapter_interface_digest": SERVICE_JOURNEY_INTERFACE_DIGEST,
            "mode": "local_isolated",
            "target": {"loopback_origin": "http://127.0.0.1:4317"},
            "synthetic_scope": {
                "namespace": "unregistered-local-service",
                "owned_resources": ["service:checkout"],
            },
            "capabilities": ["bridge:act"],
            "budgets": {
                "max_user_actions": 1,
                "max_provider_requests": 1,
                "max_cost_micros": 1,
                "max_requests": 2,
                "max_processes": 1,
                "max_persistence_writes": 1,
                "max_tokens": 100,
                "max_duration_ms": 10_000,
            },
            "secrets": [],
            "egress": {"hosts": []},
            "evidence": {"redaction_policy_digest": "a" * 64, "allowed_kinds": ["log"]},
            "teardown": {"policy": "manual_only", "max_attempts": 1},
        }
    )


def unregistered_local_service_bundle(
    manifest: AdapterManifest,
) -> ConfirmedRealTrajectoryBundle:
    source_identity_digest = digest_for(
        "unregistered-service-source", {"origin": manifest.target.origin}
    )
    brief = V52TrajectoryBrief(
        schema_version="graph-v5.trajectory-brief.v2",
        run_id="unregistered-service-run",
        brief_id="unregistered-service-brief",
        created_at="2026-09-12T08:00:00Z",
        goal="Exercise local service journey.",
        execution_envelope=RealExecutionEnvelope(
            mode="local_isolated",
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
    proposal = NodeProposal(
        node_id="local-service-checkout",
        source_anchor_id="start",
        target_landmark_id="checkout",
        action_kind="act",
        action_or_probe="Submit local synthetic checkout",
        expected_before=("Local checkout form is visible",),
        expected_after=("Local checkout result is visible",),
        derivation_reason="Confirmed local route",
        authority_refs=("trajectory:local-checkout",),
        execution_scope="service:checkout",
        side_effect="bridge:act",
        target_systems=("127.0.0.1",),
    )
    return ConfirmedRealTrajectoryBundle(
        schema_version="graph-v5.confirmed-real-trajectory-bundle.v1",
        brief=brief,
        confirmation=confirmation,
        baseline=(
            BaselineNodeProposal(
                proposal=proposal,
                entry_observation_refs=("observation:local-start",),
                budget=NodeBudgetProposal(
                    max_user_actions=1,
                    max_provider_requests=1,
                    max_cost_micros=1,
                    max_requests=1,
                    max_bytes=1_024,
                    max_wall_seconds=10,
                ),
            ),
        ),
        provider_authority=AdmittedProviderAuthority(
            schema_version="graph-v5.admitted-provider-authority.v1",
            adapter_id=manifest.adapter_id,
            provider_id="service-host-provider.v1",
            source_identity_digest=source_identity_digest,
        ),
    )


class ConfirmedRealTrajectoryBundleTests(unittest.TestCase):
    def test_bundle_rejects_typed_node_budget_above_manifest_ceiling(self) -> None:
        manifest = valid_manifest()
        payload = valid_bundle().model_dump(mode="python")
        payload["baseline"] = (
            {
                **payload["baseline"][0],
                "budget": {
                    "max_user_actions": manifest.budgets.max_user_actions + 1,
                    "max_provider_requests": 1,
                    "max_cost_micros": 1,
                    "max_requests": 1,
                    "max_bytes": 1_024,
                    "max_wall_seconds": 10,
                },
            },
        )

        with self.assertRaisesRegex(ValueError, "user-action budget exceeds"):
            ConfirmedRealTrajectoryBundle.model_validate(payload).validate_for_manifest(
                manifest
            )

    def test_bundle_rejects_mismatched_confirmation_duplicate_nodes_and_invalid_budget(self) -> None:
        bundle = valid_bundle()
        mismatched_confirmation = bundle.model_dump(mode="python")
        mismatched_confirmation["confirmation"] = {
            **mismatched_confirmation["confirmation"],
            "trajectory_digest": "0" * 64,
        }
        with self.assertRaisesRegex(ValidationError, "confirmation"):
            ConfirmedRealTrajectoryBundle.model_validate(mismatched_confirmation)

        duplicate_node = bundle.model_dump(mode="python")
        duplicate_node["baseline"] = duplicate_node["baseline"] * 2
        with self.assertRaisesRegex(ValidationError, "baseline"):
            ConfirmedRealTrajectoryBundle.model_validate(duplicate_node)

        invalid_budget = bundle.model_dump(mode="python")
        invalid_budget["baseline"] = (
            {
                **invalid_budget["baseline"][0],
                "budget": {"max_requests": 0, "max_bytes": 1_024, "max_wall_seconds": 10},
            },
        )
        with self.assertRaisesRegex(ValidationError, "baseline"):
            ConfirmedRealTrajectoryBundle.model_validate(invalid_budget)


class RealAdmissionTests(unittest.TestCase):
    def test_unregistered_fixture_source_is_rejected_before_store_creation(self) -> None:
        bundle = valid_bundle()
        foreign_source_digest = "f" * 64
        brief = bundle.brief.model_copy(
            update={
                "execution_envelope": bundle.brief.execution_envelope.model_copy(
                    update={"target_identity_digest": foreign_source_digest}
                )
            }
        )
        confirmation = bundle.confirmation.model_copy(
            update={"trajectory_digest": brief.digest}
        )
        bundle = bundle.model_copy(
            update={
                "brief": brief,
                "confirmation": confirmation,
                "provider_authority": bundle.provider_authority.model_copy(
                    update={"source_identity_digest": foreign_source_digest}
                ),
            }
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "run-store"

            with self.assertRaisesRegex(AdmissionError, "provider authority"):
                RealAdmissionCoordinator.start(
                    root=root, bundle=bundle, manifest=valid_manifest()
                )

            self.assertFalse(root.exists())

    def test_unregistered_service_source_is_rejected_before_store_creation(self) -> None:
        manifest = unregistered_local_service_manifest()
        bundle = unregistered_local_service_bundle(manifest)
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "run-store"

            with self.assertRaisesRegex(AdmissionError, "provider authority"):
                RealAdmissionCoordinator.start(
                    root=root,
                    bundle=bundle,
                    manifest=manifest,
                )

            self.assertFalse(root.exists())

    def test_sealed_baseline_rejects_node_payload_not_derived_from_bound_proposal(self) -> None:
        manifest = valid_manifest()
        bundle = valid_bundle()
        initial_state = V52RunState(
            schema_version="graph-v5.run-state.v2",
            run_id=bundle.brief.run_id,
            mode="running",
            trajectory=bundle.brief,
            confirmation=bundle.confirmation,
        )
        snapshot = EnvironmentSnapshot.for_fixture_manifest(
            manifest=manifest,
            fixture_digest=bundle.provider_authority.source_identity_digest,
        )
        run_head = RealSystemRunHead(
            run_id=initial_state.run_id,
            manifest_digest=manifest.digest,
            environment_snapshot_digest=snapshot.digest,
        )
        forged_proposal = bundle.baseline[0].proposal.model_copy(
            update={"action_or_probe": "Dispatch different admitted action"}
        )
        forged_node = DerivedBehavioralNode.seal(
            forged_proposal,
            entry_observation_refs=bundle.baseline[0].entry_observation_refs,
            run_id=initial_state.run_id,
            trajectory_digest=initial_state.trajectory.digest,
            run_head_digest=run_head.digest,
            execution_envelope_digest=initial_state.trajectory.execution_envelope.digest,
        )

        with self.assertRaisesRegex(ValueError, "proposal"):
            BaselineSpineAuthority.from_nodes(
                initial_state,
                run_head,
                manifest,
                snapshot,
                (forged_node,),
                bundle.baseline,
            )

    def test_invalid_bundle_or_provider_creates_no_store_process_or_network_effect(self) -> None:
        bundle = valid_bundle().model_copy(
            update={
                "provider_authority": AdmittedProviderAuthority(
                    schema_version="graph-v5.admitted-provider-authority.v1",
                    adapter_id="fixture-user-journey.v1",
                    provider_id="import:evil",
                    source_identity_digest=valid_bundle().provider_authority.source_identity_digest,
                )
            }
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "run-store"

            with self.assertRaisesRegex(AdmissionError, "provider authority"):
                RealAdmissionCoordinator.start(root=root, bundle=bundle, manifest=valid_manifest())

            self.assertFalse(root.exists())

    def test_valid_fixture_admission_persists_one_complete_authority_chain(self) -> None:
        bundle = valid_bundle()
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "run-store"

            controller = RealAdmissionCoordinator.start(
                root=root,
                bundle=bundle,
                manifest=valid_manifest(),
            )

            state = controller.state
            self.assertEqual("running", state.mode)
            self.assertEqual(bundle.provider_authority, state.facts.provider_authority)
            self.assertEqual(
                (bundle.baseline[0].proposal_digest,),
                state.facts.baseline_spine.proposal_digests,
            )
            self.assertTrue((root / "state.json").is_file())
            self.assertTrue((root / "adapter-manifest.json").is_file())


if __name__ == "__main__":
    unittest.main()
