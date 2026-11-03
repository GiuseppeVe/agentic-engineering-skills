import { readFile, writeFile, mkdir, mkdtemp, rm, readdir, lstat, chmod } from "node:fs/promises";
import { dirname, join, resolve, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { checkoutImmutable } from "./lib/upstream.mjs";
import { normalizeLf } from "./lib/hash.mjs";
import { writePatchBundle } from "./lib/manifest.mjs";

const exec = promisify(execFile);
const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");

// Normalize text across checkout platforms. Preserve binary and non-UTF-8 data.
function canonicalBytes(data) {
  if (data.includes(0)) return data;
  try { new TextDecoder("utf-8", { fatal: true }).decode(data); }
  catch { return data; }
  return normalizeLf(data);
}

async function collectFiles(from, base = from, result = []) {
  for (const entry of await readdir(from, { withFileTypes: true })) {
    const src = join(from, entry.name);
    const info = await lstat(src);
    if (info.isDirectory()) await collectFiles(src, base, result);
    else if (info.isFile()) result.push(relative(base, src));
    else throw new Error(`unsupported skill payload entry: ${src}`);
  }
  return result;
}

async function fileModes(sourceRoot, files, sourceFiles = files) {
  const modes = new Map();
  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    const info = await lstat(join(sourceRoot, sourceFiles[i]));
    modes.set(file, info.mode & 0o111 ? "100755" : "100644");
  }
  let gitRoot;
  try {
    const { stdout } = await exec("git", ["-C", sourceRoot, "rev-parse", "--show-toplevel"]);
    gitRoot = stdout.trim();
  } catch {
    // Inputs outside Git use filesystem executable bits as explicit fallback.
    return modes;
  }
  const sourcePrefix = relative(gitRoot, sourceRoot).split(sep).filter(Boolean).join("/");
  const gitPaths = new Map(files.map((file, i) => {
    const gitPath = [sourcePrefix, sourceFiles[i].split(sep).join("/")].filter(Boolean).join("/");
    return [gitPath, file];
  }));
  let coreFilemode = process.platform !== "win32";
  try {
    const { stdout } = await exec("git", ["-C", gitRoot, "config", "--bool", "--get", "core.filemode"]);
    coreFilemode = stdout.trim() === "true";
  } catch (error) {
    if (error.code !== 1) throw error;
  }
  const trustWorkingTree = process.platform !== "win32" && coreFilemode;
  const { stdout } = await exec("git", ["-C", gitRoot, "ls-files", "--stage", "-z", "--", ...[...gitPaths.keys()].map(path => `:(literal)${path}`)]);
  for (const record of stdout.split("\0")) {
    if (!record) continue;
    const tab = record.indexOf("\t");
    const [mode, , stage] = record.slice(0, tab).split(" ");
    const file = gitPaths.get(record.slice(tab + 1));
    if (!trustWorkingTree && file && stage === "0" && (mode === "100644" || mode === "100755")) modes.set(file, mode);
  }
  return modes;
}

async function stageDirectory(from, to, modes, base = from) {
  await mkdir(to, { recursive: true });
  for (const entry of await readdir(from, { withFileTypes: true })) {
    const src = join(from, entry.name), dst = join(to, entry.name);
    const info = await lstat(src);
    if (info.isDirectory()) await stageDirectory(src, dst, modes, base);
    else if (info.isFile()) {
      const mode = modes.get(relative(base, src)) ?? (info.mode & 0o111 ? "100755" : "100644");
      await writeFile(dst, canonicalBytes(await readFile(src)));
      await chmod(dst, mode === "100755" ? 0o755 : 0o644);
    }
    else throw new Error(`unsupported skill payload entry: ${src}`);
  }
}

async function forceModeOnlyDiffs(a, b, oldFiles, newFiles, oldModes, newModes) {
  const newFileSet = new Set(newFiles);
  const modeOnlyFiles = new Set();
  for (const file of oldFiles) {
    if (!newFileSet.has(file) || oldModes.get(file) === newModes.get(file)) continue;
    const oldBytes = await readFile(join(a, file));
    const newBytes = await readFile(join(b, file));
    if (!oldBytes.equals(newBytes)) continue;
    await writeFile(join(b, file), Buffer.concat([newBytes, Buffer.from([0])]));
    modeOnlyFiles.add(file);
  }
  return modeOnlyFiles;
}

