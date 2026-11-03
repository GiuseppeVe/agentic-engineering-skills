---
name: setup-workflow-comparison
description: Set up independent runs of the same task with different workflows, models, or parameters for the user's manual evaluation.
disable-model-invocation: true
---

# Set up workflow comparison

Act as experiment orchestrator. Launch runs, collect artifacts, and describe observable outcome differences. The user evaluates quality and chooses preferences.

## Prepare

1. Freeze the exact initial task prompt and shared inputs. Record prompt/input hashes, repository revision when applicable, and shared instructions, tools, and permissions.
2. Record the requested variant matrix: approach, model, parameters, repetitions, concurrency, and run/time/spend limits. Resolve missing choices that affect the experiment; propose a small matrix when none was supplied. Vary only declared factors; label combined changes as bundled variants.
3. Discover the current runtime's independent-chat/session launcher and supported settings. Configure approaches through per-session configuration or isolated instruction files, keeping the initial task prompt byte-identical. If this separation is unsupported, mark that variant blocked and explain the limitation; changing the task prompt requires an explicit experiment redesign. Never silently substitute models or parameters.

## Launch and collect

- Start fresh independent threads/sessions, without inherited master conversation, other outcomes, or this orchestration skill. Pass the frozen prompt verbatim. Use native chat tools when available; otherwise inspect the installed Codex or Claude Code CLI help and start independent sessions. A model name written in a prompt does not configure the model. Report any unsupported launch capability rather than claiming execution.
- Give each run isolated writable state, including relevant databases, caches, and outputs. For repository writes use dedicated branches/worktrees at the same verified revision, following the target project's location/base rules. Shared read-only inputs are fine. Preserve existing permission controls.
- Save a run manifest before dispatch; update each run immediately with its thread/session ID, workspace, requested/effective configuration, timestamps, status, and artifact/log paths. Persist enough state to resume monitoring without launching duplicates.
- Monitor launched runs to completion, failure, budget stop, or required user action. Parallelize within agreed limits. Record blocked/incomplete runs and retries; retries consume the budget. Preserve isolated changes for inspection.

## Deliver

Save a concise report and manifest outside candidate changes. Include:

- Links to every thread/session and raw output, artifact, diff, and verification log.
- Per-run configuration and execution status; separate observed evidence from worker claims. Missing measurements, including cost/token usage, are unavailable, not invented.
- Side-by-side differences in delivered behavior, scope, files, verification evidence, unresolved items, and measured resources. Explain comparability limits and combined factors without attributing causality from one run.
- A blank field for the user's evaluation and preference.

Finish by handing results to the user. Quality scores, rankings, winner selection, merges, and follow-up improvements belong to subsequent user-directed work. Running this skill authorizes the experiment, not recursive experiment orchestration inside its workers.

Example: same frozen bug-fix prompt; model A/high versus model B/high, with all other recorded settings shared. Return artifacts and differences; user decides.
