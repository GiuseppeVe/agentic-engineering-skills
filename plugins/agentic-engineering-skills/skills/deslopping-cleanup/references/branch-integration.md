# Branch integration

Use when the cleanup was done on a long-lived branch while the base (for example
`main`) or another branch kept moving. Integration is its own macro-run with its
own mandate: it decides which side wins for every changed file.

## Measure

- Fetch, record full SHAs of every ref involved and the divergence of each pair
  (`git rev-list --left-right --count A...B`). Re-measure at the start of every
  session; the base keeps moving.
- Record merge bases between each pair of branches.

## Inventory

- Simulate each merge without touching the work tree (Git 2.38 or later):
  `git merge-tree --write-tree -z --name-only --messages <base> <branch>`.
  Exit status 1 means conflicts (a script under `set -e` stops there: capture it).
  The first record is the result tree OID.
- Count conflicts by type from the `-z` informational records, whose
  `<conflict-type>` field is stable; without `-z` the messages are free text that
  must not be parsed. Never find conflicts by scanning the result tree or
  grepping for markers: modify/delete, mode, binary, file/directory and rename
  conflicts leave no markers in the tree.
- **Trap:** for modify/delete the result tree keeps the modified side. Code
  deleted by the cleanup but modified on the base comes back: list those files
  and delete them deliberately, after checking the base change carries no
  feature worth saving.
- If several branches must be combined, compare the conflict sets of the
  possible merge orders. Keep simulated results as private refs only for the
  duration of the work and delete them at the end.
- List base-only files that survive the merge and classify them.

## Decide by area

- Assign a winner per area (for example: new backend = cleanup branch; UI,
  billing, landing = base; legacy deleted by cleanup = deleted). Files changed on
  both sides are decided case by case.
- Cross-check each "legacy to delete" against the cleanup report.
- Put only real decisions on an owner decision sheet: each with options, a
  recommendation and the consequence of each option; record one answer per
  decision.
- Watch hot spots: server entrypoints, routes, workers, models, package manifests
  and lockfiles, deploy configuration, files with mixed line endings.

## Write

Two branches: a local resolution branch, never pushed, and the PR branch that
carries only the final merge commit. Commands below use plumbing, which skips
hooks: run the repository's hook checks explicitly before pushing. When the
environment reserves these commands, hand them to the owner.

1. Resolution branch from the simulated tree, markers included (checking out a
   tree over the base would not delete paths missing from it):
   `T=<result tree OID>`;
   `git branch <resolve> "$(git commit-tree "$T" -p <base> -m 'integration: simulated merge')"`.
   Unset any upstream on it.
2. Mechanical controller commit: deliberate deletions, whole-file "take side X",
   whole-file documentation.
3. Writers per area on disjoint files, one commit each, with review: one at a
   time in the resolution worktree, or each in its own worktree branched from it
   and brought back by the controller.
4. Lockfiles: restore from the winning side or regenerate with the CI toolchain
   only.
5. Final merge commit with the resolved tree and both histories as parents:
   `M="$(git commit-tree <resolve>^{tree} -p <base> -p <cleanup> -F <message-file>)"`;
   `git branch <pr-branch> "$M"`; verify `git diff --quiet <resolve> "$M"`. Push
   only `<pr-branch>`. Merge the PR with a merge commit: squash or rebase would
   lose the parents.
6. Before merging, re-check that the base is still an ancestor of `<pr-branch>`.
   If the base moved, re-simulate merging the new base into `<pr-branch>`,
   resolve the new conflicts the same way, and re-run the completeness check and
   the gate.
7. Keep the resolution branch locally as history until the owner decides.

## Prove completeness

"Zero diff against both sides" is impossible by construction. Instead:

- Trace the origin of every changed file.
- Run a per-hunk check of each side's changes against its merge base. One method:
  in a scratch worktree of the merge commit, reverse-apply each side's patch file
  by file (`git diff <merge-base> <side> -- <file> | git apply --check -R`); a
  hunk that fails did not land as-is. Explain every such hunk: recorded
  resolution, intended deletion or false positive. The goal is "no loss by
  oversight".
- Run the full gate on the merge commit with the CI toolchain versions (runtime,
  package manager), including authorized e2e suites that are not in CI. Suites
  that hit paid or external services need explicit authorization.

## Semantic conflicts

A clean textual merge can still break: the base may have added a new consumer of
something the cleanup removed (a string-registered loop, a prompt or tool name,
an environment variable read, a collection or job name). Typecheck sees only
static imports. For every removed component, variable, collection, job and tool
name, re-run the reference search and the
[hidden-consumer checklist](specialist-routing.md#hidden-consumer-checklist) over
the base's changes since the merge base (`git diff <merge-base>..<base>`) and over
the merged tree. Evidence gathered before the integration has expired.

## Downstream branches

Simulate conflicts for open branches of other people or agents and hand them a
note: expected conflicts, which side to keep, new invariants (for example test
fixtures that must now stub a gate). Do not rebase their branches yourself.

## Merge is a release when the base auto-deploys

Before merging, confirm whether the base deploys automatically, that required
secrets exist, and that a protective gate (maintenance mode, feature flag) is in
place. After merging, follow [operational residue](operational-residue.md).

## Reverting a merged integration

Revert a merge commit with `git revert -m 1 <merge>` (parent 1 = the base).
Trap: merging the same branch again later does not bring its changes back,
because its commits are already in history. Revert the revert first, then merge
the fixes. Data already cleaned up is not restored by any revert.
