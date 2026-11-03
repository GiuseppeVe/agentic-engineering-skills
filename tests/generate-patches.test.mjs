import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, writeFile, cp, rm, chmod } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { generatePatch } from "../scripts/generate-patches.mjs";
import { loadPatchBytes, writePatchBundle } from "../scripts/lib/manifest.mjs";
const exec = promisify(execFile);

test("directory patch captures every change and reconstructs the payload", async () => {
  const dir = await mkdtemp(join(tmpdir(), "patch-test-"));
  try {
    const old = join(dir, "old"), next = join(dir, "next"), apply = join(dir, "apply");
    await Promise.all([mkdir(old), mkdir(next), mkdir(apply)]);
    await Promise.all([
      writeFile(join(old, "SKILL.md"), "old\r\n"),
      writeFile(join(old, "removed.md"), "removed\n"),
      writeFile(join(old, "reference.md"), "old reference\n"),
      writeFile(join(next, "SKILL.md"), "new\n"),
      writeFile(join(next, "reference.md"), "updated reference\n"),
      writeFile(join(next, "new file.md"), "added\n"),
      writeFile(join(next, "binary.dat"), Buffer.from([0, 255, 13, 10, 1])),
    ]);
    const options = { name: "fixture", upstream: old, local: next, directory: true };
    const patch = await generatePatch(options);
    assert.equal(await generatePatch(options), patch);
    for (const name of ["SKILL.md", "reference.md", "removed.md", "new file.md", "binary.dat"]) assert.ok(patch.includes(name), name);
    // Git applies patches to LF-normalized upstream files.
    await cp(old, join(apply, "fixture"), { recursive: true });
    await writeFile(join(apply, "fixture", "SKILL.md"), "old\n");
    const patchFile = join(dir, "changes.patch");
    await writeFile(patchFile, patch);
    await exec("git", ["-c", "core.autocrlf=false", "apply", "--binary", "--unidiff-zero", "-p1", patchFile], { cwd: apply });
    for (const name of ["SKILL.md", "reference.md", "new file.md", "binary.dat"]) assert.deepEqual(await readFile(join(apply, "fixture", name)), await readFile(join(next, name)));
    await assert.rejects(readFile(join(apply, "fixture", "removed.md")), { code: "ENOENT" });
  } finally { await rm(dir, { recursive: true, force: true }); }
});

test("single-file adaptations and empty-patch rejection remain supported", async () => {
  const dir = await mkdtemp(join(tmpdir(), "patch-test-"));
  try {
    const old = join(dir, "old.md"), next = join(dir, "next.md");
    await writeFile(old, "a\r\n");
    await writeFile(next, "b\n");
    const options = { name: "fixture", upstream: old, local: next, directory: false };
    const patch = await generatePatch(options);
    assert.match(patch, /a\/fixture\/SKILL\.md/);
    assert.match(patch, /b\/fixture\/SKILL\.md/);
    await writeFile(next, "a\n");
    await assert.rejects(generatePatch(options), /empty patch/);
  } finally { await rm(dir, { recursive: true, force: true }); }
});

