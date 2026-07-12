# Agentic Harness Workflow Implementation Plan

> **For agentic workers:** REQUIRED EXECUTION SKILL: Use `implementing-plans` with `swarm-orchestration` to implement this plan end-to-end. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a public, strict-TypeScript, locally runnable agent-harness reference with deterministic mock agents, evals, workflow artifacts, and advanced-tooling documentation.

**Architecture:** A dependency-light Node CLI runs a typed pipeline: classify a task, route it to a named specialist, construct a bounded context envelope, validate structured output, retry once when recoverable, otherwise escalate, and emit an observable trace. Workflow skills and agent profiles live alongside the executable demo as provenance-aware documentation assets; they do not require a provider key.

**Tech Stack:** Node.js 20+, TypeScript strict, Vitest, ESLint, Knip, GitHub Actions, Markdown/MDX.

---

## Requirements Inventory

### Behavior & constraints

- **REQ-001** [behavior] — CLI classifies a supplied task into a supported task kind and prints the classification. _Acceptance:_ `npm run demo -- --task "Create a strength-training week for an intermediate athlete"` prints `classification`. _Satisfied by:_ Task 5.
- **REQ-002** [behavior] — Router selects a named specialized agent with a machine-readable reason. _Acceptance:_ router unit tests assert expected agent id and reason for planner, reviewer, and unsupported tasks. _Satisfied by:_ Task 3.
- **REQ-003** [behavior] — Every dispatched agent receives only objective, constraints, evidence, state, and budget through a bounded context envelope. _Acceptance:_ runner test asserts the recorded context has exactly these top-level sections and omits arbitrary task history. _Satisfied by:_ Task 2, Task 4.
- **REQ-004** [behavior] — Planner and reviewer outputs are structured data and must be validated before downstream use. _Acceptance:_ validator tests accept valid planner/reviewer output and reject malformed output with a reason. _Satisfied by:_ Task 2.
- **REQ-005** [behavior] — Recoverable invalid output retries at most once; terminal invalid output escalates with an explanatory trace event. _Acceptance:_ runner test asserts two attempts maximum and final `escalated` status. _Satisfied by:_ Task 4.
- **REQ-006** [behavior] — Final trace records task id, classification, routing decision, agent id, validation events, final outcome, and reason. _Acceptance:_ CLI integration test asserts all required trace labels appear. _Satisfied by:_ Task 4, Task 5.
- **REQ-007** [constraint] — Default demo, tests, build, and evals run without API keys, network calls, user data, or provider SDKs. _Acceptance:_ repository-wide search finds no provider key values or provider SDK dependency; `npm test`, `npm run build`, and demo pass with no `.env`. _Satisfied by:_ Task 1, Task 4, Task 9.
- **REQ-008** [constraint] — TypeScript compilation runs with `strict: true`. _Acceptance:_ `npm run build` succeeds with `tsconfig.json` `strict` set to `true`. _Satisfied by:_ Task 1.
- **REQ-009** [behavior] — At least three deterministic golden cases cover planner success, reviewer success, and escalation. _Acceptance:_ `npm run evals` reports three passing named cases. _Satisfied by:_ Task 5.
- **REQ-010** [behavior] — Knip is installed as a development dependency and its scan is exposed through an npm script without automatic deletions. _Acceptance:_ `package.json` contains `knip` in `devDependencies`, `maintenance:scan`, and docs state findings need human review. _Satisfied by:_ Task 1, Task 8.
- **REQ-011** [behavior] — Repository includes seven host-neutral agent profiles: controller, planner, implementer, reviewer, test-runner, researcher, cleanup. _Acceptance:_ `agent-profiles/` contains seven profile documents with input, allowed actions, output, validation, and failure sections. _Satisfied by:_ Task 7.
- **REQ-012** [behavior] — Repository includes the agreed design and maintenance workflow skill map, including direct dependencies such as grilling, domain modeling, codebase design, TDD, worktrees, swarm orchestration, and Knip. _Acceptance:_ `skills/sources.lock.json` lists each skill, source, pin, license, dependency relation, and packaging status. _Satisfied by:_ Task 7.
- **REQ-013** [constraint] — Third-party material has source, immutable pin, license, and modification status recorded; unknown-license material is not copied. _Acceptance:_ `THIRD_PARTY_NOTICES.md` and `skills/sources.lock.json` pass a provenance test that requires populated source, pin, license, and status fields. _Satisfied by:_ Task 7.
- **REQ-014** [constraint] — Advanced tooling is documented as an opt-in upgrade, never as a hidden core requirement. _Acceptance:_ README and `docs/advanced-tooling.md` distinguish core commands from swarm, Git worktree, `gh`, browser, Graphviz, and Knip integrations. _Satisfied by:_ Task 8, Task 9.
- **REQ-015** [constraint] — Public artifacts contain no secrets, private URLs, personal data, source-project names, copied proprietary code, internal prompts, or logs. _Acceptance:_ `npm run audit:public` exits 0 against repository content. _Satisfied by:_ Task 8, Task 10.

