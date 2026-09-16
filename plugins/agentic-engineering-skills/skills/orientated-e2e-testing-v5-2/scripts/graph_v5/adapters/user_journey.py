"""Read-only adapter contract for V5 user-journey observations."""

from __future__ import annotations

from dataclasses import dataclass
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from ..canonical import canonical_json_bytes, digest_for
from ..models import DerivedBehavioralNode, Observation


class AdapterContractError(ValueError):
    """Adapter receipt or request is outside its sealed fixture boundary."""


def _required(value: str, field: str) -> str:
    if not value.strip():
        raise AdapterContractError(f"{field} must be non-empty")
    return value


@dataclass(frozen=True, slots=True)
class FixtureSnapshot:
    fixture_id: str
    snapshot_digest: str
    adapter_id: str
    variants: tuple["VariantDirective", ...] = ()
    authorized_seams: tuple["AuthorizedSeam", ...] = ()
    sealed: Literal[True] = True

    def __post_init__(self) -> None:
        _required(self.fixture_id, "fixture_id")
        _required(self.snapshot_digest, "snapshot_digest")
        _required(self.adapter_id, "adapter_id")
        if self.sealed is not True:
            raise AdapterContractError("fixture snapshot must be sealed")
        if not isinstance(self.variants, tuple) or not all(
            isinstance(variant, VariantDirective) for variant in self.variants
        ):
            raise AdapterContractError("sealed fixture variants must be an immutable tuple")
        if not isinstance(self.authorized_seams, tuple) or not all(
            isinstance(seam, AuthorizedSeam) for seam in self.authorized_seams
        ):
            raise AdapterContractError("sealed fixture seams must be an immutable tuple")


@dataclass(frozen=True, slots=True)
class VariantDirective:
    """Finite non-primary variant allowed by one sealed fixture snapshot."""

    node_id: str
    variant_id: str
    kind: Literal["invalid", "boundary", "retry", "back"]
    action: str
    expected_outcome: Literal["accepted", "rejected"]
    expected_state: str
    evidence_ref: str

    def __post_init__(self) -> None:
        for field in (
            "node_id",
            "variant_id",
            "action",
            "expected_state",
            "evidence_ref",
        ):
            _required(getattr(self, field), field)


@dataclass(frozen=True, slots=True)
class AuthorizedSeam:
    """One node-local operational seam admitted by its fixture snapshot."""

    node_id: str
    seam: str
    evidence_ref: str

    def __post_init__(self) -> None:
        _required(self.node_id, "node_id")
        _required(self.seam, "seam")
        _required(self.evidence_ref, "evidence_ref")


@dataclass(frozen=True, slots=True)
class FixtureReceipt:
    fixture_id: str
    snapshot_digest: str
    adapter_id: str
    sealed: Literal[True] = True

    def __post_init__(self) -> None:
        _required(self.fixture_id, "fixture_id")
        _required(self.snapshot_digest, "snapshot_digest")
        _required(self.adapter_id, "adapter_id")
        if self.sealed is not True:
            raise AdapterContractError("fixture receipt must be sealed")


@dataclass(frozen=True, slots=True)
class Checkpoint:
    """Single behavioral node bound to one Run Head and fixture snapshot."""

    node_id: str
    action: str
    current_state: str
    next_state: str
    requires_persistence: bool
    run_head_digest: str
    snapshot_digest: str
    variants: tuple[VariantDirective, ...]

    def __post_init__(self) -> None:
        for field in (
            "node_id",
            "action",
            "current_state",
            "next_state",
            "run_head_digest",
            "snapshot_digest",
        ):
            _required(getattr(self, field), field)


@dataclass(frozen=True, slots=True)
class UserAction:
    """One bounded user action, never a repository query or controller command."""

    node_id: str
    variant_id: str
    action: str
    run_head_digest: str
    snapshot_digest: str

    def __post_init__(self) -> None:
        for field in (
            "node_id",
            "variant_id",
            "action",
            "run_head_digest",
            "snapshot_digest",
        ):
            _required(getattr(self, field), field)


