import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import { sha256File, sha256Path } from "./hash.mjs";

const hex = (n) => new RegExp(`^[0-9a-f]{${n}}$`, "i");
const common = new Set(["name", "sourceType", "localSha256", "dependencies", "excluded", "exclusionReason"]);
const upstreamFields = ["repository", "revision", "upstreamPath", "sha256", "localSha256"];
const originalFields = ["localSha256", "releaseCommit", "license"];

export function validateManifest(manifest) {
  if (!manifest || !Array.isArray(manifest.skills)) throw new Error("manifest.skills must be an array");
  const seen = new Set();
  const values = manifest.skills.map(entry => {
    if (!entry?.name || seen.has(entry.name)) throw new Error(`invalid or duplicate name: ${entry?.name}`);
    seen.add(entry.name);
    if (!["vendor", "adapted", "original"].includes(entry.sourceType)) throw new Error(`invalid sourceType for ${entry.name}`);
    if (entry.excluded && !entry.exclusionReason) throw new Error(`excluded entry ${entry.name} requires exclusionReason`);
    const allowed = new Set(common);
    if (entry.sourceType === "original") {
      for (const key of originalFields) allowed.add(key);
      for (const key of upstreamFields.filter(k => k !== "localSha256")) if (key in entry) throw new Error(`forbidden upstream field ${key} on original ${entry.name}`);
      for (const key of originalFields) if (!entry[key]) throw new Error(`${entry.name} requires ${key}`);
      if (!hex(40).test(entry.releaseCommit)) throw new Error(`invalid releaseCommit for ${entry.name}`);
    } else {
      for (const key of upstreamFields) allowed.add(key);
      if (entry.sourceType === "adapted") { allowed.add("changeNotice"); allowed.add("patchPath"); }
      for (const key of upstreamFields) if (!entry[key]) throw new Error(`${entry.name} requires ${key}`);
      if (!hex(40).test(entry.revision)) throw new Error(`invalid revision for ${entry.name}`);
      if (!hex(64).test(entry.sha256) || !hex(64).test(entry.localSha256)) throw new Error(`invalid sha256 for ${entry.name}`);
      if (entry.sourceType === "adapted" && (!entry.changeNotice?.trim() || !/^manifests\/patches\/[^/]+\.patch$/.test(entry.patchPath ?? ""))) throw new Error(`adapted ${entry.name} requires changeNotice and patchPath under manifests/patches`);
    }
    for (const key of Object.keys(entry)) if (!allowed.has(key)) throw new Error(`field ${key} not allowed for ${entry.sourceType}`);
    return { ...entry, dependencies: [...(entry.dependencies ?? [])].sort() };
  }).sort((a, b) => a.name.localeCompare(b.name));
  dependencyOrder(values);
  return values;
}

export function dependencyOrder(entries) {
  const byName = new Map(entries.map(x => [x.name, x]));
  const color = new Map(), result = [];
  function visit(name, trail = []) {
    if (!byName.has(name)) throw new Error(`unknown dependency: ${name}`);
    if (color.get(name) === 1) throw new Error(`dependency cycle: ${[...trail, name].join(" -> ")}`);
    if (color.get(name) === 2) return;
    color.set(name, 1);
    for (const dep of byName.get(name).dependencies ?? []) visit(dep, [...trail, name]);
    color.set(name, 2); result.push(name);
  }
  for (const name of [...byName.keys()].sort()) visit(name);
  return result;
}

export function compareLockDirectories(entries, directories) {
  const expected = entries.filter(x => !x.excluded).map(x => x.name).sort(), actual = [...directories].sort();
  if (JSON.stringify(expected) !== JSON.stringify(actual)) throw new Error(`lock/directory mismatch: lock=${expected} directories=${actual}`);
}

export async function verifyLocalEntries(entries, root, skillsRoot = "plugins/agentic-engineering-skills/skills") {
  for (const entry of entries.filter(x => !x.excluded)) {
    const skillDir = join(root, skillsRoot, entry.name);
    const actual = entry.upstreamPath?.endsWith("/") ? await sha256Path(skillDir) : await sha256File(join(skillDir, "SKILL.md"));
    if (actual !== entry.localSha256) throw new Error(`tamper detected for ${entry.name}: expected ${entry.localSha256}, got ${actual}`);
  }
}

export async function loadManifest(path) { return validateManifest(JSON.parse(await readFile(path, "utf8"))); }
export async function listFlatSkillDirectories(root) {
  try { return (await readdir(root, { withFileTypes: true })).filter(x => x.isDirectory()).map(x => x.name).sort(); }
  catch (e) { if (e.code === "ENOENT") return []; throw e; }
}
