# Runtime Protocol

## Run bootstrap

On a new run, generate the run ID in memory and make run workspace bootstrap
the first state-changing operation. Before any child creation:

1. Create one dedicated branch and worktree from the intended starting
   revision, without cleaning, resetting, stashing, or committing unrelated
   changes in the main checkout.
2. Wait for setup to become terminal and usable.
3. Record `run_branch`, `run_worktree`, and `starting_revision`.
4. Set `workspace_ref` to the exact run worktree. Use it for orchestrator
   reads/writes, integration, and every child prompt.

The main checkout is not a run workspace. Do not replace the shared run
worktree with a separate worktree per child. If bootstrap is pending, create no
child and wait. If it fails definitively, create no child; mark the run
`BLOCKED` and report after safe checks.

Only a ready, recorded run worktree may transition into `READY` and permit the
first implementer.

## Inputs

Require:

```text
plan_ref
task_selector
project/workspace_ref
spec_ref per task, or a resolvable spec location in the plan
integration_target (optional; explicit remote sidebranch for incremental integration)
```

The worktree is the code input. Do not paste source code into child prompts.
Read plan/spec only to identify the selected task and construct the envelopes;
do not reinterpret domain behavior.

## Ledger

Initialize or resume one non-versioned ledger per run:

```text
<project>/.codex/orchestration/<run-id>.json
```

Track at least:

```text
run_id, plan_ref, task_queue, current_task, side_slot
task_state, threadId, hostId, clientThreadId
model, thinking
run_worktree, run_branch, starting_revision
worktree, branch, implementation_commit, review_commit
integration_target, integration_commit, integration_status
tests, findings, assumptions, blockers
```

Update ledger after child creation, provisioning transition, terminal result,
verification, archival, integration, and acceptance. On resume, reconcile
ledger with current thread/worktree state before creating anything.

## State machine

For each task, enforce:

```text
RUN_WORKTREE_PENDING
→ RUN_WORKTREE_READY
→ READY
→ IMPLEMENTER_PENDING
→ IMPLEMENTER_ACTIVE
→ IMPLEMENTATION_VERIFIED
→ REVIEWER_PENDING
→ REVIEWER_ACTIVE
→ REVIEW_VERIFIED
→ INTEGRATION
→ ACCEPTED
→ NEXT_TASK
```

Terminal alternatives: `NEEDS_ATTENTION`, `FAILED`, `BLOCKED`, `CANCELLED`.

Use one mutex:

```text
side_slot ∈ {free, implementer(task_id), reviewer(task_id)}
```

Set the slot before requesting child creation. A pending child occupies it.
Before any creation, assert the slot is free, no same-task child is
pending/active, all predecessor tasks are `ACCEPTED`, and the task has no
accepted implementation/review pair.

## Child lifecycle

Use a fresh user-visible side task for each role. Creation is non-blocking.
Record returned identifiers immediately.

Create side tasks with these fixed settings:

| Role | `model` | `thinking` |
| --- | --- | --- |
| Implementer | `gpt-5.6-terra` | `xhigh` |
| Reviewer | `gpt-5.6-sol` | `high` |

Record the selected `model` and `thinking` in the ledger before requesting
child creation. Do not omit or substitute these settings.

If creation returns ready `threadId` and `hostId`, mark the child active and
wait for terminal progress. If it returns only `clientThreadId`, mark
provisioning pending. Never pass that value to a tool requiring `threadId`.
Do not create a fallback, fork, retry, replacement, reviewer, or next task
while unresolved. Wait for a definitive ready, failed, cancelled, or stopped
result. If no definitive resolver exists, mark `BLOCKED`; do not guess.

Release the slot only after:

```text
terminal child state
→ final output read
→ commit/worktree evidence verified
→ child archived
```

Missing or ambiguous output means `NEEDS_ATTENTION`: send a follow-up to the
same child and keep the slot. A replacement requires definitive failure or
explicit stop plus archive, with the reason recorded in the ledger.

## Implementer envelope

Send exactly this role context plus task-specific references:

```text
Role: implementation worker.
Task: {{task_id}}.

Read:
- plan: {{plan_ref}}
- spec: {{spec_ref}}
- code/worktree: {{workspace_ref}}

Use $codex-implement in bounded worker mode.
Implement only this task. Do not implement adjacent tasks or review them.

Return:
- status
- commit
- changed files
- tests and results
- assumptions
- blockers
```

Do not add domain instructions, implementation strategy, or test commands.

## Implementation verification

Do not treat “done” as evidence. Read the final response, inspect exact
worktree/branch state, confirm commit/diff and changed files, and preserve test
commands/results reported by the child. If required evidence is absent, keep
the same child open with `NEEDS_ATTENTION`.

## Reviewer envelope

Start only after implementation verification and archival. Reviewer must use
the exact implementation commit/diff and worktree state:

```text
Role: test-gap reviewer and fixer.
Task: {{task_id}}.

Read again:
- plan: {{plan_ref}}
- spec: {{spec_ref}}
- code/worktree: {{workspace_ref}}
- implementation commit/diff: {{implementation_commit_or_diff}}

Use $test-gaps and $test-driven-development.
Use $agent-architecture-audit when the task or diff is architecture-sensitive.
Review and fix only this task and regressions directly caused by it.

Return:
- status
- findings
- tests and results
- changed files
- fix commit, if any
- unresolved blockers
```

Reviewer may add regression tests and fix findings within scope. It must not
silently expand into adjacent tasks.

## Integration and cross-task fixes

Integrate only after reviewer terminal output, verification, and archival:

```text
implementation commit
→ reviewer on exact state
→ optional reviewer fix commit
→ parent verifies current diff/evidence
→ incremental integration, when `integration_target` is configured
→ task ACCEPTED
```

For configured incremental integration:

1. Confirm `side_slot` is free and the reviewer is archived.
2. Fetch/read the integration target and verify it can accept the exact
   accepted run commit without replacing remote history. Non-fast-forward or
   divergence is `BLOCKED`; do not force-push, reset, or auto-rebase.
3. Push or merge only the accepted commit range into the explicit target.
   `main` is forbidden unless the human explicitly selected it.
4. Verify the target contains the accepted commit and record
   `integration_target`, resulting `integration_commit`, command/result, and
   any assumptions in the ledger.
5. Only then set the task `ACCEPTED` and advance `current_task`.

Integration failure leaves the task before `ACCEPTED` and blocks later task
dispatch. Release/promotion gates are separate: they may block release without
blocking a verified incremental integration into its non-main sidebranch.

Parent may handle a cross-task defect only while the side slot is free. Record
affected task IDs, changed files, tests, and resulting commit before resuming
the queue. Never mutate the worktree while a child is pending/active.

Even if a later task is independent, keep it queued until the current task is
`ACCEPTED`.

## Stop and report

Ask the human only for structural plan contradictions, missing/conflicting
acceptance criteria that change scope, unreadable artifacts, missing workspace,
or unresolved provisioning after safe checks. For ordinary ambiguity, choose
the least-expansive interpretation and record the assumption.

Final report must include one row per task:

```text
task_id | implementation commit | reviewer result | fix commit | tests | assumptions | blockers
```

State whether the selected range completed. Never claim completion when plan,
spec, commit, worktree, or review evidence is missing.