@dataclass(frozen=True, slots=True)
class ActionReceipt:
    """Immutable adapter receipt for a bounded primary or variant action."""

    node_id: str
    variant_id: str
    outcome: Literal["accepted", "rejected"]
    observed_state: str
    evidence_refs: tuple[str, ...]
    run_head_digest: str
    snapshot_digest: str

    def __post_init__(self) -> None:
        for field in (
            "node_id",
            "variant_id",
            "observed_state",
            "run_head_digest",
            "snapshot_digest",
        ):
            _required(getattr(self, field), field)
        if not self.evidence_refs:
            raise AdapterContractError("action receipt requires evidence")
        for evidence_ref in self.evidence_refs:
            _required(evidence_ref, "evidence_ref")


VariantResult = ActionReceipt


@dataclass(frozen=True, slots=True)
class SeamRequest:
    """Node-local request; repository-wide and unsealed seams are impossible."""

    node_id: str
    seam: str
    evidence_ref: str
    run_head_digest: str
    snapshot_digest: str
    scope: Literal["node"] = "node"

    def __post_init__(self) -> None:
        for field in (
            "node_id",
            "seam",
            "evidence_ref",
            "run_head_digest",
            "snapshot_digest",
        ):
            _required(getattr(self, field), field)
        if self.scope != "node":
            raise AdapterContractError("repository-wide seam requests are forbidden")


@dataclass(frozen=True, slots=True)
class OperationalObservation:
    """Immutable receipt from one authorized operational seam."""

    node_id: str
    seam: str
    observed_state: str
    evidence_refs: tuple[str, ...]
    run_head_digest: str
    snapshot_digest: str

    def __post_init__(self) -> None:
        for field in (
            "node_id",
            "seam",
            "observed_state",
            "run_head_digest",
            "snapshot_digest",
        ):
            _required(getattr(self, field), field)
        if not self.evidence_refs:
            raise AdapterContractError("operational observation requires evidence")
        for evidence_ref in self.evidence_refs:
            _required(evidence_ref, "evidence_ref")


@runtime_checkable
class UserJourneyAdapter(Protocol):
    """Adapter observes fixture; traversal remains sole owner of progress."""

    spine_kind: Literal["user_journey"]

    def reset_fixture(self, snapshot: FixtureSnapshot) -> FixtureReceipt: ...

    def fixture_snapshot(self) -> FixtureSnapshot: ...

    def fixture_is_active(self) -> bool: ...

    def observe(self, *, anchor_id: str, run_head_digest: str) -> Observation: ...

    def observe_readonly(
        self, *, anchor_id: str, run_head_digest: str
    ) -> Observation: ...

    def act(
        self, node: DerivedBehavioralNode, *, run_head_digest: str
    ) -> ActionReceipt: ...


