# Agentic Engineering Skills

![Agentic Engineering Skills — shared workflow from evidence to reviewed delivery](assets/agentic-engineering-skills-hero.svg)

I share this experience-shaped workflow from hands-on engineering work: one master orchestrator coordinates a graph of focused work, while specialist agents and sessions carry each task forward.

## What this repository shares

This repository shares composable skills for Codex and Claude Code, organized around a master orchestrator. Start a conversation with the master, describe the outcome and constraints, and let it coordinate the work across a changing graph of scoped tasks, delegates, and decisions. The research and design master and the implementation-program coordinator support two complementary graph workflows. Reasoning, dependencies, evidence, and ownership stay visible enough to inspect and adapt in another project.

## My working philosophy

I start from evidence instead of an implementation guess, then turn decisions into durable specifications and traceable plans. I isolate implementation work, keep worker output separate from independent evidence, and use two quality dimensions: whether delivery remains faithful to its plan and whether implemented behavior is correct. Publication and other external actions stay under explicit owner control; a plan or passing test suite does not grant publication permission.

Vendor files remain byte-exact, adaptations stay auditable, and repository-original files use this repository's MIT license. Third-party assets keep their own terms even when bundled in an MIT-licensed skill. [Workflow philosophy](docs/philosophy.md) records lifecycle gates, handoff evidence, optional-tool fallbacks, and human authority boundaries.

## How to set up a new project

Before using the workflow in a new repository, give agents a small, reliable entry point to the project's knowledge. Add an `AGENTS.md` at the repository root. Keep it extremely short: include only cross-cutting instructions that matter broadly, and point to the project documents agents should consult for each kind of task. Links tell agents where to look; linked documents are not automatically loaded into context.

A possible starting layout:

```text
AGENTS.md                      # Short instructions and map for agents
README.md                      # Project overview and entry point for people
docs/
  development/
    CODING_STANDARDS.md        # Shared engineering conventions
    BACKEND.md                 # Backend-specific guidance, if applicable
    FRONTEND.md                # Frontend-specific guidance, if applicable
  architecture/
    OVERVIEW.md                # System boundaries and major components
    adr/                       # Important decisions and their status
  operations/
    LOCAL_SETUP.md             # Prerequisites, setup and local execution
    DEVELOPMENT_OPERATIONS.md  # Verification and development procedures
  work/
    specs/                     # Approved requirements and designs
    plans/                     # Implementation plans and progress
    reports/                   # Verification results and historical evidence
```

Create `AGENTS.md` in the root of your project and use it as the short entry point to your documentation. For example, if the guides above exist in your project, the contents of `AGENTS.md` could be:

```markdown
# Project instructions

- Project overview: read `README.md`.
- Shared conventions and verification: read `docs/development/CODING_STANDARDS.md`.
- Service boundaries and decisions: read `docs/architecture/OVERVIEW.md` and the relevant ADRs `docs/architecture/adr/`.
- Local setup: read `docs/operations/LOCAL_SETUP.md`.
```

Use only the files your project needs and adapt their names and structure. Keep each rule or decision in one authoritative place, and link to it from the short entry point. Do not create empty documents merely to match this example.

