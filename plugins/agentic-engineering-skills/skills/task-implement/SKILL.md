---
name: task-implement
description: Use when implementing exactly one assigned task from an approved plan, coordinating bounded implementation subagents, and verifying that task against its specification.
---

# Task Implement

Codex: orchestrate with GPT-6.1 Sol/high; use GPT-6.1 Terra/high for implementation subagents.
Claude Code: orchestrate with Sonnet 5.5/high; use Sonnet 5.5/medium for implementation subagents.

## Purpose

Implement exactly one task assigned by a parent orchestrator. This thread owns decomposition and integration only inside that task's scope; it does not orchestrate other plan tasks. Its scope is implementation only and excludes review of the task's implementation.

## Inputs and scope

The parent provides only: the instruction for the assigned task, its implementation plan, the governing specification, and this skill. Use those materials to identify the task's acceptance criteria, dependencies, allowed files, constraints, required checks, and expected evidence. Read repository files and applicable repository instructions only as needed to execute the assigned task; do not request or assume other plan tasks or parent-thread context.

If the task materials are missing or contradict one another on scope, contracts, or acceptance, stop before expanding scope and report the precise gap to the parent. Never infer permission to commit, push, open a PR, merge, deploy, or change global settings from assignment to implement.

## Single-task orchestration

1. Inspect the assigned task's relevant files and current repository/worktree state. Keep the parent-provided task boundary fixed.
2. Break the task into the smallest coherent implementation packets needed for parallel subagents. Delegate only when separate work can proceed with clear file ownership, interfaces, constraints, and acceptance criteria. Read [the packet contract](references/packet-contract.md).
3. Keep decisions about the assigned task's architecture and integration with this orchestrator. Do not delegate or perform adjacent plan tasks.
4. Give each subagent only the assigned-task instruction and the relevant excerpts of the plan, specification, files, and checks. Require its change summary, commands and outcomes, assumptions, deviations, and remaining work.
5. Sequence dependent packets. Parallelize only disjoint work with no unresolved shared dependency.
6. If a packet requires changing an excluded file, a shared interface outside the assigned scope, or an unresolved contract, pause that packet and report the exact dependency to the parent. Resume only when the parent supplies an updated task boundary or decision.
7. Integrate packet results within the assigned task, resolve conflicts, and verify the integrated task against its acceptance criteria.

## Implementation and verification

Use focused tests before implementation when they can capture the required behavior. After each meaningful change, run the smallest relevant checks, then the required project gates for this task. Tests must verify specified behavior and invariants, not merely mirror the implementation.

Treat a failed check, missing prerequisite, or unverified requirement as incomplete. Report the exact command, revision, outcome, and any environmental limitation. Do not claim a requirement is satisfied without code or test evidence, or an explicit reason it does not apply.

Preserve unrelated user changes. Follow repository rules for worktrees, branch names, staging, and cleanup. Perform only the external actions explicitly authorized by the user.

## Completion

Finish when every acceptance criterion for the assigned task is implemented or explicitly reported as blocked or not applicable, required checks have evidence, and the integrated task changes are summarized for the parent with their revision and remaining limitations. Report separately whether work is local, committed, published, or integrated.
