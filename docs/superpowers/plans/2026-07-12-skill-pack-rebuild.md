# Agentic Engineering Skills Pack Rebuild Implementation Plan

> **For agentic workers:** REQUIRED EXECUTION SKILL: Use implementing-plans with swarm-orchestration to implement this plan end-to-end. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the failed harness implementation with one audited, installable 19-skill bundle for Codex and Claude Code, plus accurate workflow documentation and licensing.

**Architecture:** One shared plugin payload lives at `plugins/agentic-engineering-skills/`; Codex and Claude Code marketplaces both reference it. Skills use flat Agent Skills discovery paths, while a discriminated provenance lock records `vendor`, `adapted`, or `original` status and drives verification, documentation, and license gates.

**Tech Stack:** Markdown Agent Skills, JSON manifests, Node.js 22 ESM, built-in `node:test`, Git/GitHub Actions, Codex plugin validator, Claude Code plugin validator.

---

## Requirements Inventory

### Behavior and constraints

- **REQ-001** [constraint] — The release contains no TypeScript harness, runtime runner, demo agent, mock orchestration runtime, or harness eval. _Acceptance:_ `npm test -- --test-name-pattern="legacy harness"` passes and `git ls-files` contains none of `src/`, `evals/`, `tsconfig.json`, or `vitest.config.*`. _Satisfied by:_ Task 1, Task 11.
- **REQ-002** [behavior] — The requested inventory contains exactly the 19 skill names approved in the design. _Acceptance:_ `node scripts/verify-pack.mjs` prints `Verified 19 requested skills`. _Satisfied by:_ Task 1, Task 4, Task 5.
- **REQ-003** [constraint] — No substitute skill text is invented; every distributed skill is copied from a verified local or upstream source. _Acceptance:_ every lock entry has `sourceType` equal to `upstream` or `original`, and `docs/provenance.md` records its acquisition source. _Satisfied by:_ Task 3, Task 4, Task 5, Task 7.
- **REQ-004** [constraint] — Every `vendor` skill is byte-identical to its pinned upstream content. _Acceptance:_ `node scripts/verify-upstream.mjs --status vendor` exits 0 and prints one verified line per vendor skill. _Satisfied by:_ Task 3, Task 4.
- **REQ-005** [constraint] — Every `adapted` skill has verified upstream ancestry, a local hash, a non-empty change notice, and a stored patch. _Acceptance:_ `node scripts/verify-pack.mjs --status adapted` exits 0 and every file matched by `manifests/patches/*.patch` is non-empty. _Satisfied by:_ Task 3, Task 5.
- **REQ-006** [constraint] — Every `original` skill records a local hash and repository license without a fabricated upstream revision. _Acceptance:_ manifest tests reject `revision` on original entries and require `releaseCommit`. _Satisfied by:_ Task 3, Task 5.
- **REQ-007** [constraint] — Skill directories are flat at `plugins/agentic-engineering-skills/skills/*/SKILL.md`. _Acceptance:_ structure test rejects nested classification directories and finds every approved name directly below `skills/`. _Satisfied by:_ Task 2, Task 4, Task 5.
- **REQ-008** [behavior] — The complete bundle is the supported install path for both Codex and Claude Code. _Acceptance:_ native validators and both local install smoke tests discover the same included inventory. _Satisfied by:_ Task 2, Task 10.
- **REQ-009** [behavior] — Selective installation is documented as advanced use with dependencies, license preservation, and lost workflow stages. _Acceptance:_ documentation contract test validates one matrix row per included skill and required columns. _Satisfied by:_ Task 7.
- **REQ-010** [behavior] — Users may fork, edit, remove, and redistribute content under applicable licenses; no proprietary override system is introduced. _Acceptance:_ `docs/customization.md` contract test finds fork workflow, direct edits, redistribution caveat, and cache warning. _Satisfied by:_ Task 7.
- **REQ-011** [constraint] — No upstream update bot, schedule, latest channel, or automatic dependency update is included. _Acceptance:_ repository test rejects Dependabot/Renovate configs, scheduled dependency workflows, and `latest` install flags. _Satisfied by:_ Task 1, Task 11.
- **REQ-012** [constraint] — Original repository material is MIT licensed under `GiuseppeVe`; third-party licenses remain separately applicable. _Acceptance:_ license test matches canonical MIT text and `THIRD_PARTY_NOTICES.md` maps all third-party entries to retained license files. _Satisfied by:_ Task 6.
- **REQ-013** [constraint] — Apache-2.0 material retains the exact applicable license and upstream NOTICE, and modified Apache files carry prominent change notices. _Acceptance:_ license test compares retained files to the pinned upstream revision and inspects adapted Apache headers. _Satisfied by:_ Task 5, Task 6.
- **REQ-014** [behavior] — README explains problem, philosophy, seven workflow phases, installation, customization, compatibility, provenance, and licensing without claiming unsupported hosts. _Acceptance:_ README contract test checks headings and the phase sequence `Understand -> Design -> Plan -> Implement -> Verify -> Review -> Clean`. _Satisfied by:_ Task 7.
- **REQ-015** [constraint] — Codex and Claude Code are the only verified hosts; other Agent Skills hosts are documented as unverified manual adaptation targets. _Acceptance:_ compatibility contract test finds exactly two `verified` host rows. _Satisfied by:_ Task 7, Task 10.
- **REQ-016** [constraint] — Public audit scans only Git-tracked release files and detects realistic OpenAI, Anthropic, Google, GitHub, private-key, environment-file, personal-path, private-URL, legal-template, log, generated-artifact, and oversize-file fixtures. _Acceptance:_ `node --test tests/public-audit.test.mjs` passes all positive and negative fixtures. _Satisfied by:_ Task 8.
- **REQ-017** [constraint] — Any requested skill that fails source or legal verification is excluded from both host packages and recorded with an objective failure reason. _Acceptance:_ exclusion fixture test removes one source, then asserts verifier reports the same exclusion in lock and release report. _Satisfied by:_ Task 3, Task 9.
- **REQ-018** [constraint] — Existing `impl/agentic-harness-workflow` remains untouched and original dirty `main` worktree changes remain preserved. _Acceptance:_ final handoff records branch/worktree status before and after; no command deletes, resets, or force-updates them. _Satisfied by:_ Task 11.
- **REQ-019** [constraint] — Commit, push, PR, merge, branch cleanup, and visibility change remain separate explicit approvals. _Acceptance:_ final report lists each as `not performed` unless separately approved. _Satisfied by:_ Task 11.
- **REQ-020** [behavior] — Superseded harness specifications are absent from the release branch so public documentation cannot contradict the rebuilt product. _Acceptance:_ `git ls-files docs/superpowers` contains only rebuild design and plan artifacts. _Satisfied by:_ Task 9.
- **REQ-033** [constraint] — CI uses Node 22 on Ubuntu, `contents: read`, a 15-minute timeout, push/PR/manual triggers only, and no schedule. _Acceptance:_ `tests/ci-contract.test.mjs` parses and asserts each workflow setting. _Satisfied by:_ Task 9.

