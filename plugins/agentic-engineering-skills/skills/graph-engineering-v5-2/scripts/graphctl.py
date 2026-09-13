#!/usr/bin/env python3
"""Graph Engineering V5 public command facade.

Only public parsing and immutable result projection live here. Runtime owns
durable state and product mutations. No command has a default run, artifact,
or benchmark root.
"""

from __future__ import annotations

import sys

# REQ-009 includes repository bytes: local imports must not create __pycache__
# before public input and explicit confirmation have been validated.
sys.dont_write_bytecode = True

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

from pydantic import ValidationError


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from scripts.graph_v5.environment import (
    EnvironmentPreflightError,
    HostPreflightConfig,
    LocalHostPreflightProbe,
    StartRequest,
    StartTransactionError,
)
from scripts.graph_v5.canonical import canonical_json_bytes
from scripts.graph_v5.models import (
    ConfirmedRealTrajectoryBundle,
    ConfirmedTrajectoryBundle,
    RealSystemDecision,
    TrajectoryBrief,
    TrajectoryConfirmation,
    UserDecision,
    VersionedLimits,
    import_v4_replacement_brief,
    load_run_limits_profile,
)
from scripts.graph_v5.adapters.manifest import AdapterManifest
from scripts.graph_v5.admission import AdmissionError
from scripts.graph_v5.runtime import (
    RealRuntimeController,
    RealRuntimeSliceResult,
    RuntimeController,
    RuntimeError as V5RuntimeError,
)
from scripts.graph_v5.store import CapabilityError, RecoveryError, StoreError
from scripts.graph_v5.trajectory import TrajectoryValidationError, validate_confirmed_trajectory
from scripts.graph_v5.workspace import GraphWorkspaceLifecycle, WorktreePreflightConfig, WorkspaceError


PUBLIC_COMMANDS = ("start", "run", "status", "decision")


@dataclass(frozen=True, slots=True)
class HarnessResultEnvelope:
    """Strict non-mutating projection returned by every public command."""

    status: str
    summary: str
    next_actions: tuple[str, ...]
    artifacts: tuple[str, ...]
    error_code: str | None
    root_cause_hint: str | None
    safe_retry: bool
    stop_condition: str | None
    trajectory_digest: str | None = None

    @property
    def exit_code(self) -> int:
        return 2 if self.error_code == "goal_brief_removed" else 0

    def as_dict(self) -> dict[str, object]:
        result = {
            "status": self.status,
            "summary": self.summary,
            "next_actions": list(self.next_actions),
            "artifacts": list(self.artifacts),
            "error_code": self.error_code,
            "root_cause_hint": self.root_cause_hint,
            "safe_retry": self.safe_retry,
            "stop_condition": self.stop_condition,
        }
        if self.trajectory_digest is not None:
            result["trajectory_digest"] = self.trajectory_digest
        return result


