---
name: claude-implement
description: Use when a substantial implementation plan needs isolated workspaces, bounded parallel workers, or independent semantic approval.
---

# Codex Implement — Sol–Terra Swarm

Use Sol for judgement and Terra for bounded edits. Isolate writers; serialize integration; approve only through a fresh Sol clean review. Green tests alone never prove compliance.

## Model setup

Verify Claude Code model and effort routing before dispatch:

```powershell
claude --model fable --effort xhigh --help
claude --model opus --effort high --help
```

CLI role launch:

```powershell
claude -p --model fable --effort xhigh "<Sol analyst, planner, tester, audit, or reviewer prompt>"
claude -p --model opus --effort high "<one Terra worker packet>"
```

If the host supports per-agent model selection, bind every Sol role to `fable` at `xhigh` and every Terra worker to `opus` at `high`. Otherwise retain separate contexts and report: `Reduced assurance: role isolation verified; Sol/Terra model routing unavailable.` Command parsing never proves actual routing.

## Required inputs

Controller collects original, unabridged specification, implementation plan, acceptance criteria, approval boundaries, and repository context. Missing material that changes architecture or acceptance blocks planning. Missing original spec or plan blocks final approval.

## Run isolation

Before code dispatch, verify a clean base, freeze `base_sha`, then create integration branch `claude/implement-<slug>` and its dedicated `integration/` worktree from exactly that frozen clean `base_sha`. Do not create either from a later integration or packet head. For project-local runs, verify parent is ignored before creating worktrees.

Packet worktrees are siblings of `integration/`, never children. Controller alone writes the integration branch. Independent packet branches start at `base_sha`; dependent and corrective packets start at current integration head after prerequisites integrate. If isolated worktree creation is unavailable, do not dispatch code-writing Terra or Sol test-author packets, even serially. Read-only analysis and review may proceed; record blocked writing work and reduced isolation until required worktrees exist.

## Roles

| Role | Profile | Authority |
|---|---|---|
| Sol invariants analyst | `agents/sol-invariants-analyst.md` | Read-only philosophy, invariants, boundaries. |
| Sol dependency analyst | `agents/sol-dependency-analyst.md` | Read-only DAG and contract risks. |
| Sol test strategist | `agents/sol-test-strategist.md` | Read-only test/evidence design. |
| Sol planner/synthesizer | `agents/sol-planner.md` | Sole authoritative packet decisions. |
| Terra worker | `agents/terra-worker.md` | One bounded implementation packet. |
| Sol test author | `agents/sol-test-author.md` | One bounded test packet. |
| Sol semantic tester | `agents/sol-spec-aware-tester.md` | Semantic evidence and rework findings. |
| Sol audit reviewer | `agents/sol-audit-reviewer.md` | Read-only pre-final targeted findings. |
| Sol clean reviewer | `agents/sol-clean-room-reviewer.md` | Fresh sole final gate. |

Analysts, workers, tester, audit, and clean reviewer use separate contexts. Analysts advise; planner/synthesizer resolves disagreement against original spec and plan, never by voting. No role except clean reviewer approves final integration.

Sol analysis, Terra implementation, and clean review run as distinct phases unless verified capacity permits safe overlap.

## Packets and scheduling

Planner emits every packet with `id`, classification, objective, dependencies, allowed files, file ownership, shared-contract surfaces, constraints, required tests, expected evidence, and integration risks.

```text
parallel_workers = min(ready_disjoint_packets, host_capacity - 1, 3)
```

Eligible packets have all prerequisites integrated and disjoint allowed files, ownership, and shared-contract surfaces. If no worker slot remains, do not dispatch a swarm; run applicable work serially and report reduced concurrency. Controller may lower concurrency. Increasing above three requires explicit operator authorization plus verified host capacity; controller never self-authorizes an increase.