### Tests

- **REQ-021** [test] — A repository contract test prevents reintroduction of harness files or update automation. _Acceptance:_ `node --test tests/repository-contract.test.mjs` passes. _Satisfied by:_ Task 1.
- **REQ-022** [test] — Manifest tests cover valid entries, missing fields, fake original revisions, dependency cycles, unknown dependencies, and hash mismatch. _Acceptance:_ `node --test tests/manifest.test.mjs` passes all named cases. _Satisfied by:_ Task 3.
- **REQ-023** [test] — Plugin contract tests validate both manifests, both marketplaces, flat discovery, and shared inventory. _Acceptance:_ `node --test tests/plugin-contract.test.mjs` passes. _Satisfied by:_ Task 2.
- **REQ-024** [test] — Provenance integration tests verify a real pinned upstream file and detect tampering. _Acceptance:_ `node --test tests/provenance.test.mjs` passes online in CI. _Satisfied by:_ Task 3.
- **REQ-025** [test] — Documentation tests resolve every local link and inventory table entry. _Acceptance:_ `node --test tests/docs-contract.test.mjs` passes. _Satisfied by:_ Task 7.
- **REQ-026** [test] — Public-audit tests exercise every forbidden marker and one clean control fixture. _Acceptance:_ test output lists at least 10 passing audit cases. _Satisfied by:_ Task 8.
- **REQ-027** [test] — CI executes pack, provenance, license, plugin, documentation, public-audit, and native validation gates. _Acceptance:_ workflow contract test parses `.github/workflows/ci.yml` and finds every named command. _Satisfied by:_ Task 9.
- **REQ-028** [test] — Real local smoke tests install and discover the bundle in Codex and Claude Code. _Acceptance:_ `docs/release-report.md` records command, host version, exit code 0, and 19 discovered names for each host unless a documented inclusion gate excluded a skill. _Satisfied by:_ Task 10.

### Cross-task contracts

