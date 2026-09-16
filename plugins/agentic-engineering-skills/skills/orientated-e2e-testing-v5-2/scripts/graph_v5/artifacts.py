"""Immutable V5 artifact descriptors."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .canonical import canonical_json_bytes, digest_bytes, digest_for

if TYPE_CHECKING:
    from .proof import ImportedRoleOutput


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    domain: str
    digest: str
    payload: bytes
    media_type: str = "application/json"

    @classmethod
    def from_payload(cls, domain: str, payload: Any) -> "ArtifactRecord":
        encoded = canonical_json_bytes(payload)
        return cls(domain=domain, digest=digest_for(domain, payload), payload=encoded)

    @classmethod
    def from_bytes(
        cls, domain: str, payload: bytes, media_type: str
    ) -> "ArtifactRecord":
        """Preserve authoritative non-JSON bytes exactly."""

        if not isinstance(payload, bytes):
            raise TypeError("artifact bytes payload must be bytes")
        if not isinstance(media_type, str) or not media_type.strip():
            raise ValueError("artifact media type must be a non-empty string")
        return cls(
            domain=domain,
            digest=digest_bytes(domain, payload),
            payload=payload,
            media_type=media_type,
        )

    @classmethod
    def from_role_output(cls, output: "ImportedRoleOutput") -> "ArtifactRecord":
        """Store exact role bytes inside an attested canonical envelope."""

        payload = {
            "manifest_id": output.dispatch.manifest.manifest_id,
            "manifest_digest": output.manifest_digest,
            "spine_digest": output.dispatch.spine_digest,
            "context_id": output.dispatch.context_id,
            "issued_mode": output.dispatch.issued_mode,
            "controller_capability": output.dispatch.controller_capability,
            "role": output.dispatch.manifest.role,
            "identity": output.dispatch.manifest.identity,
            "attempt": output.dispatch.manifest.attempt,
            "environment_digest": output.environment_digest,
            "raw_digest": output.raw_digest,
            "raw_payload_b64": base64.b64encode(output.raw_payload).decode("ascii"),
        }
        return cls.from_payload("role-output-attestation", payload)
