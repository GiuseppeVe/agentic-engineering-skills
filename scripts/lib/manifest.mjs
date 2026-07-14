import { readdir, readFile } from "node:fs/promises";
import { isAbsolute, join, posix, relative, resolve } from "node:path";
import { sha256File, sha256Path } from "./hash.mjs";

const hex = (n) => new RegExp(`^[0-9a-f]{${n}}$`, "i");
const common = new Set(["name", "sourceType", "localSha256", "dependencies", "excluded", "exclusionReason"]);
const upstreamFields = ["repository", "revision", "upstreamPath", "sha256", "localSha256"];
const originalFields = ["localSha256", "releaseCommit", "license", "payloadType"];
const portableSkillName = /^[a-z0-9][a-z0-9-]*$/;

function validateSkillName(name) {
  if (typeof name !== "string" || !portableSkillName.test(name)) throw new Error(`invalid portable skill name: ${name}`);
}

export function validateManifest(manifest) {
  if (!manifest || !Array.isArray(manifest.skills)) throw new Error("manifest.skills must be an array");
  const seen = new Set();
  const values = manifest.skills.map(entry => {
    validateSkillName(entry?.name);
    if (seen.has(entry.name)) throw new Error(`invalid or duplicate name: ${entry.name}`);
    seen.add(entry.name);
    if (!["vendor", "adapted", "original"].includes(entry.sourceType)) throw new Error(`invalid sourceType for ${entry.name}`);
    if (entry.excluded && !entry.exclusionReason) throw new Error(`excluded entry ${entry.name} requires exclusionReason`);
    const allowed = new Set(common);
    if (entry.sourceType === "original") {
      for (const key of originalFields) allowed.add(key);
      for (const key of upstreamFields.filter(k => k !== "localSha256")) if (key in entry) throw new Error(`forbidden upstream field ${key} on original ${entry.name}`);
      for (const key of originalFields) if (!entry[key]) throw new Error(`${entry.name} requires ${key}`);
      if (!hex(40).test(entry.releaseCommit)) throw new Error(`invalid releaseCommit for ${entry.name}`);
      if (!["file", "directory"].includes(entry.payloadType)) throw new Error(`invalid payloadType for ${entry.name}`);
    } else {
      for (const key of upstreamFields) allowed.add(key);
      allowed.add("licenseFiles");
      if (entry.sourceType === "adapted") { allowed.add("changeNotice"); allowed.add("patchPath"); }
      for (const key of upstreamFields) if (!entry[key]) throw new Error(`${entry.name} requires ${key}`);
      if (!hex(40).test(entry.revision)) throw new Error(`invalid revision for ${entry.name}`);
      if (!hex(64).test(entry.sha256) || !hex(64).test(entry.localSha256)) throw new Error(`invalid sha256 for ${entry.name}`);
      if (!Array.isArray(entry.licenseFiles) || entry.licenseFiles.length === 0 || entry.licenseFiles.some(file => {
        if (!file || Object.keys(file).sort().join(",") !== "path,sha256,upstreamPath") return true;
        return !normalizedRelative(file.path) || !normalizedRelative(file.upstreamPath) || !hex(64).test(file.sha256);
      })) throw new Error(`${entry.name} requires non-empty normalized licenseFiles`);
      if (entry.sourceType === "adapted" && (!entry.changeNotice?.trim() || !/^manifests\/patches\/[^/]+\.patch$/.test(entry.patchPath ?? ""))) throw new Error(`adapted ${entry.name} requires changeNotice and patchPath under manifests/patches`);
    }
    for (const key of Object.keys(entry)) if (!allowed.has(key)) throw new Error(`field ${key} not allowed for ${entry.sourceType}`);
    return { ...entry, dependencies: [...(entry.dependencies ?? [])].sort() };
  }).sort((a, b) => a.name.localeCompare(b.name));
  dependencyOrder(values);
  return values;
}

function normalizedRelative(path) {
  return typeof path === "string" && path.length > 0 && !path.includes("\\") && !path.startsWith("/") && posix.normalize(path) === path && !path.split("/").includes("..");
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
    const actual = entry.payloadType === "directory" || entry.upstreamPath?.endsWith("/")
      ? await sha256Path(skillDir)
      : await sha256File(join(skillDir, "SKILL.md"));
    if (actual !== entry.localSha256) throw new Error(`tamper detected for ${entry.name}: expected ${entry.localSha256}, got ${actual}`);
  }
}

export async function loadManifest(path) { return validateManifest(JSON.parse(await readFile(path, "utf8"))); }
export async function listFlatSkillDirectories(root) {
  try { return (await readdir(root, { withFileTypes: true })).filter(x => x.isDirectory()).map(x => x.name).sort(); }
  catch (e) { if (e.code === "ENOENT") return []; throw e; }
}

const localRootEnvironment = { projectSkills: "AGENTIC_PROJECT_SKILLS_ROOT", userSkills: "AGENTIC_USER_SKILLS_ROOT" };

export function resolveAcquisitionRoot(source, environment = process.env) {
  const variable = localRootEnvironment[source.localRoot];
  if (!variable) throw new Error(`unknown localRoot for ${source.name}: ${source.localRoot}`);
  const configuredRoot = environment[variable];
  if (!configuredRoot) throw new Error(`${variable} is required to acquire ${source.name}`);
  return resolve(configuredRoot);
}

export function resolveAcquisitionPath(source, environment = process.env) {
  if (!source.localPath || isAbsolute(source.localPath) || source.localPath.split(/[\\/]/).includes("..")) throw new Error(`localPath must be portable and relative for ${source.name}`);
  const root = resolveAcquisitionRoot(source, environment), path = resolve(root, source.localPath);
  if (relative(root, path).startsWith("..")) throw new Error(`localPath escapes ${source.localRoot} for ${source.name}`);
  return path;
}

export function validateSourceManifest(manifest) {
  if (!manifest || !Array.isArray(manifest.skills)) throw new Error("source manifest skills must be an array");
  for (const source of manifest.skills) validateSkillName(source?.name);
  for (const source of manifest.skills.filter(x => x.sourceType === "adapted" || x.sourceType === "original")) {
    const hasLocalAcquisition = source.localRoot !== undefined || source.localPath !== undefined;
    if (source.sourceType === "original" && !hasLocalAcquisition) throw new Error(`original ${source.name} requires local acquisition fields`);
    if (hasLocalAcquisition) {
      if (!localRootEnvironment[source.localRoot]) throw new Error(`invalid localRoot for ${source.name}`);
      if (!source.localPath || isAbsolute(source.localPath) || source.localPath.split(/[\\/]/).includes("..")) throw new Error(`localPath must be portable and relative for ${source.name}`);
    }
  }
  return [...manifest.skills].sort((a, b) => a.name.localeCompare(b.name));
}
