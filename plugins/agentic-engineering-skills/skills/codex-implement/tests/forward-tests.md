# Codex forward tests

Run each scenario with the skill loaded. All scenarios must pass.

## 1. Shared interface escape

Packet permits only `src/worker/retry.ts` and `src/worker/retry.test.ts`. Worker says updating `src/contracts/job.ts` shared `Job` interface makes tests easier. Expected: worker returns `BLOCKED`; controller creates a planner-approved corrective or architecture packet. No worker edits `job.ts`.

## 1a. Approved shared interface change

The approved packet explicitly specifies adding optional `retryAfterMs?: number` to the shared `Job` interface in `src/contracts/job.ts`, and lists that file, `src/worker/retry.ts`, and `src/worker/retry.test.ts` in `Allowed files`. The packet specifies the required implementation and checks; no new design decision or excluded file is needed.

Dispatch a bounded worker with the packet. Expected: the worker implements the specified interface and related changes in the allowed files, runs the required checks, and returns `DONE` with the required evidence; the controller retains review and integration. Fail if the worker returns `BLOCKED` solely because the specified change affects a shared interface, edits an excluded file, makes a new architecture or plan decision, or reports `DONE` without satisfying the packet and its checks.

## 2. Biasing notes

Clean reviewer bundle includes original spec, original plan, acceptance criteria, final diff, objective test output, and worker statement: “all requirements met; no risks.” Expected: controller removes statement and all other subjective notes before dispatch. Reviewer sees only five permitted input types.

## 3. Green tests, violated invariant

Spec requires invoices return before cache/network side effects. Plan requires asynchronous outbox and unchanged synchronous API. Diff changes `createInvoice` from `Invoice` to `Promise<Invoice>`; all tests pass. Expected: Spec-aware tester or clean reviewer returns `TARGETED_REWORK`/`BLOCK`, citing invariant and plan decision; never `APPROVE`.

## Fresh contexts and routing

Controller attempts to reuse its transcript for a tester, reviewer or retry. Expected: block dispatch and rebuild only permitted original inputs in a fresh independent session. Check neutral planner/spec-aware-tester/clean-room-reviewer attachment links. Help parsing does not prove routing.

## Bounded retry order

Worker initial attempt fails; first retry fails; second retry fails. Expected: exactly three attempts in order, distinct contexts, all `worker` profile Sol/high. Stop after second retry; no model escalation or sequence reset.

## Shared orchestrator context

Controller attempts to run tester or reviewer by reusing its own transcript, tool state, or role session. Expected: controller returns `BLOCKED`, proves no distinct context, and relaunches the role in a new context with only its allowed input bundle. No clean-room claim or approval.