- **REQ-029** [contract] — `.agents/plugins/marketplace.json` and `.claude-plugin/marketplace.json` both resolve to `plugins/agentic-engineering-skills/`. _Acceptance:_ plugin contract test resolves both source paths and compares their real paths. _Satisfied by:_ Task 2.
- **REQ-030** [contract] — `manifests/skills.lock.json`, flat skill directories, documentation inventory, and both native discovery results contain the same included skill set. _Acceptance:_ integrated pack verifier compares all four sets and exits non-zero on any difference. _Satisfied by:_ Task 3, Task 7, Task 10.
- **REQ-031** [contract] — Every third-party lock entry resolves to a retained license/NOTICE referenced by `THIRD_PARTY_NOTICES.md`; selective-install rows use the same dependency data. _Acceptance:_ integrated license test joins lock, notices, license files, and selective matrix by skill name. _Satisfied by:_ Task 6, Task 7.
- **REQ-032** [contract] — README installation commands use the exact marketplace and plugin names declared by native manifests. _Acceptance:_ docs contract test derives names from JSON and matches commands verbatim. _Satisfied by:_ Task 2, Task 7.

## File Structure

- `package.json` — Node 22 commands for all deterministic gates; no runtime dependencies.
- `tests/expected-inventory.mjs` — canonical requested 19-name test fixture.
- `tests/repository-contract.test.mjs` — no-harness and no-update-automation regression checks.
- `tests/plugin-contract.test.mjs` — native manifest, marketplace, path, and shared-inventory contracts.
- `tests/manifest.test.mjs` — discriminated provenance schema, hashes, and dependency graph cases.
- `tests/provenance.test.mjs` — pinned upstream and tampering integration tests.
- `tests/license.test.mjs` — root MIT and third-party license/NOTICE joins.
- `tests/docs-contract.test.mjs` — headings, links, compatibility, selective matrix, and install commands.
- `tests/public-audit.test.mjs` — tracked-file audit fixtures.
- `tests/ci-contract.test.mjs` — required CI gate names and commands.
- `scripts/lib/hash.mjs` — deterministic file/tree SHA-256.
- `scripts/lib/manifest.mjs` — lock parsing, schema validation, dependency graph, and inventory comparison.
- `scripts/lib/upstream.mjs` — temporary Git checkout at immutable revisions.
- `scripts/import-vendor.mjs` — byte-exact import from source manifest.
- `scripts/generate-patches.mjs` — deterministic adapted-skill diffs from pinned upstream.
- `scripts/stamp-originals.mjs` — record the real first-distribution commit for original skills.
- `scripts/verify-pack.mjs` — local integrated pack/provenance/license/docs verifier.
- `scripts/verify-upstream.mjs` — online source, revision, path, and hash verification.
- `scripts/audit-public.mjs` — Git-tracked release-surface audit.
- `manifests/skill-sources.json` — approved acquisition sources and immutable upstream pins.
- `manifests/skills.lock.json` — generated auditable distribution lock.
- `manifests/patches/*.patch` — adapted-skill diffs from pinned upstream.
- `.agents/plugins/marketplace.json` — Codex repo marketplace.
- `.claude-plugin/marketplace.json` — Claude Code marketplace.
- `plugins/agentic-engineering-skills/.codex-plugin/plugin.json` — Codex manifest.
- `plugins/agentic-engineering-skills/.claude-plugin/plugin.json` — Claude Code manifest.
- `plugins/agentic-engineering-skills/skills/*/` — flat canonical skill packages.
- `plugins/agentic-engineering-skills/licenses/` — licenses shipped inside installed payload.
- `LICENSE` — root MIT license for original repository material.
- `THIRD_PARTY_NOTICES.md` — human-readable third-party attribution.
- `README.md` — concise product and installation entry point.
- `docs/workflow.md` — detailed philosophy and phase/skill map.
- `docs/customization.md` — fork/edit/redistribute workflow.
- `docs/compatibility.md` — verified/unverified host matrix.
- `docs/provenance.md` — human-readable acquisition and modification record.
- `docs/selective-install.md` — advanced subset matrix.
- `docs/release-checklist.md` — manual release gate.
- `docs/release-report.md` — generated evidence and excluded-skill report.
- `.github/workflows/ci.yml` — required automated gates.

## Source Map

Use these immutable upstream revisions; verification must confirm each path before copying:

| Source | Revision | Skills |
| --- | --- | --- |
| `https://github.com/mattpocock/skills` | `391a2701dd948f94f56a39f7533f8eea9a859c87` | `grill-me`, `grilling`, `wayfinder`, `to-spec`, `setup-matt-pocock-skills`, `improve-codebase-architecture`, `codebase-design`, `domain-modeling` |
| `https://github.com/obra/superpowers` | `d884ae04edebef577e82ff7c4e143debd0bbec99` | `brainstorming`, `writing-plans`, `writing-skills`, `test-driven-development`, `using-git-worktrees` |
| `https://github.com/JuliusBrussee/caveman` | `0d95a81d35a9f2d123a5e9430d1cfc43d55f1bb0` | `caveman`, `cavecrew` |
| `https://github.com/ruvnet/ruflo` | `7ef4d4e655d81c0451f6f40f35729cce6c9928e7` | `swarm-orchestration` |
| `https://github.com/thedotmack/claude-mem` | `312d640b0188753acd92a1a82d95a84d5c7c43db` | `learn-codebase` |

