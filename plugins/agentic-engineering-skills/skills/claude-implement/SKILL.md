---
name: claude-implement
description: Use when executing a substantial implementation plan with separate planning, bounded implementation packets, semantic test verification, and independent final approval; especially when workers might expand scope, passing tests may hide invariant violations, or model-specific role routing is required.
---

# Claude Clean Review

Use Opus 5.5 for planning and review, Sonnet 5.5 for bounded edits. Approval needs a fresh independent review; green tests alone never prove compliance.

## Model setup

Use full model IDs and explicit effort for each fresh independent CLI session:

| Role | Model | Effort |
|---|---|---|
| Planner | `claude-opus-5-5` | `medium` |
| Spec-aware tester, clean-room reviewer | `claude-opus-5-5` | `high` |
| Existing bounded packet Terra worker | `claude-sonnet-5-5` | `high` |

The Terra worker retains its bounded-packet high-effort exception; generic workers use Sonnet/medium in the host configuration. Markdown attachments below are role contracts, not automatic native-agent registration. Before using `--agent`, install the matching native definitions separately. Always pass the complete attachment and only its allowed input bundle.

```powershell
claude -p --agent planner --model claude-opus-5-5 --effort medium "<planner attachment and allowed inputs>"
claude -p --agent spec-aware-tester --model claude-opus-5-5 --effort high "<tester attachment and allowed inputs>"
claude -p --agent clean-room-reviewer --model claude-opus-5-5 --effort high "<reviewer attachment and allowed inputs>"
claude -p --agent terra-worker --model claude-sonnet-5-5 --effort high "<bounded worker attachment and one packet>"
```

Current CLI supports `--agent`, full model IDs and `--effort`. Help parsing alone is not discovery or runtime model/effort proof. Record effective host telemetry. If routing cannot be verified, preserve isolated contexts and report reduced assurance with exact evidence. Do not substitute another model silently.

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
| Terra worker | `agents/terra-worker.md` | Implement exactly one packet. |
| Spec-aware tester | `agents/spec-aware-tester.md` | Read spec + plan; choose and assess test evidence. |
| Clean reviewer | `agents/clean-room-reviewer.md` | Fresh, independent final approval gate. |

Planner, tester, reviewer, every worker, and controller/orchestrator use separate contexts. Planner and worker never approve final integration.

## Packet dispatch

Planner emits every packet with: `id`, objective, scope, dependencies, allowed files, constraints, required tests, expected evidence, integration risks, and classification.

- **Independent:** send one packet to Terra; parallelize only when dependencies, file ownership, and shared contracts are disjoint.
- **Dependent:** wait for declared prerequisite evidence.
- **Architecture-sensitive or integration:** retain with Opus. Do not delegate architectural decisions to Terra.

Worker scope is binding. A required shared interface, contract, or non-allowed file means `BLOCKED`, never an edit. Controller either creates a new Opus-approved packet or changes the plan with required approval.

## Test and review loop

1. Terra returns change summary, tests/results, assumptions, deviations, and integration risks.
2. Opus tester starts fresh with original spec, original plan, acceptance criteria, final diff, test commands, and objective outputs. It validates tests against philosophy/invariants, not only coverage. It returns semantic findings to controller and a separate objective evidence bundle.
3. Material tester findings create narrow corrective packets. Run only affected Terra packets, then rerun relevant tests.
4. Start a **new** Opus clean reviewer. Its complete allowed input is original spec, original plan, acceptance criteria, final diff, and objective test output. Exclude worker notes, self-reviews, assumptions, tester reasoning, prior verdicts, and planner conclusions. If any are bundled, rebuild input before review.
5. Reviewer verdict is `APPROVE`, `TARGETED_REWORK`, or `BLOCK`. Every material finding cites spec/plan requirement plus code or test evidence. `TARGETED_REWORK` creates only affected corrective packets, then repeats testing and clean review on current diff.

Approval requires: required tests pass; every requirement maps to code/test evidence or explicit non-applicability; no material divergence remains. Passing tests are evidence, not proof.

## Red flags

| Red flag | Required action |
|---|---|
| Worker wants a shared-interface change | Block packet; Opus re-scopes or revises plan. |
| Reviewer receives worker/tester notes | Rebuild clean-room input without them. |
| Tests pass but an invariant conflicts | Request rework or block; cite invariant. |
| Reviewer lacks original spec or plan | Stop before approval. |
| Model selection unavailable | Continue isolated roles; declare reduced assurance. |

## Forward validation

Run `tests/forward-tests.md` after installing or changing this skill. Pass only when it prevents out-of-packet interface changes, excludes biasing notes, and catches a green-but-invariant-breaking diff.
