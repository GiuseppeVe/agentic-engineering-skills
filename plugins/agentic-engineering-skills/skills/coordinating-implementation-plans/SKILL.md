---
name: coordinating-implementation-plans
disable-model-invocation: true
description: Coordinate an approved contracts map of implementation plans, running compatible plan threads in parallel and managing dependencies, integration, and closeout.
---

# Coordinating Implementation Plans

Coordinate an approved multi-plan programme; you are the sole author of its
contracts map. Delegate plan execution and verification to subordinate plan
threads (`plan-implement`). For a standalone plan, invoke `plan-implement`
directly with the host's native invocation command.

At launch and on every resume, read
[master–plan dialogue](references/master-plan-dialogue.md) and the shared
[programme messages](../plan-implement/references/programme-messages.md)
definition; each plan thread follows its side in
[reporting to the master](../plan-implement/references/reporting-to-master.md).
The master decides routing, readiness, and resumption within the mandate and
escalates only reserved choices to the owner.

Run-conduct and plan/package lifecycle rules live in one place:
[Program orchestration](../development-process/references/program-orchestration.md).
Apply them and point briefs there without restating them. At programme start,
when the repository provides a host preflight script, run it on every machine
before its first gate or push, present the owner once with the list of planned
pushes and merges, and create the `integration/<map>` branch.

## 1. Sources, dependencies, and parallelism

Read repository instructions, workflow docs, the contracts map, specs, and
approved plans. On resume, reconcile these sources against ledgers, threads,
branches, and live PRs; document recency or unchecked boxes never prove
integration.

For each dependency, identify consumer, component, producer, target with
revision, and availability proof. A commit only in the producer's feature
branch does not unblock the consumer. Preserve enough state to resume partial
integrations cleanly.

**Launch compatible plan threads in parallel** when prerequisites are met: use
the contracts map to verify absence of collisions or explicit handling
(ownership, compatibility, coordination). Apply map order and stop points only
to affected plans; keep independent plans moving. Respect host capacity limits.

Preserve checkouts, forks, sessions, and processes outside the programme,
including during cleanup. Bring source conflicts, contract changes, or
uncovered behaviors to the owner; use already-granted mandate authority for
ordinary steps.

Authorize plan threads only within the perimeter of the contracts map, specs,
and approved plans. Each out-of-perimeter request requires explicit user
approval; one granted exception never authorizes subsequent requests.

## 2. Assign one visible thread per plan

Create **one user-visible plan thread** that invokes `plan-implement` with the
host's native command and receives the plan, spec, and contracts-map paths.
Each plan thread coordinates its own slice-implementer and high-risk review
subagents under `plan-implement`, and owns its ledger, full PR phase,
authorized merge, and cleanup.

Plan coordination requires visible subordinate threads, **not substitute CLI
loops**. If the host cannot create them, report `blocked`. Repository gate and
review commands remain allowed. The master does not launch a duplicate PR
verification thread.

Before delegating a plan thread, commit the
[plan mandate document](../plan-implement/references/plan-mandate.md) in its
branch and, on `pkg/*`, commit or update the
[package manifest](references/package-manifest.md) in the same step that
updates the contracts map ([dialogue procedure](references/master-plan-dialogue.md)).
Never choose or drop CI gates: the project's versioned map selects them.

Include in each plan brief:

- the master's reachable address, plan mandate (path and revision), and
  reserved decisions;
- workflow pointers; readable plan, spec, and map paths with revisions/SHAs;
- tasks or prefix, expected outcomes, dependencies, and stop points;
- `plan-implement`, project, branch, base SHA, and worktree constraints;
- `pr_base`; `integration_target` only when explicitly planned;
- authorizations, limits, known base failures, and required closing report.

Resolve missing references before launch. On new runs the plan thread creates
its branch and worktree; on resume it reconciles existing ones against its
ledger. Pass sources and constraints without injecting implementation code or
rewriting behavior.

## 3. Track threads and update the map

Use host notifications or compact snapshots. On wake, reconcile open questions,
decisions awaiting delivery, and arrived results; verify receipt before
resending, and ensure a duplicate response produces only one step. Record plan,
confirmed ID, host, branch/worktree, revisions, and status in canonical state.
Keep provisional IDs distinct: pending launches occupy a slot without counting
as confirmed running threads.

Timeouts, queued messages, and turn endings do not complete a plan. For missing
evidence, continue on the same thread. If waiting on the owner, state the exact
action needed and hold the slot. Create a replacement thread only after a
confirmed failure or closure, reconciling identity, output, and Git state.
Never bypass a denial through another thread. Compatible plans continue in
available slots.

Verify reports against actual commits, targets, worktrees, and check results;
distinguish invoked skills, completed work, and applied fixes. Route fixes and
re-verification back to the same plan thread. For blockers, identify root
cause, owner, and unblock condition, applying only authorized retries.

Update the contracts map after merges, decisions, or dependency changes with
evidence and revisions; notify affected threads. When adding a plan or opening
its PR, update the package manifest in the same step; a perimeter change is a
new committed revision of the plan mandate. Resolve content conflicts in the
owning thread.

## 4. Verify readiness, authorize, and close

Each plan thread follows [PR phase](../development-process/references/daily-workflow.md#pr-phase)
with any more specific rules of the receiving repository. Keep concrete
commands and procedures in repository documents.

Receive PR URL, base, final head SHA, readiness evidence, and blockers; slice
acceptance does not substitute for plan-level PR readiness. Verify the
authorized integration path and record head and perimeter before proposing an
action; readiness and merge authorization remain distinct and open obligations
stay visible.

A plan thread merges its own ready PR into a non-`main` branch within mandate
order, dependencies, and stops; only merges into `main` wait for explicit owner
authorization. After merge, the plan thread updates the target, runs the
integration branch check, and finishes required cleanup and index updates.

Master-declared readiness never widens the mandate: respect explicit owner
approval for `main` and repository command gates, reusing valid green statuses.
Verify integration SHA, checks, and cleanup in the closing report; update the
map and archive the thread only after verified closure. Unblock dependent items
immediately per the map without waiting for unrelated plans.

Report status per plan/package, next actions, blockers, and decisions needed,
separating pass, fail, and not run as well as implementation, integration, and
release. Close the programme when every planned unit and closure is verified or
the owner re-scopes the programme.
