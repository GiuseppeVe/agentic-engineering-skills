---
name: writing-plans
description: Use when a spec or requirements need a multi-step implementation plan before code changes, including standalone MDX plans.
---

# Writing Plans

> **Adaptation:** Based on `obra/superpowers`; updated with a portable writing-plans workflow for portable Codex and Claude Code skill-pack use.

Write standalone `.mdx` plans for skilled engineers unfamiliar with the codebase, toolset, domain, and good test design. Include what changes execution: files, contracts, code, tests, commands, docs, risks, and acceptance evidence. DRY, YAGNI, TDD, frequent commits.

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

If an approved `to-spec` artifact exists, reference it as source of truth instead of restating or silently changing requirements. Keep planning/executor prompts outcome-focused: goal, relevant context, hard constraints, approval boundaries, validation, deliverable. State each rule once; omit boilerplate that changes no decision.

Resolve hard-to-reverse choices before task breakdown: data models, public identifiers, wire formats, ownership/auth boundaries, migrations, worker topology, rollout. For unresolved architecture, UX, data, rollout, or scope decisions, choose a recommended default with rationale or record a question. Material gaps in requirements, authority, or acceptance evidence belong in `## Open Questions` at the bottom.

Plain Markdown is valid MDX. Use file maps, annotated code, decision tables, or diagrams only when useful; skip empty optional sections. UI/product plans may use `canvas.mdx` or a top "Visual Review" section with wireframes/states. Backend/data/worker plans use inline diagrams or file maps when relationships need explanation. A useful decision table records decision, choice, rationale, and reversibility.

## Plan structure

Every plan starts with this header, immediately followed by `## Requirements Inventory`, then `## File Structure` before tasks:

```markdown
# [Feature Name] Implementation Plan

> **For agentic workers:** Use the selected available mode: `codex-implement` in Codex, `claude-implement` in Claude Code, `sequential-task-orchestrator` for strict ordered execution, or inline execution with explicit checkpoints. Default to the host-specific implementation skill when available, otherwise inline. Use an explicitly available model if selected. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** [One sentence]
**Architecture:** [2-3 sentences]
**Tech Stack:** [Key technologies/libraries]

---
```

### Requirements Inventory (mandatory)

Inventory is the single source of obligations and executor fidelity coverage (`codex-implement`, `claude-implement`, or `sequential-task-orchestrator` when selected; inline execution uses the same checklist). Every obligation from the spec, prose, task bodies, or code comments must have a `REQ-NNN` entry. Prose may explain requirements, not introduce unlisted ones. An incomplete inventory is a plan failure.

One line per atomic, checkable obligation:

```markdown
- **REQ-NNN** [type] — <obligation>. _Acceptance:_ <objective oracle>. _Satisfied by:_ Task N
```

- IDs stay stable: never reuse or renumber assigned IDs.
- Types: `behavior` (runtime behavior), `test` (test added/kept), `contract` (cross-task wiring), `constraint` (cross-cutting rule, such as UTC timestamps).
- Split compound claims, such as validation and enqueueing, into separate requirements.
- `Acceptance:` is mandatory: test name, command + expected output, or grep-able artifact. "Works" / "is handled" is a placeholder. Sharpen vague requirements or drop them.
- Every requirement names at least one task in `Satisfied by:`. Every task has a nonempty `**Satisfies:**` listing matching real IDs. Check both directions.

#### Cross-Task Contracts (mandatory subsection)

List every dependency spanning tasks as `[contract]`: imports/consumers, config producers/readers, migrations/dependents, stubs/later replacements. Name both endpoints and required wiring. If none, write `_None._` after checking.

```markdown
- **REQ-007** [contract] — `SubscriptionStore.getSecret` is passed into `DeliveryWorker.secretResolver`. _Acceptance:_ integration test registers a subscription, ingests a matching event, and verifies delivered `X-Signature` against HMAC independently computed with the stored secret. _Satisfied by:_ Task 10 (wiring), Task 11 (test).
```

### File Structure

Map every created/modified file and its responsibility before tasks. Use clear interfaces and focused files; co-locate files that change together, split by responsibility rather than technical layer. Follow existing conventions. Do not unilaterally restructure large-file codebases; a split of an unwieldy file being changed may be planned with rationale. Each task produces coherent, self-contained changes.

### Task structure

Each step is one 2-5 minute action. Use this shape; replace sample paths/code with complete task-specific content:

````markdown
### Task N: [Component Name]

**Satisfies:** REQ-003, REQ-007

**Files:**
- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py:123-145`
- Test: `tests/exact/path/to/test.py`

- [ ] **Step 1: Write the failing test**

```python
def test_specific_behavior():
    result = function(input)
    assert result == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/path/test.py::test_name -v`
Expected: FAIL with "function not defined"

- [ ] **Step 3: Write minimal implementation**

```python
def function(input):
    return expected
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/path/test.py::test_name -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/path/test.py src/path/file.py
git commit -m "feat: add specific feature"
```
````

## Completeness and self-review

Exact paths, complete code for every code-changing step, exact commands and expected output are required. Repeat needed code rather than "Similar to Task N"; engineers may read tasks out of order. All referenced types/functions/methods must be defined in a task or identified existing code. Placeholders (`TBD`, `TODO`, "implement later", "fill in details"), vague validation/error-handling/edge-case directions, and "write tests for the above" without test code fail the plan.

Review yourself, not by subagent dispatch; use the spec with fresh eyes:

1. Map every spec requirement to a `REQ`; add gaps.
2. Scan architecture, context, tasks, comments for MUST/SHALL/REQUIRED/"has to"/"ensure that"/"always"/"never". Capture each obligation, especially cross-cutting constraints, in the inventory.
3. Check every task's external assumptions for a contract naming both endpoints; verify `_None._` claims.
4. Verify bidirectional `Satisfied by:` / `Satisfies:` links, with no orphan requirements or tasks.
5. Replace non-objective acceptance oracles.
6. Fix placeholders and missing concrete code/commands.
7. Check later types, signatures, and property names match earlier definitions.

Fix issues inline; no separate re-review required. Preserve required content even under deadline pressure.

## Execution handoff

After saving, report the `.mdx` path. If the user already authorized execution, choose an available mode consistent with their instructions and continue. Otherwise, present appropriate choices and wait for authorization:

1. **Host-specific implementation (default when available)** — `codex-implement` in Codex or `claude-implement` in Claude Code: bounded packets, semantic testing, clean-room review. Use `sequential-task-orchestrator` for strict ordered execution, per-task review, and resumable state.
2. **Inline Execution** — small or tightly coupled work with explicit checkpoints; fallback when executors are unavailable.

**Model choice:** If explicitly available, offer a model suited to the work, such as Sol for architecture-sensitive or high-value reasoning and independent review. This is a model choice within the selected execution mode, not a separate execution skill.

Routing: use `dispatching-parallel-agents` for small independent workstreams when available; for large distributed work, use available agent-coordination tools. The generic term “swarm” means multi-agent coordination. Keep architecture-sensitive work with controller or an explicitly available suitable model. Check runtime availability; do not invoke missing skills/models.

Choose models and reasoning effort only from options actually available in the host. Match them to the task and validate on representative work.
