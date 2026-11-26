#!/usr/bin/env node
// Inventory and cleanup of the linked worktrees of one repository, wherever they
// live on disk (inside the repository, in a harness directory, anywhere else).
//
//   node worktrees.mjs [--repo <path>] [--base origin/main] [--json]
//   node worktrees.mjs --remove-merged --yes [--repo <path>] [--base origin/main]
//
// The default is read-only. `--remove-merged --yes` removes only the worktrees of
// class `merged-clean` with `git worktree remove` (never --force), and runs
// `git worktree prune` for registrations whose folder is gone. It never deletes a
// branch, never touches a worktree with uncommitted or unpublished work, and never
// removes the main checkout. Run it on demand: nothing calls it automatically.
import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { parseArgs } from "node:util";
import { fileURLToPath } from "node:url";

export const CLASSES = ["missing", "merged-clean", "closed-clean", "open-clean", "unpublished", "dirty"];

// Pure: decides the class of one worktree from facts collected elsewhere.
//   exists     the folder is on disk
//   dirty      number of entries of `git status --porcelain`
//   merged     HEAD is an ancestor of the base
//   prState    "MERGED" | "CLOSED" | "OPEN" | null (PR of the branch, if any)
//   unpushed   commits of HEAD missing from the branch's remote; null without a remote branch
export function classify({ exists, dirty, merged, prState, unpushed }) {
  if (!exists) return "missing";
  if (dirty > 0) return "dirty";
  if (merged) return "merged-clean";
  if (prState === "MERGED" && unpushed === 0) return "merged-clean";
  if (unpushed === null || unpushed > 0) return "unpublished";
  if (prState === "CLOSED") return "closed-clean";
  return "open-clean";
}

// Pure: parses `git worktree list --porcelain`. The first entry is the main checkout.
export function parseWorktreeList(text) {
  return text.split(/\r?\n\r?\n/).map(block => block.trim()).filter(Boolean).map(block => {
    const entry = { path: null, head: null, branch: null };
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith("worktree ")) entry.path = line.slice(9);
      else if (line.startsWith("HEAD ")) entry.head = line.slice(5);
      else if (line.startsWith("branch ")) entry.branch = line.slice(7).replace(/^refs\/heads\//, "");
    }
    return entry;
  });
}

function git(cwd, ...args) {
  try {
    return execFileSync("git", ["-C", cwd, ...args], { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
  } catch {
    return null;
  }
}

function pullRequests(root) {
  try {
    const out = execFileSync("gh", ["pr", "list", "--state", "all", "--limit", "1000", "--json", "number,state,headRefName"], { cwd: root, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] });
    const byBranch = new Map();
    for (const pr of JSON.parse(out)) if (!byBranch.has(pr.headRefName)) byBranch.set(pr.headRefName, pr);
    return byBranch;
  } catch {
    return null;
  }
}

export function inventory(repo, base) {
  const listing = git(repo, "worktree", "list", "--porcelain");
  if (listing === null) throw new Error(`not a git repository: ${repo}`);
  const [main, ...linked] = parseWorktreeList(listing);
  const prs = pullRequests(main.path);
  const rows = linked.map(entry => {
    const exists = existsSync(entry.path);
    const dirty = exists ? (git(entry.path, "status", "--porcelain") ?? "").split("\n").filter(Boolean).length : 0;
    const merged = git(main.path, "merge-base", "--is-ancestor", entry.head, base) !== null;
    const remote = entry.branch && git(main.path, "rev-parse", "--verify", "-q", `refs/remotes/origin/${entry.branch}`);
    const unpushed = remote ? Number(git(main.path, "rev-list", "--count", `${remote}..${entry.head}`)) : null;
    const pr = entry.branch && prs ? prs.get(entry.branch) ?? null : null;
    return {
      class: classify({ exists, dirty, merged, prState: pr?.state ?? null, unpushed }),
      path: entry.path,
      branch: entry.branch ?? "(detached)",
      head: entry.head?.slice(0, 9) ?? null,
      lastCommit: git(main.path, "log", "-1", "--format=%cs", entry.head),
      dirty,
      unpushed,
      pr: pr ? `#${pr.number} ${pr.state}` : null,
    };
  });
  rows.sort((a, b) => CLASSES.indexOf(a.class) - CLASSES.indexOf(b.class) || a.path.localeCompare(b.path));
  return { main: main.path, base, pullRequestsRead: prs !== null, rows };
}

function main() {
  const { values } = parseArgs({
    options: {
      repo: { type: "string", default: process.cwd() },
      base: { type: "string", default: "origin/main" },
      json: { type: "boolean", default: false },
      "remove-merged": { type: "boolean", default: false },
      yes: { type: "boolean", default: false },
    },
  });
  const result = inventory(resolve(values.repo), values.base);
  if (values.json) {
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
  } else {
    for (const name of CLASSES) {
      const rows = result.rows.filter(row => row.class === name);
      if (!rows.length) continue;
      console.log(`\n${name} (${rows.length})`);
      for (const row of rows) console.log(`  ${row.path}  [${row.branch}] ${row.lastCommit ?? ""} dirty=${row.dirty} unpushed=${row.unpushed ?? "no-remote"} ${row.pr ?? ""}`);
    }
    console.log(`\n${result.rows.length} linked worktree(s) of ${result.main}, base ${result.base}`);
    if (!result.pullRequestsRead) console.log("pull requests not read (gh unavailable): squash-merged branches are not recognised as merged");
  }
  if (!values["remove-merged"]) return;
  if (!values.yes) {
    console.error("--remove-merged needs --yes: nothing removed");
    process.exitCode = 2;
    return;
  }
  let removed = 0;
  for (const row of result.rows.filter(candidate => candidate.class === "merged-clean")) {
    if (git(result.main, "worktree", "remove", row.path) === null) console.error(`not removed (git refused): ${row.path}`);
    else removed += 1;
  }
  git(result.main, "worktree", "prune");
  console.log(`removed ${removed} merged-clean worktree(s); branches untouched; missing registrations pruned`);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();
