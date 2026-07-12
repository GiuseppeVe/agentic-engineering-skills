import { dirname, isAbsolute, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { lstat, readFile, realpath, stat } from "node:fs/promises";
import { createHash } from "node:crypto";
import { validateManifest, listFlatSkillDirectories, compareLockDirectories, verifyLocalEntries } from "./lib/manifest.mjs";
import { expectedSkills } from "../tests/expected-inventory.mjs";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { verifyExclusionSection } from "./lib/release-report.mjs";
import { verifyNativeReceipt } from "./lib/native-receipt.mjs";
const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) await main();

async function main() {
const statusAt = process.argv.indexOf("--status"), status = statusAt >= 0 ? process.argv[statusAt + 1] : undefined;
if (status && !["vendor", "adapted", "original"].includes(status)) throw new Error(`invalid --status: ${status}`);
const allowUnstamped = process.argv.includes("--allow-unstamped-originals");
const raw = JSON.parse(await readFile(join(root, "manifests/skills.lock.json"), "utf8"));
if (allowUnstamped) for (const entry of raw.skills.filter(x => x.sourceType === "original" && entryIsUnstamped(x))) entry.releaseCommit = "0".repeat(40);
const entries = validateManifest(raw);
const releaseReport = await readFile(join(root, "docs/release-report.md"), "utf8");
verifyExclusionSection(entries, releaseReport);
for (const entry of entries.filter(x => x.sourceType === "original" && !(allowUnstamped && /^0{40}$/.test(x.releaseCommit)))) {
  await promisify(execFile)("git", ["-C", root, "cat-file", "-e", `${entry.releaseCommit}^{commit}`]).catch(() => { throw new Error(`releaseCommit does not exist for ${entry.name}: ${entry.releaseCommit}`); });
}
const requested = entries.map(x => x.name).sort();
if (JSON.stringify(requested) !== JSON.stringify(expectedSkills)) throw new Error(`manifest inventory mismatch: expected ${expectedSkills.join(", ")}; got ${requested.join(", ")}`);
const skillsRoot = join(root, "plugins/agentic-engineering-skills/skills");
const directories = await listFlatSkillDirectories(skillsRoot);
compareLockDirectories(entries, directories);
const included = entries.filter(x => !x.excluded).map(x => x.name).sort();
const nativeReceipt = JSON.parse(await readFile(join(root, "manifests/native-discovery.json"), "utf8"));
const nativeResult = await verifyNativeReceipt(nativeReceipt, { included, payloadRoot: skillsRoot });
process.stdout.write(`Verified native receipt: Codex ${nativeResult.count}, Claude ${nativeResult.count}, ${nativeResult.hash}\n`);
await verifyInstalledAgentProfiles({
  canonicalPath: join(root, "manifests/agent-profiles.json"),
  pluginRoot: join(root, "plugins/agentic-engineering-skills"),
});
const selected = entries.filter(x => !x.excluded && (!status || x.sourceType === status));
await verifyLocalEntries(selected, root);
await verifyDocumentationInventory(entries.filter(x => !x.excluded).map(x => x.name).sort());
for (const entry of entries.filter(x => x.excluded)) process.stdout.write(`EXCLUDED ${entry.name}: ${entry.exclusionReason}\n`);
for (const entry of selected.filter(x => x.sourceType === "adapted")) {
  const patch = join(root, entry.patchPath);
  if ((await stat(patch)).size === 0) throw new Error(`empty patch for ${entry.name}`);
}
const reportAt = process.argv.indexOf("--native-report");
if (reportAt >= 0) {
  const path = process.argv[reportAt + 1];
  if (!path) throw new Error("--native-report requires a path");
  const report = await readFile(resolve(root, path), "utf8");
  const sets = parseNativeReport(report);
  for (const host of ["codex", "claude"]) if (JSON.stringify(sets[host]) !== JSON.stringify(included)) throw new Error(`${host} native inventory mismatch`);
  process.stdout.write(`Verified native discovery: Codex ${sets.codex.length}, Claude ${sets.claude.length}\n`);
}
for (const entry of selected) process.stdout.write(`VERIFIED ${entry.sourceType} ${entry.name}\n`);
process.stdout.write(`Verified ${entries.length} requested skills (${entries.filter(x => !x.excluded).length} included, ${entries.filter(x => x.excluded).length} excluded)\n`);
}

