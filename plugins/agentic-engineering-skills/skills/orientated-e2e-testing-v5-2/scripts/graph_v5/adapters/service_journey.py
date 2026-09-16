"""Manifest-bound generic bridge adapter for real service journeys."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .manifest import AdapterManifest
from .protocol import AdapterError
from ..environment import EnvironmentSnapshot
from ..models import (
    DerivedBehavioralNode,
    ExternalOperationIntent,
    ExternalOperationReceipt,
    Observation,
    TeardownReceipt,
)


@runtime_checkable
class ServiceJourneyBridge(Protocol):
    """Application-specific bridge. It never receives undeclared authority."""

    def environment_snapshot(self) -> EnvironmentSnapshot: ...

    def observe_readonly(self, node: DerivedBehavioralNode) -> Observation: ...

    def act(
        self, node: DerivedBehavioralNode, operation_intent: ExternalOperationIntent
    ) -> ExternalOperationReceipt: ...

    def teardown(self) -> TeardownReceipt: ...


class ServiceJourneyAdapter:
    """Registered real-system adapter; bridge calls require a durable intent."""

    adapter_id = "service-journey.v1"

    def __init__(
        self,
        manifest: AdapterManifest,
        bridge: object,
        *,
        sealed_environment_snapshot: EnvironmentSnapshot,
    ) -> None:
        if not isinstance(manifest, AdapterManifest):
            raise AdapterError("service adapter requires strict admitted AdapterManifest")
        if manifest.adapter_id != self.adapter_id:
            raise AdapterError("service adapter manifest selects another registered adapter")
        if not isinstance(sealed_environment_snapshot, EnvironmentSnapshot):
            raise AdapterError("service adapter requires sealed EnvironmentSnapshot")
        if sealed_environment_snapshot.adapter_manifest_digest != manifest.digest:
            raise AdapterError("sealed EnvironmentSnapshot does not bind admitted manifest")
        if not hasattr(bridge, "environment_snapshot"):
            raise AdapterError("service adapter bridge lacks environment_snapshot")
        self._manifest = manifest
        self._bridge = bridge
        self._sealed_environment_snapshot = sealed_environment_snapshot

    @property
    def manifest_digest(self) -> str:
        return self._manifest.digest

    def environment_snapshot(self) -> EnvironmentSnapshot:
        snapshot = self.observe_environment_snapshot()
        if snapshot != self._sealed_environment_snapshot:
            raise AdapterError("service environment snapshot does not match sealed EnvironmentSnapshot")
        return snapshot

    def observe_environment_snapshot(self) -> EnvironmentSnapshot:
        """Read strict live identity so replay can evidence every field drift."""

        try:
            snapshot = self._bridge.environment_snapshot()  # type: ignore[attr-defined]
        except Exception as exc:
            raise AdapterError("service bridge cannot produce EnvironmentSnapshot") from exc
        if not isinstance(snapshot, EnvironmentSnapshot):
            raise AdapterError("service bridge must return strict EnvironmentSnapshot")
        return snapshot

    def observe_readonly(self, node: DerivedBehavioralNode) -> Observation:
        self._require_sealed_node(node)
        self.environment_snapshot()
        try:
            observation = self._bridge.observe_readonly(node)  # type: ignore[attr-defined]
        except Exception as exc:
            raise AdapterError("service bridge readonly observation failed") from exc
        if not isinstance(observation, Observation):
            raise AdapterError("service bridge must return strict Observation")
        if observation.node_id != node.source_anchor_id:
            raise AdapterError("service observation does not bind sealed node anchor")
        if observation.run_head_digest != node.run_head_digest:
            raise AdapterError("service observation does not bind sealed Run Head")
        return observation

    def act(
        self,
        node: DerivedBehavioralNode,
        *,
        operation_intent: ExternalOperationIntent | None,
    ) -> ExternalOperationReceipt:
        """Dispatch one bridge action only after exact persisted authority arrives."""

        if not isinstance(operation_intent, ExternalOperationIntent):
            raise AdapterError("real adapter action requires ExternalOperationIntent")
        self._require_sealed_node(node)
        self._require_intent_for_node(node, operation_intent)
        self.environment_snapshot()
        try:
            receipt = self._bridge.act(node, operation_intent)  # type: ignore[attr-defined]
        except Exception as exc:
            raise AdapterError("service bridge action failed") from exc
        if not isinstance(receipt, ExternalOperationReceipt):
            raise AdapterError("service bridge must return strict ExternalOperationReceipt")
        if (
            receipt.operation_id != operation_intent.operation_id
            or receipt.run_id != operation_intent.run_id
            or receipt.manifest_digest != operation_intent.manifest_digest
            or receipt.run_head_digest != operation_intent.run_head_digest
            or receipt.idempotency_key != operation_intent.idempotency_key
        ):
            raise AdapterError("service action receipt does not bind ExternalOperationIntent")
        return receipt

    def teardown(self) -> TeardownReceipt:
        self.environment_snapshot()
        try:
            receipt = self._bridge.teardown()  # type: ignore[attr-defined]
        except Exception as exc:
            raise AdapterError("service bridge teardown failed") from exc
        if not isinstance(receipt, TeardownReceipt):
            raise AdapterError("service bridge must return strict TeardownReceipt")
        return receipt

    def _require_sealed_node(self, node: object) -> DerivedBehavioralNode:
        if not isinstance(node, DerivedBehavioralNode):
            raise AdapterError("service adapter accepts only sealed DerivedBehavioralNode")
        try:
            return DerivedBehavioralNode.model_validate(node.model_dump(mode="python"))
        except ValueError as exc:
            raise AdapterError("sealed service node digest is invalid") from exc

    def _require_intent_for_node(
        self, node: DerivedBehavioralNode, intent: ExternalOperationIntent
    ) -> None:
        if intent.node_id != node.node_id:
            raise AdapterError("ExternalOperationIntent does not bind sealed node")
        if intent.manifest_digest != self._manifest.digest:
            raise AdapterError("ExternalOperationIntent does not bind admitted manifest")
        if intent.run_id != node.run_id or intent.run_head_digest != node.run_head_digest:
            raise AdapterError("ExternalOperationIntent does not bind sealed Run Head")
        if node.action_kind == "verify_only" or node.side_effect is None:
            raise AdapterError("ExternalOperationIntent cannot dispatch verification-only node")
        if intent.effect != node.side_effect:
            raise AdapterError("ExternalOperationIntent effect does not bind sealed node")
