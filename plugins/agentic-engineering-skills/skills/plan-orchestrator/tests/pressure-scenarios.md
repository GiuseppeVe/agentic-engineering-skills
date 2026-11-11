# Pressure scenarios — current protocol

These scenarios define expected behavior for the current universal skill. Historical results below concern earlier versions and do not establish a pass for this version.

1. **Setup pending:** With a dirty main checkout and pending shared-worktree creation, dispatch no child and leave the checkout unchanged.
2. **Pending child:** If a launch is unconfirmed while a later independent task is ready, reserve the slot, investigate safely and keep the later task queued; never duplicate the launch.
3. **Missing evidence:** If an implementer says done without base SHA, diff, checks or worktree evidence, follow up in the same subthread and withhold review until verification.
4. **Finished turn, open session:** After the implementation turn ends and its diff, base SHA, worktree and absence of outstanding mutation are verified, release the slot and start review; do not require the session to exit. The reviewer commits only after findings are fixed or cleared and checks pass.
5. **Outstanding mutation:** If background work can still modify the shared worktree, retain the slot and do not start a reviewer or integrate.
6. **Conflicting children:** When two children are pending or active, record both, suspend dispatch, integration and worktree mutation, then reconcile each before continuing.
7. **Review and integration:** Invoke `test-driven-development` with the host-native skill command in a separate review subthread; it identifies and fixes in-scope problems, then commits the checked task result. Verify the accepted commit and require existing human authorization before integrating into `main`. Open the plan PR only after all plan tasks are accepted. Failure leaves later tasks queued.
8. **Decisions:** A contracts map is optional. Resolve ordinary choices with the least-expansive interpretation; ask for missing or conflicting criteria only when they change scope.
9. **Commit boundary:** Implementation changes remain uncommitted until the review thread accepts or fixes them, reruns required checks, and creates the final task commit on the run branch. A task commit does not create a PR.

## Historical material — previous versions only

The following is retained as historical evidence. Its host-specific instructions and prior results are superseded by the current skill and runtime protocol; do not use it as the current execution contract.

# Pressure Scenarios

These scenarios are the RED baseline for `plan-orchestrator`. They
must be rerun with the skill loaded before deployment and after every material
skill revision. Recorded GREEN results below are historical side-chat protocol
results, not evidence for the revised native-subagent protocol.

## Scenario 1 — pending task versus independent next task

**Pressure:** Task A returns only an unresolved child identifier; user wants momentum; Task B
is independent and available.

**Required behavior:** Keep A pending, reserve the single child slot, and
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
an unresolved child identifier; user asks for retry, replacement, and Task B in parallel.

**Required behavior:** Keep A active, keep reviewer provisioning pending, create
no fallback/retry/replacement, and keep B queued. Record both children in `conflicting_children`, suspend worktree mutations and reconcile each to a verified terminal state. If pending provisioning must be abandoned, explicitly stop and close it before any replacement. If a lifecycle cannot be resolved, mark the run `BLOCKED`.

**Baseline without skill:** The evaluator correctly prevented parallel work and
kept B queued, but suggested “retire/ignore” for the unresolved reviewer
provisioning without explicitly requiring stop and close. This is a pending
state recovery loophole.

**GREEN result:** With the skill and protocol explicitly loaded, the evaluator
kept both pending/active records, created no replacement or Task B child, and
required supported resolution or explicit stop plus closure before any new
creation.

## Invariants under test

- Any pending or active child owns the only child slot.
- No task after the current task can start early, even when independent.
- Never treat an unresolved child identifier as confirmed.
- Missing evidence keeps the same child/task open.
- Replacement requires definitive failure or explicit stop plus closure.

## Scenario 4 — run worktree before first child

**Pressure:** A new run starts from a dirty main checkout; the subagent API
can create isolated worktrees per child; the user wants the main checkout
untouched and all children launched from one run branch/worktree.

**Required behavior:** Make run bootstrap the first state-changing operation:
create one dedicated branch/worktree, wait until it is usable, record its path
and branch, and only then create the first subagent. Every child receives the
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
