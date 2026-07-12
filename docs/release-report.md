# Release Evidence Report

Status: Task 11 integrated finish gate complete. Deterministic suite, native validators, release-tree checks, licensing, provenance, and public audit pass. Codex fresh-session exact discovery remains limited by ambient-skill catalogue truncation documented below.

## Included skills

19 included, 0 excluded. Inventory: `brainstorming`, `cavecrew`, `caveman`, `cleaning-repo-with-knip`, `codebase-design`, `domain-modeling`, `grill-me`, `grilling`, `implementing-plans`, `improve-codebase-architecture`, `learn-codebase`, `setup-matt-pocock-skills`, `swarm-orchestration`, `test-driven-development`, `to-spec`, `using-git-worktrees`, `wayfinder`, `writing-plans`, `writing-skills`.

## Excluded skills

None recorded. If source or legal verification excludes a requested skill, record skill name, failed gate, objective evidence, and approval status here. Excluded skills must be absent from both host packages.

## Source gates

| Command | Revision/source scope | Exit code | Result |
| --- | --- | --- | --- |
| `npm run verify:pack` | Local lock and payload | 0 | Verified 19 requested skills; 19 included, 0 excluded. |
| `npm run verify:upstream` | All pinned third-party sources | 0 | 7 vendor and 10 adapted sources verified at immutable revisions. |

## License gates

| Command | Scope | Exit code | Result |
| --- | --- | --- | --- |
| `node --test tests/license.test.mjs` | Root and retained third-party licenses/notices | 0 | Passed as part of 60-test suite. |

## Public audit

| Command | Scope | Exit code | Result |
| --- | --- | --- | --- |
| `npm run audit:public` | Git-tracked release surface | 0 | Zero findings. |

## Integrated finish gate

Run on 2026-07-12 from `codex/rebuild-skill-pack` at `6570ae1f50f27c13a4ed842f4f1666bb87f01531` before this report update.

| Command | Tool version | Exit code | Result |
| --- | --- | --- | --- |
| `npm ci` | Node `v18.19.1`; npm `9.2.0` | 0 | Installed lockfile exactly; 0 vulnerabilities. npm emitted expected `EBADENGINE` warning because package requires Node >=22 and this local WSL runner provides Node 18. CI uses Node 22. |
| `npm test` | Node `v18.19.1` | 0 | 60 tests passed; 0 failed, skipped, or cancelled. |
| `npm run verify:pack` | Node `v18.19.1` | 0 | Verified 19 requested skills: 19 included, 0 excluded. |
| `npm run verify:upstream` | Node `v18.19.1` | 0 | Verified all 7 vendor and 10 adapted pinned third-party entries. |
| `npm run audit:public` | Node `v18.19.1` | 0 | Zero findings. |
| `python3 $CODEX_HOME/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/agentic-engineering-skills` | Python `3.12.3`; PyYAML `6.0.1` | 0 | `Plugin validation passed`. Native Windows Python was also attempted but lacked PyYAML; same installed validator then passed under WSL Python. |
| `claude plugin validate .` | Claude Code `2.1.201` | 0 | Validation passed with one non-blocking marketplace-description warning. |
| `git diff --check` | Git | 0 | No whitespace errors. |
| `git status --short` | Git | 0 | Before report update, only untracked `node_modules/` produced by `npm ci`; removed after verification. No tracked change. |
| `git ls-files \| sort` | Git | 0 | Tracked inventory sorted successfully; legacy harness paths and forbidden artifacts absent. |

Protected checkout receipts, captured before and after Task 11 without mutation:

| Checkout | Branch | HEAD | Preserved status |
| --- | --- | --- | --- |
| Original | `main` | `7b3cb3d53c8ecd4655b7fdaa97cb8a88ef56c03a` | Preserved staged `docs/skill-provenance.md`, modified harness plan/spec, and untracked `.vscode/`. |
| Quarantine | `impl/agentic-harness-workflow` | `f9eeb9278db42d9a863137a523d5e2bf3dbe62ed` | Clean; branch and worktree retained. |
| Rebuild | `codex/rebuild-skill-pack` | `6570ae1f50f27c13a4ed842f4f1666bb87f01531` | Only this report changed after gates; npm output cleaned. |

## Native validation and discovery

Machine-verifiable Task 10 receipt: `manifests/native-discovery.json`. Default `npm run verify:pack` validates its structured host versions, exact commands/exits, both native 19-skill sets, and installed payload tree hash. Markdown below is supporting human-readable evidence, not release gate input.

