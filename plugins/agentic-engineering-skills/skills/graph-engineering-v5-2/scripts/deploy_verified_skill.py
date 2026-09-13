#!/usr/bin/env python3
"""Assemble and verify Graph Engineering V5 package bytes; install only via explicit CLI action."""

from __future__ import annotations

import argparse
import json
import hashlib
import os
from pathlib import Path
import sys
import tempfile
from typing import Sequence
from uuid import uuid4


_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.graph_v5.packaging import (
    CandidateVerificationError,
    PACKAGE_NAME,
    PackageVerificationError,
    assemble_package,
    canonical_json_bytes,
    verify_package,
    verify_no_reparse_path,
)


V5_DESTINATION = Path(r"C:\Users\aleda\.codex\skills\graph-engineering-v5-2")
V5_1_ACTIVE_DESTINATION = Path(r"C:\Users\aleda\.codex\skills\graph-engineering-v5")
V4_ACTIVE_DESTINATION = Path(r"C:\Users\aleda\.codex\skills\graph-engineering-v4")
V4_ARCHIVE_DESTINATION = Path(r"C:\Users\aleda\.codex\skills-archive\graph-engineering-v4")


def _verified_install_path(path: Path, *, label: str, scan_tree: bool = False) -> Path:
    try:
        return verify_no_reparse_path(path, label=label, scan_tree=scan_tree)
    except PackageVerificationError as error:
        raise CandidateVerificationError(str(error)) from error


def _path_digest(root: Path) -> str:
    """Hash directory relative names and bytes, independent of filesystem order."""
    root = _verified_install_path(root, label="installed package", scan_tree=True)
    if not root.is_dir() or root.is_symlink():
        raise CandidateVerificationError(f"installed V5 directory is unavailable: {root}")
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if path.is_file():
            relative = path.relative_to(root).as_posix().encode("utf-8")
            digest.update(relative)
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def _assert_v4_integrity(
    *,
    active_v4: Path,
    archive_v4: Path,
    archive_digest: str,
) -> None:
    if active_v4.exists():
        raise CandidateVerificationError(f"active V4 destination must remain absent: {active_v4}")
    try:
        current_digest = _path_digest(archive_v4)
    except CandidateVerificationError as error:
        raise CandidateVerificationError(f"V4 archive is unavailable: {archive_v4}") from error
    if current_digest != archive_digest:
        raise CandidateVerificationError("V4 archive digest changed during installation")


def _validate_install_paths(
    destination: Path,
    *,
    expected_destination: Path | None,
    v4_destination: Path | None,
    v4_archive_destination: Path | None,
) -> tuple[Path, Path, Path]:
    destination = _verified_install_path(
        destination,
        label="active V5 destination",
        scan_tree=destination.is_dir(),
    )
    expected_input = expected_destination or V5_DESTINATION
    expected = _verified_install_path(
        expected_input,
        label="expected active V5 destination",
        scan_tree=expected_input.is_dir(),
    )
    active_v4_input = v4_destination or V4_ACTIVE_DESTINATION
    active_v4 = _verified_install_path(
        active_v4_input,
        label="active V4 destination",
        scan_tree=active_v4_input.is_dir(),
    )
    archive_v4_input = v4_archive_destination or V4_ARCHIVE_DESTINATION
    archive_v4 = _verified_install_path(
        archive_v4_input,
        label="archived V4 destination",
        scan_tree=archive_v4_input.is_dir(),
    )
    destination = destination.resolve(strict=False)
    expected = expected.resolve(strict=False)
    active_v4 = active_v4.resolve(strict=False)
    archive_v4 = archive_v4.resolve(strict=False)
    if destination != expected:
        raise CandidateVerificationError(
            f"active V5 destination must be {expected}"
        )
    if destination == active_v4 or destination.name == "graph-engineering-v4":
        raise CandidateVerificationError("active V4 destination is not a valid V5 target")
    if destination == archive_v4:
        raise CandidateVerificationError("V4 archive destination is not a valid V5 target")
    if _paths_overlap(destination, active_v4) or _paths_overlap(destination, archive_v4):
        raise CandidateVerificationError("active V5 destination overlaps active or archived V4 path")
    return destination, active_v4, archive_v4


def _fresh_child(parent: Path, *, label: str) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    for _ in range(20):
        candidate = parent / f"{label}-{uuid4().hex}"
        if not candidate.exists():
            return candidate
    raise CandidateVerificationError("unable to allocate unique preserved backup path")


def _paths_overlap(first: Path, second: Path) -> bool:
    return first == second or first.is_relative_to(second) or second.is_relative_to(first)


def _path_is_same_or_nested(path: Path, root: Path) -> bool:
    return path == root or path.is_relative_to(root)


