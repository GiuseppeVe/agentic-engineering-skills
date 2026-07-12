# Distributable Skill and Agent Pack Implementation Plan

> **For agentic workers:** REQUIRED EXECUTION SKILL: Use `implementing-plans` with `swarm-orchestration` to implement this plan end-to-end. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a self-contained, license-audited skill and agent pack that users can clone and use without relying on private local files.

**Architecture:** Follow `docs/skill-provenance.md`: vendor exact public upstream documents under `skills/vendor/`, place repository-author modifications under `skills/adapted/`, and place sanitized original workflows under `skills/original/`. Preserve notices and record a per-skill provenance entry.

**Tech Stack:** Markdown, JSON, Node.js scripts, Vitest, GitHub Actions.

---

## Requirements Inventory

### Behavior & constraints

- **REQ-001** [constraint] — No local skill file without explicit upstream provenance and verified license is copied into the public pack. _Acceptance:_ `tests/pack-provenance.test.ts` rejects a vendored/adapted entry without a source, immutable revision, license, upstream path, and notice path. _Satisfied by:_ Task 1.
- **REQ-002** [behavior] — Pack vendors only skills listed as vendored in `docs/skill-provenance.md` from their recorded MIT or Apache-2.0 source revisions. _Acceptance:_ manifest test finds each document, upstream path, status, and pin. _Satisfied by:_ Task 2, Task 3.
- **REQ-003** [behavior] — Pack publishes every listed adapted skill under `skills/adapted/` with an upstream notice and a header naming repository-author changes; adapted Ruflo orchestration excludes its separately licensed `src/ruvocal` subtree. _Acceptance:_ contract test checks status/header and repository search finds no `ruvocal` path. _Satisfied by:_ Task 4.
- **REQ-004** [constraint] — Apache-2.0 `learn-codebase` material includes complete Apache-2.0 text and exact upstream NOTICE before vendoring. _Acceptance:_ provenance test compares required license/notice paths and verifies they are non-empty. _Satisfied by:_ Task 3.
- **REQ-005** [behavior] — Original skills `implementing-plans` and `cleaning-repo-with-knip` contain only sanitized public repository-author material. _Acceptance:_ each `skills/original/<name>/SKILL.md` has required headings and `status: original` in manifest. _Satisfied by:_ Task 5.
- **REQ-006** [behavior] — Seven agent profiles are complete, host-neutral adaptations of the public Cavecrew responsibility model and retain an upstream notice. _Acceptance:_ profile contract test finds Input, Allowed actions, Structured output, Validation, and Failure path in all seven files. _Satisfied by:_ Task 5.
- **REQ-007** [behavior] — README explains download/installation, pack structure, individual skill selection, agent profile use, compatibility assumptions, provenance, and optional integrations. _Acceptance:_ README contract test finds every required section and links resolve to tracked files. _Satisfied by:_ Task 5.
- **REQ-008** [constraint] — Public audit rejects secrets, private identifiers, private URLs, personal data markers, and transcript/log artifacts in tracked public files. _Acceptance:_ `npm run audit:public` passes repository and fails a tracked fixture containing each rule marker. _Satisfied by:_ Task 6.

### Tests

- **REQ-009** [test] — Test suite validates every skill and profile contract plus provenance and README links. _Acceptance:_ `npm test` passes pack tests. _Satisfied by:_ Task 1, Task 5, Task 6.
- **REQ-010** [test] — CI runs pack validation together with lint, build, evals, and public audit on Node 20. _Acceptance:_ `.github/workflows/ci.yml` contains the exact package commands once. _Satisfied by:_ Task 6.

### Cross-task contracts

- **REQ-011** [contract] — Each vendored/adapted skill directory is linked from `skills/README.md` and has one matching `sources.lock.json` entry. _Acceptance:_ manifest test maps directory names to manifest entries one-to-one. _Satisfied by:_ Task 1 + Task 2 + Task 4.
- **REQ-012** [contract] — Each third-party manifest entry's `noticePath` points to a tracked NOTICE or license file preserved in the repository. _Acceptance:_ provenance verifier opens every declared notice path. _Satisfied by:_ Task 1 + Task 2 + Task 3.

## File Structure

| Path | Responsibility |
| --- | --- |
| `skills/{vendor,adapted,original}/<name>/SKILL.md` | Installable, public skill document. |
| `skills/sources.lock.json` | Per-skill source, SHA, path, license, status, notice mapping. |
| `skills/README.md` | Pack index and installation/use instructions. |
| `agent-profiles/*.md` | Seven host-neutral agent contracts. |
| `licenses/`, `THIRD_PARTY_NOTICES.md` | Full licenses and exact notices. |
| `scripts/verify-skill-sources.mjs` | Structural provenance verifier. |
| `scripts/audit-public.mjs` | Tracked-public-surface scanner. |
| `tests/pack-*.test.ts` | Pack, provenance, and documentation contracts. |

