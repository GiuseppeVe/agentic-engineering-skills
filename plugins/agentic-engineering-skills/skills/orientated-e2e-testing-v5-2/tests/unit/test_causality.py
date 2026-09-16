from __future__ import annotations

import unittest
import importlib.util
from dataclasses import replace

from scripts.graph_v5.models import CausalEdge, CausalLead, Observation


def _observation(observation_id: str) -> Observation:
    return Observation(
        observation_id=observation_id,
        node_id="save-profile",
        kind="behavioral",
        observed_state="Profile summary is missing",
        evidence_refs=("fixture:profile",),
        run_head_digest="a" * 64,
    )


def _lead(
    lead_id: str,
    source_observation_id: str,
    disposition: str = "supported_cause",
) -> CausalLead:
    return CausalLead(
        lead_id=lead_id,
        source_observation_id=source_observation_id,
        subject=lead_id,
        disposition=disposition,
        evidence_refs=(f"evidence:{lead_id}",),
    )


class CausalConeTests(unittest.TestCase):
    def test_closure_requires_every_observed_lead_to_have_source_and_terminal_disposition(self) -> None:
        self.assertIsNotNone(
            importlib.util.find_spec("scripts.graph_v5.causality"),
            "causality module is missing",
        )
        from scripts.graph_v5.causality import CausalCone, CausalityError, DiscoveryReview

        observation = _observation("observation-1")
        unknown_source = _lead("unknown-source", "not-recorded")
        open_lead = _lead("open-lead", observation.observation_id, "open")
        cone = CausalCone(
            cone_id="cone-1",
            node_id="save-profile",
            observations=(observation,),
            leads=(unknown_source, open_lead),
            edges=(),
            required_variant_ids=("primary",),
            completed_variant_ids=("primary",),
            material_seam_receipts=("seam:persistence",),
            discovery_limit_remaining=1,
            discovery_review=DiscoveryReview(
                reviewer_id="discovery-reviewer-1",
                attests_no_material_omission=True,
            ),
        )

        with self.assertRaisesRegex(CausalityError, "source Observation"):
            cone.close()

        sourced_open = cone.with_leads((_lead("open-lead", observation.observation_id, "open"),))
        with self.assertRaisesRegex(CausalityError, "observed-lead queue"):
            sourced_open.close()

    def test_typed_edges_require_exact_deterministic_basis_and_complete_semantic_evidence(self) -> None:
        self.assertIsNotNone(
            importlib.util.find_spec("scripts.graph_v5.causality"),
            "causality module is missing",
        )
        from scripts.graph_v5.causality import CausalCone, CausalityError

        observation = _observation("observation-1")
        root = _lead("persistence-root", observation.observation_id)
        symptom = _lead("profile-summary", observation.observation_id, "supported_symptom")
        deterministic = CausalEdge(
            edge_id="dependency-1",
            from_lead_id=root.lead_id,
            to_lead_id=symptom.lead_id,
            relation="recorded_dependency",
            basis="trace:persistence-write -> profile-reader",
        )
        semantic = CausalEdge(
            edge_id="symptom-1",
            from_lead_id=root.lead_id,
            to_lead_id=symptom.lead_id,
            relation="supports_symptom",
            evidence_refs=("proof:profile-missing",),
            confidence=90,
            risk="medium",
            requires_independent_attestation=True,
        )
        CausalCone(
            cone_id="cone-typed",
            node_id="save-profile",
            observations=(observation,),
            leads=(root, symptom),
            edges=(deterministic, semantic),
        ).validate_graph()

        missing_basis = deterministic.model_copy(update={"basis": None})
        with self.assertRaisesRegex(CausalityError, "exact basis"):
            CausalCone(
                cone_id="cone-missing-basis",
                node_id="save-profile",
                observations=(observation,),
                leads=(root, symptom),
                edges=(missing_basis,),
            ).validate_graph()

        missing_attestation = semantic.model_copy(
            update={"requires_independent_attestation": False}
        )
        with self.assertRaisesRegex(CausalityError, "independent attestation"):
            CausalCone(
                cone_id="cone-missing-attestation",
                node_id="save-profile",
                observations=(observation,),
                leads=(root, symptom),
                edges=(missing_attestation,),
            ).validate_graph()

    def test_closure_requires_variants_seams_discovery_capacity_and_independent_review(self) -> None:
        self.assertIsNotNone(
            importlib.util.find_spec("scripts.graph_v5.causality"),
            "causality module is missing",
        )
        from scripts.graph_v5.causality import (
            CausalCone,
            CausalityError,
            ConeHop,
            DiscoveryReview,
            MaterialSeamReceipt,
        )

        before = _observation("observation-before")
        after = _observation("observation-after")
        root = _lead("persistence-root", before.observation_id)
        symptom = _lead("profile-symptom", after.observation_id, "supported_symptom")
        base = dict(
            cone_id="cone-closure",
            node_id="save-profile",
            observations=(before, after),
            leads=(root, symptom),
            edges=(
                CausalEdge(
                    edge_id="root-symptom",
                    from_lead_id=root.lead_id,
                    to_lead_id=symptom.lead_id,
                    relation="supports_symptom",
                    evidence_refs=("proof:root",),
                    confidence=95,
                    risk="medium",
                    requires_independent_attestation=True,
                ),
            ),
            required_variant_ids=("primary", "refresh"),
            completed_variant_ids=("primary",),
            required_material_seam_ids=("persistence",),
            material_seam_receipts=(),
            discovery_limit_remaining=0,
            discovery_review=None,
            candidates=(ConeHop("root", "state_owner", root.lead_id, "root-symptom"),),
        )
        with self.assertRaisesRegex(CausalityError, "required variants"):
            CausalCone(**base).close()
        ready_without_receipt = CausalCone(
            **{
                **base,
                "completed_variant_ids": ("primary", "refresh"),
                "discovery_limit_remaining": 1,
                "discovery_review": DiscoveryReview(
                    reviewer_id="discovery-reviewer-1",
                    attests_no_material_omission=True,
                ),
            }
        )
        ready = replace(
            ready_without_receipt,
            material_seam_receipts=(
                MaterialSeamReceipt(
                    seam_id="persistence",
                    cone_id="cone-closure",
                    node_id="save-profile",
                    before_observation_id=before.observation_id,
                    after_observation_id=after.observation_id,
                    evidence_refs=("proof:persistence-write",),
                ),
            ),
        )
        frozen = ready.freeze_expansion(diagnostics_implicate_runtime=False)
        closed = ready.close(frozen)
        self.assertEqual(closed.cone_id, ready.cone_id)

    def test_closure_rejects_unmatched_or_unbound_material_seam_receipts(self) -> None:
        from scripts.graph_v5.causality import (
            CausalCone,
            CausalityError,
            ConeHop,
            DiscoveryReview,
            MaterialSeamReceipt,
        )

        before = _observation("before-observation")
        after = _observation("after-observation")
        root = _lead("persistence-root", before.observation_id)
        base = CausalCone(
            cone_id="cone-material-seam",
            node_id="save-profile",
            observations=(before, after),
            leads=(root,),
            required_variant_ids=("primary",),
            completed_variant_ids=("primary",),
            required_material_seam_ids=("persistence",),
            discovery_limit_remaining=1,
            discovery_review=DiscoveryReview("discovery-reviewer-1", True),
            candidates=(ConeHop("root", "state_owner", lead_id=root.lead_id),),
        )
        frozen = base.freeze_expansion(diagnostics_implicate_runtime=False)

        unmatched = MaterialSeamReceipt(
            seam_id="cache",
            cone_id=base.cone_id,
            node_id=base.node_id,
            before_observation_id=before.observation_id,
            after_observation_id=after.observation_id,
            evidence_refs=("proof:cache",),
        )
        with self.assertRaisesRegex(CausalityError, "required material seam"):
            replace(base, material_seam_receipts=(unmatched,)).close(frozen)

        wrong_cone = MaterialSeamReceipt(
            seam_id="persistence",
            cone_id="another-cone",
            node_id=base.node_id,
            before_observation_id=before.observation_id,
            after_observation_id=after.observation_id,
            evidence_refs=("proof:persistence",),
        )
        with self.assertRaisesRegex(CausalityError, "current cone and Behavioral Node"):
            replace(base, material_seam_receipts=(wrong_cone,)).close(frozen)

        unbound = MaterialSeamReceipt(
            seam_id="persistence",
            cone_id=base.cone_id,
            node_id=base.node_id,
            before_observation_id=before.observation_id,
            after_observation_id="missing-observation",
            evidence_refs=("proof:persistence",),
        )
        with self.assertRaisesRegex(CausalityError, "before/after Observation"):
            replace(base, material_seam_receipts=(unbound,)).close(frozen)

        with self.assertRaisesRegex(CausalityError, "evidence"):
            MaterialSeamReceipt(
                seam_id="persistence",
                cone_id=base.cone_id,
                node_id=base.node_id,
                before_observation_id=before.observation_id,
                after_observation_id=after.observation_id,
                evidence_refs=(" ",),
            )

    def test_closure_rejects_proofless_terminal_lead_and_blank_seam_receipt(self) -> None:
        from scripts.graph_v5.causality import CausalCone, CausalityError, DiscoveryReview

        observation = _observation("observation-1")
        proofless = CausalLead(
            lead_id="proofless-root",
            source_observation_id=observation.observation_id,
            subject="persistence mapping",
            disposition="supported_cause",
            evidence_refs=(),
        )
        base = dict(
            cone_id="cone-proof-backed",
            node_id="save-profile",
            observations=(observation,),
            required_variant_ids=("primary",),
            completed_variant_ids=("primary",),
            required_material_seam_ids=("persistence",),
            discovery_limit_remaining=1,
            discovery_review=DiscoveryReview("discovery-reviewer-1", True),
        )

        with self.assertRaisesRegex(CausalityError, "proof-backed disposition"):
            CausalCone(
                **base,
                leads=(proofless,),
                material_seam_receipts=("seam:persistence",),
            ).close()

        with self.assertRaisesRegex(CausalityError, "material seam receipt"):
            CausalCone(
                **base,
                leads=(_lead("root", observation.observation_id),),
                material_seam_receipts=(" ",),
            ).close()

    def test_frozen_expansion_prioritizes_root_and_excludes_runtime_without_diagnostics(self) -> None:
        self.assertIsNotNone(
            importlib.util.find_spec("scripts.graph_v5.causality"),
            "causality module is missing",
        )
        from scripts.graph_v5.causality import CausalCone, ConeHop

        observation = _observation("observation-1")
        root = _lead("persistence-root", observation.observation_id)
        summary = _lead("profile-summary", observation.observation_id, "supported_symptom")
        history = _lead("profile-history", observation.observation_id, "supported_symptom")
        cone = CausalCone(
            cone_id="cone-expansion",
            node_id="save-profile",
            observations=(observation,),
            leads=(root, summary, history),
            edges=(
                CausalEdge(
                    edge_id="root-summary",
                    from_lead_id=root.lead_id,
                    to_lead_id=summary.lead_id,
                    relation="supports_symptom",
                    evidence_refs=("proof:summary",),
                    confidence=95,
                    risk="medium",
                    requires_independent_attestation=True,
                ),
                CausalEdge(
                    edge_id="root-history",
                    from_lead_id=root.lead_id,
                    to_lead_id=history.lead_id,
                    relation="supports_symptom",
                    evidence_refs=("proof:history",),
                    confidence=95,
                    risk="medium",
                    requires_independent_attestation=True,
                ),
            ),
            candidates=(
                ConeHop("runtime", "config_runtime"),
                ConeHop("consumer", "downstream_consumer"),
                ConeHop("root", "state_owner", lead_id=root.lead_id, edge_id="root-summary"),
                ConeHop("boundary", "failure_action"),
                ConeHop("adjacent", "adjacent_behavior"),
            ),
        )

        frozen = cone.freeze_expansion(diagnostics_implicate_runtime=False)
        self.assertEqual(
            tuple(hop.hop_id for hop in frozen.ordered_candidates),
            ("boundary", "root", "consumer", "adjacent"),
        )
        self.assertEqual(frozen.selected_hop_id, "root")
        self.assertEqual(frozen.selected_edge_id, "root-summary")
        self.assertEqual(frozen.selected_lead_id, root.lead_id)

    def test_frozen_expansion_selects_upstream_supported_root_over_downstream_supported_cause(self) -> None:
        from scripts.graph_v5.causality import CausalCone, ConeHop

        observation = _observation("observation-1")
        root = _lead("root", observation.observation_id)
        downstream = _lead("downstream", observation.observation_id)
        cone = CausalCone(
            cone_id="cone-upstream-root",
            node_id="save-profile",
            observations=(observation,),
            leads=(downstream, root),
            edges=(
                CausalEdge(
                    edge_id="root-downstream",
                    from_lead_id=root.lead_id,
                    to_lead_id=downstream.lead_id,
                    relation="supports_cause",
                    evidence_refs=("proof:root-downstream",),
                    confidence=95,
                    risk="medium",
                    requires_independent_attestation=True,
                ),
            ),
            candidates=(
                ConeHop("downstream", "failure_action", downstream.lead_id),
                ConeHop("root", "state_owner", root.lead_id, "root-downstream"),
            ),
        )

        frozen = cone.freeze_expansion(diagnostics_implicate_runtime=False)
        self.assertEqual(frozen.selected_lead_id, root.lead_id)
        self.assertEqual(frozen.selected_hop_id, "root")

    def test_closed_handoff_revalidates_frozen_supported_root(self) -> None:
        from scripts.graph_v5.causality import (
            CausalCone,
            CausalityError,
            ClosedCausalCone,
            ConeHop,
            DiscoveryReview,
            MaterialSeamReceipt,
        )

        before = _observation("before-observation")
        after = _observation("after-observation")
        root = _lead("persistence-root", before.observation_id)
        symptom = _lead("profile-symptom", after.observation_id, "supported_symptom")
        cone = CausalCone(
            cone_id="cone-frozen-handoff",
            node_id="save-profile",
            observations=(before, after),
            leads=(root, symptom),
            edges=(
                CausalEdge(
                    edge_id="root-symptom",
                    from_lead_id=root.lead_id,
                    to_lead_id=symptom.lead_id,
                    relation="supports_symptom",
                    evidence_refs=("proof:root",),
                    confidence=95,
                    risk="medium",
                    requires_independent_attestation=True,
                ),
            ),
            required_variant_ids=("primary",),
            completed_variant_ids=("primary",),
            required_material_seam_ids=("persistence",),
            material_seam_receipts=(
                MaterialSeamReceipt(
                    seam_id="persistence",
                    cone_id="cone-frozen-handoff",
                    node_id="save-profile",
                    before_observation_id=before.observation_id,
                    after_observation_id=after.observation_id,
                    evidence_refs=("proof:persistence",),
                ),
            ),
            discovery_limit_remaining=1,
            discovery_review=DiscoveryReview("discovery-reviewer-1", True),
            candidates=(ConeHop("root", "state_owner", root.lead_id, "root-symptom"),),
        )
        frozen = cone.freeze_expansion(diagnostics_implicate_runtime=False)
        closed = cone.close(frozen)
        self.assertEqual(closed.frozen_expansion.selected_lead_id, root.lead_id)

        forged = replace(frozen, selected_lead_id=symptom.lead_id)
        with self.assertRaisesRegex(CausalityError, "frozen expansion"):
            ClosedCausalCone(cone, forged)

    def test_closed_handoff_rejects_missing_or_unrelated_selected_semantic_edge(self) -> None:
        from scripts.graph_v5.causality import (
            CausalCone,
            CausalityError,
            ConeHop,
            DiscoveryReview,
            MaterialSeamReceipt,
        )

        before = _observation("selected-edge-before")
        after = _observation("selected-edge-after")
        root = _lead("selected-root", before.observation_id)
        symptom = _lead("selected-symptom", after.observation_id, "supported_symptom")
        unrelated_root = _lead("unrelated-root", before.observation_id)
        shared = dict(
            cone_id="cone-selected-edge",
            node_id="save-profile",
            observations=(before, after),
            required_variant_ids=("primary",),
            completed_variant_ids=("primary",),
            required_material_seam_ids=("persistence",),
            material_seam_receipts=(
                MaterialSeamReceipt(
                    seam_id="persistence",
                    cone_id="cone-selected-edge",
                    node_id="save-profile",
                    before_observation_id=before.observation_id,
                    after_observation_id=after.observation_id,
                    evidence_refs=("proof:persistence",),
                ),
            ),
            discovery_limit_remaining=1,
            discovery_review=DiscoveryReview("discovery-reviewer-1", True),
        )

        missing_edge = CausalCone(
            **shared,
            leads=(root, symptom),
            edges=(
                CausalEdge(
                    edge_id="root-symptom",
                    from_lead_id=root.lead_id,
                    to_lead_id=symptom.lead_id,
                    relation="supports_symptom",
                    evidence_refs=("proof:root",),
                    confidence=95,
                    risk="medium",
                    requires_independent_attestation=True,
                ),
            ),
            candidates=(ConeHop("root", "state_owner", root.lead_id),),
        )
        with self.assertRaisesRegex(CausalityError, "selected semantic edge"):
            missing_edge.close(missing_edge.freeze_expansion(diagnostics_implicate_runtime=False))

        unrelated_edge = CausalCone(
            **shared,
            leads=(root, symptom, unrelated_root),
            edges=(
                CausalEdge(
                    edge_id="root-symptom",
                    from_lead_id=root.lead_id,
                    to_lead_id=symptom.lead_id,
                    relation="supports_symptom",
                    evidence_refs=("proof:root",),
                    confidence=95,
                    risk="medium",
                    requires_independent_attestation=True,
                ),
                CausalEdge(
                    edge_id="unrelated-symptom",
                    from_lead_id=unrelated_root.lead_id,
                    to_lead_id=symptom.lead_id,
                    relation="supports_symptom",
                    evidence_refs=("proof:unrelated",),
                    confidence=95,
                    risk="medium",
                    requires_independent_attestation=True,
                ),
            ),
            candidates=(
                ConeHop("root", "state_owner", root.lead_id, "unrelated-symptom"),
            ),
        )
        with self.assertRaisesRegex(CausalityError, "selected semantic edge"):
            unrelated_edge.close(
                unrelated_edge.freeze_expansion(diagnostics_implicate_runtime=False)
            )

    def test_probe_receipts_bind_immutable_cone_and_frozen_expansion(self) -> None:
        from scripts.graph_v5.causality import CausalCone, CausalityError, ConeHop, ProbeIsolationReceipt

        before = _observation("probe-before")
        after = _observation("probe-after")
        root = _lead("probe-root", before.observation_id)
        symptom = _lead("probe-symptom", after.observation_id, "supported_symptom")
        edge = CausalEdge(
            edge_id="probe-root-symptom",
            from_lead_id=root.lead_id,
            to_lead_id=symptom.lead_id,
            relation="supports_symptom",
            evidence_refs=("proof:probe",),
            confidence=95,
            risk="medium",
            requires_independent_attestation=True,
        )
        cone = CausalCone(
            cone_id="cone-probe-digest",
            node_id="save-profile",
            observations=(before, after),
            leads=(root, symptom),
            edges=(edge,),
            candidates=(ConeHop("root", "state_owner", root.lead_id, edge.edge_id),),
        )
        frozen = cone.freeze_expansion(diagnostics_implicate_runtime=False)
        self.assertTrue(hasattr(cone, "digest"), "causal cone needs an immutable canonical digest")
        self.assertTrue(hasattr(frozen, "digest"), "frozen expansion needs an immutable canonical digest")
        self.assertEqual(frozen.cone_digest, cone.digest)

        receipt = ProbeIsolationReceipt(
            probe_id="probe-1",
            cone_id=cone.cone_id,
            cone_digest=cone.digest,
            frozen_expansion_digest=frozen.digest,
            frozen_hop_id="root",
            frozen_hop_index=0,
            fixture_id="fixture-a",
            process_id="process-a",
            read_only=True,
            fixture_isolated=True,
            process_isolated=True,
            non_interference_attested=True,
        )
        cone.authorize_parallel_read_only_probes(frozen, (receipt,))

        changed_cones = (
            replace(cone, node_id="profile-history"),
            replace(cone, observations=(before.model_copy(update={"observed_state": "changed"}), after)),
            replace(cone, leads=(root.model_copy(update={"subject": "changed"}), symptom)),
            replace(cone, edges=(edge.model_copy(update={"confidence": 80}),)),
            replace(
                cone,
                candidates=(ConeHop("root", "failure_action", root.lead_id, edge.edge_id),),
            ),
        )
        for changed_cone in changed_cones:
            changed_frozen = changed_cone.freeze_expansion(diagnostics_implicate_runtime=False)
            with self.assertRaisesRegex(CausalityError, "immutable causal cone"):
                changed_cone.authorize_parallel_read_only_probes(changed_frozen, (receipt,))

        changed_selection = replace(frozen, selected_edge_id=None)
        with self.assertRaisesRegex(CausalityError, "frozen expansion"):
            cone.authorize_parallel_read_only_probes(changed_selection, (receipt,))

    def test_parallel_read_only_probes_need_fixture_and_process_noninterference_receipts(self) -> None:
        self.assertIsNotNone(
            importlib.util.find_spec("scripts.graph_v5.causality"),
            "causality module is missing",
        )
        from scripts.graph_v5.causality import CausalCone, CausalityError, ConeHop, ProbeIsolationReceipt

        cone = CausalCone(
            cone_id="cone-probes",
            node_id="save-profile",
            candidates=(ConeHop("probe-boundary", "failure_action"),),
        )
        frozen = cone.freeze_expansion(diagnostics_implicate_runtime=False)
        missing_receipt = ProbeIsolationReceipt(
            probe_id="probe-1",
            cone_id="cone-probes",
            cone_digest=cone.digest,
            frozen_expansion_digest=frozen.digest,
            frozen_hop_id="probe-boundary",
            frozen_hop_index=0,
            fixture_id="fixture-a",
            process_id="process-a",
            read_only=False,
            fixture_isolated=False,
            process_isolated=True,
            non_interference_attested=True,
        )
        with self.assertRaisesRegex(CausalityError, "isolation receipt"):
            cone.authorize_parallel_read_only_probes(frozen, (missing_receipt,))

        receipts = (
            ProbeIsolationReceipt(
                probe_id="probe-1",
                cone_id="cone-probes",
                cone_digest=cone.digest,
                frozen_expansion_digest=frozen.digest,
                frozen_hop_id="probe-boundary",
                frozen_hop_index=0,
                fixture_id="fixture-a",
                process_id="process-a",
                read_only=True,
                fixture_isolated=True,
                process_isolated=True,
                non_interference_attested=True,
            ),
            ProbeIsolationReceipt(
                probe_id="probe-2",
                cone_id="cone-probes",
                cone_digest=cone.digest,
                frozen_expansion_digest=frozen.digest,
                frozen_hop_id="probe-boundary",
                frozen_hop_index=0,
                fixture_id="fixture-b",
                process_id="process-b",
                read_only=True,
                fixture_isolated=True,
                process_isolated=True,
                non_interference_attested=True,
            ),
        )
        cone.authorize_parallel_read_only_probes(frozen, receipts)
        wrong_hop = replace(receipts[0], frozen_hop_index=1)
        with self.assertRaisesRegex(CausalityError, "ordered frozen hop"):
            cone.authorize_parallel_read_only_probes(frozen, (wrong_hop,))
        wrong_cone = replace(receipts[0], cone_id="other-cone")
        with self.assertRaisesRegex(CausalityError, "frozen causal cone"):
            cone.authorize_parallel_read_only_probes(frozen, (wrong_cone,))
        with self.assertRaisesRegex(CausalityError, "frozen expansion"):
            cone.authorize_parallel_read_only_probes(object(), receipts)
        shared_isolation = replace(receipts[1], fixture_id="fixture-a", process_id="process-a")
        with self.assertRaisesRegex(CausalityError, "distinct fixture/process"):
            cone.authorize_parallel_read_only_probes(frozen, (receipts[0], shared_isolation))


if __name__ == "__main__":
    unittest.main()
