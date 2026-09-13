"""Registered V5.2 fixture wrapper over immutable legacy fixture capability."""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from .manifest import AdapterManifest
from .protocol import AdapterError
from .user_journey import FixtureSnapshot, FixtureUserJourneyAdapter
from ..canonical import digest_for
from ..environment import EnvironmentSnapshot
from ..models import (
    DerivedBehavioralNode,
    ExternalOperationIntent,
    ExternalOperationReceipt,
    Observation,
)


_PERSISTED_FIXTURE_SOURCES: Mapping[
    str, tuple[str, str, tuple[str, ...]]
] = MappingProxyType(
    {
        digest_for("fixture-admission-source", {"fixture": "checkout"}): (
            "Synthetic checkout form is visible",
            "Synthetic checkout result is visible",
            ("fixture:checkout-result",),
        )
    }
)


def require_registered_fixture_source(
    source_identity_digest: str,
) -> tuple[str, str, tuple[str, ...]]:
    """Resolve fixture evidence from package-compiled source identity only."""

    source = _PERSISTED_FIXTURE_SOURCES.get(source_identity_digest)
    if source is None:
        raise AdapterError("fixture source identity is not statically registered")
    return source


class V52FixtureJourneyAdapter:
    """Translate legacy fixture receipts; runtime remains authority owner."""

    adapter_id = "fixture-user-journey.v1"
    _legacy_snapshot_adapter_id = "fixture-user-journey"

    def __init__(self, manifest: AdapterManifest, legacy: FixtureUserJourneyAdapter) -> None:
        if not isinstance(manifest, AdapterManifest) or manifest.adapter_id != self.adapter_id:
            raise AdapterError("fixture adapter manifest selects another registered adapter")
        if manifest.mode != "fixture":
            raise AdapterError("fixture adapter requires fixture manifest mode")
        if not isinstance(legacy, FixtureUserJourneyAdapter):
            raise AdapterError("fixture adapter requires immutable legacy fixture adapter")
        self._manifest = manifest
        self._legacy = legacy

    @property
    def manifest_digest(self) -> str:
        return self._manifest.digest

    def environment_snapshot(self) -> EnvironmentSnapshot:
        fixture = self._legacy.fixture_snapshot()
        if not isinstance(fixture, FixtureSnapshot) or (
            fixture.adapter_id != self._legacy_snapshot_adapter_id
        ):
            raise AdapterError("legacy fixture identity cannot be normalized")
        return EnvironmentSnapshot.for_fixture_manifest(
            manifest=self._manifest,
            fixture_digest=fixture.snapshot_digest,
        )

    def observe_readonly(self, node: DerivedBehavioralNode, /, **_: object) -> Observation:
        if not isinstance(node, DerivedBehavioralNode):
            raise AdapterError("fixture adapter accepts only sealed DerivedBehavioralNode")
        return self._legacy.observe_readonly(
            anchor_id=node.source_anchor_id,
            run_head_digest=node.run_head_digest,
        )

    def act(
        self,
        node: DerivedBehavioralNode,
        /,
        *,
        operation_intent: ExternalOperationIntent | None,
        **_: object,
    ) -> ExternalOperationReceipt:
        if not isinstance(node, DerivedBehavioralNode):
            raise AdapterError("fixture adapter accepts only sealed DerivedBehavioralNode")
        if not isinstance(operation_intent, ExternalOperationIntent):
            raise AdapterError("fixture adapter action requires ExternalOperationIntent")
        if (
            operation_intent.node_id != node.node_id
            or operation_intent.run_id != node.run_id
            or operation_intent.run_head_digest != node.run_head_digest
            or operation_intent.manifest_digest != self._manifest.digest
            or operation_intent.effect != node.side_effect
        ):
            raise AdapterError("fixture ExternalOperationIntent does not bind sealed node")
        receipt = self._legacy.act(node, run_head_digest=operation_intent.run_head_digest)
        return ExternalOperationReceipt(
            receipt_id=f"fixture:{operation_intent.operation_id}",
            operation_id=operation_intent.operation_id,
            run_id=operation_intent.run_id,
            manifest_digest=operation_intent.manifest_digest,
            run_head_digest=operation_intent.run_head_digest,
            idempotency_key=operation_intent.idempotency_key,
            status="succeeded" if receipt.outcome == "accepted" else "failed",
            evidence_refs=receipt.evidence_refs,
        )

    def teardown(self) -> object:
        return self._legacy.teardown()


class PersistedFixtureAuthorityAdapter:
    """Compiled fixture provider adapter; inputs come only from admitted bytes."""

    adapter_id = "fixture-user-journey.v1"

    def __init__(
        self, manifest: AdapterManifest, *, snapshot: EnvironmentSnapshot
    ) -> None:
        if (
            not isinstance(manifest, AdapterManifest)
            or manifest.adapter_id != self.adapter_id
            or manifest.mode != "fixture"
            or not isinstance(snapshot, EnvironmentSnapshot)
            or snapshot.adapter_manifest_digest != manifest.digest
        ):
            raise AdapterError("persisted fixture adapter requires exact admitted authority")
        self._manifest = manifest
        self._snapshot = snapshot
        (
            self._expected_before,
            self._observed_state,
            self._evidence_refs,
        ) = require_registered_fixture_source(snapshot.target_identity_digest)

    @property
    def manifest_digest(self) -> str:
        return self._manifest.digest

    def environment_snapshot(self) -> EnvironmentSnapshot:
        return self._snapshot

    def observe_readonly(self, node: DerivedBehavioralNode, /, **_: object) -> Observation:
        if not isinstance(node, DerivedBehavioralNode):
            raise AdapterError("fixture adapter accepts only sealed DerivedBehavioralNode")
        return Observation(
            observation_id=f"fixture-observation:{node.digest}",
            node_id=node.source_anchor_id,
            kind="behavioral",
            observed_state=self._observed_state,
            evidence_refs=self._evidence_refs,
            run_head_digest=node.run_head_digest,
        )

    def act(
        self,
        node: DerivedBehavioralNode,
        /,
        *,
        operation_intent: ExternalOperationIntent | None,
        **_: object,
    ) -> ExternalOperationReceipt:
        if not isinstance(node, DerivedBehavioralNode) or not isinstance(
            operation_intent, ExternalOperationIntent
        ):
            raise AdapterError("persisted fixture action requires sealed node and intent")
        if (
            operation_intent.node_id != node.node_id
            or operation_intent.run_id != node.run_id
            or operation_intent.run_head_digest != node.run_head_digest
            or operation_intent.manifest_digest != self._manifest.digest
            or operation_intent.effect != node.side_effect
        ):
            raise AdapterError("persisted fixture intent does not bind sealed authority")
        succeeded = (
            self._expected_before in node.expected_before
            and self._observed_state in node.expected_after
        )
        return ExternalOperationReceipt(
            receipt_id=f"fixture:{operation_intent.operation_id}",
            operation_id=operation_intent.operation_id,
            run_id=operation_intent.run_id,
            manifest_digest=operation_intent.manifest_digest,
            run_head_digest=operation_intent.run_head_digest,
            idempotency_key=operation_intent.idempotency_key,
            status="succeeded" if succeeded else "failed",
            evidence_refs=self._evidence_refs,
        )

    def teardown(self) -> object:
        return None
