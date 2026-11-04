import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, readdir, stat, writeFile, rm, truncate, symlink, link } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, relative, resolve } from "node:path";
import { validateManifest, dependencyOrder, verifyLocalEntries, validateSourceManifest, resolveAcquisitionPath, loadPatchBytes, listPatchBundlePaths, writePatchBundle } from "../scripts/lib/manifest.mjs";

const upstream = { name: "a", sourceType: "vendor", repository: "https://example.test/a", revision: "a".repeat(40), upstreamPath: "SKILL.md", sha256: "b".repeat(64), localSha256: "b".repeat(64), dependencies: [], licenseFiles: [{ upstreamPath: "LICENSE", path: "plugins/agentic-engineering-skills/licenses/a-LICENSE", sha256: "c".repeat(64) }] };
const adapted = { ...upstream, name: "adapted", sourceType: "adapted", changeNotice: "Host compatibility changes", patchPath: "manifests/patches/adapted.patch" };

test("validates discriminated source entries and sorts names", () => {
  const original = { name: "z", sourceType: "original", localSha256: "c".repeat(64), releaseCommit: "d".repeat(40), license: "MIT", payloadType: "file", dependencies: [] };
  assert.deepEqual(validateManifest({ skills: [original, upstream] }).map(x => x.name), ["a", "z"]);
});

test("rejects non-portable skill names in lock and source manifests", () => {
  const invalidNames = ["../escape", "nested/skill", "nested\\skill", ".", "two.dots", "Uppercase"];
  for (const name of invalidNames) {
    assert.throws(() => validateManifest({ skills: [{ ...upstream, name }] }), /portable skill name/i, `lock name ${name}`);
    assert.throws(() => validateSourceManifest({ skills: [{ name, sourceType: "vendor" }] }), /portable skill name/i, `source name ${name}`);
  }
});

test("adapted entries require objective change metadata", () => {
  assert.doesNotThrow(() => validateManifest({ skills: [adapted] }));
  assert.throws(() => validateManifest({ skills: [{ ...adapted, changeNotice: "" }] }), /changeNotice/);
  assert.throws(() => validateManifest({ skills: [{ ...adapted, patchPath: "patches/a.patch" }] }), /manifests\/patches/);
  assert.throws(() => validateManifest({ skills: [{ ...adapted, patchPath: "manifests/patches/..\\outside.patch" }] }), /patchPath|normalized/i);
});

test("rejects missing and forbidden fields", () => {
  assert.throws(() => validateManifest({ skills: [{ ...upstream, revision: undefined }] }), /revision/);
  assert.throws(() => validateManifest({ skills: [{ name: "o", sourceType: "original", localSha256: "a".repeat(64), releaseCommit: "b".repeat(40), license: "MIT", payloadType: "file", revision: "c".repeat(40), dependencies: [] }] }), /forbidden.*revision/i);
  assert.throws(() => validateManifest({ skills: [{ name: "o", sourceType: "original", localSha256: "a".repeat(64), releaseCommit: "not-a-commit", license: "MIT", payloadType: "file", dependencies: [] }] }), /releaseCommit/);
  assert.throws(() => validateManifest({ skills: [{ name: "o", sourceType: "original", localSha256: "a".repeat(64), releaseCommit: "b".repeat(40), license: "MIT", dependencies: [] }] }), /payloadType/);
  assert.throws(() => validateManifest({ skills: [{ name: "o", sourceType: "original", localSha256: "a".repeat(64), releaseCommit: "b".repeat(40), license: "MIT", payloadType: "archive", dependencies: [] }] }), /payloadType/);
});

test("requires strict normalized licenseFiles on third-party entries", () => {
  assert.throws(() => validateManifest({ skills: [{ ...upstream, licenseFiles: [] }] }), /licenseFiles/);
  assert.throws(() => validateManifest({ skills: [{ ...upstream, licenseFiles: [{ ...upstream.licenseFiles[0], path: "../LICENSE" }] }] }), /licenseFiles/);
  assert.throws(() => validateManifest({ skills: [{ ...upstream, licenseFiles: [{ ...upstream.licenseFiles[0], upstreamPath: "/LICENSE" }] }] }), /licenseFiles/);
  assert.throws(() => validateManifest({ skills: [{ ...upstream, licenseFiles: [{ ...upstream.licenseFiles[0], sha256: "bad" }] }] }), /licenseFiles/);
});

test("rejects dependency cycles and unknown dependencies", () => {
  assert.throws(() => dependencyOrder([{ ...upstream, name: "a", dependencies: ["b"] }]), /unknown dependency/i);
  assert.throws(() => dependencyOrder([{ ...upstream, name: "a", dependencies: ["b"] }, { ...upstream, name: "b", dependencies: ["a"] }]), /cycle/i);
});

