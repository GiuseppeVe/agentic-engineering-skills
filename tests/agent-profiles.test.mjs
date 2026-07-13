import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readFile, rm, symlink, writeFile } from "node:fs/promises";
import path from "node:path";
import { tmpdir } from "node:os";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { verifyInstalledAgentProfiles } from "../scripts/verify-pack.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const manifestPath = path.join(root, "manifests", "agent-profiles.json");
const pluginRoot = path.join(root, "plugins", "agentic-engineering-skills");
const installedManifestPath = path.join(pluginRoot, "manifests", "agent-profiles.json");
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
const sourceSpecPath = "docs/agent-profiles.md";
const roleLineMarkers = {
  cleanup: "deletedPaths",
  controller: "Route",
  implementer: "changedFiles",
  planner: "acceptanceCriteria",
  researcher: "verifiedFindings",
  reviewer: "findings",
  "test-runner": "failedCommands",
};
const guideRoleFields = {
  cleanup: ["resolvedScope", "deletedPaths", "retainedPaths"],
  controller: ["route", "budget", "attempt", "trace"],
  implementer: ["taskId", "changedFiles", "redEvidence", "greenEvidence"],
  planner: ["tasks", "dependencies", "acceptanceCriteria", "unresolvedDecisions"],
  researcher: ["observations", "inferences", "verifiedFindings"],
  reviewer: ["lenses", "verdict", "findings"],
  "test-runner": ["commands", "results", "failedCommands"],
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

async function loadInstalledProfiles() {
  const manifest = JSON.parse(await readFile(installedManifestPath, "utf8"));
  assert.ok(Array.isArray(manifest.profiles), "installed profile manifest must expose profiles[]");
  return Promise.all(manifest.profiles.map(async (entry) => {
    assert.equal(typeof entry.path, "string", `${entry.name}: installed profile entry requires path`);
    assert.ok(!path.isAbsolute(entry.path), `${entry.name}: installed path must be plugin-relative`);
    const absolutePath = path.resolve(pluginRoot, entry.path);
    assert.equal(path.relative(pluginRoot, absolutePath).startsWith(".."), false,
      `${entry.name}: installed path escapes plugin root`);
    const payloadBytes = await readFile(absolutePath);
    return { ...entry, absolutePath, payloadBytes };
  }));
}

async function createInstalledFixture(prefix) {
  const fixture = await mkdtemp(path.join(tmpdir(), prefix));
  const fixturePluginRoot = path.join(fixture, "plugin");
  await mkdir(path.join(fixturePluginRoot, "manifests"), { recursive: true });
  await mkdir(path.join(fixturePluginRoot, "agent-profiles"), { recursive: true });
  const installedManifest = JSON.parse(await readFile(installedManifestPath, "utf8"));
  await writeFile(path.join(fixturePluginRoot, "manifests", "agent-profiles.json"), JSON.stringify(installedManifest));
  for (const entry of installedManifest.profiles) {
    await writeFile(path.join(fixturePluginRoot, entry.path), await readFile(path.join(pluginRoot, entry.path)));
  }
  return { fixture, fixturePluginRoot, installedManifest };
}

test("profile manifest declares exact profile inventory", async () => {
  const profiles = await loadProfiles();
  assert.deepEqual(profiles.map(({ name }) => name).sort(), expectedProfiles);
  assert.equal(new Set(profiles.map(({ path: profilePath }) => profilePath)).size, expectedProfiles.length);
});

test("installed plugin manifest mirrors canonical inventory, provenance, paths, and hashes", async () => {
  const installedManifest = JSON.parse(await readFile(installedManifestPath, "utf8"));
  assert.equal(Object.hasOwn(installedManifest, "canonicalManifest"), false,
    "installed manifest must be self-contained and must not point outside plugin root");
  const [canonical, installed] = await Promise.all([loadProfiles(), loadInstalledProfiles()]);
  assert.deepEqual(installed.map(({ name }) => name).sort(), expectedProfiles);
  assert.deepEqual(canonical.map(({ name }) => name).sort(), expectedProfiles);
  const canonicalByName = new Map(canonical.map((entry) => [entry.name, entry]));
  for (const profile of installed) {
    const source = canonicalByName.get(profile.name);
    assert.equal(profile.path, `agent-profiles/${profile.name}.md`);
    assert.equal(profile.payloadPath, profile.path);
    for (const field of ["candidatePath", "status", "source", "revision", "upstreamPath", "sha256", "license",
      "licensePath", "noticePath", "sourceSpecPath", "sourceSpecRoleLine"]) {
      assert.equal(profile[field], source[field], `${profile.name}: installed ${field} differs from canonical manifest`);
    }
    assert.equal(createHash("sha256").update(profile.payloadBytes).digest("hex"), profile.sha256,
      `${profile.name}: installed payload hash mismatch`);
  }
});

test("installed profile verification rejects symbolic-link payloads", async (t) => {
  const { fixture, fixturePluginRoot } = await createInstalledFixture("installed-profile-symlink-");
  try {
    const outsidePayload = path.join(fixture, "outside.md");
    await writeFile(outsidePayload, "outside");
    await rm(path.join(fixturePluginRoot, "agent-profiles", "reviewer.md"));
    try {
      await symlink(outsidePayload, path.join(fixturePluginRoot, "agent-profiles", "reviewer.md"), "file");
    } catch (error) {
      if (["EPERM", "EACCES"].includes(error?.code)) { t.skip(`OS disallows symlink creation: ${error.code}`); return; }
      throw error;
    }
    await assert.rejects(
      verifyInstalledAgentProfiles({ canonicalPath: manifestPath, pluginRoot: fixturePluginRoot, writeSummary: () => {} }),
      /must not be a symbolic link/,
    );
  } finally {
    await rm(fixture, { recursive: true, force: true });
  }
});

test("installed profile verification rejects a manifest file symlink", async (t) => {
  const fixture = await mkdtemp(path.join(tmpdir(), "installed-manifest-symlink-"));
  try {
    const fixturePluginRoot = path.join(fixture, "plugin");
    await mkdir(path.join(fixturePluginRoot, "manifests"), { recursive: true });
    const outsideManifest = path.join(fixture, "outside-manifest.json");
    await writeFile(outsideManifest, await readFile(installedManifestPath));
    try {
      await symlink(outsideManifest, path.join(fixturePluginRoot, "manifests", "agent-profiles.json"), "file");
    } catch (error) {
      if (["EPERM", "EACCES"].includes(error?.code)) { t.skip(`OS disallows symlink creation: ${error.code}`); return; }
      throw error;
    }
    await assert.rejects(
      verifyInstalledAgentProfiles({ canonicalPath: manifestPath, pluginRoot: fixturePluginRoot, writeSummary: () => {} }),
      /manifest must not be a symbolic link/,
    );
  } finally {
    await rm(fixture, { recursive: true, force: true });
  }
});

test("installed profile verification rejects a manifest parent directory symlink escaping plugin root", async (t) => {
  const fixture = await mkdtemp(path.join(tmpdir(), "installed-manifest-parent-symlink-"));
  try {
    const fixturePluginRoot = path.join(fixture, "plugin");
    const outsideManifests = path.join(fixture, "outside-manifests");
    await mkdir(fixturePluginRoot, { recursive: true });
    await mkdir(outsideManifests, { recursive: true });
    await writeFile(path.join(outsideManifests, "agent-profiles.json"), await readFile(installedManifestPath));
    try {
      await symlink(outsideManifests, path.join(fixturePluginRoot, "manifests"), "dir");
    } catch (error) {
      if (["EPERM", "EACCES"].includes(error?.code)) { t.skip(`OS disallows symlink creation: ${error.code}`); return; }
      throw error;
    }
    await assert.rejects(
      verifyInstalledAgentProfiles({ canonicalPath: manifestPath, pluginRoot: fixturePluginRoot, writeSummary: () => {} }),
      /manifest real path escapes plugin root/,
    );
  } finally {
    await rm(fixture, { recursive: true, force: true });
  }
});

test("installed profile verification rejects lexical traversal", async () => {
  const fixture = await mkdtemp(path.join(tmpdir(), "installed-profile-traversal-"));
  try {
    const fixturePluginRoot = path.join(fixture, "plugin");
    await mkdir(path.join(fixturePluginRoot, "manifests"), { recursive: true });
    const installedManifest = JSON.parse(await readFile(installedManifestPath, "utf8"));
    installedManifest.profiles[0].path = "../escape.md";
    installedManifest.profiles[0].payloadPath = "../escape.md";
    await writeFile(path.join(fixturePluginRoot, "manifests", "agent-profiles.json"), JSON.stringify(installedManifest));
    await assert.rejects(
      verifyInstalledAgentProfiles({ canonicalPath: manifestPath, pluginRoot: fixturePluginRoot, writeSummary: () => {} }),
      /path escapes plugin root/,
    );
  } finally {
    await rm(fixture, { recursive: true, force: true });
  }
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

function tableProfileNames(markdown, marker) {
  const table = markdown.split(marker)[1]?.split(/^## /m)[0] ?? "";
  return [...table.matchAll(/^\| `([^`]+)` \|/gm)].map((match) => match[1]).sort();
}

test("documentation guide maps exact profile inventory and host boundaries", async () => {
  const [profiles, installedProfiles, guide, readme] = await Promise.all([
    loadProfiles(),
    loadInstalledProfiles(),
    readFile(path.resolve(root, "docs/agent-profiles.md"), "utf8"),
    readFile(path.resolve(root, "README.md"), "utf8"),
  ]);
  assert.deepEqual(profiles.map(({ name }) => name).sort(), expectedProfiles);
  assert.deepEqual(installedProfiles.map(({ name }) => name).sort(), expectedProfiles);
  assert.deepEqual(tableProfileNames(guide, "## Role contracts"), expectedProfiles);
  const roleTable = guide.split("## Role contracts")[1]?.split(/^## /m)[0] ?? "";
  for (const [role, fields] of Object.entries(guideRoleFields)) {
    const row = roleTable.split("\n").find((line) => line.startsWith(`| \`${role}\` |`));
    assert.ok(row, `${role}: missing authoritative guide row`);
    for (const field of fields) {
      assert.ok(row.includes(`\`${field}\``), `${role}: guide row missing exact field ${field}`);
    }
  }
  assert.doesNotMatch(guide, /^\| `(?:builder|tester|orchestrator)` \|/gm,
    "undeclared aliases must not appear as profile identifiers");
  assert.match(readme, /\[agent profile guide\]\(docs\/agent-profiles\.md\)/i);
  await readFile(path.resolve(root, "docs/agent-profiles.md"), "utf8");
  assert.match(guide, /role contracts are consumed by workflow skills/i);
  assert.match(guide, /not an executable harness/i);
  assert.match(guide, /do not guarantee automatic native registration/i);
  const hostHeadings = [...guide.matchAll(/^## (Codex|Claude Code)$/gm)].map((match) => match[1]);
  assert.deepEqual(hostHeadings, ["Codex", "Claude Code"]);
  for (const section of ["Codex", "Claude Code"]) {
    const body = guide.split(`## ${section}`)[1]?.split(/^## /m)[0] ?? "";
    assert.match(body, /native delegation/i);
    assert.match(body, /host-specific commands.*not.*profiles|profiles.*not.*host-specific commands/is);
  }
});

test("workflow documentation maps exact profile inventory into orchestration", async () => {
  const workflow = await readFile(path.resolve(root, "docs/workflow.md"), "utf8");
  assert.deepEqual(tableProfileNames(workflow, "## Phase-to-profile mapping"), expectedProfiles);
  assert.doesNotMatch(workflow, /^\| `(?:builder|tester|orchestrator)` \|/gm,
    "undeclared aliases must not appear as profile identifiers");
});

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
