# Compatibility

Only hosts below are verified. Other Agent Skills hosts are unverified manual-adaptation targets; no compatibility claim is made for them.

| Host | Status | Payload |
| --- | --- | --- |
| `Codex` | Verified | `.codex-plugin/plugin.json` and flat Agent Skills directory |
| `Claude Code` | Verified | `.claude-plugin/plugin.json` and same flat Agent Skills directory |

Both hosts consume shared payload at `plugins/agentic-engineering-skills/`; this prevents host-specific skill drift. See [installation](../README.md#install) and [provenance](provenance.md).

Machine-verifiable native evidence lives in schema-v2 `manifests/native-discovery.json`: host versions, exact isolated install/discovery commands and exit codes, and per-host installed inventories/tree hashes. `npm run verify:pack` checks tracked receipt against lock and source bytes. CI then performs fresh official marketplace installs, locates each installed plugin root from native CLI JSON or isolated host cache, and runs `npm run verify:installed-native` against actual installed bytes. Any host transform, missing `SKILL.md`, extra skill, or byte drift fails CI. Dynamic receipts stay in runner temp; normal host config is untouched. Supporting smoke commands: `codex plugin list --available --json` and `claude plugin list`; then start a fresh corresponding host session. `docs/release-report.md` remains supporting evidence.

Validated versions: Codex CLI 0.141.0 and Claude Code 2.1.201. On Windows, set `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, `HOME`, `CODEX_HOME`, and `CLAUDE_CONFIG_DIR` together for every isolated host command. Codex 0.141.0 isolates marketplace and plugin state this way. Its model-visible skill catalogue still has a 2% context budget, so large ambient catalogues can truncate one-shot enumeration; use small fresh-session batches when checking named skills.
