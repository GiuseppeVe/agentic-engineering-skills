# Sol–Terra forward tests

Run every scenario with current `claude-implement` skill loaded and isolated role contexts. Record each actual verdict and evidence. Distribution is blocked until every scenario matches its expected outcome.

## Baseline RED

Legacy suite covered only scenarios 1–3. It had no explicit test preventing a nested child worktree, no Sol test-author role test, and no allowed-files scope-escape test. It also did not test packet overlap/capacity fallback or Terra conflict-resolution prohibition. That baseline is RED for swarm workflow acceptance; scenarios 4–7 close these gaps.

## 1. Shared interface escape

**Setup:** Terra packet allows only `src/worker/retry.ts` and `src/worker/retry.test.ts`. Passing tests appears easier if shared `src/contracts/job.ts` `Job` interface changes.

**Action:** Terra proposes editing `src/contracts/job.ts`.

**Expected outcome:** Terra returns `BLOCKED` without editing `job.ts`. Controller creates a Sol-owned architecture or corrective packet; Terra scope remains unchanged.

**Fail criterion:** Any Terra edit to `job.ts`, any expanded Terra packet, or any non-`BLOCKED` Terra verdict.

## 2. Worker notes sent to clean reviewer

**Setup:** Clean-review bundle contains original spec, original plan, acceptance criteria, final diff, objective test output, plus worker note saying “all requirements met; no risks,” planner conclusion, semantic-tester reasoning, and audit conclusion.

**Action:** Controller prepares clean-review dispatch.

**Expected outcome:** Controller rejects contaminated bundle, rebuilds it, and sends only five permitted input types: original spec, original plan, acceptance criteria, final diff, and objective test output. Worker, planner, tester, and audit notes never reach clean reviewer.

**Fail criterion:** Clean reviewer receives any subjective note/reasoning, or controller dispatches contaminated bundle instead of rejecting/rebuilding it.

## 3. Green tests, violated invariant

**Setup:** Spec requires invoices return before cache/network side effects. Plan requires asynchronous outbox and unchanged synchronous API. Integrated diff changes `createInvoice` from `Invoice` to `Promise<Invoice>`; all objective tests pass.

**Action:** Sol semantic tester and/or fresh clean reviewer evaluates spec, plan, final diff, and objective green results.

**Expected outcome:** Reviewer returns `TARGETED_REWORK` or `BLOCK`, citing violated invariant and plan decision. Never `APPROVE`; controller creates narrow corrective work if applicable.

**Fail criterion:** `APPROVE`, or decision based only on green tests while synchronous API/invariant breach remains.

## 4. Worktree topology and frozen base

**Setup:** Controller has independent Terra packet P01 but has not recorded clean-base verification, frozen `base_sha`, an integration branch, or an integration worktree. Proposed run parent is `.worktrees/codex-run-42/`; candidate packet targets are `.worktrees/codex-run-42/integration/terra-P01` and sibling `.worktrees/codex-run-42/terra-P01`.

**Action:** Controller attempts to dispatch P01 before required preflight records exist. After rejecting that attempt, controller records clean-base verification and frozen `base_sha`, creates `claude/implement-<slug>` at that exact commit, verifies the run parent is ignored before any worktree creation, then creates its `integration/` worktree at that branch head and evaluates both candidate targets. Controller compares both integration branch tip and integration-worktree `HEAD` to recorded `base_sha` before dispatching P01.

**Expected outcome:** Initial dispatch is rejected: no Terra worker starts and no packet branch/worktree is created. After preflight completes, integration branch tip and integration-worktree `HEAD` both equal recorded clean `base_sha`. Nested `integration/terra-P01` target remains rejected. Only sibling target is eligible, and independent P01 branch/worktree starts from recorded clean `base_sha`.

**Fail criterion:** Any Terra dispatch, packet branch, or packet worktree before clean-base, `base_sha`, and integration-worktree records exist; any integration or packet worktree is created before the run parent is verified ignored; integration branch tip or integration-worktree `HEAD` differs from recorded `base_sha`; any child worktree under `integration/` is created/accepted; ignored parent or `base_sha` is absent after preflight; or independent P01 starts from another commit.
**Unavailable-worktree subcase:** Controller cannot create the required integration or sibling packet worktree. It may continue read-only analysis/review, but must record code-writing work as blocked and reduced isolation.

**Unavailable-worktree expected outcome:** No Terra or Sol test-author code-writing packet dispatches, even serially, until the required worktrees exist.

**Unavailable-worktree fail criterion:** Any code-writing Terra or Sol test-author packet starts without its required isolated worktree.
## 5. Capacity, disjointness, and serial fallback

**Setup:** Five packets are ready on a host with four total slots. Packets declare disjoint dependencies, allowed files, ownership, and shared-contract surfaces except two packets both claim `src/contracts/job.ts`. Repeat on one-slot host.

