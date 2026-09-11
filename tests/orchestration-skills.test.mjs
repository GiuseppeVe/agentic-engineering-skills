import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const skillsRoot = path.join(root, "plugins", "agentic-engineering-skills", "skills");

async function skill(name) {
  return readFile(path.join(skillsRoot, name, "SKILL.md"), "utf8");
}

test("orchestrator package wires plan fidelity and implementation correctness review", async () => {
  const source = await skill("sequential-task-orchestrator");

  assert.match(source, /\$test-gaps|Test Gaps/);
  assert.match(source, /test-driven-development/);
  assert.match(source, /one independent review cycle per task/);
  assert.match(source, /runtime-protocol\.md/);
});

test("Test Gaps skill exposes coverage-gap discovery commands", async () => {
  const source = await skill("test-gaps");

  assert.match(source, /coverage-gaps/);
  assert.match(source, /coverage-suggest/);
});

test("Writing Plans names every supported implementation route", async () => {
  const source = await skill("writing-plans");

  assert.match(source, /Codex Implement|codex-implement/);
  assert.match(source, /Sequential Task Orchestrator|sequential-task-orchestrator/);
  assert.match(source, /Claude Implement|claude-implement/);
  assert.doesNotMatch(source, /sol-implement/i);
});
