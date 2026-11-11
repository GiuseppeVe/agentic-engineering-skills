import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const pluginRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "plugins", "agentic-engineering-skills");

test("task implementation packets define scope, ownership, contracts and evidence", async () => {
  const [skill, packet] = await Promise.all([
    readFile(path.join(pluginRoot, "skills/task-implement/SKILL.md"), "utf8"),
    readFile(path.join(pluginRoot, "skills/task-implement/references/packet-contract.md"), "utf8"),
  ]);
  assert.match(skill, /Break the task into the smallest coherent implementation packets/);
  assert.match(skill, /clear file ownership, interfaces, constraints, and acceptance criteria/);
  assert.match(skill, /Sequence dependent packets/);
  assert.match(skill, /Parallelize only disjoint work with no unresolved shared dependency/);
  assert.match(skill, /pause that packet and report the exact dependency/);
  assert.match(packet, /allowed files/);
  assert.match(packet, /file ownership/);
  assert.match(packet, /shared-contract surfaces/);
  assert.match(packet, /acceptance criteria/);
  assert.match(packet, /expected evidence/);
  assert.match(packet, /BLOCKED/);
});

test("task implement keeps implementation authority and final review with the parent workflow", async () => {
  const source = await readFile(path.join(pluginRoot, "skills/task-implement/SKILL.md"), "utf8");
  assert.match(source, /Implement exactly one task assigned by a parent orchestrator/);
  assert.match(source, /does not orchestrate other plan tasks/);
  assert.match(source, /excludes review of the task's implementation/);
  assert.match(source, /Never infer permission to commit, push, open a PR, merge, deploy/);
  assert.match(source, /changes are summarized for the parent/);
  assert.doesNotMatch(source, /clean-room reviewer|fresh independent reviewer|approval gate/i);
});
