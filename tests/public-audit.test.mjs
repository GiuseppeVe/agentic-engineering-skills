import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, symlink, unlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { PATCH_CHUNK_BYTES, listPatchBundlePaths, writePatchBundle } from "../scripts/lib/manifest.mjs";

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

async function runRepositoryFiles(files) {
  const directory = await mkdtemp(path.join(tmpdir(), "public-audit-repository-"));
  const paths = [];
  for (const [name, content] of files) {
    const file = path.join(directory, name);
    await mkdir(path.dirname(file), { recursive: true });
    await writeFile(file, content);
    paths.push(file);
  }
  const list = path.join(directory, "files.json");
  await writeFile(list, JSON.stringify(paths));
  return runAudit(["--test-file-list", list], { cwd: directory });
}

async function createChunkedPatch(name, content) {
  const directory = await mkdtemp(path.join(tmpdir(), "public-audit-chunked-repository-"));
  const patchPath = path.join(directory, name);
  await mkdir(path.dirname(patchPath), { recursive: true });
  await writePatchBundle(patchPath, Buffer.from(content, "utf8"), directory);
  const paths = await listPatchBundlePaths(patchPath, directory);
  return {
    paths,
    run: async (selectedPaths = paths) => {
      const list = path.join(directory, "files.json");
      await writeFile(list, JSON.stringify(selectedPaths));
      return runAudit(["--test-file-list", list], { cwd: directory });
    },
  };
}

