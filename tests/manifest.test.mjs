import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, relative, resolve } from "node:path";
import { validateManifest, dependencyOrder, verifyLocalEntries, validateSourceManifest, resolveAcquisitionPath } from "../scripts/lib/manifest.mjs";

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
