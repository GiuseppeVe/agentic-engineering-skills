---
name: merge-verified-pr-and-cleanup
description: Use when a pull request has completed review and required checks and is ready to merge, especially when its branch is in an isolated worktree
---

# Merge Verified PR and Clean Up

## Closeout contract

- **Goal:** Merge verified PR into verified base; then clean up only its branch and worktree.
- **Context:** PR, head SHA/branch, base, review/check status, merge method, related workspace.
- **Scope:** This PR only. No code changes or unrelated cleanup.
- **Requirements:** Review and required checks apply to current head SHA and pass. Follow repo release instructions; preserve recoverable work.
- **Authority:** Inspect and run required read-only checks. Mutations require the repo's exact approval gate; never bypass it or force-delete.
- **Proof/report:** Confirm merge commit is on base; run required post-merge check. Report PR, base, commit, checks, cleanup, and anything preserved.

## Workflow

1. **Resolve context.** Read repo runbook and relevant domain guide. Verify live PR, head SHA, base, merge method, review, required checks, exact branch/worktree, and owner. Never infer base from branch name.
2. **Check readiness.** Require approved review, resolved required threads, and green checks for current head SHA. Run the smallest required repo gate if no equivalent current result exists. Pending, failed, stale, or unclear state means stop and report what's missing.
3. **Inspect workspace.** Check `git status --short --untracked-files=all` and `git worktree list`. Confirm branch/worktree is clean and unused. Preserve dirty, shared, or uncertain state.
4. **Merge.** Use configured forge/method and follow the repository's approval gate for the exact mutation. Wait for required authorization; never bypass it or infer it from a prior review or general task request.
5. **Verify.** Confirm merged state, record merge commit, verify it is on target base, and run required post-merge check. On failure, stop and preserve workspace.
6. **Clean.** After verification only, clean the PR's merged, unused branch/worktree. For Codex-managed worktrees, inspect attached artifacts and prefer app archive-worktree. For manual worktrees, remove only the verified path from outside it. Preserve dirty work. Never use `--force`, `git branch -D`, `git reset --hard`, or `git clean`.
7. **Report.** Include checks/results, cleanup done or withheld, and reason. If host-managed workspace has no supported cleanup control, leave it and state why.

## Repository-specific rules

Follow the repository's release runbook and merge policy. Use its required checks and post-merge verification. Respect protected branches and never bypass an approval gate or push directly to a protected base.

## Stop conditions

- Review/checks missing or stale; base/head uncertain; merge/verification failed → no cleanup; preserve and report.
- Dirty, shared, pinned, active, or owner-unclear worktree → do not remove/archive it.
- Cleanup needs force or bypasses approval → stop.
