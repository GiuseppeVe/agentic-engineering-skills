---
name: sequential-task-worker
description: Implement one assigned task for a sequential run.
license: MIT
---

# Sequential Task Worker

Implement one task from an approved plan in the supplied run worktree. This
is the worker procedure, not an orchestration or independent approval cycle.
It works with any model that can use the required repository tools; model and
effort selection belong to the caller, not this skill.

## Inputs

Read the task ID/selector, original plan, original spec and exact run worktree
passed in the dispatch prompt. Follow root and relevant nested repository
instructions. Obtain scope, dependencies, constraints, acceptance criteria and
required checks from those artifacts, not from a guessed implementation plan.
Missing scope or conflicting acceptance criteria that prevent a bounded change
mean `BLOCKED`; state the missing information or decision rather than invent it.

## Boundaries

- Implement only the selected task and its directly necessary tests. Respect
  any file allowlist and ownership restrictions in the approved task.
- Do not spawn agents, schedule another task, or start a separate planner,
  tester or reviewer workflow. Do not invoke a full implementation orchestrator.
- Scheduling, review, integration and acceptance belong to the parent.
  Your completion report is implementation evidence, not task acceptance.
- Preserve unrelated staged, unstaged and untracked work. Never reset, clean,
  stash or include another task's changes to make the worktree appear clean.
- Architectural or product-behavior ambiguity, a required change outside task
  scope, or a permission denial means `BLOCKED`. Do not bypass the boundary.
- Do not push, merge, open a PR, deploy or perform destructive external actions.
  Local commits are allowed only within the run's granted authority.

## Procedure

1. Read the selected task and its spec, inspect branch/HEAD/worktree state,
   then inspect the involved implementation, callers and relevant tests.
   Verify dependency evidence when the task requires it; do not implement
   missing prerequisites or adjacent tasks yourself.
2. Use the repository's test-first procedure and `test-driven-development`
   when applicable: observe a relevant RED failure, implement the bounded
   change, then observe GREEN and run affected regressions. Reuse valid RED
   evidence from this same task/revision when resuming. Report any applicable
   approved exception; do not invent passing output or infer it from compilation.
3. Reuse the existing implementation path. Keep changes within approved
   scope; do not alter the plan or resolve an architectural decision yourself.
4. Run task-required checks plus directly affected checks identified from
   repository guidance and manifests. Record commands, exit codes, relevant
   output and any skipped/unavailable checks. Separate baseline failures from
   introduced failures using actual baseline evidence. Required failing or
   unverified checks prevent a `DONE` report.
5. Inspect the final diff and account for changed files. If local commit
   authority was granted, commit only this task's verified changes and record
   the commit SHA. Otherwise report the exact diff/HEAD and missing authority;
   do not claim the parent's committed-implementation gate has passed.
6. Return the evidence below. Stop; the parent decides review and acceptance.

## Return

```text
Status: DONE | BLOCKED | FAILED
Task:
Starting revision:
Commit: <full SHA, or NOT_COMMITTED with reason>
Changed files:
Tests: <command, exit code, relevant result and evidence path>
RED/GREEN evidence or approved exception:
Assumptions/deviations:
Blockers and unverified checks:
```

`DONE` means the assigned implementation and required checks are complete;
it never means independently reviewed, integrated, published or deployed.
