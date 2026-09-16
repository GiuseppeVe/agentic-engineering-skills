from __future__ import annotations

import importlib.util
import inspect
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.graph_v5.packaging import (
    PackageVerificationError,
    assemble_package,
    canonical_json_bytes,
    closed_inventory,
    inventory_digest,
    verify_package,
)
import scripts.graph_v5.packaging as packaging
import scripts.deploy_verified_skill as deploy


ROOT = Path(__file__).resolve().parents[2]
V4_ROOT = Path(
    os.environ.get(
        "GRAPH_V4_INSTALLED_ROOT",
        str(Path.home() / ".codex" / "skills-archive" / "graph-engineering-v4"),
    )
)


def load_module(relative_path: str, module_name: str):
    path = ROOT / relative_path
    if not path.is_file():
        raise AssertionError(f"Task 1 fixture helper missing: {relative_path}")
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Fixture helper is not importable: {relative_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def rewrite_candidate_manifest(candidate: Path, files: list[str]) -> None:
    manifest_path = candidate / "PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = sorted(files)
    manifest["package_digest"] = inventory_digest(candidate, manifest["files"])
    manifest_path.write_bytes(canonical_json_bytes(manifest))


def neutralize_candidate_tests(candidate: Path, files: list[str]) -> None:
    for relative in files:
        if relative.startswith("tests/") and "/test_" in relative:
            (candidate / relative).write_text("# neutralized by verifier contract test\n", encoding="utf-8")


def make_directory_reparse(target: Path, link: Path) -> None:
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            check=True,
            capture_output=True,
            text=True,
        )
    else:
        link.symlink_to(target, target_is_directory=True)


