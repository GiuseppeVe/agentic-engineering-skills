# Selective installation

Complete plugin is supported install path. Selective installation is advanced: copy chosen flat skill directories into host skill location, include dependencies from lock, and retain every listed license/NOTICE file. `None` means lock declares no skill dependency. Lost stage describes capability reduced when row is omitted, not guaranteed automatic execution.

| Skill | Dependencies | License files | Lost workflow stage |
| --- | --- | --- | --- |
| `archify` | None | `plugins/agentic-engineering-skills/licenses/tt-a1i-archify-LICENSE`; `plugins/agentic-engineering-skills/licenses/tt-a1i-archify-THIRD_PARTY_NOTICES` | Design: checked standalone diagrams and explainers |
| `brainstorming` | `to-spec` | `plugins/agentic-engineering-skills/licenses/obra-superpowers-LICENSE` | Understand: intent discovery |
| `caveman` | None | `plugins/agentic-engineering-skills/licenses/JuliusBrussee-caveman-0574b85-LICENSE` | Understand: compact collaboration |
| `cleaning-repo-with-knip` | None | `LICENSE` | Clean: dead-code cleanup |
| `development-process` | None | `LICENSE` | Plan: general process rules and orchestration guide that the orchestration skills reference |
| `deslopping-cleanup` | `development-process` | `LICENSE` | Clean: evidence review, report and separate commit per verified batch |
| `codebase-design` | None | `plugins/agentic-engineering-skills/licenses/mattpocock-skills-LICENSE` | Design: module boundaries |
| `domain-modeling` | None | `plugins/agentic-engineering-skills/licenses/mattpocock-skills-LICENSE` | Design: domain vocabulary |
| `grilling` | None | `plugins/agentic-engineering-skills/licenses/mattpocock-skills-LICENSE` | Review: plan pressure-test |
| `graphify` | None | `plugins/agentic-engineering-skills/licenses/Graphify-Labs-graphify-LICENSE`; `plugins/agentic-engineering-skills/licenses/Graphify-Labs-graphify-LICENSE-MIT`; `plugins/agentic-engineering-skills/licenses/Graphify-Labs-graphify-NOTICE` | Understand: persistent codebase knowledge graph |
| `handoff` | None | `plugins/agentic-engineering-skills/licenses/mattpocock-skills-4ae2317-LICENSE` | Plan: save a concise resumable handoff |
| `coordinating-implementation-plans` | `development-process`; `plan-implement` | `LICENSE` | Implement: coordinate approved plans and dependencies |
| `create-formal-verification-skill` | None | `plugins/agentic-engineering-skills/licenses/cursor-plugins-pstack-LICENSE` | Verify: create and prove project-local formal verification checks |
| `impeccable` | None | `plugins/agentic-engineering-skills/licenses/pbakaus-impeccable-LICENSE`; `plugins/agentic-engineering-skills/licenses/pbakaus-impeccable-NOTICE` | Design: frontend craft and critique |
| `improve-codebase-architecture` | `codebase-design` | `plugins/agentic-engineering-skills/licenses/mattpocock-skills-LICENSE` | Design: architecture audit |
| `maintain-formal-verification-skill` | None | `plugins/agentic-engineering-skills/licenses/cursor-plugins-pstack-LICENSE` | Verify: resync project-local formal checks and separate drift from bugs |
| `marketing-screenshots` | None | `LICENSE` | Design: capture and inspect real product UI for marketing assets |
| `master-orchestrator` | None | `LICENSE` | Understand: coordinate a dynamic non-implementation graph, filtered reports, decisions and design contracts |
| `mdx-to-html` | None | `LICENSE` | Verify: create a standalone MDX review artifact |
| `plan-implement` | `development-process`; `test-driven-development` | `LICENSE` | Implement: dependency-aware slice execution, L1–L3 verification, and high-risk native review checkpoints |
| `retro` | `writing-for-agents` | `plugins/agentic-engineering-skills/licenses/mattpocock-skills-4ae2317-LICENSE` | Review: reflect on a coding session |
| `setup-goal` | None | `LICENSE` | Plan: outcome runbook and approved native Goal setup |
| `setup-harness-evaluation` | None | `LICENSE` | Verify: independent harness runs for manual evaluation |
| `setup-workflow-comparison` | None | `LICENSE` | Verify: independent workflow variants for manual evaluation |
| `simplify` | None | `LICENSE` | Review: behavior-preserving code cleanup |
| `statechart` | None | `plugins/agentic-engineering-skills/licenses/cursor-plugins-pstack-LICENSE` | Verify: TLA+/TLC model checking and behavioral statechart review |
| `test-driven-development` | `development-process` | `plugins/agentic-engineering-skills/licenses/obra-superpowers-LICENSE` | Verify: red-green-refactor |
| `to-spec` | None | `plugins/agentic-engineering-skills/licenses/mattpocock-skills-LICENSE` | Plan: standalone specification |
| `wayfinder` | None | `plugins/agentic-engineering-skills/licenses/mattpocock-skills-LICENSE` | Plan: large-work map |
| `writing-for-agents` | None | `LICENSE` | Design: agent-facing document writing |
| `writing-plans` | None | `plugins/agentic-engineering-skills/licenses/obra-superpowers-LICENSE` | Plan: executable tasks |

## Conditional prerequisites

The lock records unconditional skill dependencies only. For these branches, also install:

- `wayfinder`: install `grilling` and `domain-modeling` when charting a map, resolving a Grilling ticket, or unsure which discussion skills apply.
- `improve-codebase-architecture`: install `grilling` when a candidate is selected; install `domain-modeling` when no terminology source exists or decisions crystallise.
- `plan-implement`: optionally install `simplify` and `cleaning-repo-with-knip` for the plan-level PR phase (`development-process` and `test-driven-development` are already lock-declared dependencies). This also applies when invoked through `coordinating-implementation-plans`.
- `create-formal-verification-skill`: install `statechart` when the generated project-local check uses TLA+ and TLC.

## Additional installation notes

For Impeccable, also retain `plugins/agentic-engineering-skills/licenses/pbakaus-impeccable-ADAPTATIONS-NOTICE` and `plugins/agentic-engineering-skills/licenses/ehmo-platform-design-skills-LICENSE` for the MIT-derived iOS and Android references; their attribution is preserved in the upstream NOTICE.

`Dependencies` lists bundled skill dependencies only. Runtime tools are separate: `marketing-screenshots` uses app-provided `@playwright/test` and Chromium without auto-installing them. `mdx-to-html` has no runtime package dependency; Mermaid rendering is optional and falls back to readable source plus a visible note. `statechart` requires Node.js 22.18+ (or 23.6+) and installs pinned Java + TLC via `mise` on first run (with optional `pele@1.9.0` SVG rendering).

`deslopping-cleanup` uses `development-process` for verification and documents optional external specialist routes. Its directory includes a portable skill-local copy of the repository MIT `LICENSE`; retain that copy when selectively redistributing the skill. See [dependencies and publication review](deslopping-cleanup.md) for route availability and fallbacks.

`plan-implement` does not hardcode model names or effort presets. It selects models and reasoning effort from options available in the host, the approved plan, or the operator's workspace configuration, keeping high-risk or architecture-sensitive slices on a high-reasoning profile and recording effective routing.

Both hosts discover the same 31 skills from the shared `skills/` directory; no host-specific skill root is needed.

After copying, preserve flat layout `<skills-root>/<name>/SKILL.md`. Re-run host discovery. For provenance meaning see [provenance](provenance.md); for modification rules see [customization](customization.md).
