# Release Evidence Report

Status: Task 10 native validation complete; Task 11 integrated finish gate pending.

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

## Native validation and discovery

| Host | Host version | Validation command | Exit code | Discovered skill names |
| --- | --- | --- | --- | --- |
| Codex | `codex-cli 0.139.0` | `plugin-creator/scripts/validate_plugin.py plugins/agentic-engineering-skills` | 0 | 19 skills; exact inventory below. |
| Claude Code | `2.1.201` | `claude plugin validate .` | 0 | 19 skills; exact inventory below. |

Claude smoke test used a fresh temporary `CLAUDE_CONFIG_DIR` and left normal configuration unchanged. Codex 0.139.0 ignored temporary `HOME` and `CODEX_HOME` during plugin operations; smoke installation therefore briefly used normal plugin state, then removed the test plugin and marketplace. Final normal `codex plugin list --json` returned an empty installed inventory. Both installed payloads exposed all 19 flat skill directories.

### Codex

`brainstorming`, `cavecrew`, `caveman`, `cleaning-repo-with-knip`, `codebase-design`, `domain-modeling`, `grill-me`, `grilling`, `implementing-plans`, `improve-codebase-architecture`, `learn-codebase`, `setup-matt-pocock-skills`, `swarm-orchestration`, `test-driven-development`, `to-spec`, `using-git-worktrees`, `wayfinder`, `writing-plans`, `writing-skills`

### Claude

`brainstorming`, `cavecrew`, `caveman`, `cleaning-repo-with-knip`, `codebase-design`, `domain-modeling`, `grill-me`, `grilling`, `implementing-plans`, `improve-codebase-architecture`, `learn-codebase`, `setup-matt-pocock-skills`, `swarm-orchestration`, `test-driven-development`, `to-spec`, `using-git-worktrees`, `wayfinder`, `writing-plans`, `writing-skills`

## Git actions

| Action | Status |
| --- | --- |
| Commit | not performed |
| Push | not performed |
| Pull request | not performed |
| Merge | not performed |
| Branch/worktree cleanup | not performed |
| Repository visibility change | not performed |
