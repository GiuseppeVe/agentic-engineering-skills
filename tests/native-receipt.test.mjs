import assert from "node:assert/strict";
import { cp, mkdtemp, mkdir, readFile, rm, symlink, writeFile } from "node:fs/promises";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { expectedSkills, expectedSkillsByHost } from "./expected-inventory.mjs";
import { hashPayloadTree, inspectInstalledPayload, locateInstalledPayload, verifyNativeReceipt } from "../scripts/lib/native-receipt.mjs";

const exec = promisify(execFile);
const payloadRoot = new URL("../plugins/agentic-engineering-skills/", import.meta.url);
const included = ["alpha", "claude-only"];
const includedByHost = { codex: ["alpha"], claude: included };

async function fixture(t) {
  const root = await mkdtemp(join(tmpdir(), "agentic-engineering-skills-native-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  for (const dir of [".codex-plugin", ".claude-plugin", "skills/alpha", "claude-skills/claude-only", "unused/hidden"]) {
    await mkdir(join(root, dir), { recursive: true });
  }
  await writeFile(join(root, ".codex-plugin/plugin.json"), JSON.stringify({ name: "fixture", skills: "./skills/" }));
  await writeFile(join(root, ".claude-plugin/plugin.json"), JSON.stringify({ name: "fixture", skills: ["./claude-skills/"] }));
  for (const [path, name] of [["skills/alpha", "alpha"], ["claude-skills/claude-only", "claude-only"], ["unused/hidden", "hidden"]]) {
    await writeFile(join(root, path, "SKILL.md"), `---\nname: ${name}\ndescription: Fixture\n---\n`);
  }
  return root;
}

async function mockReceipt(root) {
  const hosts = {};
  for (const host of ["codex", "claude"]) {
    const payload = await inspectInstalledPayload(root, { host });
    hosts[host] = {
      version: "fixture-1", discoveredSkills: payload.skills,
      discoveryBasis: "isolated-installed-manifest",
      installedPayload: { skills: payload.skills, skillRoots: payload.skillRoots, treeHash: payload.treeHash, fullTreeHash: await hashPayloadTree(root) },
      commands: [{ command: "synthetic fixture install", exitCode: 0 }],
    };
  }
  return { schemaVersion: 3, evidenceSource: "isolated-native-installs",
    installedPayload: { root: "plugins/agentic-engineering-skills", skills: included }, hosts };
}

async function linkOrSkip(t, target, path, type) {
  try { await symlink(target, path, type); }
  catch (error) {
    if (["EPERM", "EACCES", "ENOTSUP"].includes(error.code)) {
      t.skip(`platform denied test link creation: ${error.code}`);
      return false;
    }
    throw error;
  }
  return true;
}

test("discovery rejects a configured root whose ancestor redirects outside the plugin", async t => {
  const root = await fixture(t);
  const outside = await mkdtemp(join(tmpdir(), "native-external-skills-"));
  t.after(() => rm(outside, { recursive: true, force: true }));
  await mkdir(join(outside, "skills/escaped"), { recursive: true });
  await writeFile(join(outside, "skills/escaped/SKILL.md"), "external skill\n");
  if (!await linkOrSkip(t, outside, join(root, "linked"), process.platform === "win32" ? "junction" : "dir")) return;
  await writeFile(join(root, ".codex-plugin/plugin.json"), JSON.stringify({ skills: "./linked/skills/" }));
  await assert.rejects(() => inspectInstalledPayload(root, { host: "codex" }), /redirected payload path segment|escapes plugin root/);
});

for (const host of ["codex", "claude"]) {
  test(`${host} manifest cannot be read through an external directory junction`, async t => {
    const root = await fixture(t);
    const outside = await mkdtemp(join(tmpdir(), "native-external-manifest-"));
    t.after(() => rm(outside, { recursive: true, force: true }));
    await writeFile(join(outside, "plugin.json"), JSON.stringify({ skills: "./skills/" }));
    const directory = join(root, host === "codex" ? ".codex-plugin" : ".claude-plugin");
    await rm(directory, { recursive: true });
    if (!await linkOrSkip(t, outside, directory, process.platform === "win32" ? "junction" : "dir")) return;
    await assert.rejects(() => inspectInstalledPayload(root, { host }), /redirected payload path segment|escapes plugin root/);
  });
}

test("portable manifest cannot redirect to an external file", async t => {
  const root = await fixture(t);
  const outside = await mkdtemp(join(tmpdir(), "native-external-portable-"));
  t.after(() => rm(outside, { recursive: true, force: true }));
  const manifest = join(outside, "plugin.json");
  await writeFile(manifest, JSON.stringify({ $schema: "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json" }));
  if (!await linkOrSkip(t, manifest, join(root, "plugin.json"), "file")) return;
  await assert.rejects(() => inspectInstalledPayload(root, { host: "codex" }), /redirected payload path segment|escapes plugin root/);
});

test("tracked native receipt proves host-specific isolated configured inventories", async () => {
  const receipt = JSON.parse(await readFile(new URL("../manifests/native-discovery.json", import.meta.url), "utf8"));
  const result = await verifyNativeReceipt(receipt, { included: expectedSkills, includedByHost: expectedSkillsByHost, payloadRoot });
  assert.equal(result.count, expectedSkills.length);
  for (const host of ["codex", "claude"]) assert.equal(result.hosts[host].count, expectedSkillsByHost[host].length);
});

test("manifest discovery excludes copied skills outside the selected host paths", async t => {
  const root = await fixture(t);
  const codex = await inspectInstalledPayload(root, { host: "codex" });
  const claude = await inspectInstalledPayload(root, { host: "claude" });
  assert.deepEqual(codex.skills, includedByHost.codex);
  assert.deepEqual(claude.skills, includedByHost.claude);
  assert.deepEqual(codex.skillRoots, ["skills"]);
  assert.deepEqual(claude.skillRoots, ["claude-skills", "skills"]);
  assert.notEqual(codex.treeHash, claude.treeHash);
});

test("receipt verifies distinct host inventories and hashes", async t => {
  const root = await fixture(t);
  const result = await verifyNativeReceipt(await mockReceipt(root), { included, includedByHost, payloadRoot: root });
  assert.equal(result.count, 2);
  assert.equal(result.hosts.codex.count, 1);
  assert.equal(result.hosts.claude.count, 2);
});

test("receipt rejects host inventory drift and a shared hash substituted for host evidence", async t => {
  const root = await fixture(t);
  const receipt = await mockReceipt(root);
  receipt.hosts.codex.discoveredSkills.push("claude-only");
  await assert.rejects(() => verifyNativeReceipt(receipt, { included, includedByHost, payloadRoot: root }), /codex native inventory mismatch/);
  receipt.hosts.codex.discoveredSkills.pop();
  receipt.hosts.codex.installedPayload.treeHash = receipt.hosts.claude.installedPayload.treeHash;
  await assert.rejects(() => verifyNativeReceipt(receipt, { included, includedByHost, payloadRoot: root }), /codex native receipt payload hash mismatch/);
});

test("manifest changes invalidate a receipt even if discovered skill names are unchanged", async t => {
  const root = await fixture(t);
  const receipt = await mockReceipt(root);
  await writeFile(join(root, ".codex-plugin/plugin.json"), JSON.stringify({ name: "changed", skills: "./skills/" }));
  await assert.rejects(() => verifyNativeReceipt(receipt, { included, includedByHost, payloadRoot: root }), /codex native receipt payload hash mismatch/);
});

test("host-specific skill byte drift changes only the consuming host hash", async t => {
  const root = await fixture(t);
  const codex = await inspectInstalledPayload(root, { host: "codex" });
  const claude = await inspectInstalledPayload(root, { host: "claude" });
  await writeFile(join(root, "claude-skills/claude-only/SKILL.md"), "changed\n");
  assert.equal((await inspectInstalledPayload(root, { host: "codex" })).treeHash, codex.treeHash);
  assert.notEqual((await inspectInstalledPayload(root, { host: "claude" })).treeHash, claude.treeHash);
});

test("declared roots must exist, remain contained, and cannot duplicate names", async t => {
  const root = await fixture(t);
  const manifest = join(root, ".codex-plugin/plugin.json");
  for (const path of ["../escape", "./../escape", "./missing"]) {
    await writeFile(manifest, JSON.stringify({ skills: path }));
    await assert.rejects(() => inspectInstalledPayload(root, { host: "codex" }), /invalid manifest skill path|ENOENT/);
  }
  await mkdir(join(root, "claude-skills/alpha"));
  await writeFile(join(root, "claude-skills/alpha/SKILL.md"), "duplicate");
  await assert.rejects(() => inspectInstalledPayload(root, { host: "claude" }), /duplicate discovered skill: alpha/);
});

test("locates a native install from CLI JSON with host-aware manifests", async t => {
  const root = await fixture(t);
  const located = await locateInstalledPayload({ host: "codex", jsonDocuments: [JSON.stringify({ installPath: root })] });
  assert.equal(located.basis, "native-cli-json");
  assert.equal(located.root, root);
  assert.deepEqual(located.skills, includedByHost.codex);
});

test("locates a host cache while preserving host-specific discovery", async t => {
  const root = await fixture(t);
  const located = await locateInstalledPayload({ host: "claude", searchRoots: [root] });
  assert.equal(located.basis, "host-cache-scan");
  assert.deepEqual(located.skills, includedByHost.claude);
});

test("installed verifier checks host configuration, lock inventory and receipt bytes", async t => {
  const source = await fixture(t);
  const parent = await mkdtemp(join(tmpdir(), "agentic-engineering-skills-cli-"));
  t.after(() => rm(parent, { recursive: true, force: true }));
  const installed = join(parent, "installed");
  await cp(source, installed, { recursive: true });
  const receiptPath = join(parent, "receipt.json"), lockPath = join(parent, "lock.json");
  await writeFile(receiptPath, JSON.stringify(await mockReceipt(source)));
  await writeFile(lockPath, JSON.stringify({ skills: [
    { name: "alpha" },
    { name: "claude-only", payloadPath: "plugins/agentic-engineering-skills/claude-skills/claude-only" },
  ] }));
  const command = new URL("../scripts/verify-installed-native.mjs", import.meta.url);
  const base = [fileURLToPath(command), "--source-root", source, "--installed-root", installed, "--receipt", receiptPath, "--lock", lockPath];
  for (const host of ["codex", "claude"]) {
    const result = await exec(process.execPath, [...base, "--host", host]);
    assert.match(result.stdout, new RegExp(`${host} installed payload verified: ${includedByHost[host].length} skills`));
  }
  const hidden = join(installed, "unused/hidden/SKILL.md");
  const original = await readFile(hidden);
  await writeFile(hidden, "tampered outside host skill discovery\n");
  for (const host of ["codex", "claude"]) {
    await assert.rejects(() => exec(process.execPath, [...base, "--host", host]), /full tree hash mismatch/i);
  }
  await writeFile(hidden, original);
  await writeFile(join(installed, ".codex-plugin/plugin.json"), JSON.stringify({ skills: ["./skills/", "./claude-skills/"] }));
  await assert.rejects(() => exec(process.execPath, [...base, "--host", "codex"]), /inventory mismatch/);
});

test("Claude receipt detects missing or changed plugin agent contracts", async t => {
  const source = await fixture(t);
  await mkdir(join(source, "agents"));
  for (const name of ["asset-producer", "documenter", "finish-reviewer", "manual-edit-applier"]) {
    await writeFile(join(source, "agents", `impeccable-${name}.md`), `---\nname: impeccable-${name}\ndescription: test\n---\ncontract ${name}\n`);
  }
  const installed = await mkdtemp(join(tmpdir(), "installed-agent-fixture-"));
  t.after(() => rm(installed, { recursive: true, force: true }));
  await cp(source, installed, { recursive: true });
  const expected = (await inspectInstalledPayload(source, { host: "claude" })).treeHash;
  assert.equal((await inspectInstalledPayload(installed, { host: "claude" })).treeHash, expected);
  const reviewer = join(installed, "agents", "impeccable-finish-reviewer.md");
  await writeFile(reviewer, "tampered\n");
  assert.notEqual((await inspectInstalledPayload(installed, { host: "claude" })).treeHash, expected);
  await rm(reviewer);
  assert.notEqual((await inspectInstalledPayload(installed, { host: "claude" })).treeHash, expected);
});

test("installed receipts detect missing or modified hook and license files", async t => {
  const source = await fixture(t);
  for (const dir of ["hooks", "licenses"]) await mkdir(join(source, dir));
  for (const [dir, name] of [["hooks", "hooks.json"], ["licenses", "NOTICE"]]) await writeFile(join(source, dir, name), `original ${name}\n`);
  const installed = await mkdtemp(join(tmpdir(), "installed-plugin-fixture-"));
  t.after(() => rm(installed, { recursive: true, force: true }));
  await cp(source, installed, { recursive: true });
  for (const host of ["codex", "claude"]) {
    const expected = (await inspectInstalledPayload(source, { host })).treeHash;
    assert.equal((await inspectInstalledPayload(installed, { host })).treeHash, expected);
    for (const [dir, name] of [["hooks", "hooks.json"], ["licenses", "NOTICE"]]) {
      const file = join(installed, dir, name);
      await writeFile(file, "tampered\n");
      assert.notEqual((await inspectInstalledPayload(installed, { host })).treeHash, expected, `${host} ignored changed ${dir}/${name}`);
      await rm(file);
      assert.notEqual((await inspectInstalledPayload(installed, { host })).treeHash, expected, `${host} ignored missing ${dir}/${name}`);
      await writeFile(file, `original ${name}\n`);
    }
  }
});

test("native payload bytes are identical with autocrlf true and false", async t => {
  const fixtureRoot = await fixture(t);
  const repo = await mkdtemp(join(tmpdir(), "native-eol-repository-"));
  t.after(() => rm(repo, { recursive: true, force: true }));
  const sourcePayload = join(repo, "plugins", "agentic-engineering-skills");
  await mkdir(join(repo, "plugins"), { recursive: true });
  await cp(fixtureRoot, sourcePayload, { recursive: true });
  for (const directory of ["agents", "hooks", "licenses"]) await mkdir(join(sourcePayload, directory));
  await writeFile(join(sourcePayload, "agents", "reviewer.md"), "---\nname: reviewer\n---\nrole contract\n");
  await writeFile(join(sourcePayload, "hooks", "hooks.json"), "{\n  \"hooks\": {}\n}\n");
  await writeFile(join(sourcePayload, "licenses", "NOTICE"), "original notice\nsecond line\n");
  await writeFile(join(repo, ".gitattributes"), await readFile(new URL("../.gitattributes", import.meta.url)));
  const env = { ...process.env, GIT_CONFIG_NOSYSTEM: "1", GIT_CONFIG_GLOBAL: join(repo, "no-global-config"), GIT_TERMINAL_PROMPT: "0" };
  await exec("git", ["-C", repo, "init", "--quiet"], { env });
  await exec("git", ["-C", repo, "-c", "core.autocrlf=false", "-c", "core.safecrlf=false", "add", "--all"], { env });
  const targets = [];
  for (const value of ["false", "true"]) {
    const target = join(repo, `checkout-${value}`);
    await mkdir(target);
    const prefix = `${target.replaceAll("\\", "/")}/`;
    await exec("git", ["-C", repo, "-c", `core.autocrlf=${value}`, "-c", "core.safecrlf=false", "checkout-index", "--all", `--prefix=${prefix}`], { env });
    targets.push(join(target, "plugins", "agentic-engineering-skills"));
  }
  for (const host of ["codex", "claude"]) {
    assert.equal((await inspectInstalledPayload(targets[0], { host })).treeHash, (await inspectInstalledPayload(targets[1], { host })).treeHash, `${host} plugin bytes differ across autocrlf settings`);
  }
});

test("full native receipt detects drift outside both hosts' discovery roots", async t => {
  const root = await fixture(t);
  const receipt = await mockReceipt(root);
  const before = await Promise.all(["codex", "claude"].map(host => inspectInstalledPayload(root, { host })));
  await writeFile(join(root, "unused/hidden/SKILL.md"), "changed but not discovered\n");
  const after = await Promise.all(["codex", "claude"].map(host => inspectInstalledPayload(root, { host })));
  for (let i = 0; i < before.length; i++) assert.equal(after[i].treeHash, before[i].treeHash);
  await assert.rejects(() => verifyNativeReceipt(receipt, { included, includedByHost, payloadRoot: root }), /full tree hash mismatch/i);
});