function entryIsUnstamped(entry) { return !/^[0-9a-f]{40}$/i.test(entry.releaseCommit ?? "") || /^0{40}$/.test(entry.releaseCommit); }
export async function verifyInstalledAgentProfiles({ canonicalPath, pluginRoot, writeSummary = (text) => process.stdout.write(text) }) {
  const installedPath = join(pluginRoot, "manifests/agent-profiles.json");
  const [canonical, installed] = await Promise.all([
    readFile(canonicalPath, "utf8").then(JSON.parse),
    readFile(installedPath, "utf8").then(JSON.parse),
  ]);
  if (!Array.isArray(canonical.profiles) || !Array.isArray(installed.profiles)) throw new Error("agent profile manifests must expose profiles[]");
  const canonicalNames = canonical.profiles.map(x => x.name).sort();
  const installedNames = installed.profiles.map(x => x.name).sort();
  const expectedProfileNames = ["cleanup", "controller", "implementer", "planner", "researcher", "reviewer", "test-runner"];
  if (JSON.stringify(canonicalNames) !== JSON.stringify(expectedProfileNames)) throw new Error(`canonical profile inventory mismatch: expected ${expectedProfileNames}; got ${canonicalNames}`);
  if (JSON.stringify(installedNames) !== JSON.stringify(canonicalNames)) throw new Error(`installed profile inventory mismatch: expected ${canonicalNames}; got ${installedNames}`);
  const canonicalByName = new Map(canonical.profiles.map(x => [x.name, x]));
  const realPluginRoot = await realpath(pluginRoot);
  for (const entry of installed.profiles) {
    const canonicalEntry = canonicalByName.get(entry.name);
    const payload = resolve(pluginRoot, entry.path);
    const relativePayload = relative(pluginRoot, payload);
    if (relativePayload.startsWith("..") || isAbsolute(relativePayload)) throw new Error(`${entry.name}: installed profile path escapes plugin root`);
    if (entry.path !== `agent-profiles/${entry.name}.md`) throw new Error(`${entry.name}: invalid installed profile path ${entry.path}`);
    if (entry.payloadPath !== entry.path) throw new Error(`${entry.name}: installed payloadPath must equal path`);
    for (const field of ["candidatePath", "status", "source", "revision", "upstreamPath", "sha256", "license", "licensePath", "noticePath", "sourceSpecPath", "sourceSpecRoleLine"]) {
      if (entry[field] !== canonicalEntry[field]) throw new Error(`${entry.name}: installed ${field} differs from canonical manifest`);
    }
    const payloadStat = await lstat(payload);
    if (payloadStat.isSymbolicLink()) throw new Error(`${entry.name}: installed profile payload must not be a symbolic link`);
    if (!payloadStat.isFile()) throw new Error(`${entry.name}: installed profile payload must be a regular file`);
    const realPayload = await realpath(payload);
    const relativeRealPayload = relative(realPluginRoot, realPayload);
    if (relativeRealPayload.startsWith("..") || isAbsolute(relativeRealPayload)) throw new Error(`${entry.name}: installed profile real path escapes plugin root`);
    const actualHash = createHash("sha256").update(await readFile(realPayload)).digest("hex");
    if (actualHash !== entry.sha256) throw new Error(`${entry.name}: installed profile payload hash mismatch`);
  }
  writeSummary(`Verified agent profiles: ${installedNames.length} installed (${installedNames.join(", ")})\n`);
}
async function verifyDocumentationInventory(included) {
  const explicitAt = process.argv.indexOf("--docs-inventory");
  const path = explicitAt >= 0 ? process.argv[explicitAt + 1] : join(root, "docs/selective-install.md");
  if (explicitAt >= 0 && !path) throw new Error("--docs-inventory requires a path");
  let text;
  try { text = await readFile(resolve(root, path), "utf8"); }
  catch (error) { if (error.code === "ENOENT" && explicitAt < 0) return; throw error; }
  const documented = [...new Set([...text.matchAll(/^\|\s*`([a-z0-9][a-z0-9-]+)`\s*\|/gm)].map(x => x[1]))].sort();
  if (JSON.stringify(documented) !== JSON.stringify(included)) throw new Error(`documentation inventory mismatch: expected ${included}; got ${documented}`);
  process.stdout.write(`Verified documentation inventory: ${documented.length} included skills\n`);
}
export function parseNativeReport(text) {
  try {
    const parsed = JSON.parse(text);
    return { codex: [...parsed.nativeDiscovery.codex].sort(), claude: [...parsed.nativeDiscovery.claude].sort() };
  } catch {}
  const result = {};
  for (const host of ["codex", "claude"]) {
    const match = text.match(new RegExp(`(?:^|\\n)#{1,6}\\s+${host}[^\\n]*\\n([\\s\\S]*?)(?=\\n#{1,6}\\s|$)`, "i"));
    result[host] = [...new Set([...(match?.[1] ?? "").matchAll(/`([a-z0-9][a-z0-9-]+)`/g)].map(x => x[1]))].sort();
  }
  return result;
}
