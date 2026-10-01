# Specialist routing

Use this reference to choose the next specialist for an unresolved question.
The core owns phase order, decisions, batch boundaries and commits. Specialist
skills own their analysis procedures; this file defines handoffs, not copies of
those procedures. Select only routes relevant to the repository and task.

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
5. Review returned evidence and apply the core's
   [controller evidence gate](../SKILL.md#controller-evidence-gate). Record provenance,
   controller checks and limits in the report; resolve material disagreements before
   choosing removal, retention or deferral. A specialist/reviewer verdict alone does
   not close that gate.

Every handoff contains Campaign-ID/Run-ID, repository/branch/worktree and source
snapshot, the specific question, candidate IDs/files/symbols, relevant
contracts/consumers, verified facts,
uncertainties, scope/exclusions, allowed actions and the expected result.
For disconnected candidates, include the user's reference-document answer,
authoritative snapshots, intended integration status and unresolved questions from
[the core rule](../SKILL.md#interpret-disconnected-components-with-the-owner).
Every return identifies the question answered, verdict, evidence locations and
snapshot, counterproof, remaining uncertainty and proposed next action.

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
- **Fallback:** repository-native dependency/reference analysis and scoped review.
  Keep unsupported claims uncertain. Any config/ledger changes enter the core's
  authorized batches; analysis-only routing cannot initiate cleanup or suppression.

### Dependency Cruiser

*Module reachability and boundaries — tool; dedicated skill if available.*

- **Choose when:** module imports, entrypoint reachability, cycles or dependency
  boundaries need corroboration before or after a proposed removal.
- **Specialist:** Dependency Cruiser through an available dedicated skill or
  project guide and installed capabilities; never assume a dedicated skill exists.
- **Additional input:** entrypoints, resolver/configuration, workspace boundaries,
  relevant modules and relationships under investigation.
- **Required result:** paths/edges involved, resolution and coverage limitations,
  implications for the batch and, where useful, comparable before/after evidence.
- **Fallback:** language tooling, import searches and manual consumer tracing.
  Unresolved imports or unseen runtime links remain explicit coverage gaps.

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

### `requesting-code-review` + `verification-before-completion`

*Batch review and verification.*

- **Choose when:** a batch diff needs independent review or closure evidence.
- **Specialist:** available `requesting-code-review` and
  `verification-before-completion`, with current repository checks and permissions.
- **Additional input:** Batch-ID, approved actions/allowlist, base and diff,
  validated content manifest, expected wiring and authorized check commands.
- **Required result:** findings, their resolution, checks with actual scope and
  revision, pending/failed results and evidence of preserved live connections.
- **Fallback:** direct diff/source review and authorized available checks. Missing
  required review/check evidence blocks closure; it is never reported as a pass.

## Phase boundaries

Raw scans can generate candidates during exploration. Independent reviewers check
material findings; specialists are then reused to resolve specific gaps. New
material findings return to review before strategy or approval. The router does
not prescribe running every tool on every batch.

Specialist outputs are evidence and proposals. Their generic instructions do not
expand the run's mandate or bypass core batch/report/commit gates. Do not invent
commands, completed scans or availability, copy specialist skills into this folder,
or install missing components by implication.
