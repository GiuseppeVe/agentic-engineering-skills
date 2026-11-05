import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { parse } from "yaml";
import { sha256Path } from "../scripts/lib/hash.mjs";
import { validateManifest, validateSourceManifest } from "../scripts/lib/manifest.mjs";

const root = new URL("../", import.meta.url);
const payload = new URL("plugins/agentic-engineering-skills/skills/master-orchestrator/", root);
const readJson = async path => JSON.parse(await readFile(new URL(path, root), "utf8"));

test("master orchestrator packages both explicit host contracts and complete hashed references", async () => {
  const source = validateSourceManifest(await readJson("manifests/skill-sources.json")).find(entry => entry.name === "master-orchestrator");
  const entry = validateManifest(await readJson("manifests/skills.lock.json")).find(entry => entry.name === "master-orchestrator");
  const bytes = await readFile(new URL("SKILL.md", payload));
  assert.equal(bytes.subarray(0, 3).toString(), "---", "frontmatter must start at byte zero");
  const frontmatter = bytes.toString("utf8").match(/^---\r?\n([\s\S]*?)\r?\n---/);
  assert.ok(frontmatter, "closed YAML frontmatter required");
  const skill = parse(frontmatter[1]);
  assert.equal(skill.name, "master-orchestrator");
  assert.equal(skill["disable-model-invocation"], true);
  const metadata = parse(await readFile(new URL("agents/openai.yaml", payload), "utf8"));
  assert.equal(metadata.policy.allow_implicit_invocation, false);
  assert.equal(source.sourceType, "original");
  assert.equal(source.localPath, "master-orchestrator/");
  assert.equal(entry.sourceType, "original");
  assert.equal(entry.payloadType, "directory");
  assert.equal(entry.license, "MIT");
  assert.deepEqual(entry.dependencies, [], "optional Wayfinder and implementation handoff do not become mandatory dependencies");
  assert.equal(await sha256Path(fileURLToPath(payload)), entry.localSha256);
  await readFile(new URL("references/coordinating-design.md", payload));
});

test("master orchestrator snapshot provenance does not expose source location or claim a commit", async () => {
  const source = (await readJson("manifests/skill-sources.json")).skills.find(entry => entry.name === "master-orchestrator");
  assert.equal("repository" in source.origin, false);
  assert.equal(source.origin.state, "untracked-local-snapshot");
  assert.equal("revision" in source.origin, false);
  assert.deepEqual(source.origin.paths, [".agents/skills/master-orchestrator/", ".claude/skills/master-orchestrator/"]);
  assert.deepEqual(Object.keys(source.origin.files).sort(), [
    ".agents/skills/master-orchestrator/SKILL.md",
    ".agents/skills/master-orchestrator/agents/openai.yaml",
    ".agents/skills/master-orchestrator/references/coordinating-design.md",
    ".claude/skills/master-orchestrator/SKILL.md",
    ".claude/skills/master-orchestrator/references/coordinating-design.md",
  ]);
  for (const hash of Object.values(source.origin.files)) assert.match(hash, /^[a-f0-9]{64}$/);
  const metadata = await readFile(new URL("agents/openai.yaml", payload));
  const { createHash } = await import("node:crypto");
  assert.equal(createHash("sha256").update(metadata).digest("hex"), source.origin.files[".agents/skills/master-orchestrator/agents/openai.yaml"]);
  assert.equal(source.origin.packagingChanges.length, 2);
});
