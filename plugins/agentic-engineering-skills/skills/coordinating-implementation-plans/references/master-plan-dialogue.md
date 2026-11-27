# Master–Plan Dialogue

Read this reference at launch and on every resume before creating or resuming a
plan thread (`plan-implement`). It describes the master side of one shared
protocol: message meanings and correlation live in
[programme-messages.md](../../plan-implement/references/programme-messages.md),
and the plan thread side lives in
[reporting-to-master.md](../../plan-implement/references/reporting-to-master.md).

## Addresses and escalation ladder

Record in the contracts map and canonical master state, for every plan:
reachable address, revision, decision scope, resources, and state. The run
ledger belongs to the plan thread — read it to reconcile, do not overwrite it.
Never invent a missing address or treat a stale brief as a new mandate.

The plan thread receives address and mandate and publishes its own address to
its slice subagents. Questions travel along this ladder:

| Sender | Recipient | Content |
| --- | --- | --- |
| Slice subagent | Plan thread | Question on its assigned slice or mandate |
| Plan thread | Master | Residual flow doubt or reserved choice only, with mandate, suspended action, proposed choice, and consequence |
| Master | Owner | Reserved choice only, with exact choice, observable effect, and blocked step |
| Master | Affected plans | Decision correlated to the question, with scope and revision; only to affected plans |

A question already answered by the mandate, approved sources, or a decision in
force never climbs the ladder: the receiving thread resolves it locally and
records the basis. The master never forwards a question the plan could settle
locally, and never substitutes a decision for missing verification evidence.

## Plan mandate, package manifest, and gates

Before delegating a plan thread, commit the
[plan mandate document](../../plan-implement/references/plan-mandate.md) in its
branch with all required sections, and only then send the first message; pass
the document's path and `revision` to the plan thread and record them in the
map. Parallel plan mandates declare the same holder for every shared file.

Every mandate change is a new commit of the document with incremented
`revision` and `supersedes`; the notification message cites the new revision
and never precedes the commit: a chat-only message does not change a mandate.
When a change alters delivery (base or expected outcome), the new revision is a
distinct mandate citing the superseded one, and the old revision is never
rewritten. A late report remains attributed to the revision under which it was
requested.

When creating a package, commit the [package manifest](package-manifest.md) on
`pkg/*` before the first plan PR. Update it in the same step that adds a plan
to the map, and record `pr` when the plan PR opens: a plan present in the map
but absent from the package manifest escapes completeness checks.

Never choose or drop CI gates: the project's versioned map selects them from
the diff and defaults to running more when uncertain. Full gates are mandatory
when the diff touches an unmapped path or a shared file, or when the diff or
map cannot be read. The map itself is a shared file: changing it requires owner
review, and a PR changing it is evaluated against the map on its base.

PRs targeting non-`main` branches run selected gates; PRs targeting `main` run
the full suite. The sole exception is the consumer's diff-exception label on
the current head, valid only when applied by an owner account after that head
was pushed (by the host's recorded push timestamp, never commit timestamp); any
new push voids it. Chat approval, even from the owner, is not that label: an
agent requests it through the master and never grants it itself. Declare
readiness only when required gate statuses on the frozen head are green
(`gh pr checks <PR>`) and independent review of that head is concluded; a
hosted CI check red solely due to billing is not a blocker.

## From brief to verified delivery

1. The brief identifies address, mandate, and reserved decisions. The plan
   thread creates or resumes its branch, worktree, and slice subagents.
2. An informational update binds to the active mandate. Any receipt confirmation
   preserves delivery identity, creates no step, and grants no authority.
3. The plan thread escalates only residual flow doubts. The master checks first
   whether the mandate, sources, or state already answer it; if so, reply with
   the citation and record the basis.
4. For integration order or shared files within the mandate, the master decides
   directly. When a proposal alters structure, contracts, behavior, perimeter,
   or a reserved authorization left open by sources, the master asks the owner
   with exact choice, observable effect, and blocked step.
5. Each decision identifies the question, scope, revision, and decision maker.
   If delivery changes, the master issues a distinct mandate citing the
   superseded one.
6. Communicate the decision only to affected plans and record it. A
   programme-scoped decision carries no plan revision and is reused without
   re-evaluation. A plan-scoped decision is reused only when scope and revision
   match; if they changed, re-evaluate and record a new decision. A duplicate
   decision produces a single step.
7. The plan resumes only unblocked actions, citing the decision in the next
   step. A chat acknowledgement without an observed step does not prove
   resumption.
8. Verify every delivery report against its mandate (base and expected outcome)
   and verify `sha` on `origin` with Git or `gh`. A late report stays bound to
   its original mandate; a later decision holds precedence only within its
   scope.
9. When delivery is uncertain, verify receipt before resending. On wake,
   reconcile open questions, pending decisions, and arrived results via host
   notifications or a compact snapshot.

## Discriminating cases

- **Authorized sync:** the plan asks when to sync a branch — a flow doubt the
  master settles within the mandate without involving the owner. If the sync
  changes the base, issue a distinct mandate citing the prior one.
- **Guarantee change from `main` to `pkg/*`:** replacing a `main`-availability
  gate with package availability requires an approved equivalence basis or an
  owner decision escalated through the master. Missing product contracts follow
  the same route.
- **Draft individual PR under an aggregate mandate:** when the mandate calls
  for an aggregate PR, follow the aggregate path; the draft individual PR may
  remain draft and receives no merge green light.
- **Pre-existing programme with direct PR to `main`:** preserve that direct
  integration route and apply the same verification criteria.

## Consumer state and readiness

Verify the authorized integration path before proposing action. Derive plan and
package state from GitHub, never from orchestrator logs:
`gh pr list --base pkg/<x> --state merged --json number,title,body,mergeCommit`,
matching each PR via the `Plan: <id>` line in its body. Record head, perimeter,
and target, keeping observed facts, required perimeter, available evidence,
readiness, and merge authorization distinct.

Declare readiness only when required repository proofs cover the actual
perimeter and revision. A new push invalidates prior head proofs. With
unreadable sources, changed mandates, or skipped gates, state the remaining
verification explicitly; exceptions apply only within their authorized scope.
A tip already on `main` does not close a package while a required plan remains
open, and containment of a required revision must be verified before claiming
inclusion.

| Spec acceptance scenario | Master classification |
| --- | --- |
| Non-draft PR with missing review or failed gate | Readiness open: report missing proof or failure; no green light |
| New push after positive review | Re-verify on current head; prior head proofs are stale |
| Upstream plan feeds through another package and its tip advances | Verify containment of the new revision before claiming inclusion |
| Plan has draft individual PR under an aggregate mandate | Next step follows aggregate path; draft individual PR may stay draft |
| Tip is on `main` while a required plan remains open | Tip is integrated; package remains open |
| Source unavailable, mandate changed, or gate skipped | State residual proof and scoped exception explicitly |
| Pre-existing programme with direct PR to `main` | Preserve direct path and apply the same evidence rules |

## Resources, stops, and resumption

A question pauses only its dependent action; independent authorized work keeps
running, and an explicit owner stop halts only actions inside its declared
scope. On resume, restart only unblocked actions, each citing the authorizing
decision.

## Boundaries

Dependency selection, workspace isolation, slice-implementer and high-risk
review dispatch, commits, and integration remain governed by
[runtime protocol](../../plan-implement/references/runtime-protocol.md). The
dialogue never bypasses a dependency gate, review stage, or commit boundary,
and a question or decision never substitutes for missing evidence.
