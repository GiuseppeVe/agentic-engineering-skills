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

test("sequential dispatch resolves its dedicated worker reference without the full implementation cycle", async () => {
  const source = await skill("sequential-task-orchestrator");
  const protocol = await readFile(path.join(skillsRoot, "sequential-task-orchestrator", "references", "runtime-protocol.md"), "utf8");
  const ref = "references/sequential-task-worker.md";
  assert.ok(source.includes(`](${ref})`));
  assert.match(protocol, /worker skill: \{\{worker_skill_ref\}\}/);
  assert.match(protocol, /Read and follow the worker skill at the exact path above/);
  assert.match(protocol, /Resolve `worker_skill_ref`/);
  assert.doesNotMatch(source + protocol, /\$codex-implement|bounded worker mode/);
  const worker = await readFile(path.join(skillsRoot, "sequential-task-orchestrator", ref), "utf8");
  assert.match(worker, /^---\nname: sequential-task-worker\n/);
  assert.match(worker, /Do not spawn agents/);
  assert.match(worker, /Scheduling, review, integration and acceptance belong to the parent/);
  assert.match(worker, /Missing scope or conflicting acceptance criteria/);
  assert.match(worker, /RED.*GREEN/s);
  assert.match(worker, /commit SHA/);
  assert.doesNotMatch(worker, /Sol|Terra|gpt-\d|claude-|required_profile|xhigh/);
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
