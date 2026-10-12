---
name: codex-implement
description: Use when executing a substantial implementation plan with separate planning, bounded implementation packets, semantic test verification, and independent final approval; especially when workers might expand scope, passing tests may hide invariant violations, or model-specific role routing is required.
---

# Codex Clean Review

Use Sol/xhigh for judgement and Sol/high for bounded edits. Approval needs a fresh independent review; green tests alone never prove compliance.

## Model setup

Install minimal session layers `planner.config.toml`, `spec-aware-tester.config.toml`, `clean-room-reviewer.config.toml`, and `worker.config.toml` in `$CODEX_HOME`. Each contains only `model` and `model_reasoning_effort`; inherited permissions, provider and tools remain unchanged. These are CLI session profiles, separate from native `agents/*.toml` roles and Markdown attachments.

| Profile | Model | Reasoning effort |
|---|---|---|
| `planner` | `gpt-6.1-sol` | `xhigh` |
| `spec-aware-tester` | `gpt-6.1-sol` | `xhigh` |
| `clean-room-reviewer` | `gpt-6.1-sol` | `xhigh` |
| `worker` | `gpt-6.1-sol` | `high` |

CLI role launch in a fresh independent session; include the complete role attachment and its allowed input bundle in the prompt:

```powershell
codex -p planner "<planner attachment and allowed inputs>"
codex -p spec-aware-tester "<tester attachment and allowed inputs>"
codex -p clean-room-reviewer "<reviewer attachment and allowed inputs>"
codex -p worker "<bounded worker attachment and one packet>"
```

Current CLI `-p` layers `$CODEX_HOME/<name>.config.toml`; it does not select a native agent TOML or a `[profiles]` alias. Help parsing is not runtime discovery or routing proof. If routing cannot be verified, keep contexts isolated and report reduced assurance with exact evidence. Never claim model routing without host telemetry.

## Required inputs

Controller collects original, unabridged: specification, implementation plan, acceptance criteria, approval boundaries, and repository context. Missing material that changes architecture or acceptance blocks packet planning. Missing original spec or plan blocks final approval.

## Context isolation contract

- Controller/orchestrator is dispatch-only and runs in its own context. Never reuse its transcript, tool state, hidden context, memory, or role conversation for planner, worker, tester, reviewer, or retry.
- Launch every role and every retry in a new agent invocation/context. Pass only that role's allowed input bundle; shared artifacts do not mean shared context.
- Tester input is exactly: original specification, original plan, acceptance criteria, final diff, test commands, and objective test output. Exclude controller/orchestrator notes, planner reasoning, worker notes, self-assessments, assumptions, tester history, and prior verdicts.
- Reviewer input is exactly: original specification, original plan, acceptance criteria, final diff, and objective test output. Exclude controller/orchestrator notes, worker notes, self-assessments, assumptions, tester reasoning, prior verdicts, and planner conclusions.
- If distinct invocation/context cannot be evidenced, return `BLOCKED`; do not claim clean-room isolation or approve.

## Roles

| Role | Profile | Responsibility |
|---|---|---|
| Planner | `agents/planner.md` | Derive invariants, decisions, dependencies, and packets. |
| Bounded worker | `agents/terra-worker.md` | Implement exactly one packet. |
| Spec-aware tester | `agents/spec-aware-tester.md` | Read spec + plan; choose and assess test evidence. |
| Clean reviewer | `agents/clean-room-reviewer.md` | Fresh, independent final approval gate. |

Planner, tester, reviewer, every worker, and controller/orchestrator use separate contexts. Planner and worker never approve final integration.

## Packet dispatch

Planner emits every packet with: `id`, objective, scope, dependencies, allowed files, constraints, required tests, expected evidence, integration risks, and classification.

- **Independent:** send one packet to worker; parallelize only when dependencies, file ownership, and shared contracts are disjoint.
- **Dependent:** wait for declared prerequisite evidence.
- **Architecture-sensitive or integration:** retain with planner. Do not delegate architectural decisions to worker.

Worker scope is binding. A required shared interface, contract, or non-allowed file means `BLOCKED`, never an edit. Controller either creates a new planner-approved packet or changes the plan with required approval.

## Test and review loop

1. Worker returns change summary, tests/results, assumptions, deviations, and integration risks.
2. Spec-aware tester starts fresh with original spec, original plan, acceptance criteria, final diff, test commands, and objective outputs. It validates tests against philosophy/invariants, not only coverage. It returns semantic findings to controller and a separate objective evidence bundle.
3. Material tester findings create narrow corrective packets. Run only affected worker packets, then rerun relevant tests.
4. Start a **new** independent clean reviewer. Its complete allowed input is original spec, original plan, acceptance criteria, final diff, and objective test output. Exclude worker notes, self-reviews, assumptions, tester reasoning, prior verdicts, and planner conclusions. If any are bundled, rebuild input before review.
5. If a worker task fails, retry that same task once with `worker` (Sol/high) in a fresh context. If that retry fails, retry the task once more with `worker` (Sol/high) in another fresh context. Keep initial attempt, first retry, second retry in this order; do not skip or reset the sequence for the same task.
6. Reviewer verdict is `APPROVE`, `TARGETED_REWORK`, or `BLOCK`. Every material finding cites spec/plan requirement plus code or test evidence. `TARGETED_REWORK` creates only affected corrective packets, then repeats testing and clean review on current diff.

Approval requires: required tests pass; every requirement maps to code/test evidence or explicit non-applicability; no material divergence remains. Passing tests are evidence, not proof.

## Red flags

| Red flag | Required action |
|---|---|
| Worker wants a shared-interface change | Block packet; planner re-scopes or revises plan. |
| Reviewer receives worker/tester notes | Rebuild clean-room input without them. |
| Tests pass but an invariant conflicts | Request rework or block; cite invariant. |
| Reviewer lacks original spec or plan | Stop before approval. |
| Model selection unavailable | Continue isolated roles; declare reduced assurance. |

## Forward validation

Run `tests/forward-tests.md` after installing or changing this skill. Pass only when it prevents out-of-packet interface changes, excludes biasing notes, and catches a green-but-invariant-breaking diff.
