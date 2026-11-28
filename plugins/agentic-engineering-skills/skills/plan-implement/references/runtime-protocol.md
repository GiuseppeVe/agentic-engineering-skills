# Plan Implement Runtime Protocol

## Inputs and startup

Start from the governing specification, the implementation plan, and any approved contracts map or programme mandate. Verify the plan's `## Design Review` is recorded before dispatching the first slice.

If the plan is assigned by a master (`coordinating-implementation-plans`) or resumes as its subthread, read [reporting to the master](reporting-to-master.md) and [programme messages](programme-messages.md) after reconciling local Git state, worktrees, and open checkpoints, before dispatching any slice. When a [plan mandate](plan-mandate.md) exists, reread it at launch and after resume, and honor its `paths`, `shared`, and overlap rules.

When the repository provides a host preflight script, run it on each machine before its first gate or push; when no master is present, present the owner once with the preflight summary and planned pushes/merges.

## Workspace and isolation

Use the lightest workspace layout that isolates concurrent mutations:

- One dedicated branch and worktree for the plan (`<repo-root>/.worktrees/<name>`).
- Parallel slices may run concurrently **only** when their prerequisites are integrated and their allowed files, ownership, and shared-contract surfaces are completely disjoint. Give each parallel slice its own isolated worktree branched from the verified base SHA; cap concurrency to available host capacity.
- Materialize every accepted prerequisite into a dependent slice's workspace through its accepted commit or verified diff before dispatching that dependent slice. Never let a dependent slice build on unverified or missing upstream state.
- Preserve unrelated worktrees, branches, and working-tree changes.

## Slice grouping and dispatch

1. Use `## Slice N:` boundaries declared in the plan when present; otherwise group contiguous ready tasks that touch the same module or area into one slice.
2. Dispatch **one persistent slice-implementer subagent** per slice so it keeps warm context across contiguous tasks of that module. Supply:
   - the slice's expected outcome (or derived outcome from mapped `REQ-NNN` for older plans),
   - exact task instructions, plan and spec paths, allowed files, constraints, and `risk` level (`standard` or `high`),
   - [slice contract](slice-contract.md), plus the plan thread's reachable address and mandate path when under a master.
3. Match models and reasoning effort to slice risk using only options available in the host, plan, or operator workspace configuration; keep `risk: high` or architecture-sensitive slices on a high-reasoning profile and record effective routing. Never silently substitute an unavailable provider or model.
4. Keep `plan-implement` as controller: do not write task implementation code directly in the controller thread unless the host cannot run subagents and the owner authorized inline fallback.

## Verification, high-risk checkpoints, and acceptance

- **Standard slices (`risk: standard`):** verify the slice implementer's uncommitted diff against allowed files, contracts, mapped `REQ-NNN`, and objective `final_state` L1–L3 check evidence (following [Verification](../../development-process/references/daily-workflow.md#verification)). No separate intermediate review subagent is required.
- **High-risk slices (`risk: high` or shared-contract changes):** before accepting the slice, dispatch a separate fresh-context clean-room review subagent using the host's native code-review capability. Pass only:
  1. the slice's expected outcome as amended by any parent- or owner-approved amendment,
  2. the original task instructions and approved amendments,
  3. the plan and spec paths, exact diff, and objective command evidence.
  Exclude the slice implementer's conclusions, self-verdict, and prior review verdicts.
- If a high-risk review finds valid in-scope defects, route fixes back to the slice implementer (or an authorized fixer), rerun affected `final_state` checks, and verify the updated diff. Earlier `final_state` evidence is stale after any code edit.
- **Acceptance criteria:** accept a slice only when every `REQ-NNN` required of its tasks is satisfied with appropriate `final_state` evidence or an explicit spec/plan `not applicable` basis, all required checks passed, and no blocker remains. A `done` report with unverified required items is `partial` and rejected for acceptance. A gap may remain deferred to a named later task **only** when the plan explicitly assigns it there; neither an implementer, a reviewer, nor an owner chat remark can reassign a deferral ad hoc.
- **Commit boundary:** slice implementers leave verified diffs uncommitted. After accepting a slice (and passing any required `risk: high` review checkpoint), `plan-implement` stages only the slice's paths and creates one local commit on the plan branch when commit authority is granted. Without commit authority, record the verified uncommitted diff state explicitly.
- **Convergence limits:** two negative reviews on the same module trigger one unified redesign with a state/event matrix rather than another patch loop; three failed attempts on the same slice escalate to the owner; a reviewer never prescribes the next unit of work.

## Integration and PR closeout

Integrate accepted slices in dependency order without replacing remote work or using force-push/reset. Verify the target SHA after each integration step.

Complete the plan only after every required spec/plan `REQ-NNN` is closed with evidence or a supported `not applicable` basis, every required checkbox is closed, every slice is accepted, and the plan's expected outcome is verified on the integrated result. An open deferred `REQ` or unchecked required item prevents plan completion.

When the assignment includes a PR, open one plan-level PR (not per-slice PRs) on the integrated candidate head by running `gh pr create --draft` in a shell tool toward the authorized branch, and follow [PR phase](../../development-process/references/daily-workflow.md#pr-phase) once: lint, quick checks and relevant tests on the integrated diff; independent full-diff native review with one `simplify` pass (and Knip when warranted) in parallel; confirmed P0–P2 fixes in one commit; delta-only review if fixes touched code; `gh pr ready <number>` as a standalone command; gates verified on that head SHA. After two fix rounds without convergence, stop and deliver `partial`.

A ready PR targeting a non-`main` branch is merged by the plan thread within mandate order, dependencies, and stops, followed by the continuous integration branch update in [Program orchestration](../../development-process/references/program-orchestration.md#plan-and-package-lifecycle). Any merge into `main` waits for explicit owner authorization. Complete authorized cleanup without deleting worktrees still holding unfinished work.

## Escalation and reporting

Ask the human (or master, when coordinated) only for structural contradictions, missing or conflicting acceptance criteria that change scope, unreadable required artifacts, a missing workspace, an unresolved subagent launch after safe checks, or missing authority for an assigned external action. Record assumptions for ordinary bounded choices.

Report each slice's base SHA, accepted commit (or exact verified uncommitted diff), mapped `REQ-NNN` status, checks and outcomes, findings, assumptions, blockers, and any PR, integration, or cleanup results. Use unified status `done`, `partial`, or `blocked`; never report `done` without verified final-state evidence.
