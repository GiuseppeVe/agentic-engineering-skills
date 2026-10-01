# Release verification report

## Cleanup report-table correction: 2026-10-01

Payload correction commit: `96de8e9986bcbd73356399d994088526b0180cfa`.
The component-decision table now has seven delimiter cells matching its seven
header cells; no field or workflow changed. The lock records this corrected
payload commit and its directory SHA-256. This section supersedes the earlier
addition receipt below for the current payload hash.

- Source and both actual native-installed caches contain 29 skills with tree hash
  `sha256:09b325db89bc166f46b58d4295d97498a0a37caa96069c2e363ce15342df41b1`.
- Codex CLI `plugin add` refreshed the isolated installed payload. Claude CLI
  `plugin update` reported the same version; uninstall/install in the isolated
  profile then refreshed it. No cache files were manually patched.
- `verify-installed-native.mjs` passed for both hosts against the refreshed receipt.
- `node scripts/verify-pack.mjs` passed for all 29 lock entries and the refreshed
  native receipt; `git diff --check` passed.
- Unit/behavioral tests and fresh-session invocation were not performed for this
  formatting correction. Remote publication remains subject to owner approval.

## Earlier Deslopping Cleanup addition receipt: 2026-10-01

Payload commit: `ddc76e94a40a648f152adec7138d505f7489b270`, based on
`c6f8a0af0019257437e7661a6fa59bdfea46d571`. At that revision the lock recorded
that payload commit and directory SHA-256 for the original coordinator. The newer
correction receipt above owns the current payload hash; this earlier receipt
preserves the initial addition's validation history.

- 29 included/requested skills, zero excluded. Only the new skill payload is added;
  existing vendor/adapted bytes and licenses are preserved.
- Isolated native installations succeeded with Codex 0.159.2 and Claude Code
  2.1.260. Both actual caches contain all 29 skills, including `deslopping-cleanup`,
  with source tree hash
  `sha256:c6784a12914e21fc14051d5e02c87831efd0d190205b6b1ff253236f5b453cac`.
- `verify-installed-native.mjs` passed for each host against the refreshed tracked
  receipt. Normal host configuration was not mutated. See the receipt for successful
  invocations and limitations; raw retry captures remain outside the public payload.
- Local payload hash validation passed for all 29 lock entries. The SVG pipeline
  was rendered and visually inspected; the referenced local documents exist.
- `node scripts/verify-pack.mjs`, `node scripts/audit-public.mjs` and
  `git diff --check` passed locally. Independent review found no metadata or
  pipeline inconsistency after the documented corrections.
- Earlier native verification against the old receipt failed because its inventory
  and tree hash were stale. Earlier Claude local-path registration attempts were
  refused; successful installation followed the CLI-required declaration in the
  temporary settings. No installed cache was manually patched to pass comparison.
- Unit/behavioral tests, fresh-session skill invocation and upstream re-download
  verification were not run for this addition. Publication and CI state are not
  claimed here; remote actions remain subject to owner approval.

Availability and scoped license assessment: [Deslopping Cleanup](deslopping-cleanup.md).

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

## Historical validation receipt

Latest clean-clone gate validated implementation SHA `5320e2a`.

| Scope | Command | Exit | Stable summary |
| --- | --- | ---: | --- |
| Focused profiles | `node --test tests/agent-profiles.test.mjs` | 0 | Windows: 21 total, 18 passed, 0 failed, 3 skipped because symlink creation returned `EPERM`; Linux WSL separately exercised all symlink cases with 21 of 21 passed. |
| Documentation | `node --test tests/docs-contract.test.mjs` | 0 | 9 passed; 0 failed or skipped. |
| Licensing | `node --test tests/license.test.mjs` | 0 | 4 passed; 0 failed or skipped. |
| Pack | `npm run verify:pack` | 0 | 7 installed profiles and 21 skills verified; 21 requested and included, 0 excluded; native receipt and documentation inventory verified for Codex and Claude. |
| Public surface | `npm run audit:public` | 0 | Public-release audit completed with no findings. |
| Full local suite | `npm test` | 0 | 100 total, 92 passed, 0 failed, 8 skipped because Windows disallowed fixture symlink creation. |
| Upstream | `npm run verify:upstream` | 0 | All 17 vendor and adapted upstream payloads verified against pinned sources; payload was restored byte-exact to base after clean-clone fidelity verification. |

## Host boundary

Profiles are declarative role contracts consumed by workflow skills, not an executable harness. They do not guarantee automatic native registration in Codex or Claude Code; host orchestration remains responsible for delegation, permissions, lifecycle, and result handling.

Publication completed through GitHub pull request #4; merge and implementation-branch cleanup are complete.

## Excluded skills

| Skill | Objective reason |
| --- | --- |
| _None_ | No requested skills excluded. |