async function preservePatchModes(patch, normalized, name, oldModes, newModes, modeOnlyFiles) {
  const names = await exec("git", ["-c", "core.autocrlf=false", "diff", "--no-index", "--no-renames", "--name-status", "-z", "--", `a/${name}`, `b/${name}`], { cwd: normalized }).catch(error => error.code === 1 ? error : Promise.reject(error));
  const fields = names.stdout.split("\0").filter(Boolean);
  const changes = [];
  for (let i = 0; i < fields.length;) {
    const status = fields[i++];
    if (!["A", "D", "M"].includes(status)) throw new Error(`unsupported patch status: ${status}`);
    const sidePath = fields[i++];
    const prefixA = `a/${name}/`, prefixB = `b/${name}/`;
    const prefix = sidePath.startsWith(prefixA) ? prefixA : sidePath.startsWith(prefixB) ? prefixB : null;
    if (!prefix) throw new Error(`unexpected diff path: ${sidePath}`);
    const file = sidePath.slice(prefix.length).split("/").join(sep);
    changes.push({ status, file });
  }
  const sections = patch.split(/(?=^diff --git )/m);
  if (sections.length !== changes.length) throw new Error("patch sections do not match Git change list");
  return sections.map((section, index) => {
    const { status, file } = changes[index];
    if (modeOnlyFiles.has(file)) return `${section.split("\n", 1)[0]}\nold mode ${oldModes.get(file)}\nnew mode ${newModes.get(file)}\n`;
    let declarations = "";
    if (status === "A") declarations = `new file mode ${newModes.get(file)}\n`;
    else if (status === "D") declarations = `deleted file mode ${oldModes.get(file)}\n`;
    else if (oldModes.get(file) !== newModes.get(file)) declarations = `old mode ${oldModes.get(file)}\nnew mode ${newModes.get(file)}\n`;
    let clean = section.replace(/^(?:new file mode|deleted file mode|old mode|new mode) \d+\r?\n/gm, "");
    const indexMode = status === "M" && oldModes.get(file) === newModes.get(file) ? ` ${newModes.get(file)}` : "";
    clean = clean.replace(/^(index [0-9a-f]+\.\.[0-9a-f]+)(?: (?:100644|100755))?$/m, `$1${indexMode}`);
    const headerEnd = clean.indexOf("\n");
    return `${clean.slice(0, headerEnd + 1)}${declarations}${clean.slice(headerEnd + 1)}`;
  }).join("");
}

// Generate a reproducible, complete patch for file or directory acquisitions.
// For directory inputs all additions, modifications, removals and binary files
// are captured; the generated patch applies at -p1 to a directory named skill.
export async function generatePatch({ name, upstream, local, directory }) {
  if (!/^[a-z0-9][a-z0-9-]*$/.test(name)) throw new Error(`invalid skill name: ${name}`);
  const normalized = await mkdtemp(join(tmpdir(), "skill-patch-input-"));
  try {
    const a = join(normalized, "a", name), b = join(normalized, "b", name);
    let oldFiles, newFiles, oldModes, newModes;
    if (directory) {
      [oldFiles, newFiles] = await Promise.all([collectFiles(upstream), collectFiles(local)]);
      [oldModes, newModes] = await Promise.all([fileModes(upstream, oldFiles), fileModes(local, newFiles)]);
      await Promise.all([stageDirectory(upstream, a, oldModes), stageDirectory(local, b, newModes)]);
    } else {
      oldFiles = newFiles = ["SKILL.md"];
      [oldModes, newModes] = await Promise.all([
        fileModes(dirname(upstream), oldFiles, [upstream.split(/[\\/]/).at(-1)]),
        fileModes(dirname(local), newFiles, [local.split(/[\\/]/).at(-1)]),
      ]);
      await Promise.all([mkdir(a, { recursive: true }), mkdir(b, { recursive: true })]);
      await Promise.all([
        writeFile(join(a, "SKILL.md"), canonicalBytes(await readFile(upstream))),
        writeFile(join(b, "SKILL.md"), canonicalBytes(await readFile(local))),
      ]);
      await Promise.all([
        chmod(join(a, "SKILL.md"), oldModes.get("SKILL.md") === "100755" ? 0o755 : 0o644),
        chmod(join(b, "SKILL.md"), newModes.get("SKILL.md") === "100755" ? 0o755 : 0o644),
      ]);
    }
    const modeOnlyFiles = await forceModeOnlyDiffs(a, b, oldFiles, newFiles, oldModes, newModes);
    const result = await exec("git", ["-c", "core.autocrlf=false", "-c", "core.quotePath=true", "diff", "--no-index", "--no-ext-diff", "--no-textconv", "--no-renames", "--binary", "--unified=0", "--src-prefix=", "--dst-prefix=", "--", `a/${name}`, `b/${name}`], { cwd: normalized, maxBuffer: 64 * 1024 * 1024 }).catch(e => e.code === 1 ? e : Promise.reject(e));
    if (!result.stdout.trim()) throw new Error(`adapted skill ${name} has empty patch`);
    const modes = await preservePatchModes(result.stdout, normalized, name, oldModes, newModes, modeOnlyFiles);
    return modes.replace(/^(@@ .*? @@).*$/gm, "$1");
  } finally {
    await rm(normalized, { recursive: true, force: true });
  }
}

async function main() {
  const sources = JSON.parse(await readFile(join(root, "manifests/skill-sources.json"), "utf8"));
  for (const source of sources.skills.filter(x => x.sourceType === "adapted")) {
    const checkout = await checkoutImmutable(source.repository, source.revision);
    try {
      const directory = source.upstreamPath.endsWith("/");
      const localRoot = join(root, "plugins/agentic-engineering-skills/skills", source.name);
      const patch = await generatePatch({ name: source.name, upstream: join(checkout.path, source.upstreamPath), local: directory ? localRoot : join(localRoot, "SKILL.md"), directory });
      const path = join(root, source.patchPath);
      const rel = relative(join(root, "manifests", "patches"), path);
      if (!rel || rel.startsWith(`..${sep}`) || rel === "..") throw new Error(`invalid patch path: ${source.patchPath}`);
      await mkdir(dirname(path), { recursive: true });
      await writePatchBundle(path, patch, root);
    } finally { await checkout.cleanup(); }
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();