### Tests

- **REQ-016** [test] — Unit tests cover router, validator, and runner retry/escalation behavior. _Acceptance:_ `npm test` passes the three test files. _Satisfied by:_ Task 6.
- **REQ-017** [test] — CI installs dependencies, runs lint, tests, build, evals, and public audit on Node 20. _Acceptance:_ workflow syntax is valid and commands match `package.json` scripts. _Satisfied by:_ Task 10.

### Cross-task contracts

- **REQ-018** [contract] — Router output `agentId` selects the corresponding deterministic agent in the runner registry. _Acceptance:_ runner integration test routes `plan` task to `planner-agent` and receives planner schema output. _Satisfied by:_ Task 3 + Task 4 + Task 6.
- **REQ-019** [contract] — Runner sends validator result to observability so every dispatch attempt has an associated validation event. _Acceptance:_ runner test asserts trace validation event count equals attempt count. _Satisfied by:_ Task 2 + Task 4 + Task 6.
- **REQ-020** [contract] — Golden cases use the same public `runHarness` API as CLI rather than duplicate routing/validation logic. _Acceptance:_ eval implementation imports `runHarness`; eval test proves all cases run through it. _Satisfied by:_ Task 4 + Task 5 + Task 6.

## File Structure

| Path | Responsibility |
| --- | --- |
| `package.json` | Commands and minimal dev dependencies. |
| `tsconfig.json`, `eslint.config.mjs` | Strict compilation and lint rules. |
| `src/types.ts` | Shared task, context, output, trace, and result contracts. |
| `src/harness/context.ts` | Builds the bounded context envelope. |
| `src/harness/router.ts` | Classifies tasks and selects agents. |
| `src/harness/validator.ts` | Handwritten runtime guards for structured outputs. |
| `src/harness/observability.ts` | Creates deterministic trace events. |
| `src/harness/runner.ts` | Coordinates route, agent call, validation, retry, escalation. |
| `src/agents/mock-agent.ts` | Deterministic agent registry and fault-injection support. |
| `src/agents/planner-agent.ts`, `src/agents/reviewer-agent.ts` | Named structured-output specialists. |
| `src/evals/golden-cases.ts`, `src/evals/run-evals.ts` | Deterministic evaluation data and CLI runner. |
| `src/cli.ts` | Demo command entrypoint. |
| `tests/*.test.ts` | Router, validator, runner, and eval tests. |
| `agent-profiles/*.md` | Seven host-neutral agent role contracts. |
| `skills/sources.lock.json`, `skills/README.md` | Skill dependency map and provenance manifest. |
| `scripts/audit-public.mjs`, `scripts/verify-skill-sources.mjs` | Secret/proprietary-marker scan and lockfile validation. |
| `knip.json`, `docs/advanced-tooling.md` | Knip configuration and advanced integrations guide. |
| `README.md`, `docs/architecture.md`, `docs/workflow-diagram.md` | Public explanation and diagrams. |
| `.github/workflows/ci.yml` | Node 20 verification workflow. |

## Implementation Tasks

### Task 1: Initialize strict TypeScript tooling and deterministic commands

**Satisfies:** REQ-007, REQ-008, REQ-010

**Files:**
- Create: `package.json`
- Create: `tsconfig.json`
- Create: `eslint.config.mjs`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `knip.json`
- Create: `tests/tooling-contract.test.ts`

- [ ] **Step 1: Add the failing package scripts contract test**

Create `tests/tooling-contract.test.ts` with assertions that `package.json` exposes `demo`, `test`, `build`, `lint`, `evals`, `maintenance:scan`, and `audit:public`.

- [ ] **Step 2: Run the test to verify failure**

Run: `npm test -- --run tests/tooling-contract.test.ts`

Expected: FAIL because `package.json` does not exist.

- [ ] **Step 3: Add package and configuration**

