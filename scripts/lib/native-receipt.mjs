import { createHash } from "node:crypto";
import { readdir, readFile, lstat, realpath } from "node:fs/promises";
import { basename, dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const hosts = ["codex", "claude"];

export async function hashPayloadTree(root) {
  root = asPath(root);
  return hashFiles(root, await walk(root));
}

// Inspect the components the selected host is configured to discover, rather
// than treating every directory copied into its cache as an available skill.
export async function inspectInstalledPayload(root, { host = "codex" } = {}) {
  assertHost(host);
  root = pluginRoot(root);
  const rootInfo = await lstat(root);
  if (!rootInfo.isDirectory() || rootInfo.isSymbolicLink()) throw new Error(`invalid plugin root: ${root}`);
  const canonicalRoot = await realpath(root);
  const manifestPath = host === "codex" ? ".codex-plugin/plugin.json" : ".claude-plugin/plugin.json";
  await validateContainedPath(root, canonicalRoot, join(root, manifestPath), "file");
  const manifest = JSON.parse(await readFile(join(root, manifestPath), "utf8"));
  let skillRoots;
  let configurationPath = manifestPath;
  if (host === "claude") {
    skillRoots = ["skills", ...configuredRoots(manifest.skills)];
  } else {
    // A recognized portable manifest takes precedence over a Codex overlay.
    let portable;
    try {
      await validateContainedPath(root, canonicalRoot, join(root, "plugin.json"), "file");
      portable = JSON.parse(await readFile(join(root, "plugin.json"), "utf8"));
    }
    catch (error) { if (error.code !== "ENOENT") throw error; }
    if (portable?.$schema?.includes("agent-plugins.org/")) {
      skillRoots = ["skills"];
      configurationPath = "plugin.json";
    } else {
      skillRoots = configuredRoots(manifest.skills);
    }
  }
  skillRoots = [...new Set(skillRoots)].sort();
  const skillPaths = new Map();
  const files = [join(root, configurationPath)];
  for (const configuredRoot of skillRoots) {
    const directory = join(root, configuredRoot);
    let info;
    try { info = await validateContainedPath(root, canonicalRoot, directory, "directory"); }
    catch (error) {
      // Claude's automatic default is optional; declared paths are required.
      if (host === "claude" && configuredRoot === "skills" && error.code === "ENOENT") continue;
      throw error;
    }
    if (!info.isDirectory() || info.isSymbolicLink()) throw new Error(`invalid configured skill directory: ${configuredRoot}`);
    const directSkill = await isSkill(directory);
    const candidates = directSkill ? [directory] : (await readdir(directory, { withFileTypes: true }))
      .filter(entry => entry.isDirectory()).map(entry => join(directory, entry.name));
    for (const candidate of candidates) {
      if (!await isSkill(candidate)) continue;
      await validateContainedPath(root, canonicalRoot, join(candidate, "SKILL.md"), "file");
      const name = basename(candidate);
      const existing = skillPaths.get(name);
      if (existing && existing !== candidate) throw new Error(`${host} duplicate discovered skill: ${name}`);
      if (existing) continue;
      skillPaths.set(name, candidate);
      files.push(...await walk(candidate));
    }
  }
  // Both hosts require bundled hooks and legal files. Claude also discovers
  // agent definitions in the plugin's default agents directory.
  for (const name of ["hooks", "licenses", ...(host === "claude" ? ["agents"] : [])]) {
    const directory = join(root, name);
    let exists = false;
    try {
      await validateContainedPath(root, canonicalRoot, directory, "directory");
      exists = true;
    } catch (error) { if (error.code !== "ENOENT") throw error; }
    if (exists) files.push(...await walk(directory));
  }
  return {
    root, skills: [...skillPaths.keys()].sort(), skillRoots,
    treeHash: await hashFiles(root, [...new Set(files)]),
    fullTreeHash: await hashPayloadTree(root),
  };
}

export async function verifyNativeReceipt(receipt, { included, payloadRoot, includedByHost }) {
  if (receipt.schemaVersion !== 3) throw new Error("native receipt schemaVersion must be 3");
  if (!["isolated-native-installs", "task-10-isolated-native-installs"].includes(receipt.evidenceSource)) throw new Error("native receipt has invalid evidenceSource");
  const expected = [...included].sort();
  equalInventory(sortedUnique(receipt.installedPayload?.skills, "installedPayload.skills"), expected, "installed payload");
  if (receipt.installedPayload?.root !== "plugins/agentic-engineering-skills") throw new Error("native receipt payload root mismatch");
  const root = pluginRoot(payloadRoot);
  const results = {};
  const union = new Set();
  for (const host of hosts) {
    const current = await inspectInstalledPayload(root, { host });
    const hostExpected = includedByHost ? sortedUnique(includedByHost[host], `includedByHost.${host}`) : current.skills;
    equalInventory(current.skills, hostExpected, `${host} configured source`);
    for (const name of hostExpected) union.add(name);
    const evidence = receipt.hosts?.[host];
    if (!evidence || typeof evidence.version !== "string" || !evidence.version.trim()) throw new Error(`${host} native receipt missing version`);
    equalInventory(sortedUnique(evidence.discoveredSkills, `${host}.discoveredSkills`), hostExpected, host);
    if (evidence.discoveryBasis !== "isolated-installed-manifest") throw new Error(`${host} native receipt discoveryBasis mismatch`);
    const installed = evidence.installedPayload;
    equalInventory(sortedUnique(installed?.skills, `${host}.installedPayload.skills`), hostExpected, `${host} installed payload`);
    equalInventory(sortedUnique(installed?.skillRoots, `${host}.installedPayload.skillRoots`), current.skillRoots, `${host} configured skill roots`);
    if (!/^sha256:[0-9a-f]{64}$/.test(installed?.treeHash ?? "")) throw new Error(`${host} native receipt payload treeHash is invalid`);
    if (installed.treeHash !== current.treeHash) throw new Error(`${host} native receipt payload hash mismatch: expected ${installed.treeHash}; got ${current.treeHash}`);
    if (!/^sha256:[0-9a-f]{64}$/.test(installed.fullTreeHash ?? "")) throw new Error(`${host} native receipt full tree hash is invalid`);
    if (installed.fullTreeHash !== current.fullTreeHash) throw new Error(`${host} native receipt full tree hash mismatch: expected ${installed.fullTreeHash}; got ${current.fullTreeHash}`);
    if (!Array.isArray(evidence.commands) || evidence.commands.length === 0) throw new Error(`${host} native receipt missing commands`);
    for (const [index, command] of evidence.commands.entries()) {
      if (typeof command.command !== "string" || !command.command.trim()) throw new Error(`${host} command ${index} missing exact command`);
      if (!Number.isInteger(command.exitCode)) throw new Error(`${host} command ${index} missing integer exitCode`);
    }
    if (evidence.commands.some(command => command.exitCode !== 0)) throw new Error(`${host} native receipt contains failed command`);
    results[host] = { hash: current.treeHash, count: current.skills.length };
  }
  equalInventory([...union].sort(), expected, "configured host union");
  const hash = `sha256:${createHash("sha256").update(JSON.stringify(results)).digest("hex")}`;
  return { count: expected.length, hash, hosts: results };
}

export async function locateInstalledPayload({ host, explicitRoot, jsonDocuments = [], searchRoots = [] }) {
  assertHost(host);
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
        const payload = await inspectInstalledPayload(path, { host });
        if (payload.skills.length) matches.push({ ...payload, basis: candidate.basis ?? "host-cache-scan" });
      } catch (error) { if (!["ENOENT", "ENOTDIR"].includes(error.code)) throw error; }
    }
  }
  const unique = [...new Map(matches.map(match => [match.root, match])).values()];
  if (unique.length !== 1) throw new Error(`${host} installed plugin root lookup expected 1 match; found ${unique.length}: ${unique.map(x => x.root).join(", ")}`);
  return unique[0];
}

