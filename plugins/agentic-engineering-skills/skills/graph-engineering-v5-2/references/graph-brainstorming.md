# Graph Brainstorming for a New Graph Run

## Purpose

Use this internal reference once for each new Graph Run. Convert author intent
into one confirmed `graph-v5.trajectory-brief.v1` authority bundle. It never
creates a node-by-node journey, repair plan, patch plan, or predeclared spine.

## Read-only context first

Read only context needed to understand observable product behavior, existing
fixtures, repository boundaries, and known constraints. Do not create a run
store, artifact, ledger, Bootstrap Intent, branch, worktree, fixture mutation,
process, repository write, or product action during intake.

## Material-ambiguity test

Ask only when missing information could materially change goal, terminal
outcome, actor, fixture, ordered landmark, expected behavior, non-goal,
Execution Envelope, forbidden system, or allowed side effect. Record useful
non-material context without extending intake. Do not ask internal
implementation questions, root-cause questions, or questions that choose a
repair.

## One-question interaction

Ask one question at a time. State smallest material ambiguity, why it affects
trajectory authority, and smallest observable answer needed. Incorporate answer
before asking another material question. If no material ambiguity remains, stop
asking and move to author review.

## Trajectory Brief fields

Build canonical brief fields: run ID, brief ID, request, test philosophy, run
rationale, actor and identity constraints, fixture intent, observable start,
ordered observable landmarks, goal, terminal outcome, expected behaviors,
non-goals, Author Signals, Execution Envelope, and material ambiguities.
Landmarks name observable acceptance, not files, patches, causes, or concrete
Behavioral Nodes.

## Author Signals are attention only

Record known user problems or prior reports as immutable `attention_only`
signals. They can prioritize later observation. They cannot establish a defect,
cause, severity, scope, repair authority, or causal lead. Runtime needs an
independent Observation before treating a signal as evidence.

## Sufficiency check

Before review, verify each start, landmark, and terminal outcome has observable
acceptance; landmark IDs are unique and ordered; expected behaviors reference
known landmarks; scope and side effects fit Execution Envelope; non-goals are
explicit; all material ambiguities are resolved; no concrete node journey or
Derived Spine has been authored.

## Concise author review

Show concise trajectory summary: actor and fixture, observable start, ordered
landmarks, goal and terminal outcome, expected behaviors, non-goals, signals
labelled attention-only, envelope, and remaining ambiguities. If author rejects
or revises summary, revise brief and repeat sufficiency check.

## Explicit confirmation

Obtain explicit confirmation of reviewed summary. Record confirming identity,
timestamp, and durable reference to explicit response. Silence, implication,
or inferred agreement is not confirmation. Confirmation binds exact trajectory
digest, run ID, and brief ID.

## Atomic handoff to start

Create one confirmed bundle containing canonical Trajectory Brief JSON, exact
deterministic Markdown projection, and confirmation record. `start` validates
whole bundle before runtime creation. No separate confirmation flag, sibling
brief discovery, Bootstrap Intent, Git action, or writable side effect may
precede bundle validation.

## Resume and narrow trajectory decisions

Resume reads already persisted confirmed authority; it never reruns intake in
same chat or new chat. Ordinary traversal, evidence collection, node splitting,
conformance repair, and Causal Cone expansion do not reopen intake. Material
departure pauses for narrow digest-bound trajectory decision and, if approved,
creates confirmed successor authority without mutating predecessor bytes.
Before resume, verify persisted run ID, canonical brief JSON, exact Markdown
bytes, confirmation, and digest binding. Missing, tampered, or mismatched
authority must fail closed and never fall back to intake or a new run.

## Forbidden intake behavior

Do not expose this reference as a catalog skill, public command, or prompt
invocation. Do not ask for patch steps, architecture, implementation details,
or a concrete spine. Do not silently convert legacy brief input. Do not write
before explicit confirmation.
