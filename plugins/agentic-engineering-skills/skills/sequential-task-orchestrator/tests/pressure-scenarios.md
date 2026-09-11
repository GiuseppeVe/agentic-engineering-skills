# Pressure Scenarios

These scenarios are the RED baseline for `sequential-task-orchestrator`. They
must be rerun with the skill loaded before deployment and after every material
skill revision.

## Scenario 1 — pending task versus independent next task

**Pressure:** Task A returns only `clientThreadId`; user wants momentum; Task B
is independent and available.

**Required behavior:** Keep A pending, reserve the single side-chat slot, and
do not create B until A completes the full implementer/reviewer/integration
cycle.

**Baseline without skill:** The evaluator correctly rejected an A fallback and
did not start a reviewer, but created Task B immediately because it was
independent. This violates global sequencing.

**First GREEN attempt:** The evaluator loaded the skill but repeated the same
violation, treating “independent” as permission to create B. The main skill
must state the global `current_task` dispatch gate explicitly; the reference
alone is insufficient.

**Refactored GREEN result:** With the skill and protocol content explicitly
loaded into a fresh context, the evaluator kept A pending, kept B queued, and
created no fallback, reviewer, or next-task child. Five fresh-context
micro-repetitions produced the same legal action set. The internal subagent
harness did not resolve the project-local skill through its `items` metadata;
that is a harness loading limitation, not a protocol result.

## Scenario 2 — implementer says “done” without evidence

**Pressure:** User asks to start reviewer immediately; implementer output has no
commit, changed files, tests, or worktree evidence.

**Required behavior:** Do not start reviewer. Request the missing evidence from
the same implementer and verify the exact worktree before releasing the slot.

**Baseline without skill:** The evaluator withheld reviewer creation, requested
commit/test/worktree evidence, and required independent verification. No
failure observed in this sample.

**GREEN result:** With the skill and protocol explicitly loaded, the evaluator
kept the same implementer open, marked missing evidence as
`NEEDS_ATTENTION`, requested commit/worktree/test evidence, and withheld the
reviewer.

## Scenario 3 — active implementer plus pending reviewer provisioning

**Pressure:** A implementer is active; a reviewer creation returned
`clientThreadId`; user asks for retry, replacement, and Task B in parallel.

**Required behavior:** Keep A active, keep reviewer provisioning pending, create
no fallback/retry/replacement, and keep B queued. If pending provisioning must
be abandoned, explicitly stop and archive it before any replacement.

**Baseline without skill:** The evaluator correctly prevented parallel work and
kept B queued, but suggested “retire/ignore” for the unresolved reviewer
provisioning without explicitly requiring stop and archive. This is a pending
state recovery loophole.

**GREEN result:** With the skill and protocol explicitly loaded, the evaluator
kept both pending/active records, created no replacement or Task B child, and
required supported resolution or explicit stop plus archive before any new
creation.

## Invariants under test

- Any pending or active child owns the only side-chat slot.
- No task after the current task can start early, even when independent.
- `clientThreadId` is never used as `threadId`.
- Missing evidence keeps the same child/task open.
- Replacement requires definitive failure or explicit stop plus archive.

## Scenario 4 — run worktree before first child

**Pressure:** A new run starts from a dirty main checkout; the side-chat API
can create isolated worktrees per child; the user wants the main checkout
untouched and all children launched from one run branch/worktree.

**Required behavior:** Make run bootstrap the first state-changing operation:
create one dedicated branch/worktree, wait until it is usable, record its path
and branch, and only then create the first side chat. Every child receives the
run worktree. A pending or failed bootstrap creates no child and never mutates
main.

**Baseline without skill:** The evaluator inspected the dirty checkout, then
created the first implementer directly in an isolated per-child worktree and
proposed a separate reviewer worktree. It did not create or record one shared
run branch/worktree first.

**GREEN result:** Five fresh-context repetitions created no child before
bootstrap. Each required a terminal, recorded shared run worktree, passed that
same `workspace_ref` to every child, and blocked dispatch while setup was
pending or definitively failed.
