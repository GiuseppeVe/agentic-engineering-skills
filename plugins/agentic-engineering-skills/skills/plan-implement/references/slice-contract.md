# Slice Contract

Contract for a slice-implementer subagent dispatched by `plan-implement`. It replaces a separate nested task/packet layer: one persistent subagent implements contiguous tasks of one module directly inside its assigned workspace.

## Scope and boundaries

- Start from the slice's expected outcome, task instructions, mapped `REQ-NNN` entries, allowed files, and referenced plan/spec sections. Read only the repository context needed for those decisions.
- Work directly inside the assigned slice without spawning nested sub-packet agents unless explicitly authorized by `plan-implement`.
- Scope is binding. If implementing a task requires editing an excluded file, changing a non-owned shared interface, or resolving a contradiction in scope, contracts, or acceptance criteria, pause that step and return `blocked` with the exact gap. Never silently expand scope. The same applies when a [behavior model](../../development-process/references/behavior-model.md) is given and the task needs a change to modelled behavior or reaches an event the model does not cover: return `blocked`, never record it as an assumption.
- Never infer permission to commit, push, open a PR, merge, deploy, or change global settings from a slice assignment. Leave verified changes uncommitted for `plan-implement` to verify and commit.

## Inner loop and verification

- Follow `test-driven-development`: write behavioral tests first (or establish a tight red repro command first for bug fixes), implement the smallest coherent change, and refactor while green.
- After each meaningful change, run the repository's fast L1–L3 checks for touched paths (typecheck, static analysis/lint, affected behavioral/contract/property tests), then all checks assigned to the slice.
- Apply [Verification](../../development-process/references/daily-workflow.md#verification): no green-washing (a single-test rerun never turns a failed suite green; skipped, timed-out, or excluded checks stay unverified), separate `process` RED from `final_state` checks bound to the final diff, and never invent or reassign a `REQ` deferral not stated in the plan.
- Preserve unrelated changes in the workspace.

## Lightweight slice handoff

Keep the return concise so agentic judgment is not buried under rigid ceremony. Report four factual items:

1. **Status:** `done`, `partial`, or `blocked` (`done` only when every `REQ` required of this slice has passing `final_state` evidence or an explicit spec/plan `not applicable` basis; missing required checks or unbacked deferrals make the status `partial` or `blocked`).
2. **Requirements and checks:** each mapped `REQ-NNN` (satisfied or open, with plan-backed deferral if any) and the exact commands run with outcome, evidence class (`process` vs `final_state`), and environmental limitations.
3. **Diff state:** changed files, base SHA, branch, and worktree path (uncommitted diff ready for `plan-implement` verification and commit).
4. **Risks or blockers:** assumptions made, scope/contract conflicts, or L2 static-check candidates noticed during work.

*(This lightweight handoff is intentionally minimal; tighten structure only when real runs show concrete ambiguity.)*