def _require_verified_result(result: object, *, phase: str) -> dict[str, object]:
    if not isinstance(result, dict) or result.get("status") != "verified":
        raise CandidateVerificationError(f"{phase} verification did not report verified status")
    skipped = result.get("test_results", {}).get("skipped", []) if isinstance(result.get("test_results"), dict) else []
    if skipped:
        raise CandidateVerificationError(f"{phase} verification reported skipped tests")
    return result


def _install_verified_candidate(
    candidate: Path,
    destination: Path = V5_DESTINATION,
    *,
    prior_source: Path | None = None,
    backup_root: Path | None = None,
    backup_directory: Path | None = None,
    expected_destination: Path | None = None,
    v4_destination: Path | None = None,
    v4_archive_destination: Path | None = None,
    fail_after_swap: bool = False,
    evidence_output_directory: Path | None = None,
    evidence_filename: str = "verification-evidence.json",
) -> dict[str, object]:
    """Verify candidate, atomically install it, then rollback any preserved predecessor on failure."""
    candidate = _verified_install_path(candidate, label="candidate package", scan_tree=True)
    candidate = candidate.resolve(strict=False)
    destination, active_v4, archive_v4 = _validate_install_paths(
        destination,
        expected_destination=expected_destination,
        v4_destination=v4_destination,
        v4_archive_destination=v4_archive_destination,
    )
    migrating_v5_1 = prior_source is not None
    prior_source = _verified_install_path(
        prior_source or destination,
        label="active V5.1 source" if migrating_v5_1 else "active V5 destination",
        scan_tree=(prior_source or destination).is_dir(),
    ).resolve(strict=False)
    if migrating_v5_1 and prior_source != destination and destination.exists():
        raise CandidateVerificationError("V5.2 destination must be absent before V5.1 retirement")
    if not candidate.is_dir() or candidate.is_symlink():
        raise CandidateVerificationError("candidate package directory is unavailable")
    if _paths_overlap(candidate, destination):
        raise CandidateVerificationError("candidate and active V5 paths overlap")
    if _paths_overlap(candidate, prior_source):
        raise CandidateVerificationError("candidate and active V5.1 source paths overlap")
    if _paths_overlap(candidate, active_v4) or _paths_overlap(candidate, archive_v4):
        raise CandidateVerificationError("candidate overlaps active or archived V4 path")
    if _paths_overlap(prior_source, active_v4) or _paths_overlap(prior_source, archive_v4):
        raise CandidateVerificationError("active V5.1 source overlaps active or archived V4 path")

    if backup_root is not None:
        backup_root = _verified_install_path(backup_root, label="backup root")
        backup_parent = backup_root.resolve(strict=False)
        if _path_is_same_or_nested(backup_parent, candidate) or _path_is_same_or_nested(
            backup_parent, destination
        ) or _path_is_same_or_nested(backup_parent, prior_source):
            raise CandidateVerificationError("backup root overlaps candidate or active V5 path")
        if _path_is_same_or_nested(backup_parent, active_v4) or _path_is_same_or_nested(
            backup_parent, archive_v4
        ):
            raise CandidateVerificationError("backup root overlaps active or archived V4 path")

    try:
        archive_digest = _path_digest(archive_v4)
    except CandidateVerificationError as error:
        raise CandidateVerificationError(f"V4 archive is unavailable: {archive_v4}") from error
    _assert_v4_integrity(
        active_v4=active_v4,
        archive_v4=archive_v4,
        archive_digest=archive_digest,
    )
    if backup_root is not None and backup_directory is not None:
        raise CandidateVerificationError("backup root specified more than once")
    explicit_backup = (
        _verified_install_path(backup_directory, label="explicit backup directory").resolve(
            strict=False
        )
        if backup_directory is not None
        else None
    )
    if explicit_backup is not None and (
        _paths_overlap(explicit_backup, candidate)
        or _paths_overlap(explicit_backup, destination)
        or _paths_overlap(explicit_backup, prior_source)
    ):
        raise CandidateVerificationError("backup directory overlaps candidate or active V5 path")
    if explicit_backup is not None and (
        _path_is_same_or_nested(explicit_backup, active_v4)
        or _path_is_same_or_nested(explicit_backup, archive_v4)
    ):
        raise CandidateVerificationError("backup directory overlaps active or archived V4 path")
    if explicit_backup is not None and explicit_backup.exists():
        raise CandidateVerificationError("explicit backup path must not already exist")

    try:
        preverification = _require_verified_result(
            verify_package(candidate), phase="candidate pre"
        )
    except Exception as error:
        if isinstance(error, CandidateVerificationError):
            raise
        raise CandidateVerificationError(f"candidate preverification failed: {error}") from error

    backup_parent = (backup_root or destination.parent).resolve(strict=False)
    prior_exists = prior_source.exists()
    if migrating_v5_1 and not prior_exists:
        raise CandidateVerificationError("active V5.1 source is unavailable")
    if prior_exists and (not prior_source.is_dir() or prior_source.is_symlink()):
        label = "active V5.1 source" if migrating_v5_1 else "active V5 destination"
        raise CandidateVerificationError(f"{label} must be a regular directory")
    prior_digest = _path_digest(prior_source) if prior_exists else None
    backup: Path | None = None
    failed: Path | None = None
    moved_prior = False
    moved_candidate = False
    try:
        if prior_exists:
            backup_label = prior_source.name if migrating_v5_1 else destination.name
            backup = explicit_backup or _fresh_child(backup_parent, label=f"{backup_label}-backup")
            backup.parent.mkdir(parents=True, exist_ok=True)
            os.replace(prior_source, backup)
            moved_prior = True
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(candidate, destination)
        moved_candidate = True
        try:
            if fail_after_swap:
                raise CandidateVerificationError("injected installed-suite failure")
            postverification = _require_verified_result(
                verify_package(destination), phase="installed post"
            )
            _assert_v4_integrity(
                active_v4=active_v4,
                archive_v4=archive_v4,
                archive_digest=archive_digest,
            )
            result = {
                "status": "installed",
                "package_name": PACKAGE_NAME,
                "candidate": str(candidate),
                "destination": str(destination),
                "preverification": preverification,
                "postverification": postverification,
                "backup_path": str(backup) if backup is not None else None,
                "retired_v5_1_path": str(backup) if migrating_v5_1 and backup is not None else None,
                "failed_candidate_path": None,
                "installation_performed": True,
                "promotion_performed": True,
                "v4_destination": str(archive_v4),
                "v4_archive_destination": str(archive_v4),
                "v4_active_destination": str(active_v4),
                "v4_archive_digest": archive_digest,
                "v4_active_absent": True,
            }
            if evidence_output_directory is not None:
                evidence_path = _write_evidence(
                    evidence_output_directory,
                    result,
                    filename=evidence_filename,
                )
                result["evidence_path"] = str(evidence_path)
        except Exception as error:
            raise CandidateVerificationError(f"installed V5 verification failed: {error}") from error
    except Exception as error:
        rollback_error: Exception | None = None
        try:
            if moved_candidate and destination.exists():
                failed = _fresh_child(backup_parent, label=f"{destination.name}-failed")
                os.replace(destination, failed)
            if moved_prior and backup is not None:
                os.replace(backup, prior_source)
                if prior_digest is None or _path_digest(prior_source) != prior_digest:
                    raise CandidateVerificationError("rollback identity mismatch")
        except Exception as rollback_exc:
            rollback_error = rollback_exc
        if rollback_error is not None:
            raise CandidateVerificationError(
                f"installed V5 verification failed and rollback failed: {rollback_error}"
            ) from error
        try:
            _assert_v4_integrity(
                active_v4=active_v4,
                archive_v4=archive_v4,
                archive_digest=archive_digest,
            )
        except CandidateVerificationError as integrity_error:
            raise CandidateVerificationError(
                f"installed V5 verification failed; V4 integrity check failed: {integrity_error}"
            ) from error
        quarantine = f"; failed candidate quarantined at {failed}" if failed is not None else ""
        if isinstance(error, CandidateVerificationError):
            raise CandidateVerificationError(f"{error}{quarantine}") from error
        raise CandidateVerificationError(
            f"V5 candidate installation failed: {error}{quarantine}"
        ) from error

    return result


