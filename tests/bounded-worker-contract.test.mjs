import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const pluginRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "plugins", "agentic-engineering-skills");

test("plan-implement slice contract defines scope, ownership, verification, and lightweight handoff", async () => {
  const [skill, slice] = await Promise.all([
    readFile(path.join(pluginRoot, "skills/plan-implement/SKILL.md"), "utf8"),
    readFile(path.join(pluginRoot, "skills/plan-implement/references/slice-contract.md"), "utf8"),
  ]);
  assert.match(skill, /Keep slices disjoint in file ownership and shared-contract surfaces before running them in parallel/);
  assert.match(skill, /one persistent slice-implementer subagent/);
  assert.match(slice, /allowed files/);
  assert.match(slice, /Scope is binding/);
  assert.match(slice, /return `blocked`/);
  assert.match(slice, /Leave verified changes uncommitted for `plan-implement` to verify and commit/);
  assert.match(slice, /No green-washing|no green-washing/i);
  assert.match(slice, /`process`.*`final_state`/);
  assert.match(slice, /`done`, `partial`, or `blocked`/);
});

test("slice implementers leave commit and publication authority with plan-implement", async () => {
  const slice = await readFile(path.join(pluginRoot, "skills/plan-implement/references/slice-contract.md"), "utf8");
  assert.match(slice, /without spawning nested sub-packet agents unless explicitly authorized/);
  assert.match(slice, /Never infer permission to commit, push, open a PR, merge, deploy/);
  assert.match(slice, /Lightweight slice handoff/);
});
