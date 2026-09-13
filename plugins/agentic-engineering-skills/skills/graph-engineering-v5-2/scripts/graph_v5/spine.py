"""Bounded observable-spine traversal for V5.0 user journeys."""

from __future__ import annotations

from dataclasses import dataclass

from .adapters.user_journey import (
    ActionReceipt,
    OperationalObservation,
)
from .canonical import digest_for
from .models import (
    DerivedBehavioralNode,
    DerivedSpine,
    LandmarkVerification,
    NodeProposal,
    Observation,
    TrajectoryBrief,
    RunHead,
    validate_sealed_node_context,
)


class TraversalError(ValueError):
    """Traversal input or adapter violates V5's observable-spine boundary."""


@dataclass(frozen=True, slots=True)
class NodeVerified:
    """Immutable proof that one node is green on current sealed inputs."""

    node_id: str
    node_index: int
    next_node_id: str | None
    observations: tuple[Observation, ...]
    action_receipts: tuple[ActionReceipt, ...]
    seam_receipts: tuple[OperationalObservation, ...]
    selected_variant_ids: tuple[str, ...]
    run_head_digest: str
    snapshot_digest: str


@dataclass(frozen=True, slots=True)
class ObservedFailure:
    """Immutable observed discrepancy; it does not choose a cause or repair."""

    node_id: str
    node_index: int
    failure_code: str
    observations: tuple[Observation, ...]
    action_receipts: tuple[ActionReceipt, ...]
    seam_receipts: tuple[OperationalObservation, ...]
    selected_variant_ids: tuple[str, ...]
    run_head_digest: str
    snapshot_digest: str


