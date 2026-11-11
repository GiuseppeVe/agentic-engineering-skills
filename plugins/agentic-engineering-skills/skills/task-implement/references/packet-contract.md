# Packet contract

Every packet must define its `id`, classification, objective, dependencies, allowed files, file ownership, shared-contract surfaces, constraints, acceptance criteria, required tests, expected evidence, risks, and assumptions.

Eligible parallel packets must have all prerequisites integrated and disjoint allowed files, ownership, and shared-contract surfaces. Use at most three parallel workers unless the operator explicitly authorizes more and host capacity is verified.

```text
parallel_workers = min(ready_disjoint_packets, host_capacity - 1, 3)
```

Classify packets as:

- `INDEPENDENT`: bounded work that may be delegated in its own branch or worktree.
- `DEPENDENT`: starts only after prerequisite evidence is integrated.
- `ARCHITECTURE_SENSITIVE` or `INTEGRATION`: retained by the task orchestrator.

Scope is binding. Any excluded file, non-owned interface, ownership overlap, unresolved shared contract, architectural decision, or required scope expansion returns `BLOCKED`. worker never expands scope or resolves such decisions independently.

Return `DONE` only with a verifiable packet commit SHA in the declared packet branch; without it, return `BLOCKED`.

For each delegated worker, include this contract and its packet in the brief. The worker changes only allowed files, validates its work, and reports status, changes, tests, assumptions, deviations, integration risks, files changed, packet branch/worktree, and commit SHA. The worker never integrates or approves integration.