class _LegacyFixtureUserJourneyAdapter:
    """Deterministic isolated-fixture adapter; owns fixture state, never Graph state."""

    spine_kind: Literal["user_journey"] = "user_journey"

    def __init__(self, scenario: Mapping[str, Any]) -> None:
        self._scenario = self._copy_scenario(scenario)
        self._validate_scenario_shape()
        self._active_snapshot: FixtureSnapshot | None = None
        self._after_primary: set[str] = set()

    @classmethod
    def from_fixture_file(
        cls, path: str | Path, scenario_id: str
    ) -> "FixtureUserJourneyAdapter":
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AdapterContractError(f"invalid user journey fixture: {path}") from exc
        root = cls._mapping(payload, "fixture root")
        if root.get("schema_version") != "graph-v5.user-journey-fixture.v1":
            raise AdapterContractError("fixture schema_version is unsupported")
        cls._text(root, "fixture_family")
        scenarios = root.get("scenarios")
        if not isinstance(scenarios, list):
            raise AdapterContractError("fixture scenarios must be a list")
        scenario_ids = tuple(
            cls._text(cls._mapping(candidate, "fixture scenario"), "scenario_id")
            for candidate in scenarios
        )
        if len(scenario_ids) != len(set(scenario_ids)):
            raise AdapterContractError("fixture contains duplicate scenario id")
        for candidate in scenarios:
            if isinstance(candidate, Mapping) and candidate.get("scenario_id") == scenario_id:
                return cls(candidate)
        raise AdapterContractError(f"fixture scenario is absent: {scenario_id}")

    def fixture_snapshot(self) -> FixtureSnapshot:
        fixture = self._mapping(self._scenario.get("fixture"), "fixture identity")
        declared_digest = self._text(fixture, "snapshot_digest")
        scenario_for_digest = dict(self._scenario)
        fixture_for_digest = dict(fixture)
        fixture_for_digest.pop("snapshot_digest", None)
        scenario_for_digest["fixture"] = fixture_for_digest
        computed_digest = digest_for(
            "user-journey-fixture-snapshot", scenario_for_digest
        )
        if declared_digest != computed_digest:
            raise AdapterContractError("fixture snapshot digest does not match canonical content")
        variants = tuple(
            VariantDirective(
                node_id=self._text(item, "node_id"),
                variant_id=self._text(item, "variant_id"),
                kind=self._variant_kind(item),
                action=self._text(item, "action"),
                expected_outcome=self._action_outcome(item),
                expected_state=self._text(item, "expected_state"),
                evidence_ref=self._text(item, "evidence_ref"),
            )
            for item in self._mapping_list(self._scenario.get("variants", []), "variants")
        )
        authorized_seams = tuple(
            AuthorizedSeam(
                node_id=self._text(item, "node_id"),
                seam=self._text(item, "seam"),
                evidence_ref=self._text(item, "evidence_ref"),
            )
            for item in self._mapping_list(
                self._scenario.get("authorized_seams", []), "authorized_seams"
            )
        )
        return FixtureSnapshot(
            fixture_id=self._text(fixture, "fixture_id"),
            snapshot_digest=computed_digest,
            adapter_id="fixture-user-journey",
            variants=variants,
            authorized_seams=authorized_seams,
        )

    def fixture_is_active(self) -> bool:
        return self._active_snapshot is not None

    def reset_fixture(self, snapshot: FixtureSnapshot) -> FixtureReceipt:
        if snapshot != self.fixture_snapshot():
            raise AdapterContractError("reset requires exact sealed fixture snapshot")
        self._active_snapshot = snapshot
        self._after_primary.clear()
        return FixtureReceipt(
            fixture_id=snapshot.fixture_id,
            snapshot_digest=snapshot.snapshot_digest,
            adapter_id=snapshot.adapter_id,
        )

    def observe(self, checkpoint: Checkpoint) -> Observation:
        self._require_checkpoint(checkpoint)
        phase = "after" if checkpoint.node_id in self._after_primary else "before"
        detail = self._mapping(self._node(checkpoint.node_id).get(phase), f"{phase} observation")
        return Observation(
            observation_id=digest_for(
                "fixture-user-journey-observation",
                {
                    "scenario_id": self._scenario_id,
                    "node_id": checkpoint.node_id,
                    "phase": phase,
                    "run_head_digest": checkpoint.run_head_digest,
                    "snapshot_digest": checkpoint.snapshot_digest,
                },
            ),
            node_id=checkpoint.node_id,
            kind="behavioral",
            observed_state=self._text(detail, "observed_state"),
            evidence_refs=self._evidence_refs(detail),
            run_head_digest=checkpoint.run_head_digest,
        )

    def act(self, action: UserAction) -> ActionReceipt:
        self._require_action(action)
        node = self._node(action.node_id)
        actions = self._mapping(node.get("actions"), "fixture actions")
        detail = self._mapping(actions.get(action.variant_id), "fixture action")
        outcome = self._action_outcome(detail)
        if action.variant_id == "primary" and outcome == "accepted":
            self._after_primary.add(action.node_id)
        return ActionReceipt(
            node_id=action.node_id,
            variant_id=action.variant_id,
            outcome=outcome,
            observed_state=self._text(detail, "observed_state"),
            evidence_refs=self._evidence_refs(detail),
            run_head_digest=action.run_head_digest,
            snapshot_digest=action.snapshot_digest,
        )

    def inspect_seam(self, request: SeamRequest) -> OperationalObservation:
        self._require_request(request)
        seams = self._mapping(self._node(request.node_id).get("seams"), "fixture seams")
        detail = self._mapping(seams.get(request.seam), "fixture seam")
        return OperationalObservation(
            node_id=request.node_id,
            seam=request.seam,
            observed_state=self._text(detail, "observed_state"),
            evidence_refs=self._evidence_refs(detail),
            run_head_digest=request.run_head_digest,
            snapshot_digest=request.snapshot_digest,
        )

    @property
    def _scenario_id(self) -> str:
        return self._text(self._scenario, "scenario_id")

    def _require_checkpoint(self, checkpoint: Checkpoint) -> None:
        self._require_active_snapshot(checkpoint.snapshot_digest)
        step = self._journey_step(checkpoint.node_id)
        rank = {"invalid": 0, "boundary": 1, "retry": 2, "back": 3}
        expected_variants = tuple(
            sorted(
                (
                    variant
                    for variant in self._active_snapshot.variants  # type: ignore[union-attr]
                    if variant.node_id == checkpoint.node_id
                ),
                key=lambda item: (rank[item.kind], item.variant_id),
            )
        )
        expected_persistence = step.get("requires_persistence")
        if type(expected_persistence) is not bool:
            raise AdapterContractError("requires_persistence must be boolean")
        if (
            checkpoint.action != self._text(step, "action")
            or checkpoint.current_state != self._text(step, "current_state")
            or checkpoint.next_state != self._text(step, "next_state")
            or type(checkpoint.requires_persistence) is not bool
            or checkpoint.requires_persistence is not expected_persistence
            or checkpoint.variants != expected_variants
        ):
            raise AdapterContractError("checkpoint differs from sealed user journey")
        self._node(checkpoint.node_id)

    def _require_action(self, action: UserAction) -> None:
        self._require_active_snapshot(action.snapshot_digest)
        step = self._journey_step(action.node_id)
        if action.variant_id == "primary":
            expected_action = self._text(step, "action")
        else:
            variants = tuple(
                variant
                for variant in self._active_snapshot.variants  # type: ignore[union-attr]
                if variant.node_id == action.node_id
                and variant.variant_id == action.variant_id
            )
            if len(variants) != 1:
                raise AdapterContractError("action is not declared by sealed fixture")
            expected_action = variants[0].action
        if action.action != expected_action:
            raise AdapterContractError("action differs from sealed action")
        self._node(action.node_id)

    def _require_request(self, request: SeamRequest) -> None:
        self._require_active_snapshot(request.snapshot_digest)
        if request.scope != "node":
            raise AdapterContractError("repository-wide seam requests are forbidden")
        authorized = tuple(
            seam
            for seam in self._active_snapshot.authorized_seams  # type: ignore[union-attr]
            if seam.node_id == request.node_id
            and seam.seam == request.seam
            and seam.evidence_ref == request.evidence_ref
        )
        if len(authorized) != 1:
            raise AdapterContractError("request is not an authorized seam")
        self._node(request.node_id)

    def _require_active_snapshot(self, snapshot_digest: str) -> None:
        if self._active_snapshot is None:
            raise AdapterContractError("fixture must be reset before product observation")
        if self._active_snapshot.snapshot_digest != snapshot_digest:
            raise AdapterContractError("receipt does not bind active fixture snapshot")

    def _node(self, node_id: str) -> Mapping[str, Any]:
        nodes = self._mapping(self._scenario.get("nodes"), "fixture nodes")
        return self._mapping(nodes.get(node_id), f"fixture node {node_id}")

    def _journey_step(self, node_id: str) -> Mapping[str, Any]:
        goal = self._mapping(self._scenario.get("goal"), "fixture goal")
        journey = self._mapping_list(goal.get("journey"), "fixture journey")
        matches = tuple(step for step in journey if step.get("node_id") == node_id)
        if len(matches) != 1:
            raise AdapterContractError("node is not unique in sealed user journey")
        return matches[0]

    def _validate_scenario_shape(self) -> None:
        self._text(self._scenario, "scenario_id")
        fixture = self._mapping(self._scenario.get("fixture"), "fixture identity")
        self._text(fixture, "fixture_id")
        self._text(fixture, "snapshot_digest")
        goal = self._mapping(self._scenario.get("goal"), "fixture goal")
        journey = self._mapping_list(goal.get("journey"), "fixture journey")
        node_ids = tuple(self._text(step, "node_id") for step in journey)
        if not node_ids or len(node_ids) != len(set(node_ids)):
            raise AdapterContractError("fixture journey node ids must be unique")
        nodes = self._mapping(self._scenario.get("nodes"), "fixture nodes")
        if set(nodes) != set(node_ids):
            raise AdapterContractError("fixture nodes must exactly match sealed journey")
        variants = self._mapping_list(self._scenario.get("variants", []), "variants")
        variant_keys: list[tuple[str, str]] = []
        for variant in variants:
            node_id = self._text(variant, "node_id")
            if node_id not in node_ids:
                raise AdapterContractError("fixture variant is outside journey")
            variant_keys.append((node_id, self._text(variant, "variant_id")))
        if len(variant_keys) != len(set(variant_keys)):
            raise AdapterContractError("fixture contains duplicate variant id")
        seams = self._mapping_list(
            self._scenario.get("authorized_seams", []), "authorized_seams"
        )
        seam_keys: list[tuple[str, str]] = []
        for seam in seams:
            node_id = self._text(seam, "node_id")
            if node_id not in node_ids:
                raise AdapterContractError("authorized seam is outside journey")
            seam_keys.append((node_id, self._text(seam, "seam")))
        if len(seam_keys) != len(set(seam_keys)):
            raise AdapterContractError("fixture contains duplicate authorized seam")

    @staticmethod
    def _copy_scenario(scenario: Mapping[str, Any]) -> dict[str, Any]:
        try:
            copied = json.loads(canonical_json_bytes(scenario).decode("utf-8"))
        except (TypeError, ValueError) as exc:
            raise AdapterContractError("fixture scenario must be canonical JSON") from exc
        return FixtureUserJourneyAdapter._mapping(copied, "fixture scenario")

    @staticmethod
    def _mapping(value: object, name: str) -> Mapping[str, Any]:
        if not isinstance(value, Mapping):
            raise AdapterContractError(f"{name} must be an object")
        return value

    @classmethod
    def _mapping_list(cls, value: object, name: str) -> tuple[Mapping[str, Any], ...]:
        if not isinstance(value, list):
            raise AdapterContractError(f"{name} must be a list")
        return tuple(cls._mapping(item, name) for item in value)

    @staticmethod
    def _text(value: Mapping[str, Any], field: str) -> str:
        result = value.get(field)
        if not isinstance(result, str):
            raise AdapterContractError(f"{field} must be a string")
        return _required(result, field)

    @classmethod
    def _evidence_refs(cls, value: Mapping[str, Any]) -> tuple[str, ...]:
        raw = value.get("evidence_refs")
        if not isinstance(raw, list) or not raw:
            raise AdapterContractError("fixture observation requires evidence_refs")
        return tuple(
            _required(item, "evidence_ref")
            if isinstance(item, str)
            else cls._invalid_evidence_ref()
            for item in raw
        )

    @staticmethod
    def _invalid_evidence_ref() -> str:
        raise AdapterContractError("evidence_ref must be a string")

    @staticmethod
    def _action_outcome(value: Mapping[str, Any]) -> Literal["accepted", "rejected"]:
        outcome = value.get("expected_outcome", value.get("outcome"))
        if outcome not in {"accepted", "rejected"}:
            raise AdapterContractError("action outcome must be accepted or rejected")
        return outcome

    @staticmethod
    def _variant_kind(value: Mapping[str, Any]) -> Literal["invalid", "boundary", "retry", "back"]:
        kind = value.get("kind")
        if kind not in {"invalid", "boundary", "retry", "back"}:
            raise AdapterContractError("variant kind is unsupported")
        return kind


