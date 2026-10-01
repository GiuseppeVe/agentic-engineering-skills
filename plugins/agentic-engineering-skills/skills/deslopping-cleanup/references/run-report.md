# Canonical report for one cleanup run

Reuse the repository's existing canonical cleanup report. Otherwise, for an
authorized execution run, create `docs/cleanup/runs/<run-id>.md` in that repository.
Analysis-only runs return the proposed report in the response unless writing
documentation was requested. This report records evidence and execution; it does
not replace the project's source-of-truth documents or approved product decisions.

Use the sections below as the report's contract. Start with known facts and add
rows as investigation proceeds; explicitly mark unknown or pending information.
Preserve dated corrections and failed attempts instead of erasing their history.

## Run and mandate

- Run-ID; repository and root; branch/worktree; full base SHA; start/update dates.
- Scope, exclusions, pre-existing changes and authorization references.
- Authorized batch actions, local commits and checks; unresolved decisions.
- Specialist skill/guide references; tool versions/configurations; graph and scan
  snapshots/coverage; evidence locations and limitations.

## Component decisions

| Component-ID | Responsibility, file/symbol | Present/reachable now | Decision | Execution state | Reason and evidence/counterproof | Batch-ID |
|---|---|---|---|---|---|---|

Decision: `remove`, `retain`, `defer`.
Execution: `proposed`, `approved`, `applied`, `verified`, `committed`, `restored`.
Keep these separate: an approved removal is not yet an eliminated component.

- **Removed:** responsibility removed, consumers checked, compatibility/migration
  considerations, existing replacement if any, Batch-ID and recoverable commit.
- **Retained:** actual consumers or explicit owner rationale for intended value;
  reason to preserve and condition for re-evaluation.
- **Deferred:** missing proof, prerequisite/decision, next step and re-entry trigger.
  Public APIs or uninspectable external consumers stay uncertain where relevant.

Each material claim names a source snapshot and `file:line` or command/output.
Scanner confidence is recorded as scanner confidence, not proof of safety.

## Connections and follow-ups

| Connection-ID | Caller/entrypoint → component → consumer/data | Contract/config/flag | Actual before | Actual after | Intended connection | Evidence | Batch-ID/follow-up |
|---|---|---|---|---|---|---|---|

Capture affected links before modifying them; after cleanup record their actual
state and evidence. Include changes to callers, registrations, configuration or
contracts that could disconnect retained components.

An unintentionally lost live connection blocks batch closure and the next batch.
Repair within the approved scope or return the problem for a decision. A retained
component already disconnected gets a functional follow-up: intended caller,
target contract, prerequisites, required changes and approval still needed.
Describing intended wiring neither proves it exists nor authorizes implementing it.

## Batch journal

For each Batch-ID record:

1. Candidate IDs/actions; allowlist; owner approval reference; base SHA; dependencies.
2. Before/after inventory and wiring; diff manifest identifying validated blobs
   or equivalent reproducible content digest; unrelated changes excluded.
3. Exploration and independent review conclusions, disagreements and resolutions.
4. Each authorized check/rescan: command, scope, revision/content checked, result,
   evidence location, pending/failed/skipped status and reason.
5. Report update, local commit subject/Batch-ID and resulting full SHA when known;
   verification of committed content against validated content.
6. Corrections, WIP states, failures or reverts with dependency assessment. A WIP
   commit requires separate authorization and the label `WIP/<Batch-ID>`; it does
   not close the batch or replace its verified commit.

The commit contains its batch's report update. Resolve that commit's SHA via Git
and write it in a later report update or final documentation-only closure, avoiding
a self-reference. Report-only closure is explicitly separate from cleanup batches.
Document report changes made after checks separately; changed validated code
requires renewed relevant verification. Never attribute results to a new SHA merely
because only documentation or formatting appears to have changed.

## Closure

Summarize removed, retained, deferred and restored components; open connections;
functional follow-ups; all cleanup batch IDs/full SHAs; check/review state and limits;
Graphify snapshot and incremental update performed or remaining. A failed gate,
uncertain consumer or unapproved action stays visible. Preserve traceability to
earlier decisions rather than maintaining a second contradictory authority.
