import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const skillRoot = path.join(root, "plugins", "agentic-engineering-skills", "skills", "task-implement");

test("shared Task Implement preserves the approved model split and task boundary", async () => {
  const [skill, packet] = await Promise.all([
    readFile(path.join(skillRoot, "SKILL.md"), "utf8"),
    readFile(path.join(skillRoot, "references", "packet-contract.md"), "utf8"),
  ]);
  assert.match(skill, /^name: task-implement$/m);
  assert.match(skill, /When task materials do not specify compatible routing/);
  assert.match(skill, /Codex uses GPT-6\.1 Sol\/high for orchestration and GPT-6\.1 Terra\/high/);
  assert.match(skill, /Claude Code uses Sonnet 5\.5\/high for orchestration and Sonnet 5\.5\/medium/);
  assert.match(skill, /explicit owner- or plan-selected available model and effort takes precedence/);
  assert.match(skill, /Implement exactly one task assigned by a parent orchestrator/);
  assert.match(skill, /scope is implementation only and excludes review of the task's implementation/);
  assert.match(skill, /The parent provides only: the instruction for the assigned task, its implementation plan, the governing specification, and this skill/);
  assert.match(skill, /Integrate packet results within the assigned task/);
  assert.match(packet, /allowed files/);
  assert.match(packet, /disjoint allowed files/);
  assert.match(packet, /GPT-6\.1 Sol with high effort on Codex/);
  assert.match(packet, /Sonnet 5\.5 with high effort on Claude Code/);
  assert.match(skill, /Use `process` for historical development evidence/);
  assert.match(skill, /Use `final_state` for evidence that supports acceptance/);
  assert.doesNotMatch(skill, /fresh clean-room approval gate|clean-room reviewer|review protocol/i);
});