Exact upstream package paths:

| Skill | Upstream path |
| --- | --- |
| `grill-me` | `skills/productivity/grill-me/SKILL.md` |
| `grilling` | `skills/productivity/grilling/SKILL.md` |
| `wayfinder` | `skills/engineering/wayfinder/SKILL.md` |
| `to-spec` | `skills/engineering/to-spec/SKILL.md` |
| `setup-matt-pocock-skills` | `skills/engineering/setup-matt-pocock-skills/` |
| `improve-codebase-architecture` | `skills/engineering/improve-codebase-architecture/SKILL.md` |
| `codebase-design` | `skills/engineering/codebase-design/SKILL.md` |
| `domain-modeling` | `skills/engineering/domain-modeling/SKILL.md` |
| `brainstorming` | `skills/brainstorming/SKILL.md` |
| `writing-plans` | `skills/writing-plans/SKILL.md` |
| `writing-skills` | `skills/writing-skills/` |
| `test-driven-development` | `skills/test-driven-development/` |
| `using-git-worktrees` | `skills/using-git-worktrees/` |
| `caveman` | `skills/caveman/SKILL.md` |
| `cavecrew` | `skills/cavecrew/SKILL.md` |
| `swarm-orchestration` | `.agents/skills/swarm-orchestration/SKILL.md` |
| `learn-codebase` | `plugin/skills/learn-codebase/SKILL.md` |

Local acquisition roots for adapted/original candidates:

```text
${AGENTIC_PROJECT_SKILLS_ROOT}
${AGENTIC_USER_SKILLS_ROOT}
${CODEX_SKILLS_ROOT}
```

Exact local candidates:

| Skill | Local file |
| --- | --- |
| `wayfinder` | `${AGENTIC_PROJECT_SKILLS_ROOT}/wayfinder/SKILL.md` |
| `to-spec` | `${AGENTIC_PROJECT_SKILLS_ROOT}/to-spec/SKILL.md` |
| `brainstorming` | `${AGENTIC_PROJECT_SKILLS_ROOT}/brainstorming/SKILL.md` |
| `writing-plans` | `${AGENTIC_PROJECT_SKILLS_ROOT}/writing-plans/SKILL.md` |
| `cavecrew` | `${AGENTIC_PROJECT_SKILLS_ROOT}/cavecrew/SKILL.md` |
| `swarm-orchestration` | `${AGENTIC_PROJECT_SKILLS_ROOT}/swarm-orchestration/SKILL.md` |
| `learn-codebase` | `${AGENTIC_USER_SKILLS_ROOT}/learn-codebase/SKILL.md` |
| `implementing-plans` | `${AGENTIC_PROJECT_SKILLS_ROOT}/implementing-plans/SKILL.md` |
| `cleaning-repo-with-knip` | `${AGENTIC_PROJECT_SKILLS_ROOT}/cleaning-repo-with-knip/SKILL.md` |

## Tasks

### Task 1: Establish repository contracts

**Satisfies:** REQ-001, REQ-002, REQ-011, REQ-021

**Files:**
- Create: `package.json`
- Create: `tests/expected-inventory.mjs`
- Create: `tests/repository-contract.test.mjs`

- [ ] **Step 1: Write inventory and failing repository tests**

```js
// tests/expected-inventory.mjs
export const expectedSkills = [
  "brainstorming", "caveman", "cavecrew", "cleaning-repo-with-knip",
  "codebase-design", "domain-modeling", "grill-me", "grilling",
  "implementing-plans", "improve-codebase-architecture", "learn-codebase",
  "setup-matt-pocock-skills", "swarm-orchestration",
  "test-driven-development", "to-spec", "using-git-worktrees", "wayfinder",
  "writing-plans", "writing-skills"
].sort();
```

Test `git ls-files` for forbidden harness paths and dependency-update configs, and assert `expectedSkills.length === 19`.

- [ ] **Step 2: Run tests and verify red**

Run: `node --test tests/repository-contract.test.mjs`
Expected: FAIL because `package.json` and plugin payload do not exist.

- [ ] **Step 3: Add minimal Node command surface**

```json
{
  "name": "agentic-engineering-skills",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "engines": { "node": ">=22" },
  "scripts": {
    "test": "node --test",
    "verify:pack": "node scripts/verify-pack.mjs",
    "verify:upstream": "node scripts/verify-upstream.mjs",
    "audit:public": "node scripts/audit-public.mjs"
  }
}
```

Run `npm install --package-lock-only --ignore-scripts` to create `package-lock.json`.

- [ ] **Step 4: Run test and commit**

