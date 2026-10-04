# Workspace closure

A long cleanup leaves worktrees, branches, stashes, temporary folders and
untracked files behind. Some of them hold work that exists nowhere else. Inventory
before deleting anything; the inventory itself deletes nothing.

## Inventory

Read the repository guardrails first: protected branches, worktrees reserved for
owner review, archive branches and every ref the cleanup report cites (for
example a branch or tag keeping squashed batch commits reachable) are excluded
from deletion proposals.

Refresh remote state without deleting: `git fetch` (no `--prune`), then
`git remote prune origin --dry-run` to list remote-tracking refs whose branch was
deleted on the host. Those refs may be the last local pointer to that work:
inventory them before any prune. Record when the fetch ran.

Inventory worktrees with `git worktree list --porcelain` (note `locked` and
`prunable`). Classify as "not ours" unless the owner confirms otherwise:

- the controller's own worktree, always;
- worktrees in tool-managed locations (for example `.claude/worktrees`,
  `.codex/worktrees`) or modified recently, since a live session may own them;
- other people's or other tools' work.

For each worktree, branch, clone, stash entry and leftover folder record:

- registered or orphaned (its link to the repository is broken);
- branch, head SHA, whether it is on the remote, and its unpushed commits
  (`git log <branch> --not --remotes`, after the fetch);
- whether its content is in the base. `git merge-base --is-ancestor` only detects
  real merges. For squash or rebase merges the primary test is
  `test "$(git merge-tree --write-tree <base> <branch>)" = "$(git rev-parse <base>^{tree})"`:
  equal means the branch adds nothing. `git cherry -v <base> <branch>` helps after
  rebase merges (`-` lines are already in the base). When the test fails, review
  the differences by hand; never build pathspecs with unquoted `$(...)`, which
  breaks on spaces and silently yields an empty diff;
- uncommitted, untracked **and ignored** files (`git status --porcelain --ignored`).
  Leave out regenerable content (dependencies, build output, caches); for the rest
  check whether the same content exists elsewhere (compare blobs, not names);
- size and last activity.

Typical findings that must not be lost: design documents never committed,
branches that exist only locally, a skill or tool folder excluded by `.gitignore`.
`git worktree remove` counts ignored files as clean and deletes them: archive
unique ignored content before any removal.

**Secrets.** Env files other than tracked templates, keys, tokens and credential
stores are listed by name only and never archived in git. The owner preserves
them out of band if needed.

## Decide with the owner

Group the inventory: safe to delete (merged, pushed, clean, no unique ignored
content), needs a decision (unique content), not ours (never deleted). Present the
full deletion list, safe group included, for one explicit approval. Discuss the
second group with a recommendation per item and record one answer per item.
Remote branch deletions are approved branch by branch.

Preserve unique content before deletion: commit only explicitly listed, non-secret
paths to an archive branch, or tag it. Before pushing an archive branch (only if
the owner agrees), check its path list against secret patterns. Open a ticket
when the content needs a later decision.

## Delete

- Never delete a "not ours" worktree, including the controller's own.
- Remove registered worktrees through git (`git worktree remove`): it refuses
  tracked modifications and untracked files, not ignored ones. After deleting a
  worktree folder by hand, run `git worktree prune --dry-run -v` and prune only
  if it lists nothing but the removed entries.
- The stash stack is shared by all worktrees and sessions. Identify an entry by
  SHA and message (`git stash list --format='%H %gd %gs'`). `git stash drop`
  accepts only `stash@{n}`: re-find the index right before dropping, then check
  the SHA printed in `Dropped ... (<sha>)`. If it is not the expected entry,
  restore it at once with `git stash store -m "<message>" <sha>`.
- Folder and data deletions are run by the owner when the environment reserves
  them: give exact commands, a staging step (move to a holding folder) and a final
  delete command. On Windows, long paths may need `cmd /c rd /s /q "\\?\<path>"`,
  run from PowerShell or cmd.exe: Git Bash rewrites the switches and backslashes.
- Prune stale remote-tracking refs, then delete the approved remote branches and
  private temporary refs, at the end.
- Verify the result and record what was removed, kept and archived, with the
  approval reference.
