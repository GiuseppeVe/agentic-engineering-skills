from __future__ import annotations

import json
import unittest
from dataclasses import replace

from scripts.graph_v5.causality import CausalCone
from scripts.graph_v5.proof import (
    FinalReplaySnapshot,
    ProofLadderError,
    RoleDispatch,
    RoleRegistry,
    require_exact_issuer_output,
)
from scripts.graph_v5.review import require_trajectory_authority
from tests.unit.test_runtime_limits import _proof_spec, _state


class ProofReviewTests(unittest.TestCase):
    def _issued_output(self) -> tuple[object, object, object, object]:
        state = _state(f"proof-review:{self._testMethodName}")
        proof_spec = _proof_spec(state)
        cone = CausalCone(cone_id="profile-cone", node_id=proof_spec.node_id)
        registry = RoleRegistry()
        dispatch = registry.issue(
            state=state,
            cone=cone,
            proof_spec=proof_spec,
            role="validator",
            identity=f"validator:{self._testMethodName}",
            context_id=f"context:{self._testMethodName}",
            attempt=1,
            permitted_output_schema="proof-role-output-v1",
        )
        output = registry.import_unchanged(
            dispatch,
            json.dumps({"decision": "green"}, separators=(",", ":"), sort_keys=True).encode("utf-8"),
            environment_digest=state.facts.environment.digest,  # type: ignore[union-attr]
        )
        return state, proof_spec, cone, output

    def test_role_manifest_and_proof_spec_bind_trajectory_spine_and_mapping(self) -> None:
        state, proof_spec, cone, output = self._issued_output()
        spine = state.facts.derived_spine
        assert spine is not None
        manifest = output.dispatch.manifest
        self.assertEqual(proof_spec.trajectory_digest, state.trajectory_digest)
        self.assertEqual(proof_spec.derived_spine_digest, spine.digest)
        self.assertEqual(proof_spec.landmark_mapping_digest, spine.landmark_mapping_digest)
        self.assertEqual(manifest.trajectory_digest, state.trajectory_digest)
        self.assertEqual(manifest.derived_spine_digest, spine.digest)
        self.assertEqual(manifest.landmark_mapping_digest, spine.landmark_mapping_digest)
        require_exact_issuer_output(
            output,
            state=state,
            cone=cone,
            proof_spec=proof_spec,
            role="validator",
            permitted_output_schema="proof-role-output-v1",
            issued_mode="running",
        )

    def test_proof_spec_digest_substitution_cannot_issue_independent_role(self) -> None:
        state = _state(f"proof-review:unbound:{self._testMethodName}")
        proof_spec = _proof_spec(state)
        for field_name in (
            "trajectory_digest",
            "derived_spine_digest",
            "landmark_mapping_digest",
        ):
            with self.subTest(field_name=field_name):
                forged = proof_spec.model_copy(update={field_name: f"foreign:{field_name}"})
                with self.assertRaisesRegex(ProofLadderError, "does not bind current trajectory authority"):
                    RoleRegistry().issue(
                        state=state,
                        cone=CausalCone(cone_id=f"unbound-cone:{field_name}", node_id="save-profile"),
                        proof_spec=forged,
                        role="validator",
                        identity=f"validator:unbound:{field_name}:{self._testMethodName}",
                        context_id=f"context:unbound:{field_name}:{self._testMethodName}",
                        attempt=1,
                        permitted_output_schema="proof-role-output-v1",
                    )

    def test_review_rejects_manifest_with_foreign_trajectory_authority(self) -> None:
        state, _, _, output = self._issued_output()
        for field_name in (
            "trajectory_digest",
            "derived_spine_digest",
            "landmark_mapping_digest",
        ):
            with self.subTest(field_name=field_name):
                manifest = output.dispatch.manifest.model_copy(
                    update={field_name: f"foreign:{field_name}"}
                )
                forged_dispatch = RoleDispatch(
                    manifest=manifest,
                    spine_digest=output.dispatch.spine_digest,
                    context_id=output.dispatch.context_id,
                    issued_mode=output.dispatch.issued_mode,
                )
                forged_output = replace(
                    output,
                    dispatch=forged_dispatch,
                    issued_manifest_digest=manifest.digest,
                )
                with self.assertRaisesRegex(ProofLadderError, "does not bind current trajectory authority"):
                    require_trajectory_authority(forged_output, state=state)

    def test_final_snapshot_uses_persisted_derived_spine_authority(self) -> None:
        state = _state(f"proof-review:snapshot:{self._testMethodName}")
        spine = state.facts.derived_spine
        assert spine is not None
        snapshot = FinalReplaySnapshot.from_state(state, graph_revision=3)
        self.assertEqual(snapshot.trajectory_digest, state.trajectory_digest)
        self.assertEqual(snapshot.derived_spine_digest, spine.digest)
        self.assertEqual(snapshot.landmark_mapping_digest, spine.landmark_mapping_digest)

    def test_store_rejects_each_substituted_persisted_authority_digest(self) -> None:
        from scripts.graph_v5.models import (
            ChangeClassificationArtifact,
            ConeIdentityBinding,
            RoleManifest,
        )
        from scripts.graph_v5.store import StoreError, TransactionalRunStore

        state = _state(f"proof-review:store-substitution:{self._testMethodName}")
        spine = state.facts.derived_spine
        run_head = state.facts.run_head
        environment = state.facts.environment
        assert spine is not None and run_head is not None and environment is not None
        proof_spec = _proof_spec(state)
        cone = CausalCone(cone_id="persisted-authority-cone", node_id=proof_spec.node_id)
        manifest = RoleManifest(
            manifest_id="persisted-authority-reviewer",
            role="independent_change_reviewer",
            identity="reviewer:persisted-authority",
            attempt=1,
            goal_digest=state.trajectory_digest,
            cone_digest=cone.digest,
            base_revision=run_head.revision,
            run_head_digest=run_head.digest,
            environment_digest=environment.digest,
            fixture_digest=state.fixture_intent_digest,
            proof_spec_digest="change-classification-v1",
            permitted_output_schema="change-classification-v1",
            trajectory_digest=state.trajectory_digest,
            derived_spine_digest=spine.digest,
            landmark_mapping_digest=spine.landmark_mapping_digest,
        )
        classification = ChangeClassificationArtifact(
            artifact_id="classification:persisted-authority",
            reviewer_id=manifest.identity,
            reviewer_role="independent_change_reviewer",
            reviewer_manifest_id=manifest.manifest_id,
            reviewer_manifest_digest=manifest.digest,
            change_kind="conformance",
            run_id=state.run_id,
            node_id=proof_spec.node_id,
            cone_id=cone.cone_id,
            cone_digest=cone.digest,
            goal_digest=state.trajectory_digest,
            envelope_digest=state.trajectory.execution_envelope.digest,
            repair_hypothesis="persist exact authority bindings",
            changed_dependencies=("profile-store",),
            changed_files=("profile_store.py",),
            trajectory_digest=state.trajectory_digest,
            derived_spine_digest=spine.digest,
            landmark_mapping_digest=spine.landmark_mapping_digest,
        )
        binding = ConeIdentityBinding(
            run_id=state.run_id,
            node_id=proof_spec.node_id,
            cone_id=cone.cone_id,
        )
        exact_facts = state.facts.model_copy(
            update={
                "proof_specs": (proof_spec,),
                "role_manifests": (manifest,),
                "change_classification_artifacts": (classification,),
                "cone_identity_bindings": (binding,),
            }
        )
        TransactionalRunStore._validate_successor(
            state,
            state.model_copy(update={"facts": exact_facts}),
        )

        for fact_field, value in (
            ("proof_specs", proof_spec),
            ("role_manifests", manifest),
            ("change_classification_artifacts", classification),
        ):
            for digest_field in (
                "trajectory_digest",
                "derived_spine_digest",
                "landmark_mapping_digest",
            ):
                with self.subTest(fact_field=fact_field, digest_field=digest_field):
                    forged = value.model_copy(update={digest_field: "f" * 64})
                    forged_facts = exact_facts.model_copy(update={fact_field: (forged,)})
                    with self.assertRaisesRegex(StoreError, "trajectory authority"):
                        TransactionalRunStore._validate_successor(
                            state,
                            state.model_copy(update={"facts": forged_facts}),
                        )


if __name__ == "__main__":
    unittest.main()