Run: `npm test`
Expected: repository contract tests PASS; later suites are not present yet.

```bash
git add package.json package-lock.json tests
git commit -m "test: define skill pack contracts"
```

### Task 2: Create shared native plugin payload

**Satisfies:** REQ-007, REQ-008, REQ-023, REQ-029, REQ-032

**Files:**
- Create: `.agents/plugins/marketplace.json`
- Create: `.claude-plugin/marketplace.json`
- Create: `plugins/agentic-engineering-skills/.codex-plugin/plugin.json`
- Create: `plugins/agentic-engineering-skills/.claude-plugin/plugin.json`
- Create: `tests/plugin-contract.test.mjs`

- [ ] **Step 1: Write failing path and manifest contracts**

Test strict semver `0.1.0`, plugin name `agentic-engineering-skills`, Codex `skills: "./skills/"`, both marketplace source paths resolving to the same plugin directory, and flat skill discovery.

- [ ] **Step 2: Verify red**

Run: `node --test tests/plugin-contract.test.mjs`
Expected: FAIL with missing `.agents/plugins/marketplace.json`.

- [ ] **Step 3: Add exact native manifests**

Codex manifest core:

```json
{
  "name": "agentic-engineering-skills",
  "version": "0.1.0",
  "description": "A reproducible AI-engineering workflow skill pack.",
  "author": { "name": "GiuseppeVe", "url": "https://github.com/GiuseppeVe" },
  "homepage": "https://github.com/GiuseppeVe/agentic-engineering-skills",
  "repository": "https://github.com/GiuseppeVe/agentic-engineering-skills",
  "license": "MIT",
  "keywords": ["agent-skills", "codex", "claude-code", "workflow"],
  "skills": "./skills/",
  "interface": {
    "displayName": "Agentic Engineering Skills",
    "shortDescription": "A verified AI-engineering workflow",
    "longDescription": "Install a reproducible discovery-to-cleanup workflow for Codex and Claude Code.",
    "developerName": "GiuseppeVe",
    "category": "Productivity",
    "capabilities": ["Interactive", "Read", "Write"],
    "websiteURL": "https://github.com/GiuseppeVe/agentic-engineering-skills"
  }
}
```

Codex marketplace entry uses `source: {"source":"local","path":"./plugins/agentic-engineering-skills"}`, `installation: "AVAILABLE"`, `authentication: "ON_INSTALL"`, category `Productivity`. Claude marketplace uses relative source `./plugins/agentic-engineering-skills` and version `0.1.0`.

- [ ] **Step 4: Validate green and commit**

Run: `node --test tests/plugin-contract.test.mjs`
Expected: PASS with zero skill directories until import fixture is enabled in Task 4.

```bash
git add .agents .claude-plugin plugins tests/plugin-contract.test.mjs
git commit -m "feat: add shared native plugin shell"
```

### Task 3: Build provenance and pack verification

**Satisfies:** REQ-003, REQ-004, REQ-005, REQ-006, REQ-017, REQ-022, REQ-024, REQ-030

**Files:**
- Create: `manifests/skill-sources.json`
- Create: `manifests/skills.lock.json`
- Create: `scripts/lib/hash.mjs`
- Create: `scripts/lib/manifest.mjs`
- Create: `scripts/lib/upstream.mjs`
- Create: `scripts/import-vendor.mjs`
- Create: `scripts/generate-patches.mjs`
- Create: `scripts/stamp-originals.mjs`
- Create: `scripts/verify-pack.mjs`
- Create: `scripts/verify-upstream.mjs`
- Create: `tests/manifest.test.mjs`
- Create: `tests/provenance.test.mjs`

- [ ] **Step 1: Write failing discriminated-union tests**

Define `upstream` entries requiring `revision`, `upstreamPath`, `sha256`, and `localSha256`; define `original` entries forbidding upstream fields and requiring `releaseCommit`. Add cycle, unknown-dependency, tamper, and exclusion fixtures.

- [ ] **Step 2: Verify red**

Run: `node --test tests/manifest.test.mjs tests/provenance.test.mjs`
Expected: FAIL because verifier modules are missing.

- [ ] **Step 3: Implement deterministic hashing and validation**

```js
// scripts/lib/hash.mjs
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
export async function sha256File(path) {
  return createHash("sha256").update(await readFile(path)).digest("hex");
}
```

`manifest.mjs` must return sorted names, validate allowed fields by `sourceType`, walk dependencies with three-color DFS, and compare lock names to actual flat directories. `upstream.mjs` must create a temporary Git directory, fetch exactly the immutable commit with depth 1, and return the checked-out path without using a mutable branch.

- [ ] **Step 4: Encode approved sources and paths**