test("directory patch preserves executable modes from Git index and applies them", async () => {
  const dir = await mkdtemp(join(process.cwd(), ".patch-mode-test-"));
  try {
    const repo = join(dir, "repo"), old = join(repo, "old"), next = join(repo, "next");
    const apply = join(dir, "apply");
    await Promise.all([
      mkdir(join(old, "fixture"), { recursive: true }),
      mkdir(join(next, "fixture"), { recursive: true }),
      mkdir(apply),
    ]);
    await Promise.all([
      writeFile(join(old, "fixture", "upstream.sh"), "#!/bin/sh\necho old\n"),
      writeFile(join(next, "fixture", "upstream.sh"), "#!/bin/sh\necho new\n"),
      writeFile(join(next, "fixture", "new-script.sh"), "#!/bin/sh\necho added\n"),
      writeFile(join(old, "fixture", "mode-change.sh"), "#!/bin/sh\necho old mode\n"),
      writeFile(join(next, "fixture", "mode-change.sh"), "#!/bin/sh\necho executable now\n"),
      writeFile(join(old, "fixture", "ordinary.txt"), "old\n"),
      writeFile(join(next, "fixture", "ordinary.txt"), "new\n"),
    ]);
    await exec("git", ["init", "-q", repo]);
    // Make the Git index authoritative even on POSIX filesystems.
    await exec("git", ["-C", repo, "config", "core.filemode", "false"]);
    await exec("git", ["-C", repo, "add", "--", "old", "next"]);
    await exec("git", ["-C", repo, "update-index", "--chmod=+x", "--", "old/fixture/upstream.sh", "next/fixture/upstream.sh", "next/fixture/new-script.sh", "next/fixture/mode-change.sh"]);

    const patch = await generatePatch({ name: "fixture", upstream: join(old, "fixture"), local: join(next, "fixture"), directory: true });
    assert.match(patch, /new file mode 100755[\s\S]*new-script\.sh/);
    assert.match(patch, /old mode 100644\nnew mode 100755[\s\S]*mode-change\.sh/);
    assert.match(patch, /old mode 100644\nnew mode 100755\nindex [0-9a-f]+\.\.[0-9a-f]+\n/);
    assert.match(patch, /diff --git a\/fixture\/upstream\.sh b\/fixture\/upstream\.sh/);
    assert.match(patch, /diff --git a\/fixture\/upstream\.sh b\/fixture\/upstream\.sh\nindex [0-9a-f]+\.\.[0-9a-f]+ 100755\n/);

    await cp(join(old, "fixture"), join(apply, "fixture"), { recursive: true });
    // git apply --index requires the existing file to match its index mode.
    await chmod(join(apply, "fixture", "upstream.sh"), 0o755);
    await exec("git", ["init", "-q", apply]);
    await exec("git", ["-C", apply, "add", "--", "fixture"]);
    await exec("git", ["-C", apply, "update-index", "--chmod=+x", "--", "fixture/upstream.sh"]);
    const patchFile = join(dir, "modes.patch");
    await writeFile(patchFile, patch);
    await exec("git", ["-C", apply, "-c", "core.autocrlf=false", "apply", "--index", "--binary", "--unidiff-zero", "-p1", patchFile]);
    const { stdout } = await exec("git", ["-C", apply, "ls-files", "--stage", "-z"]);
    const index = new Map(stdout.split("\0").filter(Boolean).map(entry => {
      const [metadata, path] = entry.split("\t");
      return [path, metadata.split(" ")[0]];
    }));
    assert.equal(index.get("fixture/upstream.sh"), "100755");
    assert.equal(index.get("fixture/new-script.sh"), "100755");
    assert.equal(index.get("fixture/mode-change.sh"), "100755");
    assert.equal(index.get("fixture/ordinary.txt"), "100644");
    assert.equal(await readFile(join(apply, "fixture", "upstream.sh"), "utf8"), "#!/bin/sh\necho new\n");
  } finally { await rm(dir, { recursive: true, force: true }); }
});

