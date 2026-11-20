---
name: plan-orchestrator
description: Use when orchestrating an implementation plan by invoking one task-implement thread and one separate review thread per task, respecting dependencies, evidence and commit boundaries without imposing a global state machine.
---

# Plan Orchestrator

The main thread coordinates an implementation workflow from the plan and spec, plus a contracts map when available. It manages visible, subordinate subthreads; it does not implement or review task code itself. Use the lightest workspace and tracking model that keeps concurrent mutations isolated and the run verifiable.

For each ready task, start the implementation brief with the task's expected
outcome, then include the exact task instruction, plan and spec paths, and
applicable requirements. For an older plan without an outcome field, summarize
the assigned result from the task and its mapped requirements. If those sources
disagree on behavior or acceptance, resolve the gap before dispatch.

Select models and effort from the task-implement routing guidance. Invoke with the host-native skill command
`task-implement` and receive its uncommitted diff and evidence. Verify the
workspace and confirm the implementer has finished before starting review.

Start a separate clean-room `test-driven-development` review with the host-native skill command and the task's
expected outcome as amended by any approved amendment, the original task
instruction, those amendments,
the plan and spec paths, the exact diff, and objective command evidence.
Exclude implementer conclusions and prior verdicts. The reviewer verifies
the mapped requirements, fixes in-scope findings, reruns the final-state checks the
plan assigns to this task plus those affected by its fixes, verifies any RED
from its recorded evidence, and commits only with task-commit authority.

Follow the runtime protocol for task acceptance, parallel dispatch, integration,
and any authorized plan PR. Before claiming plan completion, verify the plan's
expected outcome on the integrated result.

When the owner or plan selects DeepSeek/Vibe for an implementation thread, read [T3 DeepSeek routing](references/t3-deepseek-routing.md) before checking tools or dispatching.

**Required:** read [runtime protocol](references/runtime-protocol.md) before dispatch or resume; follow it for dependency selection, verification, integration and closeout.
