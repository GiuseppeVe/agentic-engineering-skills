"""Strict V5 facts-and-proofs schema. No predecessor runtime model imports."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal, Mapping, Protocol
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    ValidationError,
    field_validator,
    model_validator,
)

from .canonical import canonical_json_text, digest_bytes, digest_for, trajectory_digest


class StrictModel(BaseModel):
    """Reject shadow fields and prevent in-place mutation of durable facts."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


def _json_arrays_to_tuples(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _json_arrays_to_tuples(item) for key, item in value.items()}
    if isinstance(value, list):
        return tuple(_json_arrays_to_tuples(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_json_arrays_to_tuples(item) for item in value)
    return value


class TrajectoryStrictModel(StrictModel):
    """Strict immutable facts that accept JSON arrays as immutable tuples."""

    @model_validator(mode="before")
    @classmethod
    def _freeze_json_arrays(cls, value: Any) -> Any:
        return _json_arrays_to_tuples(value)


def _non_empty(value: str) -> str:
    if not value.strip():
        raise ValueError("must be a non-empty string")
    return value


def _non_empty_terms(values: tuple[str, ...], *, field_name: str) -> tuple[str, ...]:
    if not values:
        raise ValueError(f"{field_name} must not be empty")
    return tuple(_non_empty(value) for value in values)


def _validate_rfc3339(value: str) -> str:
    value = _non_empty(value)
    if "T" not in value or not (value.endswith("Z") or re.search(r"[+-]\d{2}:\d{2}$", value)):
        raise ValueError("must be an RFC 3339 timestamp with timezone")
    try:
        datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError as exc:
        raise ValueError("must be a valid RFC 3339 timestamp") from exc
    return value


class TrajectoryActor(TrajectoryStrictModel):
    role: str
    identity_constraints: tuple[str, ...]

    _validate_role = field_validator("role")(_non_empty)

    @field_validator("identity_constraints")
    @classmethod
    def _identity_constraints_are_nonempty(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _non_empty_terms(values, field_name="identity_constraints")


class FixtureIntent(TrajectoryStrictModel):
    required_state: str
    reset_expectation: str
    forbidden_data: tuple[str, ...]

    _validate_text = field_validator("required_state", "reset_expectation")(_non_empty)

    @field_validator("forbidden_data")
    @classmethod
    def _forbidden_data_is_nonempty(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _non_empty_terms(values, field_name="forbidden_data")


class ObservableTarget(TrajectoryStrictModel):
    description: str
    acceptance: tuple[str, ...]

    _validate_description = field_validator("description")(_non_empty)

    @field_validator("acceptance")
    @classmethod
    def _acceptance_is_observable(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _non_empty_terms(values, field_name="acceptance")


class Landmark(TrajectoryStrictModel):
    landmark_id: str
    description: str
    acceptance: tuple[str, ...]

    _validate_text = field_validator("landmark_id", "description")(_non_empty)

    @field_validator("acceptance")
    @classmethod
    def _acceptance_is_observable(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _non_empty_terms(values, field_name="acceptance")


class ExpectedBehavior(TrajectoryStrictModel):
    behavior_id: str
    statement: str
    applies_to: tuple[str, ...]

    _validate_text = field_validator("behavior_id", "statement")(_non_empty)

    @field_validator("applies_to")
    @classmethod
    def _applies_to_is_nonempty(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _non_empty_terms(values, field_name="applies_to")


class AuthorSignal(TrajectoryStrictModel):
    signal_id: str
    observation: str
    context: str
    evidence_refs: tuple[str, ...] = ()
    authority: Literal["attention_only"] = "attention_only"

    _validate_text = field_validator("signal_id", "observation", "context")(_non_empty)

    @field_validator("evidence_refs")
    @classmethod
    def _evidence_refs_are_text(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_non_empty(value) for value in values)


_ADAPTER_KNOWN_TEST_EFFECTS = frozenset(
    {
        "fixture:reset",
        "fixture:user_journey_action",
        "fixture:persistence_read",
    }
)


class ExecutionEnvelope(TrajectoryStrictModel):
    allowed_environment: str
    allowed_scope: tuple[str, ...]
    allowed_side_effects: tuple[str, ...]
    forbidden_systems: tuple[str, ...]
    escalation_triggers: tuple[str, ...]

    _validate_environment = field_validator("allowed_environment")(_non_empty)

    @field_validator("allowed_scope", "forbidden_systems", "escalation_triggers")
    @classmethod
    def _terms_are_nonempty(cls, values: tuple[str, ...], info: Any) -> tuple[str, ...]:
        return _non_empty_terms(values, field_name=info.field_name)

    @field_validator("allowed_side_effects")
    @classmethod
    def _effects_are_adapter_known(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(_non_empty(value) for value in values)
        unknown = sorted(set(normalized) - _ADAPTER_KNOWN_TEST_EFFECTS)
        if unknown:
            raise ValueError(f"allowed_side_effects contain unknown test effect(s): {unknown}")
        return normalized

    @model_validator(mode="after")
    def _reject_non_test_environments(self) -> "ExecutionEnvelope":
        environment = self.allowed_environment.casefold()
        if "production" in environment or "external" in environment:
            raise ValueError("execution envelope may not permit production or external environments")
        if "test" not in environment and "fixture" not in environment:
            raise ValueError("execution envelope must name an approved test or fixture environment")
        return self

    @property
    def digest(self) -> str:
        return digest_for("execution-envelope", self)


class TrajectoryBrief(TrajectoryStrictModel):
    schema_version: Literal["graph-v5.trajectory-brief.v1"]
    run_id: str
    brief_id: str
    created_at: str
    original_request: str
    test_philosophy: str
    run_rationale: str
    actor: TrajectoryActor
    fixture_intent: FixtureIntent
    start_state: ObservableTarget
    landmarks: tuple[Landmark, ...]
    goal: str
    terminal_outcome: ObservableTarget
    expected_behaviors: tuple[ExpectedBehavior, ...]
    non_goals: tuple[str, ...]
    author_signals: tuple[AuthorSignal, ...]
    execution_envelope: ExecutionEnvelope
    material_ambiguities: tuple[str, ...] = ()

    _validate_text = field_validator(
        "run_id", "brief_id", "original_request", "test_philosophy", "run_rationale", "goal"
    )(_non_empty)
    _validate_created_at = field_validator("created_at")(_validate_rfc3339)

    @field_validator("landmarks", "expected_behaviors", "non_goals")
    @classmethod
    def _required_sequences_are_nonempty(cls, values: tuple[Any, ...], info: Any) -> tuple[Any, ...]:
        if not values:
            raise ValueError(f"{info.field_name} must not be empty")
        if info.field_name == "non_goals":
            return tuple(_non_empty(value) for value in values)
        return values

    @field_validator("material_ambiguities")
    @classmethod
    def _ambiguities_are_named(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_non_empty(value) for value in values)

    @model_validator(mode="after")
    def _trajectory_has_unique_observable_authority(self) -> "TrajectoryBrief":
        landmark_ids = tuple(item.landmark_id for item in self.landmarks)
        behavior_ids = tuple(item.behavior_id for item in self.expected_behaviors)
        signal_ids = tuple(item.signal_id for item in self.author_signals)
        all_ids = landmark_ids + behavior_ids + signal_ids
        if len(all_ids) != len(set(all_ids)):
            raise ValueError("Trajectory Brief IDs must be unique")
        landmark_id_set = set(landmark_ids)
        unknown = sorted(
            {
                landmark_id
                for behavior in self.expected_behaviors
                for landmark_id in behavior.applies_to
                if landmark_id not in landmark_id_set
            }
        )
        if unknown:
            raise ValueError(f"expected behavior applies_to unknown landmark(s): {unknown}")
        return self

    @property
    def digest(self) -> str:
        return trajectory_digest(self)


class TrajectoryConfirmation(TrajectoryStrictModel):
    schema_version: Literal["graph-v5.trajectory-confirmation.v1"]
    run_id: str
    brief_id: str
    trajectory_digest: str
    confirmed_by: str
    confirmed_at: str
    confirmation_evidence_ref: str

    _validate_text = field_validator(
        "run_id", "brief_id", "trajectory_digest", "confirmed_by", "confirmation_evidence_ref"
    )(_non_empty)
    _validate_confirmed_at = field_validator("confirmed_at")(_validate_rfc3339)

    @field_validator("trajectory_digest")
    @classmethod
    def _digest_is_lowercase_sha256(cls, value: str) -> str:
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("trajectory_digest must be lowercase SHA-256 hexadecimal")
        return value

    @field_validator("confirmation_evidence_ref")
    @classmethod
    def _evidence_is_explicit(cls, value: str) -> str:
        if any(term in value.casefold() for term in ("implicit", "silence", "inferred")):
            raise ValueError("confirmation_evidence_ref must reference an explicit response")
        return value


class RealExecutionEnvelope(TrajectoryStrictModel):
    """V5.2 real-system authority. V5.1 fixture envelopes remain unchanged."""

    mode: Literal["fixture", "local_isolated", "remote_nonprod", "production_guarded"]
    target_identity_digest: str
    adapter_manifest_digest: str | None = None

    @field_validator("target_identity_digest")
    @classmethod
    def _target_digest_is_exact(cls, value: str) -> str:
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("target_identity_digest must be lowercase SHA-256 hexadecimal")
        return value

    @field_validator("adapter_manifest_digest")
    @classmethod
    def _manifest_digest_is_exact_or_absent(cls, value: str | None) -> str | None:
        if value is not None and re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("adapter_manifest_digest must be lowercase SHA-256 hexadecimal")
        return value

    @model_validator(mode="after")
    def _real_execution_requires_admitted_manifest(self) -> "RealExecutionEnvelope":
        if self.adapter_manifest_digest is None:
            raise ValueError("real execution envelope requires adapter_manifest_digest")
        return self

    @property
    def digest(self) -> str:
        return digest_for("real-execution-envelope", self)


class V52TrajectoryBrief(TrajectoryStrictModel):
    """Separate V5.2 real-system brief. Never reinterpret V5.1 fixture authority."""

    schema_version: Literal["graph-v5.trajectory-brief.v2"]
    run_id: str
    brief_id: str
    created_at: str
    goal: str
    execution_envelope: RealExecutionEnvelope
    adapter_manifest_digest: str | None = None

    _validate_text = field_validator("run_id", "brief_id", "goal")(_non_empty)
    _validate_created_at = field_validator("created_at")(_validate_rfc3339)

    @field_validator("adapter_manifest_digest")
    @classmethod
    def _manifest_digest_is_exact_or_absent(cls, value: str | None) -> str | None:
        if value is not None and re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("adapter_manifest_digest must be lowercase SHA-256 hexadecimal")
        return value

    @model_validator(mode="after")
    def _brief_binds_exact_real_execution_authority(self) -> "V52TrajectoryBrief":
        if self.adapter_manifest_digest is None:
            raise ValueError("real trajectory authority requires adapter_manifest_digest")
        if self.adapter_manifest_digest != self.execution_envelope.adapter_manifest_digest:
            raise ValueError("real execution envelope adapter_manifest_digest mismatch")
        return self

    @property
    def digest(self) -> str:
        return digest_for("trajectory-brief-v5.2", self)


class V52TrajectoryConfirmation(TrajectoryStrictModel):
    """Explicit confirmation bound to both V5.2 brief and manifest."""

    schema_version: Literal["graph-v5.trajectory-confirmation.v2"]
    run_id: str
    brief_id: str
    trajectory_digest: str
    adapter_manifest_digest: str
    confirmed_by: str
    confirmed_at: str
    confirmation_evidence_ref: str

    _validate_text = field_validator(
        "run_id", "brief_id", "trajectory_digest", "adapter_manifest_digest", "confirmed_by",
        "confirmation_evidence_ref",
    )(_non_empty)
    _validate_confirmed_at = field_validator("confirmed_at")(_validate_rfc3339)

    @field_validator("trajectory_digest", "adapter_manifest_digest")
    @classmethod
    def _digest_is_lowercase_sha256(cls, value: str) -> str:
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("V5.2 confirmation digest must be lowercase SHA-256 hexadecimal")
        return value

    @field_validator("confirmation_evidence_ref")
    @classmethod
    def _evidence_is_explicit(cls, value: str) -> str:
        if any(term in value.casefold() for term in ("implicit", "silence", "inferred")):
            raise ValueError("confirmation_evidence_ref must reference an explicit response")
        return value


class AdmittedProviderAuthority(TrajectoryStrictModel):
    """One compiled host provider and one already-confirmed source identity."""

    schema_version: Literal["graph-v5.admitted-provider-authority.v1"]
    adapter_id: str
    provider_id: str
    source_identity_digest: str

    _validate_text = field_validator("adapter_id", "provider_id")(_non_empty)

    @field_validator("source_identity_digest")
    @classmethod
    def _source_identity_is_exact(cls, value: str) -> str:
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("provider source identity must be lowercase SHA-256 hexadecimal")
        return value

    @property
    def digest(self) -> str:
        return digest_for("admitted-provider-authority", self)


_RESOURCE_KINDS = frozenset(
    {
        "process",
        "port",
        "account",
        "namespace",
        "fixture",
        "provider_correlation",
    }
)


class ResourceLease(StrictModel):
    """Durable resource ownership fact; ownership token remains process-local."""

    lease_id: str
    run_id: str
    resource_kind: Literal[
        "process",
        "port",
        "account",
        "namespace",
        "fixture",
        "provider_correlation",
    ]
    resource_ref: str
    ownership_token_digest: str
    expires_at: str

    _issued_ownership_token: str | None = PrivateAttr(default=None)

    _validate_text = field_validator("lease_id", "run_id", "resource_ref")(_non_empty)
    _validate_expires_at = field_validator("expires_at")(_validate_rfc3339)

    @field_validator("ownership_token_digest")
    @classmethod
    def _ownership_digest_is_exact(cls, value: str) -> str:
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("ownership_token_digest must be lowercase SHA-256 hexadecimal")
        return value

    @classmethod
    def issue(
        cls,
        *,
        run_id: str,
        resource: str,
        expires_at: str | None = None,
    ) -> "ResourceLease":
        """Issue one opaque token and persist only its digest in durable state."""

        if not isinstance(resource, str) or ":" not in resource:
            raise ValueError("resource must be '<resource_kind>:<resource_ref>'")
        resource_kind, resource_ref = resource.split(":", 1)
        if resource_kind not in _RESOURCE_KINDS or not resource_ref.strip():
            raise ValueError("resource must name a supported resource kind and non-empty reference")
        token = secrets.token_urlsafe(32)
        if expires_at is None:
            expires_at = (
                datetime.now(timezone.utc) + timedelta(minutes=15)
            ).isoformat().replace("+00:00", "Z")
        lease = cls(
            lease_id=f"lease-{secrets.token_urlsafe(16)}",
            run_id=run_id,
            resource_kind=resource_kind,
            resource_ref=resource_ref,
            ownership_token_digest=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            expires_at=expires_at,
        )
        lease._issued_ownership_token = token
        return lease

    @property
    def resource(self) -> str:
        return f"{self.resource_kind}:{self.resource_ref}"

    @property
    def issued_ownership_token(self) -> str:
        """Expose token only in issuer process; restored leases must use a secure secret source."""

        if self._issued_ownership_token is None:
            raise ValueError("issued ownership token is unavailable after durable reload")
        return self._issued_ownership_token

    def ownership_matches(self, ownership_token: str) -> bool:
        if not isinstance(ownership_token, str) or not ownership_token:
            return False
        supplied = hashlib.sha256(ownership_token.encode("utf-8")).hexdigest()
        return hmac.compare_digest(supplied, self.ownership_token_digest)

    def is_expired(self, *, now: datetime | None = None) -> bool:
        expiry = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        comparison = now or datetime.now(timezone.utc)
        if comparison.tzinfo is None:
            raise ValueError("lease expiry comparison time must include timezone")
        return comparison >= expiry


class HealthReceipt(StrictModel):
    service_id: str
    lease_id: str
    endpoint: str
    status_code: int | None = Field(default=None, ge=100, le=599)
    checked_at: str

    _validate_text = field_validator("service_id", "lease_id", "endpoint")(_non_empty)
    _validate_checked_at = field_validator("checked_at")(_validate_rfc3339)


class ServiceReceipt(StrictModel):
    service_id: str
    run_id: str
    lease_id: str
    port_lease_id: str
    process_lease: ResourceLease | None = None
    port: int = Field(ge=1, le=65535)
    process_id: int | None = Field(default=None, ge=1)
    status: Literal["ready", "readiness_failed", "port_collision", "spawn_failed"]
    process_tree_terminated: bool
    started_at: str
    health: HealthReceipt | None = None

    _validate_text = field_validator(
        "service_id", "run_id", "lease_id", "port_lease_id"
    )(_non_empty)
    _validate_started_at = field_validator("started_at")(_validate_rfc3339)


class TeardownReceipt(StrictModel):
    service_id: str
    run_id: str
    lease_id: str
    status: Literal["terminated", "not_running", "ownership_unproven"]
    process_tree_terminated: bool
    completed_at: str

    _validate_text = field_validator("service_id", "run_id", "lease_id")(_non_empty)
    _validate_completed_at = field_validator("completed_at")(_validate_rfc3339)


class EgressGateReceipt(TrajectoryStrictModel):
    """Typed proof that one exact egress boundary was admitted for this run."""

    run_id: str
    adapter_manifest_digest: str
    target_identity_digest: str
    allowed_hosts: tuple[str, ...]
    allowed_protocols: tuple[Literal["https"], ...]
    issued_receipt_digest: str

    _validate_text = field_validator("run_id")(_non_empty)

    @field_validator(
        "adapter_manifest_digest", "target_identity_digest", "issued_receipt_digest"
    )
    @classmethod
    def _digests_are_exact(cls, value: str) -> str:
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("egress authority digest must be lowercase SHA-256 hexadecimal")
        return value

    @field_validator("allowed_hosts")
    @classmethod
    def _hosts_are_exact_and_distinct(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        values = _non_empty_terms(values, field_name="allowed_hosts")
        normalized = tuple(value.casefold() for value in values)
        if len(normalized) != len(set(normalized)):
            raise ValueError("egress authority hosts must be distinct")
        return normalized

    @field_validator("allowed_protocols")
    @classmethod
    def _protocols_are_exact(cls, values: tuple[Literal["https"], ...]) -> tuple[Literal["https"], ...]:
        if values != ("https",):
            raise ValueError("egress authority requires exact HTTPS protocol scope")
        return values

    @property
    def digest(self) -> str:
        return digest_for("egress-gate-receipt", self)


class SupervisorAuthorityReceipt(TrajectoryStrictModel):
    """Typed supervisor authority; opaque lease or readiness digests are forbidden."""

    run_id: str
    adapter_manifest_digest: str
    target_identity_digest: str
    service_receipt: ServiceReceipt
    readiness_receipts: tuple[HealthReceipt, ...]
    lease_ids: tuple[str, ...]

    _validate_text = field_validator("run_id")(_non_empty)

    @field_validator("adapter_manifest_digest", "target_identity_digest")
    @classmethod
    def _digests_are_exact(cls, value: str) -> str:
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("supervisor authority digest must be lowercase SHA-256 hexadecimal")
        return value

    @field_validator("lease_ids")
    @classmethod
    def _lease_ids_are_distinct(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        values = _non_empty_terms(values, field_name="lease_ids")
        if len(values) != len(set(values)):
            raise ValueError("supervisor authority lease ids must be distinct")
        return values

    @field_validator("readiness_receipts")
    @classmethod
    def _readiness_receipts_are_present(
        cls, values: tuple[HealthReceipt, ...]
    ) -> tuple[HealthReceipt, ...]:
        if not values:
            raise ValueError("supervisor authority requires readiness receipts")
        return values

    @model_validator(mode="after")
    def _binds_exact_owned_service(self) -> "SupervisorAuthorityReceipt":
        service = self.service_receipt
        if service.run_id != self.run_id:
            raise ValueError("supervisor authority service receipt belongs to another run")
        if (
            service.process_id is None
            or service.process_lease is None
            or service.process_tree_terminated
        ):
            raise ValueError("supervisor authority requires a live owned process")
        process_lease = service.process_lease
        if (
            process_lease.run_id != self.run_id
            or process_lease.resource_kind != "process"
            or process_lease.resource_ref != str(service.process_id)
        ):
            raise ValueError("supervisor authority process lease does not bind ready process")
        if service.lease_id != service.port_lease_id:
            raise ValueError("supervisor authority service lease must equal exact port lease")
        if process_lease.lease_id == service.port_lease_id:
            raise ValueError("supervisor authority requires distinct port and process leases")
        required_leases = (service.port_lease_id, process_lease.lease_id)
        if required_leases != self.lease_ids:
            raise ValueError("supervisor authority must bind exact service lease ids")
        if service.status != "ready":
            raise ValueError("supervisor authority requires ready service receipt")
        if (
            service.health is None
            or self.readiness_receipts != (service.health,)
            or service.health.lease_id != service.port_lease_id
            or service.health.status_code is None
            or not 200 <= service.health.status_code < 300
        ):
            raise ValueError("supervisor authority requires exact healthy readiness receipt")
        if service.health.service_id != service.service_id:
            raise ValueError("supervisor authority readiness receipt does not bind owned service")
        try:
            readiness_port = urlsplit(service.health.endpoint).port
        except ValueError as exc:
            raise ValueError("supervisor authority readiness endpoint is invalid") from exc
        if readiness_port != service.port:
            raise ValueError("supervisor authority readiness endpoint does not bind service port")
        return self

    @property
    def digest(self) -> str:
        return digest_for("supervisor-authority-receipt", self)


class BudgetReservation(TrajectoryStrictModel):
    """Worst-case real-system budget held before an external dispatch."""

    reservation_id: str
    run_id: str
    operation_id: str
    user_actions: int = Field(ge=0)
    provider_requests: int = Field(ge=0)
    cost_micros: int = Field(ge=0)
    requests: int = Field(ge=0)
    processes: int = Field(ge=0)
    persistence_writes: int = Field(ge=0)
    tokens: int = Field(ge=0)
    duration_ms: int = Field(ge=0)
    bytes: int = Field(default=0, ge=0)

    _validate_text = field_validator(
        "reservation_id", "run_id", "operation_id"
    )(_non_empty)

    @model_validator(mode="after")
    def _reserves_some_bounded_work(self) -> "BudgetReservation":
        if not any(
            (
                self.user_actions,
                self.provider_requests,
                self.cost_micros,
                self.requests,
                self.processes,
                self.persistence_writes,
                self.tokens,
                self.duration_ms,
                self.bytes,
            )
        ):
            raise ValueError("budget reservation must reserve at least one bounded resource")
        return self

    @property
    def digest(self) -> str:
        return digest_for("real-system-budget-reservation", self)


class ExternalOperationIntent(TrajectoryStrictModel):
    """Sealed authority for exactly one adapter operation before dispatch."""

    operation_id: str
    run_id: str
    node_id: str
    manifest_digest: str
    run_head_digest: str
    idempotency_key: str
    effect: str
    reserved_budget: BudgetReservation

    _validate_text = field_validator(
        "operation_id", "run_id", "node_id", "idempotency_key", "effect"
    )(_non_empty)

    @field_validator("manifest_digest", "run_head_digest")
    @classmethod
    def _digest_is_exact(cls, value: str) -> str:
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("external operation authority digest must be lowercase SHA-256 hexadecimal")
        return value

    @field_validator("effect")
    @classmethod
    def _effect_is_typed(cls, value: str) -> str:
        if ":" not in value or value.startswith(":") or value.endswith(":"):
            raise ValueError("external operation effect must be typed")
        return value

    @model_validator(mode="after")
    def _reservation_binds_exact_operation(self) -> "ExternalOperationIntent":
        reservation = self.reserved_budget
        if reservation.run_id != self.run_id or reservation.operation_id != self.operation_id:
            raise ValueError("budget reservation must bind exact external operation")
        return self

    @property
    def digest(self) -> str:
        return digest_for("external-operation-intent", self)


class ManifestBudgetExhaustion(TrajectoryStrictModel):
    """Terminal evidence that one exact sealed intent exceeds manifest aggregate caps."""

    run_id: str
    run_head_digest: str
    manifest_digest: str
    rejected_intent: ExternalOperationIntent
    exhausted_budget_names: tuple[
        Literal[
            "max_user_actions",
            "max_provider_requests",
            "max_cost_micros",
            "max_requests",
            "max_processes",
            "max_persistence_writes",
            "max_tokens",
            "max_duration_ms",
        ],
        ...,
    ]

    _validate_text = field_validator("run_id")(_non_empty)

    @field_validator("run_head_digest", "manifest_digest")
    @classmethod
    def _digest_is_exact(cls, value: str) -> str:
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("manifest budget exhaustion digest must be lowercase SHA-256 hexadecimal")
        return value

    @field_validator("exhausted_budget_names")
    @classmethod
    def _exhausted_names_are_distinct(
        cls, values: tuple[str, ...]
    ) -> tuple[str, ...]:
        if not values:
            raise ValueError("manifest budget exhaustion requires exhausted budget names")
        if len(values) != len(set(values)):
            raise ValueError("manifest budget exhaustion budget names must be distinct")
        return values

    @model_validator(mode="after")
    def _rejected_intent_binds_terminal_authority(self) -> "ManifestBudgetExhaustion":
        intent = self.rejected_intent
        if (
            intent.run_id != self.run_id
            or intent.run_head_digest != self.run_head_digest
            or intent.manifest_digest != self.manifest_digest
        ):
            raise ValueError("manifest budget exhaustion must bind exact rejected intent authority")
        return self

    @property
    def digest(self) -> str:
        return digest_for("manifest-budget-exhaustion", self)


class ExternalOperationReceipt(TrajectoryStrictModel):
    """Redacted adapter result bound to one already-persisted operation intent."""

    receipt_id: str
    operation_id: str
    run_id: str
    manifest_digest: str
    run_head_digest: str
    idempotency_key: str
    status: Literal["succeeded", "failed", "unknown"]
    evidence_refs: tuple[str, ...]

    _validate_text = field_validator(
        "receipt_id", "operation_id", "run_id", "idempotency_key"
    )(_non_empty)

    @field_validator("manifest_digest", "run_head_digest")
    @classmethod
    def _receipt_digest_is_exact(cls, value: str) -> str:
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("external operation receipt digest must be lowercase SHA-256 hexadecimal")
        return value

    @field_validator("evidence_refs")
    @classmethod
    def _evidence_refs_are_safe(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if not values:
            raise ValueError("external operation receipt requires redacted evidence references")
        return tuple(_safe_runtime_text(value) for value in values)

    @property
    def digest(self) -> str:
        return digest_for("external-operation-receipt", self)


_SENSITIVE_RUNTIME_TEXT = re.compile(
    r"(?i)(?:"
    r"(?:token|secret|password|api[_-]?key)\s*[=:]"
    r"|(?:authorization\s*[=:]\s*)?bearer\s+\S+"
    r"|authorization\s*[=:]\s*\S+"
    r")"
)


def _safe_runtime_text(value: str) -> str:
    value = _non_empty(value)
    if _SENSITIVE_RUNTIME_TEXT.search(value):
        raise ValueError("runtime facts must be secret-free")
    return value


class RuntimeNote(TrajectoryStrictModel):
    """Append-only, secret-free cleanup record for one leased resource."""

    resource_ref: str
    lease_id: str
    classification: Literal["ephemeral_test_data", "fix_or_patch"]
    receipt_ref: str
    cleanup_intent: str

    _validate_safe_text = field_validator(
        "resource_ref", "lease_id", "receipt_ref", "cleanup_intent"
    )(_safe_runtime_text)

    @property
    def digest(self) -> str:
        return digest_for("runtime-note", self)


class RealSystemRunHead(TrajectoryStrictModel):
    """Run authority bound to one admitted manifest and sealed environment."""

    run_id: str
    manifest_digest: str
    environment_snapshot_digest: str

    _validate_text = field_validator("run_id")(_non_empty)

    @field_validator("manifest_digest", "environment_snapshot_digest")
    @classmethod
    def _head_digest_is_exact(cls, value: str) -> str:
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("real-system Run Head digest must be lowercase SHA-256 hexadecimal")
        return value

    @property
    def digest(self) -> str:
        return digest_for("real-system-run-head", self)


class RealNodeCompletion(TrajectoryStrictModel):
    """One durable completion of a sealed V5.2 node."""

    run_id: str
    node_id: str
    run_head_digest: str
    kind: Literal["external_receipt", "verification"]
    evidence_refs: tuple[str, ...]
    operation_id: str | None = None
    verification_observation: "Observation | None" = None

    _validate_text = field_validator("run_id", "node_id")(_non_empty)

    @field_validator("run_head_digest")
    @classmethod
    def _run_head_digest_is_exact(cls, value: str) -> str:
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("node completion Run Head digest must be lowercase SHA-256 hexadecimal")
        return value

    @field_validator("evidence_refs")
    @classmethod
    def _evidence_refs_are_safe(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        values = _non_empty_terms(values, field_name="evidence_refs")
        if len(values) != len(set(values)):
            raise ValueError("node completion evidence references must be distinct")
        return tuple(_safe_runtime_text(value) for value in values)

    @field_validator("operation_id")
    @classmethod
    def _operation_id_is_nonempty(cls, value: str | None) -> str | None:
        return _non_empty(value) if value is not None else None

    @model_validator(mode="after")
    def _kind_binds_operation_identity(self) -> "RealNodeCompletion":
        if (self.kind == "external_receipt") != (self.operation_id is not None):
            raise ValueError("external node completion requires exactly one operation identity")
        if (self.kind == "verification") != (
            self.verification_observation is not None
        ):
            raise ValueError("verification node completion requires exactly one observation")
        return self

    @property
    def digest(self) -> str:
        return digest_for("real-node-completion", self)


RealSystemDecisionKind = Literal[
    "budget_widening",
    "production_write_confirmation",
    "cleanup",
    "fix_or_patch",
]


class BudgetWideningAmendment(TrajectoryStrictModel):
    """Exact bounded proposal authorized by one exceptional budget decision."""

    kind: Literal["budget_widening"]
    node_id: str
    node_authority_digest: str
    prior_budget_digest: str
    requested_budget: NodeBudgetProposal

    _validate_node_id = field_validator("node_id")(_non_empty)

    @field_validator("node_authority_digest", "prior_budget_digest")
    @classmethod
    def _prior_budget_digest_is_exact(cls, value: str) -> str:
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("prior node budget digest must be lowercase SHA-256 hexadecimal")
        return value


class ProductionWriteConfirmationAmendment(TrajectoryStrictModel):
    """Digest of admitted production synthetic-write plan confirmed by user."""

    kind: Literal["production_write_confirmation"]
    production_write_plan_digest: str

    @field_validator("production_write_plan_digest")
    @classmethod
    def _plan_digest_is_exact(cls, value: str) -> str:
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("production write plan digest must be lowercase SHA-256 hexadecimal")
        return value


class CleanupAmendment(TrajectoryStrictModel):
    """Exact ephemeral-data runtime note authorized for cleanup."""

    kind: Literal["cleanup"]
    runtime_note_digest: str

    @field_validator("runtime_note_digest")
    @classmethod
    def _runtime_note_digest_is_exact(cls, value: str) -> str:
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("cleanup runtime note digest must be lowercase SHA-256 hexadecimal")
        return value


class FixOrPatchAmendment(TrajectoryStrictModel):
    """Declared immutable treatment for one exceptional repair boundary."""

    kind: Literal["fix_or_patch"]
    runtime_note_digest: str
    treatment: Literal["fix", "patch"]

    @field_validator("runtime_note_digest")
    @classmethod
    def _runtime_note_digest_is_exact(cls, value: str) -> str:
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("fix-or-patch runtime note digest must be lowercase SHA-256 hexadecimal")
        return value


RealSystemDecisionAmendment = (
    BudgetWideningAmendment
    | ProductionWriteConfirmationAmendment
    | CleanupAmendment
    | FixOrPatchAmendment
)


class PendingRealSystemDecision(TrajectoryStrictModel):
    """Exact exceptional authority awaiting one user consumption."""

    decision_id: str
    kind: RealSystemDecisionKind
    run_id: str
    run_head_digest: str
    authority_digest: str
    payload_digest: str
    amendment: RealSystemDecisionAmendment

    _validate_text = field_validator("decision_id", "run_id")(_non_empty)

    @field_validator("run_head_digest", "authority_digest", "payload_digest")
    @classmethod
    def _digests_are_exact(cls, value: str) -> str:
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("pending real-system decision digest must be lowercase SHA-256 hexadecimal")
        return value

    @model_validator(mode="after")
    def _binds_exact_kind_specific_amendment(self) -> "PendingRealSystemDecision":
        if self.amendment.kind != self.kind:
            raise ValueError("pending real-system decision amendment kind must match decision kind")
        if self.payload_digest != digest_for("real-system-decision-amendment", self.amendment):
            raise ValueError("pending real-system decision payload digest must bind exact amendment")
        return self

    @property
    def digest(self) -> str:
        return digest_for("pending-real-system-decision", self)


class RealSystemDecision(TrajectoryStrictModel):
    """Explicit user decision bound to one pending exceptional authority fact."""

    decision_id: str
    pending_decision_digest: str
    kind: RealSystemDecisionKind
    run_id: str
    run_head_digest: str
    authority_digest: str
    payload_digest: str
    amendment: RealSystemDecisionAmendment
    actor: str

    _validate_text = field_validator("decision_id", "run_id", "actor")(_non_empty)

    @field_validator(
        "pending_decision_digest",
        "run_head_digest",
        "authority_digest",
        "payload_digest",
    )
    @classmethod
    def _digests_are_exact(cls, value: str) -> str:
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("real-system decision digest must be lowercase SHA-256 hexadecimal")
        return value

    @model_validator(mode="after")
    def _actor_is_explicit_user(self) -> "RealSystemDecision":
        if not self.actor.startswith("user:") or len(self.actor) <= len("user:"):
            raise ValueError("real-system decision requires an explicit user actor")
        if self.amendment.kind != self.kind:
            raise ValueError("real-system decision amendment kind must match decision kind")
        if self.payload_digest != digest_for("real-system-decision-amendment", self.amendment):
            raise ValueError("real-system decision payload digest must bind exact amendment")
        return self

    @property
    def digest(self) -> str:
        return digest_for("real-system-decision", self)


class RealSystemDecisionConsumption(TrajectoryStrictModel):
    """Append-only record that prevents a pending decision from being reused."""

    pending_decision_digest: str
    decision: RealSystemDecision
    amendment: RealSystemDecisionAmendment

    @field_validator("pending_decision_digest")
    @classmethod
    def _pending_digest_is_exact(cls, value: str) -> str:
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("real-system decision consumption digest must be lowercase SHA-256 hexadecimal")
        return value

    @model_validator(mode="after")
    def _decision_binds_pending_digest(self) -> "RealSystemDecisionConsumption":
        if self.decision.pending_decision_digest != self.pending_decision_digest:
            raise ValueError("real-system decision consumption must bind exact pending fact")
        if self.decision.amendment != self.amendment:
            raise ValueError("real-system decision consumption must apply exact immutable amendment")
        return self

    @property
    def digest(self) -> str:
        return digest_for("real-system-decision-consumption", self)


def real_system_decision_target_key(
    pending: PendingRealSystemDecision,
) -> tuple[str, ...]:
    """Stable logical target; differing choices for one target still conflict."""

    amendment = pending.amendment
    if isinstance(amendment, BudgetWideningAmendment):
        return (
            amendment.kind,
            amendment.node_id,
            amendment.node_authority_digest,
            amendment.prior_budget_digest,
        )
    if isinstance(amendment, ProductionWriteConfirmationAmendment):
        return (amendment.kind, amendment.production_write_plan_digest)
    if isinstance(amendment, CleanupAmendment):
        return (amendment.kind, amendment.runtime_note_digest)
    return (amendment.kind, amendment.runtime_note_digest)


class RealSystemFactIndex(TrajectoryStrictModel):
    """Append-only V5.2 facts. V5.1 FactIndex remains fixture-only."""

    environment_snapshot_digest: str | None = None
    run_head: RealSystemRunHead | None = None
    provider_authority: AdmittedProviderAuthority | None = None
    baseline_spine: "BaselineSpineAuthority | None" = None
    exploration_deltas: tuple["ExplorationDelta", ...] = ()
    supervisor_receipts: tuple[SupervisorAuthorityReceipt, ...] = ()
    egress_receipt: EgressGateReceipt | None = None
    leases: tuple[ResourceLease, ...] = ()
    budget_reservations: tuple[BudgetReservation, ...] = ()
    external_operation_intents: tuple[ExternalOperationIntent, ...] = ()
    manifest_budget_exhaustions: tuple[ManifestBudgetExhaustion, ...] = ()
    external_operation_receipts: tuple[ExternalOperationReceipt, ...] = ()
    node_completions: tuple[RealNodeCompletion, ...] = ()
    pending_real_system_decisions: tuple[PendingRealSystemDecision, ...] = ()
    real_system_decision_consumptions: tuple[RealSystemDecisionConsumption, ...] = ()
    runtime_notes: tuple[RuntimeNote, ...] = ()
    cleanup_decision_digests: tuple[str, ...] = ()

    @field_validator("environment_snapshot_digest")
    @classmethod
    def _optional_snapshot_digest_is_exact(cls, value: str | None) -> str | None:
        if value is not None and re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("environment snapshot digest must be lowercase SHA-256 hexadecimal")
        return value

    @model_validator(mode="after")
    def _collections_are_distinct(self) -> "RealSystemFactIndex":
        collections = (
            ("exploration delta", tuple(value.node.node_id for value in self.exploration_deltas)),
            ("supervisor receipt", tuple(value.digest for value in self.supervisor_receipts)),
            ("lease", tuple(value.lease_id for value in self.leases)),
            ("budget reservation", tuple(value.reservation_id for value in self.budget_reservations)),
            ("external operation intent", tuple(value.operation_id for value in self.external_operation_intents)),
            ("manifest budget exhaustion", tuple(value.rejected_intent.operation_id for value in self.manifest_budget_exhaustions)),
            ("external operation receipt", tuple(value.receipt_id for value in self.external_operation_receipts)),
            ("node completion", tuple(value.node_id for value in self.node_completions)),
            ("pending real-system decision", tuple(value.decision_id for value in self.pending_real_system_decisions)),
            ("real-system decision consumption", tuple(value.pending_decision_digest for value in self.real_system_decision_consumptions)),
            ("runtime note", tuple(value.digest for value in self.runtime_notes)),
            ("cleanup decision", self.cleanup_decision_digests),
        )
        for label, values in collections:
            if len(values) != len(set(values)):
                raise ValueError(f"{label} facts must be distinct")
        pending_target_keys = tuple(
            real_system_decision_target_key(value)
            for value in self.pending_real_system_decisions
        )
        if len(pending_target_keys) != len(set(pending_target_keys)):
            raise ValueError("pending real-system decision targets must be distinct")
        if (self.environment_snapshot_digest is None) != (self.run_head is None):
            raise ValueError("sealed environment snapshot and real-system Run Head must coexist")
        if self.baseline_spine is None:
            if (
                self.provider_authority is not None
                or self.exploration_deltas
                or self.supervisor_receipts
                or self.egress_receipt is not None
                or self.manifest_budget_exhaustions
            ):
                raise ValueError("V5.2 authority facts require immutable baseline spine")
            return self
        if self.run_head is None or self.environment_snapshot_digest is None:
            raise ValueError("baseline spine requires sealed environment authority")
        baseline = self.baseline_spine
        if (
            baseline.run_head_digest != self.run_head.digest
            or baseline.environment_snapshot_digest != self.environment_snapshot_digest
            or baseline.adapter_manifest_digest != self.run_head.manifest_digest
        ):
            raise ValueError("baseline spine does not bind sealed real-system authority")
        known_nodes = set(baseline.node_ids)
        for delta in self.exploration_deltas:
            if (
                delta.run_id != baseline.run_id
                or delta.run_head_digest != baseline.run_head_digest
                or delta.adapter_manifest_digest != baseline.adapter_manifest_digest
                or delta.environment_snapshot_digest != baseline.environment_snapshot_digest
                or delta.parent_node_id not in known_nodes
                or delta.node.node_id in known_nodes
            ):
                raise ValueError("exploration delta does not bind prior immutable authority")
            known_nodes.add(delta.node.node_id)
        if len(self.manifest_budget_exhaustions) > 1:
            raise ValueError("only one terminal manifest budget exhaustion may be recorded")
        for exhaustion in self.manifest_budget_exhaustions:
            intent = exhaustion.rejected_intent
            if (
                exhaustion.run_id != baseline.run_id
                or exhaustion.run_head_digest != baseline.run_head_digest
                or exhaustion.manifest_digest != baseline.adapter_manifest_digest
                or intent.node_id not in known_nodes
                or intent.operation_id
                in {item.operation_id for item in self.external_operation_intents}
                or intent.idempotency_key
                in {item.idempotency_key for item in self.external_operation_intents}
                or intent.reserved_budget.reservation_id
                in {item.reservation_id for item in self.budget_reservations}
                or intent.operation_id
                in {
                    item.operation_id
                    for item in self.external_operation_receipts
                }
            ):
                raise ValueError("manifest budget exhaustion must not persist rejected operation authority")
        for completion in self.node_completions:
            if (
                completion.run_id != baseline.run_id
                or completion.run_head_digest != baseline.run_head_digest
                or completion.node_id not in known_nodes
            ):
                raise ValueError("node completion does not bind admitted node authority")
            if completion.kind == "external_receipt":
                receipt = next(
                    (
                        item
                        for item in self.external_operation_receipts
                        if item.operation_id == completion.operation_id
                    ),
                    None,
                )
                intent = next(
                    (
                        item
                        for item in self.external_operation_intents
                        if item.operation_id == completion.operation_id
                    ),
                    None,
                )
                if (
                    receipt is None
                    or intent is None
                    or receipt.status != "succeeded"
                    or intent.node_id != completion.node_id
                    or receipt.evidence_refs != completion.evidence_refs
                ):
                    raise ValueError("external node completion requires exact successful receipt")
        pending_by_digest = {
            pending.digest: pending for pending in self.pending_real_system_decisions
        }
        for consumption in self.real_system_decision_consumptions:
            pending = pending_by_digest.get(consumption.pending_decision_digest)
            decision = consumption.decision
            if (
                pending is None
                or decision.decision_id != pending.decision_id
                or decision.kind != pending.kind
                or decision.run_id != pending.run_id
                or decision.run_head_digest != pending.run_head_digest
                or decision.authority_digest != pending.authority_digest
                or decision.payload_digest != pending.payload_digest
                or decision.amendment != pending.amendment
                or consumption.amendment != decision.amendment
            ):
                raise ValueError("real-system decision consumption does not bind exact pending authority")
        for receipt in self.supervisor_receipts:
            if (
                receipt.run_id != baseline.run_id
                or receipt.adapter_manifest_digest != baseline.adapter_manifest_digest
            ):
                raise ValueError("supervisor receipt does not bind baseline authority")
        if self.egress_receipt is not None and (
            self.egress_receipt.run_id != baseline.run_id
            or self.egress_receipt.adapter_manifest_digest != baseline.adapter_manifest_digest
        ):
            raise ValueError("egress receipt does not bind baseline authority")
        if any(re.fullmatch(r"[0-9a-f]{64}", value) is None for value in self.cleanup_decision_digests):
            raise ValueError("cleanup decision digest must be lowercase SHA-256 hexadecimal")
        return self


class CleanupDecision(TrajectoryStrictModel):
    """Explicit cleanup authority for one immutable runtime note."""

    decision_id: str
    run_id: str
    manifest_digest: str
    runtime_note_digest: str
    actor: str

    _validate_text = field_validator("decision_id", "run_id", "actor")(_non_empty)

    @field_validator("manifest_digest", "runtime_note_digest")
    @classmethod
    def _cleanup_digest_is_exact(cls, value: str) -> str:
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("cleanup decision digest must be lowercase SHA-256 hexadecimal")
        return value

    @model_validator(mode="after")
    def _cleanup_actor_is_explicit_user(self) -> "CleanupDecision":
        if not self.actor.startswith("user:") or len(self.actor) <= len("user:"):
            raise ValueError("cleanup decision requires an explicit user actor")
        return self

    @property
    def digest(self) -> str:
        return digest_for("runtime-cleanup-decision", self)


class V52RunState(TrajectoryStrictModel):
    """Immutable V5.2 run state; a V5 store is projected, never migrated."""

    schema_version: Literal["graph-v5.run-state.v2"]
    run_id: str
    mode: Literal["boot", "running", "paused", "verified", "blocked", "failed", "cancelled"]
    trajectory: V52TrajectoryBrief
    confirmation: V52TrajectoryConfirmation
    facts: RealSystemFactIndex = Field(default_factory=RealSystemFactIndex)

    _validate_run_id = field_validator("run_id")(_non_empty)

    @model_validator(mode="after")
    def _real_state_is_bound_to_confirmed_authority(self) -> "V52RunState":
        if self.run_id != self.trajectory.run_id or self.run_id != self.confirmation.run_id:
            raise ValueError("V5.2 run identity must match confirmed trajectory")
        if self.confirmation.brief_id != self.trajectory.brief_id:
            raise ValueError("V5.2 confirmation brief identity mismatch")
        if self.confirmation.trajectory_digest != self.trajectory.digest:
            raise ValueError("V5.2 confirmation trajectory digest mismatch")
        if self.confirmation.adapter_manifest_digest != self.trajectory.adapter_manifest_digest:
            raise ValueError("V5.2 confirmation adapter manifest digest mismatch")
        if self.facts.run_head is not None:
            head = self.facts.run_head
            if (
                head.run_id != self.run_id
                or head.manifest_digest != self.adapter_manifest_digest
                or head.environment_snapshot_digest != self.facts.environment_snapshot_digest
            ):
                raise ValueError("real-system Run Head must bind admitted authority")
        baseline = self.facts.baseline_spine
        if baseline is not None and (
            baseline.run_id != self.run_id
            or baseline.adapter_manifest_digest != self.adapter_manifest_digest
            or baseline.environment_snapshot_digest != self.facts.environment_snapshot_digest
        ):
            raise ValueError("baseline spine must bind admitted V5.2 state")
        provider = self.facts.provider_authority
        if provider is not None and (
            provider.source_identity_digest
            != self.trajectory.execution_envelope.target_identity_digest
        ):
            raise ValueError("admitted provider source must bind confirmed V5.2 target identity")
        for lease in self.facts.leases:
            if lease.run_id != self.run_id:
                raise ValueError("resource lease belongs to another real-system run")
        for reservation in self.facts.budget_reservations:
            if reservation.run_id != self.run_id:
                raise ValueError("budget reservation belongs to another real-system run")
        for intent in self.facts.external_operation_intents:
            if intent.run_id != self.run_id or intent.manifest_digest != self.adapter_manifest_digest:
                raise ValueError("external operation intent must bind admitted authority")
        for exhaustion in self.facts.manifest_budget_exhaustions:
            if (
                exhaustion.run_id != self.run_id
                or exhaustion.manifest_digest != self.adapter_manifest_digest
            ):
                raise ValueError("manifest budget exhaustion must bind admitted authority")
        if self.facts.manifest_budget_exhaustions and self.mode != "blocked":
            raise ValueError("manifest budget exhaustion requires blocked run mode")
        return self

    @property
    def adapter_manifest_digest(self) -> str:
        manifest_digest = self.trajectory.adapter_manifest_digest
        if manifest_digest is None:  # Defensive: V52TrajectoryBrief rejects this.
            raise ValueError("V5.2 run state lacks admitted adapter manifest")
        return manifest_digest

    @property
    def digest(self) -> str:
        return digest_for("run-state-v5.2", self)


class LegacyRunImmutableProjection(StrictModel):
    """Read-only status projection for durable V5.1 stores."""

    schema_version: Literal["graph-v5.legacy-run-immutable.v1"] = "graph-v5.legacy-run-immutable.v1"
    status: Literal["legacy_run_immutable"] = "legacy_run_immutable"
    legacy_schema_version: Literal["v5"]
    run_id: str

    _validate_run_id = field_validator("run_id")(_non_empty)


def legacy_run_immutable_projection(store: Mapping[str, Any]) -> LegacyRunImmutableProjection:
    """Expose a V5.1 store without translating it into V5.2 authority."""

    if not isinstance(store, Mapping) or store.get("schema_version") != "v5":
        raise ValueError("only schema_version 'v5' stores may be projected as legacy_run_immutable")
    run_id = store.get("run_id")
    if not isinstance(run_id, str):
        raise ValueError("legacy V5 store must contain run_id")
    return LegacyRunImmutableProjection(legacy_schema_version="v5", run_id=run_id)


# Names describe role at callers that distinguish fixture and real authority.
RealTrajectoryBrief = V52TrajectoryBrief
RealTrajectoryConfirmation = V52TrajectoryConfirmation
RealRunState = V52RunState


class ConfirmedTrajectoryBundle(TrajectoryStrictModel):
    brief: TrajectoryBrief
    markdown_utf8: bytes
    confirmation: TrajectoryConfirmation

    def model_copy(
        self,
        *,
        update: Mapping[str, Any] | None = None,
        deep: bool = False,
    ) -> "ConfirmedTrajectoryBundle":
        """Copy only through full validation of all authority bindings."""

        candidate = super().model_copy(update=update, deep=deep)
        return type(self).model_validate(candidate.model_dump(mode="python"))

    @model_validator(mode="after")
    def _enforce_confirmation_boundary(self) -> "ConfirmedTrajectoryBundle":
        if self.brief.material_ambiguities:
            raise ValueError("material ambiguities remain unresolved")
        if (
            self.confirmation.run_id != self.brief.run_id
            or self.confirmation.brief_id != self.brief.brief_id
        ):
            raise ValueError("confirmation identity mismatch")
        if self.confirmation.trajectory_digest != self.brief.digest:
            raise ValueError("confirmation trajectory digest mismatch")

        # Local import avoids a module cycle while ensuring direct model
        # construction cannot bypass exact-byte Markdown validation.
        from .trajectory import render_trajectory_markdown

        if self.markdown_utf8 != render_trajectory_markdown(self.brief):
            raise ValueError("Markdown differs from canonical trajectory")
        return self


class ConfirmedTrajectoryBinding(StrictModel):
    """Durable binding between one run and its confirmed trajectory artifacts."""

    run_id: str
    trajectory_digest: str
    markdown_digest: str
    confirmation_digest: str

    _validate_text = field_validator(
        "run_id", "trajectory_digest", "markdown_digest", "confirmation_digest"
    )(_non_empty)

    @field_validator("trajectory_digest", "markdown_digest", "confirmation_digest")
    @classmethod
    def _digest_is_lowercase_sha256(cls, value: str) -> str:
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("confirmed trajectory binding digests must be lowercase SHA-256 hexadecimal")
        return value

    @property
    def digest(self) -> str:
        return digest_for("confirmed-trajectory-binding", self)


_LIMIT_UNITS: dict[str, str] = {
    "causal_radius": "graph_hops",
    "failed_repair_cycles": "count_per_node",
    "diagnostic_widening": "evidence_connected_ring",
    "reasoning_escalation": "count_per_stall_fingerprint",
    "discovery_commands": "commands_per_cone",
    "discovery_duration": "milliseconds_per_cone",
    "repair_attempts": "patch_attempts_per_cone",
    "repair_commands": "commands_per_cone",
    "repair_duration": "milliseconds_per_cone",
    "artifact_output_per_command": "bytes_per_command",
    "artifact_output_per_run": "bytes_per_run",
    "agent_dispatches_per_cone": "dispatches_per_cone",
    "agent_dispatches_per_run": "dispatches_per_run",
    "model_calls_per_cone": "calls_per_cone",
    "model_calls_per_run": "calls_per_run",
    "model_reasoning_tokens_per_cone": "tokens_per_cone",
    "model_reasoning_tokens_per_run": "tokens_per_run",
    "model_reasoning_cost_per_cone": "normalized_provider_cost_per_cone",
    "model_reasoning_cost_per_run": "normalized_provider_cost_per_run",
    "global_work_commands": "commands_per_run",
    "global_work_duration": "milliseconds_per_run",
}
_REQUIRED_RUN_LIMITS = frozenset(_LIMIT_UNITS)


class LimitValue(StrictModel):
    name: str
    amount: int = Field(gt=0)
    unit: str

    _validate_name = field_validator("name")(_non_empty)
    _validate_unit = field_validator("unit")(_non_empty)

    @model_validator(mode="after")
    def _unit_matches_named_limit(self) -> "LimitValue":
        expected = _LIMIT_UNITS.get(self.name)
        if expected is None:
            raise ValueError(f"unknown V5 Run Limit: {self.name}")
        if self.unit != expected:
            raise ValueError(f"{self.name} must use unit {expected}")
        return self


class RunLimits(StrictModel):
    version: int = Field(ge=1)
    source_profile: str
    source_digest: str
    values: tuple[LimitValue, ...]

    _validate_text = field_validator("source_profile", "source_digest")(_non_empty)

    @model_validator(mode="after")
    def _complete_named_values(self) -> "RunLimits":
        names = tuple(value.name for value in self.values)
        if len(names) != len(set(names)):
            raise ValueError("Run Limits may not duplicate a named limit")
        missing = _REQUIRED_RUN_LIMITS - set(names)
        if missing:
            raise ValueError(f"Run Limits missing required values: {sorted(missing)}")
        return self

    def value_for(self, name: str) -> LimitValue:
        for value in self.values:
            if value.name == name:
                return value
        raise KeyError(name)


class LimitAmendment(StrictModel):
    old_version: int = Field(ge=1)
    new_version: int = Field(ge=2)
    name: str
    old_value: LimitValue
    new_value: LimitValue
    reason: str
    approver: str
    effective_graph_revision: int = Field(ge=0)

    _validate_text = field_validator("name", "reason", "approver")(_non_empty)

    @model_validator(mode="after")
    def _is_a_real_widening(self) -> "LimitAmendment":
        if self.new_version != self.old_version + 1:
            raise ValueError("limits amendments must advance exactly one version")
        if self.old_value.name != self.name or self.new_value.name != self.name:
            raise ValueError("limits amendment values must match amended name")
        if self.old_value.unit != self.new_value.unit:
            raise ValueError("limits amendment may not change unit")
        if self.new_value.amount <= self.old_value.amount:
            raise ValueError("limits amendment must widen, never narrow")
        return self


class VersionedLimits(StrictModel):
    versions: tuple[RunLimits, ...]
    active_version: int = Field(ge=1)
    amendments: tuple[LimitAmendment, ...] = ()

    @model_validator(mode="after")
    def _versions_are_append_only(self) -> "VersionedLimits":
        if not self.versions:
            raise ValueError("at least one Run Limits version is required")
        version_numbers = tuple(version.version for version in self.versions)
        expected = tuple(range(1, len(self.versions) + 1))
        if version_numbers != expected:
            raise ValueError("Run Limits versions must be contiguous from version 1")
        if self.active_version != self.versions[-1].version:
            raise ValueError("active Run Limits must be latest immutable version")
        if len(self.amendments) != len(self.versions) - 1:
            raise ValueError("each appended Run Limits version needs one amendment")
        for amendment, old, new in zip(self.amendments, self.versions, self.versions[1:]):
            if amendment.old_version != old.version or amendment.new_version != new.version:
                raise ValueError("limits amendment must bind adjacent versions")
            old_values = {item.name: item for item in old.values}
            new_values = {item.name: item for item in new.values}
            if set(old_values) != set(new_values):
                raise ValueError("limits amendment may not add or remove values")
            if amendment.name not in old_values:
                raise ValueError("limits amendment names an unknown value")
            if amendment.old_value != old_values[amendment.name]:
                raise ValueError("limits amendment old value does not match prior version")
            if amendment.new_value != new_values[amendment.name]:
                raise ValueError("limits amendment does not match appended value")
            for name, old_value in old_values.items():
                new_value = new_values[name]
                if name == amendment.name:
                    if new_value.unit != old_value.unit or new_value.amount <= old_value.amount:
                        raise ValueError("amended limit must widen without changing unit")
                elif new_value != old_value:
                    raise ValueError("unamended limits must remain unchanged")
            if new.source_profile != old.source_profile or new.source_digest != old.source_digest:
                raise ValueError("limits source identity may not change across amendments")
        return self

    @property
    def active(self) -> RunLimits:
        return self.versions[-1]

    def append_widening(
        self,
        *,
        name: str,
        amount: int,
        approver: str,
        reason: str,
        effective_graph_revision: int,
    ) -> "VersionedLimits":
        old_value = self.active.value_for(name)
        new_value = LimitValue(name=name, amount=amount, unit=old_value.unit)
        replacement = tuple(
            new_value if value.name == name else value for value in self.active.values
        )
        new_version = RunLimits(
            version=self.active.version + 1,
            source_profile=self.active.source_profile,
            source_digest=self.active.source_digest,
            values=replacement,
        )
        amendment = LimitAmendment(
            old_version=self.active.version,
            new_version=new_version.version,
            name=name,
            old_value=old_value,
            new_value=new_value,
            reason=reason,
            approver=approver,
            effective_graph_revision=effective_graph_revision,
        )
        return VersionedLimits(
            versions=self.versions + (new_version,),
            active_version=new_version.version,
            amendments=self.amendments + (amendment,),
        )


class EnvironmentIdentity(StrictModel):
    repository_revision: str
    runtime: str
    package_manager: str
    lockfile_digest: str
    host_fingerprint: str

    _validate_text = field_validator(
        "repository_revision", "runtime", "package_manager", "lockfile_digest", "host_fingerprint"
    )(_non_empty)

    @property
    def digest(self) -> str:
        return digest_for("environment-identity", self)


class HostPreflightReceipt(StrictModel):
    transaction_id: str
    repository_root: str
    repository_revision: str
    requested_base_revision: str
    candidate_worktree_path: str
    durable_store_root: str
    required_node_major: int
    node_executable: str
    node_version: str
    npm_executable: str
    npm_version: str
    package_manager: str
    lockfile_path: str
    lockfile_digest: str
    projected_path_length: int
    path_reserve_chars: int
    long_paths_enabled: bool
    git_filemode: str
    host_fingerprint: str
    environment: EnvironmentIdentity

    _validate_text = field_validator(
        "transaction_id",
        "repository_root",
        "repository_revision",
        "requested_base_revision",
        "candidate_worktree_path",
        "durable_store_root",
        "node_executable",
        "node_version",
        "npm_executable",
        "npm_version",
        "package_manager",
        "lockfile_path",
        "lockfile_digest",
        "git_filemode",
        "host_fingerprint",
    )(_non_empty)

    @model_validator(mode="after")
    def _identity_is_receipt_bound(self) -> "HostPreflightReceipt":
        if self.environment.repository_revision != self.repository_revision:
            raise ValueError("environment repository revision must match host receipt")
        if self.environment.lockfile_digest != self.lockfile_digest:
            raise ValueError("environment lockfile digest must match host receipt")
        if self.environment.host_fingerprint != self.host_fingerprint:
            raise ValueError("environment host fingerprint must match host receipt")
        if re.fullmatch(r"\d+\.\d+\.\d+", self.node_version) is None:
            raise ValueError("host receipt node_version must be strict semantic version")
        if re.fullmatch(r"\d+\.\d+\.\d+", self.npm_version) is None:
            raise ValueError("host receipt npm_version must be strict semantic version")
        if int(self.node_version.split(".", 1)[0]) != self.required_node_major:
            raise ValueError("host receipt Node major must match required_node_major")
        if self.environment.runtime != f"node-{self.node_version}":
            raise ValueError("environment runtime must match host receipt Node version")
        if self.package_manager != "npm":
            raise ValueError("host receipt package manager must be npm")
        if self.environment.package_manager != f"{self.package_manager}-{self.npm_version}":
            raise ValueError("environment package manager must match host receipt npm version")
        if (
            self.required_node_major < 1
            or self.projected_path_length < 1
            or self.path_reserve_chars < 0
        ):
            raise ValueError("host receipt has invalid numeric values")
        return self


class BootstrapIntent(StrictModel):
    run_id: str
    transaction_id: str
    requested_base_revision: str
    candidate_branch: str
    candidate_worktree_path: str
    compensation_plan: tuple[str, ...]

    _validate_text = field_validator(
        "run_id", "transaction_id", "requested_base_revision", "candidate_branch", "candidate_worktree_path"
    )(_non_empty)


class GitTransaction(StrictModel):
    transaction_id: str
    requested_base_revision: str
    branch: str
    worktree_path: str
    status: Literal["prepared", "created", "reconciled", "compensated", "failed"]

    _validate_text = field_validator(
        "transaction_id", "requested_base_revision", "branch", "worktree_path"
    )(_non_empty)


class Observation(StrictModel):
    observation_id: str
    node_id: str
    kind: Literal["behavioral", "operational", "persistence", "variant"]
    observed_state: str
    evidence_refs: tuple[str, ...]
    run_head_digest: str

    _validate_text = field_validator(
        "observation_id", "node_id", "observed_state", "run_head_digest"
    )(_non_empty)


class SpineFrontier(StrictModel):
    """Current immutable position in one confirmed landmark projection."""

    last_reached_landmark_id: str | None = None
    target_landmark_id: str | None
    unexecuted_node_id: str | None = None

    @field_validator("last_reached_landmark_id", "target_landmark_id", "unexecuted_node_id")
    @classmethod
    def _optional_ids_are_nonempty(cls, value: str | None) -> str | None:
        return _non_empty(value) if value is not None else value


class NodeProposal(StrictModel):
    """Runtime-only candidate. It has no authority until ObservableSpine seals it."""

    node_id: str
    source_anchor_id: str
    target_landmark_id: str
    action_kind: Literal["act", "probe", "verify_only"]
    action_or_probe: str
    expected_before: tuple[str, ...]
    expected_after: tuple[str, ...]
    derivation_reason: str
    authority_refs: tuple[str, ...]
    execution_scope: str
    side_effect: str | None
    target_systems: tuple[str, ...]

    _validate_text = field_validator(
        "node_id",
        "source_anchor_id",
        "target_landmark_id",
        "action_or_probe",
        "derivation_reason",
        "execution_scope",
    )(_non_empty)

    @field_validator(
        "expected_before", "expected_after", "authority_refs", "target_systems"
    )
    @classmethod
    def _required_terms(cls, values: tuple[str, ...], info: Any) -> tuple[str, ...]:
        return _non_empty_terms(values, field_name=info.field_name)

    @field_validator("side_effect")
    @classmethod
    def _optional_effect_is_nonempty(cls, value: str | None) -> str | None:
        return _non_empty(value) if value is not None else value

    @model_validator(mode="after")
    def _effect_matches_action_kind(self) -> "NodeProposal":
        if self.action_kind == "verify_only" and self.side_effect is not None:
            raise ValueError("verification-only proposal cannot declare a side effect")
        if self.action_kind != "verify_only" and self.side_effect is None:
            raise ValueError("action or probe proposal requires an exact side effect")
        return self

    @property
    def digest(self) -> str:
        return digest_for("node-proposal", self)


class NodeBudgetProposal(TrajectoryStrictModel):
    """Worst-case bound for one effectful persisted proposal."""

    max_user_actions: int = Field(ge=1, le=10_000)
    max_provider_requests: int = Field(ge=1, le=10_000)
    max_cost_micros: int = Field(ge=1, le=1_000_000_000_000)
    max_requests: int = Field(ge=1, le=100_000)
    max_bytes: int = Field(ge=1, le=1_000_000_000)
    max_wall_seconds: int = Field(ge=1, le=86_400)

    @property
    def digest(self) -> str:
        return digest_for("node-budget-proposal", self)


def validate_node_budget_against_manifest(
    budget: NodeBudgetProposal, manifest: object, *, authority: str
) -> None:
    """Reject typed per-node authority wider than immutable manifest ceilings."""

    for node_name, manifest_name, label in (
        ("max_user_actions", "max_user_actions", "user-action"),
        ("max_provider_requests", "max_provider_requests", "provider-request"),
        ("max_cost_micros", "max_cost_micros", "cost"),
    ):
        if getattr(budget, node_name) > getattr(manifest.budgets, manifest_name):
            raise ValueError(f"{authority} {label} budget exceeds admitted budget")


class BaselineNodeProposal(TrajectoryStrictModel):
    """Canonical pre-Run-Head node authority and its bounded work proposal."""

    proposal: NodeProposal
    entry_observation_refs: tuple[str, ...]
    budget: NodeBudgetProposal | None

    @field_validator("entry_observation_refs")
    @classmethod
    def _entry_observations_are_distinct(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        values = _non_empty_terms(values, field_name="entry_observation_refs")
        if len(values) != len(set(values)):
            raise ValueError("baseline entry observation references must be distinct")
        return values

    @model_validator(mode="after")
    def _budget_matches_effect_class(self) -> "BaselineNodeProposal":
        if self.proposal.action_kind == "verify_only" and self.budget is not None:
            raise ValueError("verification-only baseline proposal cannot reserve a budget")
        if self.proposal.action_kind != "verify_only" and self.budget is None:
            raise ValueError("effectful baseline proposal requires a bounded budget")
        return self

    @property
    def proposal_digest(self) -> str:
        return self.proposal.digest

    @property
    def budget_digest(self) -> str | None:
        return None if self.budget is None else self.budget.digest

    @property
    def digest(self) -> str:
        return digest_for("baseline-node-proposal", self)


class ConfirmedRealTrajectoryBundle(TrajectoryStrictModel):
    """Single canonical V5.2 admission input; it carries no sealed Run Head."""

    schema_version: Literal["graph-v5.confirmed-real-trajectory-bundle.v1"]
    brief: V52TrajectoryBrief
    confirmation: V52TrajectoryConfirmation
    baseline: tuple[BaselineNodeProposal, ...]
    provider_authority: AdmittedProviderAuthority

    def model_copy(
        self,
        *,
        update: Mapping[str, Any] | None = None,
        deep: bool = False,
    ) -> "ConfirmedRealTrajectoryBundle":
        candidate = super().model_copy(update=update, deep=deep)
        return type(self).model_validate(candidate.model_dump(mode="python"))

    @field_validator("baseline")
    @classmethod
    def _baseline_is_nonempty_and_unique(
        cls, values: tuple[BaselineNodeProposal, ...]
    ) -> tuple[BaselineNodeProposal, ...]:
        if not values:
            raise ValueError("baseline must contain at least one canonical proposal")
        node_ids = tuple(item.proposal.node_id for item in values)
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("baseline proposal node IDs must be unique")
        return values

    @model_validator(mode="after")
    def _binds_exact_confirmed_real_authority(self) -> "ConfirmedRealTrajectoryBundle":
        if (
            self.confirmation.run_id != self.brief.run_id
            or self.confirmation.brief_id != self.brief.brief_id
            or self.confirmation.trajectory_digest != self.brief.digest
            or self.confirmation.adapter_manifest_digest != self.brief.adapter_manifest_digest
        ):
            raise ValueError("baseline confirmation does not bind exact V5.2 brief authority")
        if self.provider_authority.source_identity_digest != self.brief.execution_envelope.target_identity_digest:
            raise ValueError("provider authority does not bind confirmed target identity")
        return self

    def validate_for_manifest(self, manifest: object) -> None:
        """Reject broad proposal/provider authority before a store or host effect exists."""

        from .adapters.manifest import AdapterManifest

        if not isinstance(manifest, AdapterManifest):
            raise ValueError("admission requires a strict AdapterManifest")
        if (
            self.brief.adapter_manifest_digest != manifest.digest
            or self.confirmation.adapter_manifest_digest != manifest.digest
        ):
            raise ValueError("canonical bundle does not bind admitted adapter manifest")
        if self.provider_authority.adapter_id != manifest.adapter_id:
            raise ValueError("provider authority does not bind admitted adapter identity")
        allowed_effects = {capability.effect for capability in manifest.capabilities}
        allowed_scopes = set(manifest.synthetic_scope.owned_resources)
        for baseline in self.baseline:
            proposal = baseline.proposal
            if proposal.execution_scope not in allowed_scopes:
                raise ValueError("baseline proposal scope is outside admitted synthetic scope")
            if set(proposal.target_systems) != {manifest.target.host}:
                raise ValueError("baseline proposal target is outside admitted exact target")
            if proposal.action_kind == "verify_only":
                continue
            if proposal.side_effect not in allowed_effects:
                raise ValueError("baseline proposal effect is outside admitted capability")
            budget = baseline.budget
            if budget is None:  # Defensive: BaselineNodeProposal validates this.
                raise ValueError("effectful baseline proposal requires a bounded budget")
            validate_node_budget_against_manifest(
                budget, manifest, authority="baseline proposal"
            )
            if budget.max_requests > manifest.budgets.max_requests:
                raise ValueError("baseline proposal request budget exceeds admitted budget")
            if budget.max_wall_seconds * 1000 > manifest.budgets.max_duration_ms:
                raise ValueError("baseline proposal wall-time budget exceeds admitted budget")

    @property
    def digest(self) -> str:
        return digest_for("confirmed-real-trajectory-bundle", self)


class LandmarkVerification(NodeProposal):
    """Zero-action node proving an already-satisfied confirmed landmark."""

    action_kind: Literal["verify_only"] = "verify_only"
    current_run_head_proof_ref: str

    _validate_proof = field_validator("current_run_head_proof_ref")(_non_empty)


class DerivedBehavioralNode(StrictModel):
    """Sealed action intent. Execution evidence is deliberately stored elsewhere."""

    node_id: str
    run_id: str
    trajectory_digest: str
    run_head_digest: str
    execution_envelope_digest: str
    source_anchor_id: str
    target_landmark_id: str
    entry_observation_refs: tuple[str, ...]
    action_kind: Literal["act", "probe", "verify_only"]
    action_or_probe: str
    expected_before: tuple[str, ...]
    expected_after: tuple[str, ...]
    derivation_reason: str
    authority_refs: tuple[str, ...]
    execution_scope: str
    side_effect: str | None
    target_systems: tuple[str, ...]
    sealed_intent_digest: str
    current_run_head_proof_ref: str | None = None

    _validate_text = field_validator(
        "node_id",
        "run_id",
        "trajectory_digest",
        "run_head_digest",
        "execution_envelope_digest",
        "source_anchor_id",
        "target_landmark_id",
        "action_or_probe",
        "derivation_reason",
        "execution_scope",
        "sealed_intent_digest",
    )(_non_empty)

    @field_validator(
        "entry_observation_refs",
        "expected_before",
        "expected_after",
        "authority_refs",
        "target_systems",
    )
    @classmethod
    def _required_terms(cls, values: tuple[str, ...], info: Any) -> tuple[str, ...]:
        return _non_empty_terms(values, field_name=info.field_name)

    @field_validator("current_run_head_proof_ref")
    @classmethod
    def _optional_proof_is_nonempty(cls, value: str | None) -> str | None:
        return _non_empty(value) if value is not None else value

    @field_validator("side_effect")
    @classmethod
    def _optional_side_effect_is_nonempty(cls, value: str | None) -> str | None:
        return _non_empty(value) if value is not None else value

    @model_validator(mode="after")
    def _sealed_digest_binds_exact_intent(self) -> "DerivedBehavioralNode":
        payload = self.model_dump(exclude={"sealed_intent_digest"}, mode="json")
        if self.sealed_intent_digest != digest_for("derived-behavioral-node-intent", payload):
            raise ValueError("sealed intent digest does not bind immutable node intent")
        if self.action_kind == "verify_only" and self.current_run_head_proof_ref is None:
            raise ValueError("verification node requires current-run-head proof")
        if self.action_kind != "verify_only" and self.current_run_head_proof_ref is not None:
            raise ValueError("only verification node may carry current-run-head proof")
        if self.action_kind == "verify_only" and self.side_effect is not None:
            raise ValueError("verification-only node cannot carry a side effect")
        if self.action_kind != "verify_only" and self.side_effect is None:
            raise ValueError("sealed action or probe requires exact side effect")
        return self

    @property
    def digest(self) -> str:
        return digest_for("derived-behavioral-node", self)

    @classmethod
    def seal(
        cls,
        proposal: NodeProposal,
        *,
        entry_observation_refs: tuple[str, ...],
        run_id: str,
        trajectory_digest: str,
        run_head_digest: str,
        execution_envelope_digest: str,
    ) -> "DerivedBehavioralNode":
        if not isinstance(proposal, NodeProposal):
            raise ValueError("Derived node requires a strict NodeProposal")
        payload: dict[str, Any] = {
            "node_id": proposal.node_id,
            "run_id": run_id,
            "trajectory_digest": trajectory_digest,
            "run_head_digest": run_head_digest,
            "execution_envelope_digest": execution_envelope_digest,
            "source_anchor_id": proposal.source_anchor_id,
            "target_landmark_id": proposal.target_landmark_id,
            "entry_observation_refs": entry_observation_refs,
            "action_kind": proposal.action_kind,
            "action_or_probe": proposal.action_or_probe,
            "expected_before": proposal.expected_before,
            "expected_after": proposal.expected_after,
            "derivation_reason": proposal.derivation_reason,
            "authority_refs": proposal.authority_refs,
            "execution_scope": proposal.execution_scope,
            "side_effect": proposal.side_effect,
            "target_systems": proposal.target_systems,
            "current_run_head_proof_ref": (
                proposal.current_run_head_proof_ref
                if isinstance(proposal, LandmarkVerification)
                else None
            ),
        }
        return cls(
            **payload,
            sealed_intent_digest=digest_for("derived-behavioral-node-intent", payload),
        )


class BaselineSpineAuthority(TrajectoryStrictModel):
    """Immutable V5.2 default route, persisted once at real-run admission."""

    schema_version: Literal["graph-v5.baseline-spine-authority.v1"]
    run_id: str
    run_head_digest: str
    adapter_manifest_digest: str
    environment_snapshot_digest: str
    nodes: tuple[DerivedBehavioralNode, ...]
    node_digests: tuple[str, ...]
    baseline_proposals: tuple[BaselineNodeProposal, ...] = ()
    proposal_digests: tuple[str, ...] = ()
    budget_digests: tuple[str | None, ...] = ()

    _validate_text = field_validator("run_id")(_non_empty)

    @field_validator(
        "run_head_digest", "adapter_manifest_digest", "environment_snapshot_digest", "node_digests"
    )
    @classmethod
    def _digests_are_exact(cls, value: str | tuple[str, ...]) -> str | tuple[str, ...]:
        values = (value,) if isinstance(value, str) else value
        if any(re.fullmatch(r"[0-9a-f]{64}", item) is None for item in values):
            raise ValueError("baseline spine digests must be lowercase SHA-256 hexadecimal")
        return value

    @field_validator("proposal_digests")
    @classmethod
    def _proposal_digests_are_exact(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(re.fullmatch(r"[0-9a-f]{64}", item) is None for item in values):
            raise ValueError("baseline proposal digests must be lowercase SHA-256 hexadecimal")
        return values

    @field_validator("budget_digests")
    @classmethod
    def _budget_digests_are_exact_or_absent(
        cls, values: tuple[str | None, ...]
    ) -> tuple[str | None, ...]:
        if any(
            item is not None and re.fullmatch(r"[0-9a-f]{64}", item) is None
            for item in values
        ):
            raise ValueError("baseline budget digests must be lowercase SHA-256 hexadecimal")
        return values

    @model_validator(mode="after")
    def _binds_exact_ordered_nodes(self) -> "BaselineSpineAuthority":
        if not self.nodes or len(self.nodes) != len(self.node_digests):
            raise ValueError("baseline spine requires ordered canonical nodes")
        if tuple(node.digest for node in self.nodes) != self.node_digests:
            raise ValueError("baseline spine node digests must match canonical nodes")
        if len(self.node_ids) != len(set(self.node_ids)):
            raise ValueError("baseline spine node ids must be unique")
        if any(
            node.run_id != self.run_id or node.run_head_digest != self.run_head_digest
            for node in self.nodes
        ):
            raise ValueError("baseline spine nodes must bind exact run head authority")
        if not self.baseline_proposals:
            if self.proposal_digests or self.budget_digests:
                raise ValueError("baseline proposal digests require canonical baseline proposals")
            return self
        if (
            len(self.baseline_proposals) != len(self.nodes)
            or len(self.proposal_digests) != len(self.nodes)
            or len(self.budget_digests) != len(self.nodes)
        ):
            raise ValueError("baseline proposal authority must align with each sealed node")
        if tuple(item.proposal.node_id for item in self.baseline_proposals) != self.node_ids:
            raise ValueError("baseline proposals must retain canonical node order")
        if self.proposal_digests != tuple(
            item.proposal_digest for item in self.baseline_proposals
        ) or self.budget_digests != tuple(
            item.budget_digest for item in self.baseline_proposals
        ):
            raise ValueError("baseline proposal and budget digests must bind canonical proposals")
        return self

    @property
    def node_ids(self) -> tuple[str, ...]:
        return tuple(node.node_id for node in self.nodes)

    def contains_exact(self, node: DerivedBehavioralNode) -> bool:
        return any(
            candidate.node_id == node.node_id and candidate.digest == node.digest
            for candidate in self.nodes
        )

    @classmethod
    def from_nodes(
        cls,
        state: V52RunState,
        run_head: RealSystemRunHead,
        manifest: object,
        snapshot: object,
        nodes: tuple[DerivedBehavioralNode, ...],
        baseline_proposals: tuple[BaselineNodeProposal, ...] = (),
    ) -> "BaselineSpineAuthority":
        from .adapters.manifest import AdapterManifest
        from .environment import EnvironmentSnapshot

        if not isinstance(state, V52RunState):
            raise ValueError("baseline spine requires strict V5.2 run state")
        if not isinstance(run_head, RealSystemRunHead):
            raise ValueError("baseline spine requires strict real-system Run Head")
        if not isinstance(manifest, AdapterManifest) or not isinstance(snapshot, EnvironmentSnapshot):
            raise ValueError("baseline spine requires strict admitted manifest and environment snapshot")
        if (
            run_head.run_id != state.run_id
            or run_head.manifest_digest != manifest.digest
            or run_head.environment_snapshot_digest != snapshot.digest
            or manifest.digest != state.adapter_manifest_digest
        ):
            raise ValueError("baseline spine admission authority does not bind exact V5.2 run")
        for node in nodes:
            if (
                node.run_id != state.run_id
                or node.trajectory_digest != state.trajectory.digest
                or node.run_head_digest != run_head.digest
                or node.execution_envelope_digest != state.trajectory.execution_envelope.digest
            ):
                raise ValueError("baseline spine node does not bind exact admitted authority")
        if baseline_proposals and tuple(
            item.proposal.node_id for item in baseline_proposals
        ) != tuple(node.node_id for node in nodes):
            raise ValueError("baseline proposals do not bind sealed node order")
        if baseline_proposals:
            for item, node in zip(baseline_proposals, nodes, strict=True):
                proposal = item.proposal
                if proposal.action_kind == "verify_only":
                    proposal = LandmarkVerification.model_validate(
                        {
                            **proposal.model_dump(mode="python"),
                            "current_run_head_proof_ref": (
                                f"admission:run-head:{run_head.digest}"
                            ),
                        }
                    )
                expected_node = DerivedBehavioralNode.seal(
                    proposal,
                    entry_observation_refs=item.entry_observation_refs,
                    run_id=state.run_id,
                    trajectory_digest=state.trajectory.digest,
                    run_head_digest=run_head.digest,
                    execution_envelope_digest=state.trajectory.execution_envelope.digest,
                )
                if node != expected_node:
                    raise ValueError(
                        "baseline sealed node payload does not match canonical proposal authority"
                    )
                if item.proposal.action_kind != "verify_only":
                    budget = item.budget
                    if budget is None:
                        raise ValueError(
                            "effectful baseline proposal requires a bounded budget"
                        )
                    validate_node_budget_against_manifest(
                        budget, manifest, authority="baseline proposal"
                    )
        return cls(
            schema_version="graph-v5.baseline-spine-authority.v1",
            run_id=state.run_id,
            run_head_digest=run_head.digest,
            adapter_manifest_digest=manifest.digest,
            environment_snapshot_digest=snapshot.digest,
            nodes=nodes,
            node_digests=tuple(node.digest for node in nodes),
            baseline_proposals=baseline_proposals,
            proposal_digests=tuple(item.proposal_digest for item in baseline_proposals),
            budget_digests=tuple(item.budget_digest for item in baseline_proposals),
        )

    @property
    def digest(self) -> str:
        return digest_for("baseline-spine-authority", self)


class ExplorationDelta(TrajectoryStrictModel):
    """One evidence-led, append-only node outside the recommended baseline."""

    schema_version: Literal["graph-v5.exploration-delta.v1"]
    node: DerivedBehavioralNode
    proposal: BaselineNodeProposal | None = None
    parent_node_id: str
    evidence_refs: tuple[str, ...]
    origin_kind: Literal["evidence_led"]
    run_id: str
    run_head_digest: str
    adapter_manifest_digest: str
    environment_snapshot_digest: str

    _validate_text = field_validator("parent_node_id", "run_id")(_non_empty)

    @field_validator("evidence_refs")
    @classmethod
    def _evidence_is_required_and_safe(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        values = _non_empty_terms(values, field_name="evidence_refs")
        if len(values) != len(set(values)):
            raise ValueError("exploration evidence references must be distinct")
        return tuple(_safe_runtime_text(value) for value in values)

    @field_validator(
        "run_head_digest", "adapter_manifest_digest", "environment_snapshot_digest"
    )
    @classmethod
    def _digests_are_exact(cls, value: str) -> str:
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("exploration authority digest must be lowercase SHA-256 hexadecimal")
        return value

    @model_validator(mode="after")
    def _binds_exact_node_authority(self) -> "ExplorationDelta":
        if self.node.run_id != self.run_id:
            raise ValueError("exploration node must bind exact run authority")
        if self.node.run_head_digest != self.run_head_digest:
            raise ValueError("exploration node must bind exact run head authority")
        if self.node.node_id == self.parent_node_id:
            raise ValueError("exploration node cannot parent itself")
        if self.node.side_effect is not None:
            if self.proposal is None or self.proposal.budget is None:
                raise ValueError("effectful exploration requires immutable proposal budget authority")
            expected = DerivedBehavioralNode.seal(
                self.proposal.proposal,
                entry_observation_refs=self.proposal.entry_observation_refs,
                run_id=self.run_id,
                trajectory_digest=self.node.trajectory_digest,
                run_head_digest=self.run_head_digest,
                execution_envelope_digest=self.node.execution_envelope_digest,
            )
            if expected != self.node:
                raise ValueError("exploration node must bind exact immutable proposal authority")
        return self

    @classmethod
    def from_node(
        cls,
        *,
        node: DerivedBehavioralNode,
        parent_node_id: str,
        evidence_refs: tuple[str, ...],
        authority: BaselineSpineAuthority | "ExplorationDelta",
        proposal: BaselineNodeProposal | None = None,
    ) -> "ExplorationDelta":
        if isinstance(authority, BaselineSpineAuthority):
            if parent_node_id not in authority.node_ids:
                raise ValueError("exploration parent must be an admitted baseline node")
            run_id = authority.run_id
            run_head_digest = authority.run_head_digest
            adapter_manifest_digest = authority.adapter_manifest_digest
            environment_snapshot_digest = authority.environment_snapshot_digest
        elif isinstance(authority, ExplorationDelta):
            if parent_node_id != authority.node.node_id:
                raise ValueError("exploration parent must match exact earlier delta")
            run_id = authority.run_id
            run_head_digest = authority.run_head_digest
            adapter_manifest_digest = authority.adapter_manifest_digest
            environment_snapshot_digest = authority.environment_snapshot_digest
        else:
            raise ValueError("exploration delta requires immutable prior authority")
        return cls(
            schema_version="graph-v5.exploration-delta.v1",
            node=node,
            proposal=proposal,
            parent_node_id=parent_node_id,
            evidence_refs=evidence_refs,
            origin_kind="evidence_led",
            run_id=run_id,
            run_head_digest=run_head_digest,
            adapter_manifest_digest=adapter_manifest_digest,
            environment_snapshot_digest=environment_snapshot_digest,
        )

    @property
    def digest(self) -> str:
        return digest_for("exploration-delta", self)


class NodeAuthority(StrictModel):
    """Store-owned membership result consumed by V5.2 runtime dispatch."""

    kind: Literal["baseline", "exploration"]
    node: DerivedBehavioralNode
    exploration_delta: ExplorationDelta | None = None

    @model_validator(mode="after")
    def _binds_kind_to_fact(self) -> "NodeAuthority":
        if (self.kind == "baseline") != (self.exploration_delta is None):
            raise ValueError("node authority kind must match persisted authority fact")
        if self.exploration_delta is not None and self.exploration_delta.node != self.node:
            raise ValueError("exploration node authority must bind exact delta node")
        return self

    @classmethod
    def baseline(cls, node: DerivedBehavioralNode) -> "NodeAuthority":
        return cls(kind="baseline", node=node)

    @classmethod
    def exploration(cls, delta: ExplorationDelta) -> "NodeAuthority":
        return cls(kind="exploration", node=delta.node, exploration_delta=delta)


class PersistedNodeExecutionAuthority(StrictModel):
    """Read-only store projection for one next executable V5.2 node."""

    kind: Literal["baseline", "exploration"]
    node: DerivedBehavioralNode
    baseline_proposal: BaselineNodeProposal | None = None
    exploration_delta: ExplorationDelta | None = None

    @model_validator(mode="after")
    def _projection_binds_exact_persisted_authority(self) -> "PersistedNodeExecutionAuthority":
        if self.kind == "baseline":
            if self.exploration_delta is not None:
                raise ValueError("baseline execution authority cannot carry exploration facts")
            if (
                self.baseline_proposal is not None
                and self.baseline_proposal.proposal.node_id != self.node.node_id
            ):
                raise ValueError("baseline execution authority must bind matching proposal")
        elif self.baseline_proposal is not None or self.exploration_delta is None:
            raise ValueError("exploration execution authority must bind exact exploration fact")
        elif self.exploration_delta.node != self.node:
            raise ValueError("exploration execution authority must bind exact exploration node")
        return self

    @classmethod
    def baseline(
        cls,
        node: DerivedBehavioralNode,
        proposal: BaselineNodeProposal | None,
    ) -> "PersistedNodeExecutionAuthority":
        return cls(kind="baseline", node=node, baseline_proposal=proposal)

    @classmethod
    def exploration(cls, delta: ExplorationDelta) -> "PersistedNodeExecutionAuthority":
        return cls(kind="exploration", node=delta.node, exploration_delta=delta)

    @property
    def node_id(self) -> str:
        return self.node.node_id


def _persisted_proposal_for_node(
    state: V52RunState, node_id: str
) -> BaselineNodeProposal | None:
    baseline = state.facts.baseline_spine
    if baseline is None:
        return None
    proposal = next(
        (
            item
            for item in baseline.baseline_proposals
            if item.proposal.node_id == node_id
        ),
        None,
    )
    if proposal is not None:
        return proposal
    delta = next(
        (
            item
            for item in state.facts.exploration_deltas
            if item.node.node_id == node_id
        ),
        None,
    )
    return None if delta is None else delta.proposal


def effective_node_budget(
    state: V52RunState,
    node_id: str,
    *,
    before_pending_digest: str | None = None,
) -> NodeBudgetProposal | None:
    """Project immutable admitted budget plus exact consumed widening chain."""

    proposal = _persisted_proposal_for_node(state, node_id)
    budget = None if proposal is None else proposal.budget
    for consumption in state.facts.real_system_decision_consumptions:
        if consumption.pending_decision_digest == before_pending_digest:
            break
        amendment = consumption.amendment
        if not isinstance(amendment, BudgetWideningAmendment):
            continue
        if amendment.node_id != node_id:
            continue
        if budget is None or amendment.prior_budget_digest != budget.digest:
            raise ValueError("budget widening does not continue exact persisted budget chain")
        budget = amendment.requested_budget
    return budget


def validate_pending_real_system_decision_amendment(
    state: V52RunState,
    manifest: object,
    pending: PendingRealSystemDecision,
) -> None:
    """Validate one exceptional amendment against exact currently admitted facts."""

    from .adapters.manifest import AdapterManifest

    baseline = state.facts.baseline_spine
    head = state.facts.run_head
    if (
        not isinstance(manifest, AdapterManifest)
        or baseline is None
        or head is None
        or pending.run_id != state.run_id
        or pending.run_head_digest != head.digest
        or pending.authority_digest != baseline.digest
    ):
        raise ValueError("pending real-system decision does not bind exact admitted authority")
    amendment = pending.amendment
    if isinstance(amendment, BudgetWideningAmendment):
        consumed = any(
            consumption.pending_decision_digest == pending.digest
            for consumption in state.facts.real_system_decision_consumptions
        )
        if not consumed and any(
            intent.node_id == amendment.node_id
            for intent in state.facts.external_operation_intents
        ):
            raise ValueError("budget widening cannot amend an already intended node")
        current_budget = effective_node_budget(
            state,
            amendment.node_id,
            before_pending_digest=pending.digest,
        )
        baseline_proposal = next(
            (
                item
                for item in baseline.baseline_proposals
                if item.proposal.node_id == amendment.node_id
            ),
            None,
        )
        exploration = next(
            (
                item
                for item in state.facts.exploration_deltas
                if item.node.node_id == amendment.node_id
            ),
            None,
        )
        node_authority_digest = (
            baseline_proposal.digest
            if baseline_proposal is not None
            else None if exploration is None else exploration.digest
        )
        requested = amendment.requested_budget
        if (
            current_budget is None
            or amendment.node_authority_digest != node_authority_digest
            or amendment.prior_budget_digest != current_budget.digest
        ):
            raise ValueError("budget widening does not bind exact persisted node budget")
        prior_values = (
            current_budget.max_user_actions,
            current_budget.max_provider_requests,
            current_budget.max_cost_micros,
            current_budget.max_requests,
            current_budget.max_bytes,
            current_budget.max_wall_seconds,
        )
        requested_values = (
            requested.max_user_actions,
            requested.max_provider_requests,
            requested.max_cost_micros,
            requested.max_requests,
            requested.max_bytes,
            requested.max_wall_seconds,
        )
        if any(new < old for old, new in zip(prior_values, requested_values, strict=True)):
            raise ValueError("budget widening cannot narrow persisted node budget")
        if requested_values == prior_values:
            raise ValueError("budget widening must increase persisted node budget")
        validate_node_budget_against_manifest(
            requested, manifest, authority="budget widening"
        )
        if (
            requested.max_requests > manifest.budgets.max_requests
            or requested.max_wall_seconds * 1000 > manifest.budgets.max_duration_ms
        ):
            raise ValueError("budget widening exceeds admitted manifest budget")
        return
    if isinstance(amendment, ProductionWriteConfirmationAmendment):
        plan = manifest.production_write_plan
        if (
            manifest.mode != "production_guarded"
            or manifest.write_policy != "synthetic"
            or plan is None
            or amendment.production_write_plan_digest != plan.write_plan_digest
        ):
            raise ValueError("production write plan is not exact admitted authority")
        return
    if isinstance(amendment, CleanupAmendment):
        note = next(
            (
                item
                for item in state.facts.runtime_notes
                if item.digest == amendment.runtime_note_digest
            ),
            None,
        )
        if note is None or note.classification != "ephemeral_test_data":
            raise ValueError("cleanup decision does not bind matching ephemeral runtime note")
        return
    if isinstance(amendment, FixOrPatchAmendment):
        note = next(
            (
                item
                for item in state.facts.runtime_notes
                if item.digest == amendment.runtime_note_digest
            ),
            None,
        )
        if note is None or note.classification != "fix_or_patch":
            raise ValueError("fix-or-patch decision does not bind matching runtime note")
        return
    raise ValueError("pending real-system decision has unsupported amendment")


def derive_persisted_external_operation_intent(
    state: V52RunState, authority: PersistedNodeExecutionAuthority
) -> ExternalOperationIntent:
    """Derive one effectful V5.2 intent from immutable persisted authority only."""

    proposal = authority.baseline_proposal
    if proposal is None and authority.exploration_delta is not None:
        proposal = authority.exploration_delta.proposal
    budget = effective_node_budget(state, authority.node.node_id)
    head = state.facts.run_head
    if (
        proposal is None
        or budget is None
        or authority.node.side_effect is None
        or head is None
    ):
        raise ValueError("effectful persisted node lacks admitted proposal budget")
    binding = {
        "run_id": state.run_id,
        "run_head_digest": head.digest,
        "node_digest": authority.node.digest,
        "proposal_digest": proposal.proposal_digest,
    }
    operation_digest = digest_for("v52-persisted-operation", binding)
    operation_id = f"operation:{operation_digest}"
    return ExternalOperationIntent(
        operation_id=operation_id,
        run_id=state.run_id,
        node_id=authority.node.node_id,
        manifest_digest=state.adapter_manifest_digest,
        run_head_digest=head.digest,
        idempotency_key=f"idempotency:{digest_for('v52-persisted-idempotency', binding)}",
        effect=authority.node.side_effect,
        reserved_budget=BudgetReservation(
            reservation_id=f"reservation:{operation_digest}",
            run_id=state.run_id,
            operation_id=operation_id,
            user_actions=budget.max_user_actions,
            provider_requests=budget.max_provider_requests,
            cost_micros=budget.max_cost_micros,
            requests=budget.max_requests,
            processes=0,
            persistence_writes=0,
            tokens=0,
            duration_ms=budget.max_wall_seconds * 1000,
            bytes=budget.max_bytes,
        ),
    )


class AcceptedNodeResult(StrictModel):
    """Accepted execution/proof appended after one sealed frontier node."""

    node_id: str
    target_landmark_id: str
    observation_refs: tuple[str, ...]
    run_head_digest: str
    landmark_satisfied: bool
    current_run_head_proof_ref: str | None = None
    result_digest: str

    _validate_text = field_validator(
        "node_id", "target_landmark_id", "run_head_digest", "result_digest"
    )(_non_empty)

    @field_validator("observation_refs")
    @classmethod
    def _observations_are_required(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return _non_empty_terms(values, field_name="observation_refs")

    @field_validator("current_run_head_proof_ref")
    @classmethod
    def _optional_result_proof_is_nonempty(cls, value: str | None) -> str | None:
        return _non_empty(value) if value is not None else value

    @model_validator(mode="after")
    def _digest_and_proof_are_exact(self) -> "AcceptedNodeResult":
        payload = self.model_dump(exclude={"result_digest"}, mode="json")
        if self.result_digest != digest_for("accepted-node-result", payload):
            raise ValueError("accepted result digest does not bind exact result")
        if self.landmark_satisfied:
            if (
                self.current_run_head_proof_ref is None
                or self.current_run_head_proof_ref not in self.observation_refs
            ):
                raise ValueError("landmark result requires current-run-head proof evidence")
        elif self.current_run_head_proof_ref is not None:
            raise ValueError("intermediate result cannot claim landmark proof")
        return self

    @classmethod
    def create(
        cls,
        *,
        node: DerivedBehavioralNode,
        observation_refs: tuple[str, ...],
        run_head_digest: str,
        landmark_satisfied: bool,
        current_run_head_proof_ref: str | None,
    ) -> "AcceptedNodeResult":
        if not isinstance(node, DerivedBehavioralNode):
            raise ValueError("accepted result requires sealed Behavioral Node")
        payload: dict[str, Any] = {
            "node_id": node.node_id,
            "target_landmark_id": node.target_landmark_id,
            "observation_refs": observation_refs,
            "run_head_digest": run_head_digest,
            "landmark_satisfied": landmark_satisfied,
            "current_run_head_proof_ref": current_run_head_proof_ref,
        }
        return cls(**payload, result_digest=digest_for("accepted-node-result", payload))


class DerivedSpine(StrictModel):
    """Run-bound, append-only projection of nodes sealed from runtime evidence."""

    schema_version: Literal["graph-v5.derived-spine.v1"]
    run_id: str
    trajectory_digest: str
    landmark_order: tuple[str, ...]
    frontier: SpineFrontier
    nodes: tuple[DerivedBehavioralNode, ...] = ()
    results: tuple[AcceptedNodeResult, ...] = ()

    _validate_text = field_validator("run_id", "trajectory_digest")(_non_empty)

    @field_validator("landmark_order")
    @classmethod
    def _landmarks_are_ordered_and_unique(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        values = _non_empty_terms(values, field_name="landmark_order")
        if len(values) != len(set(values)):
            raise ValueError("Derived Spine landmark order must not contain duplicates")
        return values

    @model_validator(mode="after")
    def _frontier_projects_confirmed_order(self) -> "DerivedSpine":
        node_ids = tuple(node.node_id for node in self.nodes)
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("Derived Spine nodes must have unique IDs")
        if len(self.results) > len(self.nodes):
            raise ValueError("Derived Spine cannot contain result without sealed node")
        if len(self.nodes) - len(self.results) not in {0, 1}:
            raise ValueError("Derived Spine exposes at most one unexecuted frontier node")

        landmark_index = 0
        expected_source = "START"
        for index, node in enumerate(self.nodes):
            if node.run_id != self.run_id or node.trajectory_digest != self.trajectory_digest:
                raise ValueError("sealed node does not bind Derived Spine run or trajectory")
            post_completion = landmark_index >= len(self.landmark_order)
            expected_landmark = (
                self.landmark_order[-1]
                if post_completion
                else self.landmark_order[landmark_index]
            )
            if node.target_landmark_id != expected_landmark:
                raise ValueError("Derived Spine node cannot reorder, skip, or substitute landmark")
            if node.source_anchor_id != expected_source:
                raise ValueError("Derived Spine node source does not follow accepted frontier")
            if index >= len(self.results):
                break
            result = self.results[index]
            if (
                result.node_id != node.node_id
                or result.target_landmark_id != node.target_landmark_id
                or result.run_head_digest != node.run_head_digest
            ):
                raise ValueError("accepted result does not bind exact sealed node and Run Head")
            if result.landmark_satisfied:
                expected_source = node.target_landmark_id
                if not post_completion:
                    landmark_index += 1
            else:
                expected_source = node.node_id

        unexecuted = len(self.nodes) == len(self.results) + 1
        expected_unexecuted_id = self.nodes[-1].node_id if unexecuted else None
        if self.frontier.unexecuted_node_id != expected_unexecuted_id:
            raise ValueError("Derived Spine frontier must expose exactly one unexecuted node")
        expected_last = self.landmark_order[landmark_index - 1] if landmark_index else None
        expected_target = (
            self.landmark_order[landmark_index]
            if landmark_index < len(self.landmark_order)
            else (
                self.landmark_order[-1]
                if unexecuted
                or (
                    self.frontier.target_landmark_id == self.landmark_order[-1]
                    and self.frontier.last_reached_landmark_id == self.landmark_order[-1]
                )
                else None
            )
        )
        if self.frontier.last_reached_landmark_id != expected_last:
            raise ValueError("Derived Spine frontier lacks accepted landmark result proof")
        if self.frontier.target_landmark_id != expected_target:
            if expected_target is None:
                raise ValueError("Derived Spine may complete only after final landmark result proof")
            raise ValueError("Derived Spine cannot skip or reorder confirmed landmarks")
        return self

    @property
    def digest(self) -> str:
        return digest_for("derived-spine", self)

    @property
    def landmark_mapping(self) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """Deterministic complete landmark-to-sealed-node projection."""

        return tuple(
            (
                landmark_id,
                tuple(
                    node.node_id
                    for node in self.nodes
                    if node.target_landmark_id == landmark_id
                ),
            )
            for landmark_id in self.landmark_order
        )

    @property
    def landmark_mapping_digest(self) -> str:
        return digest_for("derived-spine-landmark-mapping", self.landmark_mapping)

    @property
    def unexecuted_nodes(self) -> tuple[DerivedBehavioralNode, ...]:
        if self.frontier.unexecuted_node_id is None:
            return ()
        return tuple(
            node for node in self.nodes if node.node_id == self.frontier.unexecuted_node_id
        )

    def bind_trajectory(self, trajectory: TrajectoryBrief) -> "DerivedSpine":
        if not isinstance(trajectory, TrajectoryBrief):
            raise ValueError("Derived Spine requires strict Trajectory Brief")
        if self.run_id != trajectory.run_id or self.trajectory_digest != trajectory.digest:
            raise ValueError("Derived Spine does not bind confirmed trajectory")
        if self.landmark_order != tuple(item.landmark_id for item in trajectory.landmarks):
            raise ValueError("Derived Spine landmark order diverges from confirmed trajectory")
        return self

    def with_node(self, node: DerivedBehavioralNode) -> "DerivedSpine":
        if not isinstance(node, DerivedBehavioralNode):
            raise ValueError("Derived Spine accepts only sealed Behavioral Nodes")
        if self.frontier.unexecuted_node_id is not None:
            raise ValueError("Derived Spine frontier already has unexecuted node")
        if self.frontier.target_landmark_id is None:
            raise ValueError("Derived Spine is complete and cannot seal another node")
        if node.target_landmark_id != self.frontier.target_landmark_id:
            raise ValueError("Derived Spine node cannot reorder, skip, or substitute landmark")
        if node.run_id != self.run_id or node.trajectory_digest != self.trajectory_digest:
            raise ValueError("sealed node belongs to foreign run or trajectory")
        if node.node_id in {item.node_id for item in self.nodes}:
            raise ValueError("Derived Spine cannot append duplicate node")
        return DerivedSpine(
            schema_version=self.schema_version,
            run_id=self.run_id,
            trajectory_digest=self.trajectory_digest,
            landmark_order=self.landmark_order,
            frontier=SpineFrontier(
                last_reached_landmark_id=self.frontier.last_reached_landmark_id,
                target_landmark_id=self.frontier.target_landmark_id,
                unexecuted_node_id=node.node_id,
            ),
            nodes=self.nodes + (node,),
            results=self.results,
        )

    def for_repair_extension(self) -> "DerivedSpine":
        """Expose final-landmark frontier for one validated replay repair."""

        if self.frontier.target_landmark_id is not None:
            return self
        if not self.nodes or len(self.results) != len(self.nodes):
            raise ValueError("repair extension requires a complete Derived Spine")
        return DerivedSpine(
            schema_version=self.schema_version,
            run_id=self.run_id,
            trajectory_digest=self.trajectory_digest,
            landmark_order=self.landmark_order,
            frontier=SpineFrontier(
                last_reached_landmark_id=self.landmark_order[-1],
                target_landmark_id=self.landmark_order[-1],
            ),
            nodes=self.nodes,
            results=self.results,
        )

    def with_accepted_result(self, result: AcceptedNodeResult) -> "DerivedSpine":
        if not isinstance(result, AcceptedNodeResult):
            raise ValueError("Derived Spine requires strict accepted node result")
        if self.frontier.unexecuted_node_id is None or not self.nodes:
            raise ValueError("Derived Spine has no unexecuted frontier node")
        node = self.nodes[-1]
        if (
            result.node_id != node.node_id
            or result.target_landmark_id != node.target_landmark_id
            or result.run_head_digest != node.run_head_digest
        ):
            raise ValueError("accepted result does not bind exact frontier node and Run Head")
        if node.action_kind == "verify_only" and (
            not result.landmark_satisfied
            or result.current_run_head_proof_ref != node.current_run_head_proof_ref
        ):
            raise ValueError(
                "verification-only node requires matching accepted landmark proof"
            )
        current_target = self.frontier.target_landmark_id
        if current_target is None:
            raise ValueError("completed Derived Spine cannot accept another result")
        if result.landmark_satisfied:
            target_index = self.landmark_order.index(current_target)
            next_target = (
                self.landmark_order[target_index + 1]
                if target_index + 1 < len(self.landmark_order)
                else None
            )
            last_reached = current_target
        else:
            next_target = current_target
            last_reached = self.frontier.last_reached_landmark_id
        return DerivedSpine(
            schema_version=self.schema_version,
            run_id=self.run_id,
            trajectory_digest=self.trajectory_digest,
            landmark_order=self.landmark_order,
            frontier=SpineFrontier(
                last_reached_landmark_id=last_reached,
                target_landmark_id=next_target,
                unexecuted_node_id=None,
            ),
            nodes=self.nodes,
            results=self.results + (result,),
        )

    @property
    def current_source_anchor_id(self) -> str:
        if self.results:
            result = self.results[-1]
            return result.target_landmark_id if result.landmark_satisfied else result.node_id
        return self.frontier.last_reached_landmark_id or "START"


class FrozenDerivedSpine(TrajectoryStrictModel):
    """Immutable final-replay authority projected from one complete spine.

    Freeze records are deliberately separate from the mutable run projection.
    Their three authority digests, node order, and landmark mapping are all
    content addressed; a later append-only spine extension therefore creates a
    distinct record instead of rewriting an earlier freeze.
    """

    schema_version: Literal["graph-v5.frozen-derived-spine.v1"] = (
        "graph-v5.frozen-derived-spine.v1"
    )
    run_id: str
    trajectory_digest: str
    derived_spine_digest: str
    landmark_mapping_digest: str
    landmark_order: tuple[str, ...]
    frontier: SpineFrontier
    nodes: tuple[DerivedBehavioralNode, ...]
    landmark_mapping: tuple[tuple[str, tuple[str, ...]], ...]
    results: tuple[AcceptedNodeResult, ...]
    run_head: "RunHead"
    environment: "EnvironmentIdentity"
    fixture_digest: str
    fixture_id: str
    fixture_adapter_id: str
    graph_revision: int = Field(ge=1)

    _validate_identity = field_validator(
        "run_id", "fixture_id", "fixture_adapter_id"
    )(_non_empty)

    @field_validator("landmark_order")
    @classmethod
    def _landmark_order_is_unique(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        values = _non_empty_terms(values, field_name="landmark_order")
        if len(values) != len(set(values)):
            raise ValueError("Frozen Derived Spine landmark order contains duplicates")
        return values

    @field_validator(
        "trajectory_digest", "derived_spine_digest", "landmark_mapping_digest"
    )
    @classmethod
    def _digest_is_sha256(cls, value: str) -> str:
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("frozen spine authority digests must be lowercase SHA-256 hexadecimal")
        return value

    @field_validator("nodes")
    @classmethod
    def _nodes_are_ordered(cls, values: tuple[DerivedBehavioralNode, ...]) -> tuple[DerivedBehavioralNode, ...]:
        if not values:
            raise ValueError("Frozen Derived Spine requires complete sealed nodes")
        ids = tuple(node.node_id for node in values)
        if len(ids) != len(set(ids)):
            raise ValueError("Frozen Derived Spine node order contains duplicate IDs")
        return values

    @field_validator("landmark_mapping")
    @classmethod
    def _mapping_is_ordered(cls, values: tuple[tuple[str, tuple[str, ...]], ...]) -> tuple[tuple[str, tuple[str, ...]], ...]:
        if not values:
            raise ValueError("Frozen Derived Spine requires landmark mapping")
        ids = tuple(item[0] for item in values)
        if any(not isinstance(item, tuple) or len(item) != 2 for item in values):
            raise ValueError("Frozen Derived Spine landmark mapping is invalid")
        if len(ids) != len(set(ids)):
            raise ValueError("Frozen Derived Spine landmark mapping contains duplicates")
        for landmark_id, node_ids in values:
            _non_empty(landmark_id)
            if not isinstance(node_ids, tuple):
                raise ValueError("Frozen Derived Spine node mapping must be immutable")
            for node_id in node_ids:
                _non_empty(node_id)
        return values

    @model_validator(mode="after")
    def _freeze_is_complete_and_bound(self) -> "FrozenDerivedSpine":
        node_ids = tuple(node.node_id for node in self.nodes)
        mapped_ids = tuple(node_id for _, ids in self.landmark_mapping for node_id in ids)
        if mapped_ids != node_ids:
            raise ValueError("Frozen Derived Spine landmark mapping must preserve node order")
        if tuple(result.node_id for result in self.results) != node_ids:
            raise ValueError("Frozen Derived Spine results must cover nodes in order")
        if tuple(landmark_id for landmark_id, _ in self.landmark_mapping) != self.landmark_order:
            raise ValueError("Frozen Derived Spine mapping must cover exact landmark order")
        if self.run_id != self.nodes[0].run_id or any(
            node.run_id != self.run_id or node.trajectory_digest != self.trajectory_digest
            for node in self.nodes
        ):
            raise ValueError("Frozen Derived Spine nodes do not bind frozen run authority")
        if self.frontier.target_landmark_id is not None or self.frontier.unexecuted_node_id is not None:
            raise ValueError("Frozen Derived Spine frontier must be complete")
        if self.frontier.last_reached_landmark_id != self.landmark_order[-1]:
            raise ValueError("Frozen Derived Spine frontier must prove final landmark")
        expected_mapping_digest = digest_for(
            "derived-spine-landmark-mapping", self.landmark_mapping
        )
        if self.landmark_mapping_digest != expected_mapping_digest:
            raise ValueError("Frozen Derived Spine landmark mapping digest mismatch")
        if self.derived_spine_digest != self.as_replay_projection().digest:
            raise ValueError("Frozen Derived Spine projection digest mismatch")
        if (
            self.run_head.environment_digest != self.environment.digest
            or self.run_head.fixture_digest != self.fixture_digest
        ):
            raise ValueError("Frozen Derived Spine Run Head does not bind sealed environment and fixture")
        if any(node.run_head_digest != self.run_head.digest for node in self.nodes):
            raise ValueError("Frozen Derived Spine nodes do not bind frozen Run Head")
        return self

    @classmethod
    def from_spine(
        cls,
        spine: DerivedSpine,
        *,
        run_head: "RunHead",
        environment: "EnvironmentIdentity",
        fixture_digest: str,
        fixture_id: str,
        fixture_adapter_id: str,
        graph_revision: int,
    ) -> "FrozenDerivedSpine":
        if not isinstance(spine, DerivedSpine):
            raise ValueError("freeze requires strict Derived Spine")
        if spine.frontier.target_landmark_id is not None or spine.frontier.unexecuted_node_id is not None:
            raise ValueError("cannot freeze incomplete Derived Spine")
        return cls(
            run_id=spine.run_id,
            trajectory_digest=spine.trajectory_digest,
            derived_spine_digest=spine.digest,
            landmark_mapping_digest=spine.landmark_mapping_digest,
            landmark_order=spine.landmark_order,
            frontier=spine.frontier,
            nodes=spine.nodes,
            landmark_mapping=spine.landmark_mapping,
            results=spine.results,
            run_head=run_head,
            environment=environment,
            fixture_digest=fixture_digest,
            fixture_id=fixture_id,
            fixture_adapter_id=fixture_adapter_id,
            graph_revision=graph_revision,
        )

    def as_replay_projection(self) -> DerivedSpine:
        """Rebuild immutable replay projection without consulting mutable run state."""

        return DerivedSpine(
            schema_version="graph-v5.derived-spine.v1",
            run_id=self.run_id,
            trajectory_digest=self.trajectory_digest,
            landmark_order=self.landmark_order,
            frontier=self.frontier,
            nodes=self.nodes,
            results=self.results,
        )

    @property
    def digest(self) -> str:
        return digest_for("frozen-derived-spine", self)


def validate_sealed_node_context(
    *,
    trajectory: TrajectoryBrief,
    spine: DerivedSpine,
    node: DerivedBehavioralNode,
    current_run_head: "RunHead",
    accepted_observations: tuple[Observation, ...],
) -> None:
    """Revalidate one sealed node at every authority/persistence boundary."""

    if not isinstance(trajectory, TrajectoryBrief) or not isinstance(spine, DerivedSpine):
        raise ValueError("sealed node context requires strict trajectory and spine")
    if not isinstance(node, DerivedBehavioralNode) or not isinstance(current_run_head, RunHead):
        raise ValueError("sealed node context requires strict node and Run Head")
    spine.bind_trajectory(trajectory)
    if (
        node.run_id != trajectory.run_id
        or node.trajectory_digest != trajectory.digest
        or node.run_head_digest != current_run_head.digest
        or node.execution_envelope_digest != trajectory.execution_envelope.digest
    ):
        raise ValueError("sealed node context binding is foreign")
    if (
        spine.frontier.unexecuted_node_id is not None
        or spine.frontier.target_landmark_id is None
        or node.target_landmark_id != spine.frontier.target_landmark_id
        or node.source_anchor_id != spine.current_source_anchor_id
    ):
        raise ValueError("sealed node does not bind exact frontier")

    envelope = trajectory.execution_envelope
    if node.execution_scope not in envelope.allowed_scope:
        raise ValueError("Execution Envelope does not authorize node scope")
    if node.side_effect is not None and node.side_effect not in envelope.allowed_side_effects:
        raise ValueError("Execution Envelope does not authorize node side effect")
    forbidden = tuple(item.casefold() for item in envelope.forbidden_systems)
    if any(
        blocked in system.casefold()
        for blocked in forbidden
        for system in node.target_systems
    ):
        raise ValueError("Execution Envelope forbids node target system")
    allowed_scope = tuple(item.casefold() for item in envelope.allowed_scope)
    if any(
        not any(scope in system.casefold() for scope in allowed_scope)
        for system in node.target_systems
    ):
        raise ValueError("Execution Envelope scope does not bind target system")

    expected_anchor = spine.current_source_anchor_id
    expected_anchor_authority = (
        "trajectory:start_state"
        if expected_anchor == "START"
        else (
            f"trajectory:landmarks:{expected_anchor}"
            if expected_anchor in spine.landmark_order
            else f"derived-spine:nodes:{expected_anchor}"
        )
    )
    target_authority = f"trajectory:landmarks:{spine.frontier.target_landmark_id}"
    permitted_authority = {
        "trajectory:start_state",
        "trajectory:goal",
        "trajectory:terminal_outcome",
        "trajectory:execution_envelope",
        *(f"trajectory:landmarks:{item.landmark_id}" for item in trajectory.landmarks),
        *(
            f"trajectory:expected_behaviors:{item.behavior_id}"
            for item in trajectory.expected_behaviors
        ),
        *(f"derived-spine:nodes:{item.node_id}" for item in spine.nodes),
    }
    if (
        expected_anchor_authority not in node.authority_refs
        or target_authority not in node.authority_refs
        or not set(node.authority_refs).issubset(permitted_authority)
    ):
        raise ValueError("sealed node lacks exact operational authority")

    matches = tuple(
        observation
        for observation in accepted_observations
        if isinstance(observation, Observation)
        and observation.kind == "behavioral"
        and observation.node_id == expected_anchor
        and observation.run_head_digest == current_run_head.digest
        and set(node.entry_observation_refs).issubset(observation.evidence_refs)
        and observation.observed_state in node.expected_before
    )
    if not matches:
        raise ValueError("sealed node lacks accepted entry observation context")
    if node.action_kind == "verify_only":
        landmark = next(
            item
            for item in trajectory.landmarks
            if item.landmark_id == node.target_landmark_id
        )
        if not any(
            observation.observed_state in {landmark.description, *landmark.acceptance}
            and node.current_run_head_proof_ref in observation.evidence_refs
            for observation in matches
        ):
            raise ValueError("verification node lacks accepted target landmark proof")


def validate_accepted_result_context(
    *,
    trajectory: TrajectoryBrief,
    node: DerivedBehavioralNode,
    result: AcceptedNodeResult,
    current_run_head: "RunHead",
    accepted_observations: tuple[Observation, ...],
) -> None:
    """Require accepted node result evidence to prove exact observed outcome."""

    if (
        result.node_id != node.node_id
        or result.target_landmark_id != node.target_landmark_id
        or result.run_head_digest != node.run_head_digest
        or result.run_head_digest != current_run_head.digest
    ):
        raise ValueError("accepted result does not bind exact node and current Run Head")
    matching = tuple(
        observation
        for observation in accepted_observations
        if isinstance(observation, Observation)
        and observation.kind == "behavioral"
        and observation.run_head_digest == current_run_head.digest
        and set(result.observation_refs).issubset(observation.evidence_refs)
        and observation.observed_state in node.expected_after
    )
    if not matching:
        raise ValueError("accepted result lacks expected-after observation")
    landmark = next(
        item
        for item in trajectory.landmarks
        if item.landmark_id == node.target_landmark_id
    )
    target_proof = tuple(
        observation
        for observation in matching
        if observation.observed_state in {landmark.description, *landmark.acceptance}
    )
    if result.landmark_satisfied:
        if not any(
            result.current_run_head_proof_ref in observation.evidence_refs
            for observation in target_proof
        ):
            raise ValueError("accepted result does not prove target landmark")
    elif target_proof:
        raise ValueError("intermediate result contradicts accepted target landmark proof")
    elif node.action_kind == "verify_only":
        raise ValueError("verification-only result must prove target landmark")


class EvidenceGap(StrictModel):
    target_landmark_id: str
    observation_refs: tuple[str, ...]
    evidence_gap: str
    smallest_needed_input: str
    exhausted_safe_probes: tuple[str, ...]

    _validate_text = field_validator(
        "target_landmark_id", "evidence_gap", "smallest_needed_input"
    )(_non_empty)

    @field_validator("observation_refs", "exhausted_safe_probes")
    @classmethod
    def _terms_are_nonempty(cls, values: tuple[str, ...], info: Any) -> tuple[str, ...]:
        return _non_empty_terms(values, field_name=info.field_name)


class TrajectoryPause(StrictModel):
    """Durable fail-closed pause when current evidence cannot justify a node."""

    reason: Literal["insufficient_next_node_evidence"]
    trajectory_digest: str
    frontier_digest: str
    frontier_anchor_id: str
    target_landmark_id: str
    observation_refs: tuple[str, ...]
    evidence_gap: str
    smallest_needed_input: str
    exhausted_safe_probe_refs: tuple[str, ...]

    _validate_text = field_validator(
        "trajectory_digest", "frontier_digest", "frontier_anchor_id",
        "target_landmark_id", "evidence_gap", "smallest_needed_input"
    )(_non_empty)

    @field_validator("observation_refs", "exhausted_safe_probe_refs")
    @classmethod
    def _references_are_nonempty(cls, values: tuple[str, ...], info: Any) -> tuple[str, ...]:
        return _non_empty_terms(values, field_name=info.field_name)

    @property
    def digest(self) -> str:
        return digest_for("trajectory-pause", self)


class PendingTrajectoryDecision(StrictModel):
    """Immutable narrow-departure request; never restarts Graph Brainstorming."""

    decision_id: str
    run_id: str
    trajectory_digest: str
    frontier_digest: str
    evidence_refs: tuple[str, ...]
    proposed_departure: str
    impact: str
    alternatives: tuple[str, ...]
    question: str

    _validate_text = field_validator(
        "decision_id", "run_id", "trajectory_digest", "frontier_digest",
        "proposed_departure", "impact", "question",
    )(_non_empty)

    @field_validator("evidence_refs", "alternatives")
    @classmethod
    def _references_are_nonempty(cls, values: tuple[str, ...], info: Any) -> tuple[str, ...]:
        return _non_empty_terms(values, field_name=info.field_name)

    @property
    def digest(self) -> str:
        return digest_for("pending-trajectory-decision", self)


class TrajectorySuccessor(StrictModel):
    """Append-only link to a newly confirmed departure authority."""

    decision_digest: str
    predecessor_trajectory_digest: str
    successor_trajectory_digest: str
    successor_markdown_digest: str
    successor_confirmation_digest: str
    successor_spine_digest: str

    _validate_text = field_validator(
        "decision_digest", "predecessor_trajectory_digest",
        "successor_trajectory_digest", "successor_markdown_digest",
        "successor_confirmation_digest", "successor_spine_digest",
    )(_non_empty)

    @model_validator(mode="after")
    def _successor_differs_from_predecessor(self) -> "TrajectorySuccessor":
        if self.predecessor_trajectory_digest == self.successor_trajectory_digest:
            raise ValueError("successor trajectory must differ from predecessor")
        return self

    @property
    def digest(self) -> str:
        return digest_for("trajectory-successor", self)


class NodeDeriver(Protocol):
    def derive_next(
        self,
        trajectory: TrajectoryBrief,
        spine: DerivedSpine,
        entry_observation: Observation,
    ) -> NodeProposal | LandmarkVerification | EvidenceGap: ...


class DerivedSpineSeal(StrictModel):
    """Typed ledger reference for one immutable Derived Spine append."""

    fact_id: str
    fact_digest: str

    _validate_text = field_validator("fact_id", "fact_digest")(_non_empty)

    @classmethod
    def from_spine(cls, spine: DerivedSpine) -> "DerivedSpineSeal":
        if not spine.nodes:
            raise ValueError("cannot persist empty Derived Spine as a sealing event")
        return cls(fact_id=spine.nodes[-1].node_id, fact_digest=spine.digest)


class CausalLead(StrictModel):
    lead_id: str
    source_observation_id: str
    subject: str
    disposition: Literal["open", "supported_cause", "supported_symptom", "disproved", "escalated"]
    evidence_refs: tuple[str, ...]

    _validate_text = field_validator("lead_id", "source_observation_id", "subject")(_non_empty)


class CausalEdge(StrictModel):
    edge_id: str
    from_lead_id: str
    to_lead_id: str
    relation: Literal[
        "provenance",
        "recorded_dependency",
        "exact_invalidation",
        "supports_cause",
        "supports_symptom",
    ]
    basis: str | None = None
    evidence_refs: tuple[str, ...] = ()
    confidence: int | None = Field(default=None, ge=0, le=100)
    risk: Literal["low", "medium", "high"] | None = None
    requires_independent_attestation: bool = False

    _validate_text = field_validator("edge_id", "from_lead_id", "to_lead_id")(_non_empty)

    @model_validator(mode="after")
    def _typed_edge_has_required_evidence(self) -> "CausalEdge":
        semantic = self.relation in {"supports_cause", "supports_symptom"}
        if semantic and (
            not self.evidence_refs
            or self.confidence is None
            or self.risk is None
            or not self.requires_independent_attestation
        ):
            raise ValueError("semantic causal edges require evidence, confidence, risk, and attestation")
        if not semantic and not self.basis:
            raise ValueError("deterministic causal edges require exact basis")
        return self


class RepairAttempt(StrictModel):
    attempt_id: str
    cone_id: str
    cone_digest: str
    hypothesis: str
    changed_dependencies: tuple[str, ...]
    changed_files: tuple[str, ...] = ()
    status: Literal["prepared", "red", "green", "rejected", "integrated"]
    change_kind: Literal[
        "conformance", "behavior", "architecture", "external_contract"
    ]

    _validate_text = field_validator(
        "attempt_id", "cone_id", "cone_digest", "hypothesis"
    )(_non_empty)

    @field_validator("changed_dependencies", "changed_files")
    @classmethod
    def _changed_facts_are_named(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(_non_empty(value) for value in values)


class ProofSpec(StrictModel):
    proof_spec_id: str
    node_id: str
    discriminator: str
    expected_result: str
    command: tuple[str, ...]
    trajectory_digest: str = "legacy-unbound"
    derived_spine_digest: str = "legacy-unbound"
    landmark_mapping_digest: str = "legacy-unbound"

    _validate_text = field_validator(
        "proof_spec_id", "node_id", "discriminator", "expected_result",
        "trajectory_digest", "derived_spine_digest", "landmark_mapping_digest",
    )(_non_empty)

    @property
    def digest(self) -> str:
        return digest_for("proof-spec", self)


class ProofResult(StrictModel):
    proof_result_id: str
    proof_spec_id: str
    proof_spec_digest: str
    node_id: str
    proof_class: Literal[
        "exploratory_observation",
        "deterministic_execution_proof",
        "semantic_attestation",
        "operational_observation",
    ]
    result: Literal["red", "green", "inconclusive"]
    artifact_digest: str
    run_head_digest: str

    _validate_text = field_validator(
        "proof_result_id", "proof_spec_id", "proof_spec_digest", "node_id", "artifact_digest", "run_head_digest"
    )(_non_empty)

    @property
    def digest(self) -> str:
        return digest_for("proof-result", self)


class StallFingerprint(StrictModel):
    """Exact durable identity for a failed-repair stall."""

    node_id: str
    run_head_digest: str
    environment_digest: str
    fixture_snapshot_digest: str
    cone_digest: str
    repair_hypothesis: str
    proof_spec_digest: str
    deterministic_proof_result_digest: str

    _validate_text = field_validator(
        "node_id",
        "run_head_digest",
        "environment_digest",
        "fixture_snapshot_digest",
        "cone_digest",
        "repair_hypothesis",
        "proof_spec_digest",
        "deterministic_proof_result_digest",
    )(_non_empty)

    @property
    def digest(self) -> str:
        return digest_for("stall-fingerprint", self)


class IterationFact(StrictModel):
    """One observable unit of active runtime progress."""

    fact_id: str
    fact_class: Literal[
        "verified_node",
        "new_hop",
        "repair_proof",
        "escalation",
        "pause",
        "terminal",
    ]
    node_id: str
    run_head_digest: str
    subject_id: str
    cone_id: str
    cone_digest: str
    widening_used: bool = False
    reasoning_tier: int = Field(default=0, ge=0)
    stall_fingerprint: StallFingerprint | None = None

    _validate_text = field_validator(
        "fact_id", "node_id", "run_head_digest", "subject_id", "cone_id", "cone_digest"
    )(_non_empty)

    @model_validator(mode="after")
    def _is_one_real_progress_class(self) -> "IterationFact":
        if self.widening_used and self.fact_class != "new_hop":
            raise ValueError("diagnostic widening must record a new_hop fact")
        if self.reasoning_tier and not self.widening_used:
            raise ValueError("reasoning tier may increase only with diagnostic widening")
        if self.stall_fingerprint is not None and self.stall_fingerprint.node_id != self.node_id:
            raise ValueError("stall fingerprint must bind iteration Behavioral Node")
        return self

    @property
    def digest(self) -> str:
        return digest_for("runtime-iteration-fact", self)


class ConeIdentityBinding(StrictModel):
    """Authoritative stable cone identity for one Behavioral Node in one run."""

    run_id: str
    node_id: str
    cone_id: str

    _validate_text = field_validator("run_id", "node_id", "cone_id")(_non_empty)

    @property
    def digest(self) -> str:
        return digest_for("cone-identity-binding", self)


class ReplayReopen(StrictModel):
    """Durable invalidation of stale node verification after replay regression."""

    replay_id: str
    node_id: str
    cone_id: str
    cone_digest: str
    run_head_digest: str
    stale_verified_fact_ids: tuple[str, ...]

    _validate_text = field_validator(
        "replay_id", "node_id", "cone_id", "cone_digest", "run_head_digest"
    )(_non_empty)

    @field_validator("stale_verified_fact_ids")
    @classmethod
    def _stale_facts_are_unique(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(values) != len(set(values)):
            raise ValueError("replay reopen stale verified facts must be unique")
        return tuple(_non_empty(value) for value in values)

    @property
    def digest(self) -> str:
        return digest_for("final-replay-reopen", self)


class ReplayConeClosure(StrictModel):
    """Fresh proof-ladder closure which resolves one replay-reopened cone."""

    replay_id: str
    closed_cone_digest: str
    run_head_digest: str
    proof_spec_digest: str
    proof_result_ids: tuple[str, ...]

    _validate_text = field_validator(
        "replay_id", "closed_cone_digest", "run_head_digest", "proof_spec_digest"
    )(_non_empty)

    @field_validator("proof_result_ids")
    @classmethod
    def _fresh_proofs_are_unique(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if not values or len(values) != len(set(values)):
            raise ValueError("replay cone closure requires unique fresh proof results")
        return tuple(_non_empty(value) for value in values)

    @property
    def digest(self) -> str:
        return digest_for("final-replay-cone-closure", self)


class ProductWorkCounters(StrictModel):
    """Exact counters authorized for one product-work operation."""

    duration_kind: Literal["command", "agent_call"] = "command"
    completed_duration_ms: int = Field(default=0, ge=0)
    command_count: int = Field(default=0, ge=0)
    repair_attempts: int = Field(default=0, ge=0)
    agent_dispatches: int = Field(default=0, ge=0)
    model_calls: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)
    normalized_provider_cost: int = Field(default=0, ge=0)
    output_bytes: int = Field(default=0, ge=0)
    command_output_bytes: tuple[int, ...] = ()
    causal_radius: int = Field(default=0, ge=0)
    widening_allowance: int = Field(default=0, ge=0)

    @field_validator("command_output_bytes")
    @classmethod
    def _per_command_outputs_are_nonnegative(
        cls, values: tuple[int, ...]
    ) -> tuple[int, ...]:
        if any(type(value) is not int or value < 0 for value in values):
            raise ValueError("per-command output bytes must be nonnegative integers")
        return values

    @model_validator(mode="after")
    def _records_completed_product_work(self) -> "ProductWorkCounters":
        values = (
            self.completed_duration_ms,
            self.command_count,
            self.repair_attempts,
            self.agent_dispatches,
            self.model_calls,
            self.reasoning_tokens,
            self.normalized_provider_cost,
            self.output_bytes,
        )
        if not any(values):
            raise ValueError("product work counters require completed product work")
        if len(self.command_output_bytes) != self.command_count:
            raise ValueError("product work requires exact per-command output byte deltas")
        if sum(self.command_output_bytes) != self.output_bytes:
            raise ValueError("per-command output bytes must equal output_bytes")
        return self

    @property
    def digest(self) -> str:
        return digest_for("product-work-counters", self)


class WorkAuthorization(StrictModel):
    """Issuer-bound operation authority; callers never select its work kind."""

    authorization_id: str
    operation_id: str
    operation_digest: str
    kind: Literal["discovery", "repair", "proof", "process", "agent"]
    run_id: str
    node_id: str
    cone_id: str
    cone_digest: str
    trajectory_digest: str
    derived_spine_digest: str
    landmark_mapping_digest: str
    expected_counters: ProductWorkCounters

    _validate_text = field_validator(
        "authorization_id", "operation_id", "operation_digest", "run_id",
        "node_id", "cone_id", "cone_digest", "trajectory_digest",
        "derived_spine_digest", "landmark_mapping_digest",
    )(_non_empty)

    @model_validator(mode="after")
    def _kind_matches_expected_counters(self) -> "WorkAuthorization":
        counters = self.expected_counters
        if self.kind == "repair":
            if counters.repair_attempts == 0:
                raise ValueError("repair work authorization requires repair_attempts")
        elif counters.repair_attempts != 0:
            raise ValueError("process/proof/discovery work authorization cannot carry repair work")
        if self.kind in {"proof", "process", "agent"} and (
            counters.causal_radius != 0 or counters.widening_allowance != 0
        ):
            raise ValueError("only discovery or repair work authorization may charge cone expansion")
        if self.kind == "agent":
            if counters.command_count != 0 or counters.output_bytes != 0:
                raise ValueError("agent work authorization may not charge commands or command output")
            if counters.duration_kind != "agent_call":
                raise ValueError("agent work authorization requires agent_call duration")
        elif counters.duration_kind != "command":
            raise ValueError("non-agent work authorization requires command duration")
        return self

    @property
    def digest(self) -> str:
        return digest_for("work-authorization", self)


class ProductWorkReceipt(ProductWorkCounters):
    """Completed work artifact; runtime imports only an issuer-registered identity."""

    work_id: str
    kind: Literal["discovery", "repair", "proof", "process", "agent"]
    node_id: str
    cone_id: str
    cone_digest: str
    authorization_id: str | None = None
    authorization_digest: str | None = None
    operation_id: str | None = None

    _validate_text = field_validator(
        "work_id", "node_id", "cone_id", "cone_digest"
    )(_non_empty)

    @model_validator(mode="after")
    def _has_complete_issuer_binding_or_none(self) -> "ProductWorkReceipt":
        values = (
            self.authorization_id,
            self.authorization_digest,
            self.operation_id,
        )
        if any(value is None for value in values) and any(value is not None for value in values):
            raise ValueError("product work receipt issuer binding must be complete")
        if self.kind != "repair" and self.repair_attempts != 0:
            raise ValueError("non-repair receipts require repair_attempts=0")
        if self.kind in {"proof", "process", "agent"} and (
            self.causal_radius != 0 or self.widening_allowance != 0
        ):
            raise ValueError("only discovery or repair receipts may charge cone expansion")
        if self.kind == "agent":
            if self.command_count != 0 or self.output_bytes != 0:
                raise ValueError("agent receipts may not charge commands or command output")
            if self.duration_kind != "agent_call":
                raise ValueError("agent receipts require agent_call duration")
        elif self.duration_kind != "command":
            raise ValueError("non-agent receipts require command duration")
        return self

    @property
    def counters(self) -> ProductWorkCounters:
        return ProductWorkCounters.model_validate(
            self.model_dump(
                include=set(ProductWorkCounters.model_fields), mode="python"
            )
        )

    @property
    def digest(self) -> str:
        return digest_for("product-work-receipt", self)


class ChangeClassificationArtifact(StrictModel):
    """Independent classification bound to one exact repair proposal."""

    artifact_id: str
    reviewer_id: str
    reviewer_role: Literal["independent_change_reviewer"]
    change_kind: Literal[
        "conformance", "behavior", "architecture", "external_contract"
    ]
    run_id: str
    node_id: str
    cone_id: str
    cone_digest: str
    goal_digest: str
    envelope_digest: str
    repair_hypothesis: str
    changed_dependencies: tuple[str, ...]
    changed_files: tuple[str, ...]
    reviewer_manifest_id: str | None = None
    reviewer_manifest_digest: str | None = None
    user_authorization_digest: str | None = None
    trajectory_digest: str = "legacy-unbound"
    derived_spine_digest: str = "legacy-unbound"
    landmark_mapping_digest: str = "legacy-unbound"

    _validate_text = field_validator(
        "artifact_id",
        "reviewer_id",
        "run_id",
        "node_id",
        "cone_id",
        "cone_digest",
        "goal_digest",
        "envelope_digest",
        "repair_hypothesis",
        "trajectory_digest",
        "derived_spine_digest",
        "landmark_mapping_digest",
    )(_non_empty)

    @field_validator("changed_dependencies", "changed_files")
    @classmethod
    def _bound_changed_facts_are_named(
        cls, values: tuple[str, ...]
    ) -> tuple[str, ...]:
        return tuple(_non_empty(value) for value in values)

    @model_validator(mode="after")
    def _user_authority_matches_change_boundary(self) -> "ChangeClassificationArtifact":
        prohibited_prefixes = ("controller", "patch_executor", "self")
        if any(
            self.reviewer_id == identity
            or self.reviewer_id.startswith(f"{identity}:")
            for identity in prohibited_prefixes
        ):
            raise ValueError("controller, patch executor, or self may not self-classify a change")
        bindings = (self.reviewer_manifest_id, self.reviewer_manifest_digest)
        if any(value is None for value in bindings) and any(value is not None for value in bindings):
            raise ValueError("classification reviewer manifest binding must be complete")
        if self.user_authorization_digest is not None:
            raise ValueError("user authorization belongs to the exact user decision, not classification")
        return self

    @property
    def digest(self) -> str:
        return digest_for("change-classification-artifact", self)

    @property
    def change_digest(self) -> str:
        return digest_for(
            "classified-repair-change",
            {
                "run_id": self.run_id,
                "node_id": self.node_id,
                "cone_id": self.cone_id,
                "cone_digest": self.cone_digest,
                "repair_hypothesis": self.repair_hypothesis,
                "changed_dependencies": self.changed_dependencies,
                "changed_files": self.changed_files,
                "change_kind": self.change_kind,
            },
        )


class RoleManifest(StrictModel):
    manifest_id: str
    role: Literal[
        "patch_executor",
        "discovery_reviewer",
        "proof_curator",
        "validator",
        "semantic_reviewer",
        "independent_change_reviewer",
    ]
    identity: str
    attempt: int = Field(ge=1)
    goal_digest: str
    cone_digest: str
    base_revision: str
    run_head_digest: str
    environment_digest: str
    fixture_digest: str
    proof_spec_digest: str
    permitted_output_schema: str
    trajectory_digest: str = "legacy-unbound"
    derived_spine_digest: str = "legacy-unbound"
    landmark_mapping_digest: str = "legacy-unbound"

    _validate_text = field_validator(
        "manifest_id", "identity", "goal_digest", "cone_digest", "base_revision", "run_head_digest",
        "environment_digest", "fixture_digest", "proof_spec_digest", "permitted_output_schema",
        "trajectory_digest", "derived_spine_digest", "landmark_mapping_digest",
    )(_non_empty)

    @property
    def digest(self) -> str:
        return digest_for("role-manifest", self)


class RunHead(StrictModel):
    revision: str
    environment_digest: str
    fixture_digest: str

    _validate_text = field_validator("revision", "environment_digest", "fixture_digest")(_non_empty)

    @property
    def digest(self) -> str:
        return digest_for("run-head", self)


class LimitConsumption(StrictModel):
    limit_name: str
    consumed: int = Field(ge=0)

    _validate_name = field_validator("limit_name")(_non_empty)


class PauseReport(StrictModel):
    node_id: str
    reason: Literal["diagnostic_stall", "review_infrastructure", "limit_exhausted", "escalation"]
    cone_id: str
    cone_digest: str
    consumed_limits: tuple[str, ...]
    consumed_limit_values: tuple[LimitConsumption, ...]
    expected_behavior: tuple[str, ...]
    failure_evidence_refs: tuple[str, ...]
    causal_graph_refs: tuple[str, ...]
    attempted_repair_refs: tuple[str, ...]
    causal_radius: int = Field(ge=0)
    widening_used: int = Field(ge=0)
    reasoning_tier: int = Field(ge=0)
    no_safe_action_rationale: str
    requested_decisions: tuple[str, ...]
    smallest_decisions: tuple[str, ...]

    _validate_text = field_validator(
        "node_id", "cone_id", "cone_digest", "no_safe_action_rationale"
    )(_non_empty)

    @model_validator(mode="after")
    def _is_complete_diagnostic_context(self) -> "PauseReport":
        required_values = (
            self.expected_behavior,
            self.failure_evidence_refs,
            self.causal_graph_refs,
            self.attempted_repair_refs,
            self.consumed_limits,
            self.consumed_limit_values,
            self.requested_decisions,
            self.smallest_decisions,
        )
        if not all(required_values):
            raise ValueError("diagnostic stall report requires complete context")
        if len(self.consumed_limits) != len(set(self.consumed_limits)):
            raise ValueError("diagnostic consumed limits must be distinct")
        if {
            item.limit_name for item in self.consumed_limit_values
        } != set(self.consumed_limits):
            raise ValueError("diagnostic numeric limits must bind consumed limits")
        if len(self.requested_decisions) != len(set(self.requested_decisions)):
            raise ValueError("diagnostic requested decisions must be distinct")
        if self.smallest_decisions != self.requested_decisions:
            raise ValueError("diagnostic report must request only smallest decisions")
        return self

    @property
    def digest(self) -> str:
        return digest_for("pause-report", self)


class PendingDecision(StrictModel):
    decision_id: str
    cone_id: str
    cone_digest: str
    kind: Literal[
        "limit_amendment",
        "scope_authorization",
        "behavior_authorization",
        "architecture_authorization",
        "external_contract_authorization",
        "access",
        "terminalization",
        "cancellation",
    ]
    question: str
    evidence_refs: tuple[str, ...]
    allowed_kinds: tuple[
        Literal[
            "limit_amendment",
            "scope_authorization",
            "behavior_authorization",
            "architecture_authorization",
            "external_contract_authorization",
            "access",
            "terminalization",
            "cancellation",
        ],
        ...,
    ] = ()

    _validate_text = field_validator(
        "decision_id", "cone_id", "cone_digest", "question"
    )(_non_empty)

    @model_validator(mode="after")
    def _allowed_kinds_are_distinct(self) -> "PendingDecision":
        if self.kind in self.allowed_kinds or len(self.allowed_kinds) != len(set(self.allowed_kinds)):
            raise ValueError("pending decision allowed kinds must be distinct alternatives")
        return self

    @property
    def digest(self) -> str:
        return digest_for("pending-user-decision", self)


class UserDecision(StrictModel):
    """Only a digest-bound human decision may alter a paused V5 run."""

    decision_id: str
    kind: Literal[
        "limit_amendment",
        "scope_authorization",
        "behavior_authorization",
        "architecture_authorization",
        "external_contract_authorization",
        "access",
        "terminalization",
        "cancellation",
    ]
    actor: str
    pending_decision_digest: str
    classification_digest: str | None = None
    change_digest: str | None = None
    limit_name: str | None = None
    limit_amount: int | None = Field(default=None, gt=0)
    reason: str

    _validate_text = field_validator(
        "decision_id", "actor", "pending_decision_digest", "reason"
    )(_non_empty)

    @model_validator(mode="after")
    def _is_exact_human_authority(self) -> "UserDecision":
        if not self.actor.startswith("user:") or len(self.actor) <= len("user:"):
            raise ValueError("decision actor must be an explicit user identity")
        if self.kind == "limit_amendment":
            if not self.limit_name or self.limit_amount is None:
                raise ValueError("limit amendment requires name and amount")
        elif self.limit_name is not None or self.limit_amount is not None:
            raise ValueError("only limit amendment may carry a limit value")
        bindings = (self.classification_digest, self.change_digest)
        if any(value is None for value in bindings) and any(value is not None for value in bindings):
            raise ValueError("user authorization must bind both classification and change digest")
        return self

    @property
    def digest(self) -> str:
        return digest_for("user-decision", self)


class DurationDelta(StrictModel):
    kind: Literal["command", "agent_call"]
    completed_duration_ms: int = Field(gt=0)


class UserAuthorizationConsumption(StrictModel):
    """One durable use of one exact non-conformance authorization."""

    decision_digest: str
    classification_digest: str
    change_digest: str

    _validate_text = field_validator(
        "decision_digest", "classification_digest", "change_digest"
    )(_non_empty)

    @property
    def digest(self) -> str:
        return digest_for("user-authorization-consumption", self)


class FactIndex(StrictModel):
    trajectory_binding: ConfirmedTrajectoryBinding | None = None
    derived_spine: DerivedSpine | None = None
    frozen_derived_spines: tuple[FrozenDerivedSpine, ...] = ()
    bootstrap_intent: BootstrapIntent | None = None
    git_transaction: GitTransaction | None = None
    environment: EnvironmentIdentity | None = None
    run_head: RunHead | None = None
    observations: tuple[Observation, ...] = ()
    leads: tuple[CausalLead, ...] = ()
    edges: tuple[CausalEdge, ...] = ()
    repairs: tuple[RepairAttempt, ...] = ()
    proof_specs: tuple[ProofSpec, ...] = ()
    proof_results: tuple[ProofResult, ...] = ()
    role_manifests: tuple[RoleManifest, ...] = ()
    duration_deltas: tuple[DurationDelta, ...] = ()
    iteration_facts: tuple[IterationFact, ...] = ()
    cone_identity_bindings: tuple[ConeIdentityBinding, ...] = ()
    replay_reopens: tuple[ReplayReopen, ...] = ()
    replay_cone_closures: tuple[ReplayConeClosure, ...] = ()
    work_authorizations: tuple[WorkAuthorization, ...] = ()
    product_work: tuple[ProductWorkReceipt, ...] = ()
    change_classification_artifacts: tuple[ChangeClassificationArtifact, ...] = ()
    user_decisions: tuple[UserDecision, ...] = ()
    user_authorization_consumptions: tuple[UserAuthorizationConsumption, ...] = ()
    pending_decision_history: tuple[PendingDecision, ...] = ()
    pause_reports: tuple[PauseReport, ...] = ()
    pause_report: PauseReport | None = None
    trajectory_pauses: tuple[TrajectoryPause, ...] = ()
    pending_trajectory_decisions: tuple[PendingTrajectoryDecision, ...] = ()
    trajectory_successors: tuple[TrajectorySuccessor, ...] = ()

    @property
    def completed_duration_ms(self) -> int:
        return sum(delta.completed_duration_ms for delta in self.duration_deltas)

    def record_duration(self, *, kind: Literal["command", "agent_call"], completed_duration_ms: int) -> "FactIndex":
        values = self.model_dump()
        values["duration_deltas"] = self.duration_deltas + (
            DurationDelta(kind=kind, completed_duration_ms=completed_duration_ms),
        )
        return FactIndex.model_validate(values)

    def record_product_work(
        self, authorization: WorkAuthorization, receipt: ProductWorkReceipt
    ) -> "FactIndex":
        values = self.model_dump()
        values["work_authorizations"] = self.work_authorizations + (authorization,)
        values["product_work"] = self.product_work + (receipt,)
        if receipt.completed_duration_ms:
            values["duration_deltas"] = self.duration_deltas + (
                DurationDelta(
                    kind=receipt.duration_kind,
                    completed_duration_ms=receipt.completed_duration_ms,
                ),
            )
        return FactIndex.model_validate(values)


class RunState(StrictModel):
    schema_version: Literal["v5"]
    run_id: str
    mode: Literal[
        "boot",
        "running",
        "final_replay",
        "paused",
        "succeeded",
        "inconclusive",
        "blocked",
        "failed",
        "cancelled",
    ]
    trajectory: TrajectoryBrief
    facts: FactIndex
    limits: VersionedLimits
    pending_decision: PendingDecision | None = None

    _validate_run_id = field_validator("run_id")(_non_empty)

    @model_validator(mode="after")
    def _trajectory_matches_run_identity(self) -> "RunState":
        if self.trajectory.run_id != self.run_id:
            raise ValueError("RunState run_id must equal immutable Trajectory Brief run_id")
        binding = self.facts.trajectory_binding
        if binding is not None and (
            binding.run_id != self.run_id
            or binding.trajectory_digest != self.trajectory.digest
        ):
            raise ValueError("trajectory binding must match immutable RunState trajectory")
        if self.facts.derived_spine is not None:
            self.facts.derived_spine.bind_trajectory(self.trajectory)
        return self

    @property
    def trajectory_digest(self) -> str:
        return self.trajectory.digest

    @property
    def fixture_intent_digest(self) -> str:
        """Stable start binding until JIT fixture observations are available."""

        return digest_for("trajectory-fixture-intent", self.trajectory.fixture_intent)

    @property
    def trajectory_pause(self) -> TrajectoryPause | None:
        if self.mode != "paused":
            return None
        return self.facts.trajectory_pauses[-1] if self.facts.trajectory_pauses else None

    @property
    def pending_trajectory_decision(self) -> PendingTrajectoryDecision | None:
        if self.mode != "paused" or not self.facts.pending_trajectory_decisions:
            return None
        pending = self.facts.pending_trajectory_decisions[-1]
        if any(
            link.decision_digest == pending.digest
            for link in self.facts.trajectory_successors
        ):
            return None
        return pending

    @classmethod
    def empty_facts(cls) -> FactIndex:
        return FactIndex()

    def with_mode(self, mode: str) -> "RunState":
        values = self.model_dump()
        values["mode"] = mode
        return RunState.model_validate(values)

    @property
    def digest(self) -> str:
        return digest_for("run-state", self)


class ReplacementRunBrief(StrictModel):
    """Read-only, untrusted predecessor material. Never a V5 RunState."""

    predecessor_schema: Literal["v4"]
    provenance: str
    original_digest: str
    original_bytes: str
    trust: Literal["untrusted_predecessor_observation"]

    _validate_text = field_validator("provenance", "original_digest", "original_bytes")(_non_empty)


def import_v4_replacement_brief(
    predecessor: Mapping[str, Any], *, provenance: str
) -> ReplacementRunBrief:
    """Preserve predecessor bytes as untrusted context without translating state."""

    schema_version = predecessor.get("schema_version")
    if schema_version != "v4":
        raise ValueError("only an explicit V4 predecessor may create a replacement brief")
    original_bytes = canonical_json_text(predecessor)
    return ReplacementRunBrief(
        predecessor_schema="v4",
        provenance=provenance,
        original_digest=digest_bytes("untrusted-v4-predecessor", original_bytes.encode("utf-8")),
        original_bytes=original_bytes,
        trust="untrusted_predecessor_observation",
    )


class RunLimitsProfile(StrictModel):
    schema_version: Literal["v5.run_limits.v1"]
    profile_id: str
    version: Literal[1]
    values: tuple[LimitValue, ...]

    _validate_profile_id = field_validator("profile_id")(_non_empty)

    @model_validator(mode="after")
    def _has_baseline(self) -> "RunLimitsProfile":
        RunLimits(
            version=self.version,
            source_profile="profile-validation",
            source_digest="profile-validation",
            values=self.values,
        )
        return self


def load_run_limits_profile(path: str | Path) -> RunLimits:
    """Load only a committed, versioned policy profile; absent/malformed is fatal."""

    profile_path = Path(path)
    try:
        raw = profile_path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid source-controlled Run Limits profile: {profile_path}") from exc
    try:
        # Strict JSON validation preserves exact scalar types while accepting
        # JSON arrays for immutable tuple fields.
        profile = RunLimitsProfile.model_validate_json(raw)
    except ValidationError as exc:
        raise ValueError(f"invalid source-controlled Run Limits profile: {profile_path}") from exc
    return RunLimits(
        version=profile.version,
        source_profile=profile_path.as_posix(),
        source_digest=digest_bytes("run-limits-profile", raw),
        values=profile.values,
    )
