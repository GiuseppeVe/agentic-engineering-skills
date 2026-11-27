import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { parse } from "yaml";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const skillsRoot = path.join(root, "plugins", "agentic-engineering-skills", "skills");

async function skill(name) {
  return readFile(path.join(skillsRoot, name, "SKILL.md"), "utf8");
}

async function readSkillFile(name, relativePath) {
  return readFile(path.join(skillsRoot, name, relativePath), "utf8");
}

function frontmatter(source) {
  const match = source.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  assert.ok(match, "closed YAML frontmatter required");
  return parse(match[1]);
}

test("plan-implement coordinates slice subagents, L1-L3 verification, high-risk reviews, and controller commits without hardcoded models", async () => {
  const [source, protocol, sliceContract, pressure] = await Promise.all([
    skill("plan-implement"),
    readSkillFile("plan-implement", "references/runtime-protocol.md"),
    readSkillFile("plan-implement", "references/slice-contract.md"),
    readSkillFile("plan-implement", "tests/pressure-scenarios.md"),
  ]);
  assert.match(source, /^name: plan-implement$/m);
  assert.match(source, /does not implement task code itself/);
  assert.match(source, /one persistent slice-implementer subagent/);
  assert.match(source, /Do not add a nested sub-packet layer/);
  assert.match(source, /risk: standard/);
  assert.match(source, /risk: high/);
  assert.match(source, /clean-room review subagent/);
  assert.match(source, /commits the accepted slice to the plan branch when commit authority is granted/);
  assert.match(source, /daily-workflow\.md#pr-phase/);
  assert.match(source, /references\/slice-contract\.md/);
  assert.match(source, /references\/runtime-protocol\.md/);
  assert.match(source, /references\/t3-deepseek-routing\.md/);
  assert.match(source, /references\/deepseek-vibe-profile\.md/);
  assert.match(protocol, /Parallel slices may run concurrently \*\*only\*\* when their prerequisites are integrated and their allowed files, ownership, and shared-contract surfaces are completely disjoint/);
  assert.match(protocol, /Materialize every accepted prerequisite into a dependent slice's workspace/);
  assert.match(protocol, /Exclude the slice implementer's conclusions, self-verdict, and prior review verdicts/);
  assert.match(protocol, /Earlier `final_state` evidence is stale after any code edit/);
  assert.match(protocol, /unified status `done`, `partial`, or `blocked`/);
  assert.match(pressure, /uncommitted/i);
  assert.match(pressure, /Clean-room review input/i);
  assert.match(pressure, /Accepted dependency outside the slice workspace/i);
  assert.doesNotMatch(`${source}\n${protocol}\n${sliceContract}`, /GPT-6\.1|Sonnet 5\.5|task-implement|plan-orchestrator/);
  assert.doesNotMatch(`${source}\n${protocol}`, /\$(?:task-implement|test-driven-development|plan-implement)/);
  await access(path.join(skillsRoot, "plan-implement", "references", "t3-deepseek-routing.md"));
  await access(path.join(skillsRoot, "plan-implement", "references", "deepseek-vibe-profile.md"));
});

test("acceptance rejects blockers, missing evidence, and invented deferrals", async () => {
  const [protocol, sliceContract] = await Promise.all([
    readSkillFile("plan-implement", "references/runtime-protocol.md"),
    readSkillFile("plan-implement", "references/slice-contract.md"),
  ]);
  assert.match(protocol, /`done` report with unverified required items is `partial` and rejected for acceptance/);
  assert.match(protocol, /deferred to a named later task \*\*only\*\* when the plan explicitly assigns it there/);
  assert.match(protocol, /owner chat remark can reassign a deferral ad hoc/);
  assert.match(sliceContract, /never invent or reassign a `REQ` deferral not stated in the plan/);
  assert.match(sliceContract, /missing required checks or unbacked deferrals make the status `partial` or `blocked`/);
  assert.doesNotMatch(protocol, /delivery manifest|manifest check|watchdog/i);
});

test("plan completion requires all requirements, checkboxes, and slices closed", async () => {
  const protocol = await readSkillFile("plan-implement", "references/runtime-protocol.md");
  assert.match(protocol, /every required spec\/plan `REQ-NNN` is closed with evidence or a supported `not applicable` basis/);
  assert.match(protocol, /every required checkbox is closed, every slice is accepted, and the plan's expected outcome is verified on the integrated result/);
  assert.match(protocol, /open deferred `REQ` or unchecked required item prevents plan completion/);
  assert.match(protocol, /open one plan-level PR/);
});

test("coordinating-implementation-plans is English, explicit-only on both hosts, and points to plan-implement", async () => {
  const [source, agentYaml, dialogue, manifest] = await Promise.all([
    skill("coordinating-implementation-plans"),
    readSkillFile("coordinating-implementation-plans", "agents/openai.yaml"),
    readSkillFile("coordinating-implementation-plans", "references/master-plan-dialogue.md"),
    readSkillFile("coordinating-implementation-plans", "references/package-manifest.md"),
  ]);
  const fm = frontmatter(source);
  assert.equal(fm.name, "coordinating-implementation-plans");
  assert.equal(fm["disable-model-invocation"], true);
  assert.equal(parse(agentYaml)?.policy?.allow_implicit_invocation, false);
  assert.match(source, /plan-implement/);
  assert.match(source, /daily-workflow\.md/);
  assert.match(source, /program-orchestration\.md/);
  assert.doesNotMatch(`${source}\n${dialogue}\n${manifest}`, /plan-orchestrator|PROCESSO\.md|ORCHESTRAZIONE\.md/);
});

test("development-process splits daily workflow and program orchestration in English", async () => {
  const [source, daily, program] = await Promise.all([
    skill("development-process"),
    readSkillFile("development-process", "references/daily-workflow.md"),
    readSkillFile("development-process", "references/program-orchestration.md"),
  ]);
  assert.match(source, /^name: development-process$/m);
  assert.match(source, /references\/daily-workflow\.md/);
  assert.match(source, /references\/program-orchestration\.md/);
  assert.match(daily, /## Verification/);
  assert.match(daily, /\*\*L1 — Types, schemas, and structural contracts:\*\*/);
  assert.match(daily, /\*\*L2 — Static analysis and dead code:\*\*/);
  assert.match(daily, /\*\*L3 — Behavioral, contract, and real-runtime checks:\*\*/);
  assert.match(daily, /Anti-green-washing rules:/);
  assert.match(daily, /## PR Phase/);
  assert.match(program, /## Run Conduct/);
  assert.match(program, /## Plan and Package Lifecycle/);
  assert.match(program, /## Plans and Convergence Limits/);
  await assert.rejects(access(path.join(skillsRoot, "development-process", "references", "PROCESSO.md")), { code: "ENOENT" });
  await assert.rejects(access(path.join(skillsRoot, "development-process", "references", "ORCHESTRAZIONE.md")), { code: "ENOENT" });
});

test("test-driven-development includes bug red-reproduction, modern oracles, and fixed references without generic task-reviewer overload", async () => {
  const [source, goodTests] = await Promise.all([
    skill("test-driven-development"),
    readSkillFile("test-driven-development", "writing-good-tests.md"),
  ]);
  assert.match(source, /## Bug fixes: reproduce red first/);
  assert.match(source, /daily-workflow\.md#verification/);
  assert.doesNotMatch(source, /When reviewing a task implementation, verify its criteria/);
  assert.match(goodTests, /## Choose the Right Oracle/);
  assert.match(goodTests, /Cross-package or boundary contract test/);
  assert.match(goodTests, /Property-based test/);
  assert.match(goodTests, /Real-format or real-runtime check/);
  assert.match(goodTests, /writing-for-agents/);
  assert.doesNotMatch(goodTests, /superpowers:writing-skills/);
});

test("writing-plans uses contract-based template with risk tags, optional slices, and plan-implement handoff", async () => {
  const source = await skill("writing-plans");
  assert.match(source, /Every plan starts with this header, followed by `## Expected Outcome`,\s+`## Requirements Inventory`, and `## File Structure` before the tasks\./);
  assert.match(source, /Steps use checkbox \(`- \[ \]`\) syntax for tracking\.\s+\*\*Architecture:\*\* \[2-3 sentences\]\s+\*\*Tech Stack:\*\* \[Key technologies\/libraries\]\s+---\s+```/);
  assert.match(source, /### Task N: \[Name\]/);
  assert.match(source, /\*\*Expected outcome:\*\* \[Observable result this task delivers within its scope\.\]/);
  assert.match(source, /\*\*Satisfies:\*\* REQ-003, REQ-007/);
  assert.match(source, /\*\*Risk:\*\* standard \| high/);
  assert.match(source, /## Slice N:/);
  assert.match(source, /\*\*Files:\*\* \[Exact paths and ownership\.\]/);
  assert.match(source, /\*\*Contracts and constraints:\*\* \[Interfaces, required behavior, and dependencies\s+that affect this task\.\]/);
  assert.match(source, /- \[ \] \[Implement the behavior using the identified entry point and existing contracts\.\]/);
  assert.match(source, /- \[ \] \[Run the relevant check and record the result against the cited REQs\.\]/);
  assert.match(source, /Include exact code\s+or data shapes when they encode an agreed contract, a decision, or a test\s+case whose details affect correctness\./);
  assert.match(source, /Resolve placeholders and fill gaps in paths, contracts, or checks\./);
  assert.match(source, /Verify that each task's expected outcome follows from its mapped REQs/);
  assert.match(source, /plan-implement/);
  assert.doesNotMatch(source, /```python|pytest|test_specific_behavior|Write the failing test|Step 1:|After the outcome, state the approach|dispatching-parallel-agents|task-implement|plan-orchestrator|GPT-6\.1|Sonnet 5\.5/);
});

test("simplify and retro reflect lightweight verification and host-native code review", async () => {
  const [simplifySource, retroSource] = await Promise.all([
    skill("simplify"),
    skill("retro"),
  ]);
  assert.match(simplifySource, /native code[- ]review/i);
  assert.match(retroSource, /deterministic check/i);
  assert.match(retroSource, /Operational metrics/i);
});

test("updated core skills maintain cross-host invocation metadata parity", async () => {
  for (const [name, expectedImplicit] of [
    ["development-process", true],
    ["plan-implement", true],
    ["test-driven-development", true],
    ["simplify", true],
    ["coordinating-implementation-plans", false],
    ["master-orchestrator", false],
  ]) {
    const fm = frontmatter(await skill(name));
    const yaml = parse(await readSkillFile(name, "agents/openai.yaml"));
    assert.equal(fm["disable-model-invocation"] === true, !expectedImplicit, `${name} Claude disable-model-invocation mismatch`);
    assert.equal(yaml?.policy?.allow_implicit_invocation, expectedImplicit, `${name} Codex allow_implicit_invocation mismatch`);
  }
});
