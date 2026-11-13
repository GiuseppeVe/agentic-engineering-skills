# Packet contract

Every packet must define its `id`, classification, objective, dependencies, allowed files, file ownership, shared-contract surfaces, constraints, acceptance criteria, required tests, expected evidence, risks, and assumptions.

Eligible parallel packets must have all prerequisites integrated and disjoint allowed files, ownership, and shared-contract surfaces. Use at most three parallel workers unless the operator explicitly authorizes more and host capacity is verified.

```text
parallel_workers = min(ready_disjoint_packets, host_capacity - 1, 3)
```

Classify packets as:

- `INDEPENDENT`: bounded work that may be delegated in its own branch or worktree.
- `DEPENDENT`: starts only after prerequisite evidence is integrated.
- `ARCHITECTURE_SENSITIVE` or `INTEGRATION`: retained by GPT-6.1 Sol with high effort on Codex, Sonnet 5.5 with high effort on Claude Code, or the controller.

Scope is binding. Any excluded file, non-owned interface, ownership overlap, unresolved shared contract, architectural decision, or required scope expansion returns `BLOCKED`. worker never expands scope or resolves such decisions independently.

Return the semantic result described in [task-implement](../SKILL.md#completion). For an uncommitted shared-worktree packet, supply base SHA, branch, worktree, diff, and verification evidence. When the parent explicitly requires and authorizes a packet commit, supply its verifiable SHA instead. A missing commit alone does not block an uncommitted workflow.

For each delegated worker, include this contract and its packet in the brief. The worker changes only allowed files, validates its work, and reports the result contract and integration risks. The worker never integrates or approves integration.
