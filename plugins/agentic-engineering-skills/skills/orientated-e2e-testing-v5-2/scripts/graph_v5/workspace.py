"""V5-owned Graph-run and repair worktree boundary.

Only Git control-plane commands touch the source repository. Product commands
must use the persistent Graph-run worktree or a transient V5-owned candidate.
"""

from __future__ import annotations

import codecs
import hashlib
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Protocol

from pydantic import field_validator

from .canonical import canonical_json_bytes
from .causality import CausalCone, ClosedCausalCone
from .environment import StartRequest, WorkspaceReceipt, _repository_requirements
from .models import EnvironmentIdentity, GitTransaction, HostPreflightReceipt, RunHead, StrictModel


class WorkspaceError(RuntimeError):
    """Graph-run workspace is not safe to create, reconcile, or use."""


def _non_empty(value: str) -> str:
    if not value.strip():
        raise ValueError("must be non-empty")
    return value


def _validated_encoding_policy(value: tuple[str, ...]) -> tuple[str, ...]:
    if (
        not value
        or value[0].lower() != "utf-8"
        or any(not item.strip() for item in value)
    ):
        raise ValueError("encoding policy must begin with utf-8 and contain registered encodings")
    try:
        for encoding in value:
            codecs.lookup(encoding)
    except LookupError as exc:
        raise ValueError(
            "encoding policy must begin with utf-8 and contain registered encodings"
        ) from exc
    return value


class CandidateWorkspaceReceipt(StrictModel):
    """Durable-ready receipt for a transient candidate owned by this V5 run."""

    branch: str
    worktree_path: str
    source_repository_root: str
    graph_run_branch: str
    graph_run_worktree_path: str
    base_run_head_revision: str

    _validate_text = field_validator(
        "branch",
        "worktree_path",
        "source_repository_root",
        "graph_run_branch",
        "graph_run_worktree_path",
        "base_run_head_revision",
    )(_non_empty)


class RunHeadIntegrationReceipt(StrictModel):
    """One cherry-picked candidate patch integrated into persistent Graph-run."""

    graph_run_branch: str
    graph_run_worktree_path: str
    candidate_branch: str
    candidate_worktree_path: str
    prior_revision: str
    prior_run_head_digest: str
    patch_revision: str
    new_revision: str

    _validate_text = field_validator(
        "graph_run_branch",
        "graph_run_worktree_path",
        "candidate_branch",
        "candidate_worktree_path",
        "prior_revision",
        "prior_run_head_digest",
        "patch_revision",
        "new_revision",
    )(_non_empty)

    def new_run_head(self, environment_digest: str, fixture_digest: str):
        from .models import RunHead

        return RunHead(
            revision=self.new_revision,
            environment_digest=environment_digest,
            fixture_digest=fixture_digest,
        )


@dataclass(frozen=True, slots=True)
class _IssuedCandidateWorkspace:
    candidate: CandidateWorkspaceReceipt
    base_run_head: RunHead
    cone: CausalCone
    candidate_snapshot: bytes
    base_run_head_snapshot: bytes
    cone_digest: str
    common_git_dir: str


@dataclass(frozen=True, slots=True)
class _IssuedRunHeadIntegration:
    candidate: _IssuedCandidateWorkspace
    receipt: RunHeadIntegrationReceipt
    new_run_head: RunHead
    patch_revision: str
    receipt_snapshot: bytes
    new_run_head_snapshot: bytes


@dataclass(frozen=True, slots=True)
class _LadderAuthorityReservation:
    integration: RunHeadIntegrationReceipt
    role_output_ids: tuple[int, ...]


_LIFECYCLE_RECEIPT_LOCK = RLock()
_ISSUED_CANDIDATE_WORKSPACES: dict[int, _IssuedCandidateWorkspace] = {}
_ISSUED_RUN_HEAD_INTEGRATIONS: dict[int, _IssuedRunHeadIntegration] = {}
_CONSUMED_RUN_HEAD_INTEGRATIONS: set[int] = set()
_RESERVED_RUN_HEAD_INTEGRATIONS: dict[int, _LadderAuthorityReservation] = {}
_INTEGRATED_CANDIDATE_WORKSPACE_IDS: set[int] = set()


def _snapshot_model(model: StrictModel) -> bytes:
    """Canonical immutable copy of every Pydantic receipt field."""

    return canonical_json_bytes(model.model_dump(mode="json"))


def _require_unchanged_issued_candidate(
    candidate: object,
    issued: _IssuedCandidateWorkspace,
) -> None:
    if (
        issued.candidate is not candidate
        or not isinstance(candidate, CandidateWorkspaceReceipt)
        or issued.candidate_snapshot != _snapshot_model(candidate)
        or issued.base_run_head_snapshot != _snapshot_model(issued.base_run_head)
        or issued.cone_digest != issued.cone.digest
    ):
        raise WorkspaceError("candidate workspace receipt does not bind immutable lifecycle issuance")