Use the five revisions and 17 exact paths in Source Map. Mark the current classifications: 7 `vendor`, 10 `adapted`, 2 `original`; verification may exclude a failed entry but may not silently reclassify it. `grill-me`, `improve-codebase-architecture`, and `setup-matt-pocock-skills` are adapted solely to enable Codex model invocation.

- [ ] **Step 5: Verify green and commit**

Run: `node --test tests/manifest.test.mjs tests/provenance.test.mjs`
Expected: PASS, including real pinned `obra/superpowers` fetch and tamper detection.

```bash
git add manifests scripts tests/manifest.test.mjs tests/provenance.test.mjs
git commit -m "feat: verify skill provenance"
```

### Task 4: Import byte-exact vendor skills

**Satisfies:** REQ-002, REQ-003, REQ-004, REQ-007, REQ-030

**Files:**
- Create: `plugins/agentic-engineering-skills/skills/{grill-me,grilling,setup-matt-pocock-skills,improve-codebase-architecture,codebase-design,domain-modeling,writing-skills,test-driven-development,using-git-worktrees,caveman}/`
- Modify: `manifests/skills.lock.json`
- Modify: `tests/plugin-contract.test.mjs`

- [ ] **Step 1: Make vendor inventory test fail**

Expected vendor candidates are `grilling`, `codebase-design`, `domain-modeling`, `writing-skills`, `test-driven-development`, `using-git-worktrees`, and `caveman`.

Run: `node --test tests/plugin-contract.test.mjs --test-name-pattern="vendor inventory"`
Expected: FAIL with 10 missing directories.

- [ ] **Step 2: Import only verified pinned content**

Run: `node scripts/import-vendor.mjs`
Expected: each source path verified before copy; command stops on first source/license failure and writes no partial lock entry.

- [ ] **Step 3: Verify exact copies**

Run: `node scripts/verify-upstream.mjs --status vendor`
Expected: one `VERIFIED vendor` line for each of the 7 vendor skills, or an explicit exclusion report requiring user review.

- [ ] **Step 4: Commit vendor snapshot**

```bash
git add plugins/agentic-engineering-skills/skills manifests/skills.lock.json
git commit -m "feat: vendor pinned workflow skills"
```

### Task 5: Import adapted and original local skills

**Satisfies:** REQ-002, REQ-003, REQ-005, REQ-006, REQ-013, REQ-030

**Files:**
- Create: `plugins/agentic-engineering-skills/skills/{wayfinder,to-spec,brainstorming,writing-plans,cavecrew,swarm-orchestration,learn-codebase}/`
- Create: `plugins/agentic-engineering-skills/skills/{implementing-plans,cleaning-repo-with-knip}/`
- Create: `manifests/patches/*.patch`
- Modify: `manifests/skills.lock.json`

- [ ] **Step 1: Write failing adapted/original contracts**

Test ten adapted candidates for upstream/local hashes, change notices, and non-empty patches. Test two originals for `sourceType: original`, local hashes, and absence of upstream revision.

- [ ] **Step 2: Copy from approved local roots**

Use exact existing `SKILL.md` files from the three Local acquisition roots. Do not synthesize missing content. Copy required companion files only after adding them to the source manifest.

- [ ] **Step 3: Sanitize minimally and generate patches**

For each adapted skill, compare against its pinned upstream base using:

```bash
node scripts/generate-patches.mjs
```

Expected: ten non-empty patches named `wayfinder.patch`, `to-spec.patch`, `grill-me.patch`, `improve-codebase-architecture.patch`, `setup-matt-pocock-skills.patch`,
`brainstorming.patch`, `writing-plans.patch`, `cavecrew.patch`,
`swarm-orchestration.patch`, and `learn-codebase.patch`.

Remove only private paths, proprietary references, invalid host-only tool names, and unsupported wiring. Preserve semantics and add a concise `Adaptation` notice naming upstream and modification purpose.

- [ ] **Step 4: Verify unstamped working snapshot**

Run: `node scripts/verify-pack.mjs --allow-unstamped-originals`
Expected: 19 requested skills pass every check except the two intentionally
unstamped `releaseCommit` values, or explicit excluded names and reasons with
no false success.

- [ ] **Step 5: Commit first distribution snapshot**

```bash
git add plugins/agentic-engineering-skills/skills manifests
git commit -m "feat: add adapted and original skills"
```

- [ ] **Step 6: Stamp real original release commit and verify strict**

Run:

```bash
node scripts/stamp-originals.mjs "$(git rev-parse HEAD)"
node scripts/verify-pack.mjs
```

Expected: both original entries record the exact preceding commit and verifier
prints `Verified 19 requested skills`.

- [ ] **Step 7: Commit provenance stamp**

```bash
git add manifests/skills.lock.json
git commit -m "chore: record original skill provenance"
```

### Task 6: Add compliant licensing bundle

