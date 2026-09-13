from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from importlib.util import find_spec
from pathlib import Path

from scripts.graph_v5.packaging import PackageVerificationError, verify_text_payload


ROOT = Path(__file__).resolve().parents[2]
V4_ROOT = Path(
    os.environ.get(
        "GRAPH_V4_INSTALLED_ROOT",
        r"C:\Users\aleda\.codex\skills-archive\graph-engineering-v4",
    )
)
BASELINE_REVISION = "693f1922ef2a04088c286cab3c02b308724c2fd1"
EXPECTED_V4_PACKAGE_DIGEST = "50e17aa95ff601391550e40f329437a44ede279d09823b16e460a62114a64fa3"
EXPECTED_V4_SKILL_DIGEST = "47b75c9716a861e4cfb11a60b7c4b8bc9f3c8c23346e3dd52e7b09793b11ca3f"
EXCLUDED_PARTS = {".git", ".codex", "__pycache__"}


def read_skill_metadata(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    _, frontmatter, _ = text.split("---", 2)
    return {
        key.strip(): value.strip()
        for line in frontmatter.splitlines()
        if ":" in line
        for key, value in [line.split(":", 1)]
    }


def build_install_inventory(root: Path) -> tuple[str, ...]:
    fixtures_root = root / "fixtures"
    if fixtures_root.is_dir():
        static_git_paths = tuple(
            path for path in fixtures_root.rglob("*") if ".git" in path.relative_to(fixtures_root).parts
        )
        if static_git_paths:
            raise ValueError(f"static .git fixture metadata forbidden: {static_git_paths[0]}")

    return tuple(
        path.relative_to(root).as_posix()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not (set(path.relative_to(root).parts) & EXCLUDED_PARTS)
    )


def package_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for relative in build_install_inventory(root):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update((root / relative).read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


class PackageLineageTests(unittest.TestCase):
    def test_closed_inventory_contains_exact_trajectory_package_surfaces(self) -> None:
        from scripts.graph_v5.packaging import closed_inventory

        inventory = set(closed_inventory(ROOT))
        self.assertIn("references/graph-brainstorming.md", inventory)
        self.assertIn("scripts/graph_v5/trajectory.py", inventory)
        self.assertIn("tests/support/__init__.py", inventory)
        self.assertIn("tests/support/trajectory.py", inventory)
        self.assertIn("tests/unit/test_trajectory.py", inventory)
        self.assertIn("tests/integration/test_trajectory_intake.py", inventory)
        for fixture in (
            "fixtures/user_journeys/trajectory-jit.v1.json",
            "fixtures/user_journeys/trajectory-evidence-gap.v1.json",
            "fixtures/user_journeys/trajectory-drift.v1.json",
        ):
            self.assertIn(fixture, inventory)
        references = {path for path in inventory if path.startswith("references/")}
        self.assertEqual(references, {"references/graph-brainstorming.md"})
        self.assertFalse(any(path.startswith("docs/") for path in inventory))

    def test_closed_inventory_contains_all_real_system_v52_surfaces(self) -> None:
        from scripts.graph_v5.packaging import PackageVerificationError, closed_inventory

        try:
            inventory = set(closed_inventory(ROOT))
        except PackageVerificationError as error:
            self.fail(str(error))
        expected = {
            "agents/openai.yaml",
            "config/policy-fixtures/promotion-profile.test.v1.json",
            "config/policy-fixtures/run-limits.test.v1.json",
            "config/promotion-profile.schema.json",
            "config/run-limits.schema.json",
            "fixtures/processes/local_system_worker.py",
            "fixtures/user_journeys/local-system.v1.json",
            "scripts/graph_v5/adapters/fixture_journey.py",
            "scripts/graph_v5/adapters/host_registry.py",
            "scripts/graph_v5/adapters/manifest.py",
            "scripts/graph_v5/adapters/protocol.py",
            "scripts/graph_v5/adapters/registry.py",
            "scripts/graph_v5/adapters/service_journey.py",
            "scripts/graph_v5/admission.py",
            "scripts/graph_v5/policy.py",
            "scripts/graph_v5/service_supervisor.py",
            "tests/integration/test_local_system_journey.py",
            "tests/integration/test_real_authority_cli.py",
            "tests/unit/test_adapter_manifest.py",
            "tests/unit/test_policy.py",
            "tests/unit/test_real_admission.py",
            "tests/unit/test_service_supervisor.py",
        }

        self.assertTrue(expected.issubset(inventory), expected - inventory)

    def test_closed_inventory_does_not_discover_unregistered_source_files(self) -> None:
        from scripts.graph_v5.packaging import PackageVerificationError, closed_inventory

        try:
            inventory = set(closed_inventory(ROOT))
        except PackageVerificationError as error:
            self.fail(str(error))

        self.assertNotIn("tests/unit/test_architecture_screening_workflow.py", inventory)

    def test_closed_inventory_is_sorted_unique_posix(self) -> None:
        from scripts.graph_v5.packaging import closed_inventory

        inventory = closed_inventory(ROOT)
        self.assertEqual(inventory, tuple(sorted(set(inventory))))
        self.assertTrue(all("\\" not in path for path in inventory))

    def test_text_payload_validation_rejects_bom_invalid_utf8_and_bad_skill_frontmatter(self) -> None:
        cases = (
            ("references/graph-brainstorming.md", b"\xef\xbb\xbf# Graph"),
            ("references/graph-brainstorming.md", b"\xff\xfe"),
            ("SKILL.md", b"# missing frontmatter"),
        )
        for relative_path, payload in cases:
            with self.subTest(relative_path=relative_path, payload=payload):
                with self.assertRaises(PackageVerificationError):
                    verify_text_payload(relative_path, payload)

    def test_text_payload_validation_accepts_valid_utf8_and_skill_frontmatter(self) -> None:
        verify_text_payload("references/graph-brainstorming.md", "# Graph ✓".encode("utf-8"))
        verify_text_payload("SKILL.md", b"---\nname: graph-engineering-v5-2\n---\n")

    def test_install_inventory_rejects_static_git_fixture_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            package_root = Path(temporary_directory)
            static_git_config = (
                package_root / "fixtures" / "repo_templates" / "sample" / ".git" / "config"
            )
            static_git_config.parent.mkdir(parents=True)
            static_git_config.write_text("[core]\\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "static \\.git"):
                build_install_inventory(package_root)

    def test_v5_source_declares_a_distinct_package_identity(self) -> None:
        metadata = read_skill_metadata(ROOT / "SKILL.md")

        self.assertEqual(metadata["name"], "graph-engineering-v5-2")
        self.assertNotEqual(package_digest(ROOT), package_digest(V4_ROOT))

    def test_v5_source_descends_from_verified_v4_baseline(self) -> None:
        if not (ROOT / ".git").exists():
            manifest_path = ROOT / "PACKAGE_MANIFEST.json"
            if not manifest_path.exists():
                self.assertFalse((ROOT / ".git").exists())
                return
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertRegex(manifest["source_revision"], r"^[0-9a-f]{40}$")
            self.assertEqual(manifest["package_name"], "graph-engineering-v5-2")
            return
        self.assertEqual(git("rev-parse", BASELINE_REVISION), BASELINE_REVISION)
        self.assertEqual(
            subprocess.run(
                ["git", "merge-base", "--is-ancestor", BASELINE_REVISION, "HEAD"],
                cwd=ROOT,
                capture_output=True,
                text=True,
            ).returncode,
            0,
        )

    def test_installed_v4_matches_verified_package_manifest(self) -> None:
        self.assertTrue(V4_ROOT.is_dir(), f"archived V4 root missing: {V4_ROOT}")
        self.assertFalse(
            Path(r"C:\Users\aleda\.codex\skills\graph-engineering-v4").exists(),
            "active V4 destination must remain absent",
        )
        self.assertEqual(package_digest(V4_ROOT), EXPECTED_V4_PACKAGE_DIGEST)
        self.assertEqual(
            hashlib.sha256((V4_ROOT / "SKILL.md").read_bytes()).hexdigest(),
            EXPECTED_V4_SKILL_DIGEST,
        )

    def test_v5_source_has_an_importable_runtime_package(self) -> None:
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            spec = find_spec("graph_v5")
            self.assertIsNotNone(spec)
            assert spec is not None and spec.origin is not None
            self.assertEqual(
                Path(spec.origin).resolve(),
                (ROOT / "scripts" / "graph_v5" / "__init__.py").resolve(),
            )
        finally:
            sys.path.pop(0)

    def test_install_inventory_contains_v5_tests_and_fixtures(self) -> None:
        inventory = build_install_inventory(ROOT)

        self.assertTrue(any(path.startswith("tests/") for path in inventory))
        self.assertTrue(any(path.startswith("fixtures/") for path in inventory))
        self.assertIn("tests/unit/test_package_lineage.py", inventory)
        self.assertIn("tests/contract/test_installed_package.py", inventory)
        self.assertIn("fixtures/repo_templates/git_repository.py", inventory)
        self.assertIn("fixtures/stores/store_root.py", inventory)


if __name__ == "__main__":
    unittest.main()
