# Compatibility

Only hosts below are verified. Other Agent Skills hosts are unverified manual-adaptation targets; no compatibility claim is made for them.

| Host | Status | Payload |
| --- | --- | --- |
| `Codex` | Verified | `.codex-plugin/plugin.json` and flat Agent Skills directory |
| `Claude Code` | Verified | `.claude-plugin/plugin.json` and same flat Agent Skills directory |

Both hosts consume shared payload at `plugins/agentic-engineering-skills/`; this prevents host-specific skill drift. See [installation](../README.md#install) and [provenance](provenance.md).

Release validation records host versions, install/discovery commands, and discovered inventory in `docs/release-report.md`. Smoke check: run `codex plugin list --available --json` or `claude plugin list`, start a fresh corresponding host session, then invoke an included skill such as `brainstorming`.

Validated versions: Codex CLI 0.139.0 and Claude Code 2.1.201. Codex 0.139.0 does not honor temporary `HOME` or `CODEX_HOME` for plugin state; isolated automation must use an OS-level isolated user or clean up the temporary marketplace and plugin immediately after smoke testing.
