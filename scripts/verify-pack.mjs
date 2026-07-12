import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { readFile, stat } from "node:fs/promises";
import { validateManifest, listFlatSkillDirectories, compareLockDirectories, verifyLocalEntries } from "./lib/manifest.mjs";
import { expectedSkills } from "../tests/expected-inventory.mjs";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { verifyExclusionSection } from "./lib/release-report.mjs";
const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
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
  const included = entries.filter(x => !x.excluded).map(x => x.name).sort();
  for (const host of ["codex", "claude"]) if (JSON.stringify(sets[host]) !== JSON.stringify(included)) throw new Error(`${host} native inventory mismatch`);
  process.stdout.write(`Verified native discovery: Codex ${sets.codex.length}, Claude ${sets.claude.length}\n`);
}
for (const entry of selected) process.stdout.write(`VERIFIED ${entry.sourceType} ${entry.name}\n`);
process.stdout.write(`Verified ${entries.length} requested skills (${entries.filter(x => !x.excluded).length} included, ${entries.filter(x => x.excluded).length} excluded)\n`);

function entryIsUnstamped(entry) { return !/^[0-9a-f]{40}$/i.test(entry.releaseCommit ?? "") || /^0{40}$/.test(entry.releaseCommit); }
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
