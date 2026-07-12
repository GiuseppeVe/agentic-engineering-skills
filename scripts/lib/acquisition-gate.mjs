import { cp, lstat, mkdir, mkdtemp, readFile, realpath, rename, rm, writeFile } from "node:fs/promises";
import { dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { tmpdir } from "node:os";
import { randomUUID } from "node:crypto";
import { compareLockDirectories, listFlatSkillDirectories, resolveAcquisitionPath, resolveAcquisitionRoot, validateManifest, validateSourceManifest, verifyLocalEntries } from "./manifest.mjs";
import { replaceExclusionSection, verifyExclusionSection } from "./release-report.mjs";
import { sha256File, sha256Path } from "./hash.mjs";

function missingReason(source, error) {
  if (error?.code === "ENOENT") return `Configured source path is absent: ${source.localPath}.`;
  return `Source verification failed: ${error?.message ?? String(error)}`;
}

function legalReason(error) {
  return `Legal verification failed: ${error?.message ?? String(error)}`;
}

function resolveLegalPath(root, path, skillName) {
  if (!path || isAbsolute(path) || path.split(/[\\/]/).includes("..")) {
    throw new Error(`license path must be portable and relative for ${skillName}: ${path}`);
  }
  const resolvedRoot = resolve(root), resolvedPath = resolve(resolvedRoot, path);
  if (relative(resolvedRoot, resolvedPath).startsWith("..")) throw new Error(`license path escapes legal payload root for ${skillName}: ${path}`);
  return resolvedPath;
}

async function verifyLegalPayload(entry, legalPayloadRootPath) {
  if (!legalPayloadRootPath) throw new Error(`explicit legal payload root is required for ${entry.name}`);
  if (!Array.isArray(entry.licenseFiles) || entry.licenseFiles.length === 0) throw new Error(`required licenseFiles metadata is absent for ${entry.name}`);
  for (const legal of entry.licenseFiles) {
    const path = resolveLegalPath(legalPayloadRootPath, legal.path, entry.name);
    await verifyContainedRegularFile(path, legalPayloadRootPath, `license file for ${entry.name}`);
    if (legal.sha256) {
      const actual = await sha256File(path);
      if (actual !== legal.sha256) throw new Error(`license hash mismatch for ${entry.name} at ${legal.path}: expected ${legal.sha256}, got ${actual}`);
    }
  }
}

function isContained(root, path) {
  const child = relative(root, path);
  return child === "" || (!isAbsolute(child) && child !== ".." && !child.startsWith(`..${sep}`));
}

async function verifyContainedRegularFile(path, configuredRoot, label) {
  const info = await lstat(path);
  if (info.isSymbolicLink()) throw new Error(`${label} must not be a symbolic link: ${path}`);
  if (!info.isFile()) throw new Error(`${label} must be a regular file: ${path}`);
  const [rootTarget, fileTarget] = await Promise.all([realpath(configuredRoot), realpath(path)]);
  if (!isContained(rootTarget, fileTarget)) throw new Error(`${label} resolves outside configured root: ${path}`);
  return info;
}

async function replaceOutputsAtomically(outputs, beforeReplacement, beforeBackupCleanup) {
  const transactionId = `${process.pid}-${randomUUID()}`;
  const states = outputs.map(({ staged, destination }) => ({
    staged,
    destination: resolve(destination),
    prepared: `${resolve(destination)}.acquisition-stage-${transactionId}`,
    backup: `${resolve(destination)}.acquisition-backup-${transactionId}`,
    hadDestination: false,
    replaced: false,
  }));

  let committed = false;
  try {
    // Copy beside each destination first. Final renames therefore never depend on
    // temporary and output directories sharing a filesystem.
    for (const state of states) {
      await mkdir(dirname(state.destination), { recursive: true });
      await cp(state.staged, state.prepared, { recursive: true, errorOnExist: true, force: false });
    }

    for (const state of states) {
      try {
        await rename(state.destination, state.backup);
        state.hadDestination = true;
      } catch (error) {
        if (error.code !== "ENOENT") throw error;
      }
    }

    for (const [index, state] of states.entries()) {
      await beforeReplacement?.(index + 1, state.destination);
      await rename(state.prepared, state.destination);
      state.replaced = true;
    }
    // Commit point: every destination now contains matching new output.
    committed = true;
  } catch (error) {
    const rollbackErrors = [];
    for (const state of [...states].reverse()) {
      try {
        if (state.replaced) await rm(state.destination, { recursive: true, force: true });
        if (state.hadDestination) await rename(state.backup, state.destination);
      } catch (rollbackError) {
        rollbackErrors.push(rollbackError);
      }
    }
    if (rollbackErrors.length > 0) throw new AggregateError([error, ...rollbackErrors], "acquisition output replacement and rollback failed");
    throw error;
  } finally {
    // Never delete an unrestored backup after a rollback error; it remains the
    // last recoverable copy. Normal success and successful rollback leave none.
    await Promise.all(states.map(state => rm(state.prepared, { recursive: true, force: true })));
  }

  if (committed) {
    const cleanupErrors = [];
    for (const [index, state] of states.filter(state => state.hadDestination).entries()) {
      try {
        await beforeBackupCleanup?.(index + 1, state.backup);
        await rm(state.backup, { recursive: true, force: true });
      } catch (error) {
        cleanupErrors.push(error);
      }
    }
    if (cleanupErrors.length > 0) throw new AggregateError(cleanupErrors, "acquisition committed but backup cleanup failed");
  }
}

/** Runs local source verification and import into isolated outputs. */
export async function runAcquisitionGate({ sourceManifestPath, lockInputPath, lockOutputPath, payloadOutputPath, legalPayloadRootPath, releaseReportInputPath, releaseReportOutputPath, environment = process.env, _testHooks = {} }) {
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
        const info = source.localPath.endsWith("/")
          ? await lstat(from)
          : await verifyContainedRegularFile(from, resolveAcquisitionRoot(source, environment), `source file for ${source.name}`);
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
      if (!entry.excluded && entry.sourceType !== "original") {
        try {
          await verifyLegalPayload(entry, legalPayloadRootPath);
        } catch (error) {
          await rm(join(stagedPayload, source.name), { recursive: true, force: true });
          entry.excluded = true;
          entry.exclusionReason = legalReason(error);
        }
      }
    }
    const entries = validateManifest(lock);
    compareLockDirectories(entries, await listFlatSkillDirectories(stagedPayload));
    await verifyLocalEntries(entries, stage, "payload");
    const renderedReport = replaceExclusionSection(report, entries);
    verifyExclusionSection(entries, renderedReport);
    await writeFile(stagedLock, `${JSON.stringify(lock, null, 2)}\n`);
    await writeFile(stagedReport, renderedReport);
    await replaceOutputsAtomically([
      { staged: stagedPayload, destination: payloadOutputPath },
      { staged: stagedLock, destination: lockOutputPath },
      { staged: stagedReport, destination: releaseReportOutputPath },
    ], _testHooks.beforeReplacement, _testHooks.beforeBackupCleanup);
    return lock;
  } finally {
    await rm(stage, { recursive: true, force: true });
  }
}
