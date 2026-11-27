---
name: development-process
description: General engineering process rules — mandate and Git boundaries, L1-L3 verification, PR phase, closing report, and multi-plan orchestration.
---

# Development Process

Single source of portable process rules. These are guidance: no session hook enforces them. Other skills point here instead of restating them.

Read only the reference needed for the task:

- [Daily workflow](references/daily-workflow.md): mandate and Git boundaries, L1–L3 verification and anti-green-washing rules, PR phase, closing report, and process budget.
- [Program orchestration](references/program-orchestration.md): loaded only for multi-task plans or multi-package programmes — subagent delegation, run conduct, plan/package lifecycle, child delivery, and convergence limits.

Repository-specific instructions override where more specific: exact gate commands, status names, static-analysis configs, and document paths live in the receiving repository. Operator-local defaults (workspace index, machines, model routing, report language) live in the operator workspace, not here.

For a repository's linked worktree inventory and safe removal of merged clean worktrees: `node scripts/worktrees.mjs` (read-only; `--remove-merged --yes` removes only merged clean worktrees and never deletes branches; see the standing cleanup authorization in `references/daily-workflow.md`).
