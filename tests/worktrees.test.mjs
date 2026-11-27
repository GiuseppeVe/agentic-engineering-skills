import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { classify, inventory, parseWorktreeList } from "../plugins/agentic-engineering-skills/skills/development-process/scripts/worktrees.mjs";

const script = fileURLToPath(new URL("../plugins/agentic-engineering-skills/skills/development-process/scripts/worktrees.mjs", import.meta.url));

test("classify never calls removable a worktree with local or unpublished work", () => {
  const base = { exists: true, dirty: 0, merged: false, prState: null, unpushed: 0 };
  assert.equal(classify({ ...base, exists: false }), "missing");
  assert.equal(classify({ ...base, merged: true }), "merged-clean");
  assert.equal(classify({ ...base, merged: true, dirty: 1 }), "dirty");
  assert.equal(classify({ ...base, prState: "MERGED" }), "merged-clean");
  assert.equal(classify({ ...base, prState: "MERGED", unpushed: 2 }), "unpublished");
  assert.equal(classify({ ...base, prState: "MERGED", unpushed: null }), "unpublished");
  assert.equal(classify({ ...base, prState: "CLOSED" }), "closed-clean");
  assert.equal(classify({ ...base, prState: "OPEN" }), "open-clean");
  assert.equal(classify({ ...base, unpushed: null }), "unpublished");
});

test("parseWorktreeList reads branches and detached heads", () => {
  const rows = parseWorktreeList("worktree /r\nHEAD aaa\nbranch refs/heads/main\n\nworktree /r/w\nHEAD bbb\ndetached\n");
  assert.deepEqual(rows, [{ path: "/r", head: "aaa", branch: "main" }, { path: "/r/w", head: "bbb", branch: null }]);
});

test("--remove-merged removes only merged clean worktrees and keeps their branches", () => {
  const root = mkdtempSync(join(tmpdir(), "worktrees-test-"));
  const git = (cwd, ...args) => execFileSync("git", ["-C", cwd, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false", ...args], { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] });
  try {
    const repo = join(root, "repo");
    execFileSync("git", ["init", "-q", "-b", "main", repo]);
    writeFileSync(join(repo, "a.txt"), "a\n");
    git(repo, "add", "a.txt");
    git(repo, "commit", "-q", "-m", "init");
    const merged = join(root, "merged"), dirty = join(root, "dirty"), ahead = join(root, "ahead");
    git(repo, "worktree", "add", "-q", "-b", "merged", merged);
    git(repo, "worktree", "add", "-q", "-b", "dirty", dirty);
    writeFileSync(join(dirty, "b.txt"), "b\n");
    git(repo, "worktree", "add", "-q", "-b", "ahead", ahead);
    writeFileSync(join(ahead, "c.txt"), "c\n");
    git(ahead, "add", "c.txt");
    git(ahead, "commit", "-q", "-m", "ahead");

    const before = Object.fromEntries(inventory(repo, "main").rows.map(row => [row.branch, row.class]));
    assert.deepEqual(before, { merged: "merged-clean", ahead: "unpublished", dirty: "dirty" });

    const refused = spawnSync(process.execPath, [script, "--repo", repo, "--base", "main", "--remove-merged"], { encoding: "utf8" });
    assert.equal(refused.status, 2);
    assert.match(refused.stdout, /3 linked worktree/);
    assert.ok(existsSync(merged), "without --yes nothing is removed");
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("--remove-merged --yes leaves dirty and unpublished worktrees", () => {
  const root = mkdtempSync(join(tmpdir(), "worktrees-test-"));
  const git = (cwd, ...args) => execFileSync("git", ["-C", cwd, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false", ...args], { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] });
  try {
    const repo = join(root, "repo");
    execFileSync("git", ["init", "-q", "-b", "main", repo]);
    writeFileSync(join(repo, "a.txt"), "a\n");
    git(repo, "add", "a.txt");
    git(repo, "commit", "-q", "-m", "init");
    const merged = join(root, "merged"), dirty = join(root, "dirty");
    git(repo, "worktree", "add", "-q", "-b", "merged", merged);
    git(repo, "worktree", "add", "-q", "-b", "dirty", dirty);
    writeFileSync(join(dirty, "b.txt"), "b\n");
    execFileSync(process.execPath, [script, "--repo", repo, "--base", "main", "--remove-merged", "--yes"], { stdio: "ignore" });
    assert.equal(existsSync(merged), false);
    assert.ok(existsSync(dirty));
    assert.match(git(repo, "branch", "--list", "merged"), /merged/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
