---
name: orchestrating-gemini-workers
description: Use when a coding task can be split into small, independently-specifiable file-writing subtasks and you want to delegate each to a sandboxed headless LLM worker (e.g. gemini via dsh) instead of writing every file yourself — especially across a long series of similar subtasks (extractors, one-screen-at-a-time ports, repetitive refactors) where you want to stay the reviewer, not the typist.
---

# Orchestrating Gemini Workers

Controller specifies/reviews; sandboxed headless worker writes one small, independently specified unit. Worker sees no conversation: brief must contain all needed context. Use for repetitive file tasks with independently derived, checkable acceptance criteria and fast objective checks. Architecture/exploration decisions, unclear criteria or context that cannot fit a self-contained brief stay with controller.

The historical source-project `example-log.md` is intentionally omitted: its task IDs, model names, and run outcomes are project-specific evidence, not portable validation for new tasks. No run results are claimed here.

## Setup and launch

Within authorized project scope, adapt these shipped templates:

| Source | Destination / adaptation |
|---|---|
| [run-worker.ps1](templates/run-worker.ps1) | `orchestration/run-worker.ps1`; adapt paths. |
| [base.yml](templates/dsh/base.yml) | `orchestration/dsh/base.yml`; sandbox/approval overlay. |
| [model-example.yml](templates/dsh/model-example.yml) | `orchestration/dsh/model-<id>.yml`; real installed model/adapter fields. |
| [AGENTS.md.template](templates/AGENTS.md.template) | `<workspace>/AGENTS.md`; forbidden files, technical constraints, comment language. |
| [BRIEF.template.md](templates/BRIEF.template.md) | `orchestration/briefs/<name>.md`; one per task. |

Worker `cwd` is workspace root. Copy needed source/reference material into it before launch and remove temporary copies afterward; exclude them from shipped build. Verify installed `dsh`/adapter, selected overlays, preset and sandbox behavior; templates do not prove tool availability or read confinement. `base.yml` sets `workspace-write`, root `process.cwd()`, approval `never`, and matching `workspace-auto` preset. Do not silently widen permissions.

If `dsh`, a compatible Gemini adapter/model, or the required sandbox/approval preset is unavailable, stop before dispatch and report the missing prerequisite. Do not substitute another runner or model, widen permissions, or claim a run started.

```powershell
.\orchestration\run-worker.ps1 -Model 37 -Brief G25 -AutoApprove
```

`-Model` selects `model-<id>.yml`. `-Brief` reads `orchestration/briefs/<name>.md`, creates an exclusive temporary `BRIEF-<run-id>.md` in the sandbox, sends only the instruction to read it, and removes its own copy when the run closes. Keep brief in a file: PowerShell interpolation corrupts backticks/`${...}`. Each run retains its transcript as `orchestration/reports/<brief>-<model>-<run-id>.log` and reports its path; the launcher propagates the worker exit code.

`-AutoApprove` selects `base.yml` for non-interactive execution. Without it launcher selects `probe.yml`, which is not shipped; supply an authorized compatible overlay or stop. Interactive approval cannot be answered in headless mode. Confirm exact sandbox/approval pair is registered, rather than bypassing a denied policy.

## Brief contract

Tell worker to read project `AGENTS.md` first. Include:

1. Exact allowed paths at top under **FILES YOU WRITE** (`FILE CHE SCRIVI` in shipped template). Any other written file voids entire task. Explicitly name any incidental SVG/JSON/log output exempted from that list.
2. Prohibitions: no build/package commands, configuration edits, browser or dev-server; controller owns those.
3. Self-contained format, numbers, names and source/reference context; preserve existing comments when needed.
4. Numeric/checkable acceptance criteria derived independently by controller, not accepted from brief's own claims.
5. Fix failed criteria; reporting failure alone does not finish task. Unverifiable values become `TODO` and are flagged under `DATI NON RICAVATI`/`DUBBI`; never estimate.
6. Exact final `=== REPORT ===` block required by template, listing files written, checks/results, underived data and doubts.

## Controller review gates

After every worker, apply in order:

1. **Scope:** compare before/after tree or hashes. Only allowed files/exempt outputs may differ; catch stray generated artifacts such as compiled `.js` beside `.ts`.
2. **Static check:** project's fast typecheck/build check.
3. **Tests/verification:** suite remains fully green.
4. **Real visual/functional check:** exercise actual output. UI/game surfaces require opening/using them; correct numbers can still produce invisible UI. For other tasks, verify whether gate 3 fully covers functional behavior before considering gate 4 redundant.

Controller retains brief writing, independent criteria, scope decisions, small review corrections and fixing its own spec errors. If independent data supports worker against brief, correct brief assumption instead of forcing wrong output. Worker chooses how within scope, never what task to do.

| Failure | Action |
|---|---|
| Comments disappear on full rewrite | Require preservation in brief or restore in review. |
| Large formatting-only diff | Compare ignoring CRLF/LF to isolate real changes; preserve intended endings. |
| Numbers pass, UI broken | Perform required real-use gate; task remains unfinished. |
| Headless approval blocks | Check selected overlay and matching preset; do not loosen denied policy. |
| Value cannot be derived | `TODO` plus report; no plausible invention. |
