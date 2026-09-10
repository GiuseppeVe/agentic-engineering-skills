import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, writeFile, mkdir, rm, readFile, stat, readdir, symlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { sha256File, sha256Path, normalizeLf } from "../scripts/lib/hash.mjs";
import { checkoutImmutable } from "../scripts/lib/upstream.mjs";
import { verifyLocalEntries, compareLockDirectories } from "../scripts/lib/manifest.mjs";
import { renderExclusionSection, verifyExclusionSection } from "../scripts/lib/release-report.mjs";
import { runAcquisitionGate } from "../scripts/lib/acquisition-gate.mjs";

const exec = promisify(execFile);

async function git(repository, args) {
  return exec("git", ["-c", "core.autocrlf=false", "-C", repository, ...args]);
}

test("checks out an immutable local revision and detects checkout tampering", async () => {
  const source = await mkdtemp(join(tmpdir(), "upstream-fixture-"));
  let checkout;
  try {
    await git(source, ["init", "-q"]);
    await git(source, ["config", "user.name", "Provenance Test"]);
    await git(source, ["config", "user.email", "provenance@example.invalid"]);
    await mkdir(join(source, "skills/fixture"), { recursive: true });
    await writeFile(join(source, "skills/fixture/SKILL.md"), "pinned content\n");
    await git(source, ["add", "."]);
    await git(source, ["commit", "-q", "-m", "fixture"]);
    const { stdout } = await git(source, ["rev-parse", "HEAD"]);
    const revision = stdout.trim();

    await writeFile(join(source, "skills/fixture/SKILL.md"), "uncommitted source tamper\n");
    checkout = await checkoutImmutable(source, revision);
    const pinnedFile = join(checkout.path, "skills/fixture/SKILL.md");
    const pinnedHash = await sha256File(pinnedFile);
    await verifyLocalEntries([{ name: "fixture", localSha256: pinnedHash }], checkout.path, "skills");
    await writeFile(pinnedFile, "checkout tamper\n");
    await assert.rejects(
      verifyLocalEntries([{ name: "fixture", localSha256: pinnedHash }], checkout.path, "skills"),
      /tamper/i,
    );
  } finally {
    if (checkout) await checkout.cleanup();
    await rm(source, { recursive: true, force: true });
  }
});

test("immutable checkout disables Git line-ending conversion", async () => {
  const source = await readFile(new URL("../scripts/lib/upstream.mjs", import.meta.url), "utf8");
  assert.match(source, /core\.autocrlf=false/);
  assert.match(source, /core\.eol=lf/);
  assert.match(source, /core\.safecrlf=false/);
});

test("patch input LF normalization is idempotent across source line endings", () => {
  const lf = Buffer.from("first\nsecond\n");
  const crlf = Buffer.from("first\r\nsecond\r\n");
  const cr = Buffer.from("first\rsecond\r");
  assert.deepEqual(normalizeLf(lf), normalizeLf(crlf));
  assert.deepEqual(normalizeLf(lf), normalizeLf(cr));
  assert.deepEqual(normalizeLf(normalizeLf(crlf)), normalizeLf(crlf));
});

test("detects local tampering and excluded entries", async () => {
  const root = await mkdtemp(join(tmpdir(), "pack-"));
  await mkdir(join(root, "plugins/p/skills/a"), { recursive: true });
  const file = join(root, "plugins/p/skills/a/SKILL.md");
  await writeFile(file, "clean");
  const hash = await sha256File(file);
  await verifyLocalEntries([{ name: "a", localSha256: hash }], root, "plugins/p/skills");
  await writeFile(file, "tampered");
  await assert.rejects(verifyLocalEntries([{ name: "a", localSha256: hash }], root, "plugins/p/skills"), /tamper/i);
  assert.doesNotThrow(() => compareLockDirectories([{ name: "a" }, { name: "excluded", excluded: true, exclusionReason: "license missing" }], ["a"]));
  assert.throws(() => compareLockDirectories([{ name: "a" }, { name: "excluded", excluded: true, exclusionReason: "license missing" }], ["a", "excluded"]), /mismatch/i);
  await mkdir(join(root, "tree/sub"), { recursive: true });
  await writeFile(join(root, "tree/sub/file"), "content");
  assert.match(await sha256Path(join(root, "tree")), /^[a-f0-9]{64}$/);
  await rm(root, { recursive: true, force: true });
});

