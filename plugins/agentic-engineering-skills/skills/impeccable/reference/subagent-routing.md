# Impeccable subagent routing

Use the available native subagent facility and start every role with a fresh context. Pass the input packet at the call site, including the full path to the platform-appropriate `scripts/impeccable` launcher from this skill. Do not change the user's agent configuration.

Claude Code discovers the plugin's agents as `agentic-engineering-skills:impeccable-asset-producer`, `agentic-engineering-skills:impeccable-documenter`, `agentic-engineering-skills:impeccable-finish-reviewer`, and `agentic-engineering-skills:impeccable-manual-edit-applier`. Dispatch the corresponding namespaced type when present.

Other hosts may offer registered specialists, including project or user agents. Use the actual role name in the available tool schema; do not guess its punctuation. Plugin skill files alone do not register Codex agents. When the named role is unavailable, spawn a generic subagent and include the `developer_instructions` text from the corresponding bundled TOML file in its prompt, together with the input packet:

- Asset producer: `../agents/impeccable_asset_producer.toml`.
- Documenter: `../agents/impeccable_documenter.toml`.
- Finish reviewer: `../agents/impeccable_finish_reviewer.toml`.
- Manual edit applier: `../agents/impeccable_manual_edit_applier.toml`.

Use a read-only restriction for the finish reviewer when the harness supports one. The generic fallback follows the same review contract, but cannot guarantee a model, tool restriction, or sandbox that the host cannot enforce; report any such limitation with the review. Use the host's actual fresh-context option, for example `fork_context: false` or `fork_turns: "none"`, as offered by the active tool.