**Satisfies:** REQ-012, REQ-013, REQ-031

**Files:**
- Create: `LICENSE`
- Create: `THIRD_PARTY_NOTICES.md`
- Create: `plugins/agentic-engineering-skills/licenses/*`
- Create: `tests/license.test.mjs`

- [ ] **Step 1: Write failing license joins**

Test canonical MIT copyright line `Copyright (c) 2026 GiuseppeVe`, every third-party lock entry's `licenseFiles`, exact upstream Apache license/NOTICE hashes, and notice-table coverage.

- [ ] **Step 2: Verify red**

Run: `node --test tests/license.test.mjs`
Expected: FAIL with missing root `LICENSE`.

- [ ] **Step 3: Copy exact legal texts and write notices**

Use canonical MIT text for repository originals. Copy each upstream license and applicable NOTICE from its pinned commit; never use unresolved template text. Record source, revision, skill names, status, copyright holder, license identifier, and modification notice in `THIRD_PARTY_NOTICES.md`.

- [ ] **Step 4: Verify and commit**

Run: `node --test tests/license.test.mjs && node scripts/verify-upstream.mjs --licenses`
Expected: PASS.

```bash
git add LICENSE THIRD_PARTY_NOTICES.md plugins/agentic-engineering-skills/licenses tests/license.test.mjs
git commit -m "docs: add skill licensing and notices"
```

### Task 7: Write workflow and installation documentation

**Satisfies:** REQ-009, REQ-010, REQ-014, REQ-015, REQ-025, REQ-030, REQ-031, REQ-032

**Files:**
- Create: `README.md`
- Create: `docs/workflow.md`
- Create: `docs/customization.md`
- Create: `docs/compatibility.md`
- Create: `docs/provenance.md`
- Create: `docs/selective-install.md`
- Create: `tests/docs-contract.test.mjs`

- [ ] **Step 1: Write failing documentation contracts**

Resolve every Markdown link, derive plugin/marketplace names from JSON, compare all inventory tables to the lock, require exactly two verified hosts, and require dependency/license/lost-stage columns in selective installation.

- [ ] **Step 2: Verify red**

Run: `node --test tests/docs-contract.test.mjs`
Expected: FAIL with missing `README.md`.

- [ ] **Step 3: Write README and focused docs**

README sequence is Problem, Philosophy, Workflow, Install, Customize, Compatibility, Provenance, License. `docs/workflow.md` maps the seven phases to included skills without claiming every skill triggers on every task. `docs/customization.md` uses fork/source edits and warns against editing plugin cache. `docs/selective-install.md` is generated from lock dependency data and retains required legal files.

- [ ] **Step 4: Verify and commit**

Run: `node --test tests/docs-contract.test.mjs`
Expected: PASS with 19 inventory rows and zero broken links.

```bash
git add README.md docs tests/docs-contract.test.mjs
git commit -m "docs: explain workflow and installation"
```

### Task 8: Implement tracked-file public audit

**Satisfies:** REQ-016, REQ-026

**Files:**
- Create: `scripts/audit-public.mjs`
- Create: `tests/public-audit.test.mjs`
- Create: `tests/fixtures/public-audit/clean.txt`

- [ ] **Step 1: Write failing table-driven fixtures**

Cover `sk-proj-`, `sk-ant-`, `AIza`, `ghp_`, PEM private keys, `.env`, Linux and Windows user-home paths, non-public URLs, unresolved legal template brackets, logs, generated archives, and files above the configured release limit. Include one clean fixture.

- [ ] **Step 2: Verify red**

Run: `node --test tests/public-audit.test.mjs`
Expected: FAIL because `audit-public.mjs` is absent.

- [ ] **Step 3: Implement Git-tracked scanning**

Use `git ls-files -z`, reject forbidden tracked names before reading content, cap reads safely, and report `path:rule` without printing secret values. Allow fixture injection through an explicit test-only file list argument; default always comes from Git.

- [ ] **Step 4: Verify and commit**

Run: `node --test tests/public-audit.test.mjs && npm run audit:public`
Expected: tests PASS; repository audit exits 0 without echoing matched secret material.

```bash
git add scripts/audit-public.mjs tests/public-audit.test.mjs tests/fixtures
git commit -m "test: audit public release surface"
```

### Task 9: Add CI, release evidence, and remove stale specs

**Satisfies:** REQ-017, REQ-020, REQ-027, REQ-033

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `tests/ci-contract.test.mjs`
- Create: `docs/release-checklist.md`
- Create: `docs/release-report.md`
- Delete: `docs/superpowers/specs/2026-07-12-agentic-harness-workflow.mdx`
- Delete: `docs/superpowers/plans/2026-07-12-agentic-harness-workflow.md`

