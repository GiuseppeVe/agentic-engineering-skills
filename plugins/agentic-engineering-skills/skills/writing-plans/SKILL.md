---
name: writing-plans
description: Use when you have a spec or requirements for a multi-step task, before touching code
---

> **Adaptation:** Based on `obra/superpowers`; adjusted for portable Codex and Claude Code skill-pack use.

# Writing Plans

## Overview

Write comprehensive implementation plans assuming the engineer has zero context for our codebase and questionable taste. Document everything they need to know: which files to touch for each task, code, testing, docs they might need to check, how to test it. Give them the whole plan as bite-sized tasks. DRY. YAGNI. TDD. Frequent commits.

Assume they are a skilled developer, but know almost nothing about our toolset or problem domain. Assume they don't know good test design very well.

**Announce at start:** "I'm using the writing-plans skill to create the implementation plan."

**Context:** If working in an isolated worktree, it should have been created via the `superpowers:using-git-worktrees` skill at execution time.

**Save plans to:** `docs/superpowers/plans/YYYY-MM-DD-<feature-name>.md`
- (User preferences for plan location override this default)

## Scope Check

If the spec covers multiple independent subsystems, it should have been broken into sub-project specs during brainstorming. If it wasn't, suggest breaking this into separate plans — one per subsystem. Each plan should produce working, testable software on its own.

## Requirements Inventory (MANDATORY)

**Every plan MUST carry an explicit, enumerated Requirements Inventory immediately after the header, before the File Structure section.** This is the single source of truth for *what the plan obligates*. The downstream executor (`codex-implement in Codex or claude-implement in Claude Code` Phase 1) copies this list verbatim to drive its fidelity-coverage gate — so a complete inventory turns that extraction into a 1:1 parse instead of a lossy re-inference. An incomplete inventory is a **plan failure**, exactly like a placeholder.

**The Prose-Is-Not-A-Requirement rule:** every obligation the plan imposes MUST appear as a `REQ-NNN` line in this inventory. Prose, task bodies, and code comments may *explain* an obligation, but they may never *introduce* one that is absent from the inventory. If you find yourself writing "the worker must…" / "ensure that…" / "X has to…" anywhere outside the inventory, stop and add the matching `REQ` first.

### Schema

Each requirement is one line:

```
- **REQ-NNN** [type] — <atomic obligation>. _Acceptance:_ <objective oracle>. _Satisfied by:_ Task N
```

- **`REQ-NNN`** — stable, never reused, never renumbered once assigned.
- **`type`** — one of:
  - `behavior` — runtime behavior the system must exhibit.
  - `test` — a test the plan promises to add or keep.
  - `contract` — a cross-task wiring obligation (see Cross-Task Contracts below).
  - `constraint` — a cross-cutting rule that applies in more than one place ("all timestamps UTC ISO-8601", "all urls must be https"). These are the ones prose hides and inference drops.
- **One requirement = one atomic checkable claim.** Split compound obligations ("validate X and enqueue Y") into two `REQ`s.
- **`Acceptance:` is mandatory and must be objective** — a test name, a command + expected output, or a grep-able artifact. "Works correctly" / "is handled" is not an acceptance oracle; it is a placeholder. If you cannot state an objective oracle, the requirement is too vague to implement — sharpen it or drop it.
- **`Satisfied by:`** names the Task(s) that implement it. Every `REQ` maps to ≥1 task; every task maps back to ≥1 `REQ` (see Task Structure `Satisfies:` line).

### Cross-Task Contracts (MANDATORY subsection)

The most error-prone obligations have **no single owning task**: "A is wired/consumed/imported by B", a config key one task sets and another reads, a migration a later task depends on, a value stub one task leaves for another to replace. Per-task review never catches these because no single task owns them — they fall through the gap.

List every such contract as a `REQ` of `type: contract`. Each one names *both* endpoints and the wiring that must hold:

```
- **REQ-007** [contract] — `SubscriptionStore.getSecret` is passed into `DeliveryWorker` as its `secretResolver` (same secret source on both ends). _Acceptance:_ integration test registers a sub, ingests a matching event, asserts the delivered `X-Signature` equals an HMAC independently computed with the stored secret. _Satisfied by:_ Task 10 (wiring) + Task 11 (test).
```

If there are no cross-task contracts, write `_None._` — explicit emptiness proves you checked.

### Worked example

```markdown
## Requirements Inventory

### Behavior & constraints
- **REQ-001** [behavior] — `ingest(event)` rejects an event with empty `type` with `ValidationError`. _Acceptance:_ `eventIngestor.test.ts` "rejects empty type" passes. _Satisfied by:_ Task 6.
- **REQ-002** [behavior] — delivery retries any non-2xx or network error up to 5 attempts, exponential backoff from 1s. _Acceptance:_ retry test asserts 5 calls, sleeps `[1000,2000,4000,8000]`. _Satisfied by:_ Task 8.
- **REQ-003** [constraint] — every timestamp recorded anywhere (log lines AND dead-letter `failedAt`) is a UTC ISO-8601 string. _Acceptance:_ grep for timestamp assignments shows all flow through `clock.now()`; clock test asserts `/Z$/`. _Satisfied by:_ Task 2, applied in Task 7 & Task 8.

### Tests
- **REQ-004** [test] — unit test proves invalid events are rejected. _Acceptance:_ test file exists and passes. _Satisfied by:_ Task 6.

### Cross-task contracts
- **REQ-005** [contract] — `store.getSecret` wired as the worker's `secretResolver`. _Acceptance:_ integration test asserts delivered signature matches independent HMAC with stored secret. _Satisfied by:_ Task 10 + Task 11.
```

