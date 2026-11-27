# Daily Workflow

Portable process rules for everyday work in repositories that adopt this workflow. No session hook enforces them; repositories keep only automated Git hooks and CI gates.

## Mandate and Git

- Discovery, audit, and planning are read-only.
- Implementation, commit, push, PR, and live operations are separate scopes: act only within the authorized scope. Available tools or credentials do not expand the mandate.
- Exhaust legitimate paths within the mandate before asking the owner. Ask only for product or contract decisions, missing permissions, or credentials.
- Deployments, cloud resources, credentials, and product decisions require explicit owner approval.
- Default path for substantial changes: settled decisions → spec → owner review → plan → scoped implementation → verification and review → authorized integration.
- Edit code, configuration, and tests in a dedicated branch and worktree (`<repo-root>/.worktrees/<name>`); keep the `main` checkout for reading current state. Docs-only edits are exempt.
- Stage only touched paths; never `git add .`. No direct pushes to `main`, force-pushes, or destructive resets.
- Preserve others' work: check status, branch, SHA, and diff before editing or committing. Close worktrees and branches you open when done, or list them in the closing report with path, branch, and state. Inventory all worktrees of a repository with `scripts/worktrees.mjs`; removal covers only merged clean worktrees and requires owner authorization.
- Merging into `main` requires explicit owner authorization for that PR. Merging into non-`main` branches is within agent authority unless restricted by a mandate.

## Verification

Follow the repository's deterministic layers from cheapest to deepest before claiming completion:

1. **L1 — Types, schemas, and structural contracts:** typecheck, schema/codegen drift checks, and boundary contracts. Verify that touched test and helper paths are actually covered by the typecheck config rather than silently excluded.
2. **L2 — Static analysis and dead code:** fast lint on edit, type-aware lint, import/architecture boundaries, and unused-code checks. Do not bypass rules with inline disables or type escapes without a documented reason.
3. **L3 — Behavioral, contract, and real-runtime checks:** unit/behavioral tests, cross-package producer/consumer contract tests, property-based tests for invariants, and real persistence, browser, or asset-decoding checks when the contract is operational. Never replace persistence, browser, or external-service proofs with mocks.

Anti-green-washing rules:

- Claim an action complete only after verifying its result. Report merges with PR number and base branch; report pushes with the SHA present on `origin`.
- Skipped checks, timeouts, partial environments, or excluded paths are **unverified**, never green. Never weaken a gate to pass.
- An isolated rerun of one test never turns a failed suite or job green: rerun the failed gate as a whole on the final state.
- Keep evidence classes distinct: `process` (historical RED observed before the fix) versus `final_state` (re-run after the last relevant edit and bound to the final commit SHA or exact uncommitted diff).
- Keep delivery states distinct: verified locally, pushed to `origin`, integrated in target, verified on running SHA.
- Red gate: reproduce it, fix diff-introduced regressions within scope, and record unrelated issues separately. Classify a failure as **pre-existing** only if reproduced on the base revision in the same environment, and **flaky** only if repeated runs on the same revision disagree.
- **Promote mechanical defects to L2:** when verification or review uncovers a repeatable mechanical error (banned API, missing await, unsafe cast, broken import shape), propose a deterministic lint or static check in the repository instead of adding another line of prose.
- Never include tokens, personal transcripts, or raw noisy tool dumps in messages, evidence, or PR comments.

## PR Phase

Order on every PR (single PR, plan into `pkg/*`, or package into `main`):

1. **Open draft PR** from the working branch. Include in the PR body: `ADR impact: none | NNNN | new`, `Plan: none | <id>` (for PRs targeting `pkg/*`), and `Docs: none | <spec, plan, and ADR paths>`. Reviewers and fixers read document paths from the PR body instead of repeating them in briefs.
2. **Fast local verification:** run the repository's L1/L2 checks and affected L3 tests on the touched files.
3. **Independent review of the full diff** in a fresh read-only context using the host's native code-review capability (started right after push without waiting for approval), in parallel with `simplify` (and `cleaning-repo-with-knip` when warranted) on the diff. One independent review per SHA. Focus review on contracts, states, concurrency, auth/privacy, test-oracle integrity, and L2 gaps — do not duplicate what L1/L2 already enforce. Output P0–P3 findings with `file:line` and failure scenario.
4. **Fixes in one commit.** Evaluate each finding against code, contract, and evidence: confirm and fix if valid, or reject with reasoning. One thread fixes, reruns relevant checks, and makes one push.
5. **Full gates once on the frozen head.** When the PR leaves draft, the plugin hook launches the repository's `gates:pr` script if defined; where the hook does not run, invoke the repository's gate command explicitly. Launching is not an outcome: wait for and react to every final result, including red or timed-out runs. Proof is the commit status on the hosting platform, backed by the result file when produced.
6. **Delta-only review** (in parallel with gates) if step 4 changed code, configuration, or tests.
7. **Mark ready** once review is closed: this triggers step 5's gates. Green gate statuses on the frozen head are the merge condition. A hosted CI check that is red solely due to billing is not a blocker when the repository's fallback gate statuses are green.

Limits:

- After two fix rounds without convergence, stop and deliver `partial` with the open conflicts.
- A non-normative docs-only PR (touching no path read by test suites or CI guards) passes with documentation guards and agent verification: no full suites, no independent review.
- Every new head requires fresh step-5 gates.

## Closing Report

For every substantial session report: context (repository, branch, SHA), modified paths, integration state (local, pushed, integrated) with commit or PR, checks run with command and outcome, checks not run and why, residual risks, and next step. List any left-open worktrees, branches, or temporary files.

## Process Budget

A new process hook or script enters only with the metric it aims to improve and by removing an existing one.
