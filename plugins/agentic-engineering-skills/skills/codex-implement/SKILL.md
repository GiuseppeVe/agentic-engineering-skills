---
name: codex-implement
description: Use when executing a substantial implementation plan with separate planning, bounded implementation packets, semantic test verification, and independent final approval; especially when workers might expand scope, passing tests may hide invariant violations, or model-specific role routing is required.
---

# Sol–Terra Clean Review

Use Sol for judgement. Use Terra for bounded edits. Approval needs a fresh Sol review; green tests alone never prove compliance.

## Model setup

Install `sol.config.toml` and `terra.config.toml` in `$CODEX_HOME`. Verify before dispatch:

```powershell
codex --strict-config -p sol --help
codex --strict-config -p terra --help
```

CLI role launch:

```powershell
codex -p sol "<planner, tester, or reviewer prompt>"
codex -p terra "<one worker packet>"
```

If the host supports per-agent model selection, bind Sol roles to `sol` and workers to `terra`. If it does not, keep contexts isolated and report: `Reduced assurance: role isolation verified; Sol/Terra model routing unavailable.` Never claim model routing without evidence.

## Required inputs

Controller collects original, unabridged: specification, implementation plan, acceptance criteria, approval boundaries, and repository context. Missing material that changes architecture or acceptance blocks packet planning. Missing original spec or plan blocks final approval.

## Roles

| Role | Profile | Responsibility |
|---|---|---|
| Sol planner | `agents/sol-planner.md` | Derive invariants, decisions, dependencies, and packets. |
| Terra worker | `agents/terra-worker.md` | Implement exactly one packet. |
| Sol spec-aware tester | `agents/sol-spec-aware-tester.md` | Read spec + plan; choose and assess test evidence. |
| Sol clean reviewer | `agents/sol-clean-room-reviewer.md` | Fresh, independent final approval gate. |

Planner, tester, reviewer, and every worker use separate contexts. Planner and worker never approve final integration.

## Packet dispatch

Planner emits every packet with: `id`, objective, scope, dependencies, allowed files, constraints, required tests, expected evidence, integration risks, and classification.

- **Independent:** send one packet to Terra; parallelize only when dependencies, file ownership, and shared contracts are disjoint.
- **Dependent:** wait for declared prerequisite evidence.
- **Architecture-sensitive or integration:** retain with Sol. Do not delegate architectural decisions to Terra.

Worker scope is binding. A required shared interface, contract, or non-allowed file means `BLOCKED`, never an edit. Controller either creates a new Sol-approved packet or changes the plan with required approval.

## Test and review loop

1. Terra returns change summary, tests/results, assumptions, deviations, and integration risks.
2. Sol tester starts fresh with original spec, original plan, acceptance criteria, final diff, test commands, and objective outputs. It validates tests against philosophy/invariants, not only coverage. It returns semantic findings to controller and a separate objective evidence bundle.
3. Material tester findings create narrow corrective packets. Run only affected Terra packets, then rerun relevant tests.
4. Start a **new** Sol clean reviewer. Its complete allowed input is original spec, original plan, acceptance criteria, final diff, and objective test output. Exclude worker notes, self-reviews, assumptions, tester reasoning, prior verdicts, and planner conclusions. If any are bundled, rebuild input before review.
5. Reviewer verdict is `APPROVE`, `TARGETED_REWORK`, or `BLOCK`. Every material finding cites spec/plan requirement plus code or test evidence. `TARGETED_REWORK` creates only affected corrective packets, then repeats testing and clean review on current diff.

Approval requires: required tests pass; every requirement maps to code/test evidence or explicit non-applicability; no material divergence remains. Passing tests are evidence, not proof.

## Red flags

| Red flag | Required action |
|---|---|
| Worker wants a shared-interface change | Block packet; Sol re-scopes or revises plan. |
| Reviewer receives worker/tester notes | Rebuild clean-room input without them. |
| Tests pass but an invariant conflicts | Request rework or block; cite invariant. |
| Reviewer lacks original spec or plan | Stop before approval. |
| Model selection unavailable | Continue isolated roles; declare reduced assurance. |

## Forward validation

Run `tests/forward-tests.md` after installing or changing this skill. Pass only when it prevents out-of-packet interface changes, excludes biasing notes, and catches a green-but-invariant-breaking diff.
