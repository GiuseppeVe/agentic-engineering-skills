"""Host evidence and crash-safe V5 bootstrap transaction.

Owns only pre-Git safety and durable ordering. Task 5 supplies actual isolated
workspace/toolchain operations through ``WorkspaceLifecycle``.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from pydantic import field_validator

from .canonical import digest_for
from .models import (
    BootstrapIntent,
    EnvironmentIdentity,
    GitTransaction,
    HostPreflightReceipt,
    RunHead,
    StrictModel,
)
from .store import SimulatedCrash, TransactionalRunStore

_HOST_PROBE_TIMEOUT_SECONDS = 10.0


class EnvironmentPreflightError(RuntimeError):
    """Repository or host evidence cannot safely admit a Graph run."""


class StartTransactionError(RuntimeError):
    """Durable start transaction cannot advance safely."""


class SimulatedStartCrash(SimulatedCrash):
    """Deterministic interruption seam used only by start-atom tests."""


class EnvironmentSnapshot(StrictModel):
    """Sealed real-system identity consumed by every V5.2 operation and replay."""

    adapter_manifest_digest: str
    target_identity_digest: str
    lease_receipt_digests: tuple[str, ...]
    egress_receipt_digest: str | None
    evidence_policy_digest: str

    @field_validator(
        "adapter_manifest_digest",
        "target_identity_digest",
        "evidence_policy_digest",
    )
    @classmethod
    def _required_digests_are_exact(cls, value: str) -> str:
        if re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("environment snapshot digest must be lowercase SHA-256 hexadecimal")
        return value

    @field_validator("egress_receipt_digest")
    @classmethod
    def _optional_egress_digest_is_exact(cls, value: str | None) -> str | None:
        if value is not None and re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise ValueError("egress receipt digest must be lowercase SHA-256 hexadecimal")
        return value

    @field_validator("lease_receipt_digests")
    @classmethod
    def _lease_receipts_are_exact_and_distinct(
        cls, values: tuple[str, ...]
    ) -> tuple[str, ...]:
        if any(re.fullmatch(r"[0-9a-f]{64}", value) is None for value in values):
            raise ValueError("lease receipt digest must be lowercase SHA-256 hexadecimal")
        if len(values) != len(set(values)):
            raise ValueError("environment snapshot may not duplicate lease receipts")
        return values

    @property
    def digest(self) -> str:
        return digest_for("environment-snapshot", self)

    @classmethod
    def from_admitted_authority(
        cls,
        *,
        manifest: object,
        target_identity_digest: str,
        supervisor_receipts: tuple[object, ...],
        egress_receipt: object | None,
    ) -> "EnvironmentSnapshot":
        """Build a snapshot only from typed facts persisted with the admission."""

        from .adapters.manifest import AdapterManifest
        from .models import EgressGateReceipt, SupervisorAuthorityReceipt

        if not isinstance(manifest, AdapterManifest):
            raise EnvironmentPreflightError("environment snapshot requires admitted AdapterManifest")
        if not all(isinstance(item, SupervisorAuthorityReceipt) for item in supervisor_receipts):
            raise EnvironmentPreflightError("environment snapshot requires typed supervisor authority receipts")
        if egress_receipt is not None and not isinstance(egress_receipt, EgressGateReceipt):
            raise EnvironmentPreflightError("environment snapshot requires typed egress gate receipt")
        typed_supervisors = tuple(supervisor_receipts)
        typed_egress = egress_receipt
        _validate_admitted_receipt_chain(
            manifest,
            target_identity_digest=target_identity_digest,
            supervisor_receipts=typed_supervisors,
            egress_receipt=typed_egress,
        )
        return cls(
            adapter_manifest_digest=manifest.digest,
            target_identity_digest=target_identity_digest,
            lease_receipt_digests=tuple(item.digest for item in typed_supervisors),
            egress_receipt_digest=None if typed_egress is None else typed_egress.digest,
            evidence_policy_digest=manifest.evidence.redaction_policy_digest,
        )

    @classmethod
    def for_fixture_manifest(
        cls, *, manifest: object, fixture_digest: str
    ) -> "EnvironmentSnapshot":
        """Project fixture identity through the same strict V5.2 snapshot type."""

        from .adapters.manifest import AdapterManifest

        if not isinstance(manifest, AdapterManifest) or manifest.mode != "fixture":
            raise EnvironmentPreflightError("fixture snapshot requires fixture AdapterManifest")
        return cls.from_admitted_authority(
            manifest=manifest,
            target_identity_digest=fixture_digest,
            supervisor_receipts=(),
            egress_receipt=None,
        )


def _validate_admitted_receipt_chain(
    manifest: object,
    *,
    target_identity_digest: str,
    supervisor_receipts: tuple[object, ...],
    egress_receipt: object | None,
) -> None:
    """Reject foreign or opaque environment authority before a snapshot exists."""

    from .adapters.manifest import AdapterManifest
    from .models import EgressGateReceipt, SupervisorAuthorityReceipt

    if not isinstance(manifest, AdapterManifest):
        raise EnvironmentPreflightError("receipt chain requires admitted AdapterManifest")
    if not isinstance(target_identity_digest, str) or re.fullmatch(r"[0-9a-f]{64}", target_identity_digest) is None:
        raise EnvironmentPreflightError("receipt chain requires exact target identity digest")
    if not all(isinstance(item, SupervisorAuthorityReceipt) for item in supervisor_receipts):
        raise EnvironmentPreflightError("receipt chain requires typed supervisor authority receipts")
    if any(
        item.adapter_manifest_digest != manifest.digest
        or item.target_identity_digest != target_identity_digest
        for item in supervisor_receipts
    ):
        raise EnvironmentPreflightError("supervisor receipt does not bind admitted manifest and target")
    if len({item.run_id for item in supervisor_receipts}) > 1:
        raise EnvironmentPreflightError("supervisor receipts must bind one exact run")
    if manifest.egress.hosts:
        if not isinstance(egress_receipt, EgressGateReceipt):
            raise EnvironmentPreflightError("admitted egress requires typed egress gate receipt")
        if (
            egress_receipt.adapter_manifest_digest != manifest.digest
            or egress_receipt.target_identity_digest != target_identity_digest
            or egress_receipt.allowed_hosts != manifest.egress.hosts
            or egress_receipt.allowed_protocols != ("https",)
            or (
                not manifest.target.is_loopback
                and manifest.target.host not in egress_receipt.allowed_hosts
            )
            or egress_receipt.issued_receipt_digest
            != digest_for("egress-enforcement-receipt", manifest.egress.enforcement_receipt)
        ):
            raise EnvironmentPreflightError(
                "egress receipt digest does not bind admitted exact egress scope"
            )
    elif egress_receipt is not None:
        raise EnvironmentPreflightError("deny-by-default egress cannot carry a receipt")


class HostPreflightProbe(Protocol):
    """Narrow host boundary. Default implementation runs real local probes."""

    def executable_version(self, executable: str) -> tuple[str, str]: ...

    def git(self, repository_root: Path, *args: str) -> str: ...

    def branch_exists(self, repository_root: Path, branch: str) -> bool: ...

    def registered_worktree_paths(self, repository_root: Path) -> tuple[Path, ...]: ...

    def long_paths_enabled(self) -> bool: ...

    def platform_name(self) -> str: ...

    def host_values(self) -> tuple[str, str, str]: ...


class LocalHostPreflightProbe:
    """Local-only command probe; neither shell interpolation nor Git mutation."""

    def executable_version(self, executable: str) -> tuple[str, str]:
        candidates = ("npm.CMD", "npm.cmd", "npm") if executable == "npm" else (executable,)
        resolved = next((shutil.which(item) for item in candidates if shutil.which(item)), None)
        if resolved is None:
            raise EnvironmentPreflightError(f"required executable is unavailable: {executable}")
        try:
            result = subprocess.run(
                [resolved, "--version"],
                capture_output=True,
                check=False,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=_HOST_PROBE_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise EnvironmentPreflightError(f"{executable} --version timed out") from exc
        except OSError as exc:
            raise EnvironmentPreflightError(f"cannot execute {executable}: {exc}") from exc
        if result.returncode != 0:
            raise EnvironmentPreflightError(
                f"{executable} --version failed: {(result.stderr or result.stdout).strip()}"
            )
        version = result.stdout.strip()
        if not version:
            raise EnvironmentPreflightError(f"{executable} --version produced no version")
        return str(Path(resolved).resolve()), version

    def git(self, repository_root: Path, *args: str) -> str:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=repository_root,
                capture_output=True,
                check=False,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=_HOST_PROBE_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise EnvironmentPreflightError(f"git {' '.join(args)} timed out") from exc
        if result.returncode != 0:
            raise EnvironmentPreflightError(
                f"git {' '.join(args)} failed: {(result.stderr or result.stdout).strip()}"
            )
        return result.stdout.strip()

    def branch_exists(self, repository_root: Path, branch: str) -> bool:
        try:
            result = subprocess.run(
                ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
                cwd=repository_root,
                capture_output=True,
                check=False,
                timeout=_HOST_PROBE_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise EnvironmentPreflightError("Git branch verification timed out") from exc
        if result.returncode in {0, 1}:
            return result.returncode == 0
        raise EnvironmentPreflightError("cannot verify candidate Graph-run branch safety")

    def registered_worktree_paths(self, repository_root: Path) -> tuple[Path, ...]:
        output = self.git(repository_root, "worktree", "list", "--porcelain")
        paths: list[Path] = []
        for line in output.splitlines():
            if line.startswith("worktree "):
                paths.append(Path(line.removeprefix("worktree ")).resolve(strict=False))
        return tuple(paths)

    def long_paths_enabled(self) -> bool:
        if os.name != "nt":
            return True
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SYSTEM\CurrentControlSet\Control\FileSystem",
            ) as key:
                value, _ = winreg.QueryValueEx(key, "LongPathsEnabled")
        except OSError:
            return False
        return value == 1

    def platform_name(self) -> str:
        return platform.system()

    def host_values(self) -> tuple[str, str, str]:
        return (platform.system(), platform.release(), platform.machine())


@dataclass(frozen=True, slots=True)
class HostPreflightConfig:
    path_reserve_chars: int
    path_limit_chars: int = 260
    volatile_roots: tuple[Path, ...] = ()
    volatile_environment_roots: tuple[Path, ...] | None = None

    def __post_init__(self) -> None:
        if self.path_reserve_chars < 0:
            raise ValueError("path_reserve_chars must be non-negative")
        if self.path_limit_chars < 1:
            raise ValueError("path_limit_chars must be positive")


class WorkspaceReceipt(StrictModel):
    transaction_id: str
    branch: str
    worktree_path: str
    run_head_revision: str

    _validate_text = field_validator(
        "transaction_id", "branch", "worktree_path", "run_head_revision"
    )(lambda value: _non_empty_text(value))


class WorkspaceLifecycle(Protocol):
    """Task 5 implements this exact owned-workspace boundary."""

    def create_or_reconcile_graph_run_workspace(
        self, transaction: GitTransaction
    ) -> WorkspaceReceipt: ...

    def worktree_preflight_and_seal(
        self,
        workspace: WorkspaceReceipt,
        request: "StartRequest",
        host_receipt: HostPreflightReceipt,
    ) -> EnvironmentIdentity: ...

    def compensate_graph_run_workspace(self, transaction: GitTransaction) -> None: ...


StartCrashPoint = Literal[
    "bootstrap_intent",
    "host_preflight",
    "git_transaction",
    "workspace_created",
    "git_created",
    "git_reconciled",
    "environment_sealed",
    "run_head_recorded",
    "run_started",
]


@dataclass(frozen=True, slots=True)
class StartRequest:
    repository_root: Path
    requested_base_revision: str
    candidate_branch: str
    candidate_worktree_path: Path
    durable_store_root: Path
    host_config: HostPreflightConfig
    host_probe: HostPreflightProbe
    workspace_lifecycle: WorkspaceLifecycle
    crash_after: StartCrashPoint | None = None


@dataclass(frozen=True, slots=True)
class StartResult:
    run_id: str
    intent: BootstrapIntent
    host_receipt: HostPreflightReceipt
    transaction: GitTransaction
    workspace: WorkspaceReceipt
    environment: EnvironmentIdentity
    run_head: RunHead


def host_preflight(
    intent: BootstrapIntent,
    *,
    repository_root: Path,
    durable_store_root: Path,
    config: HostPreflightConfig,
    probe: HostPreflightProbe | None = None,
) -> HostPreflightReceipt:
    """Collect repository/host evidence before any Git side effect occurs."""

    probe = probe or LocalHostPreflightProbe()
    repository = _canonical_existing_directory(repository_root, "repository root")
    durable_store = _canonical_existing_directory(durable_store_root, "durable store root")
    worktree = _canonical_prospective_path(Path(intent.candidate_worktree_path), "candidate worktree path")
    _assert_not_volatile(durable_store, config)
    _assert_safe_branch(intent.candidate_branch)
    if worktree == repository or worktree.is_relative_to(repository):
        raise EnvironmentPreflightError("candidate worktree must not be nested in repository")
    if worktree.exists():
        raise EnvironmentPreflightError("candidate worktree path already exists")
    longest_relative_path = max(
        (
            len(str(path.relative_to(repository)))
            for path in repository.rglob("*")
            if ".git" not in path.relative_to(repository).parts
        ),
        default=0,
    )
    projected_length = (
        len(str(worktree))
        + (1 if longest_relative_path else 0)
        + longest_relative_path
        + config.path_reserve_chars
    )
    long_paths_enabled = probe.long_paths_enabled()
    if (
        probe.platform_name().lower() == "windows"
        and not long_paths_enabled
        and projected_length >= config.path_limit_chars
    ):
        raise EnvironmentPreflightError("prospective worktree path exceeds Windows path limit")

    required_node_major, package_manager, required_package_manager_version, lockfile = (
        _repository_requirements(repository)
    )
    node_path, raw_node_version = probe.executable_version("node")
    node_version = _normalise_semver(raw_node_version, "Node")
    node_major = int(node_version.split(".", 1)[0])
    if node_major != required_node_major:
        raise EnvironmentPreflightError(
            f"repository requires Node {required_node_major}; resolved Node {node_major}"
        )
    npm_path, raw_npm_version = probe.executable_version("npm")
    npm_version = _normalise_semver(raw_npm_version, "npm")
    if required_package_manager_version is not None and npm_version != required_package_manager_version:
        raise EnvironmentPreflightError(
            f"repository requires npm {required_package_manager_version}; resolved npm {npm_version}"
        )
    if probe.branch_exists(repository, intent.candidate_branch):
        raise EnvironmentPreflightError("candidate Graph-run branch already exists")
    if worktree in {
        item.resolve(strict=False)
        for item in probe.registered_worktree_paths(repository)
    }:
        raise EnvironmentPreflightError("candidate worktree path is already registered")

    revision = probe.git(repository, "rev-parse", "--verify", f"{intent.requested_base_revision}^{{commit}}")
    if revision != intent.requested_base_revision:
        raise EnvironmentPreflightError("requested base revision is not a verified exact commit")
    head_revision = probe.git(repository, "rev-parse", "--verify", "HEAD^{commit}")
    if head_revision != revision:
        raise EnvironmentPreflightError("checkout HEAD does not match requested base revision")
    if probe.git(repository, "status", "--porcelain"):
        raise EnvironmentPreflightError("repository base is dirty")
    git_filemode = probe.git(repository, "config", "--get", "core.filemode").lower()
    if probe.platform_name().lower() == "windows" and git_filemode != "false":
        raise EnvironmentPreflightError("Git/NTFS filemode mismatch")

    lockfile_digest = hashlib.sha256(lockfile.read_bytes()).hexdigest()
    host_fingerprint = digest_for(
        "host-preflight",
        {
            "host": probe.host_values(),
            "git_filemode": git_filemode,
            "long_paths_enabled": long_paths_enabled,
            "node_executable": node_path,
            "npm_executable": npm_path,
            "platform": probe.platform_name(),
        },
    )
    environment = EnvironmentIdentity(
        repository_revision=revision,
        runtime=f"node-{node_version}",
        package_manager=f"{package_manager}-{npm_version}",
        lockfile_digest=lockfile_digest,
        host_fingerprint=host_fingerprint,
    )
    return HostPreflightReceipt(
        transaction_id=intent.transaction_id,
        repository_root=str(repository),
        repository_revision=revision,
        requested_base_revision=intent.requested_base_revision,
        candidate_worktree_path=str(worktree),
        durable_store_root=str(durable_store),
        required_node_major=required_node_major,
        node_executable=node_path,
        node_version=node_version,
        npm_executable=npm_path,
        npm_version=npm_version,
        package_manager=package_manager,
        lockfile_path=str(lockfile),
        lockfile_digest=lockfile_digest,
        projected_path_length=projected_length,
        path_reserve_chars=config.path_reserve_chars,
        long_paths_enabled=long_paths_enabled,
        git_filemode=git_filemode,
        host_fingerprint=host_fingerprint,
        environment=environment,
    )


def start_new_run(request: StartRequest, store: TransactionalRunStore) -> StartResult:
    """Advance resumable start. Recovery uses only durable recorded ownership."""

    if request.durable_store_root.resolve(strict=False) != store.root:
        raise StartTransactionError(
            "request durable store root does not match capability-bound store"
        )
    state = store.read_state()
    if (
        state.limits.active_version != 1
        or len(state.limits.versions) != 1
        or state.limits.amendments
    ):
        raise StartTransactionError("start requires sealed initial Run Limits version 1")
    if state.mode not in {"boot", "running"}:
        raise StartTransactionError(f"run cannot start from mode {state.mode}")
    intent = store.record_bootstrap_intent(
        BootstrapIntent(
            run_id=state.run_id,
            transaction_id=_transaction_id(state.run_id, request),
            requested_base_revision=request.requested_base_revision,
            candidate_branch=request.candidate_branch,
            candidate_worktree_path=str(request.candidate_worktree_path.resolve(strict=False)),
            compensation_plan=("remove-exact-worktree", "delete-exact-branch"),
        )
    )
    _crash_if_requested(request, "bootstrap_intent")

    host = _record_or_recover_host_receipt(intent, request, store)
    _crash_if_requested(request, "host_preflight")
    transaction = store.record_git_transaction(
        GitTransaction(
            transaction_id=intent.transaction_id,
            requested_base_revision=intent.requested_base_revision,
            branch=intent.candidate_branch,
            worktree_path=intent.candidate_worktree_path,
            status="prepared",
        )
    )
    _crash_if_requested(request, "git_transaction")
    if transaction.status not in {"prepared", "created", "reconciled"}:
        raise StartTransactionError(
            f"recorded Git transaction cannot start: {transaction.status}"
        )

    try:
        if transaction.status == "prepared":
            workspace = request.workspace_lifecycle.create_or_reconcile_graph_run_workspace(transaction)
            _assert_workspace_matches(transaction, workspace)
            _crash_if_requested(request, "workspace_created")
            transaction = store.record_git_transaction_status(transaction.transaction_id, "created")
            _crash_if_requested(request, "git_created")
        else:
            workspace = request.workspace_lifecycle.create_or_reconcile_graph_run_workspace(transaction)
            _assert_workspace_matches(transaction, workspace)
        if transaction.status == "created":
            workspace = request.workspace_lifecycle.create_or_reconcile_graph_run_workspace(transaction)
            _assert_workspace_matches(transaction, workspace)
            transaction = store.record_git_transaction_status(transaction.transaction_id, "reconciled")
            _crash_if_requested(request, "git_reconciled")
        if transaction.status != "reconciled":
            raise StartTransactionError(f"recorded Git transaction cannot start: {transaction.status}")
    except SimulatedStartCrash:
        raise
    except Exception:
        _compensate_exact_transaction(request, store, transaction)
        raise

    environment = store.read_state().facts.environment
    if environment is None:
        try:
            environment = request.workspace_lifecycle.worktree_preflight_and_seal(workspace, request, host)
        except Exception:
            _compensate_exact_transaction(request, store, transaction)
            raise
        if not isinstance(environment, EnvironmentIdentity):
            _compensate_exact_transaction(request, store, transaction)
            raise StartTransactionError("worktree preflight did not return EnvironmentIdentity")
        if environment != host.environment:
            _compensate_exact_transaction(request, store, transaction)
            raise StartTransactionError(
                "worktree preflight EnvironmentIdentity does not match host-derived identity"
            )
        store.seal_environment(intent.run_id, environment)
        _crash_if_requested(request, "environment_sealed")

    state = store.read_state()
    run_head = store.record_initial_run_head(
        intent.run_id,
        RunHead(
            revision=workspace.run_head_revision,
            environment_digest=environment.digest,
            fixture_digest=state.fixture_intent_digest,
        ),
    )
    _crash_if_requested(request, "run_head_recorded")
    running = store.enter_running(intent.run_id)
    _crash_if_requested(request, "run_started")
    final_transaction = store.read_state().facts.git_transaction
    if final_transaction is None or running.facts.environment is None:
        raise StartTransactionError("start transaction did not seal required facts")
    return StartResult(
        run_id=running.run_id,
        intent=intent,
        host_receipt=host,
        transaction=final_transaction,
        workspace=workspace,
        environment=running.facts.environment,
        run_head=run_head,
    )


def _record_or_recover_host_receipt(
    intent: BootstrapIntent, request: StartRequest, store: TransactionalRunStore
) -> HostPreflightReceipt:
    recorded = store.read_latest_fact(
        kind="host_preflighted",
        fact_id=intent.transaction_id,
        domain="host-preflight",
        model_type=HostPreflightReceipt,
    )
    if recorded is not None:
        if not isinstance(recorded, HostPreflightReceipt):
            raise StartTransactionError("recorded host receipt has invalid type")
        _assert_host_receipt_matches_request(recorded, intent, request, store)
        return recorded
    receipt = host_preflight(
        intent,
        repository_root=request.repository_root,
        durable_store_root=request.durable_store_root,
        config=request.host_config,
        probe=request.host_probe,
    )
    if receipt.transaction_id != intent.transaction_id:
        raise StartTransactionError("host receipt is not bound to Bootstrap Intent")
    store.record_host_preflight(intent, receipt)
    return receipt


def _assert_host_receipt_matches_request(
    receipt: HostPreflightReceipt,
    intent: BootstrapIntent,
    request: StartRequest,
    store: TransactionalRunStore,
) -> None:
    repository = _canonical_existing_directory(request.repository_root, "repository root")
    durable_store = _canonical_existing_directory(
        request.durable_store_root, "durable store root"
    )
    worktree = _canonical_prospective_path(
        request.candidate_worktree_path, "candidate worktree path"
    )
    if receipt.repository_root != str(repository):
        raise StartTransactionError("recorded host receipt does not match repository root")
    if (
        receipt.transaction_id != intent.transaction_id
        or receipt.requested_base_revision != request.requested_base_revision
        or receipt.candidate_worktree_path != str(worktree)
        or receipt.durable_store_root != str(durable_store)
        or durable_store != store.root
    ):
        raise StartTransactionError("recorded host receipt does not match start request")


def _compensate_exact_transaction(
    request: StartRequest, store: TransactionalRunStore, transaction: GitTransaction
) -> None:
    if transaction.status in {"compensated", "failed"}:
        return
    try:
        request.workspace_lifecycle.compensate_graph_run_workspace(transaction)
    except Exception as exc:
        store.record_git_transaction_status(transaction.transaction_id, "failed")
        raise StartTransactionError("exact transaction compensation failed") from exc
    store.record_git_transaction_status(transaction.transaction_id, "compensated")


def _assert_workspace_matches(transaction: GitTransaction, workspace: WorkspaceReceipt) -> None:
    if (
        workspace.transaction_id != transaction.transaction_id
        or workspace.branch != transaction.branch
        or Path(workspace.worktree_path).resolve(strict=False)
        != Path(transaction.worktree_path).resolve(strict=False)
    ):
        raise StartTransactionError("workspace receipt is not bound to recorded Git transaction")
    if workspace.run_head_revision != transaction.requested_base_revision:
        raise StartTransactionError(
            "workspace Run Head does not match recorded requested base revision"
        )


def _crash_if_requested(request: StartRequest, point: StartCrashPoint) -> None:
    if request.crash_after == point:
        raise SimulatedStartCrash(f"injected crash after durable {point}")


def _transaction_id(run_id: str, request: StartRequest) -> str:
    return digest_for(
        "bootstrap-transaction-id",
        {
            "run_id": run_id,
            "base": request.requested_base_revision,
            "branch": request.candidate_branch,
            "worktree": str(request.candidate_worktree_path.resolve(strict=False)),
        },
    )


def _repository_requirements(repository: Path) -> tuple[int, str, str | None, Path]:
    sources: list[tuple[str, int]] = []
    nvmrc = repository / ".nvmrc"
    if nvmrc.exists():
        sources.append((".nvmrc", _node_major(nvmrc.read_text(encoding="utf-8"), ".nvmrc")))
    package_json = repository / "package.json"
    metadata: dict[str, object] = {}
    if package_json.exists():
        try:
            decoded = json.loads(package_json.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise EnvironmentPreflightError("package.json is unreadable") from exc
        if not isinstance(decoded, dict):
            raise EnvironmentPreflightError("package.json must be an object")
        metadata = decoded
        engines = metadata.get("engines")
        if isinstance(engines, dict) and isinstance(engines.get("node"), str):
            sources.append(("package.json engines.node", _node_major(engines["node"], "engines.node")))
    if not sources:
        raise EnvironmentPreflightError("repository does not declare a Node requirement")
    majors = {major for _, major in sources}
    if len(majors) != 1:
        detail = ", ".join(f"{source}={major}" for source, major in sources)
        raise EnvironmentPreflightError(f"repository Node requirements conflict: {detail}")
    package_manager = metadata.get("packageManager")
    required_package_manager_version = None
    if package_manager is not None and (
        not isinstance(package_manager, str) or not package_manager.startswith("npm@")
    ):
        raise EnvironmentPreflightError("V5.0 requires npm package-manager metadata")
    if isinstance(package_manager, str):
        required_package_manager_version = _normalise_semver(package_manager.removeprefix("npm@"), "npm")
    lockfile = next(
        (repository / item for item in ("package-lock.json", "npm-shrinkwrap.json") if (repository / item).is_file()),
        None,
    )
    if lockfile is None:
        raise EnvironmentPreflightError("repository npm lockfile is unavailable")
    return majors.pop(), "npm", required_package_manager_version, lockfile.resolve()


def _node_major(raw: str, source: str) -> int:
    match = re.search(r"(?:^|[^0-9])(\d{1,3})(?:\D|$)", raw.strip())
    if match is None:
        raise EnvironmentPreflightError(f"{source} does not declare a usable Node major")
    return int(match.group(1))


def _normalise_semver(raw: str, executable: str) -> str:
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", raw.strip())
    if match is None:
        raise EnvironmentPreflightError(f"{executable} version is not a strict semantic version")
    return ".".join(match.groups())


def _canonical_existing_directory(path: Path, description: str) -> Path:
    original = Path(path)
    if not original.is_absolute() or not original.exists() or not original.is_dir():
        raise EnvironmentPreflightError(f"{description} must be an existing absolute directory")
    resolved = original.resolve(strict=True)
    if resolved != original.absolute():
        raise EnvironmentPreflightError(f"{description} may not resolve through a symlink")
    return resolved


def _canonical_prospective_path(path: Path, description: str) -> Path:
    if not path.is_absolute():
        raise EnvironmentPreflightError(f"{description} must be absolute")
    resolved = path.resolve(strict=False)
    if resolved != path.absolute():
        raise EnvironmentPreflightError(f"{description} may not resolve through a symlink")
    return resolved


def _assert_not_volatile(path: Path, config: HostPreflightConfig) -> None:
    roots = [Path(root).resolve(strict=False) for root in config.volatile_roots]
    if config.volatile_environment_roots is None:
        for variable in ("DSH", "TEMP", "TMP"):
            raw = os.environ.get(variable)
            if raw:
                roots.append(Path(raw).resolve(strict=False))
    else:
        roots.extend(Path(root).resolve(strict=False) for root in config.volatile_environment_roots)
    if any(path == root or path.is_relative_to(root) for root in roots):
        raise EnvironmentPreflightError("durable store root is under a volatile DSH/TEMP path")


def _assert_safe_branch(branch: str) -> None:
    components = branch.split("/")
    if (
        not branch.startswith("graph-run/")
        or branch == "graph-run/"
        or branch.endswith(("/", ".", ".lock"))
        or any(component.startswith(".") or component.endswith(".lock") for component in components)
        or any(ord(character) < 32 or ord(character) == 127 for character in branch)
        or any(token in branch for token in (" ", "..", "//", "@{", "\\", "~", "^", ":", "?", "*", "["))
    ):
        raise EnvironmentPreflightError("candidate branch is unsafe for Graph-run isolation")


def _non_empty_text(value: str) -> str:
    if not value.strip():
        raise ValueError("must be non-empty")
    return value
