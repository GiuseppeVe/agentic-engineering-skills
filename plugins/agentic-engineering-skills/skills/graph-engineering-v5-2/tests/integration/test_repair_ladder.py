from __future__ import annotations

import json
import unittest
import importlib.util
from dataclasses import replace
from pathlib import Path

from scripts.graph_v5.models import CausalEdge, CausalLead, Observation, ProofSpec


_FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "user_journeys"


def _bound_proof_spec(node_id: str) -> ProofSpec:
    return ProofSpec(
        proof_spec_id=f"proof:{node_id}",
        node_id=node_id,
        discriminator="profile survives refresh",
        expected_result="green",
        command=("python", "-m", "unittest", "tests.profile"),
        trajectory_digest="a" * 64,
        derived_spine_digest="b" * 64,
        landmark_mapping_digest="c" * 64,
    )


def _shared_root_failure_observations() -> tuple[Observation, ...]:
    from scripts.graph_v5.adapters import user_journey

    path = _FIXTURE_ROOT / "shared-root.v1.json"
    adapter = user_journey.FixtureUserJourneyAdapter.from_fixture_file(
        path, "shared-root-two-symptoms"
    )
    snapshot = adapter.fixture_snapshot()
    adapter.reset_fixture(snapshot)
    root_observation = adapter.observe(anchor_id="START", run_head_digest="a" * 64)
    return (
        Observation(
            observation_id="profile-summary-failure-observation",
            node_id="profile-summary",
            kind="behavioral",
            observed_state="Profile summary is missing",
            evidence_refs=root_observation.evidence_refs + ("symptom:summary",),
            run_head_digest="a" * 64,
        ),
        Observation(
            observation_id="profile-history-failure-observation",
            node_id="profile-history",
            kind="behavioral",
            observed_state="Profile history is missing",
            evidence_refs=root_observation.evidence_refs + ("symptom:history",),
            run_head_digest="a" * 64,
        ),
    )


def _closed_cone(observations: tuple[Observation, ...] | None = None) -> object:
    from scripts.graph_v5.causality import (
        CausalCone,
        ConeHop,
        DiscoveryReview,
        MaterialSeamReceipt,
    )

    observations = observations or (
        Observation(
            observation_id="profile-summary-failure-observation",
            node_id="profile-summary",
            kind="behavioral",
            observed_state="Profile summary is missing",
            evidence_refs=("fixture:profile-persistence-root", "symptom:summary"),
            run_head_digest="a" * 64,
        ),
        Observation(
            observation_id="profile-history-failure-observation",
            node_id="profile-history",
            kind="behavioral",
            observed_state="Profile history is missing",
            evidence_refs=("fixture:profile-persistence-root", "symptom:history"),
            run_head_digest="a" * 64,
        ),
    )
    summary, history = observations
    distractor = CausalLead(
        lead_id="speculative-first-root",
        source_observation_id=summary.observation_id,
        subject="first input-order candidate",
        disposition="supported_cause",
        evidence_refs=("proof:speculative",),
    )
    root = CausalLead(
        lead_id="profile-persistence-root",
        source_observation_id=summary.observation_id,
        subject="profile persistence mapping",
        disposition="supported_cause",
        evidence_refs=("fixture:profile-persistence-root",),
    )
    symptom = CausalLead(
        lead_id="profile-history-symptom",
        source_observation_id=history.observation_id,
        subject="profile history is missing",
        disposition="supported_symptom",
        evidence_refs=("symptom:history",),
    )
    cone = CausalCone(
        cone_id="profile-cone",
        node_id="profile-summary",
        observations=observations,
        leads=(distractor, root, symptom),
        edges=(
            CausalEdge(
                edge_id="speculative-history",
                from_lead_id=distractor.lead_id,
                to_lead_id=symptom.lead_id,
                relation="supports_symptom",
                evidence_refs=("proof:speculative",),
                confidence=60,
                risk="medium",
                requires_independent_attestation=True,
            ),
            CausalEdge(
                edge_id="root-history",
                from_lead_id=root.lead_id,
                to_lead_id=symptom.lead_id,
                relation="supports_symptom",
                evidence_refs=("fixture:profile-persistence-root",),
                confidence=95,
                risk="medium",
                requires_independent_attestation=True,
            ),
        ),
        required_variant_ids=("primary",),
        completed_variant_ids=("primary",),
        required_material_seam_ids=("profile-store",),
        material_seam_receipts=(
            MaterialSeamReceipt(
                seam_id="profile-store",
                cone_id="profile-cone",
                node_id="profile-summary",
                before_observation_id=summary.observation_id,
                after_observation_id=history.observation_id,
                evidence_refs=("fixture:profile-persistence-root",),
            ),
        ),
        discovery_limit_remaining=1,
        discovery_review=DiscoveryReview("discovery-reviewer-1", True),
        candidates=(
            ConeHop(
                "profile-persistence-root",
                "state_owner",
                root.lead_id,
                "root-history",
            ),
        ),
    )
    frozen = cone.freeze_expansion(diagnostics_implicate_runtime=False)
    return cone.close(frozen)


