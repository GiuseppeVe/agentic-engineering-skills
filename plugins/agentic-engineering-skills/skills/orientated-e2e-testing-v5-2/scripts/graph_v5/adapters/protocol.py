"""Registered journey adapter boundary for sealed V5.2 environments."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..environment import EnvironmentSnapshot
from ..models import (
    DerivedBehavioralNode,
    ExternalOperationIntent,
    ExternalOperationReceipt,
    Observation,
    TeardownReceipt,
)


class AdapterError(ValueError):
    """An adapter attempted work outside sealed, persisted authority."""


@runtime_checkable
class JourneyAdapter(Protocol):
    """One registered adapter. Runtime, never bridge code, owns progression."""

    adapter_id: str

    def environment_snapshot(self) -> EnvironmentSnapshot | object: ...

    def observe_readonly(self, node: DerivedBehavioralNode, /, **kwargs: object) -> Observation: ...

    def act(
        self,
        node: DerivedBehavioralNode,
        /,
        *,
        operation_intent: ExternalOperationIntent | None,
        **kwargs: object,
    ) -> ExternalOperationReceipt | object: ...

    def teardown(self) -> TeardownReceipt | object: ...
