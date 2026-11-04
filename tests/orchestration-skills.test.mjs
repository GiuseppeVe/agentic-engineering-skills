import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const skillsRoot = path.join(root, "plugins", "agentic-engineering-skills", "skills");

function skillDirectory(name) {
  return path.join(root, "plugins", "agentic-engineering-skills", name === "claude-implement" ? "claude-skills" : "skills", name);
}

async function skill(name) {
  return readFile(path.join(skillDirectory(name), "SKILL.md"), "utf8");
}

test("orchestrator package exposes a universal skill and a resolvable runtime", async () => {
  const source = await skill("sequential-task-orchestrator");
  assert.doesNotMatch(source, /\b(?:claude|codex|cli)\b/i);
  const protocol = await readFile(path.join(skillsRoot, "sequential-task-orchestrator", "references", "runtime-protocol.md"), "utf8");
  assert.doesNotMatch(protocol, /\b(?:claude|codex|cli)\b/i);
  assert.match(source, /references\/runtime-protocol\.md/);
  assert.match(source, /test-driven-development/);
  assert.match(source, /visible, subordinate subthreads/);
  assert.match(protocol, /one slot: implementation \*\*or\*\* review/);
});

test("implementation attachments use neutral names and host-specific approved routing", async () => {
  for (const host of ["codex", "claude"]) {
    const name = `${host}-implement`;
    const source = await skill(name);
    const roleSource = host === "claude"
      ? await readFile(path.join(skillDirectory(name), "references", "agent-roles.md"), "utf8")
      : source;
    const routingSource = host === "claude"
      ? await readFile(path.join(skillDirectory(name), "references", "model-routing.md"), "utf8")
      : source;
    assert.doesNotMatch(source, /sol-(planner|spec-aware-tester|clean-room-reviewer)|gpt-5\.6|--model (?:fable|opus)\b/);
    for (const role of ["planner", "spec-aware-tester", "clean-room-reviewer"]) {
      assert.ok(roleSource.includes(`agents/${role}.md`));
      const attachment = await readFile(path.join(skillDirectory(name), "agents", `${role}.md`), "utf8");
      assert.match(attachment, new RegExp(`^name: ${role}$`, "m"));
      if (host === "codex") {
        assert.match(attachment, new RegExp(`^required_profile: ${role}$`, "m"));
        assert.match(source, new RegExp(`codex -p ${role} `));
        assert.match(source, /\$CODEX_HOME\/<name>\.config\.toml/);
        assert.match(source, /gpt-6\.1-sol/);
      } else {
        assert.match(attachment, /^model: claude-opus-5-5$/m);
        assert.match(attachment, new RegExp(`^effort: ${role === "planner" ? "medium" : "high"}$`, "m"));
        assert.match(routingSource, new RegExp(`claude -p --model claude-opus-5-5 --effort ${role === "planner" ? "medium" : "high"}`));
        assert.doesNotMatch(routingSource, /--agent\s+(?:planner|worker|spec-aware-tester|clean-room-reviewer)\b/);
      }
    }
    const workerAttachment = host === "claude" ? "worker.md" : "terra-worker.md";
    const worker = await readFile(path.join(skillDirectory(name), "agents", workerAttachment), "utf8");
    assert.match(worker, host === "codex" ? /^required_profile: worker$/m : /^model: claude-sonnet-5-5$/m);
    if (host === "claude") assert.match(worker, /^effort: high$/m);
    assert.match(source, /controller\/orchestrator.*separate contexts|Context isolation contract/s);
    assert.match(source, /original, unabridged/);
  }
  const codex = await skill("codex-implement");
  assert.match(codex, /first retry, second retry in this order/);
  assert.match(codex, /once more with `worker` \(Sol\/high\) in another fresh context/);
});

test("Writing Plans names every supported implementation route", async () => {
  const source = await skill("writing-plans");

  assert.match(source, /Codex Implement|codex-implement/);
  assert.match(source, /Sequential Task Orchestrator|sequential-task-orchestrator/);
  assert.match(source, /Claude Implement|claude-implement/);
  assert.doesNotMatch(source, /sol-implement/i);
});


test("Writing Plans respects existing execution authorization", async () => {
  const source = await skill("writing-plans");
  assert.match(source, /execution is already authorized, continue within that authority/i);
  assert.match(source, /already authorized execution, choose an available mode[\s\S]*?and continue/i);
  assert.doesNotMatch(source, /wait for the user.s choice/i);
});

test("Writing Plans respects user location instructions and routes swarm generically", async () => {
  const source = await skill("writing-plans");

  assert.match(source, /Respect system and host constraints\. Within those constraints, follow explicit user instructions over repository defaults/);
  assert.match(source, /only when neither provides a location/);
  assert.match(source, /generic term .swarm. means multi-agent coordination/i);
  assert.doesNotMatch(source, /swarm-orchestration/i);
});