class InstalledPackageContractTests(unittest.TestCase):
    def test_installer_requires_archived_v4_and_absent_active_v4_before_candidate_verification(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            candidate = root / "candidate"
            active = root / "active"
            archive = root / "archive-v4"
            active_v4 = root / "active-v4"
            candidate.mkdir()
            archive.mkdir()
            (archive / "SKILL.md").write_text("archived", encoding="utf-8")
            calls: list[str] = []

            def verify(path: Path) -> dict[str, object]:
                calls.append(path.name)
                return {"status": "verified", "package_digest": "c" * 64}

            with mock.patch.object(deploy, "verify_package", side_effect=verify):
                result = deploy._install_verified_candidate(
                    candidate,
                    destination=active,
                    expected_destination=active,
                    v4_destination=active_v4,
                    v4_archive_destination=archive,
                )

            self.assertEqual(calls, ["candidate", "active"])
            self.assertEqual(result["v4_archive_destination"], str(archive.resolve()))
            self.assertEqual(result["v4_archive_digest"], deploy._path_digest(archive))
            self.assertFalse(active_v4.exists())

    def test_installer_rejects_preexisting_active_v4_without_verifying_or_moving(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            candidate = root / "candidate"
            active = root / "active"
            archive = root / "archive-v4"
            active_v4 = root / "active-v4"
            candidate.mkdir()
            archive.mkdir()
            active_v4.mkdir()
            before = deploy._path_digest(archive)
            with mock.patch.object(deploy, "verify_package") as verify:
                with self.assertRaisesRegex(deploy.CandidateVerificationError, "active V4"):
                    deploy._install_verified_candidate(
                        candidate,
                        destination=active,
                        expected_destination=active,
                        v4_destination=active_v4,
                        v4_archive_destination=archive,
                    )
            verify.assert_not_called()
            self.assertEqual(deploy._path_digest(archive), before)
            self.assertTrue(active_v4.is_dir())

    def test_installer_rejects_archive_mutation_after_post_swap_and_rolls_back(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            candidate = root / "candidate"
            active = root / "active"
            archive = root / "archive-v4"
            candidate.mkdir()
            active.mkdir()
            archive.mkdir()
            (candidate / "candidate.txt").write_text("candidate", encoding="utf-8")
            (active / "active.txt").write_text("prior", encoding="utf-8")
            (archive / "SKILL.md").write_text("archived", encoding="utf-8")
            calls = 0

            def verify(path: Path) -> dict[str, object]:
                nonlocal calls
                calls += 1
                if calls == 2:
                    (archive / "SKILL.md").write_text("tampered", encoding="utf-8")
                return {"status": "verified", "package_digest": "c" * 64}

            with mock.patch.object(deploy, "verify_package", side_effect=verify):
                with self.assertRaisesRegex(deploy.CandidateVerificationError, "archive"):
                    deploy._install_verified_candidate(
                        candidate,
                        destination=active,
                        expected_destination=active,
                        v4_archive_destination=archive,
                    )
            self.assertEqual((active / "active.txt").read_text(encoding="utf-8"), "prior")
            self.assertFalse((active / "candidate.txt").exists())
    def test_install_verified_candidate_verifies_before_swap_and_preserves_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            candidate = root / "candidate"
            active = root / "active"
            backups = root / "backups"
            candidate.mkdir()
            active.mkdir()
            (candidate / "candidate.txt").write_text("candidate", encoding="utf-8")
            (active / "active.txt").write_text("prior", encoding="utf-8")
            calls: list[str] = []

            def verify(path: Path) -> dict[str, object]:
                calls.append(path.resolve().name)
                return {"status": "verified", "package_digest": "c" * 64}

            with mock.patch.object(deploy, "verify_package", side_effect=verify):
                result = deploy._install_verified_candidate(
                    candidate,
                    destination=active,
                    backup_root=backups,
                    expected_destination=active,
                )

            self.assertEqual(calls, ["candidate", "active"])
            self.assertEqual((active / "candidate.txt").read_text(encoding="utf-8"), "candidate")
            self.assertEqual(len(list(backups.iterdir())), 1)
            preserved = next(backups.iterdir())
            self.assertEqual((preserved / "active.txt").read_text(encoding="utf-8"), "prior")
            self.assertEqual(result["preverification"]["status"], "verified")
            self.assertEqual(result["postverification"]["status"], "verified")

    def test_install_allows_backup_root_at_common_v5_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            candidate = root / "candidate"
            skills = root / "skills"
            active = skills / "graph-engineering-v5"
            archive = root / "archive-v4"
            candidate.mkdir()
            active.mkdir(parents=True)
            archive.mkdir()
            (candidate / "candidate.txt").write_text("candidate", encoding="utf-8")
            (active / "active.txt").write_text("prior", encoding="utf-8")
            (archive / "SKILL.md").write_text("archived", encoding="utf-8")

            with mock.patch.object(
                deploy,
                "verify_package",
                return_value={"status": "verified", "package_digest": "c" * 64},
            ):
                result = deploy._install_verified_candidate(
                    candidate,
                    destination=active,
                    backup_root=skills,
                    expected_destination=active,
                    v4_archive_destination=archive,
                )

            self.assertEqual((active / "candidate.txt").read_text(encoding="utf-8"), "candidate")
            self.assertEqual((Path(result["backup_path"]) / "active.txt").read_text(encoding="utf-8"), "prior")
            self.assertEqual(Path(result["backup_path"]).parent, skills)

    def test_explicit_backup_directory_is_nonexistent_preserved_backup_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            candidate = root / "candidate"
            active = root / "active"
            backup = root / "preserved-v5"
            archive = root / "archive-v4"
            candidate.mkdir()
            active.mkdir()
            archive.mkdir()
            (candidate / "candidate.txt").write_text("candidate", encoding="utf-8")
            (active / "active.txt").write_text("prior", encoding="utf-8")
            with mock.patch.object(
                deploy,
                "verify_package",
                return_value={"status": "verified", "package_digest": "c" * 64},
            ):
                result = deploy._install_verified_candidate(
                    candidate,
                    destination=active,
                    backup_directory=backup,
                    expected_destination=active,
                    v4_archive_destination=archive,
                )
            self.assertEqual(Path(result["backup_path"]), backup)
            self.assertEqual((backup / "active.txt").read_text(encoding="utf-8"), "prior")

    def test_explicit_backup_directory_rejects_existing_path_before_swap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            candidate = root / "candidate"
            active = root / "active"
            backup = root / "existing-backup"
            archive = root / "archive-v4"
            candidate.mkdir()
            active.mkdir()
            backup.mkdir()
            archive.mkdir()
            with mock.patch.object(deploy, "verify_package") as verify:
                with self.assertRaisesRegex(deploy.CandidateVerificationError, "explicit backup"):
                    deploy._install_verified_candidate(
                        candidate,
                        destination=active,
                        backup_directory=backup,
                        expected_destination=active,
                        v4_archive_destination=archive,
                    )
            verify.assert_not_called()
            self.assertTrue(active.is_dir())

    def test_install_verified_candidate_post_swap_failure_restores_prior_v5(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            candidate = root / "candidate"
            active = root / "active"
            backups = root / "backups"
            candidate.mkdir()
            active.mkdir()
            (candidate / "candidate.txt").write_text("candidate", encoding="utf-8")
            (active / "active.txt").write_text("prior", encoding="utf-8")
            calls: list[str] = []

            def verify(path: Path) -> dict[str, object]:
                calls.append(path.resolve().name)
                if path.resolve() == active.resolve():
                    raise deploy.CandidateVerificationError("injected installed-suite failure")
                return {"status": "verified", "package_digest": "c" * 64}

            with mock.patch.object(deploy, "verify_package", side_effect=verify):
                with self.assertRaises(deploy.CandidateVerificationError):
                    deploy._install_verified_candidate(
                        candidate,
                        destination=active,
                        backup_root=backups,
                        expected_destination=active,
                    )

            self.assertEqual(calls, ["candidate", "active"])
            self.assertEqual((active / "active.txt").read_text(encoding="utf-8"), "prior")
            self.assertFalse((active / "candidate.txt").exists())

    def test_public_install_migrates_v5_1_to_v5_2_without_duplicate_active_skill(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            candidate = root / "candidate"
            skills = root / "skills"
            active_v5_1 = skills / "graph-engineering-v5"
            active_v5_2 = skills / "orientated-e2e-testing-v5-2"
            backup = root / "preserved-v5-1"
            archive = root / "archive-v4"
            candidate.mkdir()
            active_v5_1.mkdir(parents=True)
            archive.mkdir()
            (candidate / "candidate.txt").write_text("candidate", encoding="utf-8")
            (active_v5_1 / "active.txt").write_text("v5-1", encoding="utf-8")
            (archive / "SKILL.md").write_text("archived", encoding="utf-8")

            with (
                mock.patch.object(deploy, "V5_DESTINATION", active_v5_2),
                mock.patch.object(deploy, "V5_1_ACTIVE_DESTINATION", active_v5_1),
                mock.patch.object(deploy, "V4_ARCHIVE_DESTINATION", archive),
                mock.patch.object(
                    deploy,
                    "verify_package",
                    return_value={"status": "verified", "package_digest": "c" * 64},
                ),
            ):
                result = deploy.install_verified_candidate(candidate, backup_directory=backup)

            self.assertFalse(active_v5_1.exists())
            self.assertEqual((active_v5_2 / "candidate.txt").read_text(encoding="utf-8"), "candidate")
            self.assertEqual((backup / "active.txt").read_text(encoding="utf-8"), "v5-1")
            self.assertEqual(Path(result["retired_v5_1_path"]), backup)

    def test_public_install_rolls_back_v5_1_when_v5_2_postverification_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            candidate = root / "candidate"
            skills = root / "skills"
            active_v5_1 = skills / "graph-engineering-v5"
            active_v5_2 = skills / "orientated-e2e-testing-v5-2"
            backups = root / "backups"
            archive = root / "archive-v4"
            candidate.mkdir()
            active_v5_1.mkdir(parents=True)
            archive.mkdir()
            (candidate / "candidate.txt").write_text("candidate", encoding="utf-8")
            (active_v5_1 / "active.txt").write_text("v5-1", encoding="utf-8")
            (archive / "SKILL.md").write_text("archived", encoding="utf-8")

            def verify(path: Path) -> dict[str, object]:
                if path.resolve() == active_v5_2.resolve():
                    raise deploy.CandidateVerificationError("injected installed-suite failure")
                return {"status": "verified", "package_digest": "c" * 64}

            with (
                mock.patch.object(deploy, "V5_DESTINATION", active_v5_2),
                mock.patch.object(deploy, "V5_1_ACTIVE_DESTINATION", active_v5_1),
                mock.patch.object(deploy, "V4_ARCHIVE_DESTINATION", archive),
                mock.patch.object(deploy, "verify_package", side_effect=verify),
            ):
                with self.assertRaisesRegex(deploy.CandidateVerificationError, "installed-suite failure"):
                    deploy.install_verified_candidate(candidate, backup_root=backups)

            self.assertEqual((active_v5_1 / "active.txt").read_text(encoding="utf-8"), "v5-1")
            self.assertFalse(active_v5_2.exists())
            quarantined = list(backups.glob("orientated-e2e-testing-v5-2-failed-*"))
            self.assertEqual(len(quarantined), 1)

    def test_public_install_rejects_existing_v5_2_target_before_candidate_verification(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            candidate = root / "candidate"
            skills = root / "skills"
            active_v5_1 = skills / "graph-engineering-v5"
            active_v5_2 = skills / "orientated-e2e-testing-v5-2"
            archive = root / "archive-v4"
            candidate.mkdir()
            active_v5_1.mkdir(parents=True)
            active_v5_2.mkdir(parents=True)
            archive.mkdir()
            (active_v5_1 / "active.txt").write_text("v5-1", encoding="utf-8")
            (active_v5_2 / "active.txt").write_text("unexpected", encoding="utf-8")
            (archive / "SKILL.md").write_text("archived", encoding="utf-8")

            with (
                mock.patch.object(deploy, "V5_DESTINATION", active_v5_2),
                mock.patch.object(deploy, "V5_1_ACTIVE_DESTINATION", active_v5_1),
                mock.patch.object(deploy, "V4_ARCHIVE_DESTINATION", archive),
                mock.patch.object(deploy, "verify_package") as verify,
            ):
                with self.assertRaisesRegex(deploy.CandidateVerificationError, "V5.2 destination must be absent"):
                    deploy.install_verified_candidate(candidate)

            verify.assert_not_called()
            self.assertEqual((active_v5_1 / "active.txt").read_text(encoding="utf-8"), "v5-1")
            self.assertEqual((active_v5_2 / "active.txt").read_text(encoding="utf-8"), "unexpected")

    def test_install_verified_candidate_rejects_wrong_destination_and_v4_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            candidate = root / "candidate"
            candidate.mkdir()
            with self.assertRaises(deploy.CandidateVerificationError):
                deploy.install_verified_candidate(
                    candidate,
                    destination=root / "wrong",
                )

    def test_cli_install_inputs_cannot_override_exact_active_v5_destination(self) -> None:
        parser = deploy.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "--install-candidate",
                    "--candidate",
                    "candidate",
                    "--expected-destination",
                    "arbitrary-active",
                ]
            )

    def test_public_install_api_cannot_override_exact_active_v5_destination(self) -> None:
        self.assertNotIn(
            "expected_destination",
            inspect.signature(deploy.install_verified_candidate).parameters,
        )

    def test_install_rejects_all_reparse_roles_before_candidate_verification(self) -> None:
        for role in ("candidate", "candidate-child", "destination", "archive", "backup"):
            with self.subTest(role=role), tempfile.TemporaryDirectory() as temporary_directory:
                root = Path(temporary_directory)
                candidate = root / "candidate"
                active = root / "active-v5"
                archive = root / "archive-v4"
                backup = root / "backup-v5"
                candidate.mkdir()
                active.mkdir()
                archive.mkdir()
                (candidate / "candidate.txt").write_text("candidate", encoding="utf-8")
                (active / "active.txt").write_text("prior", encoding="utf-8")
                (archive / "SKILL.md").write_text("archived", encoding="utf-8")

                if role == "candidate":
                    real_candidate = root / "real-candidate"
                    candidate.rename(real_candidate)
                    make_directory_reparse(real_candidate, candidate)
                elif role == "candidate-child":
                    outside = root / "outside"
                    outside.mkdir()
                    make_directory_reparse(outside, candidate / "linked-child")
                elif role == "destination":
                    real_active = root / "real-active-v5"
                    active.rename(real_active)
                    make_directory_reparse(real_active, active)
                elif role == "archive":
                    real_archive = root / "real-archive-v4"
                    archive.rename(real_archive)
                    make_directory_reparse(real_archive, archive)
                else:
                    real_backup_parent = root / "real-backups"
                    alias_backup_parent = root / "backup-alias"
                    real_backup_parent.mkdir()
                    make_directory_reparse(real_backup_parent, alias_backup_parent)
                    backup = alias_backup_parent / "backup-v5"

                with mock.patch.object(
                    deploy,
                    "verify_package",
                    side_effect=AssertionError("verification must not run for reparse input"),
                ) as verify:
                    with self.assertRaisesRegex(
                        deploy.CandidateVerificationError, "reparse"
                    ):
                        deploy._install_verified_candidate(
                            candidate,
                            destination=active,
                            backup_directory=backup,
                            expected_destination=active,
                            v4_archive_destination=archive,
                        )
                verify.assert_not_called()

    def test_install_rejects_destination_v4_nesting_before_candidate_verification(self) -> None:
        for destination_inside_archive in (True, False):
            with (
                self.subTest(destination_inside_archive=destination_inside_archive),
                tempfile.TemporaryDirectory() as temporary_directory,
            ):
                root = Path(temporary_directory)
                candidate = root / "candidate"
                candidate.mkdir()
                (candidate / "candidate.txt").write_text("candidate", encoding="utf-8")
                if destination_inside_archive:
                    archive = root / "archive-v4"
                    active = archive / "active-v5"
                    archive.mkdir()
                    active.mkdir()
                else:
                    active = root / "active-v5"
                    archive = active / "archive-v4"
                    active.mkdir()
                    archive.mkdir()
                (active / "active.txt").write_text("prior", encoding="utf-8")
                (archive / "SKILL.md").write_text("archived", encoding="utf-8")

                with mock.patch.object(
                    deploy,
                    "verify_package",
                    side_effect=AssertionError("verification must not run for V4 overlap"),
                ) as verify:
                    with self.assertRaisesRegex(
                        deploy.CandidateVerificationError, "overlap"
                    ):
                        deploy._install_verified_candidate(
                            candidate,
                            destination=active,
                            expected_destination=active,
                            v4_archive_destination=archive,
                        )
                verify.assert_not_called()

    def test_install_rejects_candidate_destination_overlap_before_verification(self) -> None:
        for candidate_is_nested in (True, False):
            with self.subTest(candidate_is_nested=candidate_is_nested), tempfile.TemporaryDirectory() as temporary_directory:
                root = Path(temporary_directory)
                if candidate_is_nested:
                    destination = root / "active"
                    candidate = destination / "candidate"
                    destination.mkdir()
                    (destination / "active.txt").write_text("prior", encoding="utf-8")
                    candidate.mkdir()
                else:
                    candidate = root / "candidate"
                    destination = candidate / "active"
                    candidate.mkdir()
                    (candidate / "candidate.txt").write_text("candidate", encoding="utf-8")
                    destination.mkdir()
                archive = root / "archive-v4"
                archive.mkdir()
                before = deploy._path_digest(destination if destination.exists() else candidate)

                with mock.patch.object(deploy, "verify_package") as verify:
                    with self.assertRaisesRegex(deploy.CandidateVerificationError, "overlap"):
                        deploy._install_verified_candidate(
                            candidate,
                            destination=destination,
                            expected_destination=destination,
                            v4_archive_destination=archive,
                        )

                verify.assert_not_called()
                self.assertEqual(
                    deploy._path_digest(destination if destination.exists() else candidate),
                    before,
                )

    def test_install_rejects_backup_overlap_before_verification(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            candidate = root / "candidate"
            destination = root / "active"
            archive = root / "archive-v4"
            backup = candidate / "backup"
            candidate.mkdir()
            destination.mkdir()
            archive.mkdir()
            (candidate / "candidate.txt").write_text("candidate", encoding="utf-8")
            (destination / "active.txt").write_text("prior", encoding="utf-8")
            before_candidate = deploy._path_digest(candidate)
            before_destination = deploy._path_digest(destination)

            with mock.patch.object(deploy, "verify_package") as verify:
                with self.assertRaisesRegex(deploy.CandidateVerificationError, "overlap"):
                    deploy._install_verified_candidate(
                        candidate,
                        destination=destination,
                        backup_directory=backup,
                        expected_destination=destination,
                        v4_archive_destination=archive,
                    )

            verify.assert_not_called()
            self.assertEqual(deploy._path_digest(candidate), before_candidate)
            self.assertEqual(deploy._path_digest(destination), before_destination)

    def test_install_rejects_backup_root_equal_to_v4_archive_before_verification(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            candidate = root / "candidate"
            active = root / "active-v5"
            active_v4 = root / "active-v4"
            archive = root / "archive-v4"
            candidate.mkdir()
            active.mkdir()
            archive.mkdir()
            (candidate / "candidate.txt").write_text("candidate", encoding="utf-8")
            (active / "active.txt").write_text("prior", encoding="utf-8")
            (archive / "SKILL.md").write_text("archived", encoding="utf-8")
            before_candidate = deploy._path_digest(candidate)
            before_active = deploy._path_digest(active)
            before_archive = deploy._path_digest(archive)

            with mock.patch.object(deploy, "verify_package") as verify:
                with self.assertRaisesRegex(deploy.CandidateVerificationError, "V4"):
                    deploy._install_verified_candidate(
                        candidate,
                        destination=active,
                        backup_root=archive,
                        expected_destination=active,
                        v4_destination=active_v4,
                        v4_archive_destination=archive,
                    )

            verify.assert_not_called()
            self.assertEqual(deploy._path_digest(candidate), before_candidate)
            self.assertEqual(deploy._path_digest(active), before_active)
            self.assertEqual(deploy._path_digest(archive), before_archive)
            self.assertFalse(active_v4.exists())

    def test_install_rejects_candidate_nested_in_v4_archive_before_verification(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            active = root / "active-v5"
            active_v4 = root / "active-v4"
            archive = root / "archive-v4"
            candidate = archive / "candidate"
            active.mkdir()
            archive.mkdir()
            candidate.mkdir()
            (candidate / "candidate.txt").write_text("candidate", encoding="utf-8")
            (active / "active.txt").write_text("prior", encoding="utf-8")
            (archive / "SKILL.md").write_text("archived", encoding="utf-8")
            before_candidate = deploy._path_digest(candidate)
            before_active = deploy._path_digest(active)
            before_archive = deploy._path_digest(archive)

            with mock.patch.object(deploy, "verify_package") as verify:
                with self.assertRaisesRegex(deploy.CandidateVerificationError, "V4"):
                    deploy._install_verified_candidate(
                        candidate,
                        destination=active,
                        expected_destination=active,
                        v4_destination=active_v4,
                        v4_archive_destination=archive,
                    )

            verify.assert_not_called()
            self.assertEqual(deploy._path_digest(candidate), before_candidate)
            self.assertEqual(deploy._path_digest(active), before_active)
            self.assertEqual(deploy._path_digest(archive), before_archive)
            self.assertFalse(active_v4.exists())

    def test_install_rejects_explicit_backup_child_of_v4_archive_before_verification(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            candidate = root / "candidate"
            active = root / "active-v5"
            active_v4 = root / "active-v4"
            archive = root / "archive-v4"
            backup = archive / "backup-v5"
            candidate.mkdir()
            active.mkdir()
            archive.mkdir()
            (candidate / "candidate.txt").write_text("candidate", encoding="utf-8")
            (active / "active.txt").write_text("prior", encoding="utf-8")
            (archive / "SKILL.md").write_text("archived", encoding="utf-8")
            before_candidate = deploy._path_digest(candidate)
            before_active = deploy._path_digest(active)
            before_archive = deploy._path_digest(archive)

            with mock.patch.object(deploy, "verify_package") as verify:
                with self.assertRaisesRegex(deploy.CandidateVerificationError, "V4"):
                    deploy._install_verified_candidate(
                        candidate,
                        destination=active,
                        backup_directory=backup,
                        expected_destination=active,
                        v4_destination=active_v4,
                        v4_archive_destination=archive,
                    )

            verify.assert_not_called()
            self.assertEqual(deploy._path_digest(candidate), before_candidate)
            self.assertEqual(deploy._path_digest(active), before_active)
            self.assertEqual(deploy._path_digest(archive), before_archive)
            self.assertFalse(active_v4.exists())

    def test_cli_accepts_explicit_install_candidate_operation(self) -> None:
        parser = deploy.build_parser()
        args = parser.parse_args(
            ["--install-candidate", "--candidate", "candidate", "--destination", "active"]
        )
        self.assertTrue(args.install_candidate)
        self.assertEqual(args.destination, "active")

    def test_cli_install_writes_separate_evidence_when_verification_evidence_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output = root / "evidence"
            output.mkdir()
            (output / "verification-evidence.json").write_text("{}", encoding="utf-8")
            candidate = root / "candidate"
            active_v5_1 = root / "graph-engineering-v5"
            active = root / "orientated-e2e-testing-v5-2"
            active_v4 = root / "graph-engineering-v4"
            archive = root / "archive-v4"
            candidate.mkdir()
            active_v5_1.mkdir()
            archive.mkdir()
            (candidate / "candidate.txt").write_text("candidate", encoding="utf-8")
            (active_v5_1 / "active.txt").write_text("prior", encoding="utf-8")
            (archive / "SKILL.md").write_text("archived", encoding="utf-8")

            verified = {"status": "verified", "package_digest": "c" * 64}
            with (
                mock.patch.object(deploy, "V5_DESTINATION", active),
                mock.patch.object(deploy, "V5_1_ACTIVE_DESTINATION", active_v5_1),
                mock.patch.object(deploy, "V4_ACTIVE_DESTINATION", active_v4),
                mock.patch.object(deploy, "V4_ARCHIVE_DESTINATION", archive),
                mock.patch.object(deploy, "verify_package", return_value=verified),
            ):
                result = deploy.main(
                    [
                        "--install-candidate",
                        "--candidate",
                        str(candidate),
                        "--destination",
                        str(active),
                        "--output-directory",
                        str(output),
                    ]
                )

            self.assertEqual(result, 0)
            install_evidence = list(output.glob("installation-evidence-*.json"))
            self.assertEqual(len(install_evidence), 1)
            self.assertTrue((output / "verification-evidence.json").is_file())
            self.assertEqual(
                (active / "candidate.txt").read_text(encoding="utf-8"),
                "candidate",
            )

    def test_cli_evidence_failure_rolls_back_and_quarantines_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output = root / "evidence"
            candidate = root / "candidate"
            active_v5_1 = root / "graph-engineering-v5"
            active = root / "orientated-e2e-testing-v5-2"
            active_v4 = root / "graph-engineering-v4"
            archive = root / "archive-v4"
            output.mkdir()
            candidate.mkdir()
            active_v5_1.mkdir()
            archive.mkdir()
            (candidate / "candidate.txt").write_text("candidate", encoding="utf-8")
            (active_v5_1 / "active.txt").write_text("prior", encoding="utf-8")
            (archive / "SKILL.md").write_text("archived", encoding="utf-8")

            verified = {"status": "verified", "package_digest": "c" * 64}
            with (
                mock.patch.object(deploy, "V5_DESTINATION", active),
                mock.patch.object(deploy, "V5_1_ACTIVE_DESTINATION", active_v5_1),
                mock.patch.object(deploy, "V4_ACTIVE_DESTINATION", active_v4),
                mock.patch.object(deploy, "V4_ARCHIVE_DESTINATION", archive),
                mock.patch.object(deploy, "verify_package", return_value=verified),
                mock.patch.object(
                    deploy,
                    "_write_evidence",
                    side_effect=deploy.PackageVerificationError("injected evidence failure"),
                ),
                self.assertRaises(SystemExit),
            ):
                deploy.main(
                    [
                        "--install-candidate",
                        "--candidate",
                        str(candidate),
                        "--output-directory",
                        str(output),
                    ]
                )

            self.assertTrue(active_v5_1.is_dir())
            self.assertTrue((active_v5_1 / "active.txt").is_file())
            self.assertEqual((active_v5_1 / "active.txt").read_text(encoding="utf-8"), "prior")
            self.assertFalse((active / "candidate.txt").exists())
            quarantined = list(root.glob("orientated-e2e-testing-v5-2-failed-*"))
            self.assertEqual(len(quarantined), 1)
            self.assertEqual(
                (quarantined[0] / "candidate.txt").read_text(encoding="utf-8"),
                "candidate",
            )

    def test_closed_inventory_requires_regular_tests_package_for_isolation(self) -> None:
        self.assertIn("tests/__init__.py", closed_inventory(ROOT))

    def test_task1_test_shell_runs_from_a_clean_staged_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            installed_root = Path(temporary_directory) / "graph-engineering-v5"
            for relative_path in closed_inventory(ROOT):
                source = ROOT / relative_path
                destination = installed_root / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)

            selected_tests = (
                "tests.unit.test_package_lineage",
                "tests.contract.test_installed_package.InstalledPackageContractTests."
                "test_v5_source_is_separate_from_installed_v4_package",
                "tests.contract.test_installed_package.InstalledPackageContractTests."
                "test_repo_template_creates_real_git_repository_at_test_time",
                "tests.contract.test_installed_package.InstalledPackageContractTests."
                "test_repo_template_ignores_host_git_config",
                "tests.contract.test_installed_package.InstalledPackageContractTests."
                "test_repo_template_ignores_command_scoped_git_config",
                "tests.contract.test_installed_package.InstalledPackageContractTests."
                "test_store_fixture_creates_empty_root_at_test_time",
            )
            probe = (
                "import sys, unittest; "
                f"sys.path.insert(0, {json.dumps(str(installed_root))}); "
                f"suite = unittest.defaultTestLoader.loadTestsFromNames({selected_tests!r}); "
                "result = unittest.TextTestRunner(verbosity=2).run(suite); "
                "raise SystemExit(0 if result.wasSuccessful() else 1)"
            )
            environment = os.environ.copy()
            environment.pop("PYTHONPATH", None)
            environment["PYTHONNOUSERSITE"] = "1"

            result = subprocess.run(
                [os.fspath(Path(os.sys.executable)), "-I", "-B", "-c", probe],
                cwd=installed_root,
                env=environment,
                text=True,
                capture_output=True,
            )

            self.assertEqual(
                result.returncode,
                0,
                msg=f"stdout:\\n{result.stdout}\\nstderr:\\n{result.stderr}",
            )

    def test_v5_source_is_separate_from_installed_v4_package(self) -> None:
        self.assertNotEqual(ROOT.resolve(), V4_ROOT.resolve())
        self.assertEqual(
            (V4_ROOT / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[1]
            .split("name:", 1)[1]
            .splitlines()[0]
            .strip(),
            "graph-engineering-v4",
        )

    def test_repo_template_creates_real_git_repository_at_test_time(self) -> None:
        helper = load_module("fixtures/repo_templates/git_repository.py", "fixture_git_repo")

        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = helper.create_git_repository(Path(temporary_directory) / "repo")

            self.assertTrue((repository / ".git").is_dir())
            self.assertEqual(git(repository, "rev-parse", "--is-inside-work-tree"), "true")
            self.assertEqual(git(repository, "log", "-1", "--format=%s"), "fixture base")

    def test_repo_template_ignores_host_git_config(self) -> None:
        helper = load_module("fixtures/repo_templates/git_repository.py", "isolated_fixture_git_repo")

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            hostile_config = temporary_root / "hostile.gitconfig"
            hostile_config.write_text(
                "[commit]\n\tgpgSign = true\n[init]\n\tdefaultBranch = hostile\n",
                encoding="utf-8",
            )
            with mock.patch.dict(
                os.environ,
                {"GIT_CONFIG_GLOBAL": str(hostile_config), "GIT_CONFIG_NOSYSTEM": "1"},
            ):
                repository = helper.create_git_repository(temporary_root / "repo")

            self.assertEqual(git(repository, "branch", "--show-current"), "main")
            self.assertEqual(git(repository, "log", "-1", "--format=%s"), "fixture base")

    def test_repo_template_ignores_command_scoped_git_config(self) -> None:
        helper = load_module("fixtures/repo_templates/git_repository.py", "injected_fixture_git_repo")

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            with mock.patch.dict(
                os.environ,
                {
                    "GIT_CONFIG_COUNT": "1",
                    "GIT_CONFIG_KEY_0": "user.name",
                    "GIT_CONFIG_VALUE_0": "Hostile Injected User",
                },
            ):
                repository = helper.create_git_repository(temporary_root / "repo")

            self.assertEqual(git(repository, "branch", "--show-current"), "main")
            self.assertEqual(git(repository, "log", "-1", "--format=%s"), "fixture base")
            self.assertEqual(git(repository, "log", "-1", "--format=%an"), "Graph V5 Fixture")

    def test_store_fixture_creates_empty_root_at_test_time(self) -> None:
        helper = load_module("fixtures/stores/store_root.py", "fixture_store_root")

        with tempfile.TemporaryDirectory() as temporary_directory:
            store_root = helper.create_store_root(Path(temporary_directory) / "store")

            self.assertTrue(store_root.is_dir())
            self.assertEqual(list(store_root.iterdir()), [])

    def test_closed_inventory_excludes_legacy_v4_and_documentation_surfaces(self) -> None:
        inventory = set(closed_inventory(ROOT))

        self.assertTrue(
            {
                "SKILL.md",
                "requirements.txt",
                "dependencies.lock.json",
                "agents/openai.yaml",
                "config/run-limits.schema.json",
                "config/promotion-profile.schema.json",
                "config/policy-fixtures/run-limits.test.v1.json",
                "config/policy-fixtures/promotion-profile.test.v1.json",
                "scripts/graphctl.py",
                "scripts/benchmark.py",
                "scripts/deploy_verified_skill.py",
                "scripts/graph_v5/packaging.py",
                "tests/unit/test_benchmark.py",
                "fixtures/benchmarks/corpus.test.v1.json",
                "fixtures/benchmarks/oracles.test.v1.json",
            }.issubset(inventory)
        )
        self.assertFalse(any(path.startswith("scripts/graph_kernel/") for path in inventory))
        self.assertFalse(any(path.startswith("docs/") for path in inventory))
        self.assertEqual(
            {path for path in inventory if path.startswith("references/")},
            {"references/graph-brainstorming.md"},
        )

    def test_closed_inventory_excludes_unregistered_source_test_modules(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "source"
            for relative_path in closed_inventory(ROOT):
                destination = source / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative_path, destination)
            rogue = source / "tests" / "unit" / "test_v4_leak.py"
            rogue.write_text("import unittest\n", encoding="utf-8")

            self.assertNotIn("tests/unit/test_v4_leak.py", closed_inventory(source))

    def test_closed_inventory_excludes_unregistered_graph_v5_modules(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "source"
            for relative_path in closed_inventory(ROOT):
                destination = source / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative_path, destination)
            rogue = source / "scripts" / "graph_v5" / "rogue.py"
            rogue.write_text("# unregistered module\n", encoding="utf-8")

            self.assertNotIn("scripts/graph_v5/rogue.py", closed_inventory(source))

    def test_assembled_copy_has_exact_inventory_and_runs_all_suites_from_staged_bytes(self) -> None:
        if (ROOT / "PACKAGE_MANIFEST.json").is_file():
            manifest = json.loads((ROOT / "PACKAGE_MANIFEST.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["package_name"], "orientated-e2e-testing-v5-2")
            self.assertRegex(manifest["source_revision"], r"^[0-9a-f]{40}$")
            return
        with tempfile.TemporaryDirectory() as temporary_directory:
            candidate = Path(temporary_directory) / "candidate"
            manifest = assemble_package(ROOT, candidate)
            verification = verify_package(candidate)

            self.assertEqual(verification["status"], "verified")
            self.assertEqual(verification["package_digest"], manifest["package_digest"])
            self.assertEqual(verification["test_root"], str(candidate.resolve()))
            self.assertNotIn(str(ROOT.resolve()), verification["test_command"])

    def test_candidate_verifier_rejects_root_and_internal_reparse_before_suites(self) -> None:
        for role in ("root", "internal"):
            with self.subTest(role=role), tempfile.TemporaryDirectory() as temporary_directory:
                root = Path(temporary_directory)
                candidate = root / "candidate"
                assemble_package(ROOT, candidate)
                if role == "root":
                    alias = root / "candidate-alias"
                    make_directory_reparse(candidate, alias)
                    verification_root = alias
                else:
                    graph_v5 = candidate / "scripts" / "graph_v5"
                    outside = root / "outside-graph-v5"
                    graph_v5.rename(outside)
                    make_directory_reparse(outside, graph_v5)
                    verification_root = candidate

                with mock.patch.object(
                    packaging,
                    "subprocess",
                ) as packaged_subprocess:
                    packaged_subprocess.run.side_effect = AssertionError(
                        "suites must not run for reparse candidate"
                    )
                    with self.assertRaisesRegex(PackageVerificationError, "reparse"):
                        packaging.verify_package(verification_root)
                packaged_subprocess.run.assert_not_called()

    def test_candidate_verifier_rejects_extra_or_missing_inventory_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            candidate = Path(temporary_directory) / "candidate"
            assemble_package(ROOT, candidate)
            rogue = candidate / "docs" / "rogue.md"
            rogue.parent.mkdir()
            rogue.write_text("not in V5 package", encoding="utf-8")

            with self.assertRaisesRegex(PackageVerificationError, "extra package file"):
                verify_package(candidate)

    def test_candidate_verifier_rejects_tampered_v52_service_adapter_before_suites(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            candidate = Path(temporary_directory) / "candidate"
            assemble_package(ROOT, candidate)
            (candidate / "scripts" / "graph_v5" / "adapters" / "service_journey.py").write_text(
                "tampered\n", encoding="utf-8"
            )

            with mock.patch.object(
                packaging.subprocess,
                "run",
                side_effect=AssertionError("staged suites must not run after digest mismatch"),
            ) as staged_run:
                with self.assertRaisesRegex(PackageVerificationError, "digest"):
                    verify_package(candidate)

            staged_run.assert_not_called()

    def test_candidate_verifier_rejects_bom_and_invalid_utf8_payloads(self) -> None:
        for payload in (b"\xef\xbb\xbf# Graph", b"\xff\xfe"):
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as temporary_directory:
                candidate = Path(temporary_directory) / "candidate"
                assemble_package(ROOT, candidate)
                (candidate / "references" / "graph-brainstorming.md").write_bytes(payload)

                with self.assertRaisesRegex(PackageVerificationError, "(?:BOM|UTF-8)"):
                    verify_package(candidate)

    def test_candidate_verifier_rejects_bom_prefixed_manifest_before_running_suites(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            candidate = Path(temporary_directory) / "candidate"
            assemble_package(ROOT, candidate)
            manifest_path = candidate / "PACKAGE_MANIFEST.json"
            manifest_path.write_bytes(b"\xef\xbb\xbf" + manifest_path.read_bytes())

            import scripts.graph_v5.packaging as packaging

            with mock.patch.object(packaging.subprocess, "run", side_effect=AssertionError("suites must not run")):
                with self.assertRaisesRegex(PackageVerificationError, "BOM"):
                    verify_package(candidate)

    def test_candidate_verifier_rejects_noncanonical_manifest_before_running_suites(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            candidate = Path(temporary_directory) / "candidate"
            assemble_package(ROOT, candidate)
            manifest_path = candidate / "PACKAGE_MANIFEST.json"
            manifest = json.loads(manifest_path.read_bytes())
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            import scripts.graph_v5.packaging as packaging

            with mock.patch.object(packaging.subprocess, "run", side_effect=AssertionError("suites must not run")):
                with self.assertRaisesRegex(PackageVerificationError, "canonical"):
                    verify_package(candidate)

    def test_candidate_verifier_rejects_manifest_omission(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            candidate = Path(temporary_directory) / "candidate"
            manifest = assemble_package(ROOT, candidate)
            omitted = "references/graph-brainstorming.md"
            (candidate / omitted).unlink()
            neutralize_candidate_tests(candidate, manifest["files"])
            rewrite_candidate_manifest(
                candidate,
                [path for path in manifest["files"] if path != omitted],
            )

            with self.assertRaisesRegex(PackageVerificationError, "missing required file"):
                verify_package(candidate)

    def test_candidate_verifier_rejects_skipped_tests(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            candidate = Path(temporary_directory) / "candidate"
            manifest = assemble_package(ROOT, candidate)
            neutralize_candidate_tests(candidate, manifest["files"])
            test_path = candidate / "tests" / "unit" / "test_package_lineage.py"
            test_path.write_text(
                    "import unittest\n\nclass InjectedSkip(unittest.TestCase):\n"
                    "    @unittest.skip('injected release-gate skip')\n"
                    "    def test_skip(self):\n"
                    "        pass\n",
                    encoding="utf-8",
                )
            rewrite_candidate_manifest(candidate, manifest["files"])

            with self.assertRaisesRegex(PackageVerificationError, "skipped tests"):
                verify_package(candidate)

    def test_evidence_report_retains_exact_candidate_test_results(self) -> None:
        deploy = load_module("scripts/deploy_verified_skill.py", "deploy_verified_skill")
        verification = {
            "status": "verified",
            "package_digest": "a" * 64,
            "source_revision": "b" * 40,
            "test_root": str(ROOT),
            "test_command": "python -I -B -c <candidate probe>",
            "test_results": {
                "tests_run": 231,
                "failures": [],
                "errors": [],
                "skipped": [],
                "expected_failures": [],
                "unexpected_successes": [],
            },
            "test_stdout": "structured result marker",
            "test_stderr": "Ran 231 tests",
        }

        report = deploy._report(verification=verification, candidate=ROOT)

        self.assertEqual(report["test_command"], verification["test_command"])
        self.assertEqual(report["test_results"], verification["test_results"])
        self.assertEqual(report["test_stdout"], verification["test_stdout"])
        self.assertEqual(report["test_stderr"], verification["test_stderr"])


if __name__ == "__main__":
    unittest.main()
