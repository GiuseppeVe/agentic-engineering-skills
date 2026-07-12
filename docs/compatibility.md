# Compatibility

Only hosts below are verified. Other Agent Skills hosts are unverified manual-adaptation targets; no compatibility claim is made for them.

| Host | Status | Payload |
| --- | --- | --- |
| `Codex` | Verified | `.codex-plugin/plugin.json` and flat Agent Skills directory |
| `Claude Code` | Verified | `.claude-plugin/plugin.json` and same flat Agent Skills directory |

Both hosts consume shared payload at `plugins/agentic-engineering-skills/`; this prevents host-specific skill drift. See [installation](../README.md#install) and [provenance](provenance.md).
