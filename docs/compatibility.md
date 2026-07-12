# Compatibility

Only hosts below are verified. Other Agent Skills hosts are unverified manual-adaptation targets; no compatibility claim is made for them.

| Host | Status | Payload |
| --- | --- | --- |
| `Codex` | Verified | `.codex-plugin/plugin.json` and flat Agent Skills directory |
| `Claude Code` | Verified | `.claude-plugin/plugin.json` and same flat Agent Skills directory |

Both hosts consume shared payload at `plugins/agentic-engineering-skills/`; this prevents host-specific skill drift. See [installation](../README.md#install) and [provenance](provenance.md).

Machine-verifiable native evidence lives in `manifests/native-discovery.json`: host versions, exact isolated install/discovery commands and exit codes, both 19-skill inventories, and deterministic installed-payload tree hash. `npm run verify:pack` requires this receipt by default and compares it with lock, flat directories, documentation inventory, and current payload bytes. `docs/release-report.md` remains human-readable supporting evidence. Smoke check: run `codex plugin list --available --json` or `claude plugin list`, start a fresh corresponding host session, then invoke an included skill such as `brainstorming`.

Validated versions: Codex CLI 0.141.0 and Claude Code 2.1.201. On Windows, set `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, `HOME`, `CODEX_HOME`, and `CLAUDE_CONFIG_DIR` together for every isolated host command. Codex 0.141.0 isolates marketplace and plugin state this way. Its model-visible skill catalogue still has a 2% context budget, so large ambient catalogues can truncate one-shot enumeration; use small fresh-session batches when checking named skills.
