import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const skillRoot = path.join(root, "plugins", "agentic-engineering-skills", "claude-skills", "claude-implement");

async function listFiles(directory, prefix = "") {
  const entries = await readdir(path.join(directory, prefix), { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const relative = path.join(prefix, entry.name);
    return entry.isDirectory() ? listFiles(directory, relative) : [relative];
  }));
  return files.flat().map((file) => file.split(path.sep).join("/")).sort();
}

async function readSkill(relativePath) {
  return readFile(path.join(skillRoot, relativePath), "utf8");
}

test("Claude Implement carries current Alfe references and role attachments", async () => {
  const expectedFiles = [
    "SKILL.md",
    "agents/clean-room-reviewer.md",
    "agents/planner.md",
    "agents/sol-audit-reviewer.md",
    "agents/sol-dependency-analyst.md",
    "agents/sol-invariants-analyst.md",
    "agents/sol-test-author.md",
    "agents/sol-test-strategist.md",
    "agents/spec-aware-tester.md",
    "agents/worker.md",
    "references/agent-roles.md",
    "references/distribution.md",
    "references/implementation-philosophy.md",
    "references/model-routing.md",
    "references/packet-contract.md",
    "references/review-protocol.md",
    "references/work-isolation.md",
    "tests/forward-tests.md",
  ].sort();
  assert.deepEqual(await listFiles(skillRoot), expectedFiles);

  const skill = await readSkill("SKILL.md");
  for (const [, reference] of skill.matchAll(/`(references\/[\w-]+\.md)`/g)) {
    assert.ok(expectedFiles.includes(reference), `required reading must ship: ${reference}`);
  }
  assert.equal([...skill.matchAll(/`(references\/[\w-]+\.md)`/g)].length, 7,
    "skill must link all seven normative references");

  const markdownFiles = await listFiles(skillRoot);
  for (const relative of markdownFiles.filter((file) => file.endsWith(".md"))) {
    const source = await readSkill(relative);
    for (const [, target] of source.matchAll(/\[[^\]]+\]\(([^)]+)\)/g)) {
      if (/^(?:[a-z]+:|#)/i.test(target)) continue;
      const targetPath = target.split("#", 1)[0];
      assert.ok(targetPath, `${relative}: empty local link`);
      const resolved = path.resolve(skillRoot, path.dirname(relative), targetPath);
      const relativeTarget = path.relative(skillRoot, resolved);
      assert.ok(!relativeTarget.startsWith(`..${path.sep}`) && relativeTarget !== "..",
        `${relative}: link escapes skill directory: ${target}`);
      await readFile(resolved).catch((error) => {
        if (error.code === "ENOENT") assert.fail(`${relative}: broken local link: ${target}`);
        throw error;
      });
    }
  }
});