function assertHost(host) {
  if (!hosts.includes(host)) throw new Error(`unsupported host: ${host}`);
}

function asPath(root) {
  return root instanceof URL ? fileURLToPath(root) : resolve(root);
}

function pluginRoot(root) {
  root = asPath(root);
  return ["skills", "claude-skills"].includes(basename(root)) ? dirname(root) : root;
}

// Checking only the leaf misses junctions or symlinks in an ancestor. Reject
// redirected segments and verify their resolved locations against the plugin.
async function validateContainedPath(root, canonicalRoot, path, kind) {
  const pathWithinRoot = relative(root, path);
  if (isAbsolute(pathWithinRoot) || pathWithinRoot === ".." || pathWithinRoot.startsWith(`..${sep}`)) throw new Error(`payload path escapes plugin root: ${path}`);
  let current = root;
  let info;
  const segments = pathWithinRoot.split(sep).filter(Boolean);
  for (const [index, segment] of segments.entries()) {
    current = join(current, segment);
    info = await lstat(current);
    if (info.isSymbolicLink()) throw new Error(`redirected payload path segment: ${current}`);
    const canonical = await realpath(current);
    const withinCanonicalRoot = relative(canonicalRoot, canonical);
    if (isAbsolute(withinCanonicalRoot) || withinCanonicalRoot === ".." || withinCanonicalRoot.startsWith(`..${sep}`)) throw new Error(`payload path escapes plugin root: ${current}`);
    const last = index === segments.length - 1;
    if (!last && !info.isDirectory()) throw new Error(`payload path ancestor is not a directory: ${current}`);
    if (last && (kind === "file" ? !info.isFile() : !info.isDirectory())) throw new Error(`invalid payload ${kind}: ${current}`);
  }
  return info;
}

function configuredRoots(value) {
  if (value === undefined) return [];
  const values = typeof value === "string" ? [value] : value;
  if (!Array.isArray(values) || values.some(path => typeof path !== "string")) throw new Error("manifest skills must be a path or path array");
  return values.map(path => {
    if (!path.startsWith("./") || path.includes("\\") || path.includes("\0") || path.slice(2).split("/").includes("..")) throw new Error(`invalid manifest skill path: ${path}`);
    const clean = path.slice(2).replace(/\/+$/, "");
    if (!clean || clean.split("/").some(part => part === "" || part === ".")) throw new Error(`invalid manifest skill path: ${path}`);
    return clean;
  });
}

async function isSkill(directory) {
  try {
    const info = await lstat(join(directory, "SKILL.md"));
    if (!info.isFile() || info.isSymbolicLink()) throw new Error(`invalid skill entrypoint: ${directory}`);
    return true;
  } catch (error) { if (error.code === "ENOENT") return false; throw error; }
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

async function hashFiles(root, files) {
  const digest = createHash("sha256");
  for (const file of [...files].sort()) {
    const path = relative(root, file).split(sep).join("/");
    digest.update(path, "utf8");
    digest.update("\0");
    digest.update(createHash("sha256").update(await readFile(file)).digest("hex"), "ascii");
    digest.update("\n");
  }
  return `sha256:${digest.digest("hex")}`;
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
  if (entries.some(entry => entry.isDirectory() && [".codex-plugin", ".claude-plugin"].includes(entry.name))) {
    if (/agentic-engineering-skills/.test(directory)) return [{ path: directory, basis: "host-cache-scan" }];
  }
  const found = [];
  for (const entry of entries) if (entry.isDirectory()) found.push(...await findSkillRoots(join(directory, entry.name), depth - 1));
  return found;
}