class RepairLadderIntegrationTests(unittest.TestCase):
    def test_candidate_integration_cherry_picks_one_patch_to_persistent_graph_run_only(self) -> None:
        import subprocess
        import tempfile

        from fixtures.repo_templates.git_repository import create_node22_repository, git_revision
        from scripts.graph_v5.models import GitTransaction, RunHead
        from scripts.graph_v5.workspace import GraphWorkspaceLifecycle, WorktreePreflightConfig

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = create_node22_repository(root / "repository")
            base = git_revision(repository)
            transaction = GitTransaction(
                transaction_id="repair-integration",
                requested_base_revision=base,
                branch="graph-run/repair-integration",
                worktree_path=str(root / "runs" / "repair-integration"),
                status="prepared",
            )
            lifecycle = GraphWorkspaceLifecycle(
                repository,
                preflight=WorktreePreflightConfig(
                    fixture_relative_path="fixture",
                    validator_relative_path="validator",
                ),
            )
            graph_run = lifecycle.create_or_reconcile_graph_run_workspace(transaction)
            candidate = lifecycle.create_repair_candidate(
                graph_run,
                branch="graph-repair/repair-integration/profile",
                worktree_path=root / "candidates" / "profile",
            )
            candidate_path = Path(candidate.worktree_path)
            (candidate_path / "repair.txt").write_bytes(b"repair\r\n")
            subprocess.run(["git", "add", "repair.txt"], cwd=candidate_path, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "repair"], cwd=candidate_path, check=True, capture_output=True)

            receipt = lifecycle.integrate_repair_candidate(
                graph_run,
                candidate,
                current_run_head=RunHead(
                    revision=base,
                    environment_digest="e" * 64,
                    fixture_digest="f" * 64,
                ),
            )

            self.assertEqual(receipt.prior_revision, base)
            self.assertEqual(receipt.prior_run_head_digest, RunHead(
                revision=base,
                environment_digest="e" * 64,
                fixture_digest="f" * 64,
            ).digest)
            self.assertNotEqual(receipt.new_revision, base)
            self.assertEqual(
                subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=Path(graph_run.worktree_path),
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.strip(),
                receipt.new_revision,
            )
            self.assertTrue(candidate_path.is_dir(), "candidate evidence stays until terminal review")
            self.assertEqual(
                subprocess.run(
                    ["git", "rev-parse", "main"],
                    cwd=repository,
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.strip(),
                base,
            )

    def test_mutation_leases_are_process_global_and_integration_requires_issued_active_lease(self) -> None:
        from scripts.graph_v5.causality import CausalityError, MutationLeaseManager
        from scripts.graph_v5.repair import RepairError, integrate_repair, propose_repair

        closed = _closed_cone()
        manager_a = MutationLeaseManager()
        manager_b = MutationLeaseManager()
        lease_a = manager_a.acquire(closed.cone_id)
        try:
            with self.assertRaisesRegex(CausalityError, "active mutation lease"):
                manager_b.acquire("other-cone")
            candidate = propose_repair(
                closed,
                lease=lease_a,
                patch="fix profile persistence mapping",
                changed_files=("profile_store.py",),
                changed_dependencies=("profile-store",),
                local_validation_receipt="local:test-profile-store:green",
                requested_proof=_bound_proof_spec("profile-summary"),
            )
            self.assertTrue(
                hasattr(candidate, "mutation_lease"),
                "candidate patch must carry its issued mutation lease",
            )
            self.assertIs(candidate.mutation_lease, lease_a)

            with self.assertRaisesRegex(RepairError, "exact active mutation lease"):
                integrate_repair(
                    candidate,
                    lease=None,
                    proofs=(),
                    changed_ownership_seams=(),
                    direct_affected_neighbors=(),
                )
            reconstructed_lease = replace(lease_a)
            with self.assertRaisesRegex(RepairError, "exact active mutation lease"):
                integrate_repair(
                    candidate,
                    lease=reconstructed_lease,
                    proofs=(),
                    changed_ownership_seams=(),
                    direct_affected_neighbors=(),
                )
            with self.assertRaisesRegex(RepairError, "active mutation lease"):
                integrate_repair(
                    replace(candidate, mutation_lease=reconstructed_lease),
                    lease=reconstructed_lease,
                    proofs=(),
                    changed_ownership_seams=(),
                    direct_affected_neighbors=(),
                )
        finally:
            manager_a.release(lease_a)

        with self.assertRaisesRegex(RepairError, "active mutation lease"):
            integrate_repair(
                candidate,
                lease=lease_a,
                proofs=(),
                changed_ownership_seams=(),
                direct_affected_neighbors=(),
            )
        lease_b = manager_b.acquire(closed.cone_id)
        try:
            with self.assertRaisesRegex(RepairError, "exact active mutation lease"):
                integrate_repair(
                    candidate,
                    lease=lease_b,
                    proofs=(),
                    changed_ownership_seams=(),
                    direct_affected_neighbors=(),
                )
        finally:
            manager_b.release(lease_b)

    def test_candidate_derives_graph_neighbors_that_integration_cannot_omit(self) -> None:
        from scripts.graph_v5.causality import MutationLeaseManager
        from scripts.graph_v5.repair import RepairError, integrate_repair, propose_repair

        closed = _closed_cone()
        manager = MutationLeaseManager()
        lease = manager.acquire(closed.cone_id)
        try:
            candidate = propose_repair(
                closed,
                lease=lease,
                patch="fix profile persistence mapping",
                changed_files=("profile_store.py",),
                changed_dependencies=("profile-store",),
                local_validation_receipt="local:test-profile-store:green",
                requested_proof=_bound_proof_spec("profile-summary"),
            )
            self.assertTrue(
                hasattr(candidate, "derived_neighbor_node_ids"),
                "candidate patch must preserve graph-derived direct neighbors",
            )
            self.assertEqual(candidate.derived_neighbor_node_ids, frozenset({"profile-history"}))
            reconstructed = replace(candidate, derived_neighbor_node_ids=frozenset())
            with self.assertRaisesRegex(RepairError, "exact issued candidate"):
                integrate_repair(
                    reconstructed,
                    lease=lease,
                    proofs=(),
                    changed_ownership_seams=(),
                    direct_affected_neighbors=(),
                )
            plan = integrate_repair(
                candidate,
                lease=lease,
                proofs=(),
                changed_ownership_seams=(),
                direct_affected_neighbors=("settings",),
            )
            self.assertEqual(
                plan.revalidation_node_ids,
                ("profile-summary", "profile-history", "settings"),
            )
            with self.assertRaisesRegex(RepairError, "exact issued candidate"):
                integrate_repair(
                    candidate,
                    lease=lease,
                    proofs=(),
                    changed_ownership_seams=(),
                    direct_affected_neighbors=(),
                )
        finally:
            manager.release(lease)

    def test_repair_is_blocked_until_causal_cone_is_closed_and_only_one_mutation_lease_exists(self) -> None:
        self.assertIsNotNone(
            importlib.util.find_spec("scripts.graph_v5.repair"),
            "repair module is missing",
        )
        from scripts.graph_v5.causality import CausalCone, CausalityError, MutationLeaseManager
        from scripts.graph_v5.repair import RepairError, propose_repair

        manager = MutationLeaseManager()
        lease = manager.acquire("profile-cone")
        self.addCleanup(manager.release, lease)
        with self.assertRaisesRegex(RepairError, "closed cone"):
            propose_repair(
                CausalCone(cone_id="profile-cone", node_id="profile-summary"),
                lease=lease,
                patch="fix persistence mapping",
                changed_files=("profile_store.py",),
                changed_dependencies=("profile-store",),
                local_validation_receipt="local:test-profile-store:green",
                requested_proof=_bound_proof_spec("profile-summary"),
            )
        with self.assertRaisesRegex(CausalityError, "active mutation lease"):
            manager.acquire("other-cone")

        cloned_lease = type(lease)(
            cone_id=lease.cone_id,
            token=lease.token,
            _manager=manager,
        )
        with self.assertRaisesRegex(CausalityError, "active mutation lease"):
            cloned_lease.assert_active()

    def test_repair_revalidates_closed_cone_marker_before_use(self) -> None:
        from scripts.graph_v5.causality import CausalityError, ClosedCausalCone

        closed = _closed_cone()
        forged = replace(closed.frozen_expansion, selected_lead_id="profile-history-symptom")

        with self.assertRaisesRegex(CausalityError, "frozen expansion"):
            ClosedCausalCone(closed.cone, forged)

    def test_repair_rejects_unbound_proof_authority(self) -> None:
        from scripts.graph_v5.causality import MutationLeaseManager
        from scripts.graph_v5.repair import RepairError, propose_repair

        closed = _closed_cone()
        manager = MutationLeaseManager()
        lease = manager.acquire(closed.cone_id)
        self.addCleanup(manager.release, lease)
        with self.assertRaisesRegex(RepairError, "trajectory/spine/landmark authority"):
            propose_repair(
                closed,
                lease=lease,
                patch="fix profile persistence mapping",
                changed_files=("profile_store.py",),
                changed_dependencies=("profile-store",),
                local_validation_receipt="local:test-profile-store:green",
                requested_proof=ProofSpec(
                    proof_spec_id="unbound-proof",
                    node_id="profile-summary",
                    discriminator="profile survives refresh",
                    expected_result="green",
                    command=("python", "-m", "unittest", "tests.profile"),
                ),
            )

    def test_shared_root_repair_preserves_observations_and_schedules_local_revalidation_only(self) -> None:
        self.assertIsNotNone(
            importlib.util.find_spec("scripts.graph_v5.repair"),
            "repair module is missing",
        )
        from scripts.graph_v5.causality import MutationLeaseManager
        from scripts.graph_v5.repair import ProofFact, integrate_repair, propose_repair

        observations = _shared_root_failure_observations()
        self.assertEqual(
            tuple(observation.observed_state for observation in observations),
            ("Profile summary is missing", "Profile history is missing"),
        )
        cone = _closed_cone(observations)
        manager = MutationLeaseManager()
        lease = manager.acquire("profile-cone")
        self.addCleanup(manager.release, lease)
        candidate = propose_repair(
            cone,
            lease=lease,
            patch="fix profile persistence mapping",
            changed_files=("profile_store.py",),
            changed_dependencies=("profile-store",),
            local_validation_receipt="local:test-profile-store:green",
            requested_proof=_bound_proof_spec("profile-summary"),
        )
        plan = integrate_repair(
            candidate,
            lease=lease,
            proofs=(
                ProofFact(
                    proof_id="summary-proof",
                    node_id="profile-summary",
                    dynamic_trace=("profile-store",),
                ),
                ProofFact(
                    proof_id="history-proof",
                    node_id="profile-history",
                    declared_dependencies=("profile-store",),
                ),
                ProofFact(
                    proof_id="unrelated-proof",
                    node_id="settings",
                    declared_dependencies=("settings-store",),
                ),
            ),
            changed_ownership_seams=("profile-store",),
            direct_affected_neighbors=(),
        )
        self.assertEqual(plan.invalidated_proof_ids, ("summary-proof", "history-proof"))
        self.assertEqual(plan.revalidation_node_ids, ("profile-summary", "profile-history"))
        self.assertEqual(candidate.root_lead_id, "profile-persistence-root")
        self.assertEqual(candidate.preserved_observations, observations)
        self.assertFalse(hasattr(plan, "global_reset"))


if __name__ == "__main__":
    unittest.main()
