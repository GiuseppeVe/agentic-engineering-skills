import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const manifestPath = path.join(root, "manifests", "agent-profiles.json");
const expectedProfiles = [
  "cleanup",
  "controller",
  "implementer",
  "planner",
  "researcher",
  "reviewer",
  "test-runner",
];
const requiredSections = [
  "Purpose",
  "Input",
  "Allowed actions",
  "Forbidden actions",
  "Structured output",
  "Validation",
  "Failure path",
];
const envelopeFields = ["role", "status", "summary", "evidence", "risks", "nextAction"];
const upstreamRepository = "https://github.com/JuliusBrussee/caveman";
const upstreamRevision = "0d95a81d35a9f2d123a5e9430d1cfc43d55f1bb0";
const upstreamProfilePath = "skills/cavecrew/SKILL.md";
const licensePath = "plugins/agentic-engineering-skills/licenses/JuliusBrussee-caveman-LICENSE";
const noticePath = "THIRD_PARTY_NOTICES.md";
const sourceSpecPath = "docs/superpowers/plans/2026-07-12-agent-profiles-pack.md";
const roleLineMarkers = {
  cleanup: "deletedPaths",
  controller: "Route",
  implementer: "changedFiles",
  planner: "acceptanceCriteria",
  researcher: "verifiedFindings",
  reviewer: "findings",
  "test-runner": "failedCommands",
};

async function loadManifest() {
  const source = await readFile(manifestPath, "utf8").catch((error) => {
    if (error.code === "ENOENT") {
      assert.fail(`missing required profile manifest: ${manifestPath}`);
    }
    throw error;
  });
  return JSON.parse(source);
}

async function loadProfiles() {
  const manifest = await loadManifest();
  assert.ok(Array.isArray(manifest.profiles), "agent profile manifest must expose profiles[]");

  return Promise.all(manifest.profiles.map(async (entry) => {
    assert.equal(typeof entry.name, "string", "profile entry requires name");
    assert.equal(typeof entry.path, "string", `${entry.name}: profile entry requires path`);
    assert.ok(!path.isAbsolute(entry.path), `${entry.name}: path must be repository-relative`);
    assert.equal(path.normalize(entry.path).startsWith(".."), false, `${entry.name}: path escapes repository`);
    const absolutePath = path.resolve(root, entry.path);
    const payloadBytes = await readFile(absolutePath).catch((error) => {
      if (error.code === "ENOENT") assert.fail(`${entry.name}: missing profile payload ${absolutePath}`);
      throw error;
    });
    return { ...entry, absolutePath, payload: payloadBytes.toString("utf8"), payloadBytes };
  }));
}

test("profile manifest declares exact profile inventory", async () => {
  const profiles = await loadProfiles();
  assert.deepEqual(profiles.map(({ name }) => name).sort(), expectedProfiles);
  assert.equal(new Set(profiles.map(({ path: profilePath }) => profilePath)).size, expectedProfiles.length);
});

test("profile provenance is adapted, pinned, quarantined, licensed, and byte-verifiable", async () => {
  const profiles = await loadProfiles();
  const sourceSpecLines = (await readFile(path.resolve(root, sourceSpecPath), "utf8")).split(/\r?\n/);
  assert.equal(profiles.length, 7);

  for (const profile of profiles) {
    assert.equal(profile.status, "adapted", `${profile.name}: wrong adaptation status`);
    assert.equal(profile.source, upstreamRepository, `${profile.name}: wrong source URL`);
    assert.equal(profile.revision, upstreamRevision, `${profile.name}: wrong pinned revision`);
    assert.equal(profile.upstreamPath, upstreamProfilePath, `${profile.name}: wrong upstream Cavecrew path`);
    const expectedCandidatePath = `agent-profiles/${profile.name}.md`;
    assert.equal(profile.candidatePath, expectedCandidatePath, `${profile.name}: wrong quarantined candidatePath`);
    assert.equal(typeof profile.payloadPath, "string", `${profile.name}: explicit payloadPath required`);
    assert.equal(profile.payloadPath, profile.path, `${profile.name}: payload path must equal loaded path`);
    assert.match(profile.sha256, /^[a-f0-9]{64}$/, `${profile.name}: sha256 must be lowercase SHA-256`);
    assert.equal(createHash("sha256").update(profile.payloadBytes).digest("hex"), profile.sha256,
      `${profile.name}: sha256 does not match exact UTF-8 payload bytes`);
    assert.equal(profile.license, "MIT", `${profile.name}: wrong license`);
    assert.equal(profile.noticePath, noticePath, `${profile.name}: explicit noticePath required`);
    assert.equal(profile.licensePath, licensePath, `${profile.name}: wrong MIT licensePath`);
    assert.equal(profile.sourceSpecPath, sourceSpecPath, `${profile.name}: wrong source spec path`);
    assert.equal(typeof profile.sourceSpecRoleLine, "string", `${profile.name}: sourceSpecRoleLine required`);
    assert.equal(profile.sourceSpecRoleLine.trim(), profile.sourceSpecRoleLine,
      `${profile.name}: sourceSpecRoleLine must be one exact line`);
    assert.ok(profile.sourceSpecRoleLine.length > 0 && !profile.sourceSpecRoleLine.includes("\n"),
      `${profile.name}: sourceSpecRoleLine must be nonempty single line`);
    assert.ok(sourceSpecLines.includes(profile.sourceSpecRoleLine),
      `${profile.name}: sourceSpecRoleLine is not an exact source-spec line`);
    assert.ok(profile.sourceSpecRoleLine.includes(`\`${profile.name}\``),
      `${profile.name}: sourceSpecRoleLine must contain backticked role`);
    assert.ok(profile.sourceSpecRoleLine.includes(roleLineMarkers[profile.name]),
      `${profile.name}: sourceSpecRoleLine lacks authoritative role responsibility/output marker`);
    await readFile(path.resolve(root, licensePath), "utf8");
  }
});

