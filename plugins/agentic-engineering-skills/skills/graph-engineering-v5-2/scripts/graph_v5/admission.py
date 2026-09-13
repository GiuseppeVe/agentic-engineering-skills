"""V5.2 canonical admission: validate all authority before durable host effects."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from .adapters.host_registry import HostProviderError, resolve_host_provider
from .adapters.manifest import AdapterManifest
from .environment import EnvironmentPreflightError, EnvironmentSnapshot
from .models import (
    BaselineNodeProposal,
    ConfirmedRealTrajectoryBundle,
    DerivedBehavioralNode,
    LandmarkVerification,
    RealSystemRunHead,
    V52RunState,
)
from .runtime import RealRuntimeController


class AdmissionError(ValueError):
    """Canonical bundle cannot become an admitted V5.2 run."""


class RealAdmissionCoordinator:
    """Turn confirmed canonical authority into one atomically persisted run."""

    @classmethod
    def start(
        cls,
        *,
        root: Path,
        bundle: ConfirmedRealTrajectoryBundle,
        manifest: AdapterManifest,
    ) -> RealRuntimeController:
        """Validate every input before store, process, or network setup."""

        root_path = cls._new_store_root(root)
        strict_bundle, strict_manifest = cls._validated_inputs(bundle, manifest)
        try:
            strict_bundle.validate_for_manifest(strict_manifest)
            provider = resolve_host_provider(strict_manifest.adapter_id)
            provider.validate_bundle_source(strict_bundle, strict_manifest)
        except (HostProviderError, ValueError) as exc:
            raise AdmissionError("provider authority or canonical bundle is not admitted") from exc

        initial_state = V52RunState(
            schema_version="graph-v5.run-state.v2",
            run_id=strict_bundle.brief.run_id,
            mode="running",
            trajectory=strict_bundle.brief,
            confirmation=strict_bundle.confirmation,
        )
        try:
            supervisor_receipts, egress_receipt = provider.acquire_environment_authority(
                initial_state, strict_manifest
            )
            snapshot = EnvironmentSnapshot.from_admitted_authority(
                manifest=strict_manifest,
                target_identity_digest=initial_state.trajectory.execution_envelope.target_identity_digest,
                supervisor_receipts=supervisor_receipts,
                egress_receipt=egress_receipt,
            )
            run_head = RealSystemRunHead(
                run_id=initial_state.run_id,
                manifest_digest=strict_manifest.digest,
                environment_snapshot_digest=snapshot.digest,
            )
            nodes = tuple(
                cls._seal_baseline_node(
                    item,
                    state=initial_state,
                    run_head=run_head,
                )
                for item in strict_bundle.baseline
            )
        except (EnvironmentPreflightError, HostProviderError, ValidationError, ValueError) as exc:
            raise AdmissionError("admitted host authority could not seal canonical baseline") from exc

        try:
            return RealRuntimeController._start_admitted(
                root=root_path,
                initial_state=initial_state,
                manifest=strict_manifest,
                baseline_nodes=nodes,
                baseline_proposals=strict_bundle.baseline,
                provider_authority=strict_bundle.provider_authority,
                supervisor_receipts=supervisor_receipts,
                egress_receipt=egress_receipt,
            )
        except (ValidationError, ValueError) as exc:
            raise AdmissionError("canonical admission failed before run initialization") from exc

    @staticmethod
    def _new_store_root(root: Path) -> Path:
        if not isinstance(root, Path):
            raise AdmissionError("admission store root must be a Path")
        root_path = root.resolve(strict=False)
        if root_path.exists():
            raise AdmissionError("admission store root must not already exist")
        return root_path

    @staticmethod
    def _validated_inputs(
        bundle: ConfirmedRealTrajectoryBundle,
        manifest: AdapterManifest,
    ) -> tuple[ConfirmedRealTrajectoryBundle, AdapterManifest]:
        try:
            strict_bundle = ConfirmedRealTrajectoryBundle.model_validate(
                bundle.model_dump(mode="python")
                if isinstance(bundle, ConfirmedRealTrajectoryBundle)
                else bundle
            )
            strict_manifest = AdapterManifest.model_validate(
                manifest.model_dump(mode="python")
                if isinstance(manifest, AdapterManifest)
                else manifest
            )
        except (AttributeError, TypeError, ValidationError, ValueError) as exc:
            raise AdmissionError("canonical confirmed bundle and manifest are required") from exc
        return strict_bundle, strict_manifest

    @staticmethod
    def _seal_baseline_node(
        baseline: BaselineNodeProposal,
        *,
        state: V52RunState,
        run_head: RealSystemRunHead,
    ) -> DerivedBehavioralNode:
        proposal = baseline.proposal
        if proposal.action_kind == "verify_only":
            proposal = LandmarkVerification.model_validate(
                {
                    **proposal.model_dump(mode="python"),
                    "current_run_head_proof_ref": f"admission:run-head:{run_head.digest}",
                }
            )
        return DerivedBehavioralNode.seal(
            proposal,
            entry_observation_refs=baseline.entry_observation_refs,
            run_id=state.run_id,
            trajectory_digest=state.trajectory.digest,
            run_head_digest=run_head.digest,
            execution_envelope_digest=state.trajectory.execution_envelope.digest,
        )
