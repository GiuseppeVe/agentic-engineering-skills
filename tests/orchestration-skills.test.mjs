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

test("plan orchestrator dispatches dependency-ready implementation and review with explicit commit authority", async () => {
  const [source, protocol, pressure] = await Promise.all([
    skill("plan-orchestrator"),
    readFile(path.join(skillsRoot, "plan-orchestrator", "references", "runtime-protocol.md"), "utf8"),
    readFile(path.join(skillsRoot, "plan-orchestrator", "tests", "pressure-scenarios.md"), "utf8"),
  ]);
  assert.match(source, /^name: plan-orchestrator$/m);
  assert.match(source, /first five lines of its body after the frontmatter/);
  assert.match(source, /leaves its changes uncommitted/);
  assert.match(source, /Independent ready tasks may proceed concurrently only in isolated workspaces/);
  assert.match(source, /commits only when task-commit authority exists/);
  assert.match(protocol, /exactly three task inputs/);
  assert.match(protocol, /Implementation.*leaves changes uncommitted/s);
  assert.match(protocol, /Review:.*Delegate task-commit authority only when already granted/s);
  assert.match(pressure, /implementation.*uncommitted/i);
  assert.match(pressure, /commits only with task-commit authority/i);
  assert.doesNotMatch(`${source}\n${protocol}`, /\$(?:task-implement|test-driven-development)/);
});

test("implementation plan coordinator refers to the renamed plan orchestrator", async () => {
  const source = await skill("coordinating-implementation-plans");
  assert.match(source, /^name: coordinating-implementation-plans$/m);
  assert.match(source, /Per un piano isolato/);
  assert.match(source, /plan-orchestrator/);
  assert.match(source, /Avvia più thread-piano in parallelo/);
  assert.match(source, /assenza di collisioni/);
});

test("task results keep required gaps open and permit only plan-backed deferrals", async () => {
  const source = await skill("task-implement");
  assert.match(source, /failed check, missing prerequisite, or unverified criterion required of the current task as incomplete/);
  assert.match(source, /open_requirements.*deferred_to.*plan basis/s);
  assert.match(source, /without that plan basis, an open criterion required of this task makes the outcome `partial` or `blocked`/);
  assert.match(source, /not applicable only with an explicit basis in the specification or plan/);
});

test("acceptance rejects blockers, missing evidence and invented deferrals", async () => {
  const protocol = await readFile(path.join(skillsRoot, "plan-orchestrator", "references", "runtime-protocol.md"), "utf8");
  assert.match(protocol, /blocker or missing required evidence prevents `ACCEPTED`/);
  assert.match(protocol, /`complete` report with required unverified items is partial and rejected/);
  assert.match(protocol, /plan explicitly assigns it there.*not a closure criterion of the current task/s);
  assert.match(protocol, /owner instruction to proceed cannot reassign it ad hoc/);
  assert.match(protocol, /manifest check.*delivery consistency only.*does not prove semantic success/s);
});

test("review checks spec, plan, diff and evidence before committing", async () => {
  const review = await skill("test-driven-development");
  const protocol = await readFile(path.join(skillsRoot, "plan-orchestrator", "references", "runtime-protocol.md"), "utf8");
  assert.match(review, /verify its criteria and requirements against the specification, plan, diff, and evidence/);
  assert.match(protocol, /Review:.*plan\/spec paths and implementation result/s);
  assert.match(protocol, /verify the final reviewed diff and, when authorized and required, its task commit/);
  assert.match(protocol, /`final_state` evidence proves acceptance/);
  assert.match(protocol, /Earlier final-state evidence is stale/);
});

test("plan completion requires all requirements, checkboxes and tasks closed", async () => {
  const protocol = await readFile(path.join(skillsRoot, "plan-orchestrator", "references", "runtime-protocol.md"), "utf8");
  assert.match(protocol, /every required spec\/plan REQ is closed with evidence or a supported `not applicable` decision/);
  assert.match(protocol, /every required checkbox is closed, and every task is accepted/);
  assert.match(protocol, /open deferred REQ or required checkbox prevents plan completion/);
  assert.match(protocol, /open the plan's PR only if assigned and authorized/);
});
