---
name: writing-plans
description: Use when a spec or requirements need a multi-step implementation plan before code changes, including standalone MDX plans.
---

# Writing Plans

> **Adaptation:** Based on `obra/superpowers`; updated with a portable contract-based writing-plans workflow routing multi-task plans to `plan-implement`.

Write standalone `.mdx` plans for skilled engineers unfamiliar with the codebase, toolset, domain, and good test design. Include what changes execution: files, contracts, interfaces, tests, commands, docs, risks, and acceptance criteria. A plan states contracts, interfaces, tests, and acceptance criteria, not the complete implementation: the implementer designs the code. DRY, YAGNI, TDD.

Announce: "I'm using the writing-plans skill to create the implementation plan."

## Artifact and scope

- Respect system and host constraints. Within those constraints, follow explicit user instructions over repository defaults. Otherwise use the repository's canonical plan location (for example, `docs/work/plans/`). Use `docs/superpowers/plans/YYYY-MM-DD-<feature-name>.mdx` only when neither provides a location.
- For multiple review artifacts, use `docs/superpowers/plans/YYYY-MM-DD-<feature-name>/plan.mdx` as the fallback, with optional `canvas.mdx` for visual review and `prototype.mdx` for interaction notes.
- Use local MDX first. A hosted Plan MCP surface is required only if the user requests it or already uses it.
- Plans stand alone without chat, previous drafts, or spec discussions. Adapt existing or pasted plans into clean proposals, not revision memos.
- Planning/review is read-only for source code. When execution is already authorized, continue within that authority; otherwise obtain the required authorization before changes. Follow host and project worktree rules; use an available worktree tool when its behavior meets them.
- For independent subsystems not already split during brainstorming, suggest separate plans. Each must produce independently working, testable software.

## Research and decisions

Before naming tasks, read actual files, schemas, actions, helpers, tests, docs, and project conventions. For each area, name reused files, symbols, components, and contracts before additions.

When behavior depends on state or on the order of events, apply the [behavior model](../development-process/references/behavior-model.md) first: without the owner's recorded approval, do that step instead of planning. Its critical transitions become `REQ` entries.

If an approved `to-spec` artifact exists, reference it as source of truth instead of restating or silently changing requirements. Keep planning/executor prompts outcome-focused: goal, relevant context, hard constraints, approval boundaries, validation, deliverable. State each rule once; omit boilerplate that changes no decision.

Resolve hard-to-reverse choices before task breakdown: data models, public identifiers, wire formats, ownership/auth boundaries, migrations, worker topology, rollout. For unresolved architecture, UX, data, rollout, or scope decisions, choose a recommended default with rationale or record a question. Material gaps in requirements, authority, or acceptance evidence belong in `## Open Questions` at the bottom.

Plain Markdown is valid MDX. Use file maps, annotated code, decision tables, or diagrams only when useful; skip empty optional sections. UI/product plans may use `canvas.mdx` or a top "Visual Review" section with wireframes/states. Backend/data/worker plans use inline diagrams or file maps when relationships need explanation. A useful decision table records decision, choice, rationale, and reversibility.

## Plan structure

Every plan starts with this header, followed by `## Expected Outcome`,
`## Requirements Inventory`, and `## File Structure` before the tasks.

```markdown
# [Feature Name] Implementation Plan

> **For agentic workers:** Use `plan-implement` for dependency-aware multi-task execution with slice subagents, or inline execution with explicit checkpoints for small tightly-coupled work. Steps use checkbox (`- [ ]`) syntax for tracking.

**Architecture:** [2-3 sentences]
**Tech Stack:** [Key technologies/libraries]

---
```

### Expected Outcome (mandatory)

```md
## Expected Outcome

<Describe the observable result when the plan's tasks are integrated. Identify
the entry point or system boundary and the acceptance evidence that will show
the result. Derive the outcome from the approved spec or supplied requirements.
Use the Requirements Inventory for the binding obligations and evidence.>
```

### Requirements Inventory (mandatory)

Inventory is the single source of obligations and executor fidelity coverage (`plan-implement` or inline execution). Every obligation from the spec, prose, task bodies, or code comments must have a `REQ-NNN` entry. Prose may explain requirements, not introduce unlisted ones. An incomplete inventory is a plan failure.

One line per atomic, checkable obligation:

```markdown
- **REQ-NNN** [type] — <obligation>. _Evidence:_ <level>. _Acceptance:_ <objective oracle>. _Satisfied by:_ Task N
```

- IDs stay stable: never reuse or renumber assigned IDs.
- Each task's acceptance criteria are provable with fixtures. Put every native or live proof in a separate task of its own, naming the authority it needs. The plan makes this split: no implementer or reviewer moves a criterion between tasks.
- Types: `behavior` (runtime behavior), `test` (test added/kept), `contract` (cross-task wiring), `constraint` (cross-cutting rule, such as UTC timestamps).
- Split compound claims, such as validation and enqueueing, into separate requirements.
- `Evidence:` preserves the spec's required level: `artifact` (static), `fixture` (simulated), `integration`, or `real-runtime` (operational). Select the level required by the obligation, not the easiest available proof. Fixture or simulation cannot satisfy real-runtime; isolated installation cannot satisfy activation in the real target. Weaker evidence leaves the requirement open.
- `Acceptance:` is mandatory: test name, command + expected output, or grep-able artifact. Match the oracle to the obligation: choose unit behavioral tests for local logic, cross-package contract tests for shared wire formats, property-based tests for invariants (auth/revocation, idempotency, parsers), and real-runtime/real-decoder checks for operational artifacts. "Works" / "is handled" is a placeholder. Sharpen vague requirements or drop them.
- Every requirement names at least one task in `Satisfied by:`. Every task has a nonempty `**Satisfies:**` listing matching real IDs. Check both directions.
- For a required action outside current authority, retain an explicit task and gate naming the required authority and subsequent acceptance oracle. A deferred requirement names its responsible later task in `Satisfied by:` and remains globally open until its required evidence exists; neither a gate nor deferral makes it N/A or satisfied.

