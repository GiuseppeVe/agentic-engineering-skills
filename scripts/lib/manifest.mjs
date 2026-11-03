import { lstat, mkdir, open, readdir, readFile, realpath, rename, rmdir, rm } from "node:fs/promises";
import { basename, dirname, isAbsolute, join, posix, relative, resolve, sep } from "node:path";
import { constants as fsConstants } from "node:fs";
import { createHash, randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";
import { sha256File, sha256Path } from "./hash.mjs";

export const PATCH_CHUNK_POINTER_MAGIC = "AGENTIC-PATCH-CHUNKS/1\n";
export const PATCH_CHUNK_BYTES = 900 * 1024;
export const MAX_PATCH_BYTES = 64 * 1024 * 1024;
export const MAX_PATCH_CHUNKS = 128;
const MAX_PATCH_POINTER_BYTES = 1024 * 1024;
const PATCH_POINTER_PREFIX = Buffer.from("AGENTIC-PATCH-CHUNKS", "utf8");
const patchRepositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const managedPatchRoot = resolve(patchRepositoryRoot, "manifests/patches");

const hex = (n) => new RegExp(`^[0-9a-f]{${n}}$`, "i");
const common = new Set(["name", "sourceType", "localSha256", "dependencies", "excluded", "exclusionReason", "payloadPath"]);
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
    if (entry.payloadPath !== undefined && ![`plugins/agentic-engineering-skills/skills/${entry.name}`, `plugins/agentic-engineering-skills/claude-skills/${entry.name}`].includes(entry.payloadPath)) throw new Error(`invalid payloadPath for ${entry.name}`);
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
      if (entry.sourceType === "adapted" && (!entry.changeNotice?.trim() || !/^manifests\/patches\/[^/]+\.patch$/.test(entry.patchPath ?? "") || !normalizedRelative(entry.patchPath))) throw new Error(`adapted ${entry.name} requires changeNotice and a normalized patchPath under manifests/patches`);
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

function sha256(bytes) { return createHash("sha256").update(bytes).digest("hex"); }

function isWithin(root, path) {
  const rel = relative(root, resolve(path));
  return rel === "" || (!rel.startsWith(`..${sep}`) && rel !== ".." && !isAbsolute(rel));
}

function resolvePatchTrustRoot(path, trustedRoot) {
  const absolute = resolve(path);
  if (trustedRoot) return resolve(trustedRoot);
  if (isWithin(patchRepositoryRoot, absolute)) return patchRepositoryRoot;
  // External artifacts are accepted only with caller-selected roots (normally isolated test fixtures).
  throw new Error("patch artifacts outside repository require an explicit trustedRoot");
}

async function assertNoLinkedAncestors(path, trustedRoot) {
  const absolute = resolve(path), boundary = resolvePatchTrustRoot(path, trustedRoot);
  if (!isWithin(boundary, absolute)) throw new Error(`path escapes trusted root: ${path}`);
  const rootInfo = await lstat(boundary);
  if (rootInfo.isSymbolicLink() || !rootInfo.isDirectory()) throw new Error(`trusted path root must be a regular directory: ${boundary}`);
  const parts = relative(boundary, absolute).split(sep).filter(Boolean);
  let current = boundary;
  for (const part of parts) {
    current = join(current, part);
    try {
      const info = await lstat(current);
      if (info.isSymbolicLink()) throw new Error(`symlink or junction in patch path: ${current}`);
    } catch (error) { if (error.code !== "ENOENT") throw error; }
  }
}

function pointerMetadata(bytes, patchPath) {
  const magic = Buffer.from(PATCH_CHUNK_POINTER_MAGIC, "utf8");
  if (bytes.subarray(0, PATCH_POINTER_PREFIX.length).equals(PATCH_POINTER_PREFIX) && (bytes.length < magic.length || !bytes.subarray(0, magic.length).equals(magic))) throw new Error("invalid patch chunk pointer magic");
  if (bytes.length < magic.length || !bytes.subarray(0, magic.length).equals(magic)) return null;
  if (bytes.length > MAX_PATCH_POINTER_BYTES) throw new Error("patch chunk pointer exceeds size limit");
  let metadata;
  try {
    const text = new TextDecoder("utf-8", { fatal: true }).decode(bytes.subarray(magic.length));
    metadata = JSON.parse(text);
  } catch { throw new Error("invalid patch chunk pointer JSON or UTF-8"); }
  if (!metadata || Object.keys(metadata).sort().join(",") !== "byteLength,chunks,sha256,version" || metadata.version !== 1) throw new Error("invalid patch chunk pointer schema");
  if (!Number.isSafeInteger(metadata.byteLength) || metadata.byteLength <= PATCH_CHUNK_BYTES || metadata.byteLength > MAX_PATCH_BYTES) throw new Error("invalid patch chunk aggregate byteLength");
  if (typeof metadata.sha256 !== "string" || !/^[0-9a-f]{64}$/.test(metadata.sha256)) throw new Error("invalid patch chunk aggregate SHA-256");
  if (!Array.isArray(metadata.chunks) || metadata.chunks.length === 0 || metadata.chunks.length > MAX_PATCH_CHUNKS) throw new Error("invalid patch chunk count");
  const base = basename(patchPath);
  let total = 0;
  metadata.chunks.forEach((chunk, index) => {
    if (!chunk || Object.keys(chunk).sort().join(",") !== "byteLength,path,sha256") throw new Error("invalid patch chunk entry schema");
    const expected = `${base}.parts/${metadata.sha256}/${String(index + 1).padStart(6, "0")}.txt`;
    if (chunk.path !== expected || !normalizedRelative(chunk.path)) throw new Error(`unsafe or unordered patch chunk path: ${chunk.path}`);
    if (!Number.isSafeInteger(chunk.byteLength) || chunk.byteLength <= 0 || chunk.byteLength > PATCH_CHUNK_BYTES) throw new Error(`invalid patch chunk byteLength: ${chunk.path}`);
    if (typeof chunk.sha256 !== "string" || !/^[0-9a-f]{64}$/.test(chunk.sha256)) throw new Error(`invalid patch chunk SHA-256: ${chunk.path}`);
    if (index < metadata.chunks.length - 1 && chunk.byteLength < PATCH_CHUNK_BYTES - 4) throw new Error(`short non-final patch chunk: ${chunk.path}`);
    total += chunk.byteLength;
  });
  if (total !== metadata.byteLength) throw new Error("patch chunk aggregate byteLength mismatch");
  return metadata;
}

async function regularNoSymlink(path, type, label) {
  const info = await lstat(path);
  if (info.isSymbolicLink() || !(type === "directory" ? info.isDirectory() : info.isFile())) throw new Error(`${label} must be a regular ${type}`);
  return info;
}

async function readBoundedFile(path, maxBytes, label, detectPointer = false, trustedRoot) {
  const boundary = resolvePatchTrustRoot(path, trustedRoot);
  await assertNoLinkedAncestors(path, boundary);
  const pathInfo = await regularNoSymlink(path, "file", label);
  if (pathInfo.size > MAX_PATCH_BYTES) throw new Error(`${label} exceeds size limit`);
  const noFollow = fsConstants.O_NOFOLLOW ?? 0;
  const handle = await open(path, fsConstants.O_RDONLY | noFollow);
  try {
    const openedInfo = await handle.stat();
    if (!openedInfo.isFile() || openedInfo.size > MAX_PATCH_BYTES) throw new Error(`${label} exceeds size limit or is not regular`);
    if (pathInfo.ino && openedInfo.ino && (pathInfo.dev !== openedInfo.dev || pathInfo.ino !== openedInfo.ino)) throw new Error(`${label} changed while opening`);
    const prefixLength = Math.min(openedInfo.size, PATCH_POINTER_PREFIX.length);
    const prefix = Buffer.alloc(prefixLength);
    if (prefixLength) await handle.read(prefix, 0, prefixLength, 0);
    const limit = detectPointer && prefix.equals(PATCH_POINTER_PREFIX) ? MAX_PATCH_POINTER_BYTES : maxBytes;
    if (openedInfo.size > limit) throw new Error(`${label} exceeds size limit`);
    const parts = [];
    let offset = 0;
    while (offset < openedInfo.size) {
      const buffer = Buffer.alloc(Math.min(64 * 1024, openedInfo.size - offset));
      const { bytesRead } = await handle.read(buffer, 0, buffer.length, offset);
      if (!bytesRead) throw new Error(`${label} changed while reading`);
      offset += bytesRead;
      if (offset > limit) throw new Error(`${label} exceeds size limit`);
      parts.push(bytesRead === buffer.length ? buffer : buffer.subarray(0, bytesRead));
    }
    const after = await handle.stat();
    if (offset !== openedInfo.size || after.size !== openedInfo.size) throw new Error(`${label} changed while reading`);
    await assertNoLinkedAncestors(path, boundary);
    const finalPathInfo = await regularNoSymlink(path, "file", label);
    if (openedInfo.ino && finalPathInfo.ino && (openedInfo.dev !== finalPathInfo.dev || openedInfo.ino !== finalPathInfo.ino)) throw new Error(`${label} changed while reading`);
    return Buffer.concat(parts, offset);
  } finally { await handle.close(); }
}

function validateRawPatch(bytes) {
  if (!bytes.length) throw new Error("empty patch artifact");
  let text;
  try { text = new TextDecoder("utf-8", { fatal: true }).decode(bytes); }
  catch { throw new Error("patch artifact is not valid UTF-8 text"); }
  if (!/^diff --git \S+ .+(?:\r?\n|$)/.test(text) || !/^diff --git /m.test(text)) throw new Error("invalid patch artifact: expected non-empty diff --git patch");
  return text;
}

export async function loadPatchBytes(path, trustedRoot) {
  const boundary = resolvePatchTrustRoot(path, trustedRoot);
  const bytes = await readBoundedFile(path, MAX_PATCH_BYTES, "patch artifact", true, boundary);
  const metadata = pointerMetadata(bytes, path);
  if (!metadata) { validateRawPatch(bytes); return bytes; }

  const parent = dirname(path);
  const chunkRoot = join(parent, `${basename(path)}.parts`);
  const versionRoot = join(chunkRoot, metadata.sha256);
  await regularNoSymlink(chunkRoot, "directory", "patch chunk directory");
  await regularNoSymlink(versionRoot, "directory", "patch chunk version directory");
  const realParent = await realpath(parent), realVersionRoot = await realpath(versionRoot);
  if (!isWithin(realParent, realVersionRoot) || realVersionRoot === realParent) throw new Error("patch chunk directory escapes patch root");

  const parts = [];
  for (const chunk of metadata.chunks) {
    const chunkPath = join(parent, ...chunk.path.split("/"));
    await assertNoLinkedAncestors(chunkPath, boundary);
    const realChunkPath = await realpath(chunkPath);
    if (!isWithin(realVersionRoot, realChunkPath) || realChunkPath === realVersionRoot) throw new Error(`patch chunk escapes chunk directory: ${chunk.path}`);
    const part = await readBoundedFile(chunkPath, PATCH_CHUNK_BYTES, `patch chunk ${chunk.path}`, false, boundary);
    if (part.length !== chunk.byteLength) throw new Error(`patch chunk length mismatch: ${chunk.path}`);
    if (sha256(part) !== chunk.sha256) throw new Error(`patch chunk SHA-256 mismatch: ${chunk.path}`);
    try { new TextDecoder("utf-8", { fatal: true }).decode(part); }
    catch { throw new Error(`patch chunk is not valid UTF-8 text: ${chunk.path}`); }
    parts.push(part);
  }
  const result = Buffer.concat(parts, metadata.byteLength);
  if (result.length !== metadata.byteLength || sha256(result) !== metadata.sha256) throw new Error("patch chunk aggregate length or SHA-256 mismatch");
  validateRawPatch(result);
  return result;
}

export async function listPatchBundlePaths(path, trustedRoot) {
  const boundary = resolvePatchTrustRoot(path, trustedRoot);
  const bytes = await readBoundedFile(path, MAX_PATCH_BYTES, "patch artifact", true, boundary);
  const metadata = pointerMetadata(bytes, path);
  if (!metadata) validateRawPatch(bytes);
  return [resolve(path), ...(metadata?.chunks.map(chunk => resolve(dirname(path), ...chunk.path.split("/"))) ?? [])];
}

function splitUtf8(bytes) {
  let text;
  try { text = new TextDecoder("utf-8", { fatal: true }).decode(bytes); }
  catch { throw new Error("large patch must be valid UTF-8 text"); }
  const chunks = [], current = [];
  let currentBytes = 0;
  for (const character of text) {
    const byteLength = Buffer.byteLength(character, "utf8");
    if (currentBytes + byteLength > PATCH_CHUNK_BYTES) {
      chunks.push(Buffer.from(current.join(""), "utf8"));
      current.length = 0;
      currentBytes = 0;
    }
    current.push(character);
    currentBytes += byteLength;
  }
  if (current.length) chunks.push(Buffer.from(current.join(""), "utf8"));
  return chunks;
}

async function previousPatchMetadata(path, trustedRoot) {
  try {
    const bytes = await readBoundedFile(path, MAX_PATCH_BYTES, "patch artifact", true, trustedRoot);
    const metadata = pointerMetadata(bytes, path);
    if (!metadata) return null;
    await loadPatchBytes(path, trustedRoot);
    return metadata;
  } catch { return null; }
}

async function cleanupPreviousChunks(path, previous, keepPaths) {
  const absolute = resolve(path);
  if (!isWithin(managedPatchRoot, absolute) || dirname(absolute) !== managedPatchRoot || !previous) return;
  const chunkRoot = join(dirname(absolute), `${basename(absolute)}.parts`);
  await assertNoLinkedAncestors(chunkRoot);
  const realChunkRoot = await realpath(chunkRoot).catch(error => error.code === "ENOENT" ? null : Promise.reject(error));
  for (const chunk of previous.chunks) {
    if (keepPaths.has(chunk.path)) continue;
    const chunkPath = join(dirname(absolute), ...chunk.path.split("/"));
    try {
      await assertNoLinkedAncestors(chunkPath);
      const info = await lstat(chunkPath);
      // Leave externally hardlinked chunks in place; never delete another link's artifact.
      if (!info.isSymbolicLink() && info.isFile() && info.nlink === 1 && realChunkRoot) {
        const realChunkPath = await realpath(chunkPath);
        if (isWithin(realChunkRoot, realChunkPath)) await rm(chunkPath);
      }
    } catch (error) { if (error.code !== "ENOENT") throw error; }
  }
  const oldVersions = new Set(previous.chunks.map(chunk => dirname(join(dirname(absolute), ...chunk.path.split("/")))));
  for (const versionPath of oldVersions) {
    await assertNoLinkedAncestors(versionPath);
    if (realChunkRoot) {
      const realVersion = await realpath(versionPath).catch(error => error.code === "ENOENT" ? null : Promise.reject(error));
      if (realVersion && isWithin(realChunkRoot, realVersion)) await rmdir(versionPath).catch(error => { if (!['ENOENT', 'ENOTEMPTY', 'EEXIST'].includes(error.code)) throw error; });
    }
  }
  await assertNoLinkedAncestors(chunkRoot);
  if (realChunkRoot) {
    const finalChunkRoot = await realpath(chunkRoot).catch(error => error.code === "ENOENT" ? null : Promise.reject(error));
    if (finalChunkRoot && isWithin(dirname(realChunkRoot), finalChunkRoot)) await rmdir(chunkRoot).catch(error => { if (!['ENOENT', 'ENOTEMPTY', 'EEXIST'].includes(error.code)) throw error; });
  }
}

async function rejectSymlinkIfPresent(path, type, label) {
  try { await regularNoSymlink(path, type, label); }
  catch (error) { if (error.code === "ENOENT") return; throw error; }
}

async function atomicWriteFile(path, bytes, trustedRoot) {
  const temporary = join(dirname(path), `.${basename(path)}.tmp-${randomUUID()}`);
  await assertNoLinkedAncestors(temporary, trustedRoot);
  const handle = await open(temporary, "wx", 0o600);
  try {
    await handle.writeFile(bytes);
    await handle.sync();
  } catch (error) {
    await handle.close();
    await assertNoLinkedAncestors(temporary, trustedRoot);
    await rm(temporary, { force: true });
    throw error;
  }
  await handle.close();
  await assertNoLinkedAncestors(path, trustedRoot);
  await rejectSymlinkIfPresent(path, "file", "patch artifact");
  try { await rename(temporary, path); }
  catch (error) {
    await assertNoLinkedAncestors(temporary, trustedRoot);
    await rm(temporary, { force: true });
    throw error;
  }
}

export async function writePatchBundle(path, content, trustedRoot) {
  const boundary = resolvePatchTrustRoot(path, trustedRoot);
  const bytes = Buffer.isBuffer(content) ? content : Buffer.from(content);
  if (bytes.length === 0) throw new Error("cannot write empty patch");
  if (bytes.length > MAX_PATCH_BYTES) throw new Error(`patch exceeds aggregate size limit ${MAX_PATCH_BYTES}`);
  validateRawPatch(bytes);
  await assertNoLinkedAncestors(path, boundary);
  const previous = await previousPatchMetadata(path, boundary);
  await mkdir(dirname(path), { recursive: true });
  await assertNoLinkedAncestors(path, boundary);
  await rejectSymlinkIfPresent(path, "file", "patch artifact");
  if (bytes.length <= PATCH_CHUNK_BYTES) {
    await atomicWriteFile(path, bytes, boundary);
    await cleanupPreviousChunks(path, previous, new Set());
    return { chunked: false, byteLength: bytes.length };
  }

  const chunks = splitUtf8(bytes);
  if (chunks.length > MAX_PATCH_CHUNKS) throw new Error(`patch exceeds chunk count limit ${MAX_PATCH_CHUNKS}`);
  const digest = sha256(bytes), base = basename(path);
  const chunkRoot = join(dirname(path), `${base}.parts`), versionRoot = join(chunkRoot, digest);
  await assertNoLinkedAncestors(versionRoot, boundary);
  await rejectSymlinkIfPresent(chunkRoot, "directory", "patch chunk directory");
  await mkdir(versionRoot, { recursive: true });
  await regularNoSymlink(chunkRoot, "directory", "patch chunk directory");
  await regularNoSymlink(versionRoot, "directory", "patch chunk version directory");
  const chunkEntries = [];
  for (let index = 0; index < chunks.length; index++) {
    const chunk = chunks[index];
    const relativePath = `${base}.parts/${digest}/${String(index + 1).padStart(6, "0")}.txt`;
    const chunkPath = join(dirname(path), ...relativePath.split("/"));
    await assertNoLinkedAncestors(chunkPath, boundary);
    await rejectSymlinkIfPresent(chunkPath, "file", `patch chunk ${relativePath}`);
    await atomicWriteFile(chunkPath, chunk, boundary);
    chunkEntries.push({ path: relativePath, byteLength: chunk.length, sha256: sha256(chunk) });
  }
  const metadata = { version: 1, byteLength: bytes.length, sha256: digest, chunks: chunkEntries };
  const pointer = `${PATCH_CHUNK_POINTER_MAGIC}${JSON.stringify(metadata)}\n`;
  if (Buffer.byteLength(pointer, "utf8") > MAX_PATCH_POINTER_BYTES) throw new Error("patch chunk pointer exceeds size limit");
  await atomicWriteFile(path, Buffer.from(pointer, "utf8"), boundary);
  await cleanupPreviousChunks(path, previous, new Set(chunkEntries.map(chunk => chunk.path)));
  return { chunked: true, byteLength: bytes.length, chunks: chunkEntries.length };
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
    const skillDir = entry.payloadPath && skillsRoot === "plugins/agentic-engineering-skills/skills"
      ? join(root, entry.payloadPath)
      : join(root, skillsRoot, entry.name);
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

const localRootEnvironment = { projectSkills: "AGENTIC_PROJECT_SKILLS_ROOT", userSkills: "AGENTIC_USER_SKILLS_ROOT", pluginSkills: "AGENTIC_PLUGIN_ROOT" };

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
