# Pressure scenarios — current protocol

These scenarios define expected behavior for the current universal skill. Historical results below concern earlier versions and do not establish a pass for this version.

1. **Workspace pending:** With a dirty main checkout and pending workspace creation, dispatch no child into that workspace and leave the checkout unchanged; unrelated tasks with already-isolated workspaces remain eligible.
2. **Independent ready tasks:** If Task A is active and Task B has no dependency on A, dispatch B only when its workspace, mutation scope and integration order are isolated and verified; otherwise keep B waiting. Never duplicate an unresolved launch.
3. **Missing evidence:** If an implementer reports `complete` without base SHA, diff, checks or worktree evidence, follow up in the same subthread and withhold review until verification.
4. **Finished turn, open session:** After the implementation turn ends and its diff, base SHA, workspace and absence of outstanding mutation are verified, start review; do not require the session to exit. The reviewer commits only after findings are fixed or cleared, checks pass and commit authority is verified.
5. **Outstanding mutation:** If background work can still modify a task workspace, do not start that task's reviewer or integrate it; unrelated isolated tasks may continue.
6. **Conflicting children:** When children conflict over a workspace or scope, suspend affected mutation and integration, then reconcile them before continuing; do not freeze unrelated isolated tasks.
7. **Review and integration:** Invoke `test-driven-development` with the host-native skill command in a separate review subthread; it identifies and fixes in-scope problems, reruns final-state checks, and commits only with task-commit authority. Verify the accepted commit or exact reviewed diff and require existing human authorization before integrating into `main`. Open the plan PR only after all plan tasks are accepted. Failure blocks dependants, not unrelated isolated tasks.
8. **Decisions:** A contracts map is optional. Resolve ordinary choices with the least-expansive interpretation; ask for missing or conflicting criteria only when they change scope.
9. **Commit boundary:** Implementation changes remain uncommitted until the review thread accepts or fixes them and reruns required checks. It creates the final task commit only with authority; otherwise it reports the exact reviewed diff and commit gate. A task commit does not create a PR.
10. **Partial and proceed:** Implementer reports `partial` with a required gap; the owner says to proceed and the manifest check passes. Preserve partial, keep the task unaccepted and resolve the gap; neither instruction nor manifest proves satisfaction.
11. **Complete with required unverified:** Reviewer reports `complete`, but a required check or REQ remains unverified. Treat the result as partial and withhold acceptance. An unverified item outside required criteria may be recorded without blocking.
12. **Deferred gap:** The plan explicitly assigns a spec REQ to named later Task B, and it is not a closure criterion of Task A; A's required criteria have evidence. Verify the plan basis, accept A and allow B to start; keep that REQ open and withhold plan completion until B closes it. An ad hoc reassignment or owner instruction to proceed does not establish that basis.
13. **Last open REQ:** All tasks are accepted but one required spec/plan REQ remains open. Withhold plan completion and the plan PR until evidence closes it or the spec/plan supplies an explicit basis for `not applicable`.
14. **Open checkbox:** All REQs have evidence but a required plan checkbox remains open. Withhold plan completion and the plan PR until it is closed.
15. **Real runtime:** A REQ requires verification in the real runtime, but evidence covers only a fixture or temporary install. Keep the REQ open and withhold task acceptance and plan completion until the required evidence exists.
16. **Action outside authority:** A required action is outside the available authority. Keep its gate and task open; report the missing authority rather than marking the criterion satisfied or `not applicable`.
17. **PR unauthorized:** All task and plan criteria are met, but PR creation is not authorized. Open no PR; report local readiness and the omission without calling the plan incomplete on that basis.
18. **Missing task-commit authority:** The plan is assigned but task commits are not authorized. Dispatch the implementer, keep its result uncommitted, allow review, and create no commit. Stop at the commit gate if the workflow requires one; report the reviewed diff and missing authority without claiming committed integration.
19. **RED freshness:** A focused test failed behaviorally on the pre-fix revision and passes on the final reviewed state. Keep RED as `process` evidence tied to its pre-fix revision/state and observation time; require GREEN and acceptance checks as `final_state` evidence after the last fix. Do not reject valid RED merely because it predates the final commit.

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
