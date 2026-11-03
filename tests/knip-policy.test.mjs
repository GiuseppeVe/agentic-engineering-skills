import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

const skillPath = fileURLToPath(new URL("../plugins/agentic-engineering-skills/skills/cleaning-repo-with-knip/SKILL.md", import.meta.url));
const skill = await readFile(skillPath, "utf8");

test("Knip policy reconciles evidenced suppression drift only during authorized cleanup", () => {
  assert.match(skill, /config is the durable suppression\s+source of truth/);
  assert.match(skill, /ledger records its rationale/);
  assert.match(skill, /reconcile drift\s+in both directions/);
  assert.match(skill, /Never silently delete a rule\s+or invent evidence/);
  assert.match(skill, /Analysis-only runs report drift and leave both files unchanged/);
  assert.match(skill, /explicit repository spec, ADR, or owner decision/);
  assert.match(skill, /report the\s+conflict before reconciling it/);
  assert.match(skill, /analysis-only runs must not modify files, dependencies,\s+configuration, or Git state/i);
});
