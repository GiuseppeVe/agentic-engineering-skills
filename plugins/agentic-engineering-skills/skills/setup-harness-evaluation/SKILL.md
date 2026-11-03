---
name: setup-harness-evaluation
description: Set up experiments with a specified agent harness and collect results for the user's manual evaluation, including repeat runs after harness changes.
disable-model-invocation: true
---

# Set up harness evaluation

Act as experiment orchestrator. Prepare representative cases, launch independent runs, and return inspectable results. The user evaluates the harness from those outcomes.

## Prepare

1. Identify the harness under test: development orchestration or an application agent system. Freeze its revision/configuration, including relevant instructions, skills, model settings, tools, permissions, and environment. Keep it unchanged throughout the batch.
2. Use supplied cases or propose a small representative set from actual tasks and known failures. For each case save exact prompt, input snapshot, intended deliverable, and evidence to collect. Human evaluation criteria are useful context, not authorization for agent grading.
3. Record run count/repetitions, concurrency, time/spend limits, and stop conditions. Resolve consequential missing choices before dispatch. Each case may have a different task; repetitions of a case use identical inputs and setup. Comparisons to an earlier harness version reuse the same cases and record intentional changes.
4. Check the current runtime's independent-chat/session launcher and supported configuration. Use native tools when available; otherwise inspect installed Codex or Claude Code CLI help for independent sessions. Verify the chosen runner can actually exercise the frozen harness. Record unsupported combinations as blocked; never silently substitute a model or parameter.

## Launch and collect

- Start each case/repetition in a fresh independent thread/session without master history or other outcomes. Workers receive the case and specified harness, not this experiment-orchestration skill. This prevents recursive test launching.
- Isolate writable state and external fixtures per run. Repository changes require dedicated branches/worktrees at the same verified revision, respecting the target project's base/location rules. Keep permission controls and external side effects within the experiment's authorization.
- Save a manifest before dispatch. Track case/repetition IDs, harness/input hashes, requested/effective configuration, workspace, thread/session IDs, timestamps, status, outputs, and evidence paths. Persist launch IDs immediately; resume monitoring rather than duplicating runs.
- Monitor every run until completion, failure, budget stop, or required user action. Keep blocked, failed, and incomplete cases visible. Count attempts against the agreed budget; preserve artifacts and logs for the user.

## Deliver and stop

Save a concise batch report and manifest outside candidate changes:

| Per case/run | Include |
| --- | --- |
| Setup | Frozen harness, prompt/input references, actual configuration |
| Result | Raw output, deliverable/diff, thread/session and artifact links |
| Evidence | Existing verification logs, observed facts versus worker claims |
| Execution | Status, blocker, attempts, measured time/usage or unavailable |
| Human evaluation | Blank feedback field |

Summarize delivered outputs, missing evidence, and coverage gaps. Completion is execution status, not a quality verdict. Preserve logs for later diagnosis without requiring the user to audit every step.

Hand results to the user and stop. Human feedback may start a separate diagnosis/change task; this invocation does not automatically grade results, choose harness changes, or modify the harness. After an authorized correction, a new invocation reruns the frozen cases with the new harness snapshot and reports factual before/after differences for the user's evaluation.

Example: launch one implementation case and one review case against harness H1; return both outcomes and evidence. After user feedback and a separately authorized H2 change, rerun those cases.