test("sha256Path rejects symbolic links", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "hash-symlink-"));
  try {
    await mkdir(join(root, "tree"));
    await writeFile(join(root, "target"), "content");
    try {
      await symlink(join(root, "target"), join(root, "tree", "link"), "file");
    } catch (error) {
      if (error?.code === "EPERM") {
        t.skip(`OS disallows symlink creation: ${error.code}`);
        return;
      }
      throw error;
    }
    await assert.rejects(sha256Path(join(root, "tree")), /unsupported filesystem entry.*link/i);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

test("excluded skill name and objective reason round-trip into release report", () => {
  const entries = [
    { name: "included", excluded: false },
    { name: "blocked-skill", excluded: true, exclusionReason: "Pinned source path is absent at revision abc123." },
  ];
  const report = renderExclusionSection(entries);
  assert.match(report, /blocked-skill/);
  assert.match(report, /Pinned source path is absent at revision abc123\./);
  assert.deepEqual(verifyExclusionSection(entries, report), [
    { name: "blocked-skill", reason: "Pinned source path is absent at revision abc123." },
  ]);
  assert.throws(
    () => verifyExclusionSection(entries, report.replace("abc123", "different")),
    /exclusion report mismatch/,
  );
});

test("acquisition gate excludes a missing requested source from lock, payload, and release report", async () => {
  const root = await mkdtemp(join(tmpdir(), "acquisition-fixture-"));
  try {
    const sourceRoot = join(root, "sources"), output = join(root, "output");
    await mkdir(join(sourceRoot, "included"), { recursive: true });
    await writeFile(join(sourceRoot, "included", "SKILL.md"), "---\nname: included\n---\n");
    const sources = { skills: [
      { name: "included", sourceType: "original", localRoot: "projectSkills", localPath: "included/SKILL.md", license: "MIT" },
      { name: "missing", sourceType: "original", localRoot: "projectSkills", localPath: "missing/SKILL.md", license: "MIT" },
    ] };
    const lock = { skills: sources.skills.map(source => ({ name: source.name, sourceType: "original", localSha256: "0".repeat(64), releaseCommit: "0".repeat(40), license: "MIT", payloadType: "file", dependencies: [] })) };
    await mkdir(output, { recursive: true });
    await writeFile(join(root, "sources.json"), JSON.stringify(sources));
    await writeFile(join(root, "lock.json"), JSON.stringify(lock));
    await writeFile(join(root, "report.md"), `# Release\n\n${renderExclusionSection([])}`);
    const result = await runAcquisitionGate({
      sourceManifestPath: join(root, "sources.json"), lockInputPath: join(root, "lock.json"),
      lockOutputPath: join(output, "skills.lock.json"), payloadOutputPath: join(output, "skills"),
      releaseReportInputPath: join(root, "report.md"), releaseReportOutputPath: join(output, "release-report.md"),
      environment: { AGENTIC_PROJECT_SKILLS_ROOT: sourceRoot },
    });
    const excluded = result.skills.find(entry => entry.name === "missing");
    assert.equal(excluded.excluded, true);
    assert.ok(excluded.exclusionReason.length > 0);
    assert.deepEqual(await readdir(join(output, "skills")), ["included"]);
    const writtenLock = JSON.parse(await readFile(join(output, "skills.lock.json"), "utf8"));
    const writtenExcluded = writtenLock.skills.find(entry => entry.name === "missing");
    assert.equal(writtenExcluded.exclusionReason, excluded.exclusionReason);
    const report = await readFile(join(output, "release-report.md"), "utf8");
    assert.deepEqual(verifyExclusionSection(writtenLock.skills, report), [{ name: "missing", reason: excluded.exclusionReason }]);
  } finally { await rm(root, { recursive: true, force: true }); }
});

for (const failureAt of [2, 3]) {
  test(`acquisition gate restores every coherent output when replacement ${failureAt} fails`, async () => {
    const root = await mkdtemp(join(tmpdir(), "acquisition-rollback-fixture-"));
    try {
      const sourceRoot = join(root, "sources"), output = join(root, "output");
      const payloadOutputPath = join(output, "skills");
      const lockOutputPath = join(output, "skills.lock.json");
      const releaseReportOutputPath = join(output, "release-report.md");
      await mkdir(join(sourceRoot, "new-skill"), { recursive: true });
      await writeFile(join(sourceRoot, "new-skill", "SKILL.md"), "---\nname: new-skill\n---\nnew\n");
      await mkdir(payloadOutputPath, { recursive: true });
      await writeFile(join(payloadOutputPath, "ORIGINAL"), "original payload\n");
      await writeFile(lockOutputPath, "original lock\n");
      await writeFile(releaseReportOutputPath, "original report\n");

      const sources = { skills: [{
        name: "new-skill", sourceType: "original", localRoot: "projectSkills",
        localPath: "new-skill/SKILL.md", license: "MIT",
      }] };
      const lock = { skills: [{
        name: "new-skill", sourceType: "original", localSha256: "0".repeat(64),
        releaseCommit: "0".repeat(40), license: "MIT", payloadType: "file", dependencies: [],
      }] };
      await writeFile(join(root, "sources.json"), JSON.stringify(sources));
      await writeFile(join(root, "lock.json"), JSON.stringify(lock));
      await writeFile(join(root, "report.md"), `# Release\n\n${renderExclusionSection([])}`);

      await assert.rejects(runAcquisitionGate({
        sourceManifestPath: join(root, "sources.json"), lockInputPath: join(root, "lock.json"),
        lockOutputPath, payloadOutputPath,
        releaseReportInputPath: join(root, "report.md"), releaseReportOutputPath,
        environment: { AGENTIC_PROJECT_SKILLS_ROOT: sourceRoot },
        _testHooks: { beforeReplacement: replacement => {
          if (replacement === failureAt) throw new Error(`injected replacement failure ${failureAt}`);
        } },
      }), new RegExp(`injected replacement failure ${failureAt}`));

      assert.deepEqual(await readdir(payloadOutputPath), ["ORIGINAL"]);
      assert.equal(await readFile(join(payloadOutputPath, "ORIGINAL"), "utf8"), "original payload\n");
      assert.equal(await readFile(lockOutputPath, "utf8"), "original lock\n");
      assert.equal(await readFile(releaseReportOutputPath, "utf8"), "original report\n");
      assert.deepEqual((await readdir(output)).sort(), ["release-report.md", "skills", "skills.lock.json"]);
    } finally {
      await rm(root, { recursive: true, force: true });
    }
  });
}

test("acquisition backup-cleanup failure keeps committed outputs and recoverable backup", async () => {
  const root = await mkdtemp(join(tmpdir(), "acquisition-cleanup-fixture-"));
  try {
    const sourceRoot = join(root, "sources"), output = join(root, "output");
    const payloadOutputPath = join(output, "skills"), lockOutputPath = join(output, "skills.lock.json");
    const releaseReportOutputPath = join(output, "release-report.md");
    await mkdir(join(sourceRoot, "new-skill"), { recursive: true });
    await writeFile(join(sourceRoot, "new-skill", "SKILL.md"), "---\nname: new-skill\n---\nnew\n");
    await mkdir(payloadOutputPath, { recursive: true });
    await writeFile(join(payloadOutputPath, "ORIGINAL"), "original payload\n");
    await writeFile(lockOutputPath, "original lock\n");
    await writeFile(releaseReportOutputPath, "original report\n");
    const sources = { skills: [{ name: "new-skill", sourceType: "original", localRoot: "projectSkills", localPath: "new-skill/SKILL.md", license: "MIT" }] };
    const lock = { skills: [{ name: "new-skill", sourceType: "original", localSha256: "0".repeat(64), releaseCommit: "0".repeat(40), license: "MIT", payloadType: "file", dependencies: [] }] };
    await writeFile(join(root, "sources.json"), JSON.stringify(sources));
    await writeFile(join(root, "lock.json"), JSON.stringify(lock));
    await writeFile(join(root, "report.md"), `# Release\n\n${renderExclusionSection([])}`);

    let retainedBackup;
    await assert.rejects(runAcquisitionGate({
      sourceManifestPath: join(root, "sources.json"), lockInputPath: join(root, "lock.json"),
      lockOutputPath, payloadOutputPath, releaseReportInputPath: join(root, "report.md"), releaseReportOutputPath,
      environment: { AGENTIC_PROJECT_SKILLS_ROOT: sourceRoot },
      _testHooks: { beforeBackupCleanup: (index, backup) => {
        if (index === 1) { retainedBackup = backup; throw new Error("injected backup cleanup failure"); }
      } },
    }), error => {
      assert.match(error.message, /committed but backup cleanup failed/);
      assert.match(String(error.errors?.[0]), /injected backup cleanup failure/);
      return true;
    });

    assert.deepEqual(await readdir(payloadOutputPath), ["new-skill"]);
    assert.match(await readFile(join(payloadOutputPath, "new-skill", "SKILL.md"), "utf8"), /new/);
    const writtenLock = JSON.parse(await readFile(lockOutputPath, "utf8"));
    assert.equal(writtenLock.skills[0].name, "new-skill");
    assert.deepEqual(verifyExclusionSection(writtenLock.skills, await readFile(releaseReportOutputPath, "utf8")), []);
    assert.equal(await readFile(join(retainedBackup, "ORIGINAL"), "utf8"), "original payload\n");
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("acquisition rejects a source file symlink resolving outside configured root", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "acquisition-source-symlink-"));
  try {
    const sourceRoot = join(root, "sources"), outside = join(root, "outside.md"), output = join(root, "output");
    await mkdir(join(sourceRoot, "linked"), { recursive: true });
    await writeFile(outside, "---\nname: linked\n---\n");
    try { await symlink(outside, join(sourceRoot, "linked", "SKILL.md"), "file"); }
    catch (error) { if (error?.code === "EPERM") { t.skip(`OS disallows symlink creation: ${error.code}`); return; } throw error; }
    const sources = { skills: [{ name: "linked", sourceType: "original", localRoot: "projectSkills", localPath: "linked/SKILL.md", license: "MIT" }] };
    const lock = { skills: [{ name: "linked", sourceType: "original", localSha256: "0".repeat(64), releaseCommit: "0".repeat(40), license: "MIT", payloadType: "file", dependencies: [] }] };
    await mkdir(output); await writeFile(join(root, "sources.json"), JSON.stringify(sources)); await writeFile(join(root, "lock.json"), JSON.stringify(lock));
    await writeFile(join(root, "report.md"), `# Release\n\n${renderExclusionSection([])}`);
    const result = await runAcquisitionGate({ sourceManifestPath: join(root, "sources.json"), lockInputPath: join(root, "lock.json"), lockOutputPath: join(output, "lock.json"), payloadOutputPath: join(output, "skills"), releaseReportInputPath: join(root, "report.md"), releaseReportOutputPath: join(output, "report.md"), environment: { AGENTIC_PROJECT_SKILLS_ROOT: sourceRoot } });
    assert.equal(result.skills[0].excluded, true);
    assert.match(result.skills[0].exclusionReason, /symbolic link|outside configured root/i);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("acquisition rejects a directory source symlink resolving outside configured root", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "acquisition-directory-symlink-"));
  try {
    const sourceRoot = join(root, "sources"), outside = join(root, "outside"), output = join(root, "output");
    await mkdir(sourceRoot); await mkdir(outside); await mkdir(output);
    await writeFile(join(outside, "SKILL.md"), "---\nname: linked\n---\n");
    try { await symlink(outside, join(sourceRoot, "linked"), "dir"); }
    catch (error) { if (error?.code === "EPERM") { t.skip(`OS disallows symlink creation: ${error.code}`); return; } throw error; }
    const sources = { skills: [{ name: "linked", sourceType: "original", localRoot: "projectSkills", localPath: "linked/", license: "MIT" }] };
    const lock = { skills: [{ name: "linked", sourceType: "original", localSha256: "0".repeat(64), releaseCommit: "0".repeat(40), license: "MIT", payloadType: "directory", dependencies: [] }] };
    await writeFile(join(root, "sources.json"), JSON.stringify(sources)); await writeFile(join(root, "lock.json"), JSON.stringify(lock));
    await writeFile(join(root, "report.md"), `# Release\n\n${renderExclusionSection([])}`);
    const result = await runAcquisitionGate({ sourceManifestPath: join(root, "sources.json"), lockInputPath: join(root, "lock.json"), lockOutputPath: join(output, "lock.json"), payloadOutputPath: join(output, "skills"), releaseReportInputPath: join(root, "report.md"), releaseReportOutputPath: join(output, "report.md"), environment: { AGENTIC_PROJECT_SKILLS_ROOT: sourceRoot } });
    assert.equal(result.skills[0].excluded, true);
    assert.match(result.skills[0].exclusionReason, /symbolic link|outside configured root/i);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("acquisition rejects a nested symlink inside a directory source", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "acquisition-nested-symlink-"));
  try {
    const sourceRoot = join(root, "sources"), source = join(sourceRoot, "linked"), outside = join(root, "outside.md"), output = join(root, "output");
    await mkdir(join(source, "nested"), { recursive: true }); await mkdir(output);
    await writeFile(join(source, "SKILL.md"), "---\nname: linked\n---\n"); await writeFile(outside, "outside\n");
    try { await symlink(outside, join(source, "nested", "escape.md"), "file"); }
    catch (error) { if (error?.code === "EPERM") { t.skip(`OS disallows symlink creation: ${error.code}`); return; } throw error; }
    const sources = { skills: [{ name: "linked", sourceType: "original", localRoot: "projectSkills", localPath: "linked/", license: "MIT" }] };
    const lock = { skills: [{ name: "linked", sourceType: "original", localSha256: "0".repeat(64), releaseCommit: "0".repeat(40), license: "MIT", payloadType: "directory", dependencies: [] }] };
    await writeFile(join(root, "sources.json"), JSON.stringify(sources)); await writeFile(join(root, "lock.json"), JSON.stringify(lock));
    await writeFile(join(root, "report.md"), `# Release\n\n${renderExclusionSection([])}`);
    const result = await runAcquisitionGate({ sourceManifestPath: join(root, "sources.json"), lockInputPath: join(root, "lock.json"), lockOutputPath: join(output, "lock.json"), payloadOutputPath: join(output, "skills"), releaseReportInputPath: join(root, "report.md"), releaseReportOutputPath: join(output, "report.md"), environment: { AGENTIC_PROJECT_SKILLS_ROOT: sourceRoot } });
    assert.equal(result.skills[0].excluded, true);
    assert.match(result.skills[0].exclusionReason, /must not contain symbolic links/i);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("acquisition rejects a legal-file symlink", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "acquisition-legal-symlink-"));
  try {
    const sourceRoot = join(root, "sources"), legalRoot = join(root, "legal"), output = join(root, "output"), outside = join(root, "outside-LICENSE");
    await mkdir(join(sourceRoot, "linked"), { recursive: true }); await mkdir(join(legalRoot, "licenses"), { recursive: true }); await mkdir(output);
    await writeFile(join(sourceRoot, "linked", "SKILL.md"), "---\nname: linked\n---\n"); await writeFile(outside, "license\n");
    try { await symlink(outside, join(legalRoot, "licenses", "linked-LICENSE"), "file"); }
    catch (error) { if (error?.code === "EPERM") { t.skip(`OS disallows symlink creation: ${error.code}`); return; } throw error; }
    const sources = { skills: [{ name: "linked", sourceType: "adapted", repository: "https://example.test/upstream", revision: "a".repeat(40), upstreamPath: "SKILL.md", localRoot: "projectSkills", localPath: "linked/SKILL.md", changeNotice: "fixture", patchPath: "manifests/patches/linked.patch" }] };
    const lock = { skills: [{ name: "linked", sourceType: "adapted", repository: "https://example.test/upstream", revision: "a".repeat(40), upstreamPath: "SKILL.md", sha256: "b".repeat(64), localSha256: "0".repeat(64), dependencies: [], changeNotice: "fixture", patchPath: "manifests/patches/linked.patch", licenseFiles: [{ upstreamPath: "LICENSE", path: "licenses/linked-LICENSE", sha256: await sha256File(outside) }] }] };
    await writeFile(join(root, "sources.json"), JSON.stringify(sources)); await writeFile(join(root, "lock.json"), JSON.stringify(lock)); await writeFile(join(root, "report.md"), `# Release\n\n${renderExclusionSection([])}`);
    const result = await runAcquisitionGate({ sourceManifestPath: join(root, "sources.json"), lockInputPath: join(root, "lock.json"), lockOutputPath: join(output, "lock.json"), payloadOutputPath: join(output, "skills"), legalPayloadRootPath: legalRoot, releaseReportInputPath: join(root, "report.md"), releaseReportOutputPath: join(output, "report.md"), environment: { AGENTIC_PROJECT_SKILLS_ROOT: sourceRoot } });
    assert.equal(result.skills[0].excluded, true); assert.match(result.skills[0].exclusionReason, /symbolic link/i);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("acquisition gate excludes valid third-party sources with missing or tampered legal payload", async () => {
  const root = await mkdtemp(join(tmpdir(), "acquisition-legal-fixture-"));
  try {
    const sourceRoot = join(root, "sources"), legalRoot = join(root, "legal"), output = join(root, "output");
    for (const name of ["missing-legal", "tampered-legal"]) {
      await mkdir(join(sourceRoot, name), { recursive: true });
      await writeFile(join(sourceRoot, name, "SKILL.md"), `---\nname: ${name}\n---\n`);
    }
    await mkdir(join(legalRoot, "licenses"), { recursive: true });
    const expectedLicense = join(root, "expected-LICENSE");
    await writeFile(expectedLicense, "approved license\n");
    const expectedLegalHash = await sha256File(expectedLicense);
    await writeFile(join(legalRoot, "licenses", "tampered-LICENSE"), "tampered license\n");

    const sourceBase = {
      sourceType: "adapted", repository: "https://example.test/upstream", revision: "a".repeat(40),
      upstreamPath: "SKILL.md", localRoot: "projectSkills", changeNotice: "fixture adaptation",
    };
    const sources = { skills: [
      { ...sourceBase, name: "missing-legal", localPath: "missing-legal/SKILL.md", patchPath: "manifests/patches/missing-legal.patch" },
      { ...sourceBase, name: "tampered-legal", localPath: "tampered-legal/SKILL.md", patchPath: "manifests/patches/tampered-legal.patch" },
    ] };
    const lock = { skills: sources.skills.map(source => ({
      name: source.name, sourceType: "adapted", repository: source.repository, revision: source.revision,
      upstreamPath: source.upstreamPath, sha256: "b".repeat(64), localSha256: "0".repeat(64), dependencies: [],
      changeNotice: source.changeNotice, patchPath: source.patchPath,
      licenseFiles: [{
        upstreamPath: "LICENSE", path: `licenses/${source.name === "missing-legal" ? "missing" : "tampered"}-LICENSE`, sha256: expectedLegalHash,
      }],
    })) };
    await mkdir(output, { recursive: true });
    await writeFile(join(root, "sources.json"), JSON.stringify(sources));
    await writeFile(join(root, "lock.json"), JSON.stringify(lock));
    await writeFile(join(root, "report.md"), `# Release\n\n${renderExclusionSection([])}`);

    const result = await runAcquisitionGate({
      sourceManifestPath: join(root, "sources.json"), lockInputPath: join(root, "lock.json"),
      lockOutputPath: join(output, "skills.lock.json"), payloadOutputPath: join(output, "skills"), legalPayloadRootPath: legalRoot,
      releaseReportInputPath: join(root, "report.md"), releaseReportOutputPath: join(output, "release-report.md"),
      environment: { AGENTIC_PROJECT_SKILLS_ROOT: sourceRoot },
    });

    assert.deepEqual(await readdir(join(output, "skills")), []);
    const writtenLock = JSON.parse(await readFile(join(output, "skills.lock.json"), "utf8"));
    for (const name of ["missing-legal", "tampered-legal"]) {
      const returned = result.skills.find(entry => entry.name === name);
      const written = writtenLock.skills.find(entry => entry.name === name);
      assert.equal(returned.excluded, true);
      assert.match(returned.exclusionReason, /^Legal verification failed:/);
      assert.equal(written.exclusionReason, returned.exclusionReason);
    }
    assert.match(result.skills.find(entry => entry.name === "missing-legal").exclusionReason, /ENOENT|no such file/i);
    assert.match(result.skills.find(entry => entry.name === "tampered-legal").exclusionReason, /license hash mismatch/);
    const report = await readFile(join(output, "release-report.md"), "utf8");
    assert.deepEqual(verifyExclusionSection(writtenLock.skills, report), writtenLock.skills.map(({ name, exclusionReason: reason }) => ({ name, reason })));
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("adapted and original local imports retain provenance contracts", async () => {
  const lock = JSON.parse(await readFile(new URL("../manifests/skills.lock.json", import.meta.url), "utf8"));
  const byName = new Map(lock.skills.map(entry => [entry.name, entry]));
  const adapted = {
    brainstorming: "obra/superpowers",
    cavecrew: "JuliusBrussee/caveman",
    caveman: "JuliusBrussee/caveman",
    "grill-me": "mattpocock/skills",
    "improve-codebase-architecture": "mattpocock/skills",
    impeccable: "pbakaus/impeccable",
    "learn-codebase": "thedotmack/claude-mem",
    "setup-matt-pocock-skills": "mattpocock/skills",
    "swarm-orchestration": "ruvnet/ruflo",
    "to-spec": "mattpocock/skills",
    wayfinder: "mattpocock/skills",
    "writing-plans": "obra/superpowers",
    "ui-ux-pro-max": "nextlevelbuilder/ui-ux-pro-max-skill"
  };
  for (const [name, upstream] of Object.entries(adapted)) {
    const entry = byName.get(name);
    assert.equal(entry.sourceType, "adapted");
    assert.match(entry.sha256, /^[a-f0-9]{64}$/);
    const localSkill = new URL(`../plugins/agentic-engineering-skills/skills/${name}/`, import.meta.url);
    const localHash = entry.upstreamPath.endsWith("/") ? await sha256Path(fileURLToPath(localSkill)) : await sha256File(new URL("SKILL.md", localSkill));
    assert.equal(localHash, entry.localSha256);
    assert.match(await readFile(new URL(`../plugins/agentic-engineering-skills/skills/${name}/SKILL.md`, import.meta.url), "utf8"), new RegExp(`Adaptation:[^\\n]+${upstream.replace("/", "\\/")}`));
    const patchUrl = new URL(`../${entry.patchPath}`, import.meta.url);
    assert.ok((await stat(patchUrl)).size > 0);
    assert.doesNotMatch(await readFile(patchUrl, "utf8"), /(?:C:\\\\Users|\\\\wsl\.localhost|\/home\/[^/]+)/);
  }
  for (const name of ["claude-implement", "codex-implement", "cleaning-repo-with-knip", "importing-handoff"]) {
    const entry = byName.get(name);
    assert.equal(entry.sourceType, "original");
    assert.equal("revision" in entry, false);
    assert.equal("repository" in entry, false);
    const localSkill = new URL(`../plugins/agentic-engineering-skills/skills/${name}/`, import.meta.url);
    const localHash = entry.payloadType === "directory"
      ? await sha256Path(fileURLToPath(localSkill))
      : await sha256File(new URL("SKILL.md", localSkill));
    assert.equal(localHash, entry.localSha256);
  }
});

test("importing-handoff records and hashes its complete original payload", async () => {
  const lock = JSON.parse(await readFile(new URL("../manifests/skills.lock.json", import.meta.url), "utf8"));
  const entry = lock.skills.find(({ name }) => name === "importing-handoff");
  const payload = new URL("../plugins/agentic-engineering-skills/skills/importing-handoff/", import.meta.url);

  assert.equal(entry?.sourceType, "original");
  assert.equal(entry?.payloadType, "directory");
  assert.equal(await sha256Path(fileURLToPath(payload)), entry.localSha256);
  for (const path of [
    "agents/openai.yaml",
    "references/workflow-phases.md",
    "references/failure-policy.md",
    "references/contract-schema.md",
    "references/reviewer-prompts.md",
    "scripts/inspect-handoff.mjs",
    "scripts/run-reference.mjs",
    "scripts/build-contract.mjs",
    "scripts/capture-matrix.mjs",
    "scripts/compare-receipts.mjs",
    "scripts/verify-import-scope.mjs",
  ]) assert.ok(await stat(new URL(path, payload)));
});

test("all skill frontmatter is closed and adaptation notices stay in Markdown body", async () => {
  const lock = JSON.parse(await readFile(new URL("../manifests/skills.lock.json", import.meta.url), "utf8"));
  for (const entry of lock.skills) {
    const source = await readFile(new URL(`../plugins/agentic-engineering-skills/skills/${entry.name}/SKILL.md`, import.meta.url), "utf8");
    const normalized = source.replace(/\r\n/g, "\n");
    assert.ok(normalized.startsWith("---\n"), `${entry.name} must open YAML frontmatter`);
    const closing = normalized.indexOf("\n---\n", 4);
    assert.ok(closing > 4, `${entry.name} must close YAML frontmatter`);
    const frontmatter = normalized.slice(4, closing);
    const body = normalized.slice(closing + 5);
    assert.match(frontmatter, /^name:\s*[^\n]+$/m, `${entry.name} frontmatter requires name`);
    assert.match(frontmatter, /^description:\s*(?:>|[^\n]+)$/m, `${entry.name} frontmatter requires description`);
    assert.doesNotMatch(frontmatter, /Adaptation:/, `${entry.name} adaptation notice must not be YAML`);
    if (entry.sourceType === "adapted") assert.match(body, /Adaptation:/, `${entry.name} adaptation notice must be Markdown body`);
  }
});
