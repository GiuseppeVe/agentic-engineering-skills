"""Canonical V1 Trajectory Brief fixtures for focused contract tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from scripts.graph_v5.models import TrajectoryBrief, TrajectoryConfirmation


def valid_trajectory_payload() -> dict[str, Any]:
    return {
        "schema_version": "graph-v5.trajectory-brief.v1",
        "run_id": "run-trajectory-v1",
        "brief_id": "brief-trajectory-v1",
        "created_at": "2026-08-28T09:30:00Z",
        "original_request": "Verify onboarding trajectory without production effects.",
        "test_philosophy": "Prefer observable product outcomes over implementation claims.",
        "run_rationale": "Onboarding regression needs bounded evidence.",
        "actor": {
            "role": "seeded test athlete",
            "identity_constraints": ["synthetic account only"],
        },
        "fixture_intent": {
            "required_state": "Empty disposable onboarding fixture.",
            "reset_expectation": "Reset fixture before replay.",
            "forbidden_data": ["production data", "sensitive personal data"],
        },
        "start_state": {
            "description": "Onboarding form is visible.",
            "acceptance": ["Seeded athlete sees empty onboarding form."],
        },
        "landmarks": [
            {
                "landmark_id": "L1",
                "description": "Discipline selection is visible.",
                "acceptance": ["Athlete can observe selected discipline."],
            },
            {
                "landmark_id": "L2",
                "description": "Profile summary is visible.",
                "acceptance": ["Saved profile summary names selected discipline."],
            },
        ],
        "goal": "Verify seeded onboarding reaches profile summary.",
        "terminal_outcome": {
            "description": "Profile summary is visible for seeded athlete.",
            "acceptance": ["Profile summary shows saved selected discipline."],
        },
        "expected_behaviors": [
            {
                "behavior_id": "B1",
                "statement": "Selecting a valid discipline preserves selection.",
                "applies_to": ["L1"],
            },
            {
                "behavior_id": "B2",
                "statement": "Saving valid onboarding shows profile summary.",
                "applies_to": ["L2"],
            },
        ],
        "non_goals": ["Production account mutation", "Payment verification"],
        "author_signals": [
            {
                "signal_id": "S1",
                "observation": "Author reported intermittent onboarding confusion.",
                "context": "Prior manual testing.",
                "evidence_refs": [],
                "authority": "attention_only",
            }
        ],
        "execution_envelope": {
            "allowed_environment": "seeded-test",
            "allowed_scope": ["onboarding"],
            "allowed_side_effects": ["fixture:user_journey_action"],
            "forbidden_systems": ["production", "payments"],
            "escalation_triggers": ["Any production or payment boundary"],
        },
        "material_ambiguities": [],
    }


def valid_trajectory_brief() -> TrajectoryBrief:
    return TrajectoryBrief.model_validate(valid_trajectory_payload())


def confirmation_for(brief: TrajectoryBrief) -> TrajectoryConfirmation:
    return TrajectoryConfirmation(
        schema_version="graph-v5.trajectory-confirmation.v1",
        run_id=brief.run_id,
        brief_id=brief.brief_id,
        trajectory_digest=brief.digest,
        confirmed_by="user:aleda",
        confirmed_at="2026-08-28T09:35:00Z",
        confirmation_evidence_ref="conversation:explicit-confirmation:1",
    )


def invalid_duplicate_landmark_payload() -> dict[str, Any]:
    payload = deepcopy(valid_trajectory_payload())
    payload["landmarks"].append(deepcopy(payload["landmarks"][0]))
    return payload


def ambiguous_trajectory_payload() -> dict[str, Any]:
    payload = deepcopy(valid_trajectory_payload())
    payload["material_ambiguities"] = ["Whether payment systems are in scope."]
    return payload
