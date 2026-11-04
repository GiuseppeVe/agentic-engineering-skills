# Selective installation

Complete plugin is supported install path. Selective installation is advanced: copy chosen flat skill directories into host skill location, include dependencies from lock, and retain every listed license/NOTICE file. `None` means lock declares no skill dependency. Lost stage describes capability reduced when row is omitted, not guaranteed automatic execution.

| Skill | Dependencies | License files | Lost workflow stage |
| --- | --- | --- | --- |
| `archify` | None | `plugins/agentic-engineering-skills/licenses/tt-a1i-archify-LICENSE`; `plugins/agentic-engineering-skills/licenses/tt-a1i-archify-THIRD_PARTY_NOTICES` | Design: checked standalone diagrams and explainers |
| `ask-matt` | None | `plugins/agentic-engineering-skills/licenses/mattpocock-skills-4ae2317-LICENSE` | Understand: route to a fitting skill or flow |
| `brainstorming` | `writing-plans` | `plugins/agentic-engineering-skills/licenses/obra-superpowers-LICENSE` | Understand: intent discovery |
| `caveman` | None | `plugins/agentic-engineering-skills/licenses/JuliusBrussee-caveman-0574b85-LICENSE` | Understand: compact collaboration |
| `cleaning-repo-with-knip` | None | `LICENSE` | Clean: dead-code cleanup |
| `deslopping-cleanup` | None | `LICENSE` | Clean: evidence review, report and separate commit per verified batch |
| `codebase-design` | None | `plugins/agentic-engineering-skills/licenses/mattpocock-skills-LICENSE` | Design: module boundaries |
| `domain-modeling` | None | `plugins/agentic-engineering-skills/licenses/mattpocock-skills-LICENSE` | Design: domain vocabulary |
| `grill-me` | `grilling` | `plugins/agentic-engineering-skills/licenses/mattpocock-skills-LICENSE` | Understand: design challenge |
| `grilling` | None | `plugins/agentic-engineering-skills/licenses/mattpocock-skills-LICENSE` | Review: plan pressure-test |
| `graphify` | None | `plugins/agentic-engineering-skills/licenses/Graphify-Labs-graphify-LICENSE`; `plugins/agentic-engineering-skills/licenses/Graphify-Labs-graphify-LICENSE-MIT`; `plugins/agentic-engineering-skills/licenses/Graphify-Labs-graphify-NOTICE` | Understand: persistent codebase knowledge graph |
| `graphify-start` | None | `LICENSE` | Understand: route codebase questions through project Graphify protocol |
| `handoff` | None | `plugins/agentic-engineering-skills/licenses/mattpocock-skills-4ae2317-LICENSE` | Plan: save a concise resumable handoff |
| `orchestrating-gemini-workers` | None | `LICENSE` | Implement: independent bounded file-writing with sandboxed Gemini workers |
| `how-to-use-codex` | None | `LICENSE` | Plan: Codex prompt and model guidance |
| `claude-implement` | None | `LICENSE` | Implement: Claude Code only; copy from `claude-skills/claude-implement/` |
| `codex-implement` | None | `LICENSE` | Implement: Codex bounded packets and clean-room review |
| `coordinating-implementation-programs` | `sequential-task-orchestrator` | `LICENSE` | Implement: coordinate approved plans and dependencies |
| `impeccable` | None | `plugins/agentic-engineering-skills/licenses/pbakaus-impeccable-LICENSE`; `plugins/agentic-engineering-skills/licenses/pbakaus-impeccable-NOTICE` | Design: frontend craft and critique |
| `improve-codebase-architecture` | `codebase-design` | `plugins/agentic-engineering-skills/licenses/mattpocock-skills-LICENSE` | Design: architecture audit |
| `learn-codebase` | None | `plugins/agentic-engineering-skills/licenses/thedotmack-claude-mem-LICENSE`; `plugins/agentic-engineering-skills/licenses/thedotmack-claude-mem-NOTICE` | Understand: repository priming |
| `marketing-screenshots` | None | `LICENSE` | Design: capture and inspect real product UI for marketing assets |
| `master-orchestrator` | None | `LICENSE` | Understand: coordinate a dynamic non-implementation graph, filtered reports, decisions and design contracts |
| `mdx-to-html` | None | `LICENSE` | Verify: create a standalone MDX review artifact |
| `sequential-task-orchestrator` | `test-driven-development` | `LICENSE` | Implement: strictly ordered execution and per-task review |
| `retro` | `writing-for-agents` | `plugins/agentic-engineering-skills/licenses/mattpocock-skills-4ae2317-LICENSE` | Review: reflect on a coding session |
| `setup-goal` | None | `LICENSE` | Plan: outcome runbook and approved native Goal setup |
| `setup-harness-evaluation` | None | `LICENSE` | Verify: independent harness runs for manual evaluation |
| `setup-workflow-comparison` | None | `LICENSE` | Verify: independent workflow variants for manual evaluation |
| `simplify` | None | `LICENSE` | Review: behavior-preserving code cleanup |
| `test-driven-development` | None | `plugins/agentic-engineering-skills/licenses/obra-superpowers-LICENSE` | Verify: red-green-refactor |
| `to-spec` | None | `plugins/agentic-engineering-skills/licenses/mattpocock-skills-LICENSE` | Plan: standalone specification |
| `ui-ux-pro-max` | None | `plugins/agentic-engineering-skills/licenses/nextlevelbuilder-ui-ux-pro-max-LICENSE` | Design: searchable UI/UX intelligence |
| `wayfinder` | None | `plugins/agentic-engineering-skills/licenses/mattpocock-skills-LICENSE` | Plan: large-work map |
| `writing-for-agents` | None | `LICENSE` | Design: agent-facing document writing |
| `writing-plans` | None | `plugins/agentic-engineering-skills/licenses/obra-superpowers-LICENSE` | Plan: executable tasks |