test("mode-only staged executable change survives unchanged bytes and spaced path", async () => {
  const dir = await mkdtemp(join(process.cwd(), ".patch-mode-only-test-"));
  try {
    const repo = join(dir, "repo"), upstream = join(repo, "old"), local = join(repo, "next");
    const apply = join(dir, "apply"), file = "mode only.sh";
    await Promise.all([mkdir(join(upstream, "fixture"), { recursive: true }), mkdir(join(local, "fixture"), { recursive: true }), mkdir(apply)]);
    const contents = "#!/bin/sh\necho same\n";
    await Promise.all([
      writeFile(join(upstream, "fixture", file), contents),
      writeFile(join(local, "fixture", file), contents),
    ]);
    await exec("git", ["init", "-q", repo]);
    await exec("git", ["-C", repo, "config", "core.filemode", "false"]);
    await exec("git", ["-C", repo, "add", "--", "old", "next"]);
    await exec("git", ["-C", repo, "update-index", "--chmod=+x", "--", "next/fixture/mode only.sh"]);

    const patch = await generatePatch({ name: "fixture", upstream: join(upstream, "fixture"), local: join(local, "fixture"), directory: true });
    assert.match(patch, /diff --git a\/fixture\/mode only\.sh b\/fixture\/mode only\.sh\nold mode 100644\nnew mode 100755\n/);
    assert.doesNotMatch(patch, /@@/);

    await cp(join(upstream, "fixture"), join(apply, "fixture"), { recursive: true });
    await exec("git", ["init", "-q", apply]);
    await exec("git", ["-C", apply, "add", "--", "fixture"]);
    const patchFile = join(dir, "mode-only.patch");
    await writeFile(patchFile, patch);
    await exec("git", ["-C", apply, "-c", "core.autocrlf=false", "apply", "--index", "-p1", patchFile]);
    const { stdout } = await exec("git", ["-C", apply, "ls-files", "--stage", "-z"]);
    const entry = stdout.split("\0").find(value => value.endsWith("\tfixture/mode only.sh"));
    assert.equal(entry.split(" ")[0], "100755");
    assert.equal(await readFile(join(apply, "fixture", file), "utf8"), contents);
  } finally { await rm(dir, { recursive: true, force: true }); }
});

test("POSIX core.filemode=true honors unstaged executable-bit changes", { skip: process.platform === "win32" }, async () => {
  const dir = await mkdtemp(join(process.cwd(), ".patch-unstaged-mode-test-"));
  try {
    const repo = join(dir, "repo"), upstream = join(repo, "old"), local = join(repo, "next");
    await Promise.all([mkdir(join(upstream, "fixture"), { recursive: true }), mkdir(join(local, "fixture"), { recursive: true })]);
    const file = "unstaged.sh", contents = "#!/bin/sh\necho same\n";
    await Promise.all([
      writeFile(join(upstream, "fixture", file), contents),
      writeFile(join(local, "fixture", file), contents),
    ]);
    await exec("git", ["init", "-q", repo]);
    await exec("git", ["-C", repo, "config", "core.filemode", "true"]);
    await exec("git", ["-C", repo, "add", "--", "old", "next"]);
    await chmod(join(local, "fixture", file), 0o755);
    const { stdout: indexBefore } = await exec("git", ["-C", repo, "ls-files", "--stage", "--", "next/fixture/unstaged.sh"]);
    assert.match(indexBefore, /^100644 /);

    const patch = await generatePatch({ name: "fixture", upstream: join(upstream, "fixture"), local: join(local, "fixture"), directory: true });
    assert.match(patch, /old mode 100644\nnew mode 100755/);
  } finally { await rm(dir, { recursive: true, force: true }); }
});

test("large generated patch chunks stay bounded and recombine for git apply", async () => {
  const dir = await mkdtemp(join(tmpdir(), "patch-large-test-"));
  try {
    const old = join(dir, "old"), next = join(dir, "next"), apply = join(dir, "apply");
    await Promise.all([mkdir(old), mkdir(next), mkdir(apply)]);
    const contents = "line with UTF-8 💩 payload\n".repeat(60000);
    await writeFile(join(next, "large.txt"), contents);
    const patch = await generatePatch({ name: "fixture", upstream: old, local: next, directory: true });
    const patchBytes = Buffer.from(patch, "utf8");
    assert.ok(patchBytes.length > 900 * 1024);

    const patchPath = join(dir, "large.patch");
    await writePatchBundle(patchPath, patchBytes, dir);
    const reconstructed = await loadPatchBytes(patchPath, dir);
    assert.deepEqual(reconstructed, patchBytes);
    await writeFile(join(dir, "reconstructed.patch"), reconstructed);
    await exec("git", ["-c", "core.autocrlf=false", "apply", "--binary", "--unidiff-zero", "-p1", join(dir, "reconstructed.patch")], { cwd: apply });
    assert.deepEqual(await readFile(join(apply, "fixture", "large.txt")), Buffer.from(contents));
  } finally { await rm(dir, { recursive: true, force: true }); }
});
