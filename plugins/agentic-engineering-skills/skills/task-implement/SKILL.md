---
name: task-implement
description: Use when implementing exactly one assigned task from an approved plan, coordinating bounded implementation subagents, and verifying that task against its specification.
---

# Task Implement

When task materials do not specify compatible routing, Codex uses GPT-6.1 Sol/high for orchestration and GPT-6.1 Terra/high for implementation subagents; Claude Code uses Sonnet 5.5/high for orchestration and Sonnet 5.5/medium for implementation subagents. An explicit owner- or plan-selected available model and effort takes precedence; record effective routing.

## Purpose

Implement exactly one task assigned by a parent orchestrator. This thread owns decomposition and integration only inside that task's scope; it does not orchestrate other plan tasks. Its scope is implementation only and excludes review of the task's implementation.

## Inputs and scope

The parent provides only: the instruction for the assigned task, its implementation plan, the governing specification, and this skill. Use those materials to identify the task's acceptance criteria, dependencies, allowed files, constraints, required checks, and expected evidence. Read repository files and applicable repository instructions only as needed to execute the assigned task; do not request or assume other plan tasks or parent-thread context.

If the task materials are missing or contradict one another on scope, contracts, or acceptance, stop before expanding scope and report the precise gap to the parent. Never infer permission to commit, push, open a PR, merge, deploy, or change global settings from assignment to implement.

## Single-task orchestration

1. Inspect the assigned task's relevant files and current repository/worktree state. Keep the parent-provided task boundary fixed.
2. Break the assigned task into the smallest coherent implementation packets needed for parallel subagents. Delegate only when separate work can proceed with clear file ownership, interfaces, constraints, and acceptance criteria; otherwise implement directly. Read [packet-contract](references/packet-contract.md).
3. Keep decisions about the assigned task's architecture and integration with this orchestrator. Do not delegate or perform adjacent plan tasks.
4. Give each subagent only the assigned-task instruction and the relevant excerpts of the plan, specification, files, and checks. Require its change summary, commands and outcomes, assumptions, deviations, and remaining work.
5. Sequence dependent packets. Parallelize only disjoint work with no unresolved shared dependency.
6. If a packet requires changing an excluded file, a shared interface outside the assigned scope, or an unresolved contract, pause that packet and report the exact dependency to the parent. Resume only when the parent supplies an updated task boundary or decision.
7. Integrate packet results within the assigned task, resolve conflicts, and verify the integrated task against its acceptance criteria.

## Implementation and verification

Use focused tests before implementation when they can capture the required behavior. After each meaningful change, run the smallest relevant checks, then the required project gates for this task. Tests must verify specified behavior and invariants, not merely mirror the implementation.

Treat a failed check, missing prerequisite, or unverified criterion required of the current task as incomplete. Report the exact command, revision, outcome, and any environmental limitation. Mark a criterion not applicable only with an explicit basis in the specification or plan.

Preserve unrelated user changes. Follow repository rules for worktrees, branch names, staging, and cleanup. Perform only the external actions explicitly authorized by the user.

## Completion

Return the result when the turn ends; ending a turn does not imply success. Report facts and evidence for the parent, which decides acceptance. Use this result contract for implementation and TDD review:

- `outcome: complete | partial | blocked`: `complete` requires every criterion still required of the current task satisfied or explicitly not applicable and all required checks passed; use `partial` or `blocked` for an open or unverified criterion still required of this task, failed check, or missing prerequisite. Unverified items may accompany `complete` only when they are outside the current task's required criteria.
- `satisfied_requirements`: each criterion and its evidence, including any not-applicable criterion and its explicit spec/plan basis. `open_requirements`: each remaining requirement with reason and, when deferred, `deferred_to` and the plan basis. A globally required REQ explicitly assigned by the plan to a named later task remains globally unsatisfied but does not block the current task's outcome. Workers and reviewers cannot invent or reassign deferrals; without that plan basis, an open criterion required of this task makes the outcome `partial` or `blocked`. Identify other unverified items separately.
- `checks`: command, outcome, evidence class, revision or reproducible state, and environmental limitation where relevant. Use `process` for historical development evidence such as observed RED, recording the pre-fix revision/state, expected behavioral failure and observation time. Use `final_state` for evidence that supports acceptance, including GREEN/regression tests, lint, typecheck and review checks; rerun it after the last relevant fix and bind it to the final reviewed commit or exact uncommitted diff. Include assumptions, deviations, blockers, changed files, and revision; distinguish local, committed, published, and integrated work.

For an uncommitted result, identify base SHA, branch, worktree, and diff. A reviewer verifies the task criteria; the plan orchestrator decides acceptance.
