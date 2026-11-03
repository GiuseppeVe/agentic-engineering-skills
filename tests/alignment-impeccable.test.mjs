import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile, readdir, stat } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { gunzipSync } from "node:zlib";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const skillRoot = path.join(root, "plugins/agentic-engineering-skills/skills/impeccable");
const maxFileBytes = 1024 * 1024;

async function filesUnder(directory) {
  const result = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const absolute = path.join(directory, entry.name);
    if (entry.isDirectory()) result.push(...await filesUnder(absolute));
    else if (entry.isFile()) result.push(absolute);
  }
  return result;
}

test("Impeccable package aligns with the source-project host v4.8 skill and its local references", async () => {
  const skill = await readFile(path.join(skillRoot, "SKILL.md"), "utf8");
  const newWork = await readFile(path.join(skillRoot, "reference/new-work.md"), "utf8");
  const files = new Set((await filesUnder(skillRoot)).map((file) => path.relative(skillRoot, file).replaceAll("\\", "/")));

  assert.match(skill, /^version:\s*4\.8\.0\s*$/m);
  for (const reference of [
    "reference/new-work.md",
    "reference/craft-floor.md",
    "reference/product.md",
    "reference/brand.md",
    "reference/live-setup.md",
    "reference/operate.md",
    "reference/mode-read.md",
    "reference/mode-operate.md",
    "reference/mode-persuade.md",
    "reference/visualize.md",
    "reference/region-map.md",
    "reference/routing.md",
    "reference/adapt.native.md",
    "reference/audit.native.md",
    "reference/android.md",
    "reference/ios.md",
  ]) {
    assert.ok(files.has(reference), `missing source-project v4.8 reference: ${reference}`);
  }
  assert.match(skill, /scripts\/impeccable\.cmd/);
  assert.match(skill, /On a Windows shell without `sh`, call `<skill-base-dir>\/scripts\/impeccable\.cmd` instead/);
  assert.match(skill, /scripts\/impeccable/);
  assert.match(newWork, /no catalog index/);
  assert.match(newWork, /25-face style shortlist/);
});

test("Impeccable engine launchers pin verified multi-platform assets without bundling oversized binaries", async () => {
  const shellLauncher = await readFile(path.join(skillRoot, "scripts/impeccable"), "utf8");
  const windowsLauncher = await readFile(path.join(skillRoot, "scripts/impeccable.cmd"), "utf8");
  const powershellExpander = await readFile(path.join(skillRoot, "scripts/expand-font-index.ps1"), "utf8");
  const checksums = await readFile(path.join(skillRoot, "scripts/engine-checksums.txt"), "utf8");
  const version = (await readFile(path.join(skillRoot, "scripts/VERSION"), "utf8")).trim();
  const compressedIndex = await readFile(path.join(skillRoot, "scripts/data/font-index.json.deflate"));
  const index = gunzipSync(compressedIndex);
  const files = await filesUnder(skillRoot);

  assert.equal(version, "0.1.18");
  assert.match(shellLauncher, /engine-checksums\.txt/);
  assert.match(shellLauncher, /sha256sum|shasum/);
  assert.match(windowsLauncher, /engine-checksums\.txt/);
  assert.match(windowsLauncher, /certutil/);
  assert.match(shellLauncher, /impeccable-font-match\.XXXXXX/);
  assert.match(shellLauncher, /font-index\.json\.deflate/);
  assert.match(shellLauncher, /rm -rf "\$font_mirror"/);
  assert.match(shellLauncher, /IMPECCABLE_SKILL_DIR="\$font_mirror\/skill"/);
  assert.match(windowsLauncher, /expand-font-index\.ps1/);
  assert.match(windowsLauncher, /impeccable-font-match-/);
  assert.match(windowsLauncher, /rd \/s \/q "%font_mirror%"/);
  assert.match(windowsLauncher, /IMPECCABLE_SKILL_DIR=%font_mirror%\\skill/);
  assert.match(powershellExpander, /SHA256/);
  assert.equal(index.length, 1_100_013);
  assert.equal(createHash("sha256").update(index).digest("hex"), "47edbdfaf27073c47033d1ac7dfee881be49e2dcbda7671d1157300481dde6da");
  assert.equal(JSON.parse(index.toString("utf8")).entries.length, 3076);
  assert.match(checksums, new RegExp(`^${version} impeccable-darwin-arm64 [a-f0-9]{64}$`, "m"));
  assert.match(checksums, new RegExp(`^${version} impeccable-darwin-x64 [a-f0-9]{64}$`, "m"));
  assert.match(checksums, new RegExp(`^${version} impeccable-linux-arm64 [a-f0-9]{64}$`, "m"));
  assert.match(checksums, new RegExp(`^${version} impeccable-linux-x64 [a-f0-9]{64}$`, "m"));
  assert.match(checksums, new RegExp(`^${version} impeccable-windows-x64\.exe [a-f0-9]{64}$`, "m"));

  for (const file of files) {
    const metadata = await stat(file);
    assert.ok(metadata.size <= maxFileBytes, `${path.relative(skillRoot, file)} exceeds 1 MiB`);
  }
  assert.equal(files.some((file) => /\.exe$/i.test(file)), false);
});

test("Claude and Codex finish reviewers enforce the same seed-reference contract", async () => {
  const claude = await readFile(path.join(root, "plugins/agentic-engineering-skills/agents/impeccable-finish-reviewer.md"), "utf8");
  const codex = await readFile(path.join(skillRoot, "agents/impeccable_finish_reviewer.toml"), "utf8");
  const contract = text => text.split(/\r?\n/).find(line => line.startsWith("4. **Contract, promise by promise.**"));
  assert.ok(contract(codex), "Codex reviewer lacks its seed-reference contract");
  assert.equal(contract(claude), contract(codex), "Claude reviewer diverges from the shared seed-reference contract");
});

test("Claude specialist contracts match the current shared comp and craft-floor rules", async () => {
  const agentRoot = path.join(root, "plugins/agentic-engineering-skills/agents");
  const read = (dir, file) => readFile(path.join(dir, file), "utf8");
  const [claudeAsset, codexAsset, claudeReviewer, codexReviewer] = await Promise.all([
    read(agentRoot, "impeccable-asset-producer.md"), read(path.join(skillRoot, "agents"), "impeccable_asset_producer.toml"),
    read(agentRoot, "impeccable-finish-reviewer.md"), read(path.join(skillRoot, "agents"), "impeccable_finish_reviewer.toml"),
  ]);
  const comps = value => value.split("## Decision Comps\n")[1]?.split("\n## ")[0].trim();
  const floor = value => value.split(/\r?\n/).find(line => line.startsWith("6. **Floor.**"));
  assert.ok(comps(codexAsset) && floor(codexReviewer));
  assert.equal(comps(claudeAsset), comps(codexAsset), "asset producer comp rules diverged");
  assert.equal(floor(claudeReviewer), floor(codexReviewer), "reviewer craft-floor rules diverged");
});
