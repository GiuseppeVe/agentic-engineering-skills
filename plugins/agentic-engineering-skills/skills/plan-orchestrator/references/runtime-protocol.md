# Runtime Protocol

## Setup and run state

Verify the plan, spec and any supplied contracts map, including revisions. Create one branch and shared worktree from the intended revision; wait until usable and record `run_branch`, `run_worktree` and `starting_revision`. Keep main unchanged and pass the same `workspace_ref` to children. Pending setup creates no child; definitive failure is `BLOCKED`.

Initialize or resume a non-versioned ledger outside the worktree. Track run/task IDs, input paths and revisions, queue and `current_task`, child role/lifecycle and confirmed or provisional IDs, host routing and effective model/effort, worktree/branch, implementation base SHA and diff, accepted task commits, integration target/result, tests, findings, assumptions and blockers. Record transitions; on resume reconcile ledger, host status and Git before dispatch.

## Dispatch and verification

Process tasks in order with one child slot. Before dispatch, verify it is free, the task is `current_task`, and predecessors are `ACCEPTED`; reserve the slot before creating a visible subthread. Keep later tasks queued. If the host cannot create the requested child, report `BLOCKED`.

A pending or active child owns the slot. A queued ID or progress update is not completion. Follow up in the same thread when evidence is missing; retain the slot while identity or activity is unresolved. If children conflict, suspend dispatch, integration and worktree mutation until reconciled. Record failures or stops; replace a child only after confirming it cannot still modify the worktree.

Release the slot only after the child's turn ends, its role-specific evidence is verified, and no work can still modify the tree. For implementation, verify the base SHA, branch, worktree diff and checks; the implementation result remains uncommitted. For review, verify the final task commit and that it contains the reviewed and checked result. Keep later tasks queued until the current task is accepted. A session may remain open; request shutdown during final cleanup.

## Subthread assignments

For each child, pass the task ID, required references, exact shared worktree and output fields. Do not paste source, child-skill internals or implementation strategy into the assignment.

- **Implementation:** invoke `task-implement` with the host-native skill command and provide exactly three task inputs: plan path, spec path, and exact instruction identifying the selected task. Read the first five lines of the invoked skill's body after its frontmatter to select orchestrator and subagent models and effort. It implements only that plan task and may dispatch subagents for implementation subtasks within its scope. It leaves changes uncommitted and returns status, base SHA, branch, changed files, diff, checks/results, assumptions and blockers. Verify the diff, branch and worktree, and confirm no work can still modify it before proceeding.
- **Review:** after implementation verification, create a separate subthread on the same shared worktree and pass the task instruction, plan/spec paths, base SHA, exact implementation diff and related checks/results, assumptions and blockers. Invoke `test-driven-development` with the host-native skill command and explicitly authorize this thread to commit the accepted task result on the run branch only after findings are fixed or cleared and required checks pass. The reviewer returns findings, tests/results, changed files and final commit SHA, or blockers. Verify that the final commit contains the reviewed worktree state before accepting the task. Use `agent-architecture-audit` for architecture-sensitive tasks when available; record a gap if unavailable, blocking only when required by the plan.

Coordinate any fixes within the same task lifecycle. Never expand into another task. Honor model/effort stated in the opening lines of `task-implement` and higher-priority host instructions; record effective supported settings.

## Integration and closeout

After each review, verify the accepted task commit and evidence. If an integration target is provided for per-task integration, integrate only the exact accepted range without replacing remote work. Require explicit human authorization for main; divergence or non-fast-forward is `BLOCKED`, with no force-push or reset. Verify the target SHA. A failed integration leaves later tasks queued. After every plan task is accepted, open the plan's PR and follow the repository's review, gate, merge and cleanup rules on that exact head. The PR is plan-level, not task-level. If no integration target or PR is assigned, record the omission and accept locally.

If the assignment includes a PR, follow the repository’s review, gate, merge and cleanup rules on the exact head. For a map-master assignment, report readiness and wait for its merge go-ahead. Complete the authorized merge and cleanup; report any unfinished cleanup and do not remove a worktree while outstanding work could affect it.

## Decisions and reporting

Ask the human only for structural contradictions, missing or conflicting acceptance criteria that change scope, unreadable required artifacts, a missing workspace, or an unresolved subthread launch after safe checks. For ordinary choices, use the least-expansive interpretation and record assumptions. Respect previously granted authorization and applicable higher-priority requirements.

Report each task’s implementation diff and base SHA, accepted task commit, tests and results, findings, assumptions and blockers; include plan PR, integration and cleanup results when applicable. Do not report completion without the required plan, spec, accepted task commits, worktree and review evidence.