test("rejects a valid-format manifest hash that mismatches local content", async () => {
  const root = await mkdtemp(join(tmpdir(), "manifest-hash-"));
  await mkdir(join(root, "skills/a"), { recursive: true });
  await writeFile(join(root, "skills/a/SKILL.md"), "actual content");
  await assert.rejects(
    verifyLocalEntries([{ ...upstream, localSha256: "f".repeat(64) }], root, "skills"),
    /tamper detected.*expected f{64}/i,
  );
  await rm(root, { recursive: true, force: true });
});

test("source acquisition paths are portable and resolved from explicit roots", () => {
  const source = { name: "local", sourceType: "adapted", localRoot: "projectSkills", localPath: "local/SKILL.md" };
  const portableRoot = resolve(tmpdir(), "portable-root");
  const expectedRelative = join("local", "SKILL.md");
  assert.doesNotThrow(() => validateSourceManifest({ skills: [source] }));
  const acquisitionPath = resolveAcquisitionPath(source, { AGENTIC_PROJECT_SKILLS_ROOT: portableRoot });
  assert.equal(acquisitionPath, resolve(portableRoot, expectedRelative));
  assert.equal(relative(portableRoot, acquisitionPath), expectedRelative);
  assert.throws(() => validateSourceManifest({ skills: [{ ...source, localPath: "/absolute/private/SKILL.md" }] }), /portable and relative/);
  assert.throws(() => resolveAcquisitionPath(source, {}), /AGENTIC_PROJECT_SKILLS_ROOT is required/);
});