class FixtureUserJourneyAdapter:
    """Fixture capability catalog. Receives sealed nodes; never derives or stores them."""

    spine_kind: Literal["user_journey"] = "user_journey"
    adapter_id = "fixture-user-journey.v1"

    def __init__(self, scenario: Mapping[str, Any]) -> None:
        try:
            copied = json.loads(canonical_json_bytes(scenario).decode("utf-8"))
        except (TypeError, ValueError) as exc:
            raise AdapterContractError("fixture scenario must be canonical JSON") from exc
        if not isinstance(copied, dict):
            raise AdapterContractError("fixture scenario must be an object")
        self._scenario = copied
        self._validate_shape()
        self._active_snapshot: FixtureSnapshot | None = None
        self._current_fixture_anchor = "START"

    @classmethod
    def from_fixture_file(
        cls, path: str | Path, scenario_id: str
    ) -> "FixtureUserJourneyAdapter":
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AdapterContractError(f"invalid trajectory fixture: {path}") from exc
        if not isinstance(payload, dict):
            raise AdapterContractError("trajectory fixture root must be an object")
        if payload.get("schema_version") != "graph-v5.trajectory-jit-fixture.v1":
            raise AdapterContractError("fixture schema_version is unsupported")
        scenarios = payload.get("scenarios")
        if not isinstance(scenarios, list):
            raise AdapterContractError("fixture scenarios must be a list")
        matches = [
            item
            for item in scenarios
            if isinstance(item, dict) and item.get("scenario_id") == scenario_id
        ]
        if len(matches) != 1:
            raise AdapterContractError(f"fixture scenario is absent or ambiguous: {scenario_id}")
        return cls(matches[0])

    def fixture_snapshot(self) -> FixtureSnapshot:
        fixture = self._fixture()
        declared = self._text(fixture, "snapshot_digest")
        payload = dict(self._scenario)
        fixture_payload = dict(fixture)
        fixture_payload.pop("snapshot_digest", None)
        payload["fixture"] = fixture_payload
        computed = digest_for("trajectory-jit-fixture-snapshot", payload)
        if declared != computed:
            raise AdapterContractError("fixture snapshot digest does not match canonical content")
        return FixtureSnapshot(
            fixture_id=self._text(fixture, "fixture_id"),
            snapshot_digest=computed,
            adapter_id="fixture-user-journey",
        )

    def environment_snapshot(self) -> FixtureSnapshot:
        """Expose fixture identity through generic adapter discovery without real authority."""

        return self.fixture_snapshot()

    def teardown(self) -> FixtureReceipt:
        """Forget local fixture state; no external resource can be deleted here."""

        snapshot = self._active_snapshot or self.fixture_snapshot()
        self._active_snapshot = None
        self._current_fixture_anchor = "START"
        return FixtureReceipt(
            fixture_id=snapshot.fixture_id,
            snapshot_digest=snapshot.snapshot_digest,
            adapter_id=snapshot.adapter_id,
        )

    def fixture_is_active(self) -> bool:
        return self._active_snapshot is not None

    def reset_fixture(self, snapshot: FixtureSnapshot) -> FixtureReceipt:
        if snapshot != self.fixture_snapshot():
            raise AdapterContractError("reset requires exact sealed fixture snapshot")
        self._active_snapshot = snapshot
        self._current_fixture_anchor = "START"
        return FixtureReceipt(
            fixture_id=snapshot.fixture_id,
            snapshot_digest=snapshot.snapshot_digest,
            adapter_id=snapshot.adapter_id,
        )

    def observe(self, *, anchor_id: str, run_head_digest: str) -> Observation:
        self._require_active()
        assert self._active_snapshot is not None
        return self._observe_with_snapshot(
            anchor_id=anchor_id,
            run_head_digest=run_head_digest,
            snapshot=self._active_snapshot,
        )

    def observe_readonly(
        self, *, anchor_id: str, run_head_digest: str
    ) -> Observation:
        return self._observe_with_snapshot(
            anchor_id=anchor_id,
            run_head_digest=run_head_digest,
            snapshot=self._active_snapshot or self.fixture_snapshot(),
        )

    def _observe_with_snapshot(
        self,
        *,
        anchor_id: str,
        run_head_digest: str,
        snapshot: FixtureSnapshot,
    ) -> Observation:
        _required(anchor_id, "anchor_id")
        _required(run_head_digest, "run_head_digest")
        observations = self._mapping(self._scenario.get("observations"), "observations")
        detail = self._mapping(
            observations.get(self._current_fixture_anchor),
            f"observation {self._current_fixture_anchor}",
        )
        evidence_refs = self._evidence_refs(detail)
        return Observation(
            observation_id=digest_for(
                "trajectory-jit-observation",
                {
                    "scenario_id": self._text(self._scenario, "scenario_id"),
                    "anchor_id": anchor_id,
                    "run_head_digest": run_head_digest,
                    "snapshot_digest": snapshot.snapshot_digest,
                },
            ),
            node_id=anchor_id,
            kind="behavioral",
            observed_state=self._text(detail, "observed_state"),
            evidence_refs=evidence_refs,
            run_head_digest=run_head_digest,
        )

    def act(
        self, node: object, *, run_head_digest: str
    ) -> ActionReceipt:
        self._require_active()
        _required(run_head_digest, "run_head_digest")
        if not isinstance(node, DerivedBehavioralNode):
            raise AdapterContractError("adapter accepts only sealed DerivedBehavioralNode")
        try:
            sealed = DerivedBehavioralNode.model_validate(node.model_dump(mode="python"))
        except ValueError as exc:
            raise AdapterContractError("sealed intent digest is invalid") from exc
        if sealed.run_head_digest != run_head_digest:
            raise AdapterContractError("sealed action does not bind exact Run Head")
        if sealed.action_kind == "verify_only":
            raise AdapterContractError(
                "verification-only node records proof without product action"
            )
        before = self.observe(
            anchor_id=sealed.source_anchor_id,
            run_head_digest=run_head_digest,
        )
        detail = self._catalog_entry(sealed, before)
        if before.observed_state not in sealed.expected_before:
            raise AdapterContractError("sealed action precondition is not observable in fixture")
        if not set(sealed.entry_observation_refs).issubset(before.evidence_refs):
            raise AdapterContractError("sealed action evidence is foreign to current observation")
        outcome = self._outcome(detail)
        observed_state = self._text(detail, "observed_state")
        if outcome == "accepted":
            self._current_fixture_anchor = self._anchor_for_observed_state(observed_state)
        return ActionReceipt(
            node_id=sealed.node_id,
            variant_id="sealed",
            outcome=outcome,
            observed_state=observed_state,
            evidence_refs=self._evidence_refs(detail),
            run_head_digest=run_head_digest,
            snapshot_digest=self._active_snapshot.snapshot_digest,
        )

    def _catalog_entry(
        self, node: DerivedBehavioralNode, before: Observation
    ) -> Mapping[str, Any]:
        catalog = self._list(self._scenario.get("action_catalog"), "action_catalog")
        matches = [
            item
            for item in catalog
            if self._text(item, "required_observed_state") == before.observed_state
            and self._text(item, "action_or_probe") == node.action_or_probe
            and item.get("action_kind") == node.action_kind
        ]
        if len(matches) != 1:
            raise AdapterContractError("sealed action is absent from fixture capability catalog")
        return matches[0]

    def _validate_shape(self) -> None:
        self._text(self._scenario, "scenario_id")
        self._fixture()
        observations = self._mapping(self._scenario.get("observations"), "observations")
        if "START" not in observations:
            raise AdapterContractError("fixture requires START observation")
        for anchor, detail in observations.items():
            if not isinstance(anchor, str):
                raise AdapterContractError("observation anchor must be a string")
            self._text(self._mapping(detail, "observation"), "observed_state")
            self._evidence_refs(self._mapping(detail, "observation"))
        observed_states = tuple(
            self._text(self._mapping(detail, "observation"), "observed_state")
            for detail in observations.values()
        )
        if len(observed_states) != len(set(observed_states)):
            raise AdapterContractError("fixture observed states must map to one anchor")
        keys: set[tuple[str, str, str]] = set()
        for item in self._list(self._scenario.get("action_catalog"), "action_catalog"):
            key = (
                self._text(item, "required_observed_state"),
                self._text(item, "action_or_probe"),
                self._text(item, "action_kind"),
            )
            if key in keys:
                raise AdapterContractError("fixture capability catalog contains duplicate action")
            keys.add(key)
            if key[0] not in observed_states:
                raise AdapterContractError(
                    "fixture capability precondition must be observable"
                )
            if self._text(item, "observed_state") not in observed_states:
                raise AdapterContractError("fixture capability outcome must be observable")
            self._evidence_refs(item)
            self._outcome(item)

    def _anchor_for_observed_state(self, observed_state: str) -> str:
        observations = self._mapping(self._scenario.get("observations"), "observations")
        matches = [
            anchor
            for anchor, detail in observations.items()
            if self._text(self._mapping(detail, "observation"), "observed_state")
            == observed_state
        ]
        if len(matches) != 1:
            raise AdapterContractError("fixture outcome does not map to exact observation")
        return matches[0]

    def _fixture(self) -> Mapping[str, Any]:
        fixture = self._mapping(self._scenario.get("fixture"), "fixture")
        self._text(fixture, "fixture_id")
        self._text(fixture, "snapshot_digest")
        return fixture

    def _require_active(self) -> None:
        if self._active_snapshot is None:
            raise AdapterContractError("fixture must be reset before product observation or action")

    @staticmethod
    def _mapping(value: object, name: str) -> Mapping[str, Any]:
        if not isinstance(value, Mapping):
            raise AdapterContractError(f"{name} must be an object")
        return value

    @classmethod
    def _list(cls, value: object, name: str) -> tuple[Mapping[str, Any], ...]:
        if not isinstance(value, list):
            raise AdapterContractError(f"{name} must be a list")
        return tuple(cls._mapping(item, name) for item in value)

    @staticmethod
    def _text(value: Mapping[str, Any], field: str) -> str:
        text = value.get(field)
        if not isinstance(text, str):
            raise AdapterContractError(f"{field} must be a string")
        return _required(text, field)

    @classmethod
    def _evidence_refs(cls, value: Mapping[str, Any]) -> tuple[str, ...]:
        raw = value.get("evidence_refs")
        if not isinstance(raw, list) or not raw:
            raise AdapterContractError("fixture observation requires evidence_refs")
        return tuple(
            _required(item, "evidence_ref")
            if isinstance(item, str)
            else cls._invalid_evidence_ref()
            for item in raw
        )

    @staticmethod
    def _invalid_evidence_ref() -> str:
        raise AdapterContractError("evidence_ref must be a string")

    @staticmethod
    def _outcome(value: Mapping[str, Any]) -> Literal["accepted", "rejected"]:
        outcome = value.get("outcome")
        if outcome not in {"accepted", "rejected"}:
            raise AdapterContractError("action outcome must be accepted or rejected")
        return outcome