test("profile provenance joins existing cavecrew third-party notice", async () => {
  const profiles = await loadProfiles();
  assert.deepEqual([...new Set(profiles.map(({ noticePath: manifestNoticePath }) => manifestNoticePath))], [noticePath]);
  const notice = await readFile(path.resolve(root, profiles[0].noticePath), "utf8");
  const row = notice.split("\n").find((line) => /^\| `cavecrew` \|/.test(line));
  assert.ok(row, "missing cavecrew THIRD_PARTY_NOTICES row");
  assert.match(row, /\[JuliusBrussee\/caveman\]\(https:\/\/github\.com\/JuliusBrussee\/caveman\)/);
  assert.ok(row.includes(`\`${upstreamRevision}\``), "cavecrew notice revision mismatch");
  assert.ok(row.includes("| MIT |"), "cavecrew notice license mismatch");
  assert.ok(row.includes(`\`${licensePath}\``), "cavecrew notice path mismatch");

  for (const profile of profiles) {
    assert.equal(profile.source, upstreamRepository);
    assert.equal(profile.revision, upstreamRevision);
    assert.equal(profile.noticePath, noticePath);
    assert.equal(profile.licensePath, licensePath);
  }
});

test.skip("documentation guide maps every agent profile to role and use case until Task 3", () => {});
test.skip("workflow documentation maps every agent profile into orchestration until Task 3", () => {});