test("patch bundles preserve UTF-8 bytes across bounded chunks and legacy patches stay raw", async () => {
  const root = await mkdtemp(join(process.cwd(), ".patch-bundle-"));
  try {
    const patchPath = join(root, "skill.patch");
    const prefix = "diff --git a/x b/x\n";
    const bytes = Buffer.from(`${prefix}${"a".repeat(900 * 1024 - Buffer.byteLength(prefix) - 1)}💩tail`, "utf8");
    await writePatchBundle(patchPath, bytes, root);
    const pointer = await readFile(patchPath, "utf8");
    const magic = "AGENTIC-PATCH-CHUNKS/1\n";
    assert.ok(pointer.startsWith(magic));
    assert.ok(Buffer.byteLength(pointer, "utf8") < 1024 * 1024);
    const metadata = JSON.parse(pointer.slice(magic.length));
    assert.equal(metadata.byteLength, bytes.length);
    assert.ok(metadata.chunks.length >= 2);
    const chunkRoot = join(root, "skill.patch.parts", metadata.sha256);
    for (const chunk of metadata.chunks) {
      assert.ok(chunk.byteLength <= 900 * 1024);
      assert.ok(chunk.path.startsWith(`skill.patch.parts/${metadata.sha256}/`));
      const chunkPath = join(root, chunk.path);
      const chunkBytes = await readFile(chunkPath);
      assert.ok((await stat(chunkPath)).size < 1024 * 1024);
      assert.doesNotThrow(() => new TextDecoder("utf-8", { fatal: true }).decode(chunkBytes));
    }
    assert.ok((await readdir(chunkRoot)).length >= 2);
    assert.deepEqual(await loadPatchBytes(patchPath, root), bytes);
    assert.equal((await listPatchBundlePaths(patchPath, root)).length, metadata.chunks.length + 1);

    const legacyPath = join(root, "legacy.patch");
    const legacy = Buffer.from("diff --git a/x b/x\n+utf8 💩\n", "utf8");
    await writePatchBundle(legacyPath, legacy, root);
    assert.deepEqual(await readFile(legacyPath), legacy);
    assert.deepEqual(await loadPatchBytes(legacyPath, root), legacy);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("patch bundle loader rejects missing, altered and unsafe chunks", async () => {
  const root = await mkdtemp(join(process.cwd(), ".patch-bundle-invalid-"));
  try {
    const patchPath = join(root, "skill.patch");
    await writePatchBundle(patchPath, Buffer.from(`diff --git a/x b/x\n${"💩".repeat(225 * 1024 + 2)}`, "utf8"), root);
    const pointer = await readFile(patchPath, "utf8");
    const magic = "AGENTIC-PATCH-CHUNKS/1\n";
    const metadata = JSON.parse(pointer.slice(magic.length));
    const firstChunk = join(root, metadata.chunks[0].path);
    const original = await readFile(firstChunk);

    await rm(firstChunk);
    await assert.rejects(loadPatchBytes(patchPath, root), /missing|ENOENT/i);
    const altered = Buffer.from(original);
    altered[0] ^= 1;
    await writeFile(firstChunk, altered);
    await assert.rejects(loadPatchBytes(patchPath, root), /SHA-256|hash/i);

    metadata.chunks[0].path = metadata.chunks[1].path;
    await writeFile(patchPath, `${magic}${JSON.stringify(metadata)}\n`);
    await assert.rejects(loadPatchBytes(patchPath, root), /unsafe|unordered/i);

    metadata.chunks[0].path = `../${metadata.chunks[0].path}`;
    await writeFile(patchPath, `${magic}${JSON.stringify(metadata)}\n`);
    await assert.rejects(loadPatchBytes(patchPath, root), /unsafe|invalid.*path/i);

    metadata.chunks = Array.from({ length: 129 }, (_, index) => ({ ...metadata.chunks[1], path: `skill.patch.parts/${metadata.sha256}/${String(index + 1).padStart(6, "0")}.txt` }));
    await writeFile(patchPath, `${magic}${JSON.stringify(metadata)}\n`);
    await assert.rejects(loadPatchBytes(patchPath, root), /chunk count/i);

    metadata.byteLength = 64 * 1024 * 1024 + 1;
    await writeFile(patchPath, `${magic}${JSON.stringify(metadata)}\n`);
    await assert.rejects(loadPatchBytes(patchPath, root), /aggregate byteLength/i);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("patch loader rejects invalid raw patches, corrupted bundle magic and oversized files before reading", async () => {
  const root = await mkdtemp(join(process.cwd(), ".patch-invalid-raw-"));
  try {
    const invalidPath = join(root, "invalid.patch");
    await writeFile(invalidPath, "not a git patch\n");
    await assert.rejects(loadPatchBytes(invalidPath, root), /invalid patch artifact|diff --git/i);

    const bundlePath = join(root, "bundle.patch");
    await writePatchBundle(bundlePath, Buffer.from(`diff --git a/x b/x\n${"x".repeat(900 * 1024)}tail`), root);
    const pointer = await readFile(bundlePath);
    pointer[0] ^= 1;
    await writeFile(bundlePath, pointer);
    await assert.rejects(loadPatchBytes(bundlePath, root), /invalid patch artifact|chunk pointer magic/i);

    const oversizedPath = join(root, "oversized.patch");
    await writeFile(oversizedPath, "");
    await truncate(oversizedPath, 64 * 1024 * 1024 + 1);
    await assert.rejects(loadPatchBytes(oversizedPath, root), /size limit|too large/i);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("patch loader rejects symlinked ancestors and chunks", { skip: process.platform === "win32" }, async () => {
  const root = await mkdtemp(join(process.cwd(), ".patch-symlink-"));
  try {
    const realRoot = join(root, "real"), patchPath = join(realRoot, "skill.patch"), aliasRoot = join(root, "alias");
    await mkdir(realRoot);
    await writePatchBundle(patchPath, Buffer.from(`diff --git a/x b/x\n${"z".repeat(900 * 1024 + 10)}`), root);
    await symlink(realRoot, aliasRoot, "dir");
    await assert.rejects(loadPatchBytes(join(aliasRoot, "skill.patch"), root), /symlink|junction/i);

    const pointer = JSON.parse((await readFile(patchPath, "utf8")).slice("AGENTIC-PATCH-CHUNKS/1\n".length));
    const chunkPath = join(realRoot, pointer.chunks[0].path);
    const outside = join(root, "outside.txt");
    const contents = await readFile(chunkPath);
    await writeFile(outside, contents);
    await rm(chunkPath);
    await symlink(outside, chunkPath, "file");
    await assert.rejects(loadPatchBytes(patchPath, root), /symlink|junction|regular file/i);
  } finally { await rm(root, { recursive: true, force: true }); }
});

test("patch writer atomically replaces a hardlinked artifact without changing external link", async () => {
  const root = await mkdtemp(join(process.cwd(), ".patch-hardlink-"));
  try {
    const external = join(root, "external.txt"), patchPath = join(root, "skill.patch");
    const oldBytes = Buffer.from("diff --git a/x b/x\n+old\n");
    const newBytes = Buffer.from("diff --git a/x b/x\n+new\n");
    await writeFile(external, oldBytes);
    await link(external, patchPath);

    await writePatchBundle(patchPath, newBytes, root);
    assert.deepEqual(await readFile(external), oldBytes);
    assert.deepEqual(await loadPatchBytes(patchPath, root), newBytes);
  } finally { await rm(root, { recursive: true, force: true }); }
});

 test("payload paths accept only the named skill within a declared plugin root", () => {
  const path = "plugins/agentic-engineering-skills/claude-skills/a";
  assert.doesNotThrow(() => validateManifest({ skills: [{ ...upstream, payloadPath: path }] }));
  for (const invalid of ["../escape", "/tmp/a", `${path}/../b`, `${path}\n`, path.replace("/a", "/other"), "plugins/agentic-engineering-skills/agents/a"]) {
    assert.throws(() => validateManifest({ skills: [{ ...upstream, payloadPath: invalid }] }), /payloadPath/);
  }
 });
