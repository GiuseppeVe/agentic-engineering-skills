"""Compiled host-provider boundary for V5.2 admission.

Providers are selected only from adapter IDs already admitted by the static
adapter registry.  Bundle fields carry identities and digests, never paths,
imports, callables, URLs, or credentials.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Literal, Mapping, Protocol

from ..environment import EnvironmentSnapshot
from ..models import EgressGateReceipt, SupervisorAuthorityReceipt
from .manifest import AdapterManifest
from .protocol import JourneyAdapter

if TYPE_CHECKING:
    from ..models import AdmittedProviderAuthority, ConfirmedRealTrajectoryBundle, V52RunState


class HostProviderError(ValueError):
    """A host provider cannot prove its static admission authority."""


class AdmissionHostProvider(Protocol):
    """Fixed package boundary between admitted facts and host setup."""

    provider_id: str

    def validate_bundle_source(
        self, bundle: "ConfirmedRealTrajectoryBundle", manifest: AdapterManifest
    ) -> None: ...

    def acquire_environment_authority(
        self, state: "V52RunState", manifest: AdapterManifest
    ) -> tuple[tuple[SupervisorAuthorityReceipt, ...], EgressGateReceipt | None]: ...

    def construct_adapter(
        self,
        *,
        manifest: AdapterManifest,
        authority: "AdmittedProviderAuthority",
        snapshot: EnvironmentSnapshot,
    ) -> JourneyAdapter: ...


class _StaticHostProvider:
    """Shared validation; subclasses contain no dynamic loading mechanism."""

    provider_id: str
    adapter_id: str
    mode: Literal["fixture", "service"]

    def validate_bundle_source(
        self, bundle: "ConfirmedRealTrajectoryBundle", manifest: AdapterManifest
    ) -> None:
        authority = bundle.provider_authority
        if (
            authority.adapter_id != self.adapter_id
            or authority.adapter_id != manifest.adapter_id
            or authority.provider_id != self.provider_id
        ):
            raise HostProviderError("provider authority does not select registered compiled provider")
        if authority.source_identity_digest != bundle.brief.execution_envelope.target_identity_digest:
            raise HostProviderError("provider authority source does not bind confirmed target")
        if self.mode == "fixture" and manifest.mode != "fixture":
            raise HostProviderError("fixture provider does not admit non-fixture manifest")
        if self.mode == "service" and manifest.mode == "fixture":
            raise HostProviderError("service provider does not admit fixture manifest")

    def construct_adapter(
        self,
        *,
        manifest: AdapterManifest,
        authority: "AdmittedProviderAuthority",
        snapshot: EnvironmentSnapshot,
    ) -> JourneyAdapter:
        if (
            authority.adapter_id != self.adapter_id
            or authority.provider_id != self.provider_id
            or authority.source_identity_digest != snapshot.target_identity_digest
            or snapshot.adapter_manifest_digest != manifest.digest
        ):
            raise HostProviderError("provider adapter construction does not bind persisted authority")
        raise HostProviderError("provider has no compiled persisted adapter")


class _FixtureHostProvider(_StaticHostProvider):
    provider_id = "fixture-host-provider.v1"
    adapter_id = "fixture-user-journey.v1"
    mode: Literal["fixture"] = "fixture"

    def validate_bundle_source(
        self, bundle: "ConfirmedRealTrajectoryBundle", manifest: AdapterManifest
    ) -> None:
        super().validate_bundle_source(bundle, manifest)
        from .fixture_journey import require_registered_fixture_source

        require_registered_fixture_source(
            bundle.provider_authority.source_identity_digest
        )

    def acquire_environment_authority(
        self, state: "V52RunState", manifest: AdapterManifest
    ) -> tuple[tuple[SupervisorAuthorityReceipt, ...], EgressGateReceipt | None]:
        if manifest.mode != "fixture" or manifest.egress.hosts:
            raise HostProviderError("fixture provider requires deny-by-default fixture egress")
        if state.adapter_manifest_digest != manifest.digest:
            raise HostProviderError("fixture provider state does not bind admitted manifest")
        return (), None

    def construct_adapter(
        self,
        *,
        manifest: AdapterManifest,
        authority: "AdmittedProviderAuthority",
        snapshot: EnvironmentSnapshot,
    ) -> JourneyAdapter:
        if (
            authority.adapter_id != self.adapter_id
            or authority.provider_id != self.provider_id
            or authority.source_identity_digest != snapshot.target_identity_digest
            or snapshot.adapter_manifest_digest != manifest.digest
        ):
            raise HostProviderError("provider adapter construction does not bind persisted authority")
        from .fixture_journey import PersistedFixtureAuthorityAdapter

        return PersistedFixtureAuthorityAdapter(manifest, snapshot=snapshot)


class _ServiceHostProvider(_StaticHostProvider):
    provider_id = "service-host-provider.v1"
    adapter_id = "service-journey.v1"
    mode: Literal["service"] = "service"

    def validate_bundle_source(
        self, bundle: "ConfirmedRealTrajectoryBundle", manifest: AdapterManifest
    ) -> None:
        super().validate_bundle_source(bundle, manifest)
        registered_origin = _SERVICE_HOST_ORIGINS_BY_SOURCE_DIGEST.get(
            bundle.provider_authority.source_identity_digest
        )
        if registered_origin != manifest.target.origin:
            raise HostProviderError(
                "provider authority source does not select compiled host registration"
            )

    def acquire_environment_authority(
        self, state: "V52RunState", manifest: AdapterManifest
    ) -> tuple[tuple[SupervisorAuthorityReceipt, ...], EgressGateReceipt | None]:
        if state.adapter_manifest_digest != manifest.digest:
            raise HostProviderError("service provider state does not bind admitted manifest")
        if manifest.egress.hosts:
            raise HostProviderError(
                "service provider requires compiled enforceable egress authority"
            )
        return (), None


_SERVICE_HOST_ORIGINS_BY_SOURCE_DIGEST: Mapping[str, str] = MappingProxyType({})


_PROVIDERS: Mapping[str, AdmissionHostProvider] = MappingProxyType(
    {
        "fixture-user-journey.v1": _FixtureHostProvider(),
        "service-journey.v1": _ServiceHostProvider(),
    }
)


def resolve_host_provider(adapter_id: str) -> AdmissionHostProvider:
    """Resolve one package-compiled provider from admitted adapter identity only."""

    if not isinstance(adapter_id, str) or not adapter_id.strip():
        raise HostProviderError("provider authority requires a registered adapter ID")
    provider = _PROVIDERS.get(adapter_id)
    if provider is None:
        raise HostProviderError("provider authority does not select a registered compiled provider")
    return provider


__all__ = (
    "AdmissionHostProvider",
    "HostProviderError",
    "resolve_host_provider",
)
