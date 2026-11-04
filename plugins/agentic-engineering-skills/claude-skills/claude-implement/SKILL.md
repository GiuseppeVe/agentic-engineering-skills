---
name: claude-implement
description: Use when the user explicitly requests Opus for a substantial implementation task, complex development plan, or independent implementation review. Also use when explicitly dispatched as a bounded worker for one packet.
---

# Claude Implement

## Bounded worker mode

When explicitly dispatched as a bounded worker, read [the worker contract](agents/worker.md) and the assigned packet. Work in the exact shared worktree and branch supplied by the parent; do not create another worktree. Implement one assigned packet within its allowed files and existing contract, run its required checks and return the worker contract's evidence to the parent. Commit only with the required authorization on the supplied branch; when a required commit is prohibited or cannot be verified, return `BLOCKED` with the available evidence. Do not invoke the controller, planner, tester or clean-review workflow; the parent coordinates review and integration. Respect the hard boundary rule below and all higher-priority user, repository, and runtime instructions. After completing this mode, return to the parent; the remaining sections apply only to controller mode. For all other invocations, use controller mode.

## Controller mode

Use Opus 5.5 as the primary reasoning authority for complex implementation work. Rely on its judgment for decomposition, architecture, integration, testing strategy, and independent review; delegate only bounded implementation subtasks when that improves execution.

## Required reading

Before planning, read `references/implementation-philosophy.md` in full and treat it as normative. Read the other references only when their subject becomes relevant:

- `references/agent-roles.md` before delegation or review assignment;
- `references/packet-contract.md` before planning packets or parallel work;
- `references/work-isolation.md` before dispatching code-writing tasks;
- `references/review-protocol.md` before integration or final approval;
- `references/model-routing.md` before dispatching any role;
- `references/distribution.md` before promoting or distributing the reviewed tree.

## Required inputs

Collect the original, unabridged user-provided specification, implementation plan, acceptance criteria, approval boundaries, and repository context. Missing material that changes architecture or acceptance blocks planning. Missing the original specification or plan blocks final approval.

## Hard boundary rule

Never read, write, modify, execute, or inspect anything outside the assigned project, repository, worktree, or sandbox boundaries unless the user explicitly authorizes that specific external access. Treat any required boundary crossing as `BLOCKED`; state what access is needed and why, and do not proceed by assumption.

## Authority and execution

Opus owns planning, architectural judgment, integration decisions, semantic verification, and independent review. Opus may implement work directly when that is the clearest or safest path.

Use worker only for clearly scoped, low-to-moderate complexity implementation subtasks with explicit acceptance criteria and a concrete verification method. worker returns `BLOCKED` when architectural judgment, scope expansion, ownership conflict, or unresolved ambiguity is required.

Only the controller may modify the integration branch. Use isolated sibling worktrees for independent writers when supported; otherwise serialize code-writing work and report reduced assurance.

## Context isolation contract

- The Opus controller may plan, implement, and integrate within the authorized scope. Delegated roles and independent review run in separate contexts; never reuse the controller's transcript, tool state, hidden context, memory, or role conversation for them.
- Launch every delegated role and every retry in a new agent invocation/context. Pass only that role's allowed input bundle; shared artifacts do not mean shared context.
- Tester input is exactly: original specification, original plan, acceptance criteria, final diff, test commands, and objective test output. Exclude controller/orchestrator notes, planner reasoning, worker notes, self-assessments, assumptions, tester history, and prior verdicts.
- Reviewer input is exactly: original specification, original plan, acceptance criteria, final diff, and objective test output. Exclude controller/orchestrator notes, worker notes, self-assessments, assumptions, tester reasoning, prior verdicts, and planner conclusions.
- If distinct invocation/context cannot be evidenced, return `BLOCKED`; do not claim clean-room isolation or approve.

Plan bounded work with explicit scope, dependencies, acceptance criteria, tests, risks, assumptions, and evidence. Integrate completed work in dependency order and verify each meaningful group of changes.

Any failed test or material finding blocks progress until corrected and reverified. Only a fresh clean reviewer may grant final approval against the original specification, acceptance criteria, final diff, and objective test results.

## Completion and cleanup

Before completion, verify that every distributed copy matches the reviewed version and that required runtime checks pass. Keep failed worktrees when needed for diagnosis; remove completed or abandoned worktrees only after recording their outcome. Deleting local or remote branches always requires explicit operator action.
