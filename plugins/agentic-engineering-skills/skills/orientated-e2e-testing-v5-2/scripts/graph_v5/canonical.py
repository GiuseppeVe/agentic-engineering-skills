"""Canonical V5 serialization and domain-separated digests."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, is_dataclass
from decimal import Decimal
from typing import Any


class CanonicalizationError(ValueError):
    """Value cannot be represented by V5 canonical JSON."""


def _normalise(value: Any) -> Any:
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, (float, Decimal)):
        raise CanonicalizationError("canonical JSON rejects floating-point values")
    if hasattr(value, "model_dump"):
        return _normalise(value.model_dump(mode="json"))
    if is_dataclass(value):
        return _normalise(asdict(value))
    if isinstance(value, Mapping):
        if not all(isinstance(key, str) for key in value):
            raise CanonicalizationError("canonical JSON mapping keys must be strings")
        return {key: _normalise(value[key]) for key in sorted(value)}
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [_normalise(item) for item in value]
    raise CanonicalizationError(f"canonical JSON rejects {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    """Return deterministic UTF-8 JSON bytes for supported fact values."""

    return json.dumps(
        _normalise(value),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def canonical_json_text(value: Any) -> str:
    return canonical_json_bytes(value).decode("utf-8")


def canonical_trajectory_bytes(value: Any) -> bytes:
    """Return authoritative V1 Trajectory Brief bytes.

    This intentionally shares generic canonical JSON rules while making the
    trajectory boundary explicit at every authority and persistence call site.
    """

    return canonical_json_bytes(value)


def digest_for(domain: str, value: Any) -> str:
    """SHA-256 digest bound to a semantic domain and canonical bytes."""

    if not isinstance(domain, str) or not domain.strip():
        raise CanonicalizationError("digest domain must be a non-empty string")
    encoded_domain = domain.encode("utf-8")
    return hashlib.sha256(encoded_domain + b"\0" + canonical_json_bytes(value)).hexdigest()


def digest_bytes(domain: str, payload: bytes) -> str:
    if not isinstance(domain, str) or not domain.strip():
        raise CanonicalizationError("digest domain must be a non-empty string")
    return hashlib.sha256(domain.encode("utf-8") + b"\0" + payload).hexdigest()


def trajectory_digest(value: Any) -> str:
    """Return domain-separated digest for canonical Trajectory Brief bytes."""

    return digest_bytes("trajectory-brief", canonical_trajectory_bytes(value))
