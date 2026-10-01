---
name: deslopping-cleanup
license: MIT
description: Use when a repository cleanup or deslopping run spans dead code, unused dependencies, overlapping implementations, or disconnected components and needs coordinated investigation across multiple responsibilities. Also use when explicitly asked for the cleanup orchestrator.
---

# Deslopping Cleanup

Orchestrate evidence-led, behavior-preserving cleanup. This is the coordinator;
Desloppify is a separate specialist. Specialists produce findings, reviewers
challenge them, and the coordinator turns verified facts into approved batches.

## Start and authority

Read repository instructions and establish repository, branch/worktree, base
SHA, scope, exclusions, pre-existing changes, and permitted checks/mutations.
Use this workflow and the bundled report contract. If the repository or user
provides a cleanup methodology, read and reconcile it with the current mandate.
No external methodology document is required. Keep investigation and execution
within the selected repository and approved scope.

Analysis-only requests remain read-only. For execution, establish a mandate
covering the selected batches and local commits. Preserve repository approval
gates for remote actions. Neutral cleanup is the default: functional changes,
migrations, new wiring, installs and expanded scope require a separate decision.

## Interpret disconnected components with the owner

"Disconnected" describes current reachability, not lifecycle status. It does not
mean legacy, obsolete, dead or removable: a component may implement a new feature
deliberately awaiting integration. A missing consumer or scanner finding alone
does not distinguish planned work from abandoned or replaced code.

Before classifying a disconnected candidate, ask the user which reference
documents describe intended features and integrations, and which are authoritative
and current. Examples include roadmaps, Wayfinder maps, README files, engineering
guides and architecture decisions; no particular document type is required.
Reuse explicit answers already supplied for the current scope; ask about missing
authority, freshness or conflicting intent instead of repeating answered questions.
Read the relevant documents and compare their stated intent with source, history
and actual wiring. Documentation of a planned link does not prove it exists.

Record the user's answer, document references/snapshots, intended status and actual
reachability in the canonical report; pass this context to explorers and reviewers.
Preserve intentionally pending integration and its existing plan. If the user has
no reference documentation, record that gap and their explicit intent, if supplied.
If the user has not answered and intent is unknown, or intent otherwise remains
unresolved, mark the candidate `defer`. Do not assert removal is safe or
wire it automatically; integration remains a separate approved functional change.

## Organize the cleanup campaign

Use the hierarchy: campaign -> macro-runs -> coherent batches -> commits.
A macro-run answers a distinct analysis question on a recorded source snapshot;
it includes discovery, independent review, decisions and any authorized cleanup.
Its batches are execution units, not additional macro-runs or chat sessions.

Propose an ordered campaign based on the repository's evidence gaps and dependency
changes. Give each macro-run a Run-ID, objective, input baseline, primary strategy,
supporting specialists, scope, expected output and closure/acceptance criteria.
Explain what its strategy adds to the preceding run. Select the number and order
from those needs; a small task may need one run. Use the suggested progression in
[specialist routing](references/specialist-routing.md), adapting it to the mandate.

For cumulative cleanup, the next macro-run starts from the preceding run's verified
output and recorded acceptance under the current mandate. Verify the actual tree,
commits and relevant map/scan freshness; inherited summaries do not prove readiness.
Carry retained/deferred candidates forward with their evidence and stable IDs,
but re-evaluate changed consumers and confirm authorization for the new snapshot.
Earlier approvals do not automatically cover newly discovered actions.

After each run, reconcile its outcomes and revise the remaining campaign. New
orphans may justify another strategy or run; a routine rescan inside a batch does
not require one. Record why a run is added, skipped or reordered. An architectural
detachment that changes behavior requires a separate approved mandate; only then
can its verified result feed a new cleanup run. No scanner finding authorizes
severing a live connection merely to create removable code.

## Route specialists by phase

Before selecting a specialist, consult
[specialist routing](references/specialist-routing.md). Match the open question
to a route, locate the skill in the current catalog, and read its instructions
when that phase begins. Supply the route's input and reconcile its returned
evidence with reviewed facts before deciding a batch. Respect invocation triggers
and the current mandate. Missing specialists use the documented fallback; missing
necessary evidence keeps the candidate uncertain. This reference does not load
or install other skills automatically.

## Controller evidence gate

The coordinator acts as controller and owns the final technical reconciliation.
Explorer and reviewer verdicts remain claims until the controller checks the
material evidence used for decisions. This gate does not grant owner approval.

Apply it after exploration review before choosing batches, after diff review
before committing a batch, and at run closure before handing off its baseline:

