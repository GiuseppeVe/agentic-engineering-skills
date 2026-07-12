# Host-Neutral Agent Profiles Pack Implementation Plan

> **For agentic workers:** REQUIRED EXECUTION SKILL: Use implementing-plans with swarm-orchestration to implement this plan end-to-end. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the seven host-neutral agent role contracts required by the workflow without reintroducing an executable harness or claiming native agent registration.

**Architecture:** Seven Markdown profiles live inside the shared plugin payload and use one common result envelope plus role-specific fields. A separate profile manifest records their Cavecrew ancestry and local hashes; documentation maps each role to workflow phases and explains how Codex or Claude Code can instantiate it using native delegation capabilities.

**Tech Stack:** Markdown contracts, JSON provenance manifest, Node.js 22 ESM, built-in `node:test`.

**Execution order:** Run after `2026-07-12-skill-pack-rebuild.md` completes, because this plan consumes its plugin payload, license bundle, test command, README, workflow documentation, and public-audit gate.

---

## Requirements Inventory

### Behavior and constraints

- **REQ-001** [behavior] — Shared plugin payload contains exactly seven profiles named `controller`, `planner`, `implementer`, `reviewer`, `test-runner`, `researcher`, and `cleanup`. _Acceptance:_ `node --test tests/agent-profiles.test.mjs --test-name-pattern="exact profile inventory"` passes. _Satisfied by:_ Task 1, Task 2.
- **REQ-002** [constraint] — Every profile contains `Purpose`, `Input`, `Allowed actions`, `Forbidden actions`, `Structured output`, `Validation`, and `Failure path` sections. _Acceptance:_ profile contract test reports seven valid documents and zero missing sections. _Satisfied by:_ Task 1, Task 2.
- **REQ-003** [constraint] — Profiles are host-neutral and contain no slash commands, host configuration paths, named host tools, `subagent_type`, or assumptions about a specific delegation API. _Acceptance:_ forbidden-primitive table test passes against all seven profile bodies. _Satisfied by:_ Task 1, Task 2.
- **REQ-004** [behavior] — `controller` owns routing, state, budget, retry, escalation, and trace assembly, but cannot implement tasks or approve its own work. _Acceptance:_ controller semantic contract test finds all six owned responsibilities and both forbidden actions. _Satisfied by:_ Task 2.
- **REQ-005** [behavior] — `planner` produces a bounded structured plan with tasks, dependencies, acceptance criteria, and unresolved decisions, without modifying repository files. _Acceptance:_ planner semantic contract test finds all four output fields and repository-write prohibition. _Satisfied by:_ Task 2.
- **REQ-006** [behavior] — `implementer` owns one assigned task, follows test-first discipline, records changed files and test evidence, and cannot self-approve. _Acceptance:_ implementer semantic contract test finds task boundary, red-green evidence, changed-files output, and self-approval prohibition. _Satisfied by:_ Task 2.
- **REQ-007** [behavior] — `reviewer` evaluates exactly four selectable lenses—`spec`, `quality`, `security`, and `fidelity`—and emits evidence-backed findings without modifying implementation files. _Acceptance:_ reviewer semantic contract test compares the lens set exactly and finds review-only restrictions. _Satisfied by:_ Task 2.
- **REQ-008** [behavior] — `test-runner` executes only named verification commands, records command/exit-code/output evidence, and reports failures without implementing fixes. _Acceptance:_ test-runner semantic contract test finds named-command input, result triplet, and no-fix rule. _Satisfied by:_ Task 2.
- **REQ-009** [behavior] — `researcher` gathers codebase evidence, verifies maintenance findings, distinguishes observation from inference, and does not mutate the repository. _Acceptance:_ researcher semantic contract test finds evidence, inference labels, finding verification, and read-only rule. _Satisfied by:_ Task 2.
- **REQ-010** [behavior] — `cleanup` removes only explicitly scoped temporary artifacts after resolving and validating target paths, then reports deleted and retained paths. _Acceptance:_ cleanup semantic contract test finds scope input, resolved-path validation, broad-delete prohibition, and deleted/retained outputs. _Satisfied by:_ Task 2.
- **REQ-011** [constraint] — All profiles return a common envelope with `role`, `status`, `summary`, `evidence`, `risks`, and `nextAction`; status is one of `completed`, `blocked`, or `failed`. _Acceptance:_ structured-output test parses every documented schema and compares common keys and status enum. _Satisfied by:_ Task 2.
- **REQ-012** [constraint] — Profiles are documented as role contracts consumed by workflow skills, not as an executable harness or guaranteed automatic native-agent registration. _Acceptance:_ documentation test finds the explicit boundary and repository contract still passes the no-harness gate. _Satisfied by:_ Task 3, Task 4.
- **REQ-013** [constraint] — Profile content is recovered from the seven quarantined profile candidates and validated against the original source specification; no additional role is invented. _Acceptance:_ provenance manifest has seven entries, each naming its quarantined candidate and source-spec role line. _Satisfied by:_ Task 2, Task 3.
- **REQ-014** [constraint] — Every profile records adapted Cavecrew ancestry, pinned revision `0d95a81d35a9f2d123a5e9430d1cfc43d55f1bb0`, local SHA-256, and retained MIT license reference. _Acceptance:_ profile provenance test joins seven manifest entries to the Cavecrew notice and verifies local hashes. _Satisfied by:_ Task 2, Task 3.
- **REQ-015** [behavior] — Documentation maps workflow phases and relevant skills to one or more profile names and explains native instantiation for Codex and Claude Code without embedding host-specific commands inside profile files. _Acceptance:_ mapping test finds every profile at least once and exactly two verified host guidance sections. _Satisfied by:_ Task 3.
- **REQ-016** [constraint] — README links to profile documentation and the installed plugin payload contains profile files plus their manifest. _Acceptance:_ link test resolves README link and pack test resolves all seven manifest paths inside the payload. _Satisfied by:_ Task 3.

