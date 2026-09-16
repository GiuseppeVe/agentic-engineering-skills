"""Independent review outcome checks. Controller never synthesizes reviews."""

from __future__ import annotations

from .proof import ImportedRoleOutput, ProofLadderError, is_issuer_registered_output
from .models import RunState


class ReviewInfrastructureError(ProofLadderError):
    """Required independent review is unavailable after bounded fresh retries."""


def require_independent_decision(
    output: ImportedRoleOutput,
    *,
    role: str,
    decision: str,
) -> None:
    """Accept one exact imported role output; no controller-generated substitute."""

    if not is_issuer_registered_output(output):
        raise ReviewInfrastructureError("role output must be issuer-registered, not controller-generated")
    if output.dispatch.controller_capability is not False:
        raise ReviewInfrastructureError("controller fallback is forbidden")
    if output.dispatch.manifest.role != role:
        raise ProofLadderError("independent review role does not match required rung")
    if output.decision != decision:
        raise ProofLadderError("independent review decision does not satisfy required rung")


def require_trajectory_authority(output: ImportedRoleOutput, *, state: RunState) -> None:
    """Reject review output if any persisted trajectory/spine authority changes."""

    spine = state.facts.derived_spine
    if spine is None:
        raise ReviewInfrastructureError("review requires persisted Derived Spine authority")
    manifest = output.dispatch.manifest
    if (
        manifest.trajectory_digest != state.trajectory_digest
        or manifest.derived_spine_digest != spine.digest
        or manifest.landmark_mapping_digest != spine.landmark_mapping_digest
    ):
        raise ProofLadderError("review manifest does not bind current trajectory authority")
