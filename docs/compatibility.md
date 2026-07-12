# Compatibility

Only hosts below are verified. Other Agent Skills hosts are unverified manual-adaptation targets; no compatibility claim is made for them.

| Host | Status | Payload |
| --- | --- | --- |
| `Codex` | Verified | `.codex-plugin/plugin.json` and flat Agent Skills directory |
| `Claude Code` | Verified | `.claude-plugin/plugin.json` and same flat Agent Skills directory |

Both hosts consume shared payload at `plugins/agentic-engineering-skills/`; this prevents host-specific skill drift. See [installation](../README.md#install) and [provenance](provenance.md).

Release validation records host versions, install/discovery commands, and discovered inventory in `docs/release-report.md`. Smoke check: run `codex plugin list --available --json` or `claude plugin list`, start a fresh corresponding host session, then invoke an included skill such as `brainstorming`.

Validated versions: Codex CLI 0.141.0 and Claude Code 2.1.201. On Windows, set `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, `HOME`, `CODEX_HOME`, and `CLAUDE_CONFIG_DIR` together for every isolated host command. Codex 0.141.0 isolates marketplace and plugin state this way. Its model-visible skill catalogue still has a 2% context budget, so large ambient catalogues can truncate one-shot enumeration; use small fresh-session batches when checking named skills.
