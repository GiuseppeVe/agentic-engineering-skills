import assert from "node:assert/strict";
import { readdir, readFile, realpath } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const pluginRoot = path.join(root, "plugins", "agentic-engineering-skills");
const expectedName = "agentic-engineering-skills";
const expectedVersion = "0.1.0";
const strictSemver = /^\d+\.\d+\.\d+$/;

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
});

test("Claude manifest declares same plugin identity", async () => {
  const manifest = await json("plugins/agentic-engineering-skills/.claude-plugin/plugin.json");

  assert.equal(manifest.name, expectedName);
  assert.equal(manifest.version, expectedVersion);
  assert.match(manifest.version, strictSemver);
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
});

test("skill discovery is flat and shared by both manifests", async () => {
  const codexManifest = await json("plugins/agentic-engineering-skills/.codex-plugin/plugin.json");
  const skillsRoot = path.resolve(pluginRoot, codexManifest.skills);
  const entries = await readdir(skillsRoot, { withFileTypes: true }).catch((error) => {
    if (error.code === "ENOENT") return [];
    throw error;
  });
  const skillDirectories = entries.filter((entry) => entry.isDirectory());

  for (const directory of skillDirectories) {
    const children = await readdir(path.join(skillsRoot, directory.name), { withFileTypes: true });
    assert.ok(children.some((entry) => entry.isFile() && entry.name === "SKILL.md"));
    assert.equal(children.some((entry) => entry.isDirectory() && entry.name === "skills"), false);
  }
});