### Tests

- **REQ-017** [test] — `tests/agent-profiles.test.mjs` covers inventory, required sections, forbidden primitives, common envelope, all seven semantic contracts, provenance, and documentation mapping. _Acceptance:_ test output contains at least 13 passing named cases. _Satisfied by:_ Task 1, Task 2, Task 3.
- **REQ-018** [test] — Existing pack, documentation, license, repository, and public-audit gates remain green after profiles are added. _Acceptance:_ complete command matrix in Task 4 exits 0. _Satisfied by:_ Task 4.

### Cross-task contracts

- **REQ-019** [contract] — `manifests/agent-profiles.json`, plugin profile files, and `docs/agent-profiles.md` expose the same seven names. _Acceptance:_ integration test compares sorted sets from all three sources. _Satisfied by:_ Task 2, Task 3.
- **REQ-020** [contract] — Profile manifest license reference resolves to the Cavecrew MIT file already shipped by the main skill-pack plan and to its row in `THIRD_PARTY_NOTICES.md`. _Acceptance:_ provenance integration test resolves both paths and matches revision. _Satisfied by:_ Task 2, Task 3.
- **REQ-021** [contract] — Workflow documentation uses profile names exactly as declared in `manifests/agent-profiles.json`; aliases such as `builder`, `tester`, or `orchestrator` are not introduced as additional profiles. _Acceptance:_ mapping test rejects undeclared role identifiers. _Satisfied by:_ Task 3.

## File Structure

- `plugins/agentic-engineering-skills/agent-profiles/controller.md` — routing and orchestration contract.
- `plugins/agentic-engineering-skills/agent-profiles/planner.md` — bounded planning contract.
- `plugins/agentic-engineering-skills/agent-profiles/implementer.md` — single-task test-first implementation contract.
- `plugins/agentic-engineering-skills/agent-profiles/reviewer.md` — four-lens evidence review contract.
- `plugins/agentic-engineering-skills/agent-profiles/test-runner.md` — named-command verification contract.
- `plugins/agentic-engineering-skills/agent-profiles/researcher.md` — read-only evidence gathering contract.
- `plugins/agentic-engineering-skills/agent-profiles/cleanup.md` — explicitly scoped artifact cleanup contract.
- `manifests/agent-profiles.json` — seven-profile inventory, ancestry, hash, license, and payload paths.
- `tests/agent-profiles.test.mjs` — structural, semantic, provenance, and integration contracts.
- `docs/agent-profiles.md` — role table, workflow mapping, host adaptation, and boundary.
- `README.md` — link to agent profile guide.
- `docs/workflow.md` — phase-to-profile wiring.
- `docs/provenance.md` — human-readable Cavecrew adaptation record.
- `THIRD_PARTY_NOTICES.md` — profile attribution under existing Cavecrew notice.
- `docs/release-report.md` — profile verification evidence.

