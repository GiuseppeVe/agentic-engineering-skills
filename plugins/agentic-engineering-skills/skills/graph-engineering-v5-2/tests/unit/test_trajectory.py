from __future__ import annotations

from decimal import Decimal
import unittest

from pydantic import ValidationError

from scripts.graph_v5.canonical import CanonicalizationError, canonical_json_bytes, digest_bytes
from scripts.graph_v5.models import (
    ConfirmedTrajectoryBundle,
    TrajectoryBrief,
    TrajectoryConfirmation,
)
from scripts.graph_v5.trajectory import (
    TrajectoryValidationError,
    operational_authority_projection,
    render_trajectory_markdown,
    validate_confirmed_trajectory,
)
from tests.support.trajectory import (
    ambiguous_trajectory_payload,
    confirmation_for,
    invalid_duplicate_landmark_payload,
    valid_trajectory_brief,
    valid_trajectory_payload,
)


class TrajectoryBriefContractTests(unittest.TestCase):
    def test_accepts_complete_v1_brief(self) -> None:
        brief = valid_trajectory_brief()
        self.assertEqual(brief.schema_version, "graph-v5.trajectory-brief.v1")
        self.assertEqual([item.landmark_id for item in brief.landmarks], ["L1", "L2"])
        self.assertEqual(
            tuple(brief.model_dump(mode="json")),
            (
                "schema_version",
                "run_id",
                "brief_id",
                "created_at",
                "original_request",
                "test_philosophy",
                "run_rationale",
                "actor",
                "fixture_intent",
                "start_state",
                "landmarks",
                "goal",
                "terminal_outcome",
                "expected_behaviors",
                "non_goals",
                "author_signals",
                "execution_envelope",
                "material_ambiguities",
            ),
        )

    def test_rejects_duplicate_or_unobservable_landmarks(self) -> None:
        with self.assertRaises(ValidationError):
            TrajectoryBrief.model_validate(invalid_duplicate_landmark_payload())

        payload = valid_trajectory_payload()
        payload["landmarks"][0]["acceptance"] = []
        with self.assertRaises(ValidationError):
            TrajectoryBrief.model_validate(payload)

    def test_rejects_unresolved_material_ambiguity_at_confirmation(self) -> None:
        brief = TrajectoryBrief.model_validate(ambiguous_trajectory_payload())
        with self.assertRaisesRegex(TrajectoryValidationError, "material ambiguities"):
            validate_confirmed_trajectory(brief, b"", confirmation_for(brief))

    def test_author_signal_cannot_authorize_repair_or_open_causal_lead(self) -> None:
        brief = valid_trajectory_brief()
        self.assertEqual(brief.author_signals[0].authority, "attention_only")
        self.assertNotIn("author_signals", operational_authority_projection(brief))

    def test_markdown_is_deterministic_projection_and_tampering_fails(self) -> None:
        brief = valid_trajectory_brief()
        rendered = render_trajectory_markdown(brief)
        self.assertEqual(rendered, render_trajectory_markdown(brief))
        with self.assertRaisesRegex(TrajectoryValidationError, "Markdown"):
            validate_confirmed_trajectory(brief, rendered + b"tampered", confirmation_for(brief))

    def test_rejects_unknown_fields_missing_behavior_landmarks_and_unsafe_signals(self) -> None:
        unknown = valid_trajectory_payload()
        unknown["proposed_patch"] = "Change predicate"
        with self.assertRaises(ValidationError):
            TrajectoryBrief.model_validate(unknown)

        missing_landmark = valid_trajectory_payload()
        missing_landmark["expected_behaviors"][0]["applies_to"] = ["L9"]
        with self.assertRaises(ValidationError):
            TrajectoryBrief.model_validate(missing_landmark)

        unsafe_signal = valid_trajectory_payload()
        unsafe_signal["author_signals"][0]["authority"] = "repair_authority"
        with self.assertRaises(ValidationError):
            TrajectoryBrief.model_validate(unsafe_signal)

    def test_rejects_non_observable_start_and_terminal_acceptance(self) -> None:
        start = valid_trajectory_payload()
        start["start_state"]["acceptance"] = []
        with self.assertRaises(ValidationError):
            TrajectoryBrief.model_validate(start)

        terminal = valid_trajectory_payload()
        terminal["terminal_outcome"]["description"] = " "
        with self.assertRaises(ValidationError):
            TrajectoryBrief.model_validate(terminal)

    def test_rejects_non_rfc3339_trajectory_and_confirmation_timestamps(self) -> None:
        payload = valid_trajectory_payload()
        payload["created_at"] = "2026-99-28T09:30:00Z"
        with self.assertRaises(ValidationError):
            TrajectoryBrief.model_validate(payload)

        confirmation = confirmation_for(valid_trajectory_brief()).model_dump(mode="json")
        confirmation["confirmed_at"] = "not-a-timestamp"
        with self.assertRaises(ValidationError):
            TrajectoryConfirmation.model_validate(confirmation)

    def test_confirmation_requires_explicit_matching_run_brief_and_digest(self) -> None:
        brief = valid_trajectory_brief()
        markdown = render_trajectory_markdown(brief)
        confirmation = confirmation_for(brief)

        bundle = validate_confirmed_trajectory(brief, markdown, confirmation)
        self.assertIsInstance(bundle, ConfirmedTrajectoryBundle)

        for field, value in (
            ("run_id", "foreign-run"),
            ("brief_id", "foreign-brief"),
            ("trajectory_digest", "0" * 64),
        ):
            mismatched = confirmation.model_copy(update={field: value})
            with self.assertRaises(TrajectoryValidationError):
                validate_confirmed_trajectory(brief, markdown, mismatched)

        with self.assertRaises(ValidationError):
            TrajectoryConfirmation.model_validate(
                {
                    **confirmation.model_dump(mode="json"),
                    "confirmation_evidence_ref": " ",
                }
            )

    def test_bundle_model_rejects_direct_validation_boundary_bypass(self) -> None:
        brief = valid_trajectory_brief()
        markdown = render_trajectory_markdown(brief)
        confirmation = confirmation_for(brief)

        invalid_bundles = (
            {
                "brief": brief,
                "markdown_utf8": markdown,
                "confirmation": confirmation.model_copy(update={"run_id": "foreign-run"}),
            },
            {
                "brief": brief,
                "markdown_utf8": markdown,
                "confirmation": confirmation.model_copy(
                    update={"trajectory_digest": "0" * 64}
                ),
            },
            {
                "brief": brief,
                "markdown_utf8": markdown + b"tampered",
                "confirmation": confirmation,
            },
        )
        for payload in invalid_bundles:
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                ConfirmedTrajectoryBundle(**payload)

    def test_bundle_model_copy_revalidates_authority_bindings(self) -> None:
        brief = valid_trajectory_brief()
        markdown = render_trajectory_markdown(brief)
        confirmation = confirmation_for(brief)
        bundle = validate_confirmed_trajectory(brief, markdown, confirmation)

        invalid_updates = (
            {"markdown_utf8": markdown + b"tampered"},
            {
                "confirmation": confirmation.model_copy(
                    update={"trajectory_digest": "0" * 64}
                )
            },
        )
        for update in invalid_updates:
            with self.subTest(update=update), self.assertRaises(ValidationError):
                bundle.model_copy(update=update)

    def test_canonical_bytes_are_stable_and_reject_unsupported_numbers(self) -> None:
        payload = {
            "nested": {"unicode": "caf\u00e9", "nullable": None},
            "array": [True, False, "ordered"],
        }
        expected = (
            b'{"array":[true,false,"ordered"],"nested":{"nullable":null,'
            b'"unicode":"caf\xc3\xa9"}}'
        )
        rendered = canonical_json_bytes(payload)
        self.assertEqual(rendered, expected)
        self.assertEqual(digest_bytes("trajectory-brief", rendered), digest_bytes("trajectory-brief", expected))
        with self.assertRaises(CanonicalizationError):
            canonical_json_bytes({"float": 1.0})
        with self.assertRaises(CanonicalizationError):
            canonical_json_bytes({"decimal": Decimal("1.0")})

    def test_complete_v1_brief_has_golden_domain_separated_digest(self) -> None:
        self.assertEqual(
            valid_trajectory_brief().digest,
            "a1a7806edc4512fd6922418d4bc97868afcb41609fc804395b3bc46ab1668dc9",
        )

    def test_philosophy_and_rationale_cannot_create_operational_authority(self) -> None:
        projection = operational_authority_projection(valid_trajectory_brief())
        self.assertNotIn("test_philosophy", projection)
        self.assertNotIn("run_rationale", projection)


if __name__ == "__main__":
    unittest.main()
