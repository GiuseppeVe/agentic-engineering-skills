# DeepSeek Vibe execution profile

Apply this profile only when the whole `$task-implement` thread is routed to
DeepSeek V4.1 Flash through Vibe.

The main skill, repository instructions, plan, and specification remain
authoritative. This profile changes execution discipline only.

## Execution bias

Start from the exact assigned task and move toward implementation quickly.

- Read the assigned task, its referenced requirements, and directly relevant
  repository instructions.
- Inspect only the entrypoints, consumers, contracts, and tests needed for that
  task.
- Prefer one focused discovery pass. Extend it only when concrete evidence
  reveals missing context.
- Once the next safe action is clear, perform it. Do not repeatedly narrate,
  reconsider, or restate the plan.
- Implement the smallest coherent change that satisfies the task.

Do not read the entire plan, specification, or repository for completeness.
Do not repeat searches or large file reads without new evidence.

## Failure handling

Follow concrete errors, diffs, and test results.

Try the smallest evidence-backed correction. Do not branch into speculative
alternatives or restart discovery from scratch.

When completion requires an unresolved decision, excluded scope, missing
authority, or unavailable prerequisite, return `partial` or `blocked` under
the main skill instead of broadening the investigation.

## Delegation

Implement directly by default.

Do not start subagents or nested reviewers unless the parent explicitly
authorized delegation for this task.

## Stop and report

Stop as soon as the main skill's completion or blocking condition is met.

Return its shared result contract concisely. Report final facts and evidence,
not an action diary. Do not continue with cleanup, improvements, review, or
adjacent tasks after the assigned task is complete.
