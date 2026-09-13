"""Confirmed Trajectory Brief validation and deterministic review rendering."""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import ValidationError

from .models import (
    ConfirmedTrajectoryBundle,
    ExpectedBehavior,
    Landmark,
    V52TrajectoryBrief,
    V52TrajectoryConfirmation,
    TrajectoryBrief,
    TrajectoryConfirmation,
)


class TrajectoryValidationError(ValueError):
    """A candidate trajectory cannot become runtime authority."""


def _escape_markdown_text(value: str) -> str:
    """Render author-controlled text without letting it alter Markdown structure."""

    escaped = value.replace("\\", "\\\\")
    for character in ("`", "*", "_", "{", "}", "[", "]", "<", ">", "#", "+", "-", "!", "|"):
        escaped = escaped.replace(character, f"\\{character}")
    return escaped.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "  \n")


def _bullet_lines(values: Iterable[str]) -> list[str]:
    return [f"- {_escape_markdown_text(value)}" for value in values]


def _target_lines(target: object) -> list[str]:
    description = _escape_markdown_text(target.description)  # type: ignore[attr-defined]
    acceptance = _bullet_lines(target.acceptance)  # type: ignore[attr-defined]
    return [description, "Acceptance:", *acceptance]


def _landmark_lines(index: int, landmark: Landmark) -> list[str]:
    return [
        f"{index}. **{_escape_markdown_text(landmark.landmark_id)}** — "
        f"{_escape_markdown_text(landmark.description)}",
        "   Acceptance:",
        *[f"   - {_escape_markdown_text(value)}" for value in landmark.acceptance],
    ]


def _behavior_lines(index: int, behavior: ExpectedBehavior) -> list[str]:
    applies_to = ", ".join(_escape_markdown_text(value) for value in behavior.applies_to)
    return [
        f"{index}. **{_escape_markdown_text(behavior.behavior_id)}** — "
        f"{_escape_markdown_text(behavior.statement)}",
        f"   Applies to: {applies_to}",
    ]


def trajectory_markdown_sections(brief: TrajectoryBrief) -> tuple[str, ...]:
    """Render every canonical field in one fixed, non-authoritative order."""

    signals = []
    for index, signal in enumerate(brief.author_signals, start=1):
        evidence = ", ".join(_escape_markdown_text(value) for value in signal.evidence_refs)
        signals.extend(
            (
                f"{index}. **{_escape_markdown_text(signal.signal_id)}** — "
                f"{_escape_markdown_text(signal.observation)}",
                f"   Context: {_escape_markdown_text(signal.context)}",
                f"   Evidence references: {evidence or 'None'}",
                f"   Authority: {_escape_markdown_text(signal.authority)}",
            )
        )

    return (
        "\n".join(
            (
                "# Trajectory Brief",
                f"Schema: {_escape_markdown_text(brief.schema_version)}",
                f"Run ID: {_escape_markdown_text(brief.run_id)}",
                f"Brief ID: {_escape_markdown_text(brief.brief_id)}",
                f"Created at: {_escape_markdown_text(brief.created_at)}",
            )
        ),
        "\n".join(
            (
                "## Context",
                f"Original request: {_escape_markdown_text(brief.original_request)}",
                f"Test philosophy: {_escape_markdown_text(brief.test_philosophy)}",
                f"Run rationale: {_escape_markdown_text(brief.run_rationale)}",
            )
        ),
        "\n".join(
            (
                "## Actor",
                f"Role: {_escape_markdown_text(brief.actor.role)}",
                "Identity constraints:",
                *_bullet_lines(brief.actor.identity_constraints),
            )
        ),
        "\n".join(
            (
                "## Fixture intent",
                f"Required state: {_escape_markdown_text(brief.fixture_intent.required_state)}",
                f"Reset expectation: {_escape_markdown_text(brief.fixture_intent.reset_expectation)}",
                "Forbidden data:",
                *_bullet_lines(brief.fixture_intent.forbidden_data),
            )
        ),
        "\n".join(("## Observable start", *_target_lines(brief.start_state))),
        "\n".join(("## Ordered landmarks", *[
            line
            for index, landmark in enumerate(brief.landmarks, start=1)
            for line in _landmark_lines(index, landmark)
        ])),
        "\n".join(("## Goal", _escape_markdown_text(brief.goal))),
        "\n".join(("## Terminal outcome", *_target_lines(brief.terminal_outcome))),
        "\n".join(("## Expected behaviors", *[
            line
            for index, behavior in enumerate(brief.expected_behaviors, start=1)
            for line in _behavior_lines(index, behavior)
        ])),
        "\n".join(("## Non-goals", *_bullet_lines(brief.non_goals))),
        "\n".join(("## Author Signals", *(signals or ["None"]))),
        "\n".join(
            (
                "## Execution Envelope",
                f"Allowed environment: {_escape_markdown_text(brief.execution_envelope.allowed_environment)}",
                "Allowed scope:",
                *_bullet_lines(brief.execution_envelope.allowed_scope),
                "Allowed side effects:",
                *(_bullet_lines(brief.execution_envelope.allowed_side_effects) or ["- None"]),
                "Forbidden systems:",
                *_bullet_lines(brief.execution_envelope.forbidden_systems),
                "Escalation triggers:",
                *_bullet_lines(brief.execution_envelope.escalation_triggers),
            )
        ),
        "\n".join(
            (
                "## Material ambiguities",
                *(_bullet_lines(brief.material_ambiguities) or ["None"]),
            )
        ),
    )