Use Node 20 with `type: "module"`; add scripts `build: tsc -p tsconfig.json`, `test: vitest run`, `lint: eslint .`, `evals: tsx src/evals/run-evals.ts`, `demo: tsx src/cli.ts`, `maintenance:scan: knip`, and `audit:public: node scripts/audit-public.mjs`. Add only `typescript`, `tsx`, `vitest`, `eslint`, `@eslint/js`, `typescript-eslint`, and `knip` as dev dependencies.

Configure `strict: true`, `noUncheckedIndexedAccess: true`, `rootDir: src`, `outDir: dist`, and NodeNext module resolution. Ignore `node_modules`, `dist`, `.env`, `.env.*` except `.env.example`, coverage, and editor artifacts. Keep `.env.example` comment-only.

- [ ] **Step 4: Add a focused Knip configuration**

Configure entry files `src/cli.ts` and `src/evals/run-evals.ts`; ignore test and documentation patterns only when Knip cannot infer them. Do not add broad source ignores.

- [ ] **Step 5: Verify tooling contract**

Run: `npm install && npm test -- --run tests/tooling-contract.test.ts && npm run build && npm run lint`

Expected: all commands pass.

### Task 2: Define shared contracts, context envelope, validator, and trace events

**Satisfies:** REQ-003, REQ-004, REQ-019

**Files:**
- Create: `src/types.ts`
- Create: `src/harness/context.ts`
- Create: `src/harness/validator.ts`
- Create: `src/harness/observability.ts`
- Test: `tests/validator.test.ts`

- [ ] **Step 1: Write validator tests first**

Test that a planner output with `kind: "plan"`, a non-empty `summary`, and at least one action validates; test that missing actions and an unknown output kind return `{ ok: false, reason }`.

- [ ] **Step 2: Verify tests fail**

Run: `npm test -- --run tests/validator.test.ts`

Expected: FAIL because validator module is missing.

- [ ] **Step 3: Implement contracts and pure helpers**

Define discriminated unions for `TaskKind`, `AgentId`, `AgentOutput`, `ValidationResult`, `TraceEvent`, and `HarnessResult`. Make `ContextEnvelope` exactly `{ objective, constraints, evidence, state, budget }`. Implement pure `createContextEnvelope`, `validateAgentOutput`, and `createTraceEvent` functions with no environment reads.

- [ ] **Step 4: Verify validator behavior**

Run: `npm test -- --run tests/validator.test.ts && npm run build`

Expected: PASS and strict compilation succeeds.

### Task 3: Implement task classification and explicit routing

**Satisfies:** REQ-002, REQ-018

**Files:**
- Create: `src/harness/router.ts`
- Test: `tests/router.test.ts`

- [ ] **Step 1: Write routing cases**

Add tests mapping task text containing planning verbs to `{ kind: "plan", agentId: "planner-agent" }`, review verbs to `{ kind: "review", agentId: "reviewer-agent" }`, and unknown text to `{ kind: "unsupported", agentId: "mock-agent" }`. Each assertion includes a non-empty `reason`.

- [ ] **Step 2: Verify tests fail**

Run: `npm test -- --run tests/router.test.ts`

Expected: FAIL because router module is missing.

- [ ] **Step 3: Implement deterministic keyword routing**

Classify only the documented supported kinds. Lowercase normalized task text, use transparent keyword sets, and return an explicit fallback route instead of inferring hidden intent.

- [ ] **Step 4: Verify routes**

Run: `npm test -- --run tests/router.test.ts`

Expected: PASS with planner, reviewer, and unsupported cases.

### Task 4: Implement deterministic agents and harness runner

**Satisfies:** REQ-003, REQ-005, REQ-006, REQ-007, REQ-018, REQ-019, REQ-020

**Files:**
- Create: `src/agents/planner-agent.ts`
- Create: `src/agents/reviewer-agent.ts`
- Create: `src/agents/mock-agent.ts`
- Create: `src/harness/runner.ts`
- Test: `tests/runner.test.ts`

- [ ] **Step 1: Write retry and escalation tests**

Inject an agent that returns malformed output twice. Assert two calls, final status `escalated`, and two validation trace events. Add a planner task assertion that route agent id selects `planner-agent` and output validates.

- [ ] **Step 2: Verify tests fail**

Run: `npm test -- --run tests/runner.test.ts`

Expected: FAIL because runner and agent modules are missing.

- [ ] **Step 3: Implement named deterministic agents**

Planner returns a bounded plan summary and two generic actions. Reviewer returns a pass/fail review with evidence references. Mock agent returns an unsupported-task result and supports an injected invalid-output sequence for tests.