@dataclass(frozen=True, slots=True)
class _FixtureCapabilityDeriver:
    """Deterministic fixture capability planner; fixture never owns authority."""

    action_catalog: tuple[Mapping[str, object], ...]

    @classmethod
    def from_fixture_file(
        cls, fixture_file: str | Path, scenario_id: str
    ) -> "_FixtureCapabilityDeriver":
        try:
            payload = json.loads(Path(fixture_file).read_text(encoding="utf-8"))
            scenarios = payload["scenarios"]
            scenario = next(
                item
                for item in scenarios
                if isinstance(item, dict) and item.get("scenario_id") == scenario_id
            )
            catalog = scenario["action_catalog"]
        except (OSError, KeyError, StopIteration, TypeError, json.JSONDecodeError) as error:
            raise V5RuntimeError("fixture capability catalog is unavailable") from error
        if not isinstance(catalog, list) or not all(isinstance(item, dict) for item in catalog):
            raise V5RuntimeError("fixture capability catalog is invalid")
        return cls(action_catalog=tuple(catalog))

    def derive_next(self, trajectory: object, spine: object, entry_observation: object) -> object:
        from scripts.graph_v5.models import EvidenceGap, LandmarkVerification, NodeProposal

        target_id = spine.frontier.target_landmark_id
        if target_id is None:
            raise V5RuntimeError("fixture deriver requires an uncompleted Derived Spine frontier")
        target = next(
            item for item in trajectory.landmarks if item.landmark_id == target_id
        )
        scope = trajectory.execution_envelope.allowed_scope[0]
        source_anchor = entry_observation.node_id
        source_authority = (
            "trajectory:start_state"
            if source_anchor == "START"
            else (
                f"trajectory:landmarks:{source_anchor}"
                if source_anchor in {item.landmark_id for item in trajectory.landmarks}
                else f"derived-spine:nodes:{source_anchor}"
            )
        )
        authority_refs = (
            source_authority,
            f"trajectory:landmarks:{target_id}",
            "trajectory:execution_envelope",
        )
        if entry_observation.observed_state in {target.description, *target.acceptance}:
            return LandmarkVerification(
                node_id=f"fixture-verify:{target_id}:{len(spine.nodes) + 1}",
                source_anchor_id=source_anchor,
                target_landmark_id=target_id,
                action_or_probe=f"Verify {target_id} from current observation",
                expected_before=(entry_observation.observed_state,),
                expected_after=(entry_observation.observed_state,),
                derivation_reason="Current persisted observation already proves the confirmed landmark.",
                authority_refs=authority_refs,
                execution_scope=scope,
                side_effect=None,
                target_systems=(f"fixture:{scope}",),
                current_run_head_proof_ref=entry_observation.evidence_refs[0],
            )
        candidates = tuple(
            item
            for item in self.action_catalog
            if item.get("required_observed_state") == entry_observation.observed_state
            and item.get("action_kind") in {"act", "probe"}
            and isinstance(item.get("action_or_probe"), str)
            and isinstance(item.get("observed_state"), str)
        )
        if not candidates:
            return EvidenceGap(
                target_landmark_id=target_id,
                observation_refs=entry_observation.evidence_refs,
                evidence_gap="Fixture capabilities expose no action supported by current observation.",
                smallest_needed_input="One in-envelope read-only observation of the next fixture capability.",
                exhausted_safe_probes=("fixture-capability-catalog",),
            )
        candidate = min(
            candidates,
            key=lambda item: (str(item["action_kind"]), str(item["action_or_probe"])),
        )
        effect = next(
            (
                item
                for item in trajectory.execution_envelope.allowed_side_effects
                if item.startswith("fixture:")
            ),
            None,
        )
        if effect is None:
            return EvidenceGap(
                target_landmark_id=target_id,
                observation_refs=entry_observation.evidence_refs,
                evidence_gap="Execution Envelope permits no fixture side effect for current capability.",
                smallest_needed_input="Explicit in-envelope fixture side-effect authorization.",
                exhausted_safe_probes=("fixture-capability-catalog",),
            )
        return NodeProposal(
            node_id=f"fixture-derived:{target_id}:{len(spine.nodes) + 1}",
            source_anchor_id=source_anchor,
            target_landmark_id=target_id,
            action_kind=candidate["action_kind"],
            action_or_probe=candidate["action_or_probe"],
            expected_before=(entry_observation.observed_state,),
            expected_after=(candidate["observed_state"],),
            derivation_reason="Current fixture capability is bounded by persisted operational Trajectory authority.",
            authority_refs=authority_refs,
            execution_scope=scope,
            side_effect=effect,
            target_systems=(f"fixture:{scope}",),
        )


def _envelope(
    *,
    status: str,
    summary: str,
    next_actions: tuple[str, ...] = (),
    artifacts: tuple[str, ...] = (),
    error_code: str | None = None,
    root_cause_hint: str | None = None,
    safe_retry: bool = False,
    stop_condition: str | None = None,
    trajectory_digest: str | None = None,
) -> HarnessResultEnvelope:
    return HarnessResultEnvelope(
        status=status,
        summary=summary,
        next_actions=next_actions,
        artifacts=artifacts,
        error_code=error_code,
        root_cause_hint=root_cause_hint,
        safe_retry=safe_retry,
        stop_condition=stop_condition,
        trajectory_digest=trajectory_digest,
    )


def _add_read_only_options(command: argparse.ArgumentParser) -> None:
    command.add_argument(
        "--preview",
        action="store_true",
        help="Project planned work without creating state or artifacts.",
    )
    command.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate input without creating state or artifacts.",
    )


