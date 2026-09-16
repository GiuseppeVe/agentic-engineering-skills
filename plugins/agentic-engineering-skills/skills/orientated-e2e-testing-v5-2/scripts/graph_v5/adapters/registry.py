"""Static V5.2 adapter registry; manifests never select imports or factories."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Callable, Literal, Mapping

from ..canonical import digest_for
from ..environment import EnvironmentSnapshot
from .manifest import AdapterManifest
from .protocol import AdapterError, JourneyAdapter
from .service_journey import ServiceJourneyAdapter


AdapterMode = Literal["fixture", "local_isolated", "remote_nonprod", "production_guarded"]


class AdapterManifestError(AdapterError):
    """A manifest does not exactly select one registered V5.2 adapter."""


@dataclass(frozen=True, slots=True)
class AdapterDependencies:
    """Explicit non-authority dependencies admitted factories may consume."""

    service_bridge: object | None = None
    fixture_adapter: object | None = None
    sealed_environment_snapshot: EnvironmentSnapshot | None = None


@dataclass(frozen=True, slots=True)
class AdapterDescriptor:
    adapter_id: str
    supported_modes: frozenset[AdapterMode]
    interface_digest: str
    factory: Callable[[AdapterManifest, AdapterDependencies], JourneyAdapter]


SERVICE_JOURNEY_INTERFACE_DIGEST = digest_for(
    "graph-v5.adapter-interface.v1",
    {"adapter_id": "service-journey.v1", "protocol": "JourneyAdapter.v5.2"},
)
FIXTURE_JOURNEY_INTERFACE_DIGEST = digest_for(
    "graph-v5.adapter-interface.v1",
    {"adapter_id": "fixture-user-journey.v1", "protocol": "JourneyAdapter.v5.2"},
)


def _service_factory(
    manifest: AdapterManifest, dependencies: AdapterDependencies
) -> JourneyAdapter:
    if dependencies.service_bridge is None:
        raise AdapterManifestError("service-journey adapter requires registered bridge")
    if not isinstance(dependencies.sealed_environment_snapshot, EnvironmentSnapshot):
        raise AdapterManifestError("service-journey adapter requires sealed EnvironmentSnapshot")
    return ServiceJourneyAdapter(
        manifest,
        dependencies.service_bridge,
        sealed_environment_snapshot=dependencies.sealed_environment_snapshot,
    )


def _fixture_factory(
    manifest: AdapterManifest, dependencies: AdapterDependencies
) -> JourneyAdapter:
    from .fixture_journey import V52FixtureJourneyAdapter
    from .user_journey import FixtureUserJourneyAdapter

    if not isinstance(dependencies.fixture_adapter, FixtureUserJourneyAdapter):
        raise AdapterManifestError("fixture adapter requires immutable legacy fixture dependency")
    return V52FixtureJourneyAdapter(manifest, dependencies.fixture_adapter)


_DESCRIPTORS: Mapping[str, AdapterDescriptor] = MappingProxyType({
    "service-journey.v1": AdapterDescriptor(
        adapter_id="service-journey.v1",
        supported_modes=frozenset({"local_isolated", "remote_nonprod", "production_guarded"}),
        interface_digest=SERVICE_JOURNEY_INTERFACE_DIGEST,
        factory=_service_factory,
    ),
    "fixture-user-journey.v1": AdapterDescriptor(
        adapter_id="fixture-user-journey.v1",
        supported_modes=frozenset({"fixture"}),
        interface_digest=FIXTURE_JOURNEY_INTERFACE_DIGEST,
        factory=_fixture_factory,
    ),
})


def registered_adapter_ids() -> frozenset[str]:
    return frozenset(_DESCRIPTORS)


def resolve_descriptor(manifest: AdapterManifest) -> AdapterDescriptor:
    if not isinstance(manifest, AdapterManifest):
        raise AdapterManifestError("registry resolution requires strict AdapterManifest")
    descriptor = _DESCRIPTORS.get(manifest.adapter_id)
    if descriptor is None:
        raise AdapterManifestError("adapter id must select a registered adapter")
    if manifest.mode not in descriptor.supported_modes:
        raise AdapterManifestError("registered adapter does not support mode")
    if manifest.adapter_interface_digest != descriptor.interface_digest:
        raise AdapterManifestError("manifest adapter interface digest does not match registration")
    return descriptor


def resolve_adapter(manifest: AdapterManifest) -> AdapterDescriptor:
    """Public resolver used by admission and tests; construction stays explicit."""

    return resolve_descriptor(manifest)


def construct_adapter(
    manifest: AdapterManifest, dependencies: AdapterDependencies
) -> JourneyAdapter:
    return resolve_descriptor(manifest).factory(manifest, dependencies)
