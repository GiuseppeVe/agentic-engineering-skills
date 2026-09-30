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

## Route specialists by phase

Before selecting a specialist, consult
[specialist routing](references/specialist-routing.md). Match the open question
to a route, locate the skill in the current catalog, and read its instructions
when that phase begins. Supply the route's input and reconcile its returned
evidence with reviewed facts before deciding a batch. Respect invocation triggers
and the current mandate. Missing specialists use the documented fallback; missing
necessary evidence keeps the candidate uncertain. This reference does not load
or install other skills automatically.

## Run loop

1. Consult the existing graph before broad source exploration when relevant.
   Give explorers bounded questions. Handoffs contain snapshot, scope,
   files/symbols, contracts, verified facts, uncertainties and expected output.
   Raw scans may generate candidates during exploration; read their relevant
   specialist guidance then. Discovery findings remain unverified proposals.
2. Have independent reviewers check material exploration claims against sources.
   Reuse specialists for targeted discovery or specific evidence gaps;
   reconcile new findings with reviewed facts. Repeat targeted investigation
   for disagreements before choosing the strategy.
3. Classify components as remove, retain or defer with reasons and counterproof.
   Check dynamic/external consumers, alternate modes, contracts and migrations.
   An unused export can wrap a live internal function; names/recency do not
   select the canonical implementation.
4. Propose small coherent batches by responsibility and shared consumers. Each
   has Batch-ID, candidate IDs, actions, allowlist, dependencies, expected wiring,
   authorized checks and stop conditions. Obtain specific batch approval; reuse
   existing approval only for the same actions/scope. One writer owns a batch.
5. Apply only that batch. Review diff and wiring independently, perform authorized
   checks/rescans, compare pre/post, and update the canonical run report using
   [the report contract](references/run-report.md). Failed checks, contradicted
   claims or an unintentionally broken live connection keep the batch open.
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

Close with removed/retained/deferred components, wiring residuals, batch SHAs,
checks and limits. Update Graphify only through authorized, configured incremental
maintenance; record stale portions. Push/merge obey the current repository and
environment approval policy. Skill invocation alone grants no deletion or remote authority.
