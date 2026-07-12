import assert from "node:assert/strict";
import { mkdir, mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import test from "node:test";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const auditScript = path.join(root, "scripts", "audit-public.mjs");
const cleanFixture = path.join(root, "tests", "fixtures", "public-audit", "clean.txt");

function runAudit(args, options = {}) {
  const { cwd = root, ...spawnOptions } = options;
  return spawnSync(process.execPath, [auditScript, ...args], {
    cwd,
    encoding: "utf8",
    env: { ...process.env, NODE_ENV: "test" },
    ...spawnOptions,
  });
}

function runGit(cwd, args) {
  const result = spawnSync("git", args, { cwd, encoding: "utf8" });
  assert.equal(result.status, 0, `git ${args.join(" ")} failed:\n${result.stderr}`);
}

async function runFiles(files, extraArgs = []) {
  const directory = await mkdtemp(path.join(tmpdir(), "public-audit-"));
  const paths = [];
  for (const [name, content] of files) {
    const file = path.join(directory, name);
    await writeFile(file, content);
    paths.push(file);
  }
  const list = path.join(directory, "files.json");
  await writeFile(list, JSON.stringify(paths));
  return runAudit(["--test-file-list", list, ...extraArgs]);
}

const contentCases = [
  ["OpenAI project key", "notes.txt", `token=${["sk", "proj", "exampleSecretValue"].join("-")}`, "secret:openai-project-key", ["sk", "proj", "exampleSecretValue"].join("-")],
  ["Anthropic key", "notes.txt", `token=${["sk", "ant", "exampleSecretValue"].join("-")}`, "secret:anthropic-key", ["sk", "ant", "exampleSecretValue"].join("-")],
  ["Google API key", "notes.txt", `token=${["AI", "za"].join("")}${"A".repeat(35)}`, "secret:google-api-key", `${["AI", "za"].join("")}${"A".repeat(35)}`],
  ["GitHub token", "notes.txt", `token=${["ghp", ""].join("_")}${"a".repeat(36)}`, "secret:github-token", `${["ghp", ""].join("_")}${"a".repeat(36)}`],
  ["PEM private key", "notes.txt", `${["-----BEGIN", "PRIVATE", "KEY-----"].join(" ")}\nprivate material`, "secret:pem-private-key", "private material"],
  ["Linux home", "notes.txt", `source=${["", "home", "alice", "private", "repo"].join("/")}`, "private-path:linux-home", ["", "home", "alice", "private", "repo"].join("/")],
  ["Windows home", "notes.txt", `source=${["C:", "Users", "alice", "private", "repo"].join("\\")}`, "private-path:windows-home", ["C:", "Users", "alice"].join("\\")],
  ["localhost URL", "notes.txt", `endpoint=${["http:/", "localhost:3000", "admin"].join("/")}`, "url:non-public", ["http:/", "localhost:3000", "admin"].join("/")],
  ["private IP URL", "notes.txt", `endpoint=${["http:/", "192.168.1.5", "admin"].join("/")}`, "url:non-public", ["http:/", "192.168.1.5", "admin"].join("/")],
  ["internal hostname URL", "notes.txt", `endpoint=${["https:/", "build.internal", "job"].join("/")}`, "url:non-public", ["https:/", "build.internal", "job"].join("/")],
  ["legal year placeholder", "LICENSE.txt", `Copyright (c) ${["[year", "] [fullname", "]"].join("")}`, "legal-template:unresolved", ["[fullname", "]"].join("")],
  ["legal angle placeholder", "NOTICE.txt", `Copyright ${["<YEAR", "> <COPYRIGHT HOLDER", ">"].join("")}`, "legal-template:unresolved", ["<COPYRIGHT HOLDER", ">"].join("")],
];

for (const [label, name, content, rule, secret] of contentCases) {
  test(`reports ${label} without exposing matched content`, async () => {
    const result = await runFiles([[name, content]]);
    assert.equal(result.status, 1, result.stderr);
    assert.match(result.stdout, new RegExp(`:${rule.replaceAll("-", "\\-")}$`, "m"));
    assert.equal(result.stdout.includes(secret), false, result.stdout);
    assert.equal(result.stderr.includes(secret), false, result.stderr);
  });
}

const forbiddenNames = [
  [".env", "name:environment-file"],
  ["debug.log", "name:log-file"],
  ["release.zip", "name:generated-archive"],
  ["release.tar.gz", "name:generated-archive"],
];

for (const [name, rule] of forbiddenNames) {
  test(`rejects tracked-style forbidden name ${name} before content scanning`, async () => {
    const marker = "must-not-be-printed";
    const result = await runFiles([[name, marker]]);
    assert.equal(result.status, 1, result.stderr);
    assert.match(result.stdout, new RegExp(`:${rule}$`, "m"));
    assert.equal(result.stdout.includes(marker), false);
  });
}

test("rejects files above configured release limit without reading them", async () => {
  const marker = "oversize-secret-marker";
  const result = await runFiles([["large.txt", marker.repeat(10)]], ["--max-file-bytes", "16"]);
  assert.equal(result.status, 1, result.stderr);
  assert.match(result.stdout, /:size:release-limit$/m);
  assert.equal(result.stdout.includes(marker), false);
});

test("accepts clean fixture", async () => {
  const directory = await mkdtemp(path.join(tmpdir(), "public-audit-clean-"));
  const list = path.join(directory, "files.json");
  await writeFile(list, JSON.stringify([cleanFixture]));
  const result = runAudit(["--test-file-list", list]);
  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
});

test("test file override is unavailable outside test mode", async () => {
  const directory = await mkdtemp(path.join(tmpdir(), "public-audit-mode-"));
  const list = path.join(directory, "files.json");
  await writeFile(list, JSON.stringify([cleanFixture]));
  const result = runAudit(["--test-file-list", list], {
    env: { ...process.env, NODE_ENV: "production" },
  });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /test-only/);
});