def _require_unchanged_issued_integration(
    integration: object,
    issued: _IssuedRunHeadIntegration,
) -> None:
    if (
        issued.receipt is not integration
        or not isinstance(integration, RunHeadIntegrationReceipt)
        or issued.receipt_snapshot != _snapshot_model(integration)
        or issued.new_run_head_snapshot != _snapshot_model(issued.new_run_head)
    ):
        raise WorkspaceError("Run Head integration receipt does not bind immutable lifecycle issuance")


def validate_lifecycle_integration_receipts(
    candidate: object,
    integration: object,
    *,
    base_run_head: RunHead,
    closed_cone: ClosedCausalCone,
) -> RunHead:
    """Resolve exact lifecycle-owned candidate and one-patch integration evidence."""

    with _LIFECYCLE_RECEIPT_LOCK:
        issued = _ISSUED_RUN_HEAD_INTEGRATIONS.get(id(integration))
        if issued is None:
            raise WorkspaceError("Run Head integration receipt must be lifecycle-issued")
        _require_unchanged_issued_integration(integration, issued)
        _require_unchanged_issued_candidate(candidate, issued.candidate)
        if issued.candidate.candidate is not candidate:
            raise WorkspaceError("candidate workspace receipt must be lifecycle-issued")
        if id(integration) in _CONSUMED_RUN_HEAD_INTEGRATIONS:
            raise WorkspaceError("Run Head integration receipt is already consumed")
        if (
            issued.candidate.base_run_head_snapshot != _snapshot_model(base_run_head)
            or issued.candidate.cone is not closed_cone.cone
            or issued.candidate.cone_digest != closed_cone.cone.digest
            or issued.receipt.prior_revision != base_run_head.revision
            or issued.receipt.prior_run_head_digest != base_run_head.digest
            or issued.receipt.patch_revision != issued.patch_revision
            or issued.receipt.new_revision != issued.new_run_head.revision
            or issued.new_run_head
            != issued.receipt.new_run_head(
                base_run_head.environment_digest, base_run_head.fixture_digest
            )
        ):
            raise WorkspaceError("lifecycle integration receipt does not bind exact candidate, cone, and Run Heads")
        return issued.new_run_head


def consume_lifecycle_integration_receipt(
    integration: object,
    *,
    role_outputs: tuple[object, ...] = (),
) -> None:
    """Make one validated integration receipt unavailable to any retry or new controller."""

    with _LIFECYCLE_RECEIPT_LOCK:
        issued = _ISSUED_RUN_HEAD_INTEGRATIONS.get(id(integration))
        if issued is None:
            raise WorkspaceError("Run Head integration receipt must be lifecycle-issued")
        _require_unchanged_issued_integration(integration, issued)
        _require_unchanged_issued_candidate(issued.candidate.candidate, issued.candidate)
        if id(integration) in _CONSUMED_RUN_HEAD_INTEGRATIONS:
            raise WorkspaceError("Run Head integration receipt is already consumed")
        if id(integration) in _RESERVED_RUN_HEAD_INTEGRATIONS:
            raise WorkspaceError("Run Head integration receipt authority is reserved")
        if role_outputs:
            from .proof import ImportedRoleOutput, consume_issuer_registered_outputs

            if not all(isinstance(output, ImportedRoleOutput) for output in role_outputs):
                raise WorkspaceError("proof ladder role outputs must be issuer-issued")
            consume_issuer_registered_outputs(role_outputs)  # type: ignore[arg-type]
        _CONSUMED_RUN_HEAD_INTEGRATIONS.add(id(integration))


def reserve_lifecycle_integration_receipt(
    integration: object,
    *,
    role_outputs: tuple[object, ...],
) -> _LadderAuthorityReservation:
    """Reserve six fresh authorities while their single durable transition runs."""

    with _LIFECYCLE_RECEIPT_LOCK:
        issued = _ISSUED_RUN_HEAD_INTEGRATIONS.get(id(integration))
        if issued is None:
            raise WorkspaceError("Run Head integration receipt must be lifecycle-issued")
        _require_unchanged_issued_integration(integration, issued)
        _require_unchanged_issued_candidate(issued.candidate.candidate, issued.candidate)
        if id(integration) in _CONSUMED_RUN_HEAD_INTEGRATIONS:
            raise WorkspaceError("Run Head integration receipt is already consumed")
        if id(integration) in _RESERVED_RUN_HEAD_INTEGRATIONS:
            raise WorkspaceError("Run Head integration receipt authority is reserved")
        from .proof import ImportedRoleOutput, ProofLadderError, reserve_issuer_registered_outputs

        if not all(isinstance(output, ImportedRoleOutput) for output in role_outputs):
            raise WorkspaceError("proof ladder role outputs must be issuer-issued")
        try:
            role_output_ids = reserve_issuer_registered_outputs(role_outputs)  # type: ignore[arg-type]
        except ProofLadderError as error:
            raise WorkspaceError(str(error)) from error
        reservation = _LadderAuthorityReservation(
            integration=integration,  # type: ignore[arg-type]
            role_output_ids=role_output_ids,
        )
        _RESERVED_RUN_HEAD_INTEGRATIONS[id(integration)] = reservation
        return reservation