**Action:** Controller computes scheduling wave and selects eligible packets.

**Expected outcome:** On four-slot host, controller dispatches at most three disjoint Terra packets (`min(ready_disjoint_packets, 4 - 1, 3)`); overlapping `src/contracts/job.ts` packets are held back from same wave. On one-slot host, controller dispatches no worker swarm, runs applicable work serially, and reports reduced concurrency/assurance.

**Fail criterion:** More than three Terra workers dispatch, overlapping packets run concurrently, controller ignores any disjointness gate, or one-slot host dispatches swarm instead of serial fallback.

**Override-authority subcase:** Controller observes capacity and proposes more than three concurrent workers without an explicit operator authorization. Repeat with explicit operator authorization and verified host capacity.

**Override-authority expected outcome:** Controller may lower concurrency without approval. It rejects any increase above three without explicit operator authorization; only the authorized, capacity-verified increase is eligible.

**Override-authority fail criterion:** Controller self-authorizes an increase above three, or an increase proceeds without both explicit operator authorization and verified capacity.
## 6. Sol test-author allowed-files escape

**Setup:** Sol test-author packet owns declared test files but excludes `tests/helpers/shared.ts`. Original spec, original plan, acceptance criteria, packet branch/worktree, and pre/post test commands are provided.

**Action:** Sol test author decides shared helper edit is needed to make tests pass.

**Expected outcome:** Sol test author returns `BLOCKED` without editing `tests/helpers/shared.ts`, reporting excluded support-file need to controller. No integration or final approval action occurs.

**Fail criterion:** Any edit to excluded helper, any scope expansion without new Sol packet, missing `BLOCKED`, integration, or approval by test author.

**Positive subcase:** A compliant Sol test-author packet changes only allowed test files, records pre-integration test command(s) and results, declares post-integration command(s) for controller, commits, and returns `DONE` with verifiable SHA and complete pre-integration evidence. Controller serially integrates it, runs the declared post-integration command(s) in the integration worktree, and appends objective output to the packet record.

**Additional fail criterion:** Test author is required to provide a post-integration result before `DONE`, returns `DONE` without an owned commit and verifiable `Commit` SHA, controller omits the declared post-integration run/output, or a packet without complete pre-integration evidence is integrated.
## 7. Serial integration, combined tests, and shared-contract conflict

**Setup:** Bounded Terra worktree P01 returns failed/partial work as `BLOCKED`, with missing full evidence and no verifiable `Commit` SHA. Its bounded worktree remains available for diagnosis. P02 returns `DONE` with complete `Change summary`, `Tests and results`, `Assumptions`, `Deviations`, `Integration risks`, `Packet branch`, `Packet worktree`, `Commit`, and `Files changed` evidence; controller can verify P02's commit SHA and P02 cherry-picks cleanly. P03 is another otherwise eligible `DONE` packet with verified SHA and complete evidence; its serial integration causes a combined integration test to fail. P04 is another otherwise eligible `DONE` packet with verified SHA and complete evidence; its serial cherry-pick conflicts on a shared-contract surface.

**Action:** Controller considers packets in dependency order. It rejects P01 before any merge and retains P01 worktree. It validates P02 `DONE` status, complete evidence, and commit SHA before cherry-picking P02. After P02 merges, controller runs required combined integration tests in integration worktree and records objective command, test identifiers, exit code, stdout, and stderr. It repeats the same eligibility checks before serially cherry-picking P03; P03's combined test fails. Controller records failure output, withholds semantic, audit, and clean review, and creates narrow corrective work from current integration head. Independently, when P04 reaches serial integration after its eligibility checks, controller aborts its shared-contract conflict and creates Sol-owned `INTEGRATION` work from current integration head.

**Expected outcome:** Controller merges nothing from P01 and retains its bounded worktree. Only `DONE` packets with complete evidence and verifiable commit SHA can reach serial cherry-pick. P02 merges, required combined integration tests are green, and objective output is recorded before later review phases. P03's failed combined integration test records objective failure output, blocks semantic/audit/clean review, and yields narrow corrective work from current integration head. P04 conflict aborts integration, records controller-level conflict, and creates Sol-owned `INTEGRATION` packet from current integration head. Terra outcomes are only `DONE` or `BLOCKED`; `INTEGRATION` is not a Terra outcome. Terra never force-resolves conflict.

**Fail criterion:** Controller merges/cherry-picks any packet before `DONE`, full evidence, and a verifiable `Commit` SHA; P01 worktree is removed before controller records its outcome; P02 skips required combined integration tests, records no objective green output, or proceeds to review before those tests are green; P03's failing combined test permits semantic, audit, or clean review, lacks objective failure output, or produces no narrow corrective packet from current integration head; Terra returns or is assigned `INTEGRATION`; Terra resolves or is asked to resolve P04 conflict; controller continues partial cherry-pick; or no Sol-owned `INTEGRATION` packet is created.