test("default mode scans only Git-tracked files", async () => {
  const repository = await mkdtemp(path.join(tmpdir(), "public-audit-git-"));
  runGit(repository, ["init"]);
  runGit(repository, ["config", "user.name", "Public Audit Test"]);
  runGit(repository, ["config", "user.email", "public-audit@example.invalid"]);
  await writeFile(path.join(repository, "clean.txt"), "Public release content.\n");
  runGit(repository, ["add", "clean.txt"]);
  runGit(repository, ["commit", "-m", "test fixture"]);

  const secret = ["sk", "proj", "mustRemainHidden"].join("-");
  await writeFile(path.join(repository, ".env"), `TOKEN=${secret}\n`);

  const untrackedResult = runAudit([], { cwd: repository });
  assert.equal(untrackedResult.status, 0, `${untrackedResult.stdout}\n${untrackedResult.stderr}`);

  runGit(repository, ["add", ".env"]);
  const trackedResult = runAudit([], { cwd: repository });
  assert.equal(trackedResult.status, 1, trackedResult.stderr);
  assert.match(trackedResult.stdout, /^\.env:name:environment-file$/m);
  assert.equal(trackedResult.stdout.includes(secret), false);
  assert.equal(trackedResult.stderr.includes(secret), false);
});

test("retained legal templates are allowed only for exact manifest license paths", async () => {
  const repository = await mkdtemp(path.join(tmpdir(), "public-audit-license-"));
  runGit(repository, ["init"]);
  runGit(repository, ["config", "user.name", "Public Audit Test"]);
  runGit(repository, ["config", "user.email", "public-audit@example.invalid"]);
  await mkdir(path.join(repository, "manifests"), { recursive: true });
  await mkdir(path.join(repository, "licenses"), { recursive: true });
  const placeholder = ["[yyyy", "]"].join("");
  await writeFile(path.join(repository, "licenses", "retained-LICENSE"), `Copyright ${placeholder}\n`);
  await writeFile(path.join(repository, "ordinary.txt"), `Copyright ${placeholder}\n`);
  await writeFile(path.join(repository, "manifests", "skills.lock.json"), JSON.stringify({
    skills: [{ licenseFiles: [{ path: "licenses/retained-LICENSE" }] }],
  }));
  runGit(repository, ["add", "manifests/skills.lock.json", "licenses/retained-LICENSE"]);

  const approvedResult = runAudit([], { cwd: repository });
  assert.equal(approvedResult.status, 0, `${approvedResult.stdout}\n${approvedResult.stderr}`);

  runGit(repository, ["add", "ordinary.txt"]);
  const ordinaryResult = runAudit([], { cwd: repository });
  assert.equal(ordinaryResult.status, 1, ordinaryResult.stderr);
  assert.match(ordinaryResult.stdout, /^ordinary\.txt:legal-template:unresolved$/m);
  assert.doesNotMatch(ordinaryResult.stdout, /retained-LICENSE/);
});