## Authoritative Role Inventory

| Profile | Responsibility | Role-specific structured output |
| --- | --- | --- |
| `controller` | Route work; own state, budget, retry, escalation, and trace assembly. | `route`, `budget`, `attempt`, `trace` |
| `planner` | Produce a bounded structured plan. | `tasks`, `dependencies`, `acceptanceCriteria`, `unresolvedDecisions` |
| `implementer` | Apply one owned task with test-first discipline. | `taskId`, `changedFiles`, `redEvidence`, `greenEvidence` |
| `reviewer` | Review with one or more of `spec`, `quality`, `security`, `fidelity`. | `lenses`, `verdict`, `findings` |
| `test-runner` | Execute and interpret named verification commands. | `commands`, `results`, `failedCommands` |
| `researcher` | Gather codebase evidence and verify maintenance findings. | `observations`, `inferences`, `verifiedFindings` |
| `cleanup` | Remove explicitly scoped temporary artifacts only. | `resolvedScope`, `deletedPaths`, `retainedPaths` |

All profiles share this output envelope:

```json
{
  "role": "controller",
  "status": "completed",
  "summary": "Routing decision recorded.",
  "evidence": [],
  "risks": [],
  "nextAction": "Dispatch the selected role."
}
```

The example demonstrates envelope shape only. Each profile documents its own role value and required role-specific fields.

## Tasks

### Task 1: Define profile contract tests

**Satisfies:** REQ-001, REQ-002, REQ-003, REQ-017

**Files:**
- Create: `tests/agent-profiles.test.mjs`

- [ ] **Step 1: Write failing inventory and structure tests**

```js
const expectedProfiles = [
  "cleanup", "controller", "implementer", "planner",
  "researcher", "reviewer", "test-runner"
];
const requiredSections = [
  "Purpose", "Input", "Allowed actions", "Forbidden actions",
  "Structured output", "Validation", "Failure path"
];
```

Test exact inventory, section presence, forbidden primitives, common envelope, and one named semantic case per role.

- [ ] **Step 2: Verify red**

Run: `node --test tests/agent-profiles.test.mjs`

Expected: FAIL with missing `manifests/agent-profiles.json`.

- [ ] **Step 3: Commit red contract**

```bash
git add tests/agent-profiles.test.mjs
git commit -m "test: define agent profile contracts"
```

### Task 2: Recover and complete seven profile contracts

**Satisfies:** REQ-001, REQ-002, REQ-003, REQ-004, REQ-005, REQ-006, REQ-007, REQ-008, REQ-009, REQ-010, REQ-011, REQ-013, REQ-014, REQ-017, REQ-019, REQ-020

**Files:**
- Create: `plugins/agentic-engineering-skills/agent-profiles/{controller,planner,implementer,reviewer,test-runner,researcher,cleanup}.md`
- Create: `manifests/agent-profiles.json`

- [ ] **Step 1: Copy the quarantined candidates**

Source directory:

```text
${AGENT_PROFILE_SOURCE_ROOT}
```

Copy exactly the seven approved files into the shared plugin payload. Stop if candidate inventory differs from the authoritative list.

- [ ] **Step 2: Apply the common contract**

For every profile, preserve its role responsibility and add the seven required sections plus common envelope fields. Use capability descriptions such as “read repository files” or “delegate a bounded task”; do not name host tools or commands.

- [ ] **Step 3: Encode role-specific contracts**

Use the Authoritative Role Inventory verbatim. Add each role's allowed actions, prohibited boundary, role-specific output fields, objective validation rules, and failure behavior. `reviewer` remains one role with four lenses; do not create four reviewer variants.

- [ ] **Step 4: Write provenance manifest**