## File Structure

Before defining tasks, map out which files will be created or modified and what each one is responsible for. This is where decomposition decisions get locked in.

- Design units with clear boundaries and well-defined interfaces. Each file should have one clear responsibility.
- You reason best about code you can hold in context at once, and your edits are more reliable when files are focused. Prefer smaller, focused files over large ones that do too much.
- Files that change together should live together. Split by responsibility, not by technical layer.
- In existing codebases, follow established patterns. If the codebase uses large files, don't unilaterally restructure - but if a file you're modifying has grown unwieldy, including a split in the plan is reasonable.

This structure informs the task decomposition. Each task should produce self-contained changes that make sense independently.

## Bite-Sized Task Granularity

**Each step is one action (2-5 minutes):**
- "Write the failing test" - step
- "Run it to make sure it fails" - step
- "Implement the minimal code to make the test pass" - step
- "Run the tests and make sure they pass" - step
- "Commit" - step

## Plan Document Header

**Every plan MUST start with this header:**

```markdown
# [Feature Name] Implementation Plan

> **For agentic workers:** REQUIRED EXECUTION SKILL: Use codex-implement in Codex or claude-implement in Claude Code with swarm-orchestration to implement this plan end-to-end. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about approach]

**Tech Stack:** [Key technologies/libraries]

---
```

The Requirements Inventory section comes immediately after this header.

## Task Structure

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

The `**Satisfies:**` line is mandatory on every task and lists the `REQ` ids that task implements. A task that satisfies no `REQ` is either dead work or a sign of a missing inventory entry.

## No Placeholders

Every step must contain the actual content an engineer needs. These are **plan failures** — never write them:
- "TBD", "TODO", "implement later", "fill in details"
- "Add appropriate error handling" / "add validation" / "handle edge cases"
- "Write tests for the above" (without actual test code)
- "Similar to Task N" (repeat the code — the engineer may be reading tasks out of order)
- Steps that describe what to do without showing how (code blocks required for code steps)
- References to types, functions, or methods not defined in any task
- A `REQ` whose `Acceptance:` is non-objective ("works", "is handled") — an acceptance placeholder is still a placeholder
- An obligation stated only in prose with no matching `REQ`

## Remember
- Exact file paths always
- Complete code in every step — if a step changes code, show the code
- Exact commands with expected output
- DRY, YAGNI, TDD, frequent commits

## Self-Review

After writing the complete plan, look at the spec with fresh eyes and check the plan against it. This is a checklist you run yourself — not a subagent dispatch.

**1. Spec coverage:** Skim each section/requirement in the spec. Can you point to a `REQ` that captures it? List any gaps and add the missing `REQ`s.

**2. Inventory completeness (no prose-only obligations):** Re-read every task body, the architecture, and any context section hunting for MUST / SHALL / REQUIRED / "has to" / "ensure that" / "always" / "never". Every one MUST already exist as a `REQ`. If it only lives in prose, add the `REQ` now. Pay special attention to `constraint`-type obligations ("all X must be Y") — these apply in multiple places and are the ones inference drops.

**3. Cross-task contracts captured:** Re-read each task asking "does this task assume something it does not itself produce — an import, a config key, a wired dependency, a value another task fills in?" Every such assumption MUST be a `REQ` of type `contract` naming both endpoints. If the Cross-Task Contracts subsection says `_None._`, double-check that is truly the case.

**4. Traceability (both directions):** Every `REQ` has a `Satisfied by:` naming ≥1 task, and that task's `**Satisfies:**` line lists that `REQ`. Every task's `**Satisfies:**` line is non-empty. No orphans either way.

**5. Acceptance oracles:** Every `REQ` has an objective `Acceptance:` — a test name, command + expected output, or grep-able artifact. Replace any non-objective oracle.

**6. Placeholder scan:** Search your plan for the red flags in the "No Placeholders" section above. Fix them.

**7. Type consistency:** Do the types, method signatures, and property names you used in later tasks match what you defined in earlier tasks? A function called `clearLayers()` in Task 3 but `clearFullLayers()` in Task 7 is a bug.

If you find issues, fix them inline. No need to re-review — just fix and move on.

## Execution Handoff

After saving the plan, offer execution choice:

**"Plan complete and saved to `docs/superpowers/plans/<filename>.md`. Two execution options:**

**1. Host-specific implementation (recommended)** - I run `codex-implement` in Codex or `claude-implement` in Claude Code with bounded packets, semantic tests, and clean-room review; add swarm orchestration only for disjoint work.

**2. Manual Execution** - Execute tasks in this session with explicit checkpoints and user approvals

**Which approach?"**

**If Host-specific implementation chosen:**
- **REQUIRED SKILL:** Use `codex-implement` in Codex or `claude-implement` in Claude Code.
- Use bounded packets, semantic validation, and clean-room review; add swarm orchestration only for disjoint work.

**If Manual Execution chosen:**
- No required legacy superpowers skill
- Batch execution with explicit checkpoints for review
