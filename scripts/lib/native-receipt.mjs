import { createHash } from "node:crypto";
import { readdir, readFile } from "node:fs/promises";
import { relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

export async function hashPayloadTree(root) {
  root = root instanceof URL ? fileURLToPath(root) : root;
  const files = await walk(root);
  const digest = createHash("sha256");
  for (const file of files) {
    const path = relative(root, file).split(sep).join("/");
    const contents = await readFile(file);
    digest.update(path, "utf8");
    digest.update("\0");
    digest.update(createHash("sha256").update(contents).digest("hex"), "ascii");
    digest.update("\n");
  }
  return `sha256:${digest.digest("hex")}`;
}

export async function verifyNativeReceipt(receipt, { included, payloadRoot }) {
  if (receipt.schemaVersion !== 1) throw new Error("native receipt schemaVersion must be 1");
  if (receipt.evidenceSource !== "task-10-isolated-native-installs") throw new Error("native receipt has invalid evidenceSource");
  const expected = [...included].sort();
  const receiptSkills = sortedUnique(receipt.installedPayload?.skills, "installedPayload.skills");
  equalInventory(receiptSkills, expected, "installed payload");
  if (receipt.installedPayload?.root !== "plugins/agentic-engineering-skills/skills") throw new Error("native receipt payload root mismatch");
  if (!/^sha256:[0-9a-f]{64}$/.test(receipt.installedPayload?.treeHash ?? "")) throw new Error("native receipt payload treeHash is invalid");
  const actualHash = await hashPayloadTree(payloadRoot instanceof URL ? fileURLToPath(payloadRoot) : resolve(payloadRoot));
  if (receipt.installedPayload.treeHash !== actualHash) throw new Error(`native receipt payload hash mismatch: expected ${receipt.installedPayload.treeHash}; got ${actualHash}`);
  for (const host of ["codex", "claude"]) {
    const evidence = receipt.hosts?.[host];
    if (!evidence || typeof evidence.version !== "string" || !evidence.version.trim()) throw new Error(`${host} native receipt missing version`);
    equalInventory(sortedUnique(evidence.discoveredSkills, `${host}.discoveredSkills`), expected, host);
    if (evidence.discoveryBasis !== "isolated-installed-payload") throw new Error(`${host} native receipt discoveryBasis mismatch`);
    if (!Array.isArray(evidence.commands) || evidence.commands.length === 0) throw new Error(`${host} native receipt missing commands`);
    for (const [index, command] of evidence.commands.entries()) {
      if (typeof command.command !== "string" || !command.command.trim()) throw new Error(`${host} command ${index} missing exact command`);
      if (!Number.isInteger(command.exitCode)) throw new Error(`${host} command ${index} missing integer exitCode`);
    }
    if (evidence.commands.some(command => command.exitCode !== 0)) throw new Error(`${host} native receipt contains failed command`);
  }
  return { hash: actualHash, count: expected.length };
}

function sortedUnique(value, field) {
  if (!Array.isArray(value) || value.some(item => typeof item !== "string")) throw new Error(`native receipt ${field} must be a string array`);
  const sorted = [...new Set(value)].sort();
  if (sorted.length !== value.length) throw new Error(`native receipt ${field} contains duplicates`);
  return sorted;
}

function equalInventory(actual, expected, label) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) throw new Error(`${label} native inventory mismatch: expected ${expected.join(", ")}; got ${actual.join(", ")}`);
}

async function walk(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const paths = [];
  for (const entry of entries.sort((a, b) => a.name.localeCompare(b.name))) {
    const path = resolve(directory, entry.name);
    if (entry.isDirectory()) paths.push(...await walk(path));
    else if (entry.isFile()) paths.push(path);
    else throw new Error(`unsupported payload entry: ${path}`);
  }
  return paths.sort();
}
