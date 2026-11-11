---
name: plan-orchestrator
description: Use when orchestrating an ordered implementation plan by invoking one task-implement thread and one separate review thread per task, with strict sequencing, commit verification and resumable run state.
---

# Plan Orchestrator

The main thread sets up and coordinates an ordered implementation workflow. It receives the plan and spec, plus a contracts map when available, and creates one shared run worktree. It manages visible, subordinate subthreads; it does not implement or review task code itself.

For each task, invoke the `task-implement` skill with the host-native skill command, plan path, spec path, and exact task instruction. Read the first five lines of its body after the frontmatter to select the orchestrator and subagent models and effort. The implementation thread leaves its changes uncommitted and returns the base SHA, diff, checks and results, assumptions, and blockers. Verify the shared worktree and that no work can still modify it, then create a distinct review subthread and invoke `test-driven-development` with its host-native skill command, the same task instruction, plan/spec paths, and implementation evidence. The reviewer identifies and fixes in-scope problems, reruns required checks, and commits the accepted task result to the run branch. Verify that commit before accepting the task. Open the plan PR only after all plan tasks are accepted.

**Required:** read [runtime protocol](references/runtime-protocol.md) before dispatch or resume; follow it for run state, sequencing, verification, integration and closeout.
