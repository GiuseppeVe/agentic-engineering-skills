---
name: plan-implement
description: Coordinate an approved implementation plan using slice-implementer subagents, L1-L3 verification, high-risk review checkpoints, and a single plan PR.
---

# Plan Implement

The main thread coordinates an approved implementation plan from its specification and plan, plus a contracts map when available. It manages slice-implementer and clean-room review subagents or subordinate threads; it does not implement task code itself. Use the lightest workspace and tracking model that keeps concurrent mutations isolated and the run verifiable.

## Slice formation and dispatch

1. Follow `## Slice N:` boundaries declared in the plan when present; otherwise group contiguous tasks touching the same module or area into one coherent slice. Keep slices disjoint in file ownership and shared-contract surfaces before running them in parallel in isolated worktrees.
2. Assign **one persistent slice-implementer subagent** per slice so context stays warm across contiguous tasks of that module. Do not add a nested sub-packet layer inside a slice.
3. Open each slice brief with the slice's expected outcome, then pass the exact task instructions, plan and spec paths, mapped `REQ-NNN` requirements, allowed files, risk level (`standard` or `high`), and [slice contract](references/slice-contract.md). Resolve any source disagreement on behavior or acceptance before dispatch.
4. Select role-appropriate models and reasoning effort only from options available in the host, plan, or operator workspace configuration; keep high-risk or architecture-sensitive slices on a high-reasoning profile and record effective routing.

## Verification, checkpoints, and commits

- **Standard slices (`risk: standard`):** the slice-implementer subagent follows `test-driven-development` and the repository's deterministic L1–L3 checks, then hands back an uncommitted diff with objective check evidence. `plan-implement` verifies the diff, `REQ-NNN` coverage, and `final_state` checks, and commits the accepted slice to the plan branch when commit authority is granted.
- **High-risk slices (`risk: high` or shared-contract changes):** before accepting and committing the slice, dispatch a separate fresh-context clean-room review subagent using the host's native code-review capability. Pass only the slice's expected outcome (with any approved amendments), task instructions, plan and spec paths, exact diff, and objective command evidence; exclude implementer conclusions. Resolve valid findings through the slice implementer (or authorized fixer), rerun affected `final_state` checks, and commit only after acceptance.
- **Plan PR phase (once on the integrated head):** after all slices are accepted and the plan's expected outcome is verified on the integrated candidate head, run [PR phase](../development-process/references/daily-workflow.md#pr-phase) once — host native review of the full diff + `simplify` (and `cleaning-repo-with-knip` when warranted) → fixes in one commit → full gates once on the frozen head → delta review if code changed → mark ready.

## Programme coordination and references

Process rules live in one place; this skill and its briefs point to them and do not restate them: [Daily workflow](../development-process/references/daily-workflow.md) (`Verification` and `PR Phase`) and [Program orchestration](../development-process/references/program-orchestration.md) (`Run Conduct`, `Plan and Package Lifecycle`, and `Plans and Convergence Limits`).

- **Required:** read [runtime protocol](references/runtime-protocol.md) before dispatch or resume; pass [slice contract](references/slice-contract.md) to every slice-implementer subagent.
- When assigned by a master (`coordinating-implementation-plans`) or resuming as its subthread, read [reporting to the master](references/reporting-to-master.md) and [programme messages](references/programme-messages.md) at launch and after resume. When given a [plan mandate](references/plan-mandate.md), reread it at launch and after resume, pass its path and your reachable address to slice subagents, and never choose or drop gates.
- When the owner or plan explicitly routes an implementation slice to DeepSeek/Vibe, consult [T3 DeepSeek routing](references/t3-deepseek-routing.md) and [DeepSeek Vibe execution profile](references/deepseek-vibe-profile.md) before checking tools or dispatching.