test("every profile defines complete contract sections in canonical order", async () => {
  for (const { name, payload } of await loadProfiles()) {
    const headings = [...payload.matchAll(/^## (.+)$/gm)].map((match) => match[1]);
    assert.deepEqual(headings, requiredSections, `${name}: wrong contract section inventory or order`);
    for (const section of requiredSections) {
      assert.match(payload, new RegExp(`^## ${section}\\r?\\n(?!\\s*(?:##|$))`, "m"), `${name}: empty ${section}`);
    }
  }
});

test("profiles stay host-neutral and do not invoke host orchestration primitives", async () => {
  const forbiddenPrimitives = [
    /(?:^|\n)\s*(?:[-*+]\s+)?\/[a-z][\w-]*(?=\s|$)/im,
    /`\/[a-z][\w-]*`/i,
    /(?:^|[\s([{"'])\/[a-z][\w-]*(?=[\s.,;:!?)}\]"']|$)/im,
    /(?:^|[\\/])\.(?:claude|codex)(?:[\\/]|$)/im,
    /\b(?:CLAUDE|AGENTS)\.md\b/,
    /\b(?:Agent|Task|Bash|Edit|Write|Read|Glob|Grep|Skill)\s*\(/,
    /\b(?:Agent|Task|Bash|Edit|Write|Read|Glob|Grep|Skill|AskUserQuestion|TodoWrite|EnterWorktree) tool\b/,
    /\bAskUserQuestion\b/,
    /\bTodoWrite\b/,
    /\bEnterWorktree\b/,
    /\bsubagent_type\b/,
    /\b(?:multi_agent_v1|spawn_agent|send_message|followup_task|delegate(?:_task)?)\b/,
  ];

  for (const { name, payload } of await loadProfiles()) {
    for (const primitive of forbiddenPrimitives) {
      assert.doesNotMatch(payload, primitive, `${name}: leaks forbidden host primitive ${primitive}`);
    }
  }
});

test("every profile publishes common result envelope", async () => {
  for (const { name, payload } of await loadProfiles()) {
    const output = payload.split(/^## Structured output$/m)[1]?.split(/^## /m)[0] ?? "";
    const keys = [...output.matchAll(/^([a-z][A-Za-z]*):/gm)].map((match) => match[1]);
    for (const field of envelopeFields) {
      assert.equal(keys.filter((key) => key === field).length, 1, `${name}: envelope requires one ${field} field`);
    }
    assert.match(output, /^status:\s*(?:completed\s*\|\s*blocked\s*\|\s*failed|completed,\s*blocked,\s*failed)$/m,
      `${name}: status must declare exact completed/blocked/failed enum`);
    assert.doesNotMatch(output, /\b(?:DONE|DONE_WITH_CONCERNS|NEEDS_CONTEXT|BLOCKED)\b/,
      `${name}: legacy implementer statuses are forbidden`);
  }
});

const semanticCases = {
  cleanup: [
    /\b(?:explicit|assigned|bounded) (?:cleanup )?scope\b/i,
    /\bresolve\b[^\n]*\bpath/i,
    /\bvalidat(?:e|ion)\b[^\n]*\bpath|\bpath\b[^\n]*\bvalidat(?:e|ion)/i,
    /\b(?:do not|must not|never)\b[^\n]*\b(?:broad|recursive|unscoped)\b[^\n]*\bdelete/i,
    /\bdeletedPaths\b/,
    /\bretainedPaths\b/,
  ],
  controller: [
    /\brout(?:e|es|ing)\b/i,
    /\bstate\b/i,
    /\bbudget\b/i,
    /\bretr(?:y|ies)\b/i,
    /\bescalat(?:e|es|ion)\b/i,
    /\btrace(?: assembly)?\b/i,
    /\b(?:do not|must not|never)\b[^\n]*\bimplement/i,
    /\b(?:do not|must not|never)\b[^\n]*\bself[- ]approve/i,
  ],
  implementer: [
    /\b(?:one|single) (?:assigned )?task\b/i,
    /\btest[- ]first\b|\bred[-–— ]green[-–— ]refactor\b/i,
    /\bchangedFiles\b/,
    /\bredEvidence\b/,
    /\bgreenEvidence\b/,
    /\b(?:do not|must not|never)\b[^\n]*\bself[- ]approve/i,
  ],
  planner: [
    /\btasks\b/,
    /\bdependencies\b/,
    /\bacceptanceCriteria\b/,
    /\bunresolvedDecisions\b/,
    /\b(?:do not|must not|never)\b[^\n]*\b(?:write|modify|change)\b[^\n]*\brepositor/i,
  ],
  researcher: [
    /\bevidence\b/i,
    /\bobservation\b[^\n]*\binference\b|\binference\b[^\n]*\bobservation\b/i,
    /\bverifiedFindings\b/,
    /\bread[- ]only\b/i,
  ],
  reviewer: [
    /\bfindings\b/i,
    /\bread[- ]only\b/i,
  ],
  "test-runner": [
    /\bnamed (?:test )?commands?\b/i,
    /\bcommand\b/i,
    /\bexit(?:Code| code)\b/i,
    /\boutput\b/i,
    /\b(?:do not|must not|never)\b[^\n]*\bfix(?:es|ing)?\b/i,
  ],
};

test("reviewer structured output declares exact four-lens set", async () => {
  const profiles = await loadProfiles();
  const reviewer = profiles.find(({ name }) => name === "reviewer");
  assert.ok(reviewer, "missing reviewer profile");
  const output = reviewer.payload.split(/^## Structured output$/m)[1]?.split(/^## /m)[0] ?? "";
  const declaration = output.match(/^lenses?:\s*(.+)$/im)?.[1];
  assert.ok(declaration, "reviewer: Structured output must declare lenses enum");
  const lenses = declaration
    .replace(/[\[\]`]/g, "")
    .split(/\s*(?:,|\|)\s*/)
    .filter(Boolean)
    .sort();
  assert.deepEqual(lenses, ["fidelity", "quality", "security", "spec"]);
});

for (const [role, expectations] of Object.entries(semanticCases)) {
  test(`${role} profile preserves named role semantics`, async () => {
    const profiles = await loadProfiles();
    const profile = profiles.find(({ name }) => name === role);
    assert.ok(profile, `missing ${role} profile`);
    for (const expectation of expectations) {
      assert.match(profile.payload, expectation, `${role}: missing semantic contract ${expectation}`);
    }
  });
}
