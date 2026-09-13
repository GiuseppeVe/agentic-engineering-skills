"""Canonical, content-addressed real-system adapter admission manifests."""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import field_validator, model_validator

from ..canonical import digest_for
from ..policy import (
    EgressPolicy,
    EvidencePolicy,
    ExactTarget,
    PolicyStrictModel,
    ProductionWritePlan,
    RealSystemBudgets,
    SecretReference,
    SyntheticScope,
    TeardownPolicy,
    TypedEffect,
)


_SHA256 = re.compile(r"[0-9a-f]{64}")


class AdapterManifest(PolicyStrictModel):
    """All real-system authority must be declared before durable state exists."""

    schema_version: Literal["graph-v5.adapter-manifest.v1"]
    manifest_id: str
    adapter_id: str
    adapter_interface_digest: str
    mode: Literal["fixture", "local_isolated", "remote_nonprod", "production_guarded"]
    target: ExactTarget
    synthetic_scope: SyntheticScope
    capabilities: tuple[TypedEffect, ...]
    budgets: RealSystemBudgets
    secrets: tuple[SecretReference, ...]
    egress: EgressPolicy
    evidence: EvidencePolicy
    teardown: TeardownPolicy
    write_policy: Literal["read_only", "synthetic"]
    production_write_plan: ProductionWritePlan | None = None

    @model_validator(mode="before")
    @classmethod
    def _reject_unbound_production_write_policy(cls, value: Any) -> Any:
        if isinstance(value, dict):
            value = dict(value)
            if "write_policy" not in value:
                value["write_policy"] = (
                    "read_only" if value.get("mode") == "production_guarded" else "synthetic"
                )
            write_policy = value.get("write_policy")
            if (
                value.get("mode") == "production_guarded"
                and write_policy == "synthetic"
                and not value.get("production_write_plan")
            ):
                raise ValueError("production writes require an exact confirmed ProductionWritePlan")
        return value

    @field_validator("manifest_id", "adapter_id")
    @classmethod
    def _text_is_nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must be a non-empty string")
        return value

    @field_validator("adapter_interface_digest")
    @classmethod
    def _interface_digest_is_exact(cls, value: str) -> str:
        if _SHA256.fullmatch(value) is None:
            raise ValueError("adapter_interface_digest must be lowercase SHA-256 hexadecimal")
        return value

    @field_validator("capabilities")
    @classmethod
    def _capabilities_are_nonempty_and_distinct(
        cls, values: tuple[TypedEffect, ...]
    ) -> tuple[TypedEffect, ...]:
        if not values:
            raise ValueError("adapter manifest must declare allowed typed capabilities")
        effects = tuple(value.effect for value in values)
        if len(effects) != len(set(effects)):
            raise ValueError("adapter manifest may not duplicate typed capabilities")
        return values

    @field_validator("secrets")
    @classmethod
    def _secret_names_are_distinct(
        cls, values: tuple[SecretReference, ...]
    ) -> tuple[SecretReference, ...]:
        names = tuple(value.name for value in values)
        if len(names) != len(set(names)):
            raise ValueError("adapter manifest may not duplicate secret references")
        return values

    @model_validator(mode="after")
    def _is_registered_exact_and_mode_bound(self) -> "AdapterManifest":
        from .registry import resolve_descriptor

        resolve_descriptor(self)
        if self.mode in {"fixture", "local_isolated"}:
            if not self.target.is_loopback:
                raise ValueError(f"{self.mode} manifests require an exact loopback target")
            self.egress.admit()
            if self.mode == "fixture" and self.egress.hosts:
                raise ValueError("fixture manifests must deny all egress")
        else:
            if self.target.is_loopback:
                raise ValueError("remote manifests require an exact HTTPS target")
            self.egress.admit(required_host=self.target.host)
        if self.mode == "production_guarded":
            if self.write_policy == "synthetic" and self.production_write_plan is None:
                raise ValueError("production writes require an exact confirmed ProductionWritePlan")
        elif self.production_write_plan is not None:
            raise ValueError("ProductionWritePlan is valid only for production_guarded mode")
        return self

    @property
    def digest(self) -> str:
        return digest_for("adapter-manifest", self)
