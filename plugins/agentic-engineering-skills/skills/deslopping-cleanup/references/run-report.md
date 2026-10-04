# Canonical report for one cleanup campaign

Reuse the repository's existing canonical cleanup report. Otherwise, for an
authorized campaign, create `docs/cleanup/runs/<campaign-id>.md` in that repository.
Analysis-only runs return the proposed report in the response unless writing
documentation was requested. This report records evidence and execution; it does
not replace the project's source-of-truth documents, retention registry or
approved product decisions.

Use the sections below as the report's contract. Start with known facts and add
rows as investigation proceeds; explicitly mark unknown or pending information.
Preserve dated corrections and failed attempts instead of erasing their history.

**Minimum report for a small campaign** (one run, a few batches): run and mandate,
component decisions, batch approval proposals, batch journal and closure. Add
connections as soon as a batch touches wired code, owner decisions as soon as one
is asked, and the other sections only when their phase applies.

Keep a separate controller diary (outside the repository, or in the session's
scratch directory when the sandbox allows nothing else) for operational memory:
the owner's decisions in their own words, SHAs, gates run, recovery points and
lessons. Handoffs between sessions point to the report and the diary instead of
copying them. The diary is not an authority: when it disagrees with the report,
the report wins and the diary is corrected.

### Validated manifest

