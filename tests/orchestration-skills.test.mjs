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
  assert.doesNotMatch(worker, /Sol|Terra|gpt-\d|claude-|required_profile|model_reasoning_effort|effort\s*[:=]|\b(?:xhigh|medium|high)\b/);
});

test("implementation attachments use neutral names and host-specific approved routing", async () => {
  for (const host of ["codex", "claude"]) {
    const name = `${host}-implement`;
    const source = await skill(name);
    assert.doesNotMatch(source, /sol-(planner|spec-aware-tester|clean-room-reviewer)|gpt-5\.6|--model (?:fable|opus)\b/);
    for (const role of ["planner", "spec-aware-tester", "clean-room-reviewer"]) {
      assert.ok(source.includes(`agents/${role}.md`));
      const attachment = await readFile(path.join(skillsRoot, name, "agents", `${role}.md`), "utf8");
      assert.match(attachment, new RegExp(`^name: ${role}$`, "m"));
      if (host === "codex") {
        assert.match(attachment, new RegExp(`^required_profile: ${role}$`, "m"));
        assert.match(source, new RegExp(`codex -p ${role} `));
        assert.match(source, /\$CODEX_HOME\/<name>\.config\.toml/);
        assert.match(source, /gpt-6\.1-sol/);
      } else {
        assert.match(attachment, /^model: claude-opus-5-5$/m);
        assert.match(attachment, new RegExp(`^effort: ${role === "planner" ? "medium" : "high"}$`, "m"));
        assert.match(source, new RegExp(`--agent ${role} --model claude-opus-5-5 --effort ${role === "planner" ? "medium" : "high"}`));
      }
    }
    const worker = await readFile(path.join(skillsRoot, name, "agents", "terra-worker.md"), "utf8");
    assert.match(worker, host === "codex" ? /^required_profile: worker$/m : /^model: claude-sonnet-5-5$/m);
    if (host === "claude") assert.match(worker, /^effort: high$/m);
    assert.match(source, /controller\/orchestrator.*separate contexts|Context isolation contract/s);
    assert.match(source, /original, unabridged/);
  }
  const codex = await skill("codex-implement");
  assert.match(codex, /first retry, second retry in this order/);
  assert.match(codex, /once more with `worker` \(Sol\/high\) in another fresh context/);
});

test("sequential calling layer selects Sol/high worker and Sol/xhigh reviewer without changing queue", async () => {
  const source = await skill("sequential-task-orchestrator");
  const protocol = await readFile(path.join(skillsRoot, "sequential-task-orchestrator", "references", "runtime-protocol.md"), "utf8");
  assert.match(source, /model `gpt-6\.1-sol` and thinking `high`/);
  assert.match(source, /model `gpt-6\.1-sol` and thinking `xhigh`/);
  assert.match(protocol, /\| Implementer \| `gpt-6\.1-sol` \| `high` \|/);
  assert.match(protocol, /\| Reviewer \| `gpt-6\.1-sol` \| `xhigh` \|/);
  assert.match(source, /One side-chat slot only/);
  assert.match(protocol, /Even if a later task is independent, keep it queued/);
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
