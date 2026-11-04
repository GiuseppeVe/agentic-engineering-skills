import assert from "node:assert/strict";
import { access, readdir, readFile, realpath } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { expectedSkillsByHost } from "./expected-inventory.mjs";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const pluginRoot = path.join(root, "plugins", "agentic-engineering-skills");
const expectedName = "agentic-engineering-skills";
const expectedVersion = "1.1.0";
const strictSemver = /^\d+\.\d+\.\d+$/;
const expectedVendorSkills = [];

async function json(relativePath) {
  return JSON.parse(await readFile(path.join(root, relativePath), "utf8"));
}

function marketplacePlugins(marketplace) {
  assert.ok(Array.isArray(marketplace.plugins), "marketplace.plugins must be an array");
  return marketplace.plugins;
}

test("Codex manifest declares exact native plugin contract", async () => {
  const manifest = await json("plugins/agentic-engineering-skills/.codex-plugin/plugin.json");

  assert.equal(manifest.name, expectedName);
  assert.equal(manifest.version, expectedVersion);
  assert.match(manifest.version, strictSemver);
  assert.equal(manifest.skills, "./skills/");
  assert.equal(manifest.interface.category, "Productivity");
  assert.match(manifest.interface.defaultPrompt, /engineering skills/i);
});

test("Claude manifest declares same plugin identity", async () => {
  const manifest = await json("plugins/agentic-engineering-skills/.claude-plugin/plugin.json");

  assert.equal(manifest.name, expectedName);
  assert.equal(manifest.version, expectedVersion);
  assert.match(manifest.version, strictSemver);
  assert.deepEqual(manifest.skills, ["./claude-skills/"]);
});

test("both marketplaces resolve to shared plugin directory", async () => {
  const codexMarketplace = await json(".agents/plugins/marketplace.json");
  const claudeMarketplace = await json(".claude-plugin/marketplace.json");
  const codexEntry = marketplacePlugins(codexMarketplace).find(({ name }) => name === expectedName);
  const claudeEntry = marketplacePlugins(claudeMarketplace).find(({ name }) => name === expectedName);

  assert.ok(codexEntry, "Codex marketplace entry missing");
  assert.deepEqual(codexEntry.source, {
    source: "local",
    path: "./plugins/agentic-engineering-skills",
  });
  assert.equal(codexEntry.installation, "AVAILABLE");
  assert.equal(codexEntry.authentication, "ON_INSTALL");
  assert.equal(codexEntry.category, "Productivity");
  assert.equal(claudeEntry?.source, "./plugins/agentic-engineering-skills");
  assert.equal(claudeEntry?.version, expectedVersion);

  const codexTarget = await realpath(path.resolve(root, codexEntry.source.path));
  const claudeTarget = await realpath(path.resolve(root, claudeEntry.source));
  assert.equal(codexTarget, await realpath(pluginRoot));
  assert.equal(claudeTarget, codexTarget);
  assert.match(codexMarketplace.description, /PR workflow/i);
  assert.match(claudeMarketplace.description, /PR workflow/i);
  assert.match(codexEntry.description, /PR workflow/i);
  assert.match(claudeEntry.description, /PR workflow/i);
});

test("plugin metadata advertises supported engineering and PR workflows", async () => {
  const [codex, claude] = await Promise.all([
    json("plugins/agentic-engineering-skills/.codex-plugin/plugin.json"),
    json("plugins/agentic-engineering-skills/.claude-plugin/plugin.json"),
  ]);

  assert.match(codex.description, /PR workflow/i);
  assert.match(claude.description, /PR workflow/i);
  assert.ok(!codex.keywords.includes("frontend-handoff"));
  assert.ok(!claude.keywords.includes("frontend-handoff"));
  assert.match(codex.interface.defaultPrompt, /project PR workflow/i);
});

test("host manifest discovery exposes Claude Implement only to Claude Code", async () => {
  for (const host of ["codex", "claude"]) {
    const manifest = await json(`plugins/agentic-engineering-skills/.${host === "codex" ? "codex" : "claude"}-plugin/plugin.json`);
    const declared = Array.isArray(manifest.skills) ? manifest.skills : [manifest.skills];
    const roots = host === "claude" ? ["./skills/", ...declared] : declared;
    const discovered = [];
    for (const relativeRoot of roots) {
      const rootPath = path.resolve(pluginRoot, relativeRoot);
      assert.ok(rootPath.startsWith(`${pluginRoot}${path.sep}`), "skill roots must stay inside the plugin");
      for (const entry of await readdir(rootPath, { withFileTypes: true })) {
        if (!entry.isDirectory()) continue;
        await readFile(path.join(rootPath, entry.name, "SKILL.md"));
        discovered.push(entry.name);
      }
    }
    assert.equal(new Set(discovered).size, discovered.length, `${host}: duplicate skill discovery`);
    assert.deepEqual(discovered.sort(), expectedSkillsByHost[host]);
    assert.equal(discovered.includes("claude-implement"), host === "claude");
  }
});

test("vendor inventory contains every approved byte-exact skill", async () => {
  const lock = await json("manifests/skills.lock.json");
  const lockedVendorSkills = lock.skills
    .filter(({ sourceType }) => sourceType === "vendor")
    .map(({ name }) => name)
    .sort();
  const entries = await readdir(path.join(pluginRoot, "skills"), { withFileTypes: true }).catch(
    (error) => {
      if (error.code === "ENOENT") return [];
      throw error;
    },
  );
  const actual = entries.filter((entry) => entry.isDirectory()).map((entry) => entry.name);
  const missing = expectedVendorSkills.filter((name) => !actual.includes(name));

  assert.deepEqual(lockedVendorSkills, expectedVendorSkills);
  assert.deepEqual(missing, [], `missing ${missing.length} vendor skill directories`);
});

async function skillEntrypoints(directory, prefix = "") {
  const found = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const relative = prefix ? `${prefix}/${entry.name}` : entry.name;
    if (entry.isDirectory()) found.push(...await skillEntrypoints(path.join(directory, entry.name), relative));
    else if (entry.isFile() && entry.name === "SKILL.md") found.push(relative);
  }
  return found.sort();
}

test("recursive host discovery cannot expose supporting documents as extra skills", async () => {
  for (const directory of ["skills", "claude-skills"]) {
    const entrypoints = await skillEntrypoints(path.join(pluginRoot, directory));
    const topLevel = (await readdir(path.join(pluginRoot, directory), { withFileTypes: true }))
      .filter(entry => entry.isDirectory()).map(entry => `${entry.name}/SKILL.md`).sort();
    assert.deepEqual(entrypoints, topLevel,
      `${directory}: nested SKILL.md files become independent skills in native discovery`);
  }
});


test("retired generic profiles are not shipped and specialist attachments remain available", async () => {
  for (const relativePath of ["agent-profiles", "manifests/agent-profiles.json"]) {
    await assert.rejects(access(path.join(pluginRoot, relativePath)), { code: "ENOENT" });
  }
  await access(path.join(pluginRoot, "skills/codex-implement/agents/planner.md"));
  await access(path.join(pluginRoot, "claude-skills/claude-implement/agents/planner.md"));
});
