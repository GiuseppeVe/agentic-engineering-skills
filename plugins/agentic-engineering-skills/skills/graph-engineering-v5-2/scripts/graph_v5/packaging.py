"""Closed V5 package assembly and explicit benchmark policy validation."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
from typing import Any, Mapping, Sequence


PACKAGE_MANIFEST_NAME = "PACKAGE_MANIFEST.json"
PACKAGE_NAME = "graph-engineering-v5-2"
PACKAGE_SCHEMA_VERSION = "v1"
REQUIRED_THRESHOLDS = (
    "max_product_work_time_seconds",
    "max_reproduction_latency_seconds",
    "min_resolved_on_run_head_rate",
    "max_interaction_count",
    "max_false_ready_count",
    "max_controller_fallback_count",
    "max_read_only_write_count",
    "min_restart_recovery_rate",
    "max_control_overhead_rate",
    "min_v4_relative_throughput",
)
REQUIRED_RESULT_METRICS = (
    "product_work_time_seconds",
    "reproduction_latency_seconds",
    "resolved_on_run_head_rate",
    "interaction_count",
    "false_ready_count",
    "controller_fallback_count",
    "read_only_write_count",
    "restart_recovery_rate",
    "control_overhead_rate",
    "v4_relative_throughput",
)

_ROOT_FILES = frozenset({"SKILL.md", "requirements.txt", "dependencies.lock.json"})
_REFERENCE_FILES = frozenset({"references/graph-brainstorming.md"})
_CONFIG_FILES = frozenset(
    {
        "config/run-limits.schema.json",
        "config/promotion-profile.schema.json",
        "config/policy-fixtures/run-limits.test.v1.json",
        "config/policy-fixtures/promotion-profile.test.v1.json",
    }
)
_SCRIPT_ROOT_FILES = frozenset(
    {
        "scripts/__init__.py",
        "scripts/graphctl.py",
        "scripts/benchmark.py",
        "scripts/deploy_verified_skill.py",
    }
)
_GRAPH_V5_FILES = frozenset(
    {
        "scripts/graph_v5/__init__.py",
        "scripts/graph_v5/adapters/__init__.py",
        "scripts/graph_v5/adapters/fixture_journey.py",
        "scripts/graph_v5/adapters/host_registry.py",
        "scripts/graph_v5/adapters/manifest.py",
        "scripts/graph_v5/adapters/protocol.py",
        "scripts/graph_v5/adapters/registry.py",
        "scripts/graph_v5/adapters/service_journey.py",
        "scripts/graph_v5/adapters/user_journey.py",
        "scripts/graph_v5/admission.py",
        "scripts/graph_v5/artifacts.py",
        "scripts/graph_v5/canonical.py",
        "scripts/graph_v5/causality.py",
        "scripts/graph_v5/environment.py",
        "scripts/graph_v5/models.py",
        "scripts/graph_v5/packaging.py",
        "scripts/graph_v5/policy.py",
        "scripts/graph_v5/process_runner.py",
        "scripts/graph_v5/proof.py",
        "scripts/graph_v5/repair.py",
        "scripts/graph_v5/review.py",
        "scripts/graph_v5/runtime.py",
        "scripts/graph_v5/service_supervisor.py",
        "scripts/graph_v5/spine.py",
        "scripts/graph_v5/store.py",
        "scripts/graph_v5/trajectory.py",
        "scripts/graph_v5/workspace.py",
    }
)
_TEST_GROUPS = frozenset({"unit", "integration", "contract"})
_V5_TEST_FILES = frozenset(
    {
        "tests/unit/test_adapter_manifest.py",
        "tests/unit/test_models.py",
        "tests/unit/__init__.py",
        "tests/unit/test_store.py",
        "tests/unit/test_store_integrity.py",
        "tests/unit/test_environment.py",
        "tests/unit/test_workspace.py",
        "tests/unit/test_process_runner.py",
        "tests/unit/test_spine.py",
        "tests/unit/test_causality.py",
        "tests/unit/test_runtime_limits.py",
        "tests/unit/test_proof_review.py",
        "tests/unit/test_benchmark.py",
        "tests/unit/test_package_lineage.py",
        "tests/unit/test_policy.py",
        "tests/unit/test_real_admission.py",
        "tests/unit/test_service_supervisor.py",
        "tests/unit/test_trajectory.py",
        "tests/integration/__init__.py",
        "tests/integration/test_start_transaction.py",
        "tests/integration/test_isolated_worktree.py",
        "tests/integration/test_local_system_journey.py",
        "tests/integration/test_real_authority_cli.py",
        "tests/integration/test_user_journey_traversal.py",
        "tests/integration/test_repair_ladder.py",
        "tests/integration/test_final_replay.py",
        "tests/integration/test_runner_recovery.py",
        "tests/integration/test_trajectory_intake.py",
        "tests/contract/__init__.py",
        "tests/contract/test_public_cli.py",
        "tests/contract/test_readonly_cli.py",
        "tests/contract/test_installed_package.py",
        "tests/contract/test_v4_immutability.py",
        "tests/contract/test_skill_metadata.py",
    }
)
_TEST_SUPPORT_FILES = frozenset({"tests/support/__init__.py", "tests/support/trajectory.py"})
_FIXTURE_FILES = frozenset(
    {
        "fixtures/__init__.py",
        "fixtures/benchmarks/corpus.test.v1.json",
        "fixtures/benchmarks/oracles.test.v1.json",
        "fixtures/host_profiles/node22.v1.json",
        "fixtures/host_profiles/node24.v1.json",
        "fixtures/processes/__init__.py",
        "fixtures/processes/emit_output.py",
        "fixtures/processes/local_system_worker.py",
        "fixtures/processes/spawn_tree.py",
        "fixtures/repo_templates/__init__.py",
        "fixtures/repo_templates/git_repository.py",
        "fixtures/stores/__init__.py",
        "fixtures/stores/store_root.py",
        "fixtures/user_journeys/bounded-variants.v1.json",
        "fixtures/user_journeys/healthy.v1.json",
        "fixtures/user_journeys/local-system.v1.json",
        "fixtures/user_journeys/replay-regression.v1.json",
        "fixtures/user_journeys/shared-root.v1.json",
        "fixtures/user_journeys/trajectory-drift.v1.json",
        "fixtures/user_journeys/trajectory-evidence-gap.v1.json",
        "fixtures/user_journeys/trajectory-jit.v1.json",
    }
)
_TEST_RESULT_MARKER = "GRAPH_V5_TEST_RESULT="


class PackageVerificationError(ValueError):
    """Candidate package does not match exact V5 assembly contract."""


class CandidateVerificationError(PackageVerificationError):
    """Verified candidate could not be promoted or installed safely."""


def _is_reparse_path(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_attribute = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    is_junction = getattr(path, "is_junction", None)
    return bool(
        path.is_symlink()
        or (callable(is_junction) and is_junction())
        or (reparse_attribute and attributes & reparse_attribute)
    )


def verify_no_reparse_path(
    path: Path,
    *,
    label: str,
    scan_tree: bool = False,
) -> Path:
    """Reject aliases before resolution so package bytes cannot escape selected roots."""

    lexical = Path(os.path.abspath(os.fspath(path)))
    current = lexical
    while True:
        if _is_reparse_path(current):
            raise PackageVerificationError(f"reparse path forbidden for {label}: {current}")
        if current.parent == current:
            break
        current = current.parent
    if scan_tree and lexical.is_dir():
        for directory, child_directories, files in os.walk(lexical, followlinks=False):
            root = Path(directory)
            for name in (*child_directories, *files):
                child = root / name
                if _is_reparse_path(child):
                    raise PackageVerificationError(
                        f"reparse path forbidden for {label}: {child}"
                    )
    return lexical


class BenchmarkError(ValueError):
    """Explicit benchmark input is incomplete, mutable, or non-promotable."""


@dataclass(frozen=True, slots=True)
class PromotionProfile:
    profile_id: str
    corpus_digest: str
    trial_method: str
    thresholds: tuple[tuple[str, float], ...]
    test_only: bool

    def threshold(self, name: str) -> float:
        return dict(self.thresholds)[name]


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    metrics: tuple[tuple[str, float], ...]

    def metric(self, name: str) -> float:
        return dict(self.metrics)[name]


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        character in "0123456789abcdef" for character in value.lower()
    )


def _number(value: object, *, label: str, error_type: type[ValueError]) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise error_type(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise error_type(f"{label} must be finite")
    return result


def _require_mapping(value: object, *, label: str, error_type: type[ValueError]) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise error_type(f"{label} must be an object")
    if not all(isinstance(key, str) for key in value):
        raise error_type(f"{label} has non-string keys")
    return value


def _require_exact_keys(
    value: Mapping[str, object],
    *,
    required: frozenset[str],
    label: str,
    error_type: type[ValueError],
) -> None:
    missing = required - set(value)
    extra = set(value) - required
    if missing:
        raise error_type(f"{label} missing required field: {sorted(missing)[0]}")
    if extra:
        raise error_type(f"{label} has unknown field: {sorted(extra)[0]}")


def validate_benchmark_corpus(payload: object) -> str:
    corpus = _require_mapping(payload, label="benchmark corpus", error_type=BenchmarkError)
    _require_exact_keys(
        corpus,
        required=frozenset({"schema_version", "corpus_id", "test_only", "workload_classes", "seed"}),
        label="benchmark corpus",
        error_type=BenchmarkError,
    )
    if corpus["schema_version"] != PACKAGE_SCHEMA_VERSION:
        raise BenchmarkError("benchmark corpus schema version is unsupported")
    if not isinstance(corpus["corpus_id"], str) or not corpus["corpus_id"].strip():
        raise BenchmarkError("benchmark corpus identifier is required")
    if corpus["test_only"] is not True:
        raise BenchmarkError("benchmark corpus must be test-only")
    workload_classes = corpus["workload_classes"]
    if (
        not isinstance(workload_classes, list)
        or not workload_classes
        or any(not isinstance(item, str) or not item.strip() for item in workload_classes)
        or len(set(workload_classes)) != len(workload_classes)
    ):
        raise BenchmarkError("benchmark corpus workload classes must be unique non-empty strings")
    if not isinstance(corpus["seed"], str) or not corpus["seed"].strip():
        raise BenchmarkError("benchmark corpus seed is required")
    return _sha256_bytes(canonical_json_bytes(corpus))


def validate_promotion_profile(
    payload: object, *, corpus: object
) -> PromotionProfile:
    profile = _require_mapping(payload, label="promotion profile", error_type=BenchmarkError)
    _require_exact_keys(
        profile,
        required=frozenset(
            {
                "schema_version",
                "profile_id",
                "immutable",
                "test_only",
                "workload_corpus_digest",
                "trial_method",
                "thresholds",
                "v4_baseline",
            }
        ),
        label="promotion profile",
        error_type=BenchmarkError,
    )
    if profile["schema_version"] != PACKAGE_SCHEMA_VERSION:
        raise BenchmarkError("promotion profile schema version is unsupported")
    if not isinstance(profile["profile_id"], str) or not profile["profile_id"].strip():
        raise BenchmarkError("promotion profile identifier is required")
    if profile["immutable"] is not True:
        raise BenchmarkError("promotion profile must be immutable")
    if not isinstance(profile["test_only"], bool):
        raise BenchmarkError("promotion profile test-only marker must be boolean")
    if not _is_sha256(profile["workload_corpus_digest"]):
        raise BenchmarkError("promotion profile workload corpus digest is required")
    if profile["workload_corpus_digest"] != validate_benchmark_corpus(corpus):
        raise BenchmarkError("promotion profile corpus digest does not match explicit corpus")
    if not isinstance(profile["trial_method"], str) or not profile["trial_method"].strip():
        raise BenchmarkError("promotion profile trial method is required")
    thresholds = _require_mapping(
        profile["thresholds"], label="promotion profile thresholds", error_type=BenchmarkError
    )
    for name in REQUIRED_THRESHOLDS:
        if name not in thresholds:
            raise BenchmarkError(f"promotion profile missing numeric threshold: {name}")
        _number(
            thresholds[name],
            label=f"promotion profile threshold {name}",
            error_type=BenchmarkError,
        )
    unexpected_thresholds = set(thresholds) - set(REQUIRED_THRESHOLDS)
    if unexpected_thresholds:
        raise BenchmarkError(
            f"promotion profile has unknown threshold: {sorted(unexpected_thresholds)[0]}"
        )
    baseline = _require_mapping(profile["v4_baseline"], label="V4 baseline", error_type=BenchmarkError)
    _require_exact_keys(
        baseline,
        required=frozenset({"label", "digest"}),
        label="V4 baseline",
        error_type=BenchmarkError,
    )
    if not isinstance(baseline["label"], str) or not baseline["label"].strip():
        raise BenchmarkError("V4 baseline label is required")
    if not _is_sha256(baseline["digest"]):
        raise BenchmarkError("V4 baseline digest is required")
    return PromotionProfile(
        profile_id=profile["profile_id"],
        corpus_digest=profile["workload_corpus_digest"],
        trial_method=profile["trial_method"],
        thresholds=tuple(
            (name, _number(thresholds[name], label=name, error_type=BenchmarkError))
            for name in REQUIRED_THRESHOLDS
        ),
        test_only=profile["test_only"],
    )


def validate_benchmark_result(payload: object) -> BenchmarkResult:
    result = _require_mapping(payload, label="benchmark result", error_type=BenchmarkError)
    _require_exact_keys(
        result,
        required=frozenset({"schema_version", "metrics"}),
        label="benchmark result",
        error_type=BenchmarkError,
    )
    if result["schema_version"] != PACKAGE_SCHEMA_VERSION:
        raise BenchmarkError("benchmark result schema version is unsupported")
    metrics = _require_mapping(result["metrics"], label="benchmark result metrics", error_type=BenchmarkError)
    for name in REQUIRED_RESULT_METRICS:
        if name not in metrics:
            raise BenchmarkError(f"benchmark result missing numeric result metric: {name}")
        _number(metrics[name], label=f"benchmark result metric {name}", error_type=BenchmarkError)
    unexpected_metrics = set(metrics) - set(REQUIRED_RESULT_METRICS)
    if unexpected_metrics:
        raise BenchmarkError(f"benchmark result has unknown metric: {sorted(unexpected_metrics)[0]}")
    return BenchmarkResult(
        metrics=tuple(
            (name, _number(metrics[name], label=name, error_type=BenchmarkError))
            for name in REQUIRED_RESULT_METRICS
        )
    )


def promotion_gate(profile: PromotionProfile, result: BenchmarkResult) -> tuple[bool, tuple[str, ...]]:
    """Evaluate source-spec hard gates only; never performs promotion or install."""

    failures: list[str] = []
    comparisons = (
        ("product_work_time_seconds", "max_product_work_time_seconds", "max"),
        ("reproduction_latency_seconds", "max_reproduction_latency_seconds", "max"),
        ("resolved_on_run_head_rate", "min_resolved_on_run_head_rate", "min"),
        ("interaction_count", "max_interaction_count", "max"),
        ("false_ready_count", "max_false_ready_count", "max"),
        ("controller_fallback_count", "max_controller_fallback_count", "max"),
        ("read_only_write_count", "max_read_only_write_count", "max"),
        ("restart_recovery_rate", "min_restart_recovery_rate", "min"),
        ("control_overhead_rate", "max_control_overhead_rate", "max"),
        ("v4_relative_throughput", "min_v4_relative_throughput", "min"),
    )
    for metric_name, threshold_name, direction in comparisons:
        observed = result.metric(metric_name)
        threshold = profile.threshold(threshold_name)
        if (direction == "max" and observed > threshold) or (
            direction == "min" and observed < threshold
        ):
            failures.append(f"{metric_name} fails {threshold_name}")
    for metric_name, required_value in (
        ("false_ready_count", 0.0),
        ("controller_fallback_count", 0.0),
        ("read_only_write_count", 0.0),
        ("interaction_count", 0.0),
        ("restart_recovery_rate", 1.0),
    ):
        if result.metric(metric_name) != required_value:
            failures.append(f"{metric_name} violates source hard gate")
    return not failures, tuple(failures)


def _read_json(path: Path, *, label: str) -> object:
    try:
        return json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BenchmarkError(f"cannot read explicit {label}: {path}") from error


def write_benchmark_candidate(
    *, corpus_path: Path, profile_path: Path, result_path: Path, output_root: Path
) -> dict[str, object]:
    """Create a test-only candidate under exactly one caller-selected new root."""

    corpus = _read_json(corpus_path, label="benchmark corpus")
    profile_payload = _read_json(profile_path, label="promotion profile")
    result_payload = _read_json(result_path, label="benchmark result")
    profile = validate_promotion_profile(profile_payload, corpus=corpus)
    result = validate_benchmark_result(result_payload)
    if not profile.test_only:
        raise BenchmarkError("benchmark candidate requires immutable test-only promotion profile")
    root = output_root.resolve(strict=False)
    if root.exists():
        raise BenchmarkError("benchmark output root must be a new directory")
    if not root.parent.is_dir():
        raise BenchmarkError("benchmark output root parent must already exist")
    candidate = {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "status": "candidate_recorded",
        "test_only": True,
        "promotion_eligible": False,
        "corpus_digest": validate_benchmark_corpus(corpus),
        "profile_digest": _sha256_bytes(canonical_json_bytes(profile_payload)),
        "result_digest": _sha256_bytes(canonical_json_bytes(result_payload)),
        "metrics": dict(result.metrics),
    }
    root.mkdir()
    (root / "candidate.json").write_bytes(canonical_json_bytes(candidate))
    return candidate | {"output_root": str(root)}


def verify_text_payload(relative_path: str, payload: bytes) -> None:
    """Reject malformed text before package bytes become deployable input."""

    if payload.startswith(b"\xef\xbb\xbf"):
        raise PackageVerificationError(f"UTF-8 BOM forbidden: {relative_path}")
    try:
        payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise PackageVerificationError(f"invalid UTF-8: {relative_path}") from error
    if relative_path == "SKILL.md" and not payload.startswith(b"---"):
        raise PackageVerificationError("SKILL.md frontmatter must start at byte 0")


def closed_inventory(root: Path) -> tuple[str, ...]:
    """Return exact V5 deploy inventory, excluding inherited V4 bytes."""

    root = verify_no_reparse_path(root, label="V5 package root", scan_tree=True)
    root = root.resolve()
    if not root.is_dir():
        raise PackageVerificationError(f"V5 source root does not exist: {root}")
    fixtures_root = root / "fixtures"
    if fixtures_root.is_dir():
        for path in fixtures_root.rglob("*"):
            if path.is_file() and ".git" in path.relative_to(fixtures_root).parts:
                raise PackageVerificationError(f"static .git fixture metadata forbidden: {path}")
    required = _ROOT_FILES | _REFERENCE_FILES | _CONFIG_FILES | _SCRIPT_ROOT_FILES | _GRAPH_V5_FILES | _FIXTURE_FILES | _V5_TEST_FILES | _TEST_SUPPORT_FILES | {
        "agents/openai.yaml",
        "tests/__init__.py",
        "scripts/graph_v5/__init__.py",
        "scripts/graph_v5/packaging.py",
    }
    missing = {relative for relative in required if not (root / relative).is_file()}
    if missing:
        raise PackageVerificationError(f"closed inventory missing required file: {sorted(missing)[0]}")
    inventory = tuple(sorted(required))
    for relative in inventory:
        verify_text_payload(relative, (root / relative).read_bytes())
    for group in _TEST_GROUPS:
        if not any(path.startswith(f"tests/{group}/") for path in inventory):
            raise PackageVerificationError(f"closed inventory missing {group} tests")
    return inventory


def inventory_digest(root: Path, inventory: Sequence[str]) -> str:
    digest = hashlib.sha256()
    for relative in inventory:
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update((root / relative).read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _source_revision(source: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=source,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        try:
            manifest = _candidate_manifest(source)
            revision = manifest["source_revision"]
        except PackageVerificationError as error:
            raise PackageVerificationError("V5 source revision is unavailable") from error
    else:
        revision = result.stdout.strip()
    if not isinstance(revision, str):
        raise PackageVerificationError("V5 source revision is invalid")
    if len(revision) != 40:
        raise PackageVerificationError("V5 source revision is not a full commit digest")
    return revision


def assemble_package(source: Path, destination: Path) -> dict[str, object]:
    """Copy only closed V5 inventory to new candidate destination and manifest it."""

    source = verify_no_reparse_path(source, label="V5 source", scan_tree=True)
    destination = verify_no_reparse_path(destination, label="candidate destination")
    source = source.resolve()
    destination = destination.resolve(strict=False)
    if destination.exists():
        raise PackageVerificationError("candidate destination must be a new directory")
    if not destination.parent.is_dir():
        raise PackageVerificationError("candidate destination parent must already exist")
    inventory = closed_inventory(source)
    destination.mkdir()
    try:
        for relative in inventory:
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / relative, target)
        manifest = {
            "schema_version": PACKAGE_SCHEMA_VERSION,
            "package_name": PACKAGE_NAME,
            "source_revision": _source_revision(source),
            "files": list(inventory),
            "package_digest": inventory_digest(destination, inventory),
        }
        (destination / PACKAGE_MANIFEST_NAME).write_bytes(canonical_json_bytes(manifest))
        return manifest
    except BaseException:
        shutil.rmtree(destination)
        raise


def _candidate_manifest(candidate: Path) -> Mapping[str, object]:
    try:
        raw = (candidate / PACKAGE_MANIFEST_NAME).read_bytes()
    except OSError as error:
        raise PackageVerificationError("candidate package manifest is unreadable") from error
    verify_text_payload(PACKAGE_MANIFEST_NAME, raw)
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as error:
        raise PackageVerificationError("candidate package manifest is unreadable") from error
    if canonical_json_bytes(manifest) != raw:
        raise PackageVerificationError("candidate package manifest must use canonical JSON")
    mapping = _require_mapping(manifest, label="candidate package manifest", error_type=PackageVerificationError)
    _require_exact_keys(
        mapping,
        required=frozenset({"schema_version", "package_name", "source_revision", "files", "package_digest"}),
        label="candidate package manifest",
        error_type=PackageVerificationError,
    )
    if mapping["schema_version"] != PACKAGE_SCHEMA_VERSION or mapping["package_name"] != PACKAGE_NAME:
        raise PackageVerificationError("candidate package manifest identity is invalid")
    return mapping


def _verify_candidate_inventory(candidate: Path, manifest: Mapping[str, object]) -> tuple[str, ...]:
    files = manifest["files"]
    if not isinstance(files, list) or not all(isinstance(item, str) for item in files):
        raise PackageVerificationError("candidate package manifest file list is invalid")
    expected = tuple(files)
    actual = tuple(
        sorted(
            path.relative_to(candidate).as_posix()
            for path in candidate.rglob("*")
            if path.is_file() and path.name != PACKAGE_MANIFEST_NAME
        )
    )
    extra = set(actual) - set(expected)
    missing = set(expected) - set(actual)
    if extra:
        raise PackageVerificationError(f"extra package file: {sorted(extra)[0]}")
    if missing:
        raise PackageVerificationError(f"missing package file: {sorted(missing)[0]}")
    if len(expected) != len(set(expected)) or tuple(sorted(expected)) != expected:
        raise PackageVerificationError("candidate package inventory must be unique and sorted")
    if not _is_sha256(manifest["package_digest"]):
        raise PackageVerificationError("candidate package digest is invalid")
    for relative in expected:
        verify_text_payload(relative, (candidate / relative).read_bytes())
    if inventory_digest(candidate, expected) != manifest["package_digest"]:
        raise PackageVerificationError("candidate package digest does not match staged bytes")
    closed = closed_inventory(candidate)
    if expected != closed:
        raise PackageVerificationError("candidate manifest does not match closed V5 inventory")
    return expected


def _staged_test_command(candidate: Path) -> tuple[list[str], str]:
    root_text = os.fspath(candidate.resolve())
    probe = (
        "import json, sys, unittest; "
        f"root = {root_text!r}; "
        "sys.path.insert(0, root); "
        "from pathlib import Path; "
        "from scripts.graph_v5 import packaging; "
        "assert Path(packaging.__file__).resolve().is_relative_to(Path(root).resolve()); "
        "suite = unittest.TestSuite(); "
        "loader = unittest.defaultTestLoader; "
        "[suite.addTests(loader.discover(str(Path(root) / 'tests' / group), top_level_dir=root)) "
        "for group in ('unit', 'integration', 'contract')]; "
        "result = unittest.TextTestRunner(verbosity=2).run(suite); "
        "payload = {'tests_run': result.testsRun, "
        "'failures': sorted(test.id() for test, _ in result.failures), "
        "'errors': sorted(test.id() for test, _ in result.errors), "
        "'skipped': sorted((test.id(), reason) for test, reason in result.skipped), "
        "'expected_failures': sorted(test.id() for test, _ in result.expectedFailures), "
        "'unexpected_successes': sorted(test.id() for test in result.unexpectedSuccesses)}; "
        f"print({_TEST_RESULT_MARKER!r} + json.dumps(payload, sort_keys=True, separators=(',', ':'))); "
        "raise SystemExit(0 if result.wasSuccessful() else 1)"
    )
    return [sys.executable, "-I", "-B", "-c", probe], probe


def verify_package(candidate: Path) -> dict[str, object]:
    """Verify exact candidate bytes and execute every suite from those bytes."""

    candidate = verify_no_reparse_path(candidate, label="candidate package", scan_tree=True)
    candidate = candidate.resolve()
    if not candidate.is_dir():
        raise PackageVerificationError("candidate package directory is unavailable")
    manifest = _candidate_manifest(candidate)
    _verify_candidate_inventory(candidate, manifest)
    command, _ = _staged_test_command(candidate)
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PYTHONNOUSERSITE"] = "1"
    completed = subprocess.run(
        command,
        cwd=candidate,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    result_lines = [
        line.removeprefix(_TEST_RESULT_MARKER)
        for line in completed.stdout.splitlines()
        if line.startswith(_TEST_RESULT_MARKER)
    ]
    if len(result_lines) != 1:
        raise PackageVerificationError("assembled package test result marker is missing or ambiguous")
    try:
        test_results = json.loads(result_lines[0])
    except json.JSONDecodeError as error:
        raise PackageVerificationError("assembled package test result marker is invalid") from error
    if test_results.get("skipped"):
        raise PackageVerificationError(f"assembled package has skipped tests: {test_results['skipped']}")
    if completed.returncode != 0:
        raise PackageVerificationError(
            "assembled package tests failed:\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )
    return {
        "status": "verified",
        "package_digest": manifest["package_digest"],
        "source_revision": manifest["source_revision"],
        "test_root": str(candidate),
        "test_command": " ".join(command[:4]),
        "test_results": test_results,
        "test_stdout": completed.stdout,
        "test_stderr": completed.stderr,
    }
