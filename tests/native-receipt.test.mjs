import assert from "node:assert/strict";
import { cp, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import test from "node:test";
import { expectedSkills } from "./expected-inventory.mjs";
import { hashPayloadTree, inspectInstalledPayload, locateInstalledPayload, verifyNativeReceipt } from "../scripts/lib/native-receipt.mjs";

const root = new URL("../", import.meta.url);
const payloadRoot = new URL("../plugins/agentic-engineering-skills/skills/", import.meta.url);

test("tracked native receipt proves both isolated native payload inventories", async () => {
  const receipt = JSON.parse(await readFile(new URL("../manifests/native-discovery.json", import.meta.url), "utf8"));
  const result = await verifyNativeReceipt(receipt, { included: expectedSkills, payloadRoot });
  assert.equal(result.count, 20);
  assert.equal(result.hash, await hashPayloadTree(payloadRoot));
});

test("native receipt rejects host inventory drift", async () => {
  const receipt = JSON.parse(await readFile(new URL("../manifests/native-discovery.json", import.meta.url), "utf8"));
  receipt.hosts.codex.discoveredSkills.pop();
  await assert.rejects(() => verifyNativeReceipt(receipt, { included: expectedSkills, payloadRoot }), /codex native inventory mismatch/);
});

test("native receipt rejects payload hash drift", async () => {
  const receipt = JSON.parse(await readFile(new URL("../manifests/native-discovery.json", import.meta.url), "utf8"));
  receipt.installedPayload.treeHash = `sha256:${"0".repeat(64)}`;
  await assert.rejects(() => verifyNativeReceipt(receipt, { included: expectedSkills, payloadRoot }), /payload hash mismatch/);
});

test("locates and hashes fake native host install from CLI JSON", async () => {
  const home = await mkdtemp(join(tmpdir(), "native-host-"));
  const plugin = join(home, "cache", "agentic-engineering-skills", "0.1.0");
  await cp(payloadRoot, join(plugin, "skills"), { recursive: true });
  const located = await locateInstalledPayload({ host: "codex", jsonDocuments: [JSON.stringify({ installPath: plugin })], searchRoots: [] });
  assert.equal(located.basis, "native-cli-json");
  assert.deepEqual(located.skills, expectedSkills);
  assert.equal(located.treeHash, await hashPayloadTree(payloadRoot));
});

test("locates fake host cache and detects installed byte drift", async () => {
  const home = await mkdtemp(join(tmpdir(), "native-host-"));
  const plugin = join(home, "plugins", "agentic-engineering-skills");
  await cp(payloadRoot, join(plugin, "skills"), { recursive: true });
  const located = await locateInstalledPayload({ host: "claude", searchRoots: [home] });
  assert.equal(located.basis, "host-cache-scan");
  await writeFile(join(located.root, expectedSkills[0], "SKILL.md"), "drift\n");
  const drifted = await inspectInstalledPayload(plugin);
  assert.notEqual(drifted.treeHash, await hashPayloadTree(payloadRoot));
});