For a file-by-file explanation, how to decide what belongs where, and host-specific setup, see [project context and instructions](docs/workflow.md#project-context-and-instructions).

## Graph workflows

A graph workflow starts with a **new chat and an explicit orchestration skill**. Give the master the objective, scope, expected result, constraints, and existing instructions. It sets up the run from that context: nodes, dependencies, responsibilities, and completion criteria evolve as the work reveals new questions. You keep the conversation with the master while it coordinates focused subagents and, when supported and authorized, separate sessions or subthreads.

These are task and decision graphs. Graphify's semantic codebase graph can supply evidence to a delegated investigation; it is a separate tool and is not required to run the master.

### When Graphify is useful

Consider Graphify when a large codebase makes an agent spend substantial time and tokens finding files and their relationships. As a rough guideline, maintaining a codebase graph is often inefficient below 100,000 lines of code; above that scale, evaluate whether faster discovery outweighs the cost of building and updating it. This is a heuristic, not a hard threshold.

### Research, analysis, and design

In a fresh Codex chat, explicitly invoke `$master-orchestrator`. In Claude Code, select the installed `master-orchestrator` skill explicitly. The [skill](plugins/agentic-engineering-skills/skills/master-orchestrator/SKILL.md) covers non-implementation work: repository study, research, audits, design, and migration planning.

The master keeps the run's objective, state, decisions, and dependencies in view. Delegates inspect sources and return filtered, attributable findings; a different delegate authors the deliverable, with independent review when needed. The master evaluates the reports and updates the graph, adding or revisiting nodes as evidence changes. Human decisions pause their dependent nodes while unrelated work can continue. Creating visible chats, using trackers, and preserving resumable state depend on the host's capabilities and the user's authorization.

For larger design programs, the master also maintains a map of decisions and a separate map of shared contracts. It coordinates authorized streams, ownership, amendments, and unresolved conflicts before delivering specifications, plans, or an implementation handoff. The master itself does not implement code.

![Available non-implementation graph workflow: a user starts a master chat, the master dispatches scoped investigation and authorship, reviews filtered results, and updates the graph before delivering decisions, specifications, plans, or a handoff](assets/graph-workflow-non-implementation.svg)

### Implementation programs — available

In a new chat, explicitly invoke [`coordinating-implementation-plans`](plugins/agentic-engineering-skills/skills/coordinating-implementation-plans/SKILL.md) with the approved contracts map, plans, specifications, constraints and authorizations. The master coordinates dependencies and compatible plans in parallel; a dependency is ready only when the required revision is available on its target.

Each plan has a visible subordinate thread using `plan-implement`, which delegates contiguous module tasks to persistent slice-implementer subagents, verifies deterministic L1–L3 checks, runs clean-room native review checkpoints on `risk: high` slices and shared contracts, commits accepted slices when authorized, and runs the full-diff PR phase once on the integrated head. Independent slices may overlap only in isolated worktrees with disjoint ownership and a defined integration order. The plan thread owns its PR lifecycle and authorized merge and cleanup; the master verifies evidence, maintains the contract map and unblocks dependent work. If the host cannot create the required visible threads, the workflow reports a block. For a single plan, invoke `plan-implement` directly.

![Implementation graph workflow: the master coordinates parallel plan threads, each with sequential implementation and independent review, then verifies integration and unblocks dependencies](assets/graph-workflow-implementation.svg)

## How I use the workflow

The master selects relevant specialist routes within the authorized scope. These are composable choices, not mandatory stages for every task; existing implementation routes remain usable directly.

| Situation | Path | Purpose |
| --- | --- | --- |
| Research, analysis, audit, or design program | `Master Orchestrator` | Coordinate a dynamic graph of delegated non-implementation work. |
| Large, uncertain initiative | `Wayfinder` | Map scope that reaches beyond one session when useful and available. |
| Outcome-driven native Goal run | `Setup Goal` | Agree the outcome, constraints, and metrics, save a runbook, then request confirmation to launch the host's native Goal. |
| Bounded or creative design | `Brainstorming` | Clarify intent before changes. |
| Consequential or disputed design | `Grilling` | Pressure-test assumptions. |
| Agreed design | `To Spec` | Create standalone specification. |
| Multi-step implementation | `Writing Plans` | Create traceable implementation plan. |
| Implementation program with multiple approved plans | `Coordinating Implementation Plans` | Coordinate compatible plan threads in parallel and track dependencies. |
| One implementation plan | `Plan Implement` | Coordinate dependency-ready slices with persistent slice-implementer subagents, L1–L3 verification, and high-risk native review checkpoints. |
| Small, well-understood implementation | Inline with `Test-Driven Development` | Implement directly with red-green-refactor, deterministic checks, and explicit checkpoints without plan-level orchestration. |
| Repository cleanup across responsibilities | `Deslopping Cleanup` | Investigate candidates, review evidence, and commit verified cleanup batches. |
| General process rules for any session | `Development Process` | Read the daily workflow (mandate, verification, PR phase, closing report) and program orchestration rules that the other skills point to. |

Explicitly invoke [`setup-goal`](plugins/agentic-engineering-skills/skills/setup-goal/SKILL.md) when you want to prepare a native Goal run. It co-designs the outcome, constraints, and progress metrics, then saves `runbook.md` with those three sections. Review the saved runbook and exact Goal condition before giving final confirmation to start that version. Only then does it activate the host's native Goal; agreeing individual sections does not start execution. If the host has no native Goal capability, the runbook remains ready and activation is reported as blocked.

See [workflow guide](docs/workflow.md) for routing detail.

## The quality loop

For ordered work, `Test-Driven Development` checks plan fidelity, requirement coverage, and implementation correctness through failing tests, implementation, and passing tests, backed by deterministic L1–L3 checks (typecheck, static analysis, and behavioral, contract, property, or real-runtime tests). Findings return through the TDD fix cycle before acceptance, then independent evidence informs host-native code review.

The [process rules](plugins/agentic-engineering-skills/skills/development-process/SKILL.md) fix the order of the PR phase: a fast local check, one independent host-native review of the whole diff with `simplify` and Knip in parallel, fixes in one commit, and the full gates once on the frozen head. They are guidance the agent follows under the receiving project's rules; no hook enforces them.

## Hooks I use

The plugin registers one PR-gate launcher and one fast read-only edit-lint hook as `PostToolUse` hooks. Invoke `Caveman` explicitly when you want compact communication.

After a shell command opens a draft pull request (`gh pr create --draft`), a `PostToolUse` hook starts the repository's own `npm run gates:lint` in the background. After one opens a non-draft pull request or marks one ready (`gh pr create` without `--draft`, or `gh pr ready`), it starts `npm run gates:lint` and then `npm run gates:pr`. Each script runs only if the root `package.json` defines it, and the hook tells the agent where the log is. It never blocks, verifies or reminds; without the scripts it does nothing. The repository decides what its gates are.

After an edit tool modifies JS/TS files (`Edit`, `Write`, `MultiEdit`, `apply_patch`), a second `PostToolUse` hook (`edit-lint.mjs`) runs the repository's local Oxlint in fast syntactic read-only mode on only the edited files when `.oxlintrc.json` and local `oxlint` are present, returning only blocking errors and staying silent otherwise. Shared presets live in [`standards/static-analysis/`](standards/static-analysis/README.md).

The plugin ships no reminder or verifier hook. Earlier versions added `PostToolUse` reminders after PR creation and after merge, together with a PR preflight verifier and a comment marker. Version 1.2 removed them: the steps they repeated now live as short rules in [`development-process`](plugins/agentic-engineering-skills/skills/development-process/SKILL.md), and a repository keeps its own git hooks and CI as its gates.

The hook needs Node.js 22 or newer. Codex requires the plugin hooks to be reviewed and trusted before a fresh session; Claude Code also needs the plugin and hook configuration enabled. The [plugin hooks guide](docs/plugin-hooks.md) documents setup and coverage limits.

## Supporting skills

I invoke `Impeccable` for frontend design and critique, and `Caveman` to keep communication compact. `Improve Codebase Architecture` helps me identify where modules lack depth or locality, so I can choose focused refactors that improve leverage and testability.

### Deslopping Cleanup

[`deslopping-cleanup`](plugins/agentic-engineering-skills/skills/deslopping-cleanup/SKILL.md)
coordinates behavior-preserving repository cleanup as a campaign of macro-runs,
coherent batches and recoverable commits. Run count and strategy order follow
evidence gaps: each cumulative run consumes the preceding verified output and
answers a complementary question. Explorers gather facts; independent reviewers
challenge them; the controller directly checks decisive source claims, consumer
links, diff scope and gate evidence before approving the technical conclusions. Before batch approval, every proposed file/action receives its own rationale, evidence, expected wiring impact and uncertainty in the run report. Each verified batch updates a cumulative report of
removed, retained and deferred components and their actual or intended connections,
then receives its own local commit before the next batch starts. The campaign
report records run baselines, closure/acceptance criteria, controller verdicts and
handoffs; new residuals can justify another run without prescribing a fixed count.

The skill also helps determine whether a component is superseded, belongs to an
older implementation, or still serves a current or planned responsibility. It
combines semantic inference with source and history checks, actual consumers,
replacement behavior, compatibility requirements and intended functionality.
Before classifying disconnected components, it asks the owner which reference
documents describe that intent and which are authoritative and current, then
compares them with actual wiring. This adds context to static findings and makes
removal, retention and deferral proposals more precise and easier to judge.

An older name or a newer alternative alone does not establish obsolescence;
disconnected code may be a new feature deliberately awaiting integration.
Unresolved intent remains deferred rather than being presented as safe to remove.

Removals need at least two independent kinds of evidence, such as static analysis,
reference search, history, flow tracing or runtime observation, and no unresolved
counterproof. After discovery, the campaign can continue with branch integration
(conflict inventory, per-area decisions, completeness and semantic-conflict
checks), operational residue (configuration, stored data, external artifacts and
deployments, each non-file action separately approved) and workspace closure
(inventory of unique work, including ignored files, before any deletion).

![Deslopping Cleanup pipeline: reviewed evidence, approved batches, report and commit checkpoints](assets/deslopping-cleanup-pipeline.svg)

Specialists remain distinct. `cleaning-repo-with-knip` and `graphify` are included.
Desloppify, Dependency Cruiser and the named external dispatch/review capabilities
remain optional, with explicit fallbacks; the bundle does not install those
external tools or load them automatically. Graphify supplies a semantic evidence
graph, separate from the master's task and decision graph. See [availability and license review](docs/deslopping-cleanup.md)
and the skill's [specialist routing](plugins/agentic-engineering-skills/skills/deslopping-cleanup/references/specialist-routing.md).

### Implementation routes

The diagram below shows the shared lifecycle of delivery responsibilities. The
master coordinates non-implementation nodes according to scope and uncertainty;
implementation is handed off to an appropriate, authorized execution route.

For a large change spanning multiple modules, I start with `Master Orchestrator`
to coordinate discovery and design, using `Wayfinder` when useful and available.
After the agreed design and plan are ready, an authorized handoff can use
`Plan Implement` to dispatch persistent slice-implementer subagents, verify
deterministic checks, run clean-room native review checkpoints on high-risk
slices, and open one plan PR.

For a small, well-understood change, I implement inline with `Test-Driven Development`, retaining
the relevant TDD, verification and owner-approval gates.

## Workflow at a glance

This diagram is the canonical overview of delivery responsibilities. A graph run can branch or revisit work within the relevant stages; the diagram does not prescribe one chat per stage.

```mermaid
flowchart LR
  U[Understand] --> D[Design]
  D --> P[Plan]
  P --> I[Implement]
  I --> V[Verify]
  V --> R[Review]
  R --> C[Clean]
  C --> A{Owner approves publication?}
  A -->|Yes| X[Approved external action]
  A -->|No| L[Keep local]
```

## Install

Install complete bundle. This is supported path.

Codex:

```text
codex plugin marketplace add GiuseppeVe/agentic-engineering-skills
codex plugin add agentic-engineering-skills@agentic-engineering-skills
```

Claude Code:

```text
claude plugin marketplace add GiuseppeVe/agentic-engineering-skills
claude plugin install agentic-engineering-skills@agentic-engineering-skills
```

Confirm discovery with `codex plugin list --available --json` or `claude plugin list`. Then start a fresh host session and invoke one included skill, such as `brainstorming`; plugin listing alone does not prove fresh-session invocation.

Enable and trust the plugin hooks separately from skill installation; see [Hooks I use](#hooks-i-use) for what they load and their prerequisites.

Role attachments and native-agent registrations are separate. Implementation session profiles require explicit local setup; see the relevant implementation skill for its role and routing requirements.

The plugin exposes 31 shared skills to both Codex and Claude Code. Role-appropriate models and reasoning effort are selected from host, plan, or operator workspace options rather than hardcoded defaults.

Selective copying is advanced and can remove workflow stages. See [selective installation](docs/selective-install.md).

## Why version 1.2

Version 1.1 introduced graph workflows: instead of managing one chat at a time, I start with a master orchestrator that coordinates the work.

For research and design, the master delegates focused investigations and brings the results together. For implementation, a second master coordinates approved plans, running compatible plan threads in parallel while each plan handles its tasks and reviews in sequence.

Version 1.2 makes this plugin the single source of my general development process. The `development-process` skill carries the process and orchestration rules, and the orchestration skills point to it instead of restating them or pointing at one project's documents. The PR lifecycle hooks, the PR preflight verifier and its marker are removed: enforcement inside agent sessions slowed the work down, so the rules are now short guidance and each repository keeps its own git hooks and CI.

Version 1.5 refines that foundation: `development-process` splits daily workflow (with lightweight L1–L3 verification) from multi-package program orchestration in English, and `plan-implement` replaces `plan-orchestrator` and `task-implement` with a 2-level slice-subagent model and high-risk native review checkpoints.

The idea behind this software factory and the decisions that shape it are recorded in the [factory decision records](docs/adr/README.md), written in Italian.

## Customize

Fork repository and edit source files, never generated plugin cache. Full workflow: [customization guide](docs/customization.md).

## Compatibility

Bundle targets exactly two verified hosts: Codex and Claude Code. Release-specific validation evidence belongs in `docs/release-report.md`. See [compatibility](docs/compatibility.md).

## Provenance

Every skill is classified as `vendor`, `adapted`, or `original`, with hashes and pinned revisions in lock. See [provenance inventory](docs/provenance.md).

## License

Repository-original material: [MIT](LICENSE), copyright GiuseppeVe. Upstream MIT terms cover only the upstream works they license; bundled assets can carry separate restrictions. Archify's MIT license covers its code, while bundled artwork includes CC-BY-NC-SA-4.0 Vue artwork, CC-BY-SA artwork, and an SIL OFL 1.1 font. Review [Third-Party Notices](THIRD_PARTY_NOTICES.md) and the [pinned Archify asset notice](plugins/agentic-engineering-skills/licenses/tt-a1i-archify-THIRD_PARTY_NOTICES) before reuse. Forking, editing, removal, and redistribution remain subject to all applicable terms.