- [ ] **Step 4: Implement `runHarness`**

`runHarness(task, options)` must create task id, route task, construct envelope, record trace events, invoke registry agent, validate result, retry one recoverable invalid result, and return escalation after second invalid result. Keep provider adapters out of this path.

- [ ] **Step 5: Verify runner behavior**

Run: `npm test -- --run tests/runner.test.ts && npm run build`

Expected: PASS and no API key is requested.

### Task 5: Add CLI demo and golden-case evaluation

**Satisfies:** REQ-001, REQ-006, REQ-009, REQ-020

**Files:**
- Create: `src/cli.ts`
- Create: `src/evals/golden-cases.ts`
- Create: `src/evals/run-evals.ts`
- Test: `tests/evals.test.ts`

- [ ] **Step 1: Write eval tests**

Define named cases `planner-success`, `reviewer-success`, and `invalid-output-escalates`. Assert each uses `runHarness` and expected final status/agent id.

- [ ] **Step 2: Verify tests fail**

Run: `npm test -- --run tests/evals.test.ts`

Expected: FAIL because eval modules are missing.

- [ ] **Step 3: Implement JSON-safe CLI output**

Parse `--task <text>`, reject a missing task with exit code 1, call `runHarness`, and print labeled sections `classification`, `route`, `context`, `output`, `validation`, and `final trace`.

- [ ] **Step 4: Implement deterministic eval runner**

Run all golden cases serially, print one pass/fail line per case, and set non-zero exit code on any mismatch.

- [ ] **Step 5: Verify demo and evals**

Run: `npm run demo -- --task "Create a strength-training week for an intermediate athlete" && npm run evals`

Expected: six labeled demo sections and three passing golden cases.

### Task 6: Complete behavior-focused tests and coverage of public contracts

**Satisfies:** REQ-016, REQ-018, REQ-019, REQ-020

**Files:**
- Modify: `tests/router.test.ts`
- Modify: `tests/validator.test.ts`
- Modify: `tests/runner.test.ts`
- Modify: `tests/evals.test.ts`

- [ ] **Step 1: Add bounded-context assertion**

Assert runner trace contains one context event whose object keys are exactly `objective`, `constraints`, `evidence`, `state`, and `budget`.

- [ ] **Step 2: Add trace contract assertions**

Assert success and escalation results both expose task id, classification, route reason, agent id, validation events, final outcome, and final reason.

- [ ] **Step 3: Run all tests**

Run: `npm test`

Expected: all router, validator, runner, eval, and tooling tests pass.

### Task 7: Add agent profiles, skill manifest, and provenance artifacts

**Satisfies:** REQ-011, REQ-012, REQ-013

**Files:**
- Create: `agent-profiles/{controller,planner,implementer,reviewer,test-runner,researcher,cleanup}.md`
- Create: `skills/README.md`
- Create: `skills/sources.lock.json`
- Create: `THIRD_PARTY_NOTICES.md`
- Create: `licenses/Apache-2.0.txt`
- Create: `licenses/claude-mem-NOTICE.txt`
- Create: `scripts/verify-skill-sources.mjs`
- Test: `tests/skill-sources.test.ts`

- [ ] **Step 1: Write provenance validation test**

Load `skills/sources.lock.json`. Assert every entry has non-empty `name`, `source`, `revision`, `license`, `status`, and `dependencies`; reject `license: "unknown"` when `status` is `vendored` or `adapted`.

- [ ] **Step 2: Verify test fails**

Run: `npm test -- --run tests/skill-sources.test.ts`

Expected: FAIL because manifest is missing.

- [ ] **Step 3: Create host-neutral profiles**

Each profile must contain sections `Input`, `Allowed actions`, `Structured output`, `Validation`, and `Failure path`. Reviewer documents four lenses rather than creating duplicate roles.

- [ ] **Step 4: Create source manifest and notices**

Record source-pinned MIT entries for Matt Pocock workflow skills, Superpowers workflow skills, Caveman profiles, and Ruflo swarm orchestration. Record Apache-2.0 `learn-codebase` with upstream notice. Mark original sanitized skills `implementing-plans` and `cleaning-repo-with-knip` as `original`; do not copy the unlicensed architecture variant. Keep only source manifests and original/adapted public material in the first skeleton; fetch verbatim upstream files only from revisions verified during implementation.

- [ ] **Step 5: Verify provenance**

Run: `npm test -- --run tests/skill-sources.test.ts && node scripts/verify-skill-sources.mjs`

