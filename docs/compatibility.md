# Compatibility

Only hosts below are verified. Other Agent Skills hosts are unverified manual-adaptation targets; no compatibility claim is made for them.

| Host | Status | Payload |
| --- | --- | --- |
| `Codex` | Verified | `.codex-plugin/plugin.json` and flat Agent Skills directory |
| `Claude Code` | Verified | `.claude-plugin/plugin.json` and same flat Agent Skills directory |

Both hosts consume shared payload at `plugins/agentic-engineering-skills/`; this prevents host-specific skill drift. See [installation](../README.md#install) and [provenance](provenance.md).

Machine-verifiable native evidence lives in schema-v2 `manifests/native-discovery.json`: host versions, exact isolated install/discovery commands and exit codes, and per-host installed inventories/tree hashes. `npm run verify:pack` checks tracked receipt against lock and source bytes. CI then performs fresh official marketplace installs, locates each installed plugin root from native CLI JSON or isolated host cache, and runs `npm run verify:installed-native` against actual installed bytes. Any host transform, missing `SKILL.md`, extra skill, or byte drift fails CI. Dynamic receipts stay in runner temp; normal host config is untouched. Supporting smoke commands: `codex plugin list --available --json` and `claude plugin list`; then start a fresh corresponding host session. `docs/release-report.md` remains supporting evidence.

Validated versions: Codex CLI 0.141.0 and Claude Code 2.1.201. On Windows, set `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, `HOME`, `CODEX_HOME`, and `CLAUDE_CONFIG_DIR` together for every isolated host command. Codex 0.141.0 isolates marketplace and plugin state this way. Its model-visible skill catalogue still has a 2% context budget, so large ambient catalogues can truncate one-shot enumeration; use small fresh-session batches when checking named skills.

## Current action rationale receipt: 2026-10-01

The current tracked receipt records fresh isolated WSL Ubuntu-24.04 installs using
Node.js 22.23.1, Codex CLI 0.141.0 and Claude Code 2.1.201 at payload commit
`4d09e6571f3e77ba5d033510e91d8e79c4400fd7`. Both actual installed caches contain
29 skills with source-matching tree hash
`sha256:50482b8953ebb5df63ef6dd3c0dc77d37b17865f95737ddb6f0d6b6c13ba6230`.
Cache inventory and hashes prove native packaging fidelity; fresh-session skill
invocation was not performed. Fresh HOME, npm prefix, CODEX_HOME and
CLAUDE_CONFIG_DIR isolate every host command. Normal profiles were untouched.

## Historical cleanup addition receipt: 2026-10-01

The earlier Windows receipt at payload commit `8612af774e407e8800c0225d4b1b63983152a030`
recorded isolated local installation with Codex CLI
0.159.2 and Claude Code 2.1.260, and actual installed-cache inventories/hashes for
all 29 skills. Child-only Git configuration disables CRLF conversion for byte-exact
payload comparison. Claude required declaring the local directory marketplace
under `extraKnownMarketplaces` in the temporary user settings before installation.
Codex listed the installed plugin even though its `available` array was empty.
Neither result proves fresh-session invocation or behavioral correctness of the
new coordinator; those checks were not performed.