Create seven entries with `status: "adapted"`, Cavecrew source URL, pinned revision, upstream Cavecrew skill path, quarantined candidate path, payload path, local SHA-256, `license: "MIT"`, and Cavecrew notice path.

- [ ] **Step 5: Verify green and commit**

Run: `node --test tests/agent-profiles.test.mjs`

Expected: inventory, structure, semantic, host-neutrality, envelope, and provenance cases PASS; documentation cases remain skipped until Task 3 files exist.

```bash
git add plugins/agentic-engineering-skills/agent-profiles manifests/agent-profiles.json
git commit -m "feat: add host-neutral agent profiles"
```

### Task 3: Wire profiles into workflow documentation

**Satisfies:** REQ-012, REQ-013, REQ-014, REQ-015, REQ-016, REQ-017, REQ-019, REQ-020, REQ-021

**Files:**
- Create: `docs/agent-profiles.md`
- Modify: `README.md`
- Modify: `docs/workflow.md`
- Modify: `docs/provenance.md`
- Modify: `THIRD_PARTY_NOTICES.md`

- [ ] **Step 1: Enable failing documentation cases**

Remove Task 2's documentation skips. Require same seven-name set across manifest, payload, role guide, and workflow map; reject undeclared aliases.

- [ ] **Step 2: Verify red**

Run: `node --test tests/agent-profiles.test.mjs --test-name-pattern="documentation|workflow mapping"`

Expected: FAIL with missing `docs/agent-profiles.md`.

- [ ] **Step 3: Write role and host-adaptation guide**

Document the authoritative table, common envelope, each role boundary, and phase mapping. Explain that Codex and Claude Code instantiate these contracts through their own delegation capabilities; profile files do not guarantee automatic native registration and contain no host-specific commands.

- [ ] **Step 4: Add discoverability and provenance**

Link guide from README, map workflow phases in `docs/workflow.md`, add Cavecrew adaptation record to `docs/provenance.md`, and extend existing Cavecrew row in `THIRD_PARTY_NOTICES.md` to cover all seven profiles.

- [ ] **Step 5: Verify and commit**

Run: `node --test tests/agent-profiles.test.mjs tests/docs-contract.test.mjs tests/license.test.mjs`

Expected: PASS with seven profiles mapped and Cavecrew license join intact.

```bash
git add README.md docs THIRD_PARTY_NOTICES.md tests/agent-profiles.test.mjs
git commit -m "docs: map workflow agent roles"
```

### Task 4: Run integrated profile finish gate

**Satisfies:** REQ-012, REQ-018

**Files:**
- Modify: `docs/release-report.md`

- [ ] **Step 1: Run focused profile gate**

Run:

```bash
node --test tests/agent-profiles.test.mjs
npm run verify:pack
npm run audit:public
```

Expected: all commands exit 0 and profile suite reports at least 13 passing cases.

- [ ] **Step 2: Run regression suite**

Run:

```bash
npm test
npm run verify:upstream
```

Expected: all existing pack, provenance, license, documentation, repository, CI, and public-audit tests remain green.

- [ ] **Step 3: Record evidence and commit**

Add seven-profile inventory, hashes, Cavecrew revision, focused commands, exit codes, and explicit no-harness/native-registration boundary to `docs/release-report.md`.

```bash
git add docs/release-report.md
git commit -m "docs: record agent profile verification"
```

- [ ] **Step 4: Stop before publication**

Present profile diff and evidence. Push, PR, merge, branch cleanup, and visibility remain governed by the main plan's explicit approval gate.

## Verification Matrix

| Gate | Command | Required result |
| --- | --- | --- |
| Profile contracts | `node --test tests/agent-profiles.test.mjs` | At least 13 PASS, zero FAIL |
| Pack integration | `npm run verify:pack` | Profile paths and skill inventory valid |
| Documentation | `node --test tests/docs-contract.test.mjs` | Links and mappings PASS |
| Licensing | `node --test tests/license.test.mjs` | Cavecrew notice joins PASS |
| Public surface | `npm run audit:public` | Zero findings |
| Full regression | `npm test && npm run verify:upstream` | All commands exit 0 |
