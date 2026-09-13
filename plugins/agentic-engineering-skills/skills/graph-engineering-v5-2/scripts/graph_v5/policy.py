"""Immutable policy facts used to admit a real-system journey."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
from ipaddress import ip_address
import re
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator

from .models import StrictModel, _json_arrays_to_tuples


_SHA256 = re.compile(r"[0-9a-f]{64}")
_SECRET_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}")
_DNS_LABEL = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?")
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


class PolicyError(ValueError):
    """A policy cannot safely authorize a real-system operation."""


class PolicyStrictModel(StrictModel):
    """Strict immutable policy input that accepts canonical JSON arrays."""

    @model_validator(mode="before")
    @classmethod
    def _freeze_json_arrays(cls, value: Any) -> Any:
        return _json_arrays_to_tuples(value)


def _non_empty(value: str) -> str:
    if not value.strip():
        raise ValueError("must be a non-empty string")
    return value


def _sha256(value: str, *, field_name: str) -> str:
    value = _non_empty(value)
    if _SHA256.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be lowercase SHA-256 hexadecimal")
    return value


def _validate_host_name(value: str) -> str:
    value = _non_empty(value).casefold()
    try:
        address = ip_address(value)
    except ValueError:
        labels = value.split(".")
        if (
            len(value) > 253
            or any(_DNS_LABEL.fullmatch(label) is None for label in labels)
            or value.isdigit()
            or all(label.isdigit() for label in labels)
        ):
            raise ValueError("target must use an exact host name")
    else:
        if value != address.compressed:
            raise ValueError("target must use a canonical exact IP address")
    return value


def _validate_origin(value: str, *, https: bool) -> str:
    value = _non_empty(value)
    parts = urlsplit(value)
    if parts.scheme != ("https" if https else "http"):
        expected = "HTTPS" if https else "HTTP"
        raise ValueError(f"target must be an exact {expected} origin")
    if not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("target must be an exact origin without credentials, query, or fragment")
    if parts.path not in ("", "/"):
        raise ValueError("target must not include a path")
    try:
        port = parts.port
    except ValueError as exc:
        raise ValueError("target port is invalid") from exc
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("target port is invalid")
    host = _validate_host_name(parts.hostname)
    authority_host = f"[{host}]" if ":" in host else host
    authority = authority_host if port is None else f"{authority_host}:{port}"
    return f"{parts.scheme}://{authority}"


class ExactTarget(PolicyStrictModel):
    """One declared endpoint. URL paths and endpoint discovery are forbidden."""

    https_origin: str | None = None
    loopback_origin: str | None = None

    @model_validator(mode="after")
    def _exactly_one_origin(self) -> "ExactTarget":
        if (self.https_origin is None) == (self.loopback_origin is None):
            raise ValueError("target must declare exactly one HTTPS or loopback origin")
        if self.https_origin is not None:
            canonical = _validate_origin(self.https_origin, https=True)
            if canonical != self.https_origin:
                raise ValueError("HTTPS target must be canonical exact origin")
        if self.loopback_origin is not None:
            canonical = _validate_origin(self.loopback_origin, https=False)
            host = urlsplit(canonical).hostname
            if host not in _LOOPBACK_HOSTS:
                raise ValueError("loopback target must use a loopback host")
            if canonical != self.loopback_origin:
                raise ValueError("loopback target must be canonical exact origin")
        return self

    @property
    def origin(self) -> str:
        return self.https_origin or self.loopback_origin or ""

    @property
    def host(self) -> str:
        host = urlsplit(self.origin).hostname
        if host is None:  # Defensive: model validation already proves this.
            raise PolicyError("target host is unavailable")
        return host

    @property
    def is_loopback(self) -> bool:
        if self.loopback_origin is not None or self.host == "localhost":
            return True
        try:
            address = ip_address(self.host)
        except ValueError:
            return False
        if address.is_loopback:
            return True
        mapped = getattr(address, "ipv4_mapped", None)
        return mapped is not None and mapped.is_loopback


class SyntheticScope(PolicyStrictModel):
    namespace: str
    owned_resources: tuple[str, ...]

    _validate_namespace = field_validator("namespace")(_non_empty)

    @field_validator("owned_resources")
    @classmethod
    def _owned_resources_are_distinct(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if not values:
            raise ValueError("synthetic scope must name owned resources")
        normalized = tuple(_non_empty(value) for value in values)
        if len(normalized) != len(set(normalized)):
            raise ValueError("synthetic scope may not duplicate owned resources")
        return normalized


class TypedEffect(PolicyStrictModel):
    effect: str

    @model_validator(mode="before")
    @classmethod
    def _accept_short_effect_form(cls, value: Any) -> Any:
        if isinstance(value, str):
            return {"effect": value}
        return value

    @field_validator("effect")
    @classmethod
    def _effect_is_typed(cls, value: str) -> str:
        value = _non_empty(value)
        if ":" not in value or value.startswith(":") or value.endswith(":"):
            raise ValueError("capability must be a typed effect")
        return value


class RealSystemBudgets(PolicyStrictModel):
    max_user_actions: int = Field(gt=0, le=10_000)
    max_provider_requests: int = Field(gt=0, le=10_000)
    max_cost_micros: int = Field(gt=0, le=1_000_000_000_000)
    max_requests: int = Field(gt=0, le=100_000)
    max_processes: int = Field(gt=0, le=128)
    max_persistence_writes: int = Field(gt=0, le=100_000)
    max_tokens: int = Field(gt=0, le=100_000_000)
    max_duration_ms: int = Field(gt=0, le=86_400_000)


class SecretReference(PolicyStrictModel):
    """Secret handle only. Values cannot enter a manifest."""

    name: str

    @field_validator("name")
    @classmethod
    def _name_is_handle(cls, value: str) -> str:
        if _SECRET_NAME.fullmatch(value) is None:
            raise ValueError("secret reference must be a declared handle name")
        return value


class EgressPolicy(PolicyStrictModel):
    hosts: tuple[str, ...] = ()
    enforcement_receipt: str | None = None

    @field_validator("hosts")
    @classmethod
    def _hosts_are_exact_and_distinct(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(_validate_host_name(value) for value in values)
        if len(normalized) != len(set(normalized)):
            raise ValueError("egress hosts may not repeat")
        return normalized

    @field_validator("enforcement_receipt")
    @classmethod
    def _receipt_is_text_when_declared(cls, value: str | None) -> str | None:
        return None if value is None else _non_empty(value)

    def admit(self, *, required_host: str | None = None) -> "EgressPolicy":
        if required_host is not None and required_host.casefold() not in self.hosts:
            raise PolicyError("egress gate must include the exact target host")
        if self.hosts and self.enforcement_receipt is None:
            raise PolicyError("egress gate requires an enforcement receipt")
        return self


class EvidencePolicy(PolicyStrictModel):
    redaction_policy_digest: str
    allowed_kinds: tuple[
        Literal["log", "trace", "screenshot", "ui", "persistence_assertion"], ...
    ]

    @field_validator("redaction_policy_digest")
    @classmethod
    def _redaction_digest_is_bound(cls, value: str) -> str:
        return _sha256(value, field_name="redaction_policy_digest")

    @field_validator("allowed_kinds")
    @classmethod
    def _evidence_kinds_are_declared(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if not values:
            raise ValueError("evidence policy must permit at least one redacted evidence kind")
        if len(values) != len(set(values)):
            raise ValueError("evidence policy may not repeat evidence kinds")
        return values


class TeardownPolicy(PolicyStrictModel):
    policy: Literal["manual_after_terminal_decision", "manual_only"]
    max_attempts: int = Field(ge=1, le=3)


class ProductionWritePlan(PolicyStrictModel):
    plan_id: str
    write_plan_digest: str
    operations: tuple[str, ...]
    confirmed_by: str
    confirmation_evidence_ref: str

    _validate_text = field_validator(
        "plan_id", "confirmed_by", "confirmation_evidence_ref"
    )(_non_empty)

    @field_validator("write_plan_digest")
    @classmethod
    def _plan_digest_is_bound(cls, value: str) -> str:
        return _sha256(value, field_name="write_plan_digest")

    @field_validator("operations")
    @classmethod
    def _operations_are_exact(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if not values:
            raise ValueError("ProductionWritePlan must declare exact operations")
        normalized = tuple(_non_empty(value) for value in values)
        if len(normalized) != len(set(normalized)):
            raise ValueError("ProductionWritePlan may not duplicate operations")
        return normalized

    @field_validator("confirmation_evidence_ref")
    @classmethod
    def _confirmation_is_explicit(cls, value: str) -> str:
        if any(term in value.casefold() for term in ("implicit", "silence", "inferred")):
            raise ValueError("ProductionWritePlan confirmation_evidence_ref must be explicit")
        return value


_SENSITIVE_ASSIGNMENT = re.compile(
    rb"(?i)\b(?:token|secret|password|api[_-]?key)\s*[=:]\s*(?P<value>[^\s&;]+)"
)
_SENSITIVE_BEARER = re.compile(
    rb"(?i)\b(?:authorization\s*[=:]\s*)?bearer\s+(?P<value>[^\s&;]+)"
)
_SENSITIVE_AUTHORIZATION = re.compile(
    rb"(?i)\bauthorization\s*[=:]\s*(?!bearer\b)(?P<value>[^\s&;]+)"
)
_SENSITIVE_PATTERNS = (
    _SENSITIVE_ASSIGNMENT,
    _SENSITIVE_BEARER,
    _SENSITIVE_AUTHORIZATION,
)
# A fixed display marker can itself contain a secret (for example ``RED`` in
# ``[REDACTED]``). Removal is the only representation-safe replacement.
_REDACTED = b""


@dataclass(frozen=True, slots=True, repr=False)
class EvidenceRedactionPolicy:
    """Ephemeral redaction inputs; resolved secret bytes never become durable facts."""

    redaction_policy_digest: str
    max_output_bytes: int = 1_000_000

    def __post_init__(self) -> None:
        _sha256(
            self.redaction_policy_digest,
            field_name="redaction_policy_digest",
        )
        if not isinstance(self.max_output_bytes, int) or self.max_output_bytes <= 0:
            raise ValueError("max_output_bytes must be a positive integer")
    def __repr__(self) -> str:
        return (
            "EvidenceRedactionPolicy("
            f"redaction_policy_digest={self.redaction_policy_digest!r}, "
            f"max_output_bytes={self.max_output_bytes})"
        )


@dataclass(frozen=True, slots=True)
class RedactionReceipt:
    """Durable-safe proof that one evidence payload was redacted first."""

    policy_digest: str
    redacted_payload_sha256: str
    redacted_bytes: int
    redacted_secret_count: int


@dataclass(frozen=True, slots=True)
class RedactedEvidence:
    payload: bytes
    receipt: RedactionReceipt


class RedactingEvidenceWriter:
    """Reject unknown sensitive bytes before any caller receives evidence."""

    def __init__(self, policy: EvidenceRedactionPolicy) -> None:
        self._policy = policy

    @staticmethod
    def _secret_representations(values: tuple[bytes | str, ...]) -> tuple[bytes, ...]:
        representations: set[bytes] = set()
        for value in values:
            if isinstance(value, str):
                secret = value.encode("utf-8")
            elif isinstance(value, bytes):
                secret = value
            else:
                raise TypeError("secret_values must contain text or bytes")
            if not secret:
                raise ValueError("secret_values may not contain an empty secret")
            standard_base64 = base64.b64encode(secret)
            urlsafe_base64 = base64.urlsafe_b64encode(secret)
            hexadecimal = secret.hex().encode("ascii")
            representations.update(
                (
                    secret,
                    standard_base64,
                    standard_base64.rstrip(b"="),
                    urlsafe_base64,
                    urlsafe_base64.rstrip(b"="),
                    hexadecimal,
                    hexadecimal.upper(),
                )
            )
        return tuple(sorted(representations, key=len, reverse=True))

    def write(
        self,
        payload: bytes,
        *,
        secret_values: tuple[bytes | str, ...] = (),
    ) -> RedactedEvidence:
        if not isinstance(payload, bytes):
            raise TypeError("evidence payload must be bytes")
        if len(payload) > self._policy.max_output_bytes:
            raise PolicyError("output cap exceeded before evidence receipt")

        known_values = self._secret_representations(secret_values)
        for pattern in _SENSITIVE_PATTERNS:
            for match in pattern.finditer(payload):
                if match.group("value") not in known_values:
                    raise PolicyError("redaction cannot prove sensitive output is covered")

        redacted = payload
        redacted_count = 0
        for secret in known_values:
            occurrences = redacted.count(secret)
            if occurrences:
                redacted = redacted.replace(secret, _REDACTED)
                redacted_count += occurrences

        receipt = RedactionReceipt(
            policy_digest=self._policy.redaction_policy_digest,
            redacted_payload_sha256=hashlib.sha256(redacted).hexdigest(),
            redacted_bytes=len(redacted),
            redacted_secret_count=redacted_count,
        )
        return RedactedEvidence(payload=redacted, receipt=receipt)
