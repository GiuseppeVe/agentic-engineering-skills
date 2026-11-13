---
name: plan-orchestrator
description: Use when orchestrating an implementation plan by invoking one task-implement thread and one separate review thread per task, respecting dependencies, evidence and commit boundaries without imposing a global state machine.
---

# Plan Orchestrator

The main thread coordinates an implementation workflow from the plan and spec, plus a contracts map when available. It manages visible, subordinate subthreads; it does not implement or review task code itself. Use the lightest workspace and tracking model that keeps concurrent mutations isolated and the run verifiable.

The code your implementing through your subthreads must work - as the plan and spec suppose it to work - at the end of the run implementation, so verify wether it works or not. If not fix and make it working before claiming that the implementation is done.

For each ready task, invoke `task-implement` with the host-native skill command, plan path, spec path, and exact task instruction. Read the first five lines of its body after the frontmatter to select the orchestrator and subagent models and effort. The implementation thread leaves its changes uncommitted and returns facts and evidence using the shared result contract. Verify its workspace and that no work can still modify it, then create a distinct clean-room review subthread and invoke `test-driven-development` with the host-native skill command, original task instruction, any parent- or owner-approved task amendments, plan/spec paths, exact diff, and objective command evidence. Exclude implementer conclusions and prior verdicts from the reviewer packet. The reviewer verifies criteria, fixes in-scope problems and reruns required checks; it commits only when task-commit authority exists. Verify the final reviewed state and decide task acceptance under the runtime protocol. Independent ready tasks may proceed concurrently only in isolated workspaces with clear ownership and integration order. Open a plan PR only when assigned and authorized, after all plan tasks are accepted and plan completion criteria are met; otherwise report local readiness and the omission.

**Required:** read [runtime protocol](references/runtime-protocol.md) before dispatch or resume; follow it for dependency selection, verification, integration and closeout.
