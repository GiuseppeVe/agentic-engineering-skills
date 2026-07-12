import { readFile, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { checkoutImmutable } from "./lib/upstream.mjs";
import { sha256File, sha256Path } from "./lib/hash.mjs";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { resolveAcquisitionPath, validateSourceManifest } from "./lib/manifest.mjs";
const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const stamp = process.argv.includes("--stamp");
const licenses = process.argv.includes("--licenses");
const statusAt = process.argv.indexOf("--status");
const status = statusAt >= 0 ? process.argv[statusAt + 1] : undefined;
if (status && !["vendor", "adapted"].includes(status)) throw new Error(`invalid --status: ${status}`);
let lock = JSON.parse(await readFile(join(root, "manifests/skills.lock.json"), "utf8"));
if (stamp && lock.skills.length === 0) {
  const sources = { skills: validateSourceManifest(JSON.parse(await readFile(join(root, "manifests/skill-sources.json"), "utf8"))) };
  const { stdout } = await promisify(execFile)("git", ["-C", root, "rev-parse", "HEAD"]);
  lock.skills = await Promise.all(sources.skills.map(async source => source.sourceType === "original"
    ? { name: source.name, sourceType: source.sourceType, localSha256: await sha256File(resolveAcquisitionPath(source)), releaseCommit: stdout.trim(), license: source.license, dependencies: [] }
    : { name: source.name, sourceType: source.sourceType, repository: source.repository, revision: source.revision, upstreamPath: source.upstreamPath, sha256: "0".repeat(64), localSha256: source.sourceType === "adapted" ? await sha256File(resolveAcquisitionPath(source)) : "0".repeat(64), ...(source.sourceType === "adapted" ? { changeNotice: source.changeNotice, patchPath: source.patchPath } : {}), dependencies: [] }));
  lock.skills.sort((a, b) => a.name.localeCompare(b.name));
}
if (licenses) {
  const groups = new Map();
  for (const entry of lock.skills.filter(x => x.sourceType !== "original" && !x.excluded)) {
    const key = `${entry.repository}@${entry.revision}`;
    if (!groups.has(key)) groups.set(key, { repository: entry.repository, revision: entry.revision, entries: [] });
    groups.get(key).entries.push(entry);
  }
  for (const group of groups.values()) {
    const checkout = await checkoutImmutable(group.repository, group.revision);
    try {
      for (const entry of group.entries) {
        if (!Array.isArray(entry.licenseFiles) || entry.licenseFiles.length === 0) throw new Error(`missing licenseFiles for ${entry.name}`);
        for (const legal of entry.licenseFiles) {
          const upstreamHash = await sha256File(join(checkout.path, legal.upstreamPath));
          const localHash = await sha256File(join(root, legal.path));
          if (upstreamHash !== legal.sha256) throw new Error(`upstream legal file mismatch for ${entry.name}: ${legal.upstreamPath}`);
          if (localHash !== legal.sha256) throw new Error(`local legal file mismatch for ${entry.name}: ${legal.path}`);
        }
        process.stdout.write(`VERIFIED licenses ${entry.name}\n`);
      }
    } finally { await checkout.cleanup(); }
  }
  process.exit(0);
}
for (const entry of lock.skills.filter(x => x.sourceType !== "original" && !x.excluded && (!status || x.sourceType === status))) {
  const checkout = await checkoutImmutable(entry.repository, entry.revision);
  try {
    const actual = await sha256Path(join(checkout.path, entry.upstreamPath));
    if (stamp) { entry.sha256 = actual; if (entry.sourceType === "vendor") entry.localSha256 = actual; }
    else if (actual !== entry.sha256) throw new Error(`upstream tamper or path mismatch for ${entry.name}`);
    if (!stamp) process.stdout.write(`VERIFIED ${entry.sourceType} ${entry.name}\n`);
  } finally { await checkout.cleanup(); }
}
if (stamp) await writeFile(join(root, "manifests/skills.lock.json"), `${JSON.stringify(lock, null, 2)}\n`);