const contentCases = [
  ["OpenAI project key", "notes.txt", `token=${["sk", "proj", "exampleSecretValue"].join("-")}`, "secret:openai-project-key", ["sk", "proj", "exampleSecretValue"].join("-")],
  ["Anthropic key", "notes.txt", `token=${["sk", "ant", "exampleSecretValue"].join("-")}`, "secret:anthropic-key", ["sk", "ant", "exampleSecretValue"].join("-")],
  ["Google API key", "notes.txt", `token=${["AI", "za"].join("")}${"A".repeat(35)}`, "secret:google-api-key", `${["AI", "za"].join("")}${"A".repeat(35)}`],
  ["GitHub token", "notes.txt", `token=${["ghp", ""].join("_")}${"a".repeat(36)}`, "secret:github-token", `${["ghp", ""].join("_")}${"a".repeat(36)}`],
  ["PEM private key", "notes.txt", `${["-----BEGIN", "PRIVATE", "KEY-----"].join(" ")}\nprivate material`, "secret:pem-private-key", "private material"],
  ["Linux home", "notes.txt", `source=${["", "home", "alice", "private", "repo"].join("/")}`, "private-path:linux-home", ["", "home", "alice", "private", "repo"].join("/")],
  ["Windows home", "notes.txt", `source=${["C:", "Users", "alice", "private", "repo"].join("\\")}`, "private-path:windows-home", ["C:", "Users", "alice"].join("\\")],
  ["Windows home with forward slashes", "notes.txt", `source=${["C:", "Users", "example", "private", "repo"].join("/")}`, "private-path:windows-home", ["C:", "Users", "example", "private", "repo"].join("/")],
  ["Windows home with mixed separators", "notes.txt", `source=${["D:", "users", "example"].join("/") + "\\private/repo"}`, "private-path:windows-home", ["D:", "users", "example"].join("/") + "\\private/repo"],
  ["Windows home user root with forward slashes", "notes.txt", `source=${["E:", "USERS", "example"].join("/")}`, "private-path:windows-home", ["E:", "USERS", "example"].join("/")],
  ["localhost URL", "notes.txt", `endpoint=${["http:/", "localhost:3000", "admin"].join("/")}`, "url:non-public", ["http:/", "localhost:3000", "admin"].join("/")],
  ["private IP URL", "notes.txt", `endpoint=${["http:/", "192.168.1.5", "admin"].join("/")}`, "url:non-public", ["http:/", "192.168.1.5", "admin"].join("/")],
  ["short-form loopback URL", "notes.txt", `endpoint=${["http:/", "127.1", "admin"].join("/")}`, "url:non-public", ["http:/", "127.1", "admin"].join("/")],
  ["integer loopback URL", "notes.txt", `endpoint=${["http:/", "2130706433", "admin"].join("/")}`, "url:non-public", ["http:/", "2130706433", "admin"].join("/")],
  ["hex loopback URL", "notes.txt", `endpoint=${["http:/", "0x7f000001", "admin"].join("/")}`, "url:non-public", ["http:/", "0x7f000001", "admin"].join("/")],
  ["trailing-dot localhost URL", "notes.txt", `endpoint=${["http:/", "localhost.", "admin"].join("/")}`, "url:non-public", ["http:/", "localhost.", "admin"].join("/")],
  ["zero-address URL", "notes.txt", `endpoint=${["http:/", "0.0.0.0", "admin"].join("/")}`, "url:non-public", ["http:/", "0.0.0.0", "admin"].join("/")],
  ["IPv4 link-local URL", "notes.txt", `endpoint=${["http:/", "169.254.10.20", "admin"].join("/")}`, "url:non-public", ["http:/", "169.254.10.20", "admin"].join("/")],
  ["IPv6 loopback URL", "notes.txt", `endpoint=${["http:/", "[::1]", "admin"].join("/")}`, "url:non-public", ["http:/", "[::1]", "admin"].join("/")],
  ["IPv6 ULA URL", "notes.txt", `endpoint=${["http:/", "[fd12:3456::1]", "admin"].join("/")}`, "url:non-public", ["http:/", "[fd12:3456::1]", "admin"].join("/")],
  ["IPv6 link-local URL", "notes.txt", `endpoint=${["http:/", "[fe80::1]", "admin"].join("/")}`, "url:non-public", ["http:/", "[fe80::1]", "admin"].join("/")],
  ["IPv4-mapped IPv6 private URL", "notes.txt", `endpoint=${["http:/", "[::ffff:192.168.1.5]", "admin"].join("/")}`, "url:non-public", ["http:/", "[::ffff:192.168.1.5]", "admin"].join("/")],
  ["shared-address-space URL", "notes.txt", `endpoint=${["http:/", "100.64.0.1", "admin"].join("/")}`, "url:non-public", ["http:/", "100.64.0.1", "admin"].join("/")],
  ["userinfo private IP URL", "notes.txt", `endpoint=${["http:/", "alice:credential@192.168.1.5", "admin"].join("/")}`, "url:non-public", ["http:/", "alice:credential@192.168.1.5", "admin"].join("/")],
  ["backslash authority URL", "notes.txt", `endpoint=${["http:/", "127.0.0.1\\@public.com", "admin"].join("/")}`, "url:non-public", ["http:/", "127.0.0.1\\@public.com", "admin"].join("/")],
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

const punctuatedPrivateUrls = [
  ["parenthesized private hostname", "notes.txt", ["http:/", "service.internal"].join("/"), (url) => "(" + url + ")."],
  ["parenthesized private IPv4", "notes.txt", ["http:/", "192.168.1.5"].join("/"), (url) => "(" + url + ")."],
  ["localhost with closing punctuation", "notes.txt", ["http:/", "localhost"].join("/"), (url) => url + ")."],
  ["Markdown link to private hostname", "notes.md", ["http:/", "service.internal"].join("/"), (url) => "[target](" + url + ")"],
  ["Markdown link to private IPv6", "notes.md", ["http:/", "[::1]"].join("/"), (url) => "[target](" + url + ")."],
  ["private hostname with userinfo", "notes.md", ["http:/", "guest:credential@service.internal"].join("/"), (url) => "[target](" + url + ")"],
  ["private hostname with parenthesis in userinfo", "notes.md", ["http:/", "guest)@service.internal"].join("/"), (url) => "[target](" + url + ")"],
  ["private IPv4 with deceptive userinfo", "notes.txt", ["http:/", "public.example@192.168.1.5"].join("/"), (url) => "(" + url + ")."],
  ["private hostname with templated port", "notes.md", ["http:/", "service.internal:" + ["$", "{PORT}"].join("")].join("/"), (url) => "[target](" + url + ")"],
  ["private hostname with trailing comma", "notes.txt", ["http:/", "service.internal"].join("/"), (url) => url + ","],
  ["private IPv4 with trailing comma", "notes.txt", ["http:/", "192.168.1.5"].join("/"), (url) => url + ","],
  ["localhost with trailing exclamation", "notes.txt", ["http:/", "localhost"].join("/"), (url) => url + "!"],
  ["bracket-wrapped private hostname", "notes.md", ["http:/", "service.internal"].join("/"), (url) => "[" + url + "]"],
  ["private hostname and port with trailing comma", "notes.txt", ["https:/", "service.internal:8080"].join("/"), (url) => url + ","],
  ["bare private IPv6", "notes.txt", ["http:/", "[::1]"].join("/"), (url) => url],
  ["private IPv6 with trailing comma", "notes.txt", ["http:/", "[::1]"].join("/"), (url) => url + ","],
  ["bracket-wrapped private IPv6", "notes.md", ["http:/", "[::1]"].join("/"), (url) => "[" + url + "]"],
  ["bracket-wrapped private IPv6 and port", "notes.md", ["http:/", "[::1]:8080"].join("/"), (url) => "[" + url + "]."],
  ["bracket-wrapped private IPv6 with userinfo", "notes.md", ["http:/", "guest@[::1]"].join("/"), (url) => "[" + url + "]"],
  ["bracket-wrapped private host with bracket in userinfo", "notes.md", ["http:/", "guest[@service.internal"].join("/"), (url) => "[" + url + "]"],
  ["private hostname with userinfo and comma", "notes.txt", ["http:/", "guest@service.internal"].join("/"), (url) => url + ","],
];

for (const [label, name, privateUrl, wrap] of punctuatedPrivateUrls) {
  test("reports " + label + " without exposing the URL", async () => {
    const result = await runFiles([[name, wrap(privateUrl)]]);
    assert.equal(result.status, 1, result.stderr);
    assert.match(result.stdout, /:url:non-public$/m);
    assert.equal(result.stdout.includes(privateUrl), false);
    assert.equal(result.stderr.includes(privateUrl), false);
  });
}

test("allows punctuated public hosts even when they resemble private URLs", async () => {
  const publicUrls = [
    ["https:/", "service.internal.example"].join("/"),
    ["http:/", "localhost.example"].join("/"),
    ["https:/", "service.internal@public.example"].join("/"),
    ["https:/", "guest)@public.example"].join("/"),
    ["https:/", "guest[@public.example"].join("/"),
    ["https:/", "[2001:db8::1]"].join("/"),
    ["https:/", "public.example", "path(with)parentheses"].join("/"),
  ];
  const result = await runFiles([["notes.md", publicUrls.map((url) => "[target](" + url + ").").join("\n")]]);
  assert.equal(result.status, 0, result.stderr);
});

test("controlled loopback exception rejects punctuated URLs with userinfo", async () => {
  const approvedPath = "plugins/agentic-engineering-skills/skills/brainstorming/visual-companion.md";
  const privateUrl = ["http:/", "guest@localhost"].join("/");
  const result = await runRepositoryFiles([[approvedPath, "[target](" + privateUrl + ")."]]);
  assert.equal(result.status, 1, result.stderr);
  assert.match(result.stdout, /visual-companion\.md:url:non-public$/m);
  assert.equal(result.stdout.includes(privateUrl), false);
  assert.equal(result.stderr.includes(privateUrl), false);
});

const serializedWindowsPaths = [
  ["JSON Windows home", ["C:", "Users", "example", "private", "repo"].join("\\")],
  ["JSON Windows home user root", ["E:", "USERS", "example"].join("\\")],
  ["JSON Windows home with mixed separators", ["D:", "users"].join("\\") + "/example\\private/repo"],
  ["JSON Windows home with repeated forward slashes", ["F:", "Users", "example", "private"].join("//")],
];

for (const [label, privatePath] of serializedWindowsPaths) {
  test("reports " + label + " without exposing matched content", async () => {
    const content = JSON.stringify({ source: privatePath });
    const serializedPath = JSON.stringify(privatePath).slice(1, -1);
    const result = await runFiles([["notes.json", content]]);
    assert.equal(result.status, 1, result.stderr);
    assert.match(result.stdout, /:private-path:windows-home$/m);
    assert.equal(result.stdout.includes(privatePath), false);
    assert.equal(result.stderr.includes(privatePath), false);
    assert.equal(result.stdout.includes(serializedPath), false);
    assert.equal(result.stderr.includes(serializedPath), false);
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

test("rejects a regular file reached through a linked ancestor", async (t) => {
  const base = await mkdtemp(path.join(tmpdir(), "public-audit-linked-ancestor-"));
  const repository = path.join(base, "repo");
  const outside = path.join(base, "outside");
  const outsideFile = path.join(outside, "secret.txt");
  const marker = "linked-ancestor-content-must-stay-private";
  await mkdir(repository, { recursive: true });
  await mkdir(outside, { recursive: true });
  await writeFile(outsideFile, `${marker}\n`);
  try {
    await symlink(outside, path.join(repository, "linked"), process.platform === "win32" ? "junction" : "dir");
  } catch (error) {
    if (["EPERM", "EACCES", "ENOTSUP"].includes(error?.code)) {
      t.skip(`directory symlink unavailable: ${error.code}`);
      return;
    }
    throw error;
  }

  const listPath = path.join(base, "files.json");
  await writeFile(listPath, JSON.stringify([path.join(repository, "linked", "secret.txt")]));
  const result = runAudit(["--test-file-list", listPath], { cwd: repository });
  assert.equal(result.status, 2, `${result.stdout}\n${result.stderr}`);
  assert.match(result.stderr, /escapes trusted root through a linked ancestor/);
  assert.equal(result.stdout.includes(marker), false);
  assert.equal(result.stderr.includes(marker), false);
});

test("scans complete chunked patch content across chunk boundaries", async () => {
  const directory = await mkdtemp(path.join(tmpdir(), "public-audit-chunked-patch-"));
  const patchPath = path.join(directory, "manifests", "patches", "boundary.patch");
  await mkdir(path.dirname(patchPath), { recursive: true });
  const secret = ["sk", "proj", "boundarySecretValue"].join("-");
  const chunkSecret = ["sk", "proj", "chunkLocalSecretValue"].join("-");
  const diffPrefix = `diff --git a/boundary.txt b/boundary.txt\n+${chunkSecret}\n+`;
  const prefix = `${diffPrefix}${"a".repeat(PATCH_CHUNK_BYTES - Buffer.byteLength(diffPrefix) - 4)}\n`;
  const patchBytes = Buffer.from(`${prefix}${secret}\n`, "utf8");
  assert.equal(patchBytes.subarray(PATCH_CHUNK_BYTES - 3, PATCH_CHUNK_BYTES).toString("utf8"), "sk-");
  await writePatchBundle(patchPath, patchBytes, directory);
  const bundlePaths = await listPatchBundlePaths(patchPath, directory);
  const listPath = path.join(directory, "files.json");
  await writeFile(listPath, JSON.stringify(bundlePaths));

  const result = runAudit(["--test-file-list", listPath], { cwd: directory });
  assert.equal(result.status, 1, result.stderr);
  assert.match(result.stdout, /boundary\.patch:secret:openai-project-key$/m);
  assert.doesNotMatch(result.stdout, /boundary\.patch:patch:untracked-chunk$/m);
  assert.equal(result.stdout.includes(secret), false, result.stdout);
  assert.equal(result.stdout.includes(chunkSecret), false, result.stdout);
  assert.equal(result.stderr.includes(secret), false, result.stderr);

  const firstChunkListPath = path.join(directory, "first-chunk.json");
  await writeFile(firstChunkListPath, JSON.stringify([bundlePaths[1]]));
  const firstChunk = runAudit(["--test-file-list", firstChunkListPath], { cwd: directory });
  assert.equal(firstChunk.status, 2, firstChunk.stderr);
  assert.match(firstChunk.stderr, /patch chunk has no validated pointer/);
  assert.equal(firstChunk.stdout.includes(chunkSecret), false, firstChunk.stdout);

  const incompleteListPath = path.join(directory, "incomplete-files.json");
  await writeFile(incompleteListPath, JSON.stringify([patchPath]));
  const incomplete = runAudit(["--test-file-list", incompleteListPath], { cwd: directory });
  assert.equal(incomplete.status, 1, incomplete.stderr);
  assert.match(incomplete.stdout, /boundary\.patch:patch:untracked-chunk$/m);
  assert.match(incomplete.stdout, /boundary\.patch:secret:openai-project-key$/m);

  const pointerBytes = await readFile(patchPath);
  await writeFile(patchPath, Buffer.concat([Buffer.from("X"), pointerBytes.subarray(1)]));
  const malformedPointer = runAudit(["--test-file-list", listPath], { cwd: directory });
  assert.equal(malformedPointer.status, 2);
  assert.match(malformedPointer.stderr, /invalid patch artifact header/);
  await writeFile(patchPath, pointerBytes);

  await writeFile(bundlePaths[1], "tampered chunk");
  const tampered = runAudit(["--test-file-list", listPath], { cwd: directory });
  assert.equal(tampered.status, 2);
  assert.match(tampered.stderr, /patch chunk (?:length|SHA-256) mismatch/i);
  assert.equal(tampered.stderr.includes(secret), false);

  await unlink(bundlePaths[1]);
  const missing = runAudit(["--test-file-list", listPath], { cwd: directory });
  assert.equal(missing.status, 2);
  assert.match(missing.stderr, /ENOENT|missing/i);
  assert.equal(missing.stderr.includes(secret), false);
});

test("fails closed on patch chunks missing their validated pointer", async () => {
  const secret = ["sk", "proj", "orphanBoundarySecret"].join("-");
  const prefix = `diff --git a/orphan.txt b/orphan.txt\n+${"x".repeat(PATCH_CHUNK_BYTES - Buffer.byteLength("diff --git a/orphan.txt b/orphan.txt\n+") - 2)}`;
  const bundle = await createChunkedPatch("orphan.patch", `${prefix}${secret}\n`);
  const orphanChunks = bundle.paths.slice(1);
  const result = await bundle.run(orphanChunks);
  assert.equal(result.status, 2, `${result.stdout}\n${result.stderr}`);
  assert.match(result.stderr, /no validated pointer/);
  assert.equal(result.stdout.includes(secret), false);
  assert.equal(result.stderr.includes(secret), false);
});

const testFixturePort = ["$", "{server.address().port}"].join("");
const testFixtureUrl = ["http:/", "127.0.0.1:" + testFixturePort].join("/");
const agentTestUrls = [
  ["tests/impeccable-agent-discovery.test.mjs", [testFixtureUrl, testFixtureUrl + "/v1"]],
  ["tests/impeccable-agent-mcp.test.mjs", [testFixtureUrl]],
];

for (const [fixturePath, expectedUrls] of agentTestUrls) {
  const fixture = (urls) => urls.map((url) => '"' + url + '"').join("\n");

  test("allows the exact test server endpoints in " + fixturePath, async () => {
    const result = await runRepositoryFiles([[fixturePath, fixture(expectedUrls)]]);
    assert.equal(result.status, 0, result.stderr);
  });

  const replacements = [
    ["a different private host", ["http:/", "service.internal"].join("/")],
    ["a different loopback address", ["http:/", "127.0.0.2:" + testFixturePort].join("/")],
    ["a different port expression", ["http:/", "127.0.0.1:" + ["$", "{otherPort}"].join("")].join("/")],
    ["userinfo", ["http:/", "guest@127.0.0.1:" + testFixturePort].join("/")],
    ["a different endpoint path", testFixtureUrl + "/admin"],
  ];

  for (const [label, replacement] of replacements) {
    test("rejects " + label + " in " + fixturePath, async () => {
      const result = await runRepositoryFiles([[fixturePath, fixture([replacement, ...expectedUrls.slice(1)])]]);
      assert.equal(result.status, 1, result.stderr);
      assert.match(result.stdout, /:url:non-public$/m);
      assert.equal(result.stdout.includes(replacement), false);
      assert.equal(result.stderr.includes(replacement), false);
    });
  }

  test("rejects an extra private URL in " + fixturePath, async () => {
    const privateUrl = ["http:/", "service.internal"].join("/");
    const result = await runRepositoryFiles([[fixturePath, fixture([...expectedUrls, privateUrl])]]);
    assert.equal(result.status, 1, result.stderr);
    assert.match(result.stdout, /:url:non-public$/m);
    assert.equal(result.stdout.includes(privateUrl), false);
    assert.equal(result.stderr.includes(privateUrl), false);
  });
}

test("does not allow test server endpoints in unrelated files", async () => {
  const result = await runRepositoryFiles([["tests/unrelated.test.mjs", '"' + testFixtureUrl + '"']]);
  assert.equal(result.status, 1, result.stderr);
  assert.match(result.stdout, /:url:non-public$/m);
  assert.equal(result.stdout.includes(testFixtureUrl), false);
  assert.equal(result.stderr.includes(testFixtureUrl), false);
});

test("allows only counted loopback URLs in approved copied artifacts", async () => {
  const approvedPath = "plugins/agentic-engineering-skills/skills/brainstorming/visual-companion.md";
  const loopbackUrl = ["http:/", "localhost:52341"].join("/");
  const privateUrl = ["http:/", "service.internal"].join("/");
  const deceptivePrivateUrl = ["http:/", "localhost.attacker.internal"].join("/");
  const allowed = await runRepositoryFiles([[approvedPath, `Example: "${loopbackUrl}/"\n`]]);
  assert.equal(allowed.status, 0, `${allowed.stdout}\n${allowed.stderr}`);

  const withPrivateHost = await runRepositoryFiles([[
    approvedPath,
    `Example: "${loopbackUrl}/" and "${privateUrl}/"\n`,
  ]]);
  assert.equal(withPrivateHost.status, 1, withPrivateHost.stderr);
  assert.match(withPrivateHost.stdout, /visual-companion\.md:url:non-public$/m);

  const privateOnly = await runRepositoryFiles([[
    approvedPath,
    `Example: "${deceptivePrivateUrl}/"\n`,
  ]]);
  assert.equal(privateOnly.status, 1, privateOnly.stderr);
  assert.match(privateOnly.stdout, /visual-companion\.md:url:non-public$/m);
});

test("patch URL exception keeps both expected count and loopback pattern", async () => {
  const patchPath = "manifests/patches/impeccable.patch";
  const loopbackUrl = ["http:/", "localhost:8400"].join("/");
  const urls = Array.from({ length: 18 }, () => `${loopbackUrl}/`);
  const patch = (values) => `diff --git a/example.txt b/example.txt\n+${values.join("\n+")}\n`;
  const allowed = await runRepositoryFiles([[patchPath, patch(urls)]]);
  assert.equal(allowed.status, 0, `${allowed.stdout}\n${allowed.stderr}`);

  urls[0] = ["https:/", "service.internal"].join("/");
  const withPrivateUrl = await runRepositoryFiles([[patchPath, patch(urls)]]);
  assert.equal(withPrivateUrl.status, 1, withPrivateUrl.stderr);
  assert.match(withPrivateUrl.stdout, /impeccable\.patch:url:non-public$/m);
});

test("removed E2E payload no longer receives private-URL audit exceptions", async () => {
  const removedPath = "plugins/agentic-engineering-skills/skills/orientated-e2e-testing-v5-2/tests/unit/test_adapter_manifest.py";
  const fixture = ["http:/", "[::1]:8000", "health"].join("/");
  const result = await runRepositoryFiles([[removedPath, fixture]]);
  assert.equal(result.status, 1, result.stderr);
  assert.match(result.stdout, /test_adapter_manifest\.py:url:non-public$/m);
});

test("allows exact deleted Archify example only while added private URLs still fail", async () => {
  const patchPath = "manifests/patches/archify.patch";
  const section = "diff --git a/archify/references/authoring-contract.md b/archify/references/authoring-contract.md";
  const removedExample = ["http:/", "git.internal:3000", "Platform", "Services", 'service",'].join("/");
  const addedPrivate = ["http:/", "service.internal", "new-endpoint"].join("/");
  const patch = (sign, url) => `${section}\n${sign}  "url": "${url}\n`;
  const removed = await runRepositoryFiles([[patchPath, patch("-", removedExample)]]);
  assert.equal(removed.status, 0, `${removed.stdout}\n${removed.stderr}`);

  const added = await runRepositoryFiles([[patchPath, patch("+", removedExample)]]);
  assert.equal(added.status, 1, added.stderr);
  assert.match(added.stdout, /archify\.patch:url:non-public$/m);

  const changed = await runRepositoryFiles([[patchPath, patch("-", addedPrivate)]]);
  assert.equal(changed.status, 1, changed.stderr);
  assert.match(changed.stdout, /archify\.patch:url:non-public$/m);
});

test("chunk URL exceptions require complete parent policy and reject private host variants", async () => {
  const patchPath = "manifests/patches/impeccable.patch";
  const loopbackUrl = ["http:/", "localhost:8400"].join("/");
  const privateUrl = ["http:/", "service.internal"].join("/");
  const urls = Array.from({ length: 18 }, () => `${loopbackUrl}/`);
  const patchText = (values) => `diff --git a/example.txt b/example.txt\n+${values.join("\n+")}\n+${"x".repeat(PATCH_CHUNK_BYTES)}\n`;
  const bundle = await createChunkedPatch(patchPath, patchText(urls));
  assert.ok(bundle.paths.length > 2);
  const allowed = await bundle.run();
  assert.equal(allowed.status, 0, `${allowed.stdout}\n${allowed.stderr}`);

  const incomplete = await bundle.run(bundle.paths.slice(0, 2));
  assert.equal(incomplete.status, 2, incomplete.stderr);
  assert.match(incomplete.stderr, /patch chunk has no validated pointer/);

  for (const host of [privateUrl, ["http:/", "localhost.attacker.internal"].join("/")]) {
    const unsafeUrls = [...urls];
    unsafeUrls[0] = `${host}/`;
    const unsafe = await createChunkedPatch(patchPath, patchText(unsafeUrls));
    const result = await unsafe.run();
    assert.equal(result.status, 1, result.stderr);
    assert.match(result.stdout, /impeccable\.patch:url:non-public$/m);
    assert.match(result.stdout, /000001\.txt:url:non-public$/m);
  }
});

test("chunk fixture exception inherits only exact reconstructed UI-UX sample", async () => {
  const patchPath = "manifests/patches/ui-ux-pro-max.patch";
  const loopbackUrl = ["http:/", "localhost:8080"].join("/");
  const samplePath = ["C:", "Users", "data", "config.json"].join("\\");
  const makePatch = (windowsPath) => {
    const lead = `diff --git a/avalonia.csv b/avalonia.csv\n+${loopbackUrl}\n+row,`;
    const prefix = `${lead}${"x".repeat(PATCH_CHUNK_BYTES - Buffer.byteLength(lead) - 3)}@""`;
    assert.equal(Buffer.byteLength(prefix), PATCH_CHUNK_BYTES);
    return `${prefix}${windowsPath}""",Medium\n`;
  };

  const allowed = await createChunkedPatch(patchPath, makePatch(samplePath));
  const result = await allowed.run();
  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);

  const changed = ["C:", "Users", "data", "private.json"].join("\\");
  const altered = await createChunkedPatch(patchPath, makePatch(changed));
  const alteredResult = await altered.run();
  assert.equal(alteredResult.status, 1, alteredResult.stderr);
  assert.match(alteredResult.stdout, /ui-ux-pro-max\.patch:private-path:windows-home$/m);
  assert.match(alteredResult.stdout, /000002\.txt:private-path:windows-home$/m);
});

test("allows exact synthetic fixture path without masking real Linux home paths", async () => {
  const fixturePath = "plugins/agentic-engineering-skills/skills/marketing-screenshots/tests/marketing-screenshots.test.mjs";
  const syntheticAsset = ["/tmp/assets", "home", "home--raw.png"].join("/");
  const fixture = `outputs: { raw: '${syntheticAsset}' }\n`;
  const allowed = await runRepositoryFiles([[fixturePath, fixture]]);
  assert.equal(allowed.status, 0, `${allowed.stdout}\n${allowed.stderr}`);

  const privateHome = ["", "home", "alice", "private", "repo"].join("/");
  const withHomePath = await runRepositoryFiles([[fixturePath, `${fixture}source=${privateHome}\n`]]);
  assert.equal(withHomePath.status, 1, withHomePath.stderr);
  assert.match(withHomePath.stdout, /marketing-screenshots\.test\.mjs:private-path:linux-home$/m);
});

test("allows only exact synthetic Windows path in the pinned data patch", async () => {
  const patchPath = "manifests/patches/ui-ux-pro-max.patch";
  const samplePath = ["C:", "Users", "data", "config.json"].join("\\");
  const csvRow = (filePath) => `diff --git a/avalonia.csv b/avalonia.csv\n+row,"@""${filePath}""",Medium\n`;
  const allowed = await runRepositoryFiles([[patchPath, csvRow(samplePath)]]);
  assert.equal(allowed.status, 0, `${allowed.stdout}\n${allowed.stderr}`);

  for (const path of [
    ["C:", "Users", "data", "private.json"].join("\\"),
    ["C:", "Users", "alice", "secrets.json"].join("\\"),
    ["C:", "Users", "alice,senior", "secrets.json"].join("\\"),
  ]) {
    const result = await runRepositoryFiles([[patchPath, csvRow(path)]]);
    assert.equal(result.status, 1, result.stderr);
    assert.match(result.stdout, /ui-ux-pro-max\.patch:private-path:windows-home$/m);
  }
});

test("does not flag paths outside a Windows user home", async () => {
  const safePaths = [
    ["C:", "Users"].join("/") + "/",
    ["C:", "UsersPublic", "example", "data"].join("/"),
    ["C:", "work", "example"].join("/"),
    ["Users", "example"].join("/"),
    ["C:", "UsersPublic", "example"].join("\\\\"),
    ["C:", "Users"].join("\\\\") + "\\\\",
  ];
  const result = await runFiles([["notes.txt", safePaths.join("\n")]]);
  assert.equal(result.status, 0, result.stderr);
});

test("synthetic Windows fixture cannot mask additional Windows paths", async () => {
  const patchPath = "manifests/patches/ui-ux-pro-max.patch";
  const samplePath = ["C:", "Users", "data", "config.json"].join("\\");
  const csvRow = (filePath) => `diff --git a/avalonia.csv b/avalonia.csv\n+row,"@""${filePath}""",Medium\n`;
  for (const privatePath of [
    ["C:", "Users", "data", "config.json"].join("/"),
    ["D:", "users", "example"].join("/") + "\\private.json",
    JSON.stringify(["F:", "Users", "example", "private.json"].join("\\")).slice(1, -1),
  ]) {
    const result = await runRepositoryFiles([[patchPath, csvRow(samplePath) + csvRow(privatePath)]]);
    assert.equal(result.status, 1, result.stderr);
    assert.match(result.stdout, /ui-ux-pro-max\.patch:private-path:windows-home$/m);
    assert.equal(result.stdout.includes(privatePath), false);
    assert.equal(result.stderr.includes(privatePath), false);
  }
});

test("never exempts secret-shaped content from copied third-party paths", async () => {
  const secret = ["sk", "ant", "syntheticNeverAllow"].join("-");
  const path = "plugins/agentic-engineering-skills/skills/impeccable/scripts/live-copy-edit-agent.mjs";
  const result = await runRepositoryFiles([[path, `TOKEN=${secret}\n`]]);
  assert.equal(result.status, 1, result.stderr);
  assert.match(result.stdout, /live-copy-edit-agent\.mjs:secret:anthropic-key$/m);
  assert.equal(result.stdout.includes(secret), false, result.stdout);
  assert.equal(result.stderr.includes(secret), false, result.stderr);
});

test("accepts clean fixture", async () => {
  const directory = await mkdtemp(path.join(tmpdir(), "public-audit-clean-"));
  const list = path.join(directory, "files.json");
  await writeFile(list, JSON.stringify([cleanFixture]));
  const result = runAudit(["--test-file-list", list]);
  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
});

test("does not flag public internet URLs", async () => {
  const url = ["https:/", "docs.example.com", "guide"].join("/");
  const result = await runFiles([["notes.txt", `See ${url}.\n`]]);
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
