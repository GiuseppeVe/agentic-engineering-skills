import { cp, mkdir, mkdtemp, readFile, rename, rm, stat, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { tmpdir } from "node:os";
import { compareLockDirectories, listFlatSkillDirectories, resolveAcquisitionPath, validateManifest, validateSourceManifest, verifyLocalEntries } from "./manifest.mjs";
import { replaceExclusionSection, verifyExclusionSection } from "./release-report.mjs";
import { sha256File, sha256Path } from "./hash.mjs";

function missingReason(source, error) {
  if (error?.code === "ENOENT") return `Configured source path is absent: ${source.localPath}.`;
  return `Source verification failed: ${error?.message ?? String(error)}`;
}

async function atomicReplace(staged, destination) {
  await mkdir(dirname(destination), { recursive: true });
  const backup = `${destination}.acquisition-backup-${process.pid}`;
  let hadDestination = false;
  try {
    await rename(destination, backup);
    hadDestination = true;
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }
  try {
    await rename(staged, destination);
    if (hadDestination) await rm(backup, { recursive: true, force: true });
  } catch (error) {
    if (hadDestination) await rename(backup, destination);
    throw error;
  }
}

/** Runs local source verification and import into isolated outputs. */
export async function runAcquisitionGate({ sourceManifestPath, lockInputPath, lockOutputPath, payloadOutputPath, releaseReportInputPath, releaseReportOutputPath, environment = process.env }) {
  if (!lockOutputPath || !payloadOutputPath || !releaseReportOutputPath) throw new Error("explicit lock, payload, and release-report output paths are required");
  const sources = validateSourceManifest(JSON.parse(await readFile(sourceManifestPath, "utf8")));
  const lock = JSON.parse(await readFile(lockInputPath, "utf8"));
  const report = await readFile(releaseReportInputPath, "utf8");
  const stage = await mkdtemp(join(tmpdir(), "skill-acquisition-"));
  const stagedPayload = join(stage, "payload"), stagedLock = join(stage, "skills.lock.json"), stagedReport = join(stage, "release-report.md");
  await mkdir(stagedPayload, { recursive: true });
  try {
    for (const source of sources) {
      const entry = lock.skills.find(item => item.name === source.name);
      if (!entry) throw new Error(`lock missing requested skill: ${source.name}`);
      if (!source.localRoot) throw new Error(`fixture acquisition requires local source for ${source.name}`);
      try {
        const from = resolveAcquisitionPath(source, environment);
        const info = await stat(from);
        const to = join(stagedPayload, source.name);
        await mkdir(to, { recursive: true });
        if (info.isDirectory()) await cp(from, to, { recursive: true });
        else await cp(from, join(to, "SKILL.md"));
        entry.localSha256 = info.isDirectory() ? await sha256Path(to) : await sha256File(join(to, "SKILL.md"));
        entry.excluded = false;
        delete entry.exclusionReason;
      } catch (error) {
        entry.excluded = true;
        entry.exclusionReason = missingReason(source, error);
      }
    }
    const entries = validateManifest(lock);
    compareLockDirectories(entries, await listFlatSkillDirectories(stagedPayload));
    await verifyLocalEntries(entries, stage, "payload");
    const renderedReport = replaceExclusionSection(report, entries);
    verifyExclusionSection(entries, renderedReport);
    await writeFile(stagedLock, `${JSON.stringify(lock, null, 2)}\n`);
    await writeFile(stagedReport, renderedReport);
    await atomicReplace(stagedPayload, payloadOutputPath);
    await atomicReplace(stagedLock, lockOutputPath);
    await atomicReplace(stagedReport, releaseReportOutputPath);
    return lock;
  } finally {
    await rm(stage, { recursive: true, force: true });
  }
}
