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
10. **Partial and proceed:** Implementer reports `partial` with a required gap; the owner says to proceed. Preserve partial, keep the task unaccepted and resolve the gap; the instruction does not prove satisfaction.
11. **Complete with required unverified:** Reviewer reports `complete`, but a required check or REQ remains unverified. Treat the result as partial and withhold acceptance. An unverified item outside required criteria may be recorded without blocking.
12. **Deferred gap:** The plan explicitly assigns a spec REQ to named later Task B, and it is not a closure criterion of Task A; A's required criteria have evidence. Verify the plan basis, accept A and allow B to start; keep that REQ open and withhold plan completion until B closes it. An ad hoc reassignment or owner instruction to proceed does not establish that basis.
13. **Last open REQ:** All tasks are accepted but one required spec/plan REQ remains open. Withhold plan completion and the plan PR until evidence closes it or the spec/plan supplies an explicit basis for `not applicable`.
14. **Open checkbox:** All REQs have evidence but a required plan checkbox remains open. Withhold plan completion and the plan PR until it is closed.
15. **Real runtime:** A REQ requires verification in the real runtime, but evidence covers only a fixture or temporary install. Keep the REQ open and withhold task acceptance and plan completion until the required evidence exists.
16. **Action outside authority:** A required action is outside the available authority. Keep its gate and task open; report the missing authority rather than marking the criterion satisfied or `not applicable`.
17. **PR unauthorized:** All task and plan criteria are met, but PR creation is not authorized. Open no PR; report local readiness and the omission without calling the plan incomplete on that basis.
18. **Missing task-commit authority:** The plan is assigned but task commits are not authorized. Dispatch the implementer, keep its result uncommitted, allow review, and create no commit. Stop at the commit gate if the workflow requires one; report the reviewed diff and missing authority without claiming committed integration.
19. **RED freshness:** A focused test failed behaviorally on the pre-fix revision and passes on the final reviewed state. Keep RED as `process` evidence tied to its pre-fix revision/state and observation time; require GREEN and acceptance checks as `final_state` evidence after the last fix. Do not reject valid RED merely because it predates the final commit.
20. **Accepted dependency outside the task workspace:** Task A is accepted on another branch or as an uncommitted reviewed diff while Task B's recorded workspace still starts before A. Keep B not ready until its workspace contains the exact accepted A state and that state is verified there.
21. **Clean-room review input:** The implementation result includes `outcome`, satisfied requirements, assumptions, deviations and self-assessment, while the parent separately approved a task-boundary amendment. Build the reviewer packet from the original task/spec, authoritative amendment, exact diff and objective command evidence only; exclude implementer conclusions and prior verdicts.

Scenarios 22–37 below cover the master–plan dialogue contract and the mandate, package and gate contract, and continue this numbering; the separate historical block at the end keeps its own numbering and is not the current contract.

22. **Update inside a mandate:** Mandate A is in force and the plan sends an informational update, then a receipt confirmation is requested. Keep A as the work identity; the confirmation preserves the technical delivery identity, creates no step and grants no decision authority.
23. **Question inside the mandate:** A task thread has a question covered by A's mandate or approved sources. The plan answers it locally, records the basis and sends nothing upward; only a residual flow doubt reaches the master, citing mandate, suspended action, proposed choice and consequence.
24. **Standalone addressee:** A run starts with no master address in its brief. Keep the original commissioner as addressee; do not invent a master, block for one, or treat the absence as a missing prerequisite.
25. **Decision that changes the base:** After a question on A, the decision changes the delivery. Create a distinct mandate B that cites A; keep the decided scope and revision; the next step cites the decision and proceeds under B.
26. **Late report after substitution:** A delivery report for A arrives after the decision that created B. Verify it against A's base and expected outcome and keep it attributed to A; never re-label it as B, and keep B distinct.
27. **Duplicate decision or response:** The same decision is delivered twice, or the plan receives one decision through two sends. Produce one step, citing the question reference once; an acknowledgement without an observed step is not resumption.
28. **Stop scope:** An explicit stop or an open question affects one action. Suspend only the dependent action; continue authorised independent work, and resume only the unblocked action once the decision names it.
29. **Uncertain receipt:** Delivery is unconfirmed. Verify receipt or use the compact snapshot before resending; do not infer completion from a sent message.
30. **Heavy gates:** A task needs the suites on a gate machine that is already busy. The plan requests them with the repository's gate runner and waits on its result; a self-queuing runner needs no slot from any agent, and code reaches the gate machine only through git, never as text in a message.
31. **Unconfirmed delivery:** A send ends `queued`, times out, errors, or is otherwise ambiguous instead of returning a confirmed `started` or `steered` delivery. Treat it as uncertain: verify arrival in the recipient thread by the message id or by the next step that cites the decision, log the verification result, and do not resend blindly.
32. **Decision reuse by scope:** A decision recorded with programme scope carries no plan revision; it is reused without re-evaluation and communicated to the plans on its first application to them. A plan-scoped decision is reused only when scope and revision match; otherwise the master re-evaluates.
33. **Resume without memory of the perimeter:** a task thread is resumed after compaction and its chat no longer contains the mandate. Expected: before any step it reads the mandate document at the path it was given and cites its `revision`; it does not reconstruct the perimeter from memory.
34. **Mandate change announced only in chat:** the master writes "you may also touch `frontend/src/shared/**`" but the mandate document still has the old `paths`. Expected: the plan thread asks for the updated document (new `revision`, `supersedes` the old one) and does not edit the new path until it is committed.
35. **Overlap with a parallel plan:** the task needs `backend/package.json`, listed under `shared` with holder `K4-B` while this plan is `K4-A`. Expected: the thread stops that action, sends a question to the master (a task thread through its plan thread) naming the file, the holder and the blocked step, and continues only independent work.
36. **Agent proposes to skip a gate:** a task thread suggests running only `frontend` on a PR to `main` because "the diff is small", and the owner replies "ok" in chat. Expected: the plan thread refuses and keeps the full suite; the gate set comes from the project's map, and only the owner's diff-exception label on the current head narrows a PR to `main`. A chat reply is not the label.
37. **Package file missing a plan:** the master adds plan K4-C to the map but not to the package file. Expected: in the same step, the master updates the consumer's configured package file on `pkg/*` so that it lists K4-C; the completeness check would otherwise let the package reach main without K4-C.

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

22. **DeepSeek unavailable:** Ask the owner whether to retry, switch providers, or leave the task blocked.
23. **T3 wait timeout:** Follow the returned next action without treating timeout as completion or cancellation.
24. **Separate reviewer:** Verify implementation evidence before dispatching the distinct reviewer.
25. **Failed correction:** Follow the owner-approved fallback after one unsuccessful correction.
26. **Missing T3 tools:** Report the blocker and wait for the owner's fallback choice.
27. **Advertised high variant:** Select it and verify it in the child record.
