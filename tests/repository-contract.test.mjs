import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import test from "node:test";

import { expectedSkills } from "./expected-inventory.mjs";

const root = new URL("../", import.meta.url);

function trackedFiles() {
  return execFileSync("git", ["ls-files", "-z"], {
    cwd: root,
    encoding: "utf8",
  })
    .split("\0")
    .filter(Boolean);
}

test("requested inventory contains exactly 19 unique sorted skills", () => {
  assert.equal(expectedSkills.length, 19);
  assert.equal(new Set(expectedSkills).size, 19);
  assert.deepEqual(expectedSkills, [...expectedSkills].sort());
});

test("package exposes the minimal Node 22 command surface", async () => {
  const packageJson = JSON.parse(await readFile(new URL("package.json", root), "utf8"));

  assert.equal(packageJson.name, "agentic-engineering-skills");
  assert.equal(packageJson.version, "0.1.0");
  assert.equal(packageJson.private, true);
  assert.equal(packageJson.type, "module");
  assert.deepEqual(packageJson.engines, { node: ">=22" });
  assert.deepEqual(packageJson.scripts, {
    test: "node --test",
    "verify:pack": "node scripts/verify-pack.mjs",
    "verify:upstream": "node scripts/verify-upstream.mjs",
    "audit:public": "node scripts/audit-public.mjs",
  });
});

test("legacy harness files stay absent", () => {
  const forbidden = trackedFiles().filter(
    (path) =>
      path.startsWith("src/") ||
      path.startsWith("evals/") ||
      path === "tsconfig.json" ||
      /^vitest\.config(?:\.[^/]+)?$/.test(path),
  );

  assert.deepEqual(forbidden, []);
});

test("dependency update automation stays absent", async () => {
  const files = trackedFiles();
  const forbiddenConfigs = files.filter(
    (path) =>
      path === ".github/dependabot.yml" ||
      path === ".github/dependabot.yaml" ||
      /(^|\/)(?:renovate\.json|renovate\.json5|\.renovaterc(?:\.json)?)$/.test(path),
  );
  assert.deepEqual(forbiddenConfigs, []);

  const workflows = files.filter((path) => /^\.github\/workflows\/[^/]+\.ya?ml$/.test(path));
  for (const path of workflows) {
    const contents = await readFile(new URL(path, root), "utf8");
    assert.doesNotMatch(contents, /^\s*schedule\s*:/m, `${path} must not use a schedule`);
  }
});

test("tracked release files contain no latest install flags", async () => {
  const mutableTag = ["@", "latest"].join("");
  const latestInstallFlag = new RegExp(
    `(?:--(?:channel|tag|version)[= ]latest|${mutableTag}\\b)`,
    "i",
  );
  const textFiles = trackedFiles().filter((path) =>
    /(?:^|\/)(?:[^/]+\.(?:md|mdx|json|mjs|js|ya?ml)|Dockerfile)$/.test(path),
  );

  for (const path of textFiles) {
    const contents = await readFile(new URL(path, root), "utf8");
    assert.doesNotMatch(
      contents,
      latestInstallFlag,
      `${path} must not select a mutable latest release`,
    );
  }
});
