# DeepSeek Vibe Execution Profile

Apply this profile only when a `plan-implement` slice is explicitly routed to
DeepSeek V4.1 Flash through Vibe.

The [slice contract](slice-contract.md), repository instructions, plan, and
specification remain authoritative. This profile tunes execution discipline
only.

## Execution bias

Start from the exact assigned slice and move toward implementation quickly.

- Read the assigned slice tasks, referenced `REQ-NNN` entries, and directly
  relevant repository instructions.
- Inspect only the entrypoints, consumers, contracts, and tests needed for that
  slice.
- Prefer one focused discovery pass. Extend it only when concrete evidence
  reveals missing context.
- Once the next safe action is clear, perform it. Do not repeatedly narrate,
  reconsider, or restate the plan.
- Implement the smallest coherent change that satisfies the slice.

Do not read the entire plan, specification, or repository for completeness.
Do not repeat searches or large file reads without new evidence.

## Failure handling

Follow concrete errors, diffs, and test results.

Try the smallest evidence-backed correction. Do not branch into speculative
alternatives or restart discovery from scratch.

When completion requires an unresolved decision, excluded scope, missing
authority, or unavailable prerequisite, return `partial` or `blocked` under
[slice contract](slice-contract.md) instead of broadening the investigation.

## Delegation

Implement directly by default.

Do not start subagents or nested reviewers unless `plan-implement` explicitly
authorized delegation for this slice.

## Stop and report

Stop as soon as the slice completion or blocking condition is met.

Return the lightweight handoff from [slice contract](slice-contract.md)
concisely. Report final facts and evidence, not an action diary. Do not
continue with cleanup, improvements, review, or adjacent slices after the
assigned slice is complete.