def render_trajectory_markdown(brief: TrajectoryBrief) -> bytes:
    sections = trajectory_markdown_sections(brief)
    text = "\n\n".join(sections).rstrip() + "\n"
    return text.encode("utf-8")


def operational_authority_projection(brief: TrajectoryBrief) -> dict[str, object]:
    """Return fields with operational authority; context and signals remain non-authoritative."""

    return {
        "run_id": brief.run_id,
        "brief_id": brief.brief_id,
        "actor": brief.actor,
        "fixture_intent": brief.fixture_intent,
        "start_state": brief.start_state,
        "landmarks": brief.landmarks,
        "goal": brief.goal,
        "terminal_outcome": brief.terminal_outcome,
        "expected_behaviors": brief.expected_behaviors,
        "non_goals": brief.non_goals,
        "execution_envelope": brief.execution_envelope,
    }


def _strict_trajectory_brief(brief: object) -> TrajectoryBrief:
    if not isinstance(brief, TrajectoryBrief):
        raise TrajectoryValidationError("Trajectory Brief must be a strict V1 model")
    try:
        return TrajectoryBrief.model_validate(brief.model_dump(mode="json"))
    except ValidationError as exc:
        raise TrajectoryValidationError("invalid Trajectory Brief") from exc


def _strict_confirmation(confirmation: object) -> TrajectoryConfirmation:
    if not isinstance(confirmation, TrajectoryConfirmation):
        raise TrajectoryValidationError("Trajectory confirmation is required")
    try:
        return TrajectoryConfirmation.model_validate(confirmation.model_dump(mode="json"))
    except ValidationError as exc:
        raise TrajectoryValidationError("invalid explicit trajectory confirmation") from exc


def validate_confirmed_trajectory(
    brief: TrajectoryBrief,
    markdown_utf8: bytes,
    confirmation: TrajectoryConfirmation,
) -> ConfirmedTrajectoryBundle:
    """Validate sole bundle boundary accepted by durable Graph-run genesis."""

    strict_brief = _strict_trajectory_brief(brief)
    strict_confirmation = _strict_confirmation(confirmation)
    if not isinstance(markdown_utf8, bytes):
        raise TrajectoryValidationError("Markdown must be exact UTF-8 bytes")
    if strict_brief.material_ambiguities:
        raise TrajectoryValidationError("material ambiguities remain unresolved")
    if (
        strict_confirmation.run_id != strict_brief.run_id
        or strict_confirmation.brief_id != strict_brief.brief_id
    ):
        raise TrajectoryValidationError("confirmation identity mismatch")
    if strict_confirmation.trajectory_digest != strict_brief.digest:
        raise TrajectoryValidationError("confirmation trajectory digest mismatch")
    if markdown_utf8 != render_trajectory_markdown(strict_brief):
        raise TrajectoryValidationError("Markdown differs from canonical trajectory")
    return ConfirmedTrajectoryBundle(
        brief=strict_brief,
        markdown_utf8=markdown_utf8,
        confirmation=strict_confirmation,
    )


def real_operational_authority_projection(brief: V52TrajectoryBrief) -> dict[str, object]:
    """Return only V5.2 real-system authority, including exact manifest binding."""

    if not isinstance(brief, V52TrajectoryBrief):
        raise TrajectoryValidationError("real trajectory must be a strict V5.2 model")
    return {
        "run_id": brief.run_id,
        "brief_id": brief.brief_id,
        "goal": brief.goal,
        "execution_envelope": brief.execution_envelope,
        "adapter_manifest_digest": brief.adapter_manifest_digest,
    }


def validate_confirmed_real_trajectory(
    brief: V52TrajectoryBrief,
    confirmation: V52TrajectoryConfirmation,
) -> tuple[V52TrajectoryBrief, V52TrajectoryConfirmation]:
    """Validate V5.2 confirmation without allowing a V5.1 authority upgrade."""

    if not isinstance(brief, V52TrajectoryBrief):
        raise TrajectoryValidationError("real trajectory must be a strict V5.2 model")
    if not isinstance(confirmation, V52TrajectoryConfirmation):
        raise TrajectoryValidationError("real trajectory confirmation is required")
    try:
        strict_brief = V52TrajectoryBrief.model_validate(brief.model_dump(mode="json"))
        strict_confirmation = V52TrajectoryConfirmation.model_validate(
            confirmation.model_dump(mode="json")
        )
    except ValidationError as exc:
        raise TrajectoryValidationError("invalid real trajectory authority") from exc
    if (
        strict_confirmation.run_id != strict_brief.run_id
        or strict_confirmation.brief_id != strict_brief.brief_id
    ):
        raise TrajectoryValidationError("real trajectory confirmation identity mismatch")
    if strict_confirmation.trajectory_digest != strict_brief.digest:
        raise TrajectoryValidationError("real trajectory confirmation digest mismatch")
    if strict_confirmation.adapter_manifest_digest != strict_brief.adapter_manifest_digest:
        raise TrajectoryValidationError("real trajectory confirmation adapter manifest mismatch")
    return strict_brief, strict_confirmation
