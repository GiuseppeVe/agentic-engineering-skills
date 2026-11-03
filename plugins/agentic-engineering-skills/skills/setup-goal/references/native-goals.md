# Native Goal integration

Use the current host's exposed tools and their live schema/policies. These references guide integration with the existing native feature, not its reimplementation. Read the section matching the active host. Keep `runbook.md` as working context and include its path and a compact anti-drift clause in the native prompt: metrics track progress toward the agreed outcome, not separate objectives.

## Codex

Official reference: [Using Goals in Codex](https://developers.openai.com/cookbook/examples/codex/using_goals_in_codex).

Use the native Goal tools when exposed: inspect with `get_goal`, then activate with `create_goal` after final confirmation. Put the approved outcome, evidence checks, hard boundaries, limits, anti-drift instruction, and runbook read/update instruction in `objective`; include further contract detail as input capacity permits. Supply `token_budget` only for an explicitly requested token count. Do not replace an unfinished Goal. Obey the live native lifecycle contract, including who may pause/resume and when completion or blocked status is valid.

The CLI surface is `/goal <objective>`; `/goal` inspects status. Let the native implementation handle continuation, accounting, and stopping. Report actual creation acknowledgment/state, not merely the text of a command.

## Claude Code

Official reference: [Keep Claude working toward a goal](https://code.claude.com/docs/en/goal).

The native session feature is `/goal <condition>`; `/goal` inspects it. If the host exposes native `ProposeGoal`, use its current schema after final confirmation. Its shipped description in installed Claude Code 2.1.296 limits `condition` to 500 characters; the documented slash-command limit is 4,000. Follow the actual invoked interface's limit rather than sending the whole runbook blindly.

Keep the concise condition equivalent to the agreed outcome: verifiable end state and check, essential boundaries/limits, runbook path, and anti-drift clause. Show it before approval. If it cannot fit without losing essential meaning, resolve a tighter contract or use a supported native surface; never silently drop constraints. Use `ask_user: false` only when the live tool policy permits the user's explicit request/confirmation; otherwise retain its native approval dialog. Wait for native kickoff before claiming the Goal is active.

Claude's evaluator judges the conversation; it does not independently read `runbook.md`. Surface relevant measured results/check outputs in the transcript at checkpoints. A file link alone is not verification. Keep deadline/turn limits and progress visible without resetting them when resuming a runbook. Native clearing may mean success, impossibility, or an error; classify the real outcome separately.

## Missing activation access

If native tools are unavailable but the client supports `/goal`, provide the exact approved command for entry in this same session. Printing it is not activation. If native Goal is disabled/unavailable, explain the prerequisite and preserve the ready runbook; do not launch a new CLI session, change permission policies, or emulate the feature.