def _add_explicit_roots(command: argparse.ArgumentParser) -> None:
    """Accept caller-selected watched roots without creating/opening defaults."""

    command.add_argument("--run-store-root", help="Explicit durable V5 run store root.")
    command.add_argument("--artifact-root", help="Optional watched artifact root; never opened here.")
    command.add_argument("--benchmark-root", help="Optional watched benchmark root; never opened here.")
    command.add_argument("--v4-reference", help="Read-only V4 predecessor JSON reference.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="graphctl.py",
        description=(
            "Graph Engineering V5 public interface. Runtime owns durable state "
            "and all product mutations."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)

    start = commands.add_parser("start", help="Validate confirmed Trajectory Brief and crash-safe start.")
    _add_read_only_options(start)
    _add_explicit_roots(start)
    start.add_argument("--run-id", help="New V5 run identifier.")
    start.add_argument(
        "--trajectory-brief",
        required=False,
        help="Path or run-artifact reference to a confirmed Trajectory Brief bundle.",
    )
    start.add_argument(
        "--adapter-manifest",
        help="Canonical adapter manifest for a confirmed real trajectory bundle.",
    )
    start.add_argument("--goal-brief", help=argparse.SUPPRESS)
    start.add_argument("--limits-profile", help="Path to source-controlled Run Limits JSON.")
    start.add_argument("--repository-root", help="Clean verified source repository root.")
    start.add_argument("--base-revision", help="Exact verified source commit.")
    start.add_argument("--graph-worktree-root", help="Parent directory for owned Graph-run worktree.")
    start.add_argument("--fixture-relative-path", help="Marked disposable fixture directory in worktree.")
    start.add_argument("--validator-relative-path", help="Marked disposable validator directory in worktree.")
    start.add_argument("--required-package-binary", action="append", default=[])
    start.add_argument("--path-reserve-chars", type=int, default=32)
    start.add_argument("--main-branch", default="main")

    run = commands.add_parser("run", help="Advance one bounded autonomous traversal slice.")
    _add_read_only_options(run)
    _add_explicit_roots(run)
    run.add_argument("--run-id", help="Existing V5 run identifier.")
    # Legacy V5.1 compatibility only. V5.2 selects its fixture adapter from
    # persisted admission authority, so these must not be public run inputs.
    run.add_argument("--fixture-file", help=argparse.SUPPRESS)
    run.add_argument("--fixture-scenario", help=argparse.SUPPRESS)
    run.add_argument("--max-nodes", type=int, default=1)

    status = commands.add_parser("status", help="Project immutable progress without writing state.")
    _add_explicit_roots(status)
    status.add_argument("--run-id", help="Existing V5 run identifier.")

    decision = commands.add_parser("decision", help="Apply one digest-bound pending user decision.")
    _add_explicit_roots(decision)
    decision.add_argument("--run-id", help="Paused V5 run identifier.")
    decision.add_argument(
        "--decision-file",
        help="Strict digest-bound decision JSON; stored run schema selects its type.",
    )
    return parser


def _read_strict_json(
    path_text: str,
    model_type: type[UserDecision] | type[RealSystemDecision],
) -> object:
    try:
        payload = Path(path_text).read_bytes()
    except OSError as error:
        raise ValueError(f"cannot read input JSON: {path_text}") from error
    try:
        return model_type.model_validate_json(payload)
    except ValidationError as error:
        raise ValueError(f"input does not satisfy strict {model_type.__name__}") from error


def _read_canonical_json(path: Path, *, label: str) -> object:
    try:
        payload = path.read_bytes()
    except OSError as error:
        raise ValueError(f"confirmed trajectory bundle is missing {label}") from error
    try:
        decoded = json.loads(payload.decode("utf-8"))
        canonical = canonical_json_bytes(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError(f"confirmed trajectory bundle {label} is not canonical JSON") from error
    if payload != canonical:
        raise ValueError(f"confirmed trajectory bundle {label} is not canonical JSON")
    return decoded


def _load_confirmed_trajectory_bundle(path_text: str) -> ConfirmedTrajectoryBundle:
    """Load one self-contained, confirmation-bound trajectory bundle without writes."""

    bundle_root = Path(path_text)
    if not bundle_root.is_dir():
        raise ValueError(
            "--trajectory-brief must reference one confirmed bundle directory; bare briefs are rejected"
        )
    brief_path = bundle_root / "trajectory-brief.json"
    markdown_path = bundle_root / "trajectory-brief.md"
    confirmation_path = bundle_root / "trajectory-confirmation.json"
    try:
        brief = TrajectoryBrief.model_validate(
            _read_canonical_json(brief_path, label="trajectory-brief.json")
        )
    except ValidationError as error:
        field = ".".join(str(item) for item in error.errors()[0]["loc"])
        correction = error.errors()[0]["msg"]
        raise ValueError(
            f"confirmed trajectory bundle trajectory-brief.json field {field} "
            f"is invalid: {correction}"
        ) from error
    try:
        confirmation = TrajectoryConfirmation.model_validate(
            _read_canonical_json(
                confirmation_path, label="trajectory-confirmation.json"
            )
        )
    except ValidationError as error:
        field = ".".join(str(item) for item in error.errors()[0]["loc"])
        correction = error.errors()[0]["msg"]
        raise ValueError(
            f"confirmed trajectory bundle trajectory-confirmation.json field {field} "
            f"is invalid: {correction}"
        ) from error
    try:
        markdown = markdown_path.read_bytes()
    except OSError as error:
        raise ValueError(
            "confirmed trajectory bundle is missing trajectory-brief.md"
        ) from error
    try:
        return validate_confirmed_trajectory(brief, markdown, confirmation)
    except TrajectoryValidationError as error:
        detail = str(error)
        if detail.startswith("Markdown"):
            field = "trajectory-brief.md"
        elif detail.startswith("confirmation"):
            field = "trajectory-confirmation.json"
        elif detail.startswith("material ambiguities"):
            field = "trajectory-brief.json field material_ambiguities"
        else:
            field = "confirmed authority binding"
        raise ValueError(
            f"confirmed trajectory bundle {field} invalid: {detail}"
        ) from error


def _load_confirmed_real_trajectory_bundle(path_text: str) -> ConfirmedRealTrajectoryBundle:
    """Load one canonical V5.2 admission bundle without store or host effects."""

    try:
        payload = _read_canonical_json(
            Path(path_text), label="confirmed-real-trajectory-bundle.json"
        )
        return ConfirmedRealTrajectoryBundle.model_validate(payload)
    except ValidationError as error:
        field = ".".join(str(item) for item in error.errors()[0]["loc"])
        raise ValueError(
            f"confirmed real trajectory bundle field {field} is invalid"
        ) from error


def _is_confirmed_real_trajectory_bundle_reference(path_text: str) -> bool:
    """Detect V5.2 intake schema without store, recovery, or host effects."""

    try:
        payload = json.loads(Path(path_text).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return (
        isinstance(payload, dict)
        and payload.get("schema_version")
        == "graph-v5.confirmed-real-trajectory-bundle.v1"
    )


def _load_adapter_manifest(path_text: str) -> AdapterManifest:
    """Load one canonical static adapter manifest without dynamic provider input."""

    try:
        payload = _read_canonical_json(Path(path_text), label="adapter-manifest.json")
        return AdapterManifest.model_validate(payload)
    except ValidationError as error:
        field = ".".join(str(item) for item in error.errors()[0]["loc"])
        raise ValueError(f"adapter manifest field {field} is invalid") from error


def _is_v52_real_run(root: str, run_id: str) -> bool:
    """Inspect stored schema bytes only; never recover, create, or mutate a run."""

    try:
        payload = json.loads((Path(root) / "state.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return (
        isinstance(payload, dict)
        and payload.get("schema_version") == "graph-v5.run-state.v2"
        and payload.get("run_id") == run_id
    )


def _load_v4_reference(path_text: str | None) -> tuple[object, dict[str, object]] | None:
    if path_text is None:
        return None
    try:
        decoded = json.loads(Path(path_text).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("V4 reference is not readable strict JSON") from error
    if not isinstance(decoded, dict):
        raise ValueError("V4 reference must be a JSON object")
    return import_v4_replacement_brief(decoded, provenance=str(Path(path_text))), decoded


def _v4_envelope(command: str, reference: tuple[object, dict[str, object]]) -> HarnessResultEnvelope:
    brief, raw = reference
    digest = getattr(brief, "original_digest")
    if command == "status":
        phase = raw.get("phase") or raw.get("mode") or "terminal history"
        return _envelope(
            status=str(phase),
            summary="V4 immutable terminal history projected as untrusted predecessor observation.",
            next_actions=("Create separate V5 replacement run with confirmed Trajectory Brief.",),
            artifacts=(f"v4-replacement-brief:{digest}",),
            safe_retry=False,
            stop_condition="V4 references are immutable.",
        )
    return _envelope(
        status="blocked",
        summary="V4 reference is immutable; create V5 replacement run instead.",
        next_actions=("Start separate V5 replacement run with confirmed Trajectory Brief.",),
        artifacts=(f"v4-replacement-brief:{digest}",),
        error_code="v4_immutable",
        root_cause_hint="V5 never reopens, migrates, or edits V4 state.",
        safe_retry=False,
        stop_condition="V4 references are immutable.",
    )


def _missing(*fields: str) -> HarnessResultEnvelope:
    return _envelope(
        status="blocked",
        summary=f"Missing required public input: {', '.join(fields)}.",
        next_actions=("Supply only explicit V5 public command inputs.",),
        error_code="input_required",
        root_cause_hint="No default run, artifact, or benchmark root exists.",
        safe_retry=True,
        stop_condition="Required public input is absent.",
    )


def _read_only_projection(command: str) -> HarnessResultEnvelope:
    return _envelope(
        status="preview",
        summary=f"{command} accepted for read-only projection; no state was created.",
        next_actions=("Remove --preview or --dry-run after reviewing explicit inputs.",),
        safe_retry=True,
        stop_condition="Read-only operator option requested.",
    )


def _v4_or_error(args: argparse.Namespace, command: str) -> HarnessResultEnvelope | None:
    try:
        predecessor = _load_v4_reference(args.v4_reference)
    except ValueError as error:
        return _envelope(status="blocked", summary=str(error), error_code="invalid_v4_reference")
    return _v4_envelope(command, predecessor) if predecessor is not None else None


def start_run(args: argparse.Namespace) -> HarnessResultEnvelope:
    if args.goal_brief is not None:
        return _envelope(
            status="blocked",
            summary=(
                "--goal-brief is no longer supported by Graph Engineering V5.\n"
                "Create or confirm a graph-v5.trajectory-brief.v1 input and use --trajectory-brief."
            ),
            error_code="goal_brief_removed",
            safe_retry=True,
            stop_condition="Legacy Goal Brief input is not V5 trajectory authority.",
        )
    v4 = _v4_or_error(args, "start")
    if v4 is not None:
        return v4
    is_real_bundle = (
        args.trajectory_brief is not None
        and _is_confirmed_real_trajectory_bundle_reference(args.trajectory_brief)
    )
    if args.adapter_manifest is not None or is_real_bundle:
        if args.trajectory_brief is None:
            return _missing("--trajectory-brief")
        if args.adapter_manifest is None:
            return _missing("--adapter-manifest")
        try:
            real_bundle = _load_confirmed_real_trajectory_bundle(args.trajectory_brief)
            manifest = _load_adapter_manifest(args.adapter_manifest)
        except ValueError as error:
            return _envelope(
                status="blocked",
                summary="Confirmed real trajectory bundle validation failed.",
                next_actions=(
                    "Provide canonical confirmed real trajectory and adapter manifest bytes.",
                ),
                error_code="invalid_trajectory_brief",
                root_cause_hint=str(error),
                safe_retry=True,
                stop_condition="Confirmed real trajectory authority is invalid.",
            )
        if args.run_id is not None and args.run_id != real_bundle.brief.run_id:
            return _envelope(
                status="blocked",
                summary="Confirmed real trajectory run ID does not match --run-id.",
                next_actions=("Use run ID bound into confirmed real trajectory authority.",),
                error_code="trajectory_run_id_mismatch",
                safe_retry=True,
                stop_condition="CLI run ID cannot replace confirmed real trajectory authority.",
            )
        if args.preview or args.dry_run:
            projection = _read_only_projection("start")
            return _envelope(
                status=projection.status,
                summary=projection.summary,
                next_actions=projection.next_actions,
                artifacts=projection.artifacts,
                error_code=projection.error_code,
                root_cause_hint=projection.root_cause_hint,
                safe_retry=projection.safe_retry,
                stop_condition=projection.stop_condition,
                trajectory_digest=real_bundle.brief.digest,
            )
        if args.run_store_root is None:
            return _missing("--run-store-root")
        try:
            runtime = RealRuntimeController.start_from_confirmed_bundle(
                root=Path(args.run_store_root), bundle=real_bundle, manifest=manifest
            )
            run_head = runtime.state.facts.run_head
            if run_head is None:
                raise V5RuntimeError("admitted real trajectory did not persist a Run Head")
        except (AdmissionError, StoreError, CapabilityError, V5RuntimeError, ValueError) as error:
            return _envelope(
                status="blocked",
                summary="Confirmed real trajectory start did not advance.",
                next_actions=("Correct canonical bundle, manifest, or admitted run-store input.",),
                error_code="start_rejected",
                root_cause_hint=str(error),
                safe_retry=True,
                stop_condition="Real-system admission precondition failed.",
            )
        return _envelope(
            status=runtime.state.mode,
            summary="Confirmed real trajectory admitted; first bounded step is ready.",
            next_actions=("Run one bounded autonomous traversal slice.",),
            artifacts=(
                f"trajectory-brief:{real_bundle.brief.digest}",
                f"run-head:{run_head.digest}",
            ),
            safe_retry=True,
            stop_condition="Admitted baseline traversal has not yet run.",
            trajectory_digest=real_bundle.brief.digest,
        )
    confirmed: ConfirmedTrajectoryBundle | None = None
    if args.trajectory_brief is not None:
        try:
            confirmed = _load_confirmed_trajectory_bundle(args.trajectory_brief)
        except ValueError as error:
            return _envelope(
                status="blocked",
                summary="Confirmed Trajectory Brief validation failed.",
                next_actions=(
                    "Provide one canonical confirmed Trajectory Brief bundle with exact Markdown and confirmation.",
                ),
                error_code="invalid_trajectory_brief",
                root_cause_hint=str(error),
                safe_retry=True,
                stop_condition="Confirmed Trajectory Brief bundle is invalid.",
            )
        if args.run_id is not None and args.run_id != confirmed.brief.run_id:
            return _envelope(
                status="blocked",
                summary="Confirmed Trajectory Brief run ID does not match --run-id.",
                next_actions=("Use the run ID bound into the confirmed Trajectory Brief.",),
                error_code="trajectory_run_id_mismatch",
                safe_retry=True,
                stop_condition="CLI run ID cannot replace confirmed trajectory authority.",
            )
    if args.preview or args.dry_run:
        projection = _read_only_projection("start")
        if confirmed is None:
            return projection
        return _envelope(
            status=projection.status,
            summary=projection.summary,
            next_actions=projection.next_actions,
            artifacts=projection.artifacts,
            error_code=projection.error_code,
            root_cause_hint=projection.root_cause_hint,
            safe_retry=projection.safe_retry,
            stop_condition=projection.stop_condition,
            trajectory_digest=confirmed.brief.digest,
        )
    required = tuple(
        name
        for name, value in (
            ("--run-id", args.run_id),
            ("--trajectory-brief", confirmed),
            ("--limits-profile", args.limits_profile),
            ("--run-store-root", args.run_store_root),
            ("--repository-root", args.repository_root),
            ("--base-revision", args.base_revision),
            ("--graph-worktree-root", args.graph_worktree_root),
            ("--fixture-relative-path", args.fixture_relative_path),
            ("--validator-relative-path", args.validator_relative_path),
        )
        if value is None
    )
    if required:
        return _missing(*required)
    assert confirmed is not None
    try:
        limits = load_run_limits_profile(args.limits_profile)
        repository_root = Path(args.repository_root).resolve(strict=False)
        workspace_lifecycle = GraphWorkspaceLifecycle(
            repository_root,
            preflight=WorktreePreflightConfig(
                fixture_relative_path=args.fixture_relative_path,
                validator_relative_path=args.validator_relative_path,
                required_package_binaries=tuple(args.required_package_binary),
            ),
            main_branch=args.main_branch,
        )
        request = StartRequest(
            repository_root=repository_root,
            requested_base_revision=args.base_revision,
            candidate_branch=f"graph-run/{args.run_id}",
            candidate_worktree_path=Path(args.graph_worktree_root).resolve(strict=False) / args.run_id,
            durable_store_root=Path(args.run_store_root).resolve(strict=False),
            host_config=HostPreflightConfig(path_reserve_chars=args.path_reserve_chars),
            host_probe=LocalHostPreflightProbe(),
            workspace_lifecycle=workspace_lifecycle,
        )
        _, result = RuntimeController.start(
            root=args.run_store_root,
            confirmed=confirmed,
            limits=VersionedLimits(versions=(limits,), active_version=1),
            request=request,
        )
    except (ValueError, EnvironmentPreflightError, StartTransactionError, WorkspaceError, StoreError, CapabilityError, V5RuntimeError) as error:
        return _envelope(
            status="blocked",
            summary="Crash-safe V5 start did not advance.",
            next_actions=("Correct confirmed trajectory, limits, repository, or worktree inputs.",),
            error_code="start_rejected",
            root_cause_hint=str(error),
            safe_retry=True,
            stop_condition="Crash-safe start precondition failed.",
        )
    return _envelope(
        status="running",
        summary="Crash-safe V5 start completed; first Behavioral Node is ready.",
        next_actions=("Run one bounded autonomous traversal slice.",),
        artifacts=(
            f"trajectory-brief:{confirmed.brief.digest}",
            f"run-head:{result.run_head.digest}",
            f"graph-run-branch:{result.transaction.branch}",
            f"graph-run-worktree:{result.transaction.worktree_path}",
        ),
        safe_retry=True,
        stop_condition="Behavioral Node traversal has not yet run.",
        trajectory_digest=confirmed.brief.digest,
    )


def continue_run(args: argparse.Namespace) -> HarnessResultEnvelope:
    v4 = _v4_or_error(args, "run")
    if v4 is not None:
        return v4
    if args.preview or args.dry_run:
        return _read_only_projection("run")
    required = tuple(
        name
        for name, value in (
            ("--run-store-root", args.run_store_root),
            ("--run-id", args.run_id),
        )
        if value is None
    )
    if required:
        return _missing(*required)
    assert args.run_store_root is not None and args.run_id is not None
    if _is_v52_real_run(args.run_store_root, args.run_id):
        if args.fixture_file is not None or args.fixture_scenario is not None:
            return _envelope(
                status="blocked",
                summary="V5.2 run rejects caller-supplied fixture authority.",
                next_actions=("Run V5.2 from persisted admitted authority only.",),
                error_code="run_rejected",
                safe_retry=True,
                stop_condition="V5.2 runtime fixture source is selected at admission.",
            )
        try:
            result = RealRuntimeController.open(
                root=args.run_store_root, run_id=args.run_id
            ).run_next_persisted_slice(max_nodes=args.max_nodes)
        except (StoreError, CapabilityError, V5RuntimeError, ValueError) as error:
            return _envelope(
                status="blocked",
                summary="Bounded V5.2 run slice did not advance.",
                next_actions=("Inspect immutable status, then retry only when safe.",),
                error_code="run_rejected",
                root_cause_hint=str(error),
                safe_retry=True,
                stop_condition="Persisted V5.2 authority rejected execution.",
            )
        return _project_v52_slice(result)
    legacy_required = tuple(
        name
        for name, value in (
            ("--fixture-file", args.fixture_file),
            ("--fixture-scenario", args.fixture_scenario),
        )
        if value is None
    )
    if legacy_required:
        return _missing(*legacy_required)
    try:
        runtime = RuntimeController.open(root=args.run_store_root, run_id=args.run_id)
        deriver = _FixtureCapabilityDeriver.from_fixture_file(
            args.fixture_file, args.fixture_scenario
        )
        from scripts.graph_v5.adapters.user_journey import FixtureUserJourneyAdapter

        adapter = FixtureUserJourneyAdapter.from_fixture_file(
            args.fixture_file, args.fixture_scenario
        )
        result = runtime.run_bounded_slice(
            adapter=adapter, deriver=deriver, max_nodes=args.max_nodes
        )
    except (ValueError, StoreError, CapabilityError, V5RuntimeError) as error:
        return _envelope(
            status="blocked",
            summary="Bounded V5 run slice did not advance.",
            next_actions=("Inspect immutable status; supply sealed fixture only.",),
            error_code="run_rejected",
            root_cause_hint=str(error),
            safe_retry=True,
            stop_condition="Bounded runtime slice rejected input or durable state.",
        )
    return _envelope(
        status=result.state.mode,
        summary=result.summary,
        next_actions=(RuntimeController._project_status(result.state).next_automatic_step,),
        artifacts=("current_node",) if result.node_id is not None else (),
        error_code=("observed_failure" if result.outcome == "observed_failure" else None),
        safe_retry=result.safe_retry,
        stop_condition=result.stop_condition,
    )


def _project_v52_slice(result: RealRuntimeSliceResult) -> HarnessResultEnvelope:
    """Keep persisted V5.2 execution authority internal to public CLI projection."""

    completed = result.node_id
    return _envelope(
        status=result.state.mode,
        summary=(
            "Bounded V5.2 traversal slice completed."
            if completed is not None
            else "No V5.2 traversal step was available."
        ),
        next_actions=("Inspect status for recommended next step.",),
        artifacts=() if completed is None else (f"completed-node:{completed}",),
        safe_retry=result.state.mode == "running",
        stop_condition=None if result.state.mode == "running" else "V5.2 run is no longer active.",
    )


def project_status(args: argparse.Namespace) -> HarnessResultEnvelope:
    v4 = _v4_or_error(args, "status")
    if v4 is not None:
        return v4
    missing = tuple(
        name
        for name, value in (("--run-store-root", args.run_store_root), ("--run-id", args.run_id))
        if value is None
    )
    if missing:
        return _missing(*missing)
    assert args.run_store_root is not None and args.run_id is not None
    if _is_v52_real_run(args.run_store_root, args.run_id):
        try:
            status = RealRuntimeController.read_only_status(
                root=Path(args.run_store_root), run_id=args.run_id
            )
        except (StoreError, CapabilityError, V5RuntimeError, ValueError) as error:
            return _envelope(
                status="blocked",
                summary="Read-only status cannot project requested V5.2 run.",
                next_actions=("Supply existing admitted V5.2 run store and identifier.",),
                error_code="status_unavailable",
                root_cause_hint=str(error),
                safe_retry=True,
                stop_condition="Requested V5.2 run is unavailable or invalid.",
            )
        terminal_budget_exhaustion = None
        if status.mode == "blocked":
            facts = RealRuntimeController.open_readonly(
                root=Path(args.run_store_root), run_id=args.run_id
            ).state.facts
            if facts.manifest_budget_exhaustions:
                terminal_budget_exhaustion = facts.manifest_budget_exhaustions[-1]
        next_step = (
            None
            if terminal_budget_exhaustion is not None
            else status.next_executable_node_id or status.recommended_baseline_node_id
        )
        artifacts = tuple(
            item
            for item in (
                None
                if terminal_budget_exhaustion is not None
                or status.recommended_baseline_node_id is None
                else f"recommended-baseline:{status.recommended_baseline_node_id}",
                None
                if terminal_budget_exhaustion is not None
                or status.next_executable_node_id is None
                else f"next-step:{status.next_executable_node_id}",
                *(
                    f"exploration:{item.node_id}:from:{item.parent_node_id}"
                    for item in status.active_explorations
                ),
                *(f"remaining-budget:{name}={value}" for name, value in status.remaining_budget),
            )
            if item is not None
        )
        return _envelope(
            status=status.mode,
            summary=(
                "V5.2 status is recovery-pending; no recovery was attempted."
                if status.mode == "recovery_pending"
                else "V5.2 status projected persisted authority without mutation."
            ),
            next_actions=(
                "Use run to recover safely."
                if status.mode == "recovery_pending"
                else ()
                if terminal_budget_exhaustion is not None
                else (
                    "Run one bounded autonomous traversal slice."
                    if next_step is not None
                    else "No further admitted traversal step is currently available."
                )
            ),
            artifacts=artifacts,
            error_code=("recovery_pending" if status.mode == "recovery_pending" else None),
            safe_retry=status.mode == "running",
            stop_condition=(
                "Pending recovery requires a mutating run."
                if status.mode == "recovery_pending"
                else "Manifest budget exhausted: "
                + ", ".join(terminal_budget_exhaustion.exhausted_budget_names)
                + "."
                if terminal_budget_exhaustion is not None
                else (
                    f"Pending exceptional decision: {status.pending_decision_kind}."
                    if status.pending_decision_kind is not None
                    else None
                )
            ),
        )
    try:
        status = RuntimeController.read_only_status(
            root=args.run_store_root, run_id=args.run_id
        )
    except RecoveryError as error:
        return _envelope(
            status="blocked",
            summary="Read-only status refused pending recovery.",
            next_actions=("Use explicit mutating run command to recover safely.",),
            error_code="recovery_pending",
            root_cause_hint=str(error),
            safe_retry=True,
            stop_condition="Read-only status cannot recover a journal.",
        )
    except (StoreError, CapabilityError) as error:
        return _envelope(
            status="blocked",
            summary="Read-only status cannot project requested V5 run.",
            next_actions=("Supply existing explicit V5 run store and run identifier.",),
            error_code="status_unavailable",
            root_cause_hint=str(error),
            safe_retry=True,
            stop_condition="Requested run is unavailable or invalid.",
        )
    artifacts = [
        "current_node",
        "current_cone",
        "remaining_limits",
        f"persisted-facts:{status.progress_fact_count}",
    ]
    if status.current_node_id is not None:
        artifacts.append(f"current-node:{status.current_node_id}")
    if status.current_cone_id is not None and status.current_cone_digest is not None:
        artifacts.append(
            f"current-cone:{status.current_cone_id}:{status.current_cone_digest}"
        )
    if status.graph_run_branch is not None:
        artifacts.append(f"graph-run-branch:{status.graph_run_branch}")
    if status.graph_run_worktree is not None:
        artifacts.append(f"graph-run-worktree:{status.graph_run_worktree}")
    if status.sealed_environment_digest is not None:
        artifacts.append(f"sealed-environment:{status.sealed_environment_digest}")
    artifacts.extend(f"open-defect:{item}" for item in status.open_defect_ids)
    artifacts.extend(
        f"remaining-limit:{item.limit_name}={item.consumed}"
        for item in status.remaining_limits
    )
    return _envelope(
        status=status.mode,
        summary=(
            f"Run has {status.progress_fact_count} persisted progress facts; "
            f"current node is {status.current_node_id or 'none'}."
        ),
        next_actions=(status.next_automatic_step,),
        artifacts=tuple(artifacts),
        safe_retry=status.mode not in {"succeeded", "inconclusive", "blocked", "failed", "cancelled"},
        stop_condition=(
            "Pending user decision requires exact digest."
            if status.pending_decision_digest is not None
            else None
        ),
    )


def apply_decision(args: argparse.Namespace) -> HarnessResultEnvelope:
    v4 = _v4_or_error(args, "decision")
    if v4 is not None:
        return v4
    required = tuple(
        name
        for name, value in (
            ("--run-store-root", args.run_store_root),
            ("--run-id", args.run_id),
            ("--decision-file", args.decision_file),
        )
        if value is None
    )
    if required:
        return _missing(*required)
    assert args.run_store_root is not None and args.run_id is not None and args.decision_file is not None
    if _is_v52_real_run(args.run_store_root, args.run_id):
        try:
            loaded_decision = _read_strict_json(args.decision_file, RealSystemDecision)
            assert isinstance(loaded_decision, RealSystemDecision)
            state = RealRuntimeController.open(
                root=args.run_store_root, run_id=args.run_id
            ).apply_real_system_decision(loaded_decision)
        except (ValueError, StoreError, CapabilityError, V5RuntimeError) as error:
            return _envelope(
                status="blocked",
                summary="Digest-bound V5.2 exceptional decision was not applied.",
                next_actions=("Supply exact pending V5.2 decision authority.",),
                error_code="decision_rejected",
                root_cause_hint=str(error),
                safe_retry=True,
                stop_condition="No matching V5.2 exceptional decision was mutated.",
            )
        return _envelope(
            status=state.mode,
            summary="Digest-bound V5.2 exceptional decision appended immutably.",
            next_actions=("Run one bounded autonomous traversal slice.",),
            artifacts=("real-system-decision",),
            safe_retry=True,
        )
    try:
        loaded_decision = _read_strict_json(args.decision_file, UserDecision)
        assert isinstance(loaded_decision, UserDecision)
        state = RuntimeController.open(
            root=args.run_store_root, run_id=args.run_id
        ).apply_user_decision(loaded_decision)
    except (ValueError, StoreError, CapabilityError, V5RuntimeError) as error:
        return _envelope(
            status="blocked",
            summary="Digest-bound user decision was not applied.",
            next_actions=("Supply exact pending digest and allowed decision kind.",),
            error_code="decision_rejected",
            root_cause_hint=str(error),
            safe_retry=True,
            stop_condition="No matching pending user decision was mutated.",
        )
    return _envelope(
        status=state.mode,
        summary="Digest-bound user decision appended immutably.",
        next_actions=(RuntimeController._project_status(state).next_automatic_step,),
        artifacts=("user-decision",),
        safe_retry=True,
    )


_COMMAND_HANDLERS: Mapping[str, Callable[[argparse.Namespace], HarnessResultEnvelope]] = {
    "start": start_run,
    "run": continue_run,
    "status": project_status,
    "decision": apply_decision,
}


def dispatch_public_command(args: argparse.Namespace) -> HarnessResultEnvelope:
    return _COMMAND_HANDLERS[args.command](args)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    envelope = dispatch_public_command(args)
    print(json.dumps(envelope.as_dict(), sort_keys=True))
    return envelope.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