## Implementation Tasks

### Task 1: Strengthen provenance schema and pack contract tests

**Satisfies:** REQ-001, REQ-009, REQ-011, REQ-012

**Files:**
- Modify: `skills/sources.lock.json`
- Modify: `scripts/verify-skill-sources.mjs`
- Create: `tests/pack-provenance.test.ts`

- [ ] **Step 1: Write failing provenance tests**

Assert every entry has `name`, `source`, full 40-character `revision`, `upstreamPath`, `license`, `status`, `dependencies`, and `noticePath`; assert vendored/adapted status has a tracked notice path and skill directory.

- [ ] **Step 2: Run focused test**

Run: `npm test -- --run tests/pack-provenance.test.ts`
Expected: FAIL until schema and pack directories exist.

- [ ] **Step 3: Implement schema verifier**

Parse the lock file once, reject unrecognized statuses, resolve each `noticePath` under repository root, and print only entry name plus missing field/path.

- [ ] **Step 4: Verify focused contract**

Run: `npm test -- --run tests/pack-provenance.test.ts && npm run verify:skills`
Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add skills/sources.lock.json scripts/verify-skill-sources.mjs tests/pack-provenance.test.ts && git commit -m "test(pack): enforce provenance contracts"`

### Task 2: Vendor verified MIT skill documents only

**Satisfies:** REQ-002, REQ-011, REQ-012

**Files:**
- Create: `skills/grilling/`, `skills/domain-modeling/`, `skills/codebase-design/`
- Create: `skills/using-git-worktrees/`, `skills/test-driven-development/`
- Create: `skills/caveman/`, `skills/swarm-orchestration/`
- Create: `licenses/MIT-mattpocock-skills.txt`, `licenses/MIT-obra-superpowers.txt`, `licenses/MIT-caveman.txt`, `licenses/MIT-ruflo.txt`
- Modify: `skills/sources.lock.json`, `THIRD_PARTY_NOTICES.md`

- [ ] **Step 1: Fetch only exact audited documents**

Download raw files from these immutable paths, never from local unlicensed copies:

```text
mattpocock/skills@391a2701dd948f94f56a39f7533f8eea9a859c87
obra/superpowers@d884ae04edebef577e82ff7c4e143debd0bbec99
JuliusBrussee/caveman@0d95a81d35a9f2d123a5e9430d1cfc43d55f1bb0
ruvnet/ruflo@7ef4d4e655d81c0451f6f40f35729cce6c9928e7
```

- [ ] **Step 2: Preserve notices**

Copy each upstream root MIT license into its named destination and add source, SHA, upstream path, copyright, and unmodified status to notices.

- [ ] **Step 3: Guard Ruflo scope**

Vendor only `.agents/skills/swarm-orchestration/`; do not download `src/ruvocal/` or any other Ruflo subtree.

- [ ] **Step 4: Run provenance checks**

Run: `npm test -- --run tests/pack-provenance.test.ts && npm run verify:skills`
Expected: PASS with every MIT skill and notice mapped.

- [ ] **Step 5: Commit**

Run: `git add skills licenses THIRD_PARTY_NOTICES.md && git commit -m "feat(pack): vendor verified MIT skills"`

### Task 3: Vendor Apache-2.0 codebase-learning skill with exact notice

**Satisfies:** REQ-002, REQ-004, REQ-012

**Files:**
- Create: `skills/learn-codebase/SKILL.md`
- Modify: `licenses/Apache-2.0.txt`, `licenses/claude-mem-NOTICE.txt`, `skills/sources.lock.json`, `THIRD_PARTY_NOTICES.md`

- [ ] **Step 1: Replace Apache pointer with complete license text**

Use canonical Apache-2.0 license text before any Apache material is copied.

- [ ] **Step 2: Preserve exact upstream notice and audited skill**

Copy upstream root NOTICE and `plugin/skills/learn-codebase/SKILL.md` from `thedotmack/claude-mem@312d640b0188753acd92a1a82d95a84d5c7c43db`.

- [ ] **Step 3: Register provenance**

Record `license: "Apache-2.0"`, `status: "vendored"`, exact source path, and both license/notice paths.

- [ ] **Step 4: Verify**

Run: `npm test -- --run tests/pack-provenance.test.ts && npm run verify:skills`
Expected: PASS.

- [ ] **Step 5: Commit**

Run: `git add skills/learn-codebase licenses THIRD_PARTY_NOTICES.md && git commit -m "feat(pack): add Apache codebase skill"`

### Task 4: Package audited adapted workflow skills

**Satisfies:** REQ-003, REQ-011

**Files:**
- Create: `skills/adapted/{wayfinder,to-spec,brainstorming,writing-plans,cavecrew,swarm-orchestration}/SKILL.md`
- Modify: `skills/sources.lock.json`, `skills/README.md`

- [ ] **Step 1: Write contract test**

Require frontmatter, upstream notice, author-change header, and sections `When to use`, `Inputs`, `Workflow`, `Validation`, and `Failure behavior` in every adapted skill.

- [ ] **Step 2: Run focused test**

Run: `npm test -- --run tests/pack-contract.test.ts`
Expected: FAIL before adapted skill documents exist.

- [ ] **Step 3: Write adapted host-neutral documents**

Start from each pinned permissive upstream skill, retain its notice, document repository-author changes, sanitize host-specific instructions, and state serial/manual fallback.

- [ ] **Step 4: Register adapted status**

Use upstream source and full SHA, `status: "adapted"`, plus upstream notice path and author-change summary.

- [ ] **Step 5: Verify and commit**

Run: `npm test -- --run tests/pack-contract.test.ts && git add skills && git commit -m "feat(pack): add adapted workflow skills"`

### Task 5: Write original public workflow skills

**Satisfies:** REQ-005, REQ-011

**Files:**
- Create: `skills/original/implementing-plans/SKILL.md`, `skills/original/cleaning-repo-with-knip/SKILL.md`
- Modify: `skills/sources.lock.json`, `skills/README.md`

- [ ] **Step 1: Write failing original-skill contract test**

Require frontmatter and sections `When to use`, `Inputs`, `Workflow`, `Validation`, and `Failure behavior` in each original skill.

- [ ] **Step 2: Run focused test**

Run: `npm test -- --run tests/pack-contract.test.ts`
Expected: FAIL before original skill documents exist.

- [ ] **Step 3: Write sanitized original documents**

Use repository-author wording only. Exclude private tool names, internal prompts, local paths, source-project material, and copied protected expression.

- [ ] **Step 4: Register original status**

Use repository source, immutable base commit `d248470`, `status: "original"`, and no third-party notice path.

- [ ] **Step 5: Verify and commit**

Run: `npm test -- --run tests/pack-contract.test.ts && git add skills && git commit -m "feat(pack): add original workflow skills"`

### Task 6: Finish agent pack and public README

**Satisfies:** REQ-006, REQ-007, REQ-009, REQ-011

**Files:**
- Modify: `agent-profiles/*.md`, `README.md`, `skills/README.md`
- Create: `tests/agent-profiles.test.ts`, `tests/pack-readme.test.ts`

- [ ] **Step 1: Write failing profile and README tests**

Assert exactly seven named profiles have five contract sections. Assert README links all skill directories and explains clone/download, selective install, provenance, compatibility, and fallback behavior.

- [ ] **Step 2: Run focused tests**

Run: `npm test -- --run tests/agent-profiles.test.ts tests/pack-readme.test.ts`
Expected: FAIL until documentation is complete.

- [ ] **Step 3: Complete profiles and README**

Each profile names inputs, allowed actions, structured output, validation, and failure path. README contains no host-specific hidden requirement and labels external integrations optional.

- [ ] **Step 4: Verify and commit**

Run: `npm test -- --run tests/agent-profiles.test.ts tests/pack-readme.test.ts && git add agent-profiles README.md skills/README.md tests && git commit -m "docs(pack): publish agent and skill guides"`

### Task 7: Harden public audit and release verification

**Satisfies:** REQ-008, REQ-009, REQ-010

**Files:**
- Modify: `scripts/audit-public.mjs`, `tests/public-audit.test.ts`, `.github/workflows/ci.yml`

- [ ] **Step 1: Add tracked-file audit cases**

Use a temporary Git repository fixture. Assert scan rejects each rule marker only when it is tracked and ignores untracked test artifacts.

- [ ] **Step 2: Implement tracked-file enumeration**

Use `git ls-files -z`; if target is not a Git repository, fail with an explanatory message instead of scanning arbitrary files.

- [ ] **Step 3: Run complete release suite on Node 20**

Run: `npm ci && npm run lint && npm test && npm run build && npm run evals && npm run audit:public && npm run verify:skills && npm run maintenance:scan`
Expected: all commands exit 0; Knip may emit advisory findings but makes no edits.

- [ ] **Step 4: Inspect published surface**

Run: `git status --short && git ls-files skills agent-profiles licenses THIRD_PARTY_NOTICES.md README.md`
Expected: expected pack paths tracked, no secrets/private artifacts.

- [ ] **Step 5: Commit**

Run: `git add scripts tests .github/workflows/ci.yml && git commit -m "test(pack): verify public release surface"`

## Plan Self-Review

- Every provenance, licensing, pack, profile, documentation, audit, and CI obligation maps to REQ-001 through REQ-012.
- Vendored directory, manifest entry, and notice file are connected by REQ-011 and REQ-012.
- No local ready file is treated as licensed evidence; every third-party fetch has a verified source and SHA.
- No unlicensed or uncertain source is copied; any new uncertainty is a user decision before implementation.
