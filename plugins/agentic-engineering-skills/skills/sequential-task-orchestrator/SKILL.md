---
name: sequential-task-orchestrator
description: Use when executing an ordered implementation plan through separate implementation and review subthreads, with strict sequencing, commit verification and resumable run state.
---

# Sequential Task Orchestrator

The main thread sets up and coordinates an ordered implementation workflow. It receives the plan and spec, plus a contracts map when available, and creates one shared run worktree. It manages visible, subordinate subthreads; it does not implement or review task code itself.

For each task, create an implementation subthread using the available implementation skill in bounded worker mode, followed by a distinct review subthread using `test-driven-development` skill. The orchestrator monitors progress, verifies evidence, coordinates fixes and integration, and reports the outcome.

**Required:** read [runtime protocol](references/runtime-protocol.md) before dispatch or resume; follow it for run state, sequencing, verification, integration and closeout.
