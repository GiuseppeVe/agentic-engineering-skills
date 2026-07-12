---
name: wayfinder
description: Break a large uncertain change into bounded investigation tickets and resolve them in order.
upstream: https://github.com/mattpocock/skills
upstream_revision: 391a2701dd948f94f56a39f7533f8eea9a859c87
license: MIT
status: adapted
---

# Wayfinder

Upstream notice: derived from Matt Pocock Skills under MIT; see `licenses/MIT-mattpocock-skills.txt`. Repository changes: host-neutral ticket language and no required tracker integration.

## When to use

Use for migrations, broad refactors, or architecture work too large for one bounded plan.

## Inputs

Objective, known constraints, current evidence, and a place to record tickets.

## Workflow

Create small investigation tickets. Each ticket states question, evidence to collect, decision, dependency, and done condition. Resolve one ticket at a time; split a ticket when its decision cannot fit in one focused session.

## Validation

Every open uncertainty is represented by one ticket. Every closed ticket records evidence and its downstream decision.

## Failure behavior

If a tracker is unavailable, use versioned Markdown tickets. Do not pretend uncertain decisions are resolved.
