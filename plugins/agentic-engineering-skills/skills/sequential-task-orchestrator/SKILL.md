---
name: sequential-task-orchestrator
description: Use when a user asks Codex to execute an ordered implementation plan through one bounded worker and one independent review cycle per task, with strict sequencing, pending-thread safety, commit verification, and resumable run state.
---

# Sequential Task Orchestrator

Dispatch-only coordinator. Orchestrator knows task order, artifact references,
side-chat lifecycle, commit/worktree evidence, ledger state, and reporting. It
does not know product domain, implementation strategy, test commands, or the
internal behavior of child skills.

**REQUIRED:** Read [references/runtime-protocol.md](references/runtime-protocol.md)
before dispatching or resuming a run.

## Run bootstrap

At the start of every new run, bootstrap the run workspace before dispatching
any child:

1. Create one dedicated branch and worktree for the run from the intended
   starting revision.
2. Wait until branch/worktree setup is terminal and usable; record the branch,
   path, and starting revision.
3. Set `workspace_ref` to that exact run worktree for all orchestration,
   integration, and child prompts.
4. Only then create the first implementer.

The main checkout stays untouched during the run. Do not use a per-child
worktree as a substitute for the shared run worktree. If setup is pending, wait
without creating children. If it fails definitively, create no child and mark
the run `BLOCKED`/report it after safe checks.

## Fixed child skills

- Implementer: `$codex-implement` in bounded worker mode. Launch its side chat
  with model `gpt-5.6-terra` and thinking `xhigh`.
- Reviewer: `$test-gaps` and `$test-driven-development`. Launch its side chat
  with model `gpt-5.6-sol` and thinking `high`.
- Optional reviewer audit: `$agent-architecture-audit` when the reviewer finds
  architecture-sensitive boundaries, shared contracts, persistence,
  concurrency, or cross-module integration.

Do not make these skills run inputs. Do not copy their instructions into child
prompts. Pass plan, spec, worktree, and exact implementation diff/commit.

## Hard invariants

- No child exists before the shared run branch/worktree is ready and recorded;
  main checkout is never the run `workspace_ref`.
- One side-chat slot only: implementer **or** reviewer, never both.
- Pending provisioning owns the slot. `clientThreadId` is not `threadId`.
- Never create a fallback, retry, fork, replacement, reviewer, or next task
  while a same-task side chat is pending/active.
- Never start a later task merely because it is independent.
- Release the slot only after terminal output, commit/worktree verification,
  and archival.
- Missing evidence keeps the same child in `NEEDS_ATTENTION`.
- Reviewer starts only after implementation verification.
- When an `integration_target` is configured, next task starts only after
  review, fixes, incremental integration, and acceptance reach `ACCEPTED`.
- Record every transition and assumption in the runtime ledger.

## Incremental integration

When the run defines an integration target, integrate every accepted task
before dispatching its successor. Treat this as a task gate, not end-of-run
cleanup.

- Configure an explicit non-main target, for example
  `origin/codex/alfe-agent-restyle`. Never infer `main` as a target; it needs
  explicit human authorization.
- Integrate only after reviewer terminal output, parent verification, and
  reviewer archival. No child may be pending or active during integration.
- First verify that the target can receive the accepted run commit without
  overwriting remote work. A diverged or non-fast-forward target is `BLOCKED`;
  do not force-push, reset, or guess a reconciliation.
- Push or merge the exact accepted commit range into the target, verify the
  remote target contains the accepted commit, then record its resulting SHA.
- If integration fails, keep the task out of `ACCEPTED`, record the failure,
  and do not start the next task.

If no integration target was supplied, record that deliberate omission and
continue with local acceptance. Release/promotion gates remain separate from
incremental integration.

## Dispatch gate

Treat the run as a single-task queue. `current_task` is the only task eligible
for child creation. Every later task is `QUEUED`, even when independent or
ready to work.

Before every `create_thread` call, evaluate these gates in order:

1. requested task must equal `current_task`;
2. `side_slot` must be `free`;
3. no child for that task may be pending or active;
4. predecessor tasks must be `ACCEPTED`.

If any gate fails, do not create any child. Keep later tasks queued. Advance
`current_task` only after implementation, review, fixes, integration, and
acceptance complete. This is a global queue gate, not a per-task optimization.

Ask the human only for structural contradictions, unreadable required
artifacts, missing target workspace, or unresolved side-chat provisioning.
Choose least-expansive ordinary decisions and record them.

Return a self-contained report with implementation/review commits, tests,
findings, fixes, assumptions, blockers, and per-task outcome.