class ObservableSpine:
    """Only runtime sealing boundary for one evidence-derived next node."""

    def __init__(
        self,
        trajectory: TrajectoryBrief,
        spine: DerivedSpine,
        *,
        current_run_head: RunHead,
        accepted_observations: tuple[Observation, ...],
    ) -> None:
        if not isinstance(trajectory, TrajectoryBrief):
            raise TraversalError("Observable Spine requires confirmed Trajectory Brief")
        if not isinstance(spine, DerivedSpine):
            raise TraversalError("Observable Spine requires strict Derived Spine")
        try:
            spine.bind_trajectory(trajectory)
        except ValueError as exc:
            raise TraversalError("Derived Spine does not bind confirmed trajectory") from exc
        if not isinstance(current_run_head, RunHead):
            raise TraversalError("Observable Spine requires canonical current Run Head")
        if not isinstance(accepted_observations, tuple) or not all(
            isinstance(item, Observation) for item in accepted_observations
        ):
            raise TraversalError("accepted observations must be immutable Observations")
        self._trajectory = trajectory
        self._spine = spine
        self._current_run_head = current_run_head
        self._accepted_observations = accepted_observations

    @property
    def spine(self) -> DerivedSpine:
        return self._spine

    def seal_next(
        self,
        *,
        entry_observation: Observation | None,
        proposal: NodeProposal | LandmarkVerification,
    ) -> DerivedBehavioralNode:
        """Seal exactly one evidence- and authority-bound action before execution."""

        if entry_observation is None:
            raise TraversalError("entry observation is required before first node sealing")
        if not isinstance(entry_observation, Observation):
            raise TraversalError("entry observation must be immutable Observation")
        if entry_observation.kind != "behavioral":
            raise TraversalError("entry observation must be behavioral")
        if entry_observation.run_head_digest != self._current_run_head.digest:
            raise TraversalError("entry observation does not bind current Run Head")
        if entry_observation not in self._accepted_observations:
            raise TraversalError("entry observation is not accepted evidence")
        if not entry_observation.evidence_refs:
            raise TraversalError("entry observation requires immutable evidence reference")
        if not isinstance(proposal, NodeProposal):
            raise TraversalError("next node requires strict NodeProposal")
        if self._spine.frontier.unexecuted_node_id is not None:
            raise TraversalError("frontier already has one unexecuted sealed node")
        if not self._trajectory.execution_envelope.allowed_scope:
            raise TraversalError("Execution Envelope does not authorize product scope")

        frontier = self._spine.frontier
        if frontier.target_landmark_id is None:
            raise TraversalError("frontier has reached final confirmed landmark")
        envelope = self._trajectory.execution_envelope
        if proposal.execution_scope not in envelope.allowed_scope:
            raise TraversalError("Execution Envelope does not authorize node scope")
        if proposal.side_effect is not None and proposal.side_effect not in envelope.allowed_side_effects:
            raise TraversalError("Execution Envelope does not authorize node side effect")
        forbidden = tuple(item.casefold() for item in envelope.forbidden_systems)
        if any(
            blocked in system.casefold()
            for blocked in forbidden
            for system in proposal.target_systems
        ):
            raise TraversalError("Execution Envelope forbids node target system")
        allowed_scope = tuple(item.casefold() for item in envelope.allowed_scope)
        if any(
            not any(scope in system.casefold() for scope in allowed_scope)
            for system in proposal.target_systems
        ):
            raise TraversalError("Execution Envelope scope does not bind target system")
        expected_anchor = self._spine.current_source_anchor_id
        expected_anchor_authority = (
            "trajectory:start_state"
            if expected_anchor == "START"
            else (
                f"trajectory:landmarks:{expected_anchor}"
                if expected_anchor in self._spine.landmark_order
                else f"derived-spine:nodes:{expected_anchor}"
            )
        )
        target_authority = f"trajectory:landmarks:{frontier.target_landmark_id}"
        if proposal.source_anchor_id != expected_anchor:
            raise TraversalError("proposal source anchor does not match current frontier")
        if entry_observation.node_id != expected_anchor:
            raise TraversalError("entry observation does not bind current frontier anchor")
        if proposal.target_landmark_id != frontier.target_landmark_id:
            raise TraversalError("proposal cannot reorder, skip, substitute, or add landmark")
        permitted_authority = {
            "trajectory:start_state",
            "trajectory:goal",
            "trajectory:terminal_outcome",
            "trajectory:execution_envelope",
            *(f"trajectory:landmarks:{item.landmark_id}" for item in self._trajectory.landmarks),
            *(
                f"trajectory:expected_behaviors:{item.behavior_id}"
                for item in self._trajectory.expected_behaviors
            ),
            *(f"derived-spine:nodes:{item.node_id}" for item in self._spine.nodes),
        }
        if (
            expected_anchor_authority not in proposal.authority_refs
            or target_authority not in proposal.authority_refs
            or not set(proposal.authority_refs).issubset(permitted_authority)
        ):
            raise TraversalError("proposal lacks operational Trajectory Brief authority")
        if entry_observation.observed_state not in proposal.expected_before:
            raise TraversalError("proposal expected_before is not justified by entry observation")
        if isinstance(proposal, LandmarkVerification):
            if entry_observation.observed_state not in proposal.expected_after:
                raise TraversalError("verification node must prove current satisfied landmark")
            landmark = next(
                item
                for item in self._trajectory.landmarks
                if item.landmark_id == frontier.target_landmark_id
            )
            if entry_observation.observed_state not in {
                landmark.description,
                *landmark.acceptance,
            }:
                raise TraversalError("verification evidence does not prove target landmark")
            if proposal.current_run_head_proof_ref not in entry_observation.evidence_refs:
                raise TraversalError("verification proof is not accepted current-head evidence")
        elif proposal.action_kind == "verify_only":
            raise TraversalError("verify_only proposal requires LandmarkVerification proof")

        try:
            sealed = DerivedBehavioralNode.seal(
                proposal,
                entry_observation_refs=entry_observation.evidence_refs,
                run_id=self._trajectory.run_id,
                trajectory_digest=self._trajectory.digest,
                run_head_digest=self._current_run_head.digest,
                execution_envelope_digest=envelope.digest,
            )
            validate_sealed_node_context(
                trajectory=self._trajectory,
                spine=self._spine,
                node=sealed,
                current_run_head=self._current_run_head,
                accepted_observations=self._accepted_observations,
            )
            return sealed
        except ValueError as exc:
            raise TraversalError("next node could not be sealed") from exc

    def advance(
        self,
        *,
        adapter: object,
        node_index: int,
        previous: NodeVerified | None,
    ) -> NodeVerified | ObservedFailure:
        """Replay one already-frozen node through stateful adapter progression.

        Replay owns no derivation or sealing. It consumes exact persisted node
        order, executes one adapter action, and returns immutable evidence for
        the caller to prove or reopen. Fixture reset is intentionally outside
        this method, so a complete replay resets exactly once.
        """

        if type(node_index) is not int or node_index < 0 or node_index >= len(self._spine.nodes):
            raise TraversalError("replay node index is outside frozen Derived Spine")
        node = self._spine.nodes[node_index]
        if node.run_id != self._trajectory.run_id or node.trajectory_digest != self._trajectory.digest:
            raise TraversalError("replay node does not bind confirmed trajectory")
        if node.run_head_digest != self._current_run_head.digest:
            raise TraversalError("replay node does not bind current Run Head")
        if node_index == 0:
            if previous is not None:
                raise TraversalError("first replay node cannot have predecessor")
        elif (
            previous is None
            or previous.node_index != node_index - 1
            or previous.node_id != self._spine.nodes[node_index - 1].node_id
        ):
            raise TraversalError("replay predecessor does not follow frozen node order")

        snapshot_digest = self._current_run_head.fixture_digest
        observations: tuple[Observation, ...] = ()
        receipts: tuple[ActionReceipt, ...] = ()
        try:
            if node.action_kind == "verify_only":
                # Verification-only nodes still require an adapter observation.
                # Never manufacture proof from the sealed expected state.
                observation = adapter.observe_readonly(
                    anchor_id=node.source_anchor_id,
                    run_head_digest=self._current_run_head.digest,
                )  # type: ignore[attr-defined]
                if not isinstance(observation, Observation):
                    raise TraversalError("replay adapter returned invalid readonly observation")
                observations = (observation,)
                snapshot_digest = self._current_run_head.fixture_digest
                if (
                    observation.node_id != node.source_anchor_id
                    or observation.run_head_digest != self._current_run_head.digest
                    or observation.observed_state not in node.expected_after
                    or not set(node.entry_observation_refs).issubset(observation.evidence_refs)
                    or (
                        node.current_run_head_proof_ref is not None
                        and node.current_run_head_proof_ref not in observation.evidence_refs
                    )
                ):
                    return ObservedFailure(
                        node_id=node.node_id,
                        node_index=node_index,
                        failure_code="replay_verification_mismatch",
                        observations=observations,
                        action_receipts=(),
                        seam_receipts=(),
                        selected_variant_ids=(),
                        run_head_digest=self._current_run_head.digest,
                        snapshot_digest=snapshot_digest,
                    )
            else:
                receipt = adapter.act(node, run_head_digest=self._current_run_head.digest)  # type: ignore[attr-defined]
                if not isinstance(receipt, ActionReceipt):
                    raise TraversalError("replay adapter returned invalid action receipt")
                receipts = (receipt,)
                snapshot_digest = receipt.snapshot_digest
                # Receipt identity is replay authority. Reject mismatches
                # before deriving any observation or proof from its payload.
                if (
                    receipt.node_id != node.node_id
                    or receipt.run_head_digest != self._current_run_head.digest
                ):
                    return ObservedFailure(
                        node_id=node.node_id,
                        node_index=node_index,
                        failure_code="replay_receipt_mismatch",
                        observations=(),
                        action_receipts=receipts,
                        seam_receipts=(),
                        selected_variant_ids=(),
                        run_head_digest=self._current_run_head.digest,
                        snapshot_digest=snapshot_digest,
                    )
                if receipt.snapshot_digest != self._current_run_head.fixture_digest:
                    return ObservedFailure(
                        node_id=node.node_id,
                        node_index=node_index,
                        failure_code="replay_fixture_mismatch",
                        observations=(),
                        action_receipts=receipts,
                        seam_receipts=(),
                        selected_variant_ids=(),
                        run_head_digest=self._current_run_head.digest,
                        snapshot_digest=snapshot_digest,
                    )
                observation = Observation(
                    observation_id=digest_for(
                        "frozen-replay-observation",
                        {"node_id": node.node_id, "receipt": receipt},
                    ),
                    node_id=node.target_landmark_id,
                    kind="behavioral",
                    observed_state=receipt.observed_state,
                    evidence_refs=receipt.evidence_refs,
                    run_head_digest=self._current_run_head.digest,
                )
                observations = (observation,)
                if receipt.outcome != "accepted" or receipt.observed_state not in node.expected_after:
                    return ObservedFailure(
                        node_id=node.node_id,
                        node_index=node_index,
                        failure_code="replay_expectation_mismatch",
                        observations=observations,
                        action_receipts=receipts,
                        seam_receipts=(),
                        selected_variant_ids=(receipt.variant_id,),
                        run_head_digest=self._current_run_head.digest,
                        snapshot_digest=snapshot_digest,
                    )
        # Adapter execution is untrusted product-work boundary. Any ordinary
        # adapter exception (including RuntimeError) is observed as a replay
        # failure so caller can durably reopen its smallest cone. Never let an
        # adapter exception strand final replay in final_replay mode.
        except Exception:
            return ObservedFailure(
                node_id=node.node_id,
                node_index=node_index,
                failure_code="replay_execution_failed",
                observations=observations,
                action_receipts=receipts,
                seam_receipts=(),
                selected_variant_ids=(),
                run_head_digest=self._current_run_head.digest,
                snapshot_digest=snapshot_digest,
            )
        return NodeVerified(
            node_id=node.node_id,
            node_index=node_index,
            next_node_id=(self._spine.nodes[node_index + 1].node_id if node_index + 1 < len(self._spine.nodes) else None),
            observations=observations,
            action_receipts=receipts,
            seam_receipts=(),
            selected_variant_ids=(receipts[0].variant_id,) if receipts else (),
            run_head_digest=self._current_run_head.digest,
            snapshot_digest=snapshot_digest,
        )
