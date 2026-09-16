"""Registered V5 adapter construction; dynamic imports are intentionally absent."""

from __future__ import annotations

from ..environment import EnvironmentSnapshot
from .fixture_journey import PersistedFixtureAuthorityAdapter, V52FixtureJourneyAdapter
from .host_registry import AdmissionHostProvider, resolve_host_provider
from .manifest import AdapterManifest
from .protocol import AdapterError, JourneyAdapter
from .registry import AdapterDependencies, construct_adapter


def construct_registered_adapter(
    manifest: AdapterManifest,
    *,
    service_bridge: object | None = None,
    fixture_adapter: object | None = None,
    sealed_environment_snapshot: EnvironmentSnapshot | None = None,
) -> JourneyAdapter:
    """Select fixed package factories only from admitted adapter identity."""

    if not isinstance(manifest, AdapterManifest):
        raise AdapterError("registered adapter construction requires strict AdapterManifest")
    return construct_adapter(
        manifest,
        AdapterDependencies(
            service_bridge=service_bridge,
            fixture_adapter=fixture_adapter,
            sealed_environment_snapshot=sealed_environment_snapshot,
        ),
    )


__all__ = (
    "AdapterError",
    "AdmissionHostProvider",
    "JourneyAdapter",
    "PersistedFixtureAuthorityAdapter",
    "V52FixtureJourneyAdapter",
    "construct_registered_adapter",
    "resolve_host_provider",
)
