---
name: cleaning-repo-with-knip
description: Turn Knip findings into reviewed cleanup proposals without automatic deletion.
license: MIT
status: original
---

# Cleaning Repository with Knip

## When to use

Use after a Knip scan reports unused files, exports, or dependencies.

## Inputs

Knip output, repository entry points, dynamic loading conventions, and test commands.

## Workflow

Classify each finding with codebase evidence. Mark it remove, retain, or investigate. Apply only approved removals and verify the full suite.

## Validation

Each removal has a finding, supporting evidence, changed-file list, and passing verification command.

## Failure behavior

Treat uncertain dynamic usage as retained until an owner decides. Never auto-delete from scan output alone.
