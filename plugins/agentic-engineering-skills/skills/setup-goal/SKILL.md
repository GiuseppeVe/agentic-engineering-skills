---
name: setup-goal
description: Co-design a runbook from a fresh session's desired outcome, then activate the host's native Goal after the user approves the outcome, constraints, and progress metrics.
disable-model-invocation: true
---

# Design and launch a native Goal

Start with the user's desired outcome, not assumed conversation history. This skill prepares a native Goal run; the host's Goal mechanism owns continuation and lifecycle.

## Interactive design

Work in the user's language, one stage at a time. Offer short concrete proposals and ask one focused question at a time. Reuse information already supplied, including later-stage details, without repeating questions. Advance when the current section is agreed; do not invent a complete contract from an underspecified request.

1. **Outcome:** jointly refine what the user actually wants, the finish line, deliverable, and necessary context. Read applicable project instructions and narrowly relevant sources as needed. Treat assumptions as questions, not inherited decisions.
2. **Constraints:** agree scope, allowed actions, isolation/environment prerequisites, budget choices, stop conditions, and decisions reserved for the user. Identify enforceable versus best-effort limits. Consequential missing limits require a choice, including deliberately leaving them unset.
3. **Metrics:** agree the smallest set that reveals progress and the remaining outcome gap. Specify evidence, baseline or unknown baseline, useful checkpoints, and acceptance criteria versus progress indicators. Metrics guide the run toward the outcome; they never become separate tasks, activity quotas, or substitute goals.

## Write and confirm

Use [the runbook template](references/goal-brief.md) to write an actual `runbook.md` in the selected task workspace, respecting project isolation rules. Retain exactly three main sections: outcome, constraints, metrics. Preserve an existing file; establish whether it belongs to this run or choose another run-specific directory. Setup may write this artifact and prepare an authorized workspace, but does not execute the task or activate a Goal.

Prepare the native Goal condition from the agreed runbook within the tool's input limit. Preserve success criteria, hard constraints, stop limits, and the rule that metrics measure progress toward the outcome.

Show the saved path, completed runbook, exact native condition, and unresolved prerequisites. Once ready, ask for final confirmation to start this specific version. Section agreement and skill-creation approval are not launch confirmation. Material edits after confirmation require renewed approval.

## Native run

After confirmation, activate the session's native `/goal` through the available tool (`create_goal` in Codex; `ProposeGoal` in Claude Code). Preserve an unrelated existing Goal and verify native acknowledgment before claiming activation. Consult [host-specific details](references/native-goals.md) when needed. If neither native tools nor `/goal` are available, leave the approved runbook ready, report activation as blocked with the host prerequisite, and stop; do not create a custom loop, hook, scheduler, background agent, or substitute session.

During the native run, read `runbook.md` at start and after resumption/context compaction. At meaningful checkpoints and before yielding, update observed state, measured progress, evidence, consumed limits when measurable, blockers, and next outcome-directed action inside its existing sections. Preserve approved targets and boundaries; seek approval for material contract changes. Keep the record compact rather than logging every action.

Choose work from the remaining outcome gap. Completion requires actual outcome evidence and preserved constraints, not a progress score or merely an updated runbook. A limit, blocker, or native clearing event can end execution without achieving the outcome; record that distinction and follow native lifecycle rules.
