# Specialist routing

Use this reference to choose the next specialist for an unresolved question.
The core owns phase order, decisions, batch boundaries and commits. Specialist
skills own their analysis procedures; this file defines handoffs, not copies of
those procedures. Select only routes relevant to the repository and task.
Integration, operational residue and workspace closure are phases with their own
references, linked from the core; this file covers discovery and verification.

Contents: [choosing a route](#choosing-a-route) ·
[progression](#suggested-progression-across-macro-runs) ·
[locate and prepare](#locate-and-prepare) ·
[evidence strength](#evidence-strength-and-blind-spots) ·
[hidden consumers](#hidden-consumer-checklist) · [routes](#routes) ·
[batch review](#batch-review-and-verification) ·
[phase boundaries](#phase-boundaries)

## Choosing a route

| Open question | Route |
|---|---|
| Who owns this responsibility, who consumes it? | Graphify, then source |
| Is this export, type, file or dependency unused? | `cleaning-repo-with-knip` |
| Does this live file mix old and new paths or dead symbols? | Desloppify |
| Is this module reachable from a production entrypoint? | Dependency Cruiser |
| Is reachable code part of a replaced architecture? | Flow investigation |
| Was it ever wired, and when did it lose its consumer? | History |
| Do configuration, scripts, infra, prompts or clients use it? | Non-code consumers |
| Is it exercised in production at all? | Runtime evidence |
| Several independent areas, or a claim needing a second check | Parallel agents / swarm |
| Is the batch diff correct, complete and verified? | Batch review and verification |

## Suggested progression across macro-runs

Build a sequence of complementary analysis strategies, not a checklist of tools.
The following progression is a planning aid; it does not fix a run count or require
every strategy. Combine strategies when one bounded question suffices; separate
them when they need different baselines, decisions or closure gates.

- **Established candidates first:** when removals are already supported by reviewed
  evidence, validate that evidence on the current tree and execute only approved
  batches. Their verified output becomes the discovery baseline.
- **Responsibility and symbol discovery:** use Graphify for orientation where
  relevant, then Desloppify/source investigation for intra-file remnants and
  overlapping implementations. Use cleaning-repo-with-knip to corroborate applicable
  static claims. Independent review reconciles findings with actual consumers.
- **Entrypoint reachability on the updated tree:** use Dependency Cruiser or native
  equivalents to investigate module paths and boundaries left after earlier cleanup.
  Distinguish production, test and dynamic/external consumers; cross-check with Knip
  and sources. This strategy exposes different gaps from symbol discovery.
- **Flow investigation of reachable legacy:** reachability tools only see code
  that is unreachable. Code still imported by a live path but belonging to a
  replaced architecture needs a trace of the real runtime flows. Usually the
  coupling must be cut first (with an approved functional change), after which
  reachability exposes the dead code.
- **Cascading residuals:** after verified removals, or a separately approved and
  verified architectural detachment, rescan affected dependencies and symbols.
  Review newly orphaned code, tests, configuration and documentation before planning
  further batches. Preserve shared responsibilities and protected components.

At each transition state what changed in the source tree, which question is now
answerable, and why the next strategy is useful. Revisit an earlier strategy when
new evidence warrants it. Graphify and Knip can support several runs without being
standalone runs. Lint/typecheck/tests remain authorized verification gates; they
do not establish that discovery is exhaustive.

## Locate and prepare

1. Identify the open question and existing evidence. Choose a route below.
2. Locate the named skill in the current session's catalog and read its actual
   `SKILL.md`. For tool-specific routes without a cataloged skill, use an available
   project guide and installed tool documentation. Do not assume a skill exists
   from its name or substitute a tool invocation for reading skill instructions.
   Confirm that any helper scripts and agent types mentioned by a runbook exist
   in the current environment; use configured alternatives when they do not.
3. Respect the selected skill's trigger and repository instructions. A skill
   requiring explicit user invocation is not implicitly authorized by this router.
4. Give the specialist a bounded handoff. Use authorized subagents when delegation
   is appropriate; reading a specialist skill does not itself create a subagent.
   Brief and return formats: [delegation](delegation.md).
5. Review returned evidence and apply the core's
   [controller evidence gate](../SKILL.md#controller-evidence-gate). Record provenance,
   controller checks and limits in the report; resolve material disagreements before
   choosing removal, retention or deferral. A specialist/reviewer verdict alone does
   not close that gate.

Handoffs and returns follow the canonical
[brief template](delegation.md#brief-template), including scan reproducibility and
per-claim evidence kind and confidence. For disconnected candidates it carries the
context required by
[the core rule](../SKILL.md#disconnected-components-and-the-owner). Each route
below lists only its additional input and required result.

## Evidence strength and blind spots

| Evidence | Sees | Misses |
|---|---|---|
| Graphify | responsibilities, cross-module paths | stale snapshots; inferred edges are hypotheses |
| Knip | unused files, exports, types, dependencies | computed imports, config-only use, public API |
| Dependency Cruiser | module reachability, cycles, boundaries | unresolved and computed imports, non-JS consumers |
| Desloppify | intra-file remnants, overlaps | intent; its subjective review is opinion, not proof |
| Reference search | literal names anywhere, including non-code | computed names, other repositories |
| History | when a link appeared or disappeared | intent not written in commits or tickets |
| Flow investigation | reachable legacy, runtime paths | flows not traced |
| Runtime evidence | actual use in a time window | rare paths outside the window |

- **Triangulate removals.** Removing needs at least two independent kinds of
  evidence and no unresolved counterproof. Two static tools sharing a blind spot
  are one kind; agreement between agents is no evidence at all.
- **Absence is only as strong as the search.** A "not found" records the query,
  the scope searched and what was excluded (generated code, other repositories,
  untracked files), and which items of the hidden-consumer checklist were covered.
- **Evidence expires.** A scan is tied to its SHA; after a batch, evidence on the
  changed paths and their dependents must be refreshed before reuse.

## Hidden-consumer checklist

Check the items relevant to the candidate before calling it unused:

- string or computed imports, `require` with variables, lazy `import()`;
- registries: dependency injection, route tables, worker and side-loop
  registration, plugin lists, event handler maps, queue and job handler names;
- names used by LLM prompts, tool schemas or templates;
- configuration: package `scripts`, `bin` and `exports`, CI workflows, Dockerfiles,
  deploy blueprints, cron definitions, modules selected by environment variables;
- build and test tooling: codegen inputs, bundler entry points, test setup files,
  mocks that shadow modules;
- public surface: published exports, HTTP endpoints, webhooks, clients pinned to
  older API versions, other repositories;
- persistence: collections read by other services, migrations, one-shot scripts;
- open pull requests and active branches of others that add consumers: check them
  during discovery, not only at integration;
- tests: a test-only consumer does not make code live, but removing the code
  removes coverage; record it.

## Routes

### Graphify

*Orientation and consumer discovery — optional skill/guide, if available.*

- **Choose when:** responsibility ownership, consumers or cross-module impact are
  unclear before broad exploration or before changing a contract.
- **Specialist:** available Graphify skill/guide and graph capabilities. Apply the
  repository's graph protocol where present and honor actual invocation triggers.
- **Additional input:** graph location, indexed revision/coverage if known, source
  changes since that snapshot, entrypoints and the responsibility being traced.
- **Required result:** relevant files/symbols and paths to consumers, graph snapshot
  and coverage limits, plus source confirmation of material inferred connections.
- **Fallback:** targeted text/language searches and source reading. An empty or
  stale graph result does not establish absence. No automatic install or rebuild.

### Desloppify

*Intra-file remnants and overlapping implementations — optional skill/guide, if available.*

- **Choose when:** a live file contains suspected unused symbols, duplicate
  responsibilities, or old and new implementation paths mixed together.
- **Specialist:** available Desloppify skill/guide and scoped detectors, followed
  by semantic investigation and independent review of material conclusions.
- **Additional input:** relevant files/symbols, current entrypoints, alternative
  modes, intended behavior and existing canonical-implementation evidence.
- **Required result:** precise candidates, actual references and path reachability,
  replacement/compatibility evidence, detector limitations and counterexamples.
  Distinguish detector output from subjective review actually performed.
- **Fallback:** symbol/reference analysis and direct source review. A detector
  finding or a newer implementation alone does not justify removal.

### `cleaning-repo-with-knip`

*Static findings, dependencies and false positives.*

- **Choose when:** unused files, exports, types or dependencies need triage, or
  recurring false positives need explanation.
- **Specialist:** `cleaning-repo-with-knip`, when its stated applicability fits.
- **Additional input:** workspace/configuration, installed version, raw findings,
  existing false-positive config/ledger and relevant dynamic/public consumers.
- **Required result:** per-claim verdict and evidence using the specialist's
  contract; uncertain and false-positive claims remain distinguishable. Separate
  removal proposals from missing-import/dependency reports and suppression edits.
  Compare runs as before/after differences; absolute counts are not reliable.
  Production mode (`--production`) separates code used only by tests, but it keeps
  only configured `entry`/`project` patterns marked with a trailing `!`, plus
  plugin production entries and package manifest entries (`main`, `module`,
  `browser`, `bin`, `exports`, `types`/`typings`, the `start` script's inputs).
  Without those markers the custom
  entrypoints drop out and
  findings are false positives: mark production patterns first, as an authorized
  config change, or compare against the default run.
- **Fallback:** repository-native dependency/reference analysis and scoped review.
  Keep unsupported claims uncertain. Any config/ledger changes enter the core's
  authorized batches; analysis-only routing cannot initiate cleanup or suppression.

### Dependency Cruiser

*Module reachability and boundaries — tool; dedicated skill if available.*

- **Choose when:** module imports, entrypoint reachability, cycles or dependency
  boundaries need corroboration before or after a proposed removal.
- **Specialist:** Dependency Cruiser through an available dedicated skill or
  project guide and installed capabilities; never assume a dedicated skill exists.
- **Additional input:** entrypoints (production and test kept separate),
  resolver/configuration, workspace boundaries, relevant modules and
  relationships under investigation. Run it with dependencies installed, or
  unresolved imports flood the result.
- **Required result:** paths/edges involved, resolution and coverage limitations,
  implications for the batch and, where useful, comparable before/after evidence.
  Record pinned version and rule digest.
- **Fallback:** language tooling, import searches and manual consumer tracing.
  Unresolved imports or unseen runtime links remain explicit coverage gaps.

### Flow investigation

*Reachable legacy and runtime paths — direct investigation.*

- **Choose when:** reachability tools report nothing, but an old architecture is
  suspected to still run behind live paths; or dynamic imports, spawned processes,
  configuration registrations and barrels hide consumers.
- **Specialist:** scoped explorers tracing a named flow end to end (request or job
  entry, workers, side loops, persistence), plus independent review.
- **Additional input:** the flows to trace, entrypoints, feature flags and modes,
  the target architecture and owner intent.
- **Required result:** per component a three-way classification: serves the target
  architecture, about to become legacy once a coupling is cut, already dead. Name
  the couplings to cut and the functional decision each needs.
- **Fallback:** targeted reads of entrypoints and call sites. An untraced flow
  stays an explicit gap.

### History

*Once wired or never wired — direct investigation with git.*

- **Choose when:** classification depends on whether a component was wired once
  (removable when orphaned) or never wired (defer), when its last consumer
  disappeared, or which change replaced it.
- **Specialist:** git history: `git log -S'<symbol>'` or `-G'<regex>'`,
  `git log --follow -- <path>`, blame on the former call site, linked PRs and tickets.
- **Additional input:** symbol and path, known renames, suspected replacing change.
- **Required result:** full SHAs of the commit that introduced the component and
  of the one that removed its last consumer (or "never wired"), and the replacing
  implementation if any.
- **Fallback:** PR descriptions and tickets. Unknown history leaves the
  orphaned/never-wired question open, so the candidate stays `defer`.

### Non-code consumers

*Configuration, scripts, infrastructure, prompts and clients — direct investigation.*

- **Choose when:** a candidate's name may appear outside source code, or before
  removing an endpoint, data model, environment variable, job or flag.
- **Specialist:** targeted search across the whole repository including non-source
  files, walking the hidden-consumer checklist. For environment variables use
  entrypoint reachability per deployable unit, as in
  [operational residue](operational-residue.md).
- **Additional input:** exact names and their variants (case, prefixes, routes).
- **Required result:** each reference with `file:line`, classified as live
  consumer, stale reference to clean up, or documentation.
- **Fallback:** owner knowledge of external clients, recorded as such. Unknown
  external consumers keep public surface uncertain.

### Runtime evidence

*Actual production use — read-only observation, owner-authorized.*

- **Choose when:** static, history and flow evidence cannot decide whether an
  endpoint, job, flag or stored model is used in production.
- **Specialist:** read-only logs, metrics, traces or database counts the owner
  authorizes; owner-run queries when the agent has no access.
- **Additional input:** environments, time window, identifiers to look for
  (routes, job names, collection names). Never secret values or personal data.
- **Required result:** query, window and counts. The window must cover the usage
  cycle: a monthly job needs more than a month.
- **Fallback:** an owner statement, recorded as such; without it, `defer`. Runtime
  absence never covers rare paths (yearly jobs, recovery, admin tools).

### `dispatching-parallel-agents` / `swarm-advanced`

*Exploration and independent review.*

- **Choose when:** independent responsibility areas need investigation, or
  material exploration claims need a separate source check.
- **Specialist:** `dispatching-parallel-agents` for small independent scopes;
  `swarm-advanced` for complex runs, subject to repository delegation rules.
- **Additional input:** disjoint read scopes and questions, shared verified context,
  expected evidence and the claims requiring review.
- **Required result:** scoped explorer findings and independently checked review
  conclusions, disagreements and source-based resolutions. Reviewer reads relevant
  sources; repeating the explorer's summary is not independent verification.
- **Fallback:** authorized native explorer/reviewer delegation, or sequential
  scoped investigation. If independent review is a
  required gate and unavailable, keep that gate pending and affected batches open.

### Batch review and verification

*`requesting-code-review` + `verification-before-completion`.*

- **Choose when:** a batch diff needs independent review or closure evidence.
- **Specialist:** available `requesting-code-review` and
  `verification-before-completion`, with current repository checks and permissions.
- **Additional input:** Batch-ID, approved actions/allowlist, base and diff,
  validated content manifest, expected wiring and authorized check commands.
- **Required result:** findings, their resolution, checks with actual scope and
  revision, pending/failed results and evidence of preserved live connections.
  Include byte hygiene (`git diff --check`, BOM, final newline, line endings) and
  any external reviewer available on the hosting platform.
- **Documentation:** the batch updates documents that name removed components.
  Instruction files (`AGENTS.md`, `CLAUDE.md`) get a proposed change, not an edit,
  unless the owner authorizes it.
- **Checks:** run them with the CI toolchain versions (runtime, package manager).
  Separate environment failures (shared ports, missing tools, wrong runtime) from
  code failures. A failure is pre-existing only if it reproduces on the base in
  the same environment; a test is flaky only if repeated runs on the same revision
  disagree. Neither label lets a failure pass silently: record it. When local
  resources are shared with other sessions, the clean external CI is authoritative.
- **Fallback:** direct diff/source review and authorized available checks. Missing
  required review/check evidence blocks closure; it is never reported as a pass.

## Phase boundaries

Raw scans can generate candidates during exploration. Independent reviewers check
material findings; specialists are then reused to resolve specific gaps. New
material findings return to review before strategy or approval. The router does
not prescribe running every tool on every batch: heavy scans run per run, while
batches refresh only the evidence their diff touched.

Propose ending discovery when a fresh strategy on the updated tree yields no new
material candidates, or every remaining candidate is retained or deferred with a
re-entry trigger. Record that stopping point; it is not proof that no dead code
is left.

Specialist outputs are evidence and proposals. Their generic instructions do not
expand the run's mandate or bypass core batch/report/commit gates. Do not invent
commands, completed scans or availability, copy specialist skills into this folder,
or install missing components by implication.