#### Cross-Task Contracts (mandatory subsection)

List every dependency spanning tasks as `[contract]`: imports/consumers, config producers/readers, migrations/dependents, stubs/later replacements. Name both endpoints and required wiring. If none, write `_None._` after checking.

```markdown
- **REQ-007** [contract] — `SubscriptionStore.getSecret` is passed into `DeliveryWorker.secretResolver`. _Evidence:_ integration. _Acceptance:_ integration test registers a subscription, ingests a matching event, and verifies delivered `X-Signature` against HMAC independently computed with the stored secret. _Satisfied by:_ Task 10 (wiring), Task 11 (test).
```

### File Structure

Map every created/modified file and its responsibility before tasks. Use clear interfaces and focused files; co-locate files that change together, split by responsibility rather than technical layer. Follow existing conventions. Do not unilaterally restructure large-file codebases; a split of an unwieldy file being changed may be planned with rationale. Each task produces coherent, self-contained changes.

### Task and slice structure

Use steps where sequence, dependencies, or verification affect execution. Choose task boundaries that produce a coherent result that can be verified independently. When contiguous tasks share the same module or area, group them under `## Slice N: [Module or Area]` so `plan-implement` can keep one persistent slice-implementer subagent warm across them; otherwise `plan-implement` groups contiguous same-module tasks into slices at runtime.

Mark each task `**Risk:** standard | high`. Flag `high` on authorization, privacy, persistence/migrations, concurrency, or shared cross-module/package contracts so `plan-implement` triggers an intermediate clean-room review checkpoint before dependent slices build on it.

Commit boundary and owner follow the selected execution mode and explicit authority; a plan does not grant commit or PR permission. For `plan-implement`, slice-implementer subagents hand off verified uncommitted diffs and `plan-implement` commits each accepted slice on the plan branch only when authorized. Inline execution commits only when explicitly assigned and authorized.

```md
### Task N: [Name]

**Expected outcome:** [Observable result this task delivers within its scope.]

**Satisfies:** REQ-003, REQ-007

**Risk:** standard | high

**Files:** [Exact paths and ownership.]

**Contracts and constraints:** [Interfaces, required behavior, and dependencies
that affect this task.]

- [ ] [Implement the behavior using the identified entry point and existing contracts.]
- [ ] [Run the relevant check and record the result against the cited REQs.]
```

## Completeness and self-review

Provide exact paths, relevant existing symbols or planned interfaces, and
runnable verification commands with expected results. Include exact code
or data shapes when they encode an agreed contract, a decision, or a test
case whose details affect correctness. Resolve placeholders and give each
task enough context to execute and verify its outcome.

Review yourself first, with the spec and fresh eyes:

1. Map every spec requirement to a `REQ`; add gaps.
2. Scan architecture, context, tasks, comments for MUST/SHALL/REQUIRED/"has to"/"ensure that"/"always"/"never". Capture each obligation, especially cross-cutting constraints, in the inventory.
3. Check every task's external assumptions for a contract naming both endpoints; verify `_None._` claims.
4. Verify bidirectional `Satisfied by:` / `Satisfies:` links, with no orphan requirements or tasks.
5. Check each evidence level against the spec and each oracle against its required behavior and environment; retain gated and deferred work with authority, later owner task, and open status until proven.
6. Verify that each task's expected outcome follows from its mapped REQs and that high-risk tasks are marked `high`.
   Resolve placeholders and fill gaps in paths, contracts, or checks.
7. Check later types, signatures, and property names match earlier definitions.

Fix issues inline. Preserve required content even under deadline pressure.

### Design review before implementation

Before the first task, a separate fresh-context reviewer reviews the plan on states, concurrency, cancellation, authorizations, and privacy. Record the review (reviewer, date, findings, and how each was closed) in the plan under `## Design Review`; no task starts without it.

## Execution handoff

After saving, report the `.mdx` path. If the user already authorized execution, choose an available mode consistent with their instructions and continue. Otherwise, present appropriate choices and wait for authorization:

1. **Plan implementation** — use `plan-implement` for multi-task plans requiring dependency-aware slice subagents, L1–L3 verification, high-risk review checkpoints, and a plan-level PR.
2. **Inline execution** — small or tightly coupled work with explicit checkpoints; fallback when subagent execution is unavailable.

**Model choice:** Choose models and reasoning effort only from options actually available in the host or operator workspace configuration. Match them to task risk and keep architecture-sensitive or high-risk work on a high-reasoning profile. Check runtime availability; never invoke missing skills or models.
