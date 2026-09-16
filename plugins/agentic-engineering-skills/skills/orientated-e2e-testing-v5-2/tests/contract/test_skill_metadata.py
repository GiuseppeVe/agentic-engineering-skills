from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / "references" / "graph-brainstorming.md"
HISTORICAL_PLAN = ROOT / "docs" / "superpowers" / "plans" / "2026-08-27-graph-engineering-v5.md"
HISTORICAL_SPEC = ROOT / "docs" / "superpowers" / "specs" / "2026-08-26-graph-engineering-v5-discovery-repair-design.md"


class SkillMetadataContractTests(unittest.TestCase):
    def test_trajectory_docs_pointers_are_checked_without_skipping_installed_package(self) -> None:
        docs_exist = HISTORICAL_PLAN.is_file() or HISTORICAL_SPEC.is_file()
        if docs_exist:
            self.assertTrue(HISTORICAL_PLAN.is_file())
            self.assertTrue(HISTORICAL_SPEC.is_file())
            self.assertIn(
                "Trajectory intake update (2026-08-28)",
                HISTORICAL_SPEC.read_text(encoding="utf-8"),
            )
            self.assertIn(
                "2026-08-28-graph-engineering-v5-trajectory-intake-design.md",
                HISTORICAL_SPEC.read_text(encoding="utf-8"),
            )
            self.assertIn(
                "Incremental update",
                HISTORICAL_PLAN.read_text(encoding="utf-8"),
            )
            self.assertIn(
                "2026-08-28-graph-engineering-v5-trajectory-intake.md",
                HISTORICAL_PLAN.read_text(encoding="utf-8"),
            )
        else:
            self.assertFalse(HISTORICAL_PLAN.exists())
            self.assertFalse(HISTORICAL_SPEC.exists())

    def test_skill_frontmatter_starts_at_byte_zero(self) -> None:
        self.assertTrue((ROOT / "SKILL.md").read_bytes().startswith(b"---"))

    def test_metadata_declares_v5_2_fixture_and_real_system_boundaries(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        metadata = (ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")

        self.assertIn("Orientated E2E Testing v5.2", metadata)
        self.assertIn("fixture adapter manifest", skill)
        self.assertIn("legacy run stores are immutable", skill)

    def test_trajectory_brief_target_language_supports_every_v5_2_mode(self) -> None:
        skill = " ".join((ROOT / "SKILL.md").read_text(encoding="utf-8").split())

        self.assertIn("actor, admitted target, and isolation boundary", skill)
        self.assertNotIn("actor and isolated fixture", skill)

    def test_skill_uses_internal_graph_brainstorming_only_for_new_run(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        reference = REFERENCE.read_text(encoding="utf-8")

        self.assertIn("references/graph-brainstorming.md", skill)
        self.assertIn("new Graph Run", reference)
        self.assertIn("Resume", reference)
        self.assertIn("one question at a time", reference)
        self.assertIn("explicit confirmation", reference)
        self.assertNotIn("name: graph-brainstorming", reference)
        self.assertNotIn("$graph-brainstorming", skill)
        self.assertFalse(reference.startswith("---"))

    def test_skill_limits_v5_to_confirmed_observable_trajectory(self) -> None:
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("Trajectory Brief", text)
        self.assertIn("confirmed", text)
        self.assertIn("Bootstrap Intent before Git effects", text)
        self.assertIn("Derived Spine", text)
        self.assertIn("`status` is read-only", text)
        self.assertIn("isolated Graph-run branch and worktree", text)
        self.assertIn("never mutates main", text)
        self.assertIn("deterministic pause", text)
        self.assertIn("explicit human integration decision", text)
        self.assertNotIn("Goal Brief is behavioral", text)
        self.assertNotIn("$graph-brainstorming", text)

    def test_skill_code_gates_public_operations_through_graphctl(self) -> None:
        text = " ".join((ROOT / "SKILL.md").read_text(encoding="utf-8").split())

        self.assertIn("All public operations go through `scripts/graphctl.py`", text)
        self.assertIn("Never bypass the CLI/runtime gate", text)
        self.assertIn("direct filesystem, Git, process, or repository tools", text)

    def test_resume_verifies_persisted_authority_and_fails_closed(self) -> None:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        reference = REFERENCE.read_text(encoding="utf-8")

        for raw_text in (skill, reference):
            text = " ".join(raw_text.split())
            self.assertIn("exact Markdown bytes", text)
            self.assertIn("fail closed", text)
            self.assertIn("never fall back to intake", text)

        metadata = (ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn("new run", metadata)
        self.assertIn("resume", metadata)

    def test_plugin_metadata_advertises_v5_2_with_v5_2_invocation_identity(self) -> None:
        text = (ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")

        self.assertIn('display_name: "Orientated E2E Testing v5.2"', text)
        self.assertIn("$orientated-e2e-testing-v5-2", text)
        self.assertNotIn("Use $graph-engineering-v5 to", text)
        self.assertNotIn("graph-brainstorming", text)
        self.assertNotIn("graph-engineering-v4", text)


if __name__ == "__main__":
    unittest.main()
