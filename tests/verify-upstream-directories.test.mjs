import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { mkdtemp, mkdir, readFile, rm, writeFile, cp } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

const repository = new URL("../", import.meta.url);
const revision = "0123456789012345678901234567890123456789";

test("--stamp hashes adapted directory payloads and original file or directory payloads offline", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "verify-upstream-directories-"));
  t.after(() => rm(root, { recursive: true, force: true }));

  await mkdir(join(root, "scripts/lib"), { recursive: true });
  await cp(new URL("../scripts/verify-upstream.mjs", import.meta.url), join(root, "scripts/verify-upstream.mjs"));
  await cp(new URL("../scripts/lib/hash.mjs", import.meta.url), join(root, "scripts/lib/hash.mjs"));
  await cp(new URL("../scripts/lib/manifest.mjs", import.meta.url), join(root, "scripts/lib/manifest.mjs"));
  await cp(new URL("../scripts/lib/upstream.mjs", import.meta.url), join(root, "scripts/lib/upstream.mjs"));
  await mkdir(join(root, "manifests"), { recursive: true });
  await mkdir(join(root, "adapted"));
  await writeFile(join(root, "adapted/a.txt"), "alpha\n");
  await mkdir(join(root, "original-tree"));
  await writeFile(join(root, "original-tree/SKILL.md"), "Adapted tree\n");
  await mkdir(join(root, "original-file"));
  await writeFile(join(root, "original-file/SKILL.md"), "Original file\n");
  await writeFile(join(root, "manifests/skills.lock.json"), JSON.stringify({ skills: [] }));
  await writeFile(join(root, "manifests/skill-sources.json"), JSON.stringify({ skills: [
    {
      name: "adapted-tree",
      sourceType: "adapted",
      repository: "https://example.test/upstream.git",
      revision,
      upstreamPath: "skill/",
      localRoot: "projectSkills",
      localPath: "adapted/",
      changeNotice: "Fixture adaptation",
      patchPath: "manifests/patches/adapted-tree.patch",
    },
    {
      name: "original-tree",
      sourceType: "original",
      localRoot: "projectSkills",
      localPath: "original-tree/",
      license: "MIT",
    },
    {
      name: "original-file",
      sourceType: "original",
      localRoot: "projectSkills",
      localPath: "original-file/SKILL.md",
      license: "MIT",
    },
  ] }));

  const git = ["init", "-q", root];
  execFileSync("git", git);
  execFileSync("git", ["-C", root, "config", "user.name", "Fixture"]);
  execFileSync("git", ["-C", root, "config", "user.email", "fixture@example.test"]);
  execFileSync("git", ["-C", root, "commit", "--allow-empty", "-qm", "fixture"]);

  const result = spawnSync(process.execPath, [join(root, "scripts/verify-upstream.mjs"), "--stamp", "--status", "vendor"], {
    encoding: "utf8",
    env: { ...process.env, AGENTIC_PROJECT_SKILLS_ROOT: root },
  });
  assert.equal(result.status, 0, result.stderr || result.stdout);

  const lock = JSON.parse(await readFile(join(root, "manifests/skills.lock.json"), "utf8"));
  assert.deepEqual(lock.skills.map(({ name, localSha256 }) => [name, localSha256]), [
    ["adapted-tree", "a75a15df05d06ea19bfd25812d63272a46257b360ef47b8d2b4a79e24cbe0ac7"],
    ["original-file", "ee5081fe11e897fc389c5d60c5ad319df9e2f0262aec427da1f6a227a4c2e3ce"],
    ["original-tree", "4cd490da160e3d6e76e18609ec8b565d567961661dc928504b0a96645db31e50"],
  ]);
});