The "validated manifest" (also the run's "content digest") is the exact content
the checks approved. After checks pass, record `git ls-files -s -- <allowlist>`
(path and blob OID per file) once the batch's files are staged. After the commit,
`git ls-tree -r HEAD -- <allowlist>` must show the same blobs. The report update
is outside the allowlist; any later change to an allowlisted file invalidates the
manifest and the checks.

## Campaign and macro-run plan

- Campaign-ID, overall objective, repository scope and initial baseline.
- Ordered Run-IDs with objective, analysis strategy, complementary specialists,
  required predecessor output, expected result and closure/acceptance criteria.
- Phases beyond discovery that apply: branch integration, operational residue,
  workspace closure.
- Reasons for that sequence and for later additions, skips or reordering.
- Overall state, accepted run outputs and remaining dependencies/decisions.

Keep one canonical campaign index. If the repository already uses separate run
reports, link them from that index instead of duplicating their detailed evidence.
Otherwise repeat the sections below for each Run-ID in the same report. Qualify
batch and finding references by their owning run; record cross-run provenance when
carrying a candidate forward.

## Run and mandate

- Campaign-ID and Run-ID; objective and primary strategy; start/update dates.
- Repository and root; branch/worktree; full input SHA and relevant content digest.
- Predecessor Run-ID/output, closure evidence and acceptance reference, where needed;
  actual baseline comparison, drift and any required evidence refresh. Inherited
  tickets and plans re-validated against the current base.
- Scope, exclusions, pre-existing changes and authorization references.
- Authorized batch actions, local commits and checks; unresolved decisions.
- User-confirmed reference documents for intended features/integrations, their
  authority and current snapshots; unanswered questions, missing documentation
  and conflicts. Keep intended lifecycle status separate from actual reachability.
- Retention registry location and the entries consulted.
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
  reason to preserve and condition for re-evaluation. A closed owner decision to
  keep goes into the repository's retention registry; the report links to it.
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
For intentionally pending integration, record its existing plan/status; do not
treat the missing link as a defect or invent a repair mandate. Record the owner
and documentation check from
[the core rule](../SKILL.md#disconnected-components-and-the-owner).
Unresolved intent remains `defer`, not an established removal candidate.
Describing intended wiring neither proves it exists nor authorizes implementing it.

## Owner decisions

| Decision-ID | Question | Options and consequences | Recommendation | Owner answer (own words) | Date |
|---|---|---|---|---|---|

Only real decisions belong here. Ask them one at a time, or on a decision sheet,
always with one recorded answer per decision; record open questions as open,
never as recorded decisions.

## Batch approval proposals

Before requesting approval, present and record this proposal for each Batch-ID.
Use one row per affected file and distinct action, including changes supporting
the cleanup. Multiple actions on one file require separate rows.

| Batch-ID | File / symbol | Proposed action | Specific rationale | Evidence / snapshot | Expected behavior / wiring impact | Uncertainty |
|---|---|---|---|---|---|---|

Explain why each specific change is appropriate for that file and cite its
supporting evidence; rows may reference the run's shared recorded snapshot.
A batch-level reason or component decision does not replace these justifications.
An incomplete proposal cannot be submitted for approval or used to execute an
unjustified action. Material changes to approved actions, scope or rationale
require renewed approval for the affected proposal under the existing mandate.
Preserve superseded proposal versions and their approval references.

## Batch journal

For each Batch-ID record its owning Run-ID, then:

1. Candidate IDs/actions; exact file/action proposal version or reference;
   allowlist; owner approval reference; base SHA; dependencies.
2. Before/after inventory and wiring; diff manifest identifying validated blobs
   or equivalent reproducible content digest; unrelated changes excluded.
3. Exploration and independent review conclusions; controller checks of material
   claims against primary sources or actual command evidence, with snapshot and
   evidence locations; disagreements, agent errors, corrections and technical
   verdict. Separate reviewer conclusions from controller verification and owner
   approval; missing proof or required checks remain pending.
4. Each authorized check/rescan: command, scope, revision/content checked, result,
   evidence location, pending/failed/skipped status and reason. Mark environment
   failures (shared ports, missing tools) as such, not as code results. Checks
   before the commit run on the working tree (base SHA plus the batch's changes);
   they carry to the commit only through the
   [validated manifest](#validated-manifest). Exact-SHA gates (external CI,
   the merge-commit gate) run on the commit itself.
5. Report update, local commit subject/Batch-ID and resulting full SHA when known;
   verification of committed content against validated content. If the branch is
   merged by squash: the squash SHA and the branch or tag keeping batch commits
   reachable.
6. Corrections, WIP states, failures or reverts with dependency assessment. A WIP
   commit requires separate authorization and the label `WIP/<Batch-ID>`; it does
   not close the batch or replace its verified commit.

The commit contains its batch's report update. Resolve that commit's SHA via Git
and write it in a later report update or final documentation-only closure, avoiding
a self-reference. Report-only closure is explicitly separate from cleanup batches.
Document report changes made after checks separately; changed validated code
requires renewed relevant verification. Never attribute results to a new SHA merely
because only documentation or formatting appears to have changed.

## Integration log

When [branch integration](branch-integration.md) applies: refs and divergence at
each measurement, conflict inventory by type, area winners, owner decision sheet
reference, integration commits, merge commit parents, completeness check results
and every explained exception, notes handed to downstream branches.

## Operational action proposals

Actions outside files, proposed before execution as described in
[operational residue](operational-residue.md#proposing-operational-actions):

| Action-ID | Unit / resource | Action (names only) | Rationale | Evidence | Dry run / verification | Rollback impact | Who runs it | Approval reference |
|---|---|---|---|---|---|---|---|---|

## Operational residue

When [operational residue](operational-residue.md) applies, per deployable unit:

| Unit | Version live | Variables removed/added (names only) | Data actions (dry run → applied → verified) | Artifacts and consumers | Post-deploy checks | Open issues / ticket |
|---|---|---|---|---|---|---|

Record missing backups, placeholder values and owner statements that data is
disposable.

## Workspace closure

The [workspace closure](workspace-closure.md) inventory: each worktree, branch,
clone, stash and folder with its state, unique content found (ignored files
included), decision, approval reference, archive location (branch/tag/ticket) and
who ran the deletion.

## Run closure and handoff

Record the full output SHA and relevant content digest, strategy/question answered,
new and resolved findings, review/check state, controller reconciliation and its
evidence/limits, closure criteria and acceptance
reference under the current mandate. Identify residuals carried forward, protected
components, authorized scope and next-run question/input. A failed required gate
leaves the run open; deferred items may remain when explicitly compatible with its
closure criteria. Do not transfer an approval to new actions by implication.

## Campaign closure

Summarize all Run-IDs, objectives, input/output baselines and closure/acceptance
states; explain any skipped or added runs and remaining follow-ups. Distinguish
completion of the campaign's agreed scope from exhaustive absence of dead code.

Summarize removed, retained, deferred and restored components; open connections;
functional follow-ups; all cleanup batch IDs/full SHAs; check/review state and limits;
integration result, operational residue state per unit and workspace closure;
Graphify snapshot and incremental update performed or remaining. A failed gate,
uncertain consumer or unapproved action stays visible. Preserve traceability to
earlier decisions rather than maintaining a second contradictory authority.
