import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdtemp, mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join, relative } from "node:path";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { hashPayloadTree } from "../scripts/lib/native-receipt.mjs";
import { sha256Path } from "../scripts/lib/hash.mjs";
import { listPatchBundlePaths, loadPatchBytes } from "../scripts/lib/manifest.mjs";

const execFileAsync = promisify(execFile);
const payloadRoot = new URL("../plugins/agentic-engineering-skills/skills/", import.meta.url);

test("native plugin component bytes survive autocrlf checkouts", async (t) => {
  for (const sampleRoot of ["plugins/agentic-engineering-skills/skills", "plugins/agentic-engineering-skills/claude-skills", "plugins/agentic-engineering-skills/.claude-plugin", "plugins/agentic-engineering-skills/.codex-plugin", "plugins/agentic-engineering-skills/agents", "plugins/agentic-engineering-skills/hooks", "plugins/agentic-engineering-skills/licenses"]) {
  const tempRoot = await mkdtemp(join(tmpdir(), "skill-payload-eol-"));
  t.after(() => rm(tempRoot, { recursive: true, force: true }));

  const samples = await findEolSamples(new URL(`../${sampleRoot}/`, import.meta.url));
  assert.ok(samples.lf, "expected an LF payload file");
  samples.crlf ??= { path: "byte-fixture/CRLF.md", bytes: Buffer.from(samples.lf.bytes.toString("utf8").replace(/\n/g, "\r\n")) };

  const repo = join(tempRoot, "repo");
  await mkdir(repo);
  await git(repo, "init", "-q");
  await git(repo, "config", "user.name", "EOL test");
  await git(repo, "config", "user.email", "eol-test@example.invalid");
  await git(repo, "config", "core.autocrlf", "false");

  for (const sample of [samples.crlf, samples.lf]) {
    const target = join(repo, sampleRoot, sample.path);
    await mkdir(dirname(target), { recursive: true });
    await writeFile(target, sample.bytes);
  }
  const attrs = join(repo, ".gitattributes");
  await writeFile(attrs, await readFile(fileURLToPath(new URL("../.gitattributes", import.meta.url))));
  const fixtureRoot = join(repo, sampleRoot);
  const expectedBytes = new Map([
    [samples.crlf.path, samples.crlf.bytes],
    [samples.lf.path, samples.lf.bytes],
  ]);
  const expectedTreeHash = await hashPayloadTree(fixtureRoot);
  const expectedPathHash = await sha256Path(fixtureRoot);

  await git(repo, "add", ".gitattributes", sampleRoot);
  await git(repo, "commit", "-qm", "fixture");

  for (const autocrlf of ["true", "false"]) {
    const clone = join(tempRoot, `clone-${autocrlf}`);
    await git(tempRoot, "clone", "-q", repo, clone);
    await git(clone, "config", "core.autocrlf", autocrlf);
    await git(clone, "checkout", "-qf", "HEAD");
    for (const [path, bytes] of expectedBytes) {
      assert.deepEqual(await readFile(join(clone, sampleRoot, path)), bytes, `${path} bytes with core.autocrlf=${autocrlf}`);
      assert.equal(await git(clone, "show", `HEAD:${sampleRoot}/${path}`, { encoding: "buffer" }).then(({ stdout }) => stdout.equals(bytes)), true, `${path} object bytes`);
      assert.equal((await git(clone, "check-attr", "text", "--", `${sampleRoot}/${path}`)).stdout.trim(), `${sampleRoot}/${path}: text: unset`);
    }
    assert.equal(await hashPayloadTree(join(clone, sampleRoot)), expectedTreeHash, `native receipt hash with core.autocrlf=${autocrlf}`);
    assert.equal(await sha256Path(join(clone, sampleRoot)), expectedPathHash, `sha256Path with core.autocrlf=${autocrlf}`);
  }
  }
});

async function findEolSamples(rootUrl) {
  const root = fileURLToPath(rootUrl);
  const files = await walk(root);
  let crlf;
  let crlfFixture;
  let lf;
  for (const path of files) {
    const bytes = await readFile(path);
    if (bytes.includes(Buffer.from("\r\n"))) {
      const sample = { path: relative(root, path).replaceAll("\\", "/"), bytes };
      if (!crlf) crlf = sample;
      if (!crlfFixture && sample.path.includes("/fixtures/")) crlfFixture = sample;
    }
    if (!lf && bytes.includes(Buffer.from("\n")) && !bytes.includes(Buffer.from("\r\n"))) lf = { path: relative(root, path).replaceAll("\\", "/"), bytes };
    if (lf && crlfFixture) return { crlf: crlfFixture, lf };
  }
  return { crlf, lf };
}

async function walk(directory) {
  const paths = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) paths.push(...await walk(path));
    else if (entry.isFile()) paths.push(path);
  }
  return paths.sort();
}

async function git(cwd, ...args) {
  const options = args.at(-1);
  const commandOptions = options && typeof options === "object" && !Array.isArray(options) ? args.pop() : {};
  return execFileAsync("git", args, { cwd, ...commandOptions });
}

test("chunked provenance patches survive autocrlf checkouts byte-for-byte", async t => {
  const sourceRoot = fileURLToPath(new URL("../", import.meta.url));
  const patch = join(sourceRoot, "manifests", "patches", "impeccable.patch");
  const expected = await loadPatchBytes(patch, sourceRoot);
  const artifacts = await listPatchBundlePaths(patch, sourceRoot);
  assert.ok(artifacts.length > 1, "expected a chunked provenance patch");
  const tempRoot = await mkdtemp(join(tmpdir(), "patch-payload-eol-"));
  t.after(() => rm(tempRoot, { recursive: true, force: true }));
  const repo = join(tempRoot, "repo"); await mkdir(repo);
  await git(repo, "init", "-q");
  await git(repo, "config", "user.name", "EOL test");
  await git(repo, "config", "user.email", "eol-test@example.invalid");
  await git(repo, "config", "core.autocrlf", "false");
  await writeFile(join(repo, ".gitattributes"), await readFile(join(sourceRoot, ".gitattributes")));
  for (const file of artifacts) {
    const destination = join(repo, relative(sourceRoot, file));
    await mkdir(dirname(destination), { recursive: true });
    await writeFile(destination, await readFile(file));
  }
  await git(repo, "add", ".gitattributes", "manifests/patches");
  await git(repo, "commit", "-qm", "fixture");
  for (const autocrlf of ["true", "false"]) {
    const clone = join(tempRoot, `clone-${autocrlf}`);
    await git(tempRoot, "clone", "-q", repo, clone);
    await git(clone, "config", "core.autocrlf", autocrlf);
    await git(clone, "checkout", "-qf", "HEAD");
    assert.deepEqual(await loadPatchBytes(join(clone, "manifests", "patches", "impeccable.patch"), clone), expected, `patch bytes with autocrlf=${autocrlf}`);
  }
});
