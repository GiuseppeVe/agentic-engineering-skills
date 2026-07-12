import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { expectedSkills } from "./expected-inventory.mjs";
import { hashPayloadTree, verifyNativeReceipt } from "../scripts/lib/native-receipt.mjs";

const root = new URL("../", import.meta.url);
const payloadRoot = new URL("../plugins/agentic-engineering-skills/skills/", import.meta.url);

test("tracked native receipt proves both isolated native payload inventories", async () => {
  const receipt = JSON.parse(await readFile(new URL("../manifests/native-discovery.json", import.meta.url), "utf8"));
  const result = await verifyNativeReceipt(receipt, { included: expectedSkills, payloadRoot });
  assert.equal(result.count, 19);
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