def commit_lifecycle_integration_reservation(
    reservation: _LadderAuthorityReservation,
) -> None:
    """Consume reserved authorities only after their Run Head is durable."""

    with _LIFECYCLE_RECEIPT_LOCK:
        active = _RESERVED_RUN_HEAD_INTEGRATIONS.get(id(reservation.integration))
        if active is not reservation:
            raise WorkspaceError("Run Head integration reservation is not active")
        from .proof import ProofLadderError, commit_issuer_registered_output_reservation

        try:
            commit_issuer_registered_output_reservation(reservation.role_output_ids)
        except ProofLadderError as error:
            raise WorkspaceError(str(error)) from error
        _RESERVED_RUN_HEAD_INTEGRATIONS.pop(id(reservation.integration))
        _CONSUMED_RUN_HEAD_INTEGRATIONS.add(id(reservation.integration))


def rollback_lifecycle_integration_reservation(
    reservation: _LadderAuthorityReservation,
) -> None:
    """Release every authority after a failed pre-durability store transaction."""

    with _LIFECYCLE_RECEIPT_LOCK:
        active = _RESERVED_RUN_HEAD_INTEGRATIONS.get(id(reservation.integration))
        if active is not reservation:
            raise WorkspaceError("Run Head integration reservation is not active")
        from .proof import ProofLadderError, rollback_issuer_registered_output_reservation

        try:
            rollback_issuer_registered_output_reservation(reservation.role_output_ids)
        except ProofLadderError as error:
            raise WorkspaceError(str(error)) from error
        _RESERVED_RUN_HEAD_INTEGRATIONS.pop(id(reservation.integration))