def install_verified_candidate(
    candidate: Path,
    destination: Path | None = None,
    *,
    backup_root: Path | None = None,
    backup_directory: Path | None = None,
    fail_after_swap: bool = False,
    evidence_output_directory: Path | None = None,
    evidence_filename: str = "verification-evidence.json",
) -> dict[str, object]:
    """Replace active V5.1 with exact V5.2 destination; test-only path modeling stays private."""

    destination = destination or V5_DESTINATION
    return _install_verified_candidate(
        candidate,
        destination,
        backup_root=backup_root,
        backup_directory=backup_directory,
        prior_source=V5_1_ACTIVE_DESTINATION,
        expected_destination=V5_DESTINATION,
        v4_destination=V4_ACTIVE_DESTINATION,
        v4_archive_destination=V4_ARCHIVE_DESTINATION,
        fail_after_swap=fail_after_swap,
        evidence_output_directory=evidence_output_directory,
        evidence_filename=evidence_filename,
    )


def _report(*, verification: dict[str, object], candidate: Path) -> dict[str, object]:
    report = {
        "status": verification["status"],
        "package_name": PACKAGE_NAME,
        "candidate": str(candidate.resolve()),
        "package_digest": verification["package_digest"],
        "source_revision": verification["source_revision"],
        "test_root": verification["test_root"],
        "destination": str(V5_DESTINATION),
        "v4_destination": str(V4_ARCHIVE_DESTINATION),
        "v4_archive_destination": str(V4_ARCHIVE_DESTINATION),
        "installation_performed": False,
        "promotion_performed": False,
        "evidence_only": True,
    }
    for key in ("test_command", "test_results", "test_stdout", "test_stderr"):
        report[key] = verification[key]
    return report