- Read the relevant source, configuration, history or actual command evidence
  directly. Confirm files/symbols exist, cited locations and counts are accurate,
  and the verdict concerns the requested object: file, export, function or type.
- Trace decisive consumers, entrypoints and dynamic wiring. Check whether evidence
  supports removal, retention or uncertainty; distinguish replaced code from code
  never connected and intended wiring from actual wiring. Agreement between agents
  or scanners does not establish correctness.
- Resolve full revisions through Git; compare evidence snapshots with the actual
  tree. After writing, inspect actual changed files/blobs against the allowlist,
  approved actions and expected wiring. Read check results and their scope/revision;
  a reviewer saying "passed" does not substitute for the recorded result.
- Resolve conflicting claims using primary evidence. Return a bounded question to
  the relevant specialist/reviewer when needed, then check the answer. Record agent
  errors and corrections. Missing proof remains uncertain; a contradicted claim or
  pending required check blocks the affected decision or closure.

Record controller checks, evidence locations, snapshot, resolved disagreements
and technical verdict in the report. Scope checks to decision-bearing claims and
changed surfaces; do not repeat broad exploration or rerun every check by default.
Use only authorized reads/checks; unavailable evidence is a limit, not a pass.

## Justify every file action before approval

Before requesting approval for any batch, present one proposal row for every
affected file and distinct action. Identify the exact path and relevant symbol,
concrete change, specific reason, supporting evidence and source snapshot,
expected effect on behavior and wiring, and unresolved uncertainties. Rows may
reference a shared recorded snapshot. Multiple actions on the same file require
separate rows; a general batch rationale or component decision does not replace
each action's justification.

Keep the approval-facing proposal in the canonical report using
[the report contract](references/run-report.md#batch-approval-proposals).
An incomplete proposal cannot be submitted for batch approval; do not execute an
action lacking its justification. Material changes to approved actions, scope or
rationale require renewed approval of the affected proposal under the existing
mandate. Preserve the prior proposal and its approval reference.

## Batch loop within each macro-run

1. Consult the existing graph before broad source exploration when relevant.
   Give explorers bounded questions. Handoffs contain snapshot, scope,
   files/symbols, contracts, verified facts, uncertainties and expected output.
   Raw scans may generate candidates during exploration; read their relevant
   specialist guidance then. Discovery findings remain unverified proposals.
2. Have independent reviewers check material exploration claims against sources.
   Reuse specialists for targeted discovery or specific evidence gaps;
   reconcile new findings with reviewed facts. Repeat targeted investigation
   for disagreements, then apply the controller evidence gate before choosing
   the strategy.
3. Classify components as remove, retain or defer with reasons and counterproof.
   For disconnected candidates, first apply the owner/documentation check above.
   Check dynamic/external consumers, alternate modes, contracts and migrations.
   An unused export can wrap a live internal function; names/recency do not
   select the canonical implementation.
4. Propose small coherent batches by responsibility and shared consumers. Each
   has Batch-ID, candidate IDs, actions, allowlist, dependencies, expected wiring,
   authorized checks and stop conditions. Present the justified file/action
   proposals before obtaining specific batch approval; reuse
   existing approval only for the same actions/scope. One writer owns a batch.
5. Apply only that batch. Review diff and wiring independently, perform authorized
   checks/rescans, compare pre/post, and update the canonical run report using
   [the report contract](references/run-report.md). Failed checks, contradicted
   claims or an unintentionally broken live connection keep the batch open.
   The controller checks the actual diff and review/check evidence before commit.
6. Commit each approved, verified batch immediately before starting the next.
   Stage only its changes and report update; inspect the staged diff to exclude
   unrelated work. Use the Batch-ID in report and commit message. Compare the
   validated file blobs with committed content; exact-SHA gates remain pending
   until actually run on that SHA. No automatic squash/amend of batch history.

Record the resulting full SHA in the next report update or final documentation
closure; never embed a commit's own SHA in its own report. By default, WIP stays
in the report and working tree. A separately authorized WIP commit is labelled
`WIP/<Batch-ID>` and never replaces the verified batch commit. On failure, pause
and correct within mandate; assess any revert against
later dependencies and preserve unrelated changes. No automatic destructive reset.

Close each macro-run with its output baseline, review/check state, controller
verdict, acceptance and handoff. Close the campaign with run outcomes, removed/retained/deferred components,
wiring residuals, batch SHAs, checks and limits. Update Graphify only through authorized, configured incremental
maintenance; record stale portions. Push/merge obey the current repository and
environment approval policy. Skill invocation alone grants no deletion or remote authority.
