# README Philosophy and Usage Implementation Plan

> **For agentic workers:** REQUIRED EXECUTION SKILL: Use `codex-implement` for this focused implementation, or execute inline with explicit checkpoints. `sol-implement` is not part of this repository workflow. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace repetitive README introduction text with a concrete, first-person explanation of the shared workflow and update the public GitHub description to match it.

**Architecture:** Keep the hero as the visual summary and make README prose the detailed reference for philosophy, conditional routing, quality checks, and a practical example. Update GitHub's repository description as one exact metadata value; do not alter repository files outside README and planning/spec documentation.

**Tech Stack:** Markdown, GitHub CLI, Node.js repository verification scripts, Git.

---

## Requirements Inventory

### Behavior & constraints

- **REQ-001** [behavior] — README keeps the existing hero immediately below the title and follows it with one non-repetitive framing sentence. _Acceptance:_ the first six README lines contain the existing relative hero reference and no full workflow-label list. _Satisfied by:_ Task 1.
- **REQ-002** [behavior] — README contains concrete sections `What this repository shares`, `My working philosophy`, `How I use the workflow`, `The quality loop`, and `Supporting skills`. _Acceptance:_ `rg -n "What this repository shares|My working philosophy|How I use the workflow|The quality loop|Supporting skills" README.md` finds all five headings. _Satisfied by:_ Task 1.
- **REQ-003** [behavior] — README explains conditional routing for `Wayfinder`, `Brainstorming`, `Grill-me`, `To Spec`, `Writing Plans`, `Sequential Task Orchestrator`, `Codex Implement`, and `Claude Implement`, with large implementations routed to the orchestrator and small implementations routed to Codex Implement. _Acceptance:_ the workflow table contains every named skill and the phrases `large implementation` and `small implementation`. _Satisfied by:_ Task 1.
- **REQ-004** [behavior] — README explains the orchestrator's two quality signals: `Test Gaps` checks plan fidelity and `Test-Driven Development` checks implementation correctness, with findings fixed through TDD. _Acceptance:_ `rg -n "Test Gaps|Test-Driven Development|plan fidelity|implementation correctness|TDD" README.md` finds the complete quality-loop explanation. _Satisfied by:_ Task 1.
- **REQ-005** [behavior] — README includes supporting-skill usage for `Impeccable`, `UI UX Pro Max`, `Caveman`, and `How to Use Codex`, a conditional end-to-end example, and an explicit note that Graph Engineering V5.2 is planned and excluded. _Acceptance:_ `rg -ni "Impeccable|UI UX Pro Max|Caveman|How to Use Codex|Graph Engineering V5\.2|planned|excluded" README.md` finds each item. _Satisfied by:_ Task 1.
- **REQ-006** [constraint] — README preserves the existing Mermaid workflow, installation, customization, compatibility, provenance, and license sections, and no file under `plugins/` changes. _Acceptance:_ `rg -n "mermaid|## Install|## Customize|## Compatibility|## Provenance|## License" README.md` finds all retained sections; `git diff --name-only main...HEAD` contains no `plugins/` path. _Satisfied by:_ Task 1 + Task 3.

### GitHub metadata

- **REQ-007** [behavior] — Public GitHub repository description equals the approved exact string. _Acceptance:_ `gh api repos/GiuseppeVe/agentic-engineering-skills --jq .description` returns `An experience-shaped workflow of composable skills for Codex and Claude Code: evidence, design, planning, implementation, verification, and review.` _Satisfied by:_ Task 2.

### Tests and delivery constraints

- **REQ-008** [test] — Documentation and public-safety verification pass after README changes. _Acceptance:_ `npm run verify:pack`, `npm run audit:public`, and `git diff --check` exit with code 0. _Satisfied by:_ Task 3.
- **REQ-009** [constraint] — Work is committed on `codex/readme-philosophy` and merged only through an explicit owner-approved action; `main` remains clean until then. _Acceptance:_ `git branch --show-current` returns `codex/readme-philosophy` during implementation and `git diff main...HEAD --name-only` lists only intended documentation files. _Satisfied by:_ Task 3.

### Cross-task contracts

