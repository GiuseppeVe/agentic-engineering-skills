# Runtime Protocol

## Setup and run state

Verify the plan, spec and any supplied contracts map, including their revisions. Before dispatch, create one branch and shared worktree from the intended revision, respecting repository rules; wait until usable and record `run_branch`, `run_worktree` and `starting_revision`. Keep the main checkout unchanged and pass the exact shared `workspace_ref` to every subthread. Pending setup creates no child; definitive failure is `BLOCKED`.

Initialize or resume a non-versioned ledger outside the run worktree; record its location and reuse it on resume. Track the run and task identifiers, input references and revisions, task queue, `current_task`, `side_slot`, child roles and lifecycle, confirmed and provisional identifiers, host routing information when available, effective model/effort, worktree/branch, implementation and review commits, integration target and result, tests, findings, assumptions and blockers. Record transitions; on resume reconcile the ledger with host status and Git state before dispatch.

## Dispatch and verification

Process tasks in order with one slot: implementation **or** review. Before creating a visible subthread, verify that the slot is free, the task is `current_task`, no same-task child is pending/active, and all predecessors are `ACCEPTED`; then reserve the slot before creation. Keep later tasks queued. If the host cannot create the requested visible subthread, report `BLOCKED`.

A pending or active child owns the slot. Record provisional identifiers separately; a timeout, progress update or queued message is not completion. If evidence is missing, follow up in the same subthread. If identity or activity remains unresolved after safe checks, retain the slot and report `NEEDS_ATTENTION` or `BLOCKED`. If multiple children are pending/active, record each, suspend dispatch, integration and worktree mutation, and reconcile all before continuing. Record failures or stops; replace a child only after confirming it cannot continue to modify the worktree.

Release the slot only after the child’s turn ends, its final result and commit/worktree evidence are verified, outstanding work cannot modify the worktree, and the role is recorded complete. Keep later tasks blocked or assigned so earlier children cannot take them during review. The session may remain open; request shutdown during final cleanup.

## Subthread assignments

For each role, pass the task ID, plan and spec references, exact shared worktree and required output fields. Do not paste source code, child-skill internals, implementation strategy or test commands into the assignment.

- **Implementation:** use the available implementation skill in bounded worker mode; implement only the selected task and commit it on the run branch. Return status, commit, changed files, tests/results, assumptions and blockers. The orchestrator verifies the exact commit, diff, branch and worktree before dispatching review.
- **Review:** create a different subthread on the verified implementation commit/diff; run `test-driven-development` against the task and its requirements. Return findings, tests/results, changed files, fix commit when applicable and blockers. Use `agent-architecture-audit` for architecture-sensitive work only when available; record the gap if unavailable, and block only if the plan requires it.

Coordinate any fixes through the same single-slot lifecycle. Never expand silently into unrelated tasks. Honor explicit model/effort requirements and higher-priority host instructions; otherwise use host defaults. Record effective supported settings.

## Integration and closeout

After review and fixes, verify the accepted commit/diff and evidence. If an integration target is provided, integrate the exact accepted range before the next task only when the slot is free and the target can accept it without replacing remote work. Require explicit human authorization for `main`; divergence or non-fast-forward is `BLOCKED`, with no force-push or reset. Verify the target contains the accepted commit and record the resulting SHA. A failed integration leaves the task unaccepted and later tasks queued. If no target is supplied, record the omission and accept locally.

If the assignment includes a PR, follow the repository’s review, gate, merge and cleanup rules on the exact head. For a map-master assignment, report readiness and wait for its merge go-ahead. Complete the authorized merge and cleanup; report any unfinished cleanup and do not remove a worktree while outstanding work could affect it.

## Decisions and reporting

Ask the human only for structural contradictions, missing or conflicting acceptance criteria that change scope, unreadable required artifacts, a missing workspace, or an unresolved subthread launch after safe checks. For ordinary choices, use the least-expansive interpretation and record assumptions. Respect previously granted authorization and applicable higher-priority requirements.

Report each task’s implementation/review/fix commits, tests and results, findings, assumptions and blockers; include integration and cleanup results when applicable. Do not report completion without the required plan, spec, commit, worktree and review evidence.
