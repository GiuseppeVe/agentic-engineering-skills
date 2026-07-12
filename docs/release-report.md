# Release verification report

## Agent profile pack

Seven host-neutral role contracts adapt Cavecrew at revision `0d95a81d35a9f2d123a5e9430d1cfc43d55f1bb0`.

| Profile | Local payload SHA-256 |
| --- | --- |
| `cleanup` | `c89857b025ad66f81146e68c0bd539cb5147c3ccb2409ad5b55ce04c454f2946` |
| `controller` | `62bf55276eb48d20df0e8352fa451b8cc7a18c82960637e15f1aeeb8f3123529` |
| `implementer` | `f7726498fc6c6ddbcd3d028187a3f9adab19e020c3094c532534228521a641ee` |
| `planner` | `92701ee8d015bf0d2483608f8d68d0c46620cf5c7373a801665c701050b7c4cf` |
| `researcher` | `8d2adaef824a0dc227fc8bb0a84c1642e2fe779abd26350f30d53a5d11bad3d9` |
| `reviewer` | `e88701f78b72f81afc55ea474758248ee2baab5f81f64daa54c46c413a592595` |
| `test-runner` | `a00f02866cea8c71a8ad77d15c971b07fb528945dd418080da107c4a76550a3a` |

Hashes cover exact UTF-8 bytes at paths recorded in `manifests/agent-profiles.json`. Provenance, MIT license, and notice references remain joined to existing Cavecrew attribution.

## Validation receipt

Latest clean-clone gate validated implementation SHA `90bf1d1`.

| Scope | Command | Exit | Stable summary |
| --- | --- | ---: | --- |
| Focused profiles | `node --test tests/agent-profiles.test.mjs` | 0 | Windows: 19 total, 18 passed, 0 failed, 1 skipped because symlink creation returned `EPERM`; Linux WSL separately exercised the symlink case with 19 of 19 passed. |
| Documentation | `node --test tests/docs-contract.test.mjs` | 0 | 9 passed; 0 failed or skipped. |
| Licensing | `node --test tests/license.test.mjs` | 0 | 4 passed; 0 failed or skipped. |
| Pack | `npm run verify:pack` | 0 | 7 installed profiles and 19 skills verified; 19 requested and included, 0 excluded; native receipt and documentation inventory verified for Codex and Claude. |
| Public surface | `npm run audit:public` | 0 | Public-release audit completed with no findings. |
| Full local suite | `npm test` | 0 | 98 total, 92 passed, 0 failed, 6 skipped because Windows disallowed fixture symlink creation. |
| Upstream | `npm run verify:upstream` | 0 | All 17 vendor and adapted upstream payloads verified against pinned sources; payload was restored byte-exact to base after clean-clone fidelity verification. |

## Host boundary

Profiles are declarative role contracts consumed by workflow skills, not an executable harness. They do not guarantee automatic native registration in Codex or Claude Code; host orchestration remains responsible for delegation, permissions, lifecycle, and result handling.

Publication remains deferred pending the main-plan approval gate: push, pull request creation, merge, branch cleanup, and public visibility have not occurred.

## Excluded skills

| Skill | Objective reason |
| --- | --- |
| _None_ | No requested skills excluded. |