- **REQ-010** [contract] — The README's explanation and GitHub description share the same experience-shaped positioning while serving different purposes: README provides detail; GitHub metadata provides the one-line discovery summary. _Acceptance:_ README contains `experience-shaped` and the exact description from REQ-007 matches the remote API value. _Satisfied by:_ Task 1 + Task 2 + Task 3.

## File Structure

- Modify: `README.md` — concrete philosophy, conditional skill routing, quality loop, supporting skills, and example.
- Create: `docs/superpowers/plans/2026-09-13-readme-philosophy-usage.md` — this execution plan.
- Remote metadata: GitHub repository description only.
- Do not modify: `plugins/`, manifests, receipts, hero asset, or other documentation sections unless a link needs consistency repair.

### Task 1: Rewrite README narrative and usage guidance

**Satisfies:** REQ-001, REQ-002, REQ-003, REQ-004, REQ-005, REQ-006, REQ-010

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Keep the title and hero, then replace the repeated opening with one first-person framing sentence.** Use the approved positioning: this is a workflow shaped through hands-on engineering work and shared for inspection, adaptation, and reuse.
- [ ] **Step 2: Add `What this repository shares` and `My working philosophy`.** Explain evidence-first work, explicit decisions, durable specs/plans, isolation, independent evidence, the two-dimensional quality loop, and owner-controlled publication without tutorial or universal-prescription language.
- [ ] **Step 3: Add `How I use the workflow` as a conditional routing table.** Include the exact routing rule: large implementations use `Sequential Task Orchestrator`; small implementations use `Codex Implement`; Claude users can use `Claude Implement`. State that not every task needs every stage.
- [ ] **Step 4: Add `The quality loop` and `Supporting skills`.** Explain `Test Gaps` versus `Test-Driven Development`, the TDD fix cycle, and the roles of `Impeccable`, `UI UX Pro Max`, `Caveman`, and `How to Use Codex`.
- [ ] **Step 5: Add one short conditional example and the Graph Engineering V5.2 status note.** Show the large/uncertain path and state that a small clear change can start with Codex Implement while retaining relevant verification and owner gates.
- [ ] **Step 6: Re-read retained sections and remove only prose that now duplicates the new narrative.** Keep Mermaid, installation, customization, compatibility, provenance, and license sections.

### Task 2: Update public GitHub repository description

**Satisfies:** REQ-007, REQ-010

**Files:**
- Remote: `GiuseppeVe/agentic-engineering-skills` repository metadata

- [ ] **Step 1: Set the description to this exact value.**

```text
An experience-shaped workflow of composable skills for Codex and Claude Code: evidence, design, planning, implementation, verification, and review.
```

Run: `gh repo edit GiuseppeVe/agentic-engineering-skills --description "An experience-shaped workflow of composable skills for Codex and Claude Code: evidence, design, planning, implementation, verification, and review."`
Expected: command exits with code `0`.

- [ ] **Step 2: Read the remote description back and compare it byte-for-byte with the approved value.**

### Task 3: Verify and prepare delivery

**Satisfies:** REQ-006, REQ-008, REQ-009, REQ-010

**Files:**
- Test: README content, repository verification commands, and Git diff inspection

- [ ] **Step 1: Run `npm run verify:pack`.** Expected: exit code `0`.
- [ ] **Step 2: Run `npm run audit:public`.** Expected: exit code `0`.
- [ ] **Step 3: Run `git diff --check`.** Expected: no output.
- [ ] **Step 4: Confirm `git diff --name-only main...HEAD` contains README and plan/spec documentation only, with no `plugins/` path.**
- [ ] **Step 5: Confirm the working tree is clean except for intentionally untracked local files outside the commit, then commit the README change on `codex/readme-philosophy`.**

```bash
git add README.md docs/superpowers/plans/2026-09-13-readme-philosophy-usage.md
git commit -m "docs: explain workflow philosophy and usage"
```

## Self-review

- Spec coverage: all approved narrative, routing, quality-loop, metadata, preservation, and scope rules map to `REQ-001` through `REQ-010`.
- Traceability: every requirement maps to a task; every task lists its requirements.
- Cross-task contract: README positioning and GitHub one-line description are explicitly linked by `REQ-010`.
- Acceptance oracles: each requirement has a grep, API value, command exit code, or Git diff check.
- Scope: only README prose and GitHub description are implementation targets; no skill payload or hero changes.
