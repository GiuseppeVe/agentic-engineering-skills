---
name: Orientated E2E Testing v5.2
description: Use when the user explicitly invokes $graph-engineering-v5-2 to confirm and traverse one bounded observable product trajectory.
---

# Orientated E2E Testing v5.2

V5.2 confirms an observable product trajectory, then derives and traverses one
Behavioral Node at a time.
It maximizes operational work and minimizes process.

## Scope

Trajectory Brief is behavioral authority. It names actor, admitted target, and
isolation boundary, observable start, ordered observable landmarks, goal,
terminal outcome, expected behaviors, non-goals, Author Signals, and Execution
Envelope. It must not prescribe files, root causes, patches, or a catalog of
defects.

Graph Brainstorming for a new Graph Run follows
`references/graph-brainstorming.md`. It is internal reference material, not a
catalog skill or public invocation. New runs conduct intake once; resume,
traversal, and repair load persisted confirmed authority without reopening it.

V5.2 rejects broad audits, free-form refactors, migrations, and unsupported
work before confirmation.

## V5.2 adapter boundary and V5.1 compatibility

V5.2 keeps fixture traversal through a confirmed fixture adapter manifest and
adds manifest-bound real-system traversal. `start` requires one canonical,
confirmed adapter manifest that is digest-bound to the Trajectory Brief before
it creates a store, worktree, process, connection, or adapter. The manifest
selects only a package-registered adapter factory; dynamic imports, arbitrary
adapter code, and shell strings are forbidden.

Choose exactly one admitted mode:

- `fixture` for sealed simulation through the registered fixture adapter
  manifest;
- `local_isolated` for declared local services and owned synthetic data;
- `remote_nonprod` for one exact non-production target and synthetic data;
- `production_guarded` for one exact production target, read-only by default.

Production synthetic writes require a digest-bound `ProductionWritePlan` and a
second explicit confirmation. Production is never a fallback. Every admitted
real run records only secret references, bounded effects and budgets, redacted
evidence, leases, and a sealed environment identity.

V5.1 stores are legacy records: legacy run stores are immutable, report as
such, and are never silently migrated. V5.2 fixture runs use the registered
fixture adapter manifest rather than legacy fixture arguments.

## Public operation

V5 exposes exactly four operations:

- `start` accepts one confirmed Trajectory Brief bundle and its confirmed
  adapter manifest, validates both before any write, persists Bootstrap Intent before Git effects,
  completes host and worktree preflight, derives sealed environment identity,
  and enters first frontier.
- `run` advances autonomously inside Execution Envelope until frontier change,
  deterministic pause, narrow escalation, terminal result, or caller-bounded
  slice.
- `status` is read-only. It projects current node, local Causal Cone,
  verified/open work, limits, proof result, and next action without writing.
- `decision` applies only a digest-bound pending limits amendment, production
  write, cleanup, fix-treatment, or narrow escalation decision.

`--preview` and `--dry-run` are read-only options on `start` and `run`;
they are not separate operations. Internal proof, review, dispatch, and
integration mechanics have no public operation.

All public operations go through `scripts/graphctl.py` from package root.
Use only its `start`, `run`, `status`, and `decision` routes. Never bypass the
CLI/runtime gate with direct filesystem, Git, process, or repository tools.
Those tools may be used only by runtime after its persisted authority gates
allow them.

For resume, call `status` first and verify persisted run ID, canonical brief
JSON, exact Markdown bytes, confirmation, adapter-manifest digest, and sealed
environment identity. Missing, tampered, or mismatched authority must fail
closed and never fall back to intake or a new run. Then use `run` or
`decision`; never call `start` for resume.

## Run boundary

Start creates one isolated Graph-run branch and worktree from recorded base.
V5 never mutates main, pushes, rebases, or auto-merges. It runs product work,
repairs, validation, and replay from Graph-run workspace only. Successful,
paused, and terminal workspaces remain preserved for review.

Each Derived Spine node observes entry state, records sealed intent before an
action, checks immediate and next visible state, and checks persistence only
when behavior requires it. Real effects require a persisted, idempotency-bound
intent and exact redacted receipt. Variants stay evidence-driven and bounded;
V5.2 does not turn a trajectory into an unbounded repository audit.

On failure V5 closes local Causal Cone before repair. It gathers
evidence-connected leads, evaluates required seams and variants, and repairs
most upstream supported cause before downstream symptoms. A failed repair adds
one new evidence-connected causal hop; exhausted bounded investigation pauses
rather than guessing.

## Repair and proof

Automatic repair restores behavior already specified by confirmed Trajectory
Brief. Behavior,
architecture, contract, schema, dependency, deployment, secret, production,
or high-risk changes become narrow escalation.

Every automatic repair follows one hidden proof ladder: reproduce failure,
approve discriminating proof, patch isolated candidate workspace, validate and
review independently, integrate one patch to Graph-run branch, prove original
node and direct affected neighbors on new Run Head.

Final acceptance is clean replay of complete sealed Derived Spine on sealed Run
Head.
Local test success alone never closes a defect.

## Operator output

Status reports product progress, block reason, current cone, consumed limits,
last proof, and smallest next action. It does not present administrative work
as progress.

After a successful run, branch and worktree stay intact. User makes explicit human integration decision later; V5 never performs that integration itself.

## Safety, recovery, and cleanup

Bootstrap Intent precedes every Git effect. Host failure compensates recorded
resources before product observation. State, artifacts, and proofs are durable
and append-only. Runtime owns writes; CLI validates public input and projects
results.

`runtime_notes.md` is append-only and secret-free in the external run store.
It records synthetic-resource ownership, classification, receipt, and cleanup
intent. Post-review cleanup requires an explicit digest-bound decision and a
fresh matching lease check: only owned `ephemeral_test_data` may be removed.
`fix_or_patch` always pauses for a treatment decision. Failed cleanup pauses
with evidence; it never broadens cleanup or retries uncertain external effects.

When proof cannot establish safe progress within limits, V5 returns deterministic
pause with evidence and smallest available decision. It never fabricates a
green result.