Expected: all entries complete and no unknown license is vendored.

### Task 8: Add public audit, Knip maintenance tooling, and advanced-tooling guide

**Satisfies:** REQ-010, REQ-014, REQ-015

**Files:**
- Create: `scripts/audit-public.mjs`
- Create: `docs/advanced-tooling.md`
- Create: `.vscode/settings.json`
- Modify: `package.json`
- Test: `tests/public-audit.test.ts`

- [ ] **Step 1: Write public audit tests**

Create a temporary fixture with a forbidden marker and assert audit exits non-zero; create a clean fixture and assert exit zero.

- [ ] **Step 2: Verify tests fail**

Run: `npm test -- --run tests/public-audit.test.ts`

Expected: FAIL because audit script is missing.

- [ ] **Step 3: Implement narrow public-content audit**

Scan tracked text files while excluding `.git`, `node_modules`, and `dist`. Detect generic secret prefixes, private URL patterns, source-project identifiers supplied as a local denylist, and known transcript/log extensions. Print filename and rule only; never print secret values.

- [ ] **Step 4: Document advanced tooling**

Explain swarm orchestration, Git worktrees, `gh`, browser capability, Graphviz, and Knip. For each, specify prerequisite, workflow stage, upgrade gained, and honest behavior when unavailable. Add `.vscode/settings.json` associating `*.mdx` with Markdown and enabling preview-friendly settings.

- [ ] **Step 5: Verify maintenance and audit tooling**

Run: `npm test -- --run tests/public-audit.test.ts && npm run audit:public && npm run maintenance:scan`

Expected: audit passes and Knip reports findings without modifying files.

### Task 9: Write public README and architecture/workflow documentation

**Satisfies:** REQ-007, REQ-014

**Files:**
- Create: `README.md`
- Create: `docs/architecture.md`
- Create: `docs/workflow-diagram.md`
- Create: `LICENSE`
- Create: `tests/readme-contract.test.ts`

- [ ] **Step 1: Draft README acceptance test**

Add a text test asserting README includes problem statement, Mermaid/ASCII architecture, quick start of fewer than five commands, demo output, router/context/validator/golden-case explanations, design decisions, limits, security/privacy, advanced tooling, and roadmap.

- [ ] **Step 2: Verify test fails**

Run: `npm test -- --run tests/readme-contract.test.ts`

Expected: FAIL because README is missing.

- [ ] **Step 3: Write docs and MIT license**

README must remain technical and plain-spoken. Explain default deterministic core separately from advanced integrations. Architecture docs describe contracts and escalation. Workflow docs visualize design and maintenance flows. Root MIT license applies to original material only; third-party notices control external material.

- [ ] **Step 4: Verify documentation contract**

Run: `npm test -- --run tests/readme-contract.test.ts && npm run audit:public`

Expected: PASS.

### Task 10: Add CI and execute final public verification

**Satisfies:** REQ-007, REQ-015, REQ-017

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `package.json`
- Modify: `docs/advanced-tooling.md`

- [ ] **Step 1: Add CI workflow**

Use `actions/checkout@v4` and `actions/setup-node@v4` with Node 20 and npm cache. Run `npm ci`, `npm run lint`, `npm test`, `npm run build`, `npm run evals`, and `npm run audit:public`.

- [ ] **Step 2: Verify CI command parity**

Add a test that reads CI YAML and asserts each required local command appears exactly once in job steps.

- [ ] **Step 3: Run final verification suite**

Run: `npm run lint && npm test && npm run build && npm run evals && npm run audit:public && npm run demo -- --task "Create a strength-training week for an intermediate athlete" && npm run maintenance:scan`

Expected: all commands exit 0; demo prints classification, route, bounded context, structured output, validation, and final trace.

- [ ] **Step 4: Inspect final public surface**

Run: `git status --short && rg -n -i 'TODO|TBD|source-project-name|private-user-images|sk-[A-Za-z0-9_-]+' . -g '!node_modules' -g '!.git'`

Expected: only intentional worktree changes, no placeholders, secrets, private URLs, or prohibited source-project markers.

## Plan Self-Review

- Spec coverage: REQ-001 through REQ-017 map all approved core, workflow, advanced-tooling, public-safety, and verification obligations.
- Cross-task wiring: REQ-018 through REQ-020 map route-to-agent, validation-to-trace, and eval-to-runner seams.
- Traceability: every task lists at least one requirement and every requirement identifies owning tasks.
- No implementation code has been written by this plan; source paths are exact and every test command has an expected result.
