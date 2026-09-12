# README Visual Branding Implementation Plan

> **For agentic workers:** REQUIRED EXECUTION SKILL: Use `sequential-task-orchestrator` for ordered execution, or execute inline with explicit checkpoints. `sol-implement` is not part of this repository workflow.

**Goal:** Add a polished, original hero graphic and sharpen the README opening so the public repository presents a hands-on workflow worth sharing.

**Architecture:** Keep branding assets outside the plugin payload in `assets/`. Use one self-contained SVG for exact typography and workflow labels, then reference it from the README with a relative path. Preserve the existing Mermaid diagram and all skill files.

**Tech Stack:** Markdown, standalone SVG, Node.js repository verification scripts, Git.

---

## Requirements Inventory

### Behavior & constraints

- **REQ-001** [behavior] — The repository contains an original hero graphic at `assets/agentic-engineering-skills-hero.svg`. _Acceptance:_ `Test-Path assets/agentic-engineering-skills-hero.svg` returns `True`, and `git ls-files` lists the path. _Satisfied by:_ Task 1.
- **REQ-002** [behavior] — The hero communicates the approved B2 message with exact labels `Agentic Engineering Skills`, `A workflow worth sharing.`, and the workflow path `Evidence`, `Decisions`, `Spec`, `Plan`, `Implement`, `Test Gaps + TDD`, `Review`, `Owner Gate`. _Acceptance:_ a text search of the SVG finds all nine labels. _Satisfied by:_ Task 1.
- **REQ-003** [constraint] — The hero is a self-contained accessible SVG with no JavaScript, `foreignObject`, base64 data, remote references, or external fonts, and remains below 1 MB. _Acceptance:_ `rg -n "<title>|<desc>|<script|foreignObject|data:|https?://|@import|font-face" assets/agentic-engineering-skills-hero.svg` returns only the required `<title>` and `<desc>` lines; file size is `< 1048576` bytes. _Satisfied by:_ Task 1.
- **REQ-004** [behavior] — README places the hero immediately after the repository title and keeps a fallback textual introduction. _Acceptance:_ the first README section contains the relative image reference followed by a concise paragraph describing the shared workflow. _Satisfied by:_ Task 2.
- **REQ-005** [behavior] — README retains the existing Mermaid lifecycle diagram and links to the current workflow/philosophy documentation. _Acceptance:_ `rg -n "mermaid|docs/workflow.md|docs/philosophy.md" README.md` finds all three references. _Satisfied by:_ Task 2.
- **REQ-006** [behavior] — README explicitly labels Graph Engineering V5.2 as planned/out of scope until validated. _Acceptance:_ `rg -ni "Graph Engineering V5\.2|planned|out of scope" README.md` finds the status statement. _Satisfied by:_ Task 2.

### Tests

- **REQ-007** [test] — Repository packaging and public-safety verification pass after the visual changes. _Acceptance:_ `npm run verify:pack` and `npm run audit:public` both exit with code 0. _Satisfied by:_ Task 3.
- **REQ-008** [test] — The final diff contains no changes under `plugins/` and no tracked brainstorming session files. _Acceptance:_ `git diff --name-only main...HEAD` contains no `plugins/` path and `git ls-files '.superpowers/*'` returns no output. _Satisfied by:_ Task 3.

### Cross-task contracts

- **REQ-009** [contract] — README's relative image reference resolves to the exact SVG path created by Task 1, while the asset remains outside the plugin payload. _Acceptance:_ `README.md` contains `assets/agentic-engineering-skills-hero.svg`, and `git diff --name-only main...HEAD` shows both `README.md` and `assets/agentic-engineering-skills-hero.svg` but no plugin skill file. _Satisfied by:_ Task 1 + Task 2 + Task 3.

## File Structure

- Create: `assets/agentic-engineering-skills-hero.svg` — original static hero with accessible metadata and workflow path.
- Modify: `README.md` — hero placement, shared-workflow introduction, and current-scope note.
- Create: `docs/superpowers/plans/2026-09-12-readme-visual-branding.md` — this execution record.
- Do not modify: `plugins/`, skill manifests, receipts, or generated plugin payloads.

### Task 1: Create the original hero asset

**Satisfies:** REQ-001, REQ-002, REQ-003, REQ-009

**Files:**
- Create: `assets/agentic-engineering-skills-hero.svg`

- [ ] **Step 1: Create a 1200×420 SVG with exact text, embedded colors, `<title>`, `<desc>`, and a two-row evidence path.** Use only SVG primitives (`rect`, `line`, `path`, `circle`, `text`, `g`) and system font stacks; keep all workflow labels manually authored.
- [ ] **Step 2: Inspect the SVG as text and verify the forbidden-reference scan and byte-size limit.**

Run: `rg -n "<title>|<desc>|<script|foreignObject|data:|https?://|@import|font-face" assets/agentic-engineering-skills-hero.svg`  
Expected: only `<title>` and `<desc>` matches.  
Run: `(Get-Item assets/agentic-engineering-skills-hero.svg).Length -lt 1048576`  
Expected: `True`.

### Task 2: Integrate hero and positioning into README

**Satisfies:** REQ-004, REQ-005, REQ-006, REQ-009

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Insert the relative hero image directly below `# Agentic Engineering Skills`.** Use alt text that describes the workflow for readers who cannot see the image.
- [ ] **Step 2: Replace the abstract opening paragraph with a concise shared-workflow statement.** Explain that the repository shares an experience-shaped, inspectable workflow for Codex and Claude Code; do not use tutorial, course, or prescriptive language.
- [ ] **Step 3: Add one current-scope sentence stating that Graph Engineering V5.2 is planned and excluded until validated.** Leave installation, provenance, compatibility, license, and Mermaid sections intact except for links or wording needed for consistency.

### Task 3: Verify, review, and prepare the branch

**Satisfies:** REQ-007, REQ-008, REQ-009

**Files:**
- Test: repository verification commands and Git diff inspection

- [ ] **Step 1: Run `npm run verify:pack`.** Expected: exit code `0`.
- [ ] **Step 2: Run `npm run audit:public`.** Expected: exit code `0`; no local path or temporary-session finding.
- [ ] **Step 3: Run `git diff --check`.** Expected: no output.
- [ ] **Step 4: Confirm `git diff --name-only main...HEAD` includes only the spec, plan, hero, and README, with no `plugins/` path.**
- [ ] **Step 5: Confirm `.superpowers/` remains untracked and absent from `git ls-files`; clean only this task's temporary session before commit if needed.**
- [ ] **Step 6: Commit the verified visual pass on `codex/readme-branding`.**

```bash
git add assets/agentic-engineering-skills-hero.svg README.md docs/superpowers/plans/2026-09-12-readme-visual-branding.md
git commit -m "docs: add shared workflow README branding"
```

## Self-review

- Spec coverage: all approved visual, voice, scope, accessibility, and verification constraints appear as `REQ-001` through `REQ-009`.
- Traceability: every requirement maps to a task, and every task lists its requirements.
- Cross-task wiring: README path and asset location are captured by `REQ-009`.
- Placeholder scan: no `TBD`, `TODO`, or non-objective acceptance language.
- Scope control: no plugin payload, Graph Engineering V5.2, social-preview upload, or GitHub settings work included.
