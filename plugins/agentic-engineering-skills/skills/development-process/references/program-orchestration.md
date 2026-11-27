# Program Orchestration

Guide for agents coordinating multi-task plans or multi-package programmes. Complements [Daily workflow](daily-workflow.md). `coordinating-implementation-plans` and `plan-implement` point here instead of restating these rules.

## Subagent Delegation

Before delegating, ask what the subagent would otherwise have to guess or rediscover. Each brief contains:

- **Expected outcome** in one sentence, **constraints** (allowed files, scope, off-limits areas), and **success criteria**.
- **References:** ADRs, specs, plans, and entry-point files to read first.
- **Facts separated from hypotheses;** details surfaced only in chat stated explicitly.
- Pointers to these process documents without restating them.

Use a fresh context for explorations and independent reviews. For an independent clean-room review, pass only objective evidence and contracts — never your own diagnosis or conclusions. For contiguous tasks in the same module, `plan-implement` may keep one persistent slice-implementer subagent warm across that slice while keeping reviews independent.

## Run Conduct

- **Startup:** when the repository provides a host preflight script, run it on every machine before its first gate or push. Present the owner once with a single upfront list: preflight issues plus planned pushes and merges. Do not re-ask items already in that list. The list never authorizes a merge into `main`.
- **Code transport:** code reaches gate machines only through Git (branch push or bundle file). Never put patches or base64 diffs in briefs or messages.
- **Gates:** when the repository provides a self-queuing gate runner, request gates through it; no agent assigns slots or polls locks manually.
- **Owner questions:** an open question never stalls independent authorized work; keep moving on unrelated tasks and resurface the question in the next report.
- **Child outcomes:** only `done`, `partial`, or `blocked`. The coordinator acts on `partial`, `blocked`, conflicts, and plan deviations; a `done` result updates status without extra relay turns.
- **Owner messages:** open with a single action-needed first line in the user's language (e.g. `Action needed: none` or `Action needed: <action> in <link>`), followed by details. Link every referenced thread or PR.

## Plan and Package Lifecycle

A contracts map groups plans into packages; each package has a `pkg/*` branch that ultimately holds all its plans.

- **Plan → `pkg/*`:** open the plan PR against `pkg/*`; follow [PR phase](daily-workflow.md#pr-phase); once green, notify the owner (`Action needed: none. Plan <id> is green; merging into pkg/<x> (PR #N).`) and merge without waiting.
- **Continuous integration branch:** each map has an `integration/<map>` branch created from `origin/main` at programme start. Right after merging a plan into `pkg/*`, the plan thread merges that `pkg/*` into `integration/<map>`, pushes, and runs the repository's integration suite via its gate command. Any red returns to the plan thread that introduced it; a merge conflict escalates to the master as `blocked`. No force-pushes.
- **Package → `main`:** once all plans are in `pkg/*`, open a single PR from `pkg/*` to `main` with the integration suite already green on `integration/<map>`, run the PR phase, then ask the owner for explicit merge authorization into `main`.
- **Status from the host:** derive plan and package status from the hosting platform rather than orchestrator logs (e.g. `gh pr list --base pkg/<x> --state merged --json number,title,body,mergeCommit`), matching each PR to its plan via the `Plan: <id>` line in the PR body. A PR without that line is unmatched and does not advance status.
- When repository CI checks mandates and package manifests, the master commits the mandate document before delegating a plan and commits/updates the package manifest when creating or adding plans to a package.

## Child Delivery

A subordinate thread's final message begins with one status line:

```text
status=<done|partial|blocked> | pr=<URL|none> | sha=<sha|none> | base=<branch|none> | report=<absolute path|none>
```

Details live below the line or in the report file. Use `done` only when the assigned scope is complete and verified with `sha` present on `origin`; locally accepted work without a required remote push is `partial`. The receiver verifies `sha` on `origin` with Git or `gh`.

*(Inside a single plan, lightweight slice handoffs between `plan-implement` and its slice-implementer subagents follow [slice-contract.md](../../plan-implement/references/slice-contract.md) so subagent agency is not bogged down by rigid ceremony.)*

## Plans and Convergence Limits

- Plans state contracts, interfaces, tests, risk tags, and acceptance criteria — not full implementation code.
- Before implementation, a plan receives an adversarial design review covering states, concurrency, cancellation, authorization, and privacy.
- Acceptance criteria are provable with fixtures; native or live operational proofs are separate tasks.
- Two negative review outcomes on the same module trigger a single redesign with a state/event matrix rather than another patch loop.
- Three attempts on the same slice/task without acceptance escalate to the owner.
- A reviewer never prescribes the next unit of work.

## Optional OpenCode / External Provider Threads

When a run explicitly routes a thread to an external bridge provider (such as an OpenCode loopback bridge), verify the bridge and server are running using the receiving repository's scripts and `plan-implement`'s optional provider-routing reference. On connection refusal (`ECONNREFUSED`), start or diagnose the bridge instead of blindly retrying, and never switch models or providers without owner authorization.