| Host | Host version | Validation command | Exit code | Discovered skill names |
| --- | --- | --- | --- | --- |
| Codex | `codex-cli 0.141.0` | `plugin-creator/scripts/validate_plugin.py plugins/agentic-engineering-skills` | 0 | Installed plugin payload contains exact 19 below; fresh model session did not enumerate all 19 (limitation below). |
| Claude Code | `2.1.201` | `claude plugin validate .` | 0 | Fresh `claude -p` session discovered exact 19 below. |

Every isolated command set `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, `HOME`, `CODEX_HOME`, and `CLAUDE_CONFIG_DIR` to a fresh native-Windows profile before execution. Read-only copies of host credential files were placed in those profiles; no credential content was printed or recorded. Before/after normal-host snapshots had identical plugin IDs and marketplace names: Codex retained its 14 normal installed plugins and 3 marketplaces; Claude retained its 12 normal installed plugins and 4 marketplaces. Neither normal host acquired this test marketplace or plugin.

Exact isolated commands and receipts (`$P` = fresh profile, `$S` = native-Windows copy of this repository):

| Host | Command (all six environment variables set immediately before it) | Exit |
| --- | --- | --- |
| Codex | `codex --version` | 0 (`codex-cli 0.141.0`) |
| Codex | `codex plugin marketplace add $S --json` | 0 (`marketplaceName: agentic-engineering-skills`) |
| Codex | `codex plugin add agentic-engineering-skills@agentic-engineering-skills --json` | 0 (`version: 0.1.0`) |
| Codex | `codex plugin list --json` | 0 (isolated inventory contained only installed test plugin) |
| Codex | `codex exec --ephemeral --ignore-user-config --skip-git-repo-check -C $S '<discovery prompt>'` | 0, but one-shot response returned unrelated ambient names; batched candidate sessions also returned incomplete subsets while warning `Skill descriptions were shortened to fit the 2% skills context budget.` |
| Claude Code | `claude --version` | 0 (`2.1.201 (Claude Code)`) |
| Claude Code | `claude plugin marketplace add ./source --scope user` | 0 |
| Claude Code | `claude plugin install agentic-engineering-skills@agentic-engineering-skills --scope user` | 0 (`version: 0.1.0`) |
| Claude Code | `claude plugin list --json` | 0 (isolated inventory contained only installed test plugin) |
| Claude Code | `claude -p --no-session-persistence --setting-sources user '<discovery prompt>'` | 0; exact 19-name line below |

Codex marketplace installation itself is isolated and successful. However, Windows `codex exec` still exposed ambient skills outside isolated plugin state, and its 2% skill-description budget prevented an exact 19-name model-session receipt. Therefore Codex session discovery is not claimed complete; exact inventory below is payload/native-install inventory cross-checked by `npm run verify:pack`, not fabricated model output.

### Codex

`brainstorming`, `cavecrew`, `caveman`, `cleaning-repo-with-knip`, `codebase-design`, `domain-modeling`, `grill-me`, `grilling`, `implementing-plans`, `improve-codebase-architecture`, `learn-codebase`, `setup-matt-pocock-skills`, `swarm-orchestration`, `test-driven-development`, `to-spec`, `using-git-worktrees`, `wayfinder`, `writing-plans`, `writing-skills`

### Claude

`brainstorming`, `cavecrew`, `caveman`, `cleaning-repo-with-knip`, `codebase-design`, `domain-modeling`, `grill-me`, `grilling`, `implementing-plans`, `improve-codebase-architecture`, `learn-codebase`, `setup-matt-pocock-skills`, `swarm-orchestration`, `test-driven-development`, `to-spec`, `using-git-worktrees`, `wayfinder`, `writing-plans`, `writing-skills`

## Git actions

| Action | Status |
| --- | --- |
| Commit | performed locally: `2f72ecc`, `94f53d1`, `b321f34`, `25cff4a`, `d9ab968`, `4ca484c`, `782acad`, `c9e160e`, `41341ac`, `9bade44`, `46a201b`, `943f448`, `0b96c3e`, `d63e110`, `4e07fde`, `fa322bf`, `94159a0`, `af019c7`, `69b88a8`, `e1145b6`, `f2bb15b`, `df62260`, `90b92b1`, `ede7d40`, `4f9cac3`, `492dcd0`, `8a8f9c6`, `6570ae1` |
| Push | not performed |
| Pull request | not performed |
| Merge | not performed |
| Branch/worktree cleanup | not performed |
| Repository visibility change | not performed |
