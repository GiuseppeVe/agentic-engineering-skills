import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const skillsRoot = path.join(root, "plugins", "agentic-engineering-skills", "skills");

async function skill(name) {
  return readFile(path.join(skillsRoot, name, "SKILL.md"), "utf8");
}

test("task implement exposes one implementation-only task workflow and host model routing", async () => {
  const source = await skill("task-implement");
  const body = source.split(/^---\s*$/m).at(2).trimStart();
  const firstFiveBodyLines = body.split(/\r?\n/).slice(0, 5).join("\n");
  assert.match(source, /^name: task-implement$/m);
  assert.match(firstFiveBodyLines, /GPT-6\.1 Sol\/high/);
  assert.match(firstFiveBodyLines, /GPT-6\.1 Terra\/high/);
  assert.match(firstFiveBodyLines, /Sonnet 5\.5\/high/);
  assert.match(firstFiveBodyLines, /Sonnet 5\.5\/medium/);
  assert.match(source, /Implement exactly one task assigned by a parent orchestrator/);
  assert.match(source, /scope is implementation only and excludes review of the task's implementation/);
  assert.match(source, /Never infer permission to commit, push, open a PR, merge, deploy/);
  assert.match(source, /references\/packet-contract\.md/);
  assert.doesNotMatch(source, /clean-room reviewer|clean-room approval|review protocol/i);
  await access(path.join(skillsRoot, "task-implement", "references", "packet-contract.md"));
});

test("plan orchestrator dispatches implementation and review sequentially and commits after fixes", async () => {
  const [source, protocol, pressure] = await Promise.all([
    skill("plan-orchestrator"),
    readFile(path.join(skillsRoot, "plan-orchestrator", "references", "runtime-protocol.md"), "utf8"),
    readFile(path.join(skillsRoot, "plan-orchestrator", "tests", "pressure-scenarios.md"), "utf8"),
  ]);
  assert.match(source, /^name: plan-orchestrator$/m);
  assert.match(source, /first five lines of its body after the frontmatter/);
  assert.match(source, /leaves its changes uncommitted/);
  assert.match(source, /reviewer identifies and fixes in-scope problems/);
  assert.match(source, /commits the accepted task result/);
  assert.match(protocol, /exactly three task inputs/);
  assert.match(protocol, /Implementation.*leaves changes uncommitted/s);
  assert.match(protocol, /Review.*explicitly authorize this thread to commit/s);
  assert.match(pressure, /implementation.*uncommitted/i);
  assert.match(pressure, /review.*fixes.*commits/i);
  assert.doesNotMatch(`${source}\n${protocol}`, /\$(?:task-implement|test-driven-development)/);
});

test("implementation plan coordinator refers to the renamed plan orchestrator", async () => {
  const source = await skill("coordinating-implementation-plans");
  assert.match(source, /^name: coordinating-implementation-plans$/m);
  assert.match(source, /For a plan isolato/);
  assert.match(source, /plan-orchestrator/);
  assert.match(source, /Avvia più thread-piano in parallelo/);
  assert.match(source, /senza collisioni/);
});
