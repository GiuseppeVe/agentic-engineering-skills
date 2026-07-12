---
name: cavecrew
description: Delegate bounded investigation, editing, and review work to specialized public profiles.
upstream: https://github.com/JuliusBrussee/caveman
upstream_revision: 0d95a81d35a9f2d123a5e9430d1cfc43d55f1bb0
license: MIT
status: adapted
---

# Cavecrew

Upstream notice: derived from Caveman under MIT; see `licenses/MIT-caveman.txt`. Repository changes: replaces host-specific role names with profiles in `agent-profiles/`.

## When to use

Use when independent bounded work benefits from separate investigation, implementation, and review perspectives.

## Inputs

Task boundary, owned files, acceptance criteria, and selected profile.

## Workflow

Use researcher for evidence, implementer for owned edits, reviewer for read-only assessment, and test-runner for commands. Keep overlapping writes serial.

## Validation

Every delegated result cites files or commands; reviewer and test-runner do not edit.

## Failure behavior

Run work serially when no agent runtime is available.