## Conditional prerequisites

The lock records unconditional skill dependencies only. For these branches, also install:

- `wayfinder`: install `grilling` and `domain-modeling` when charting a map, resolving a Grilling ticket, or unsure which discussion skills apply.
- `graphify-start`: if no project-specific Graphify protocol exists, install `graphify` for the default route.
- `improve-codebase-architecture`: install `grilling` when a candidate is selected; install `domain-modeling` when no terminology source exists or decisions crystallise.
- `sequential-task-orchestrator`: use an implementation skill with bounded worker mode, such as `codex-implement` on Codex or `claude-implement` on Claude Code. This also applies when invoked through `coordinating-implementation-programs`.

## Additional installation notes

For Impeccable, also retain `plugins/agentic-engineering-skills/licenses/pbakaus-impeccable-ADAPTATIONS-NOTICE` and `plugins/agentic-engineering-skills/licenses/ehmo-platform-design-skills-LICENSE` for the MIT-derived iOS and Android references; their attribution is preserved in the upstream NOTICE.

`Dependencies` lists bundled skill dependencies only. Runtime tools are separate: `marketing-screenshots` uses app-provided `@playwright/test` and Chromium without auto-installing them; `orchestrating-gemini-workers` needs installed `dsh`, a compatible Gemini adapter/model, and a supported sandbox/approval preset. Its `run-worker.ps1` template assumes PowerShell and Windows app-data paths; adapt it for the target host. If tooling or a compatible shell is unavailable, report the run blocked; do not substitute a runner or model or widen permissions. `mdx-to-html` has no runtime package dependency; Mermaid rendering is optional and falls back to readable source plus a visible note.

`deslopping-cleanup` documents optional external specialist routes, not lock-declared dependencies. Its directory includes a portable skill-local copy of the repository MIT `LICENSE`; retain that copy when selectively redistributing the skill. See [dependencies and publication review](deslopping-cleanup.md) for route availability and fallbacks.

Implementation role attachments do not register native agents or create CLI session profiles. For `codex-implement`, configure minimal `$CODEX_HOME/<name>.config.toml` layers for `planner`, `spec-aware-tester`, `clean-room-reviewer` (Sol/xhigh) and `worker` (Sol/high). For `claude-implement`, launch each role and retry in a fresh generic session with its explicit model and effort, complete role attachment and permitted inputs. Tester and reviewer sessions restrict built-in tools and disable unlisted MCP servers. Named global agent profiles are not required. Consult each implementation skill for its routing and verification requirements.

The shared `skills/` directory contains 35 skills. Claude Code additionally scans `claude-skills/` declared in its manifest; that directory contains only `claude-implement`. Codex does not declare or scan it.

After copying, preserve flat layout `<skills-root>/<name>/SKILL.md`. Re-run host discovery. For provenance meaning see [provenance](provenance.md); for modification rules see [customization](customization.md).