- [ ] **Step 1: Write failing CI contract**

Require `npm ci`, `npm test`, `npm run verify:pack`, `npm run verify:upstream`, `npm run audit:public`, Codex validation, and Claude validation in the workflow.

- [ ] **Step 2: Verify red**

Run: `node --test tests/ci-contract.test.mjs`
Expected: FAIL with missing workflow.

- [ ] **Step 3: Add CI and manual evidence templates**

Use Node 22 on Ubuntu, least-privilege `contents: read`, timeout 15 minutes, and no scheduled trigger. Release report must list included/excluded skills, source gates, license gates, native versions, discovery results, and Git actions not performed.

- [ ] **Step 4: Remove contradictory harness documents**

Delete only the two superseded files named above; preserve the approved rebuild design and this plan.

- [ ] **Step 5: Verify and commit**

Run: `node --test tests/ci-contract.test.mjs tests/repository-contract.test.mjs`
Expected: PASS.

```bash
git add .github docs tests/ci-contract.test.mjs
git commit -m "ci: enforce skill pack release gates"
```

### Task 10: Validate and smoke-test Codex and Claude Code

**Satisfies:** REQ-008, REQ-015, REQ-028, REQ-030

**Files:**
- Modify: `docs/release-report.md`
- Modify: `docs/compatibility.md`

- [ ] **Step 1: Validate Codex plugin schema**

Run the installed `plugin-creator/scripts/validate_plugin.py` against `plugins/agentic-engineering-skills`.
Expected: exit 0 and valid manifest report.

- [ ] **Step 2: Validate Claude Code plugin and marketplace**

Run: `claude plugin validate .`
Expected: exit 0.

- [ ] **Step 3: Run isolated local installs**

Use temporary host homes/config directories. Add repository marketplace, install `agentic-engineering-skills`, start a fresh non-interactive host session, and record discovered skill names. Do not modify the user's normal Codex or Claude configuration.

- [ ] **Step 4: Compare discoveries and document evidence**

Run: `node scripts/verify-pack.mjs --native-report docs/release-report.md`
Expected: both native sets equal the lock included set.

- [ ] **Step 5: Commit evidence**

```bash
git add docs/release-report.md docs/compatibility.md
git commit -m "test: verify native skill discovery"
```

### Task 11: Run integrated finish gate

**Satisfies:** REQ-001, REQ-011, REQ-018, REQ-019

**Files:**
- Modify: `docs/release-report.md`

- [ ] **Step 1: Run complete deterministic suite**

Run:

```bash
npm ci
npm test
npm run verify:pack
npm run verify:upstream
npm run audit:public
```

Expected: every command exits 0; verifier reports 19 included skills or an explicit user-approved exclusion set.

- [ ] **Step 2: Confirm clean release tree**

Run:

```bash
git diff --check
git status --short
git ls-files | sort
```

Expected: no unstaged changes before final report update; no legacy harness paths or forbidden artifacts.

- [ ] **Step 3: Recheck protected branches/worktrees**

Record `git status --short --branch` for original `main`, quarantine worktree, and rebuild worktree. Confirm original staged files and quarantine branch were not reset, deleted, or force-updated.

- [ ] **Step 4: Write final implementation report and commit**

Update `docs/release-report.md` with commands, versions, exit codes, included/excluded inventory, native discovery, licensing result, public audit, and `not performed` status for push, PR, merge, cleanup, and visibility.

```bash
git add docs/release-report.md
git commit -m "docs: record skill pack verification"
```

- [ ] **Step 5: Stop before publication**

Present full diff, commit list, verification evidence, and remaining explicit GitHub actions to the repository owner. Do not push or change visibility without a new approval.

## Final Verification Matrix

| Gate | Command | Required result |
| --- | --- | --- |
| Repository contracts | `node --test tests/repository-contract.test.mjs` | PASS |
| Plugin contracts | `node --test tests/plugin-contract.test.mjs` | PASS |
| Manifest/provenance tests | `node --test tests/manifest.test.mjs tests/provenance.test.mjs` | PASS |
| License tests | `node --test tests/license.test.mjs` | PASS |
| Documentation tests | `node --test tests/docs-contract.test.mjs` | PASS |
| Public-audit tests | `node --test tests/public-audit.test.mjs` | PASS |
| CI contract | `node --test tests/ci-contract.test.mjs` | PASS |
| Integrated local pack | `npm run verify:pack` | Included inventory matches all surfaces |
| Upstream provenance | `npm run verify:upstream` | Every included third-party entry verified |
| Public release surface | `npm run audit:public` | Zero findings |
| Codex native validation | plugin creator validator | Exit 0 |
| Claude native validation | `claude plugin validate .` | Exit 0 |
| Native discovery | isolated Codex + Claude smoke tests | Same included set |
