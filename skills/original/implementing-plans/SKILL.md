---
name: implementing-plans
description: Execute an approved plan with isolated branches, requirement checks, reviews, and verification.
license: MIT
status: original
---

# Implementing Plans

## When to use

Use when a detailed, approved implementation plan already exists.

## Inputs

Plan path, clean repository, test command, and publication authority.

## Workflow

Create a dedicated worktree and branch, implement in dependency order, verify each requirement, review the integrated result, run the complete suite, and write a concise implementation report.

## Validation

Require clean status, passing tests, and evidence for every plan requirement before publication.

## Failure behavior

Stop when a plan is missing, an ambiguity blocks a safe decision, or verification fails. Keep publication as explicit user approval.
