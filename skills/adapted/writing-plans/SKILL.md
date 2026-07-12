---
name: writing-plans
description: Turn an approved specification into a testable, traceable implementation plan.
upstream: https://github.com/obra/superpowers
upstream_revision: d884ae04edebef577e82ff7c4e143debd0bbec99
license: MIT
status: adapted
---

# Writing Plans

Upstream notice: derived from Obra Superpowers under MIT; see `licenses/MIT-obra-superpowers.txt`. Repository changes: plan format is host-neutral and uses no proprietary task tool.

## When to use

Use after a specification is approved and before implementation begins.

## Inputs

Approved specification, repository structure, constraints, and verification commands.

## Workflow

Create a requirement inventory, file map, dependency order, and small test-first tasks. Link every requirement to a task and objective acceptance oracle.

## Validation

No requirement exists only in prose. Every task has exact paths, commands, and a completion condition.

## Failure behavior

Stop for ambiguous requirements; revise the specification before implementation.