def _write_evidence(
    output_directory: Path,
    report: dict[str, object],
    *,
    filename: str = "verification-evidence.json",
) -> Path:
    root = output_directory.resolve()
    if not root.is_dir():
        raise PackageVerificationError("explicit evidence output directory must already exist")
    evidence_path = root / filename
    if evidence_path.exists():
        raise PackageVerificationError("verification evidence already exists; refusing overwrite")
    evidence_path.write_bytes(canonical_json_bytes(report))
    return evidence_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="deploy_verified_skill.py",
        description=(
            "Prepare Graph Engineering V5 package evidence. --verify-package, "
            "--assemble-candidate, and --verify-candidate never install; "
            "installation requires explicit --install-candidate."
        ),
    )
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--verify-package", action="store_true", help="Stage and verify explicit source bytes.")
    operation.add_argument("--assemble-candidate", action="store_true", help="Assemble explicit candidate bytes only.")
    operation.add_argument("--verify-candidate", action="store_true", help="Verify an existing assembled candidate.")
    operation.add_argument("--install-candidate", action="store_true", help="Explicitly install a verified candidate into V5.")
    parser.add_argument("--source", help="Explicit V5 source root for assembly.")
    parser.add_argument("--candidate", help="Explicit assembled candidate root for verification.")
    parser.add_argument("--destination", help="Explicit active V5 destination; defaults to production destination.")
    parser.add_argument("--backup-directory", help="Nonexistent path reserved for preserved prior V5 bytes.")
    parser.add_argument(
        "--output-directory",
        help="Explicit existing evidence directory; assemble creates candidate-package beneath it.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.install_candidate and args.source is not None:
        parser.error("--install-candidate cannot be combined with --source")
    if args.verify_candidate and args.source is not None:
        parser.error("--verify-candidate cannot be combined with --source")
    evidence_filename = "verification-evidence.json"
    if args.install_candidate and args.output_directory is not None:
        evidence_filename = f"installation-evidence-{uuid4().hex}.json"
    try:
        if args.verify_package:
            if args.source is None:
                parser.error("--verify-package requires --source")
            with tempfile.TemporaryDirectory(prefix="graph-engineering-v5-stage-") as temporary_directory:
                candidate = Path(temporary_directory) / "candidate-package"
                assemble_package(Path(args.source), candidate)
                report = _report(verification=verify_package(candidate), candidate=candidate)
        elif args.assemble_candidate:
            if args.source is None or args.output_directory is None:
                parser.error("--assemble-candidate requires --source and --output-directory")
            output_directory = Path(args.output_directory)
            if not output_directory.is_dir():
                parser.error("--output-directory must be an existing explicit evidence directory")
            candidate = output_directory / "candidate-package"
            manifest = assemble_package(Path(args.source), candidate)
            report = {
                "status": "assembled",
                "package_name": PACKAGE_NAME,
                "candidate": str(candidate.resolve()),
                "package_digest": manifest["package_digest"],
                "source_revision": manifest["source_revision"],
                "destination": str(V5_DESTINATION),
                "v4_destination": str(V4_ARCHIVE_DESTINATION),
                "v4_archive_destination": str(V4_ARCHIVE_DESTINATION),
                "installation_performed": False,
                "promotion_performed": False,
                "evidence_only": True,
            }
        else:
            if args.install_candidate:
                if args.candidate is None:
                    parser.error("--install-candidate requires --candidate")
                destination = Path(args.destination) if args.destination else V5_DESTINATION
                result = install_verified_candidate(
                    Path(args.candidate),
                    destination=destination,
                    backup_directory=(
                        Path(args.backup_directory) if args.backup_directory else None
                    ),
                    evidence_output_directory=(
                        Path(args.output_directory) if args.output_directory else None
                    ),
                    evidence_filename=evidence_filename,
                )
                report = result
            elif args.candidate is None:
                parser.error("--verify-candidate requires --candidate")
            else:
                candidate = Path(args.candidate)
                report = _report(verification=verify_package(candidate), candidate=candidate)
        if (
            args.output_directory is not None
            and not args.assemble_candidate
            and not args.install_candidate
        ):
            report["evidence_path"] = str(
                _write_evidence(
                    Path(args.output_directory), report, filename=evidence_filename
                )
            )
    except PackageVerificationError as error:
        parser.error(str(error))
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
