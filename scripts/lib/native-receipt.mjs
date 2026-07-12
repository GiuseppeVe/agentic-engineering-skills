import { createHash } from "node:crypto";
import { readdir, readFile, stat } from "node:fs/promises";
import { basename, dirname, join, relative, resolve, sep } from "node:path";
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
  if (receipt.schemaVersion !== 2) throw new Error("native receipt schemaVersion must be 2");
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
    if (evidence.installedPayload?.treeHash !== receipt.installedPayload.treeHash) throw new Error(`${host} installed payload hash mismatch`);
    equalInventory(sortedUnique(evidence.installedPayload?.skills, `${host}.installedPayload.skills`), expected, `${host} installed payload`);
    if (!Array.isArray(evidence.commands) || evidence.commands.length === 0) throw new Error(`${host} native receipt missing commands`);
    for (const [index, command] of evidence.commands.entries()) {
      if (typeof command.command !== "string" || !command.command.trim()) throw new Error(`${host} command ${index} missing exact command`);
      if (!Number.isInteger(command.exitCode)) throw new Error(`${host} command ${index} missing integer exitCode`);
    }
    if (evidence.commands.some(command => command.exitCode !== 0)) throw new Error(`${host} native receipt contains failed command`);
  }
  return { hash: actualHash, count: expected.length };
}

export async function inspectInstalledPayload(root) {
  root = resolve(root);
  const skillsRoot = basename(root) === "skills" ? root : join(root, "skills");
  const entries = await readdir(skillsRoot, { withFileTypes: true });
  const skills = [];
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    try { await stat(join(skillsRoot, entry.name, "SKILL.md")); skills.push(entry.name); }
    catch (error) { if (error.code !== "ENOENT") throw error; }
  }
  return { root: skillsRoot, skills: skills.sort(), treeHash: await hashPayloadTree(skillsRoot) };
}

export async function locateInstalledPayload({ host, explicitRoot, jsonDocuments = [], searchRoots = [] }) {
  if (!['codex', 'claude'].includes(host)) throw new Error(`unsupported host: ${host}`);
  const candidates = [];
  if (explicitRoot) candidates.push({ path: explicitRoot, basis: "explicit-root" });
  const absoluteSearchRoots = searchRoots.map(root => resolve(root));
  for (const document of jsonDocuments) {
    let value;
    try { value = JSON.parse(document); } catch { continue; }
    for (const path of jsonPaths(value)) {
      const absolute = resolve(path);
      if (!absoluteSearchRoots.length || absoluteSearchRoots.some(root => absolute === root || absolute.startsWith(`${root}${sep}`))) candidates.push({ path: absolute, basis: "native-cli-json" });
    }
  }
  for (const root of absoluteSearchRoots) candidates.push(...await findSkillRoots(root, 7));
  const matches = [];
  for (const candidate of candidates) {
    for (const path of candidateVariants(candidate.path)) {
      try {
        const payload = await inspectInstalledPayload(path);
        if (payload.skills.length) matches.push({ ...payload, basis: candidate.basis ?? "host-cache-scan" });
      } catch (error) { if (!["ENOENT", "ENOTDIR"].includes(error.code)) throw error; }
    }
  }
  const unique = [...new Map(matches.map(match => [match.root, match])).values()];
  if (unique.length !== 1) throw new Error(`${host} installed plugin root lookup expected 1 match; found ${unique.length}: ${unique.map(x => x.root).join(", ")}`);
  return unique[0];
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

function *jsonPaths(value) {
  if (typeof value === "string" && (/[/\\]/.test(value) || value.startsWith("."))) yield value;
  else if (Array.isArray(value)) for (const item of value) yield *jsonPaths(item);
  else if (value && typeof value === "object") for (const item of Object.values(value)) yield *jsonPaths(item);
}

function candidateVariants(path) {
  const absolute = resolve(path);
  return [absolute, join(absolute, "skills"), dirname(absolute)];
}

async function findSkillRoots(directory, depth) {
  if (depth < 0) return [];
  let entries;
  try { entries = await readdir(directory, { withFileTypes: true }); }
  catch (error) { if (["ENOENT", "ENOTDIR", "EACCES"].includes(error.code)) return []; throw error; }
  if (entries.some(entry => entry.isDirectory() && entry.name === "skills")) {
    const pluginRoot = directory;
    if (/agentic-engineering-skills/.test(pluginRoot)) return [{ path: pluginRoot, basis: "host-cache-scan" }];
  }
  const found = [];
  for (const entry of entries) if (entry.isDirectory()) found.push(...await findSkillRoots(join(directory, entry.name), depth - 1));
  return found;
}