- **INDEPENDENT:** delegate one packet to Terra or Sol test author in its own branch/worktree.
- **DEPENDENT:** wait for prerequisite evidence and current integration head.
- **ARCHITECTURE_SENSITIVE / INTEGRATION:** retain with Sol/controller.

Scope is binding. An excluded or non-owned file, shared interface or cross-packet contract, ownership overlap, or architecture decision returns `BLOCKED`; Terra never expands scope or resolves it. Before integration, controller creates an appropriately classified Sol-owned `ARCHITECTURE_SENSITIVE`, `INTEGRATION`, or corrective packet from current integration head, or requests defined approval; Terra scope remains unchanged. A cherry-pick conflict remains an integration event handled below.

## Integration, test, and review loop

1. Controller integrates only `DONE` packets with verified commit SHA and complete pre-integration objective evidence; partial or `BLOCKED` states never integrate. Controller owns and appends post-integration test output after serial integration; that result is never a precondition for packet `DONE`. It then integrates commits serially in dependency order. After every successful serial merge or cherry-pick, controller runs declared combined integration tests in the integration worktree and captures objective output: command, exit code, stdout/stderr, and test identifiers. A non-green result blocks further integration plus semantic testing, audit review, and clean review. Create a narrow Sol-owned corrective packet from current integration head, rerun affected combined integration tests, and do not proceed until green.
2. Conflict, ownership breach, or shared-contract decision aborts integration and creates a Sol-owned `INTEGRATION` packet; never ask Terra to force-resolve it.
3. Sol test author receives original spec, plan, acceptance criteria, and owned test files. A declared pre-implementation red result is evidence only; required integrated tests must be green.
4. Sol semantic tester starts fresh with original spec, plan, acceptance criteria, integrated diff, test commands, and objective outputs. It returns material findings to controller and separate objective evidence only.
5. Sol audit reviewers may return `NO_MATERIAL_FINDING` or `TARGETED_REWORK`; they never approve integration.
6. Material findings create narrow corrective packets from current integration head, rerun affected tests, then repeat review.
7. Start a new Sol clean reviewer with only original spec, original plan, acceptance criteria, final diff (`base_sha..integration_head`), and objective test output. Exclude worker notes, assumptions, planner/tester/audit reasoning, and prior verdicts. Rebuild any contaminated bundle.

Clean reviewer returns `APPROVE`, `TARGETED_REWORK`, or `BLOCK`, citing requirement and code/test evidence. Approval requires required tests pass, every requirement traces to code/test evidence or explicit non-applicability, and no material divergence remains.

## Distribution and runtime verification

Personal canonical `C:\Users\aleda\.claude\skills\claude-implement` is the source of truth. After repository integration and required combined tests are green, promote the exact reviewed tree to canonical through a recorded action; then copy from canonical to Ubuntu WSL `/home/aledalin/.claude/skills/claude-implement`, Debian WSL `/home/aledaDeb/.claude/skills/claude-implement`, and the repository mirror. Verify identical relative file sets and SHA-256 hashes across canonical, both WSL targets, and repository mirror. Run `claude --model fable --effort xhigh --help` and `claude --model opus --effort high --help`; record exit status and output.

Any copy, hash, or model-command mismatch blocks final clean approval. Create a narrow corrective packet, re-synchronize, and repeat verification. Give the clean reviewer only the resulting objective verification output, never worker or reviewer reasoning.

## Failure handling and cleanup

No ready disjoint packet means sequential work. Model-routing failure means reduced assurance, not false model claims. Keep failed packet worktrees for diagnosis; remove named completed or abandoned worktrees only after recorded outcome. Local or remote branch deletion is always explicit operator action.

## Forward validation

Run `tests/forward-tests.md` after every change. Distribution is blocked until it prevents out-of-packet interface changes, clean-room bias, green-but-invariant-breaking diffs, nested worktrees, overlapping packets, Sol test-author scope escape, and Terra integration-conflict resolution.