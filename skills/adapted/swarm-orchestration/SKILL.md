---
name: swarm-orchestration
description: Coordinate independent agent work with explicit dependencies, evidence, and fallbacks.
upstream: https://github.com/ruvnet/ruflo
upstream_revision: 7ef4d4e655d81c0451f6f40f35729cce6c9928e7
license: MIT
status: adapted
---

# Swarm Orchestration

Upstream notice: derived from Ruflo under MIT; see `licenses/MIT-ruflo.txt`. Repository changes: removes host CLI commands, bundled runtime claims, and all `ruvocal` material; uses public capability contracts and deterministic mock support.

## When to use

Use for three or more independent tasks where separate evidence improves quality.

## Inputs

Dependency graph, owned-file sets, worker capability map, and verification plan.

## Workflow

Group only disjoint tasks into a wave. Give each worker exact owned files and completion evidence. Run integration review after every wave; rerun verification after implementation changes.

## Validation

No two concurrent writers own the same file. Final claims include test and review evidence.

## Failure behavior

If no swarm runtime is installed, run the same dependency order serially. Never claim parallel execution occurred.