test("Claude Implement contracts match current Alfe workflow and stay portable", async () => {
  const [skill, roleMap, routing, packet, isolation, review, worker, forwardTests] = await Promise.all([
    readSkill("SKILL.md"),
    readSkill("references/agent-roles.md"),
    readSkill("references/model-routing.md"),
    readSkill("references/packet-contract.md"),
    readSkill("references/work-isolation.md"),
    readSkill("references/review-protocol.md"),
    readSkill("agents/worker.md"),
    readSkill("tests/forward-tests.md"),
  ]);

  for (const attachment of [
    "clean-room-reviewer", "planner", "sol-audit-reviewer", "sol-dependency-analyst",
    "sol-invariants-analyst", "sol-test-author", "sol-test-strategist", "spec-aware-tester", "worker",
  ]) {
    assert.ok(roleMap.includes(`agents/${attachment}.md`), `role map must identify ${attachment}`);
  }
  assert.match(skill, /original, unabridged user-provided specification/);
  assert.match(skill, /Hard boundary rule/);
  assert.match(skill, /fresh clean reviewer/);
  assert.match(skill, /new agent invocation\/context/);
  assert.match(routing, /claude-opus-5-5/);
  assert.match(routing, /claude-sonnet-5-5/);
  assert.match(routing, /A return without `Status:` is treated as BLOCKED/);
  for (const field of ["Status: DONE | BLOCKED", "Change summary:", "Tests and results:", "Assumptions:", "Deviations:", "Integration risks:", "Files changed:"]) {
    assert.ok(worker.includes(field), `worker attachment requires ${field}`);
  }
  assert.match(worker, /Commit:/);
  assert.match(packet, /shared-contract surfaces/);
  assert.match(packet, /Return `DONE` only with a verifiable packet commit SHA/);
  assert.match(isolation, /explicit user instructions first, then repository and host policy/);
  assert.match(isolation, /Do not impose this plugin's branch or path convention/);
  assert.match(isolation, /If remote verification fails, return `BLOCKED`/);
  assert.match(isolation, /never fall back to local `main`, current `HEAD`, or an unverified cached remote ref/);
  assert.doesNotMatch(isolation, /claude\/implement-<slug>|\.codex\/worktrees|\.claude\/worktrees/);
  assert.match(isolation, /never from a later integration or packet head/);
  assert.match(isolation, /Packet worktrees must be siblings/);
  assert.match(review, /Any failed test or material finding blocks further integration/);
  for (const scenario of ["Shared interface escape", "Worker notes sent to clean reviewer", "Green tests, violated invariant", "Worktree topology and frozen base", "Capacity, disjointness, and serial fallback", "Test-author allowed-files escape", "Serial integration, combined tests, and shared-contract conflict", "Fresh contexts and host routing", "Bounded worker in the shared run worktree"]) {
    assert.ok(forwardTests.includes(scenario), `forward validation must cover: ${scenario}`);
  }
  assert.match(forwardTests, /Remote-base subcase[\s\S]*?Remote-base expected outcome[\s\S]*?Remote-base fail criterion/);

  const files = await listFiles(skillRoot);
  for (const relative of files.filter((file) => file.endsWith(".md"))) {
    const contents = await readSkill(relative);
    assert.doesNotMatch(contents, /alfe_AI_app|[A-Z]:\\Users\\|\/Users\/[^/]+\//i,
      `${relative}: plugin skill must not depend on a project-specific absolute path`);
  }
});

test("bounded dispatch uses the parent's shared worktree and leaves review to the parent", async () => {
  const skill = await readSkill("SKILL.md");
  assert.match(skill, /^description:.*bounded worker/m, "bounded dispatch must be discoverable");
  const bounded = skill.match(/^## Bounded worker mode\r?\n([\s\S]*?)(?=^## Controller mode\r?$)/m)?.[1];
  assert.ok(bounded, "bounded mode must precede and exit before the controller mode");
  assert.match(bounded, /explicitly dispatched as a bounded worker/i);
  assert.match(bounded, /\[the worker (?:role|contract)\]\(agents\/worker\.md\)/i);
  assert.match(bounded, /one (?:assigned |supplied )?packet/i);
  assert.match(bounded, /shared worktree and (?:run )?branch/i);
  assert.match(bounded, /do not create (?:an? )?(?:own |another |new )?worktree/i);
  assert.match(bounded, /do not (?:invoke|run|start).*controller/i);
  assert.match(bounded, /parent.*review and integration/i);
  assert.match(bounded, /return.*remaining sections.*controller mode/i);
  assert.match(bounded, /other invocations.*controller mode/i);
  assert.match(bounded, /(?:checks|tests).*(?:evidence|results)/i);
  assert.match(bounded, /commit/i);
  assert.match(bounded, /(?:authorization|permission)/i);
  assert.match(bounded, /BLOCKED/);
});

test("controller dispatch retains planning, isolation and independent approval", async () => {
  const skill = await readSkill("SKILL.md");
  const controller = skill.match(/^## Controller mode\r?\n([\s\S]*)$/m)?.[1];
  assert.ok(controller, "ordinary dispatch must retain the full controller path");
  for (const requirement of [
    /references\/implementation-philosophy\.md/,
    /references\/packet-contract\.md/,
    /references\/work-isolation\.md/,
    /new agent invocation\/context/,
    /fresh clean reviewer/,
    /Only the controller may modify the integration branch/,
  ]) {
    assert.match(controller, requirement);
  }
});

test("worker and test-author roles agree with model routing", async () => {
  const [author, worker, routing, roleMap, isolation, distribution, forwardTests] = await Promise.all([
    readSkill("agents/sol-test-author.md"),
    readSkill("agents/worker.md"),
    readSkill("references/model-routing.md"),
    readSkill("references/agent-roles.md"),
    readSkill("references/work-isolation.md"),
    readSkill("references/distribution.md"),
    readSkill("tests/forward-tests.md"),
  ]);
  assert.match(author, /^model: claude-sonnet-5-5$/m);
  assert.match(author, /^effort: medium$/m);
  assert.match(worker, /^model: claude-sonnet-5-5$/m);
  assert.match(worker, /^effort: high$/m);
  assert.ok(routing.includes("| Bounded packet worker | `claude-sonnet-5-5` | `high` |"));
  assert.match(routing, /^\| Test author \| `claude-sonnet-5-5` \| `medium` \|$/m);
  assert.ok(roleMap.includes("| Test author |"), "role map uses a neutral label");
  for (const [name, source] of [
    ["test-author attachment", author],
    ["role map", roleMap],
    ["work isolation", isolation],
    ["distribution", distribution],
    ["forward tests", forwardTests],
  ]) {
    assert.doesNotMatch(source, /Opus[- ]test[- ]author/i, name + " must not mislabel the test author");
  }
});