class WorktreePreflightReceipt(StrictModel):
    """Strict receipt suitable for an existing typed artifact store."""

    worktree_path: str
    source_repository_root: str
    branch: str
    run_head_revision: str
    node_executable: str
    npm_executable: str
    package_binaries: tuple[str, ...]
    fixture_path: str
    validator_path: str
    encoding_policy: tuple[str, ...]

    _validate_text = field_validator(
        "worktree_path", "source_repository_root", "branch", "run_head_revision", "node_executable", "npm_executable", "fixture_path", "validator_path"
    )(_non_empty)

    @field_validator("encoding_policy")
    @classmethod
    def _validate_encoding_policy(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _validated_encoding_policy(value)


class WorkspaceToolchainProbe(Protocol):
    """Narrow executable probe; test fixtures never need a real Node install."""

    def executable_version(self, executable: Path) -> str: ...


class LocalWorkspaceToolchainProbe:
    def executable_version(self, executable: Path) -> str:
        try:
            result = subprocess.run(
                [str(executable), "--version"],
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=10.0,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise WorkspaceError(f"cannot execute required tool {executable}") from exc
        if result.returncode != 0:
            raise WorkspaceError(f"required tool failed version probe: {executable}")
        return result.stdout.decode("utf-8", errors="strict").strip()


@dataclass(frozen=True, slots=True)
class WorktreePreflightConfig:
    fixture_relative_path: str
    validator_relative_path: str
    required_package_binaries: tuple[str, ...] = ()
    executable_search_path: tuple[Path, ...] = ()
    pathext: str | None = None
    platform_name: str | None = None
    encoding_policy: tuple[str, ...] = ("utf-8", "cp1252")

    def __post_init__(self) -> None:
        for value in (self.fixture_relative_path, self.validator_relative_path):
            path = Path(value)
            if not value or path.is_absolute() or ".." in path.parts:
                raise ValueError("fixture and validator paths must be safe relative paths")
        _validated_encoding_policy(self.encoding_policy)
        if any(not binary or Path(binary).name != binary for binary in self.required_package_binaries):
            raise ValueError("package binaries must be simple names")


@dataclass(frozen=True, slots=True)
class _RegisteredWorktree:
    path: Path
    head: str
    branch_ref: str | None


@dataclass(frozen=True, slots=True)
class _MainSnapshot:
    branch_head: str
    tree: str
    source_status: str


class GraphWorkspaceLifecycle:
    """Exact Task 4 ``WorkspaceLifecycle`` implementation.

    This object deliberately exposes no merge, rebase, push, reset, or terminal
    Graph-run cleanup operation. Exact compensation is limited to an incomplete
    recorded bootstrap transaction; candidate disposal is explicit and separate.
    """

    def __init__(
        self,
        repository_root: Path,
        *,
        preflight: WorktreePreflightConfig,
        toolchain_probe: WorkspaceToolchainProbe | None = None,
        main_branch: str = "main",
    ) -> None:
        repository = Path(repository_root)
        if not repository.is_absolute() or not repository.is_dir():
            raise WorkspaceError("repository root must be an existing absolute directory")
        self.repository_root = repository.resolve(strict=True)
        self._source_git_dir = self._source_git_directory()
        self.preflight = preflight
        self.toolchain_probe = toolchain_probe or LocalWorkspaceToolchainProbe()
        self.main_branch = main_branch
        self.git_operations: list[str] = []
        self._main_snapshot = self._capture_main_snapshot()
        self._last_preflight: WorktreePreflightReceipt | None = None
        self._candidates: dict[str, CandidateWorkspaceReceipt] = {}

    @property
    def last_preflight(self) -> WorktreePreflightReceipt:
        if self._last_preflight is None:
            raise WorkspaceError("worktree preflight has not completed")
        return self._last_preflight

    def create_or_reconcile_graph_run_workspace(
        self, transaction: GitTransaction
    ) -> WorkspaceReceipt:
        """Create one owned branch/worktree or verify its exact recovery state."""
        workspace_path = self._transaction_path(transaction)
        self._assert_main_unchanged()
        self._assert_clean_verified_base(transaction)
        registered = self._registered_worktrees()
        matches = [item for item in registered if item.path == workspace_path]
        expected_branch_ref = f"refs/heads/{transaction.branch}"
        if matches:
            if len(matches) != 1:
                raise WorkspaceError("recorded Graph-run worktree is registered more than once")
            item = matches[0]
            if item.branch_ref != expected_branch_ref or item.head != transaction.requested_base_revision:
                raise WorkspaceError("registered Graph-run worktree does not match recorded transaction")
            if not workspace_path.is_dir():
                raise WorkspaceError("registered Graph-run worktree path is unavailable")
        else:
            if workspace_path.exists():
                raise WorkspaceError("unregistered Graph-run worktree path already exists")
            if self._branch_exists(transaction.branch):
                branch_head = self._git("rev-parse", "--verify", f"refs/heads/{transaction.branch}^{{commit}}")
                if branch_head != transaction.requested_base_revision:
                    raise WorkspaceError("orphan Graph-run branch does not match verified base")
                self._git("worktree", "add", str(workspace_path), transaction.branch)
            else:
                self._git(
                    "worktree",
                    "add",
                    "-b",
                    transaction.branch,
                    str(workspace_path),
                    transaction.requested_base_revision,
                )
            self._assert_registered_exact(
                workspace_path, expected_branch_ref, transaction.requested_base_revision
            )
        self._assert_main_unchanged()
        return WorkspaceReceipt(
            transaction_id=transaction.transaction_id,
            branch=transaction.branch,
            worktree_path=str(workspace_path),
            run_head_revision=transaction.requested_base_revision,
        )

    def worktree_preflight_and_seal(
        self,
        workspace: WorkspaceReceipt,
        request: StartRequest,
        host_receipt: HostPreflightReceipt,
    ) -> EnvironmentIdentity:
        """Fail closed on materialized toolchain/fixture evidence, then return host identity."""
        del request
        worktree = Path(workspace.worktree_path).resolve(strict=True)
        self._assert_workspace_root(worktree)
        if self._git_in_workspace(worktree, "branch", "--show-current") != workspace.branch:
            raise WorkspaceError("Graph-run workspace branch differs from receipt")
        if self._git_in_workspace(worktree, "rev-parse", "HEAD") != workspace.run_head_revision:
            raise WorkspaceError("Graph-run workspace Run Head differs from receipt")
        if host_receipt.repository_root != str(self.repository_root):
            raise WorkspaceError("host receipt repository does not match workspace lifecycle")
        if host_receipt.repository_revision != workspace.run_head_revision:
            raise WorkspaceError("host receipt revision does not match Graph-run Run Head")

        required_node_major, package_manager, _, lockfile = _repository_requirements(worktree)
        if package_manager != "npm":
            raise WorkspaceError("V5 worktree requires npm")
        if required_node_major != host_receipt.required_node_major:
            raise WorkspaceError(f"workspace requires Node {required_node_major}")
        lockfile_digest = hashlib.sha256(lockfile.read_bytes()).hexdigest()
        if lockfile_digest != host_receipt.lockfile_digest:
            raise WorkspaceError("worktree lockfile differs from sealed host receipt")

        node = self._existing_file(host_receipt.node_executable, "Node executable")
        npm = resolve_executable(
            "npm",
            search_path=self.preflight.executable_search_path or (Path(host_receipt.npm_executable).parent,),
            pathext=self.preflight.pathext,
            platform_name=self.preflight.platform_name,
        )
        expected_npm = Path(host_receipt.npm_executable).resolve(strict=True)
        if npm != expected_npm:
            raise WorkspaceError("resolved npm executable differs from sealed host receipt")
        actual_node = _semver(self.toolchain_probe.executable_version(node), "Node")
        actual_npm = _semver(self.toolchain_probe.executable_version(npm), "npm")
        if actual_node != host_receipt.node_version or int(actual_node.split(".", 1)[0]) != required_node_major:
            raise WorkspaceError(f"workspace requires Node {required_node_major}")
        if actual_npm != host_receipt.npm_version:
            raise WorkspaceError("workspace npm materialization differs from sealed host receipt")
        binaries = self._assert_materialized_binaries(worktree)
        fixture = self._assert_disposable_directory(
            worktree, self.preflight.fixture_relative_path, ".graph-v5-disposable-fixture"
        )
        validator = self._assert_disposable_directory(
            worktree, self.preflight.validator_relative_path, ".graph-v5-disposable-validator"
        )
        self._last_preflight = WorktreePreflightReceipt(
            worktree_path=str(worktree),
            source_repository_root=str(self.repository_root),
            branch=workspace.branch,
            run_head_revision=workspace.run_head_revision,
            node_executable=str(node),
            npm_executable=str(npm),
            package_binaries=binaries,
            fixture_path=str(fixture),
            validator_path=str(validator),
            encoding_policy=self.preflight.encoding_policy,
        )
        self._assert_main_unchanged()
        return host_receipt.environment

    def compensate_graph_run_workspace(self, transaction: GitTransaction) -> None:
        """Remove only exact incomplete bootstrap ownership before observation."""
        workspace_path = self._transaction_path(transaction)
        expected_ref = f"refs/heads/{transaction.branch}"
        matches = [
            registered
            for registered in self._registered_worktrees()
            if registered.path == workspace_path
        ]
        if len(matches) > 1:
            raise WorkspaceError("refusing to compensate ambiguous worktree registration")
        if matches:
            registered = matches[0]
            if registered.branch_ref != expected_ref:
                raise WorkspaceError("refusing to compensate non-owned worktree")
            if registered.head != transaction.requested_base_revision:
                raise WorkspaceError("refusing to compensate Graph-run worktree at unexpected revision")
        branch_exists = self._branch_exists(transaction.branch)
        if branch_exists:
            branch_head = self._git("rev-parse", "--verify", f"refs/heads/{transaction.branch}^{{commit}}")
            if branch_head != transaction.requested_base_revision:
                raise WorkspaceError("refusing to compensate Graph-run branch at unexpected revision")
        elif matches:
            raise WorkspaceError("refusing to compensate worktree without its recorded branch")
        if matches:
            self._git("worktree", "remove", "--force", str(workspace_path))
        if branch_exists:
            self._git("branch", "-D", transaction.branch)
        self._assert_main_unchanged()

    def create_repair_candidate(
        self,
        graph_run: WorkspaceReceipt,
        *,
        branch: str,
        worktree_path: Path,
        current_run_head: RunHead | None = None,
        cone: CausalCone | None = None,
    ) -> CandidateWorkspaceReceipt:
        """Create transient candidate from current Graph-run Run Head, never main."""
        run_root = Path(graph_run.worktree_path).resolve(strict=True)
        self._assert_workspace_root(run_root)
        if self._git_in_workspace(run_root, "branch", "--show-current") != graph_run.branch:
            raise WorkspaceError("candidate source is not recorded Graph-run branch")
        run_owner = graph_run.branch.removeprefix("graph-run/")
        if not run_owner or not branch.startswith(f"graph-repair/{run_owner}/"):
            raise WorkspaceError("candidate branch is not V5-owned child of Graph-run branch")
        candidate_path = Path(worktree_path).resolve(strict=False)
        if not candidate_path.is_absolute() or candidate_path.exists():
            raise WorkspaceError("candidate worktree path must be new and absolute")
        if candidate_path == self.repository_root or candidate_path.is_relative_to(self.repository_root):
            raise WorkspaceError("candidate worktree may not be nested under source checkout")
        if self._branch_exists(branch):
            raise WorkspaceError("candidate repair branch already exists")
        run_head = self._git_in_workspace(run_root, "rev-parse", "HEAD")
        if (current_run_head is None) != (cone is None):
            raise WorkspaceError("candidate proof authority requires both current Run Head and causal cone")
        if current_run_head is not None and current_run_head.revision != run_head:
            raise WorkspaceError("candidate authority Run Head does not match persistent Graph-run")
        self._git("worktree", "add", "-b", branch, str(candidate_path), run_head)
        self._assert_registered_exact(candidate_path, f"refs/heads/{branch}", run_head)
        receipt = CandidateWorkspaceReceipt(
            branch=branch,
            worktree_path=str(candidate_path),
            source_repository_root=str(self.repository_root),
            graph_run_branch=graph_run.branch,
            graph_run_worktree_path=str(run_root),
            base_run_head_revision=run_head,
        )
        self._candidates[str(candidate_path)] = receipt
        if current_run_head is not None and cone is not None:
            with _LIFECYCLE_RECEIPT_LOCK:
                _ISSUED_CANDIDATE_WORKSPACES[id(receipt)] = _IssuedCandidateWorkspace(
                    receipt,
                    current_run_head,
                    cone,
                    _snapshot_model(receipt),
                    _snapshot_model(current_run_head),
                    cone.digest,
                    str(getattr(self, "_source_git_dir", self.repository_root)),
                )
        self._assert_main_unchanged()
        return receipt

    def discard_repair_candidate(self, candidate: CandidateWorkspaceReceipt) -> None:
        """Explicitly dispose a known V5-owned transient candidate; never Graph-run."""
        candidate_path = Path(candidate.worktree_path).resolve(strict=False)
        recorded = self._candidates.get(str(candidate_path))
        if recorded != candidate:
            raise WorkspaceError("refusing to dispose candidate without local V5 ownership receipt")
        expected_ref = f"refs/heads/{candidate.branch}"
        registered = [item for item in self._registered_worktrees() if item.path == candidate_path]
        if len(registered) != 1 or registered[0].branch_ref != expected_ref:
            raise WorkspaceError("candidate registration no longer matches V5 ownership")
        self._git("worktree", "remove", "--force", str(candidate_path))
        self._git("branch", "-D", candidate.branch)
        self._candidates.pop(str(candidate_path), None)
        with _LIFECYCLE_RECEIPT_LOCK:
            _ISSUED_CANDIDATE_WORKSPACES.pop(id(candidate), None)
        self._assert_main_unchanged()

    def integrate_repair_candidate(
        self,
        graph_run: WorkspaceReceipt,
        candidate: CandidateWorkspaceReceipt,
        *,
        current_run_head: RunHead,
    ) -> RunHeadIntegrationReceipt:
        """Cherry-pick exactly one clean candidate commit onto persistent Graph-run."""

        with _LIFECYCLE_RECEIPT_LOCK:
            issued_candidate = _ISSUED_CANDIDATE_WORKSPACES.get(id(candidate))
            if issued_candidate is not None:
                _require_unchanged_issued_candidate(candidate, issued_candidate)
                if id(candidate) in _INTEGRATED_CANDIDATE_WORKSPACE_IDS:
                    raise WorkspaceError("candidate workspace receipt is already integrated")
                if str(getattr(self, "_source_git_dir", self.repository_root)) != issued_candidate.common_git_dir:
                    raise WorkspaceError("candidate workspace common Git directory changed after issuance")
        candidate_path = Path(candidate.worktree_path).resolve(strict=True)
        recorded = self._candidates.get(str(candidate_path))
        if recorded != candidate:
            raise WorkspaceError("candidate integration requires local V5 ownership receipt")
        run_root = Path(graph_run.worktree_path).resolve(strict=True)
        self._assert_workspace_root(run_root)
        if (
            candidate.graph_run_branch != graph_run.branch
            or Path(candidate.graph_run_worktree_path).resolve(strict=True) != run_root
        ):
            raise WorkspaceError("candidate does not bind recorded persistent Graph-run")
        if self._git_in_workspace(run_root, "branch", "--show-current") != graph_run.branch:
            raise WorkspaceError("integration target is not persistent Graph-run branch")
        prior_revision = self._git_in_workspace(run_root, "rev-parse", "HEAD")
        if (
            prior_revision != candidate.base_run_head_revision
            or current_run_head.revision != prior_revision
        ):
            raise WorkspaceError("candidate base does not match current Graph-run Run Head")
        if self._git_in_workspace(candidate_path, "branch", "--show-current") != candidate.branch:
            raise WorkspaceError("candidate worktree is not its recorded V5 branch")
        candidate_status = self._git_in_workspace(
            candidate_path, "status", "--porcelain=v1", "--untracked-files=no"
        )
        candidate_diff = self._git_result(
            "diff", "--ignore-space-at-eol", "--quiet", cwd=candidate_path
        )
        if candidate_status and candidate_diff.returncode != 0:
            raise WorkspaceError(
                f"candidate evidence must be clean before single-patch integration: {candidate_status}"
            )
        patch_revision = self._git_in_workspace(candidate_path, "rev-parse", "HEAD")
        patch_count = self._git_in_workspace(
            candidate_path, "rev-list", "--count", f"{candidate.base_run_head_revision}..{patch_revision}"
        )
        if patch_count != "1":
            raise WorkspaceError("candidate integration requires exactly one patch commit")
        parents = self._git_in_workspace(candidate_path, "show", "-s", "--format=%P", patch_revision).split()
        if len(parents) != 1:
            raise WorkspaceError("candidate integration requires a non-merge patch commit")
        self._git_in_workspace(run_root, "cherry-pick", "--no-edit", patch_revision)
        new_revision = self._git_in_workspace(run_root, "rev-parse", "HEAD")
        if new_revision == prior_revision or self._git_in_workspace(run_root, "status", "--porcelain=v1", "--untracked-files=no"):
            raise WorkspaceError("single-patch integration did not produce a clean new Run Head")
        self._assert_main_unchanged()
        receipt = RunHeadIntegrationReceipt(
            graph_run_branch=graph_run.branch,
            graph_run_worktree_path=str(run_root),
            candidate_branch=candidate.branch,
            candidate_worktree_path=str(candidate_path),
            prior_revision=prior_revision,
            prior_run_head_digest=current_run_head.digest,
            patch_revision=patch_revision,
            new_revision=new_revision,
        )
        with _LIFECYCLE_RECEIPT_LOCK:
            issued_candidate = _ISSUED_CANDIDATE_WORKSPACES.get(id(candidate))
            if issued_candidate is not None and issued_candidate.candidate is candidate:
                _require_unchanged_issued_candidate(candidate, issued_candidate)
                new_run_head = receipt.new_run_head(
                    current_run_head.environment_digest, current_run_head.fixture_digest
                )
                _ISSUED_RUN_HEAD_INTEGRATIONS[id(receipt)] = _IssuedRunHeadIntegration(
                    issued_candidate,
                    receipt,
                    new_run_head,
                    patch_revision,
                    _snapshot_model(receipt),
                    _snapshot_model(new_run_head),
                )
                _INTEGRATED_CANDIDATE_WORKSPACE_IDS.add(id(candidate))
        return receipt

    def _assert_clean_verified_base(self, transaction: GitTransaction) -> None:
        resolved = self._git("rev-parse", "--verify", f"{transaction.requested_base_revision}^{{commit}}")
        if resolved != transaction.requested_base_revision:
            raise WorkspaceError("requested Graph-run base is not an exact commit revision")
        if self._git("status", "--porcelain=v1", "--untracked-files=all"):
            raise WorkspaceError("source checkout must be clean before Graph-run worktree creation")

    def _capture_main_snapshot(self) -> _MainSnapshot:
        return _MainSnapshot(
            branch_head=self._git("rev-parse", "--verify", f"refs/heads/{self.main_branch}^{{commit}}"),
            tree=self._git("rev-parse", "--verify", f"refs/heads/{self.main_branch}^{{tree}}"),
            source_status=self._git("status", "--porcelain=v1", "--untracked-files=all"),
        )

    def _assert_main_unchanged(self) -> None:
        if self._capture_main_snapshot() != self._main_snapshot:
            raise WorkspaceError("main/source snapshot drifted during Graph-run workspace operation")

    def _transaction_path(self, transaction: GitTransaction) -> Path:
        path = Path(transaction.worktree_path)
        if not path.is_absolute():
            raise WorkspaceError("recorded Graph-run worktree path must be absolute")
        return path.resolve(strict=False)

    def _registered_worktrees(self) -> tuple[_RegisteredWorktree, ...]:
        records: list[_RegisteredWorktree] = []
        path: Path | None = None
        head = ""
        branch: str | None = None
        for line in (*self._git("worktree", "list", "--porcelain").splitlines(), ""):
            if line.startswith("worktree "):
                path = Path(line.removeprefix("worktree ")).resolve(strict=False)
            elif line.startswith("HEAD "):
                head = line.removeprefix("HEAD ")
            elif line.startswith("branch "):
                branch = line.removeprefix("branch ")
            elif not line and path is not None:
                records.append(_RegisteredWorktree(path=path, head=head, branch_ref=branch))
                path, head, branch = None, "", None
        return tuple(records)

    def _assert_registered_exact(self, path: Path, branch_ref: str, head: str) -> None:
        matches = [item for item in self._registered_worktrees() if item.path == path]
        if len(matches) != 1 or matches[0].branch_ref != branch_ref or matches[0].head != head:
            raise WorkspaceError("created worktree cannot be proven bound to recorded branch and Run Head")

    def _assert_workspace_root(self, workspace: Path) -> None:
        root = Path(self._git_in_workspace(workspace, "rev-parse", "--show-toplevel")).resolve(strict=True)
        if root != workspace:
            raise WorkspaceError("product command root must be an owned worktree root")
        if root == self.repository_root:
            raise WorkspaceError("main/source checkout cannot be a Graph product command root")

    def _assert_materialized_binaries(self, worktree: Path) -> tuple[str, ...]:
        modules = worktree / "node_modules"
        binaries = modules / ".bin"
        if not modules.is_dir():
            raise WorkspaceError("node_modules is not materialized")
        if not binaries.is_dir():
            raise WorkspaceError("partial node_modules/.bin is unavailable")
        resolved: list[str] = []
        for binary in self.preflight.required_package_binaries:
            try:
                path = resolve_executable(
                    binary,
                    search_path=(binaries,),
                    pathext=self.preflight.pathext,
                    platform_name=self.preflight.platform_name,
                )
            except WorkspaceError as exc:
                raise WorkspaceError(f"partial node_modules/.bin is missing required binary: {binary}")
            try:
                version_output = self.toolchain_probe.executable_version(path)
            except (OSError, WorkspaceError) as exc:
                raise WorkspaceError(
                    f"partial node_modules/.bin binary is not executable: {binary}"
                ) from exc
            if not version_output.strip():
                raise WorkspaceError(
                    f"partial node_modules/.bin binary is not executable: {binary}"
                )
            resolved.append(str(path))
        return tuple(resolved)

    def _assert_disposable_directory(self, worktree: Path, relative: str, marker: str) -> Path:
        path = (worktree / relative).resolve(strict=True)
        if not path.is_relative_to(worktree) or not path.is_dir() or not (path / marker).is_file():
            raise WorkspaceError("fixture or validator environment is not a marked disposable workspace directory")
        return path

    def _existing_file(self, raw: str, description: str) -> Path:
        path = Path(raw)
        if not path.is_absolute() or not path.is_file():
            raise WorkspaceError(f"{description} is not materialized")
        return path.resolve(strict=True)

    def _branch_exists(self, branch: str) -> bool:
        result = self._git_result("show-ref", "--verify", "--quiet", f"refs/heads/{branch}")
        if result.returncode in {0, 1}:
            return result.returncode == 0
        raise WorkspaceError("cannot verify Graph-run branch ownership")

    def _git_in_workspace(self, workspace: Path, *args: str) -> str:
        return self._git(*args, cwd=workspace)

    def _git(self, *args: str, cwd: Path | None = None) -> str:
        result = self._git_result(*args, cwd=cwd)
        if result.returncode != 0:
            diagnostic = (result.stderr or result.stdout).decode("utf-8", errors="replace").strip()
            raise WorkspaceError(f"git {' '.join(args)} failed: {diagnostic}")
        return result.stdout.decode("utf-8", errors="strict").strip()

    def _git_result(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[bytes]:
        self.git_operations.append(args[0])
        environment = os.environ.copy()
        environment["GIT_CONFIG_NOSYSTEM"] = "1"
        environment["GIT_CONFIG_GLOBAL"] = os.devnull
        for key in tuple(environment):
            if key == "GIT_CONFIG_COUNT" or key.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")):
                environment.pop(key)
        try:
            if cwd is None:
                command = [
                    "git",
                    f"--git-dir={self._source_git_dir}",
                    f"--work-tree={self.repository_root}",
                    *args,
                ]
                command_cwd = self.repository_root.parent
            else:
                command = ["git", *args]
                command_cwd = cwd
            return subprocess.run(
                command,
                cwd=command_cwd,
                env=environment,
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=20.0,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise WorkspaceError(f"git {' '.join(args)} could not complete") from exc

    def _source_git_directory(self) -> Path:
        dot_git = self.repository_root / ".git"
        if dot_git.is_dir():
            return dot_git.resolve(strict=True)
        if dot_git.is_file():
            value = dot_git.read_text(encoding="utf-8").strip()
            if value.startswith("gitdir: "):
                candidate = (dot_git.parent / value.removeprefix("gitdir: ")).resolve(strict=True)
                if candidate.is_dir():
                    return candidate
        raise WorkspaceError("repository root does not expose a usable Git directory")


def resolve_executable(
    name: str,
    *,
    search_path: tuple[Path, ...],
    pathext: str | None = None,
    platform_name: str | None = None,
) -> Path:
    """Resolve explicit executable paths without shell interpolation or PATH mutation."""
    if not name or Path(name).name != name:
        raise WorkspaceError("executable name must be a simple command name")
    windows = (platform_name or os.name).lower() in {"windows", "nt"}
    extensions = ("",)
    if windows and not Path(name).suffix:
        extensions = tuple(
            extension for extension in (pathext or os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD")).split(";") if extension
        )
    for directory in search_path:
        parent = Path(directory)
        for extension in extensions:
            candidate = parent / f"{name}{extension}"
            if candidate.is_file():
                return candidate.resolve(strict=True)
    raise WorkspaceError(f"required executable is unavailable: {name}")


def _semver(raw: str, executable: str) -> str:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", raw.strip())
    if match is None:
        raise WorkspaceError(f"{executable} version is not strict semantic version")
    return ".".join(match.groups())
