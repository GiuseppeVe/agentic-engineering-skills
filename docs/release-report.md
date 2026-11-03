# Release verification report

## Caveman startup hook smoke: 2026-11-03

Both host runs used an isolated local fake API server and dummy credentials; no real model inference was performed.

- Claude Code 2.1.317 loaded the plugin with `--plugin-dir`. `SessionStart` and `SubagentStart` both exited 0, and Caveman context was observed.
- Codex 0.163.0 installed the plugin through an isolated marketplace. Both startup events were observed, including Caveman context delivered to the subagent. Hook trust was bypassed only for the test process.

These synthetic host checks do not establish persistent hook trust or normal approval through the host UI.

## Generic profile removal: 2026-11-03

The seven optional generic role contracts and their profile manifests have been removed. Skill-specific implementation attachments, host-native role configuration, and the Caveman startup hooks remain separate. A fresh isolated installation for each host confirmed the generic payload and profile manifest are absent while the relevant specialist attachments, 35 Codex skills and 36 Claude Code skills remain present. This checks packaging and inventory, not model invocation or live orchestration.

## Historical unified Caveman candidate: 2026-11-03

That candidate contained 36 skills: 35 for Codex and 36 for Claude Code. `caveman` follows the owner-supplied unified Alfe version; `setup-matt-pocock-skills` was removed along with active routes to it. The separate legacy skills named in the cleanup request were already absent. Existing third-party skill attribution remained in place. Generic profiles were subsequently removed.

Fresh isolated native installations and payload comparisons passed for Codex (`sha256:e6457b41007ed11334bda49d5c36ca7c3382e69b7ebcfcd4c1c797f216736db9`) and Claude Code (`sha256:ab5b08666c0304e6a97da80da8b42cdf35ec50d711ba3eec5f954756ac5560f3`). This evidence covers installation, inventory and bytes, not invocation or live hook behavior.

## Implementation program coordinator: 2026-11-03

The prior candidate contained 37 skills: 36 exposed to Codex and 37 to Claude Code. The added `coordinating-implementation-programs` is the byte-identical owner-supplied Alfe snapshot. A run requires a host capable of visible subordinate threads and remains subject to host instructions and user authorization.

Fresh isolated native plugin installs and payload comparisons passed on both hosts. Codex discovered 36 skills with payload hash `sha256:e053c863a50a70752438df729e3e4372fc57791bb12dc839f2a7112bd3cd0fd9`; Claude Code discovered 37 with `sha256:21b128a948ae0b2384705d310c04199b12f2440a24a7e199ab06d7e7055a76b5`. These checks establish installed bytes and discovery, not skill execution, live orchestration, or hook behavior.

## Long-task-run removal: 2026-11-02

The prior candidate contained 36 skills: 35 exposed to Codex and 36 to Claude
Code. `long-task-run` is absent from the package and both installed inventories.
`master-orchestrator` remains explicit-only on both hosts, and
`claude-implement` remains in the Claude-only skill root. This schema 3 native
receipt supersedes the earlier 36-Codex/37-Claude proof below.

Fresh isolated Windows installs used Codex CLI 0.163.0, Claude Code 2.1.296
and Node.js 24.16.0. Marketplace installation, plugin listing and both installed
payload verifiers exited 0. Source, snapshot and installed cache matched each
host's manifest-selected inventory and hash:

- Codex: 35 skills from `skills/`, hash
  `sha256:eb1a24dc0614603130b8c338e6b3ad50c0a12528e535077ebfe6b1cb6dd4ee0d`.
- Claude Code: 36 skills from `skills/` and `claude-skills/`, hash
  `sha256:6b625f12056e9714098ac4ff0c6a52c0def4abf09242d5abe029e46b3b204594`.
- Offline `codex debug prompt-input` showed exactly 17 unique implicit skills.
  All 18 explicit-only skills, including `master-orchestrator`, were omitted
  by policy. No duplicate entries appeared; neither `long-task-run` nor
  `claude-implement` appeared. `claude plugin details` listed the expected
  36 skills without `long-task-run`.
- All five hook files matched source, snapshot and both installed caches, with
  tree hash
  `sha256:e6aa673d676f0893449276ce8fd6321cfa184d8fa03b551aafdd313dc57dc310`.
  Hooks were not executed; this evidence does not establish live hook behavior
  or skill invocation in a model session.
- Raw command logs remain outside the public payload at
  `<user-temp>/aes3-native-no-longtask-20261102/logs`.

No Alfe checkout or normal agent profile was changed; no push, merge or
publication was performed.

## Master orchestrator packaging: 2026-11-02

This earlier candidate contained 37 skills: 36 exposed to Codex and 37 to Claude
Code. The added `master-orchestrator` is explicit-only on both hosts;
`claude-implement` remains in the Claude-only skill root. This schema 3 native
receipt supersedes the earlier 35-Codex/36-Claude proof below.

Fresh isolated Windows installs used Codex CLI 0.163.0, Claude Code 2.1.296
and Node.js 24.16.0. Marketplace installation, plugin listing and both installed
payload verifiers exited 0. Source, snapshot and installed cache matched each
host's manifest-selected inventory and hash:

- Codex: 36 skills from `skills/`, hash
  `sha256:1a0cf0918389cf38d60b7bf7bead8acd77f82307898bba52f1438016ebe95abd`.
- Claude Code: 37 skills from `skills/` and `claude-skills/`, hash
  `sha256:b4c1c522639d6a90bbeb65499cd483c6bd9e664b29e6ed711846f4ef651838e0`.
- Offline `codex debug prompt-input` showed exactly 17 unique implicit skills.
  All 19 explicit-only skills, including `master-orchestrator`, were omitted
  by policy. No duplicate skill entries or `claude-implement` appeared.
  `claude plugin details` listed all 37 expected skills.
- All five hook files matched source, snapshot and both installed caches, with
  tree hash
  `sha256:e6aa673d676f0893449276ce8fd6321cfa184d8fa03b551aafdd313dc57dc310`.
  Hooks were not executed; this evidence does not establish live hook behavior
  or skill invocation in a model session.
- Raw command logs remain outside the public payload at
  `<user-temp>/aes3-native-next-20261102/logs`.

No Alfe checkout or normal agent profile was changed; no push, merge or
publication was performed.

## Project skill-set alignment: 2026-11-02

This earlier candidate contained 36 skills: 35 exposed to Codex and 36 to Claude
Code, with `claude-implement` in the Claude-only skill root. This matches the union of the Alfe project
Codex and Claude Code skill directories. Eight obsolete plugin skills were
removed together with their manifest entries and stale routing. The retained
role contracts preserve their separate Cavecrew attribution and license.
Sequential orchestration now routes to the current host-specific Alfe workflow:
native Codex subagents or separate Codex/Claude CLI processes in Claude Code.

Fresh isolated Windows installs used Codex CLI 0.163.0, Claude Code 2.1.296
and Node.js 24.16.0. Marketplace installation, plugin listing and both installed
payload verifiers exited 0. The schema 3 receipt in
`manifests/native-discovery.json` records separate host inventories and hashes:

- Codex loads 35 skills from `skills/`; source, snapshot and installed cache
  match hash
  `sha256:3e984483a232bccea3bc59e5ec614518dffa79b7b76a8670c9885ef6c1cc935c`.
- Claude Code loads 36 skills from `skills/` and `claude-skills/`; source,
  snapshot and installed cache match hash
  `sha256:66207560e19213f2ff3f5fb49a5753416291f5c838ca0648c4364e5b90497bb0`.
- Offline native discovery through `codex debug prompt-input` showed exactly
  17 unique implicit skills, with all 18 explicit-only skills omitted by policy.
  It showed no duplicate orchestrator entries and no `claude-implement`.
  `claude plugin details` listed the expected 36 skills.
- All five hook files matched the source snapshot in both installed caches, with
  tree hash
  `sha256:e6aa673d676f0893449276ce8fd6321cfa184d8fa03b551aafdd313dc57dc310`.
  Hooks were not executed; this receipt does not establish live hook behavior
  or skill invocation in a model session.
- Raw command logs remain outside the public payload at
  `<user-temp>/aes3-native-final-20261102/logs`.

The earlier 44-skill native-install receipt below is historical and is
superseded by this schema 3 evidence. No Alfe checkout or normal agent profile
was changed; no push, merge or publication was performed.

## Version 1.1 alignment: 2026-11-02

This earlier candidate contained 44 skill directories, including an independent
`long-task-run` implementation explicitly enabled by the owner for this plugin.

- Fresh isolated Windows installs with Codex CLI 0.163.0 and Claude Code
  2.1.296 succeeded. Both installed caches contained all 44 skill directories
  and 628 files identical to the source snapshot, with common tree hash
  `sha256:eb26cc08f81c4022dda15ae4bd9f57cbc62ad5f6ade1c71644cf00042d0a4034`.
- Both caches contained the same five hook files as the source snapshot; their
  common tree hash was
  `sha256:e6aa673d676f0893449276ce8fd6321cfa184d8fa03b551aafdd313dc57dc310`.
  This proves installation fidelity, not live host discovery or hook execution.
- Pinned upstream and license checks passed; 22 patches reconstructed their
  target payloads using the generator's canonical line-ending rules.
- No changes were made to Alfe, its installed agents or the normal user profiles.
  No release, push or merge has been performed.

## Skill synchronization packaging: 2026-11-02

Payload: uncommitted changes based on `908a2ff`; no release commit or publish.
Five existing skills were updated: Caveman, Cleaning Repo with Knip, Codex
Implement, Test-Driven Development and Writing Plans. The directory hash is
`sha256:518d1b12d753240002368b75ab71122b59c5c6d0cff2dac9152246ca26673f62`.

- Separate isolated Windows host profiles used Codex CLI 0.163.0 and Claude
  Code 2.1.296 with Node.js 24.16.0. Official marketplace install/list commands
  completed successfully; Claude plugin validation also passed.
- Both actual installed plugin caches contain 29 skills and 299 files identical
  byte-for-byte to the uncommitted source snapshot. Normal user profiles and
  installed caches were not changed; no package cache was manually patched.
- This receipt establishes packaging fidelity, not skill invocation, role
  discovery, model access or authorization to publish. Before release, stamp
  original payloads to an actual commit and rerun the applicable gates.


## Role-routing synchronization: 2026-10-12

Payload commit: `ac0190a94d80dbd1fd51ae55dcce482661e06490`. Implementation
attachments use neutral planner, spec-aware-tester and clean-room-reviewer
names. Codex independent session profiles select Sol/xhigh for those roles and
Sol/high for bounded workers and both ordered retries. Claude callers select
Opus 5.5/medium for planning, Opus 5.5/high for semantic review, and
Sonnet 5.5/high for the existing bounded Terra packet-worker exception.
Sequential orchestration retains its single child slot, dedicated neutral
worker reference and acceptance gates; only calling-layer model selection changed.
Seven host-neutral base contracts, vendor payloads and retained licenses are
unchanged. The original stamping script records this reachable payload revision.
This section owned the native receipt at the time; subsequent sections supersede it.

- Official npm CLI versions were verified available and installed in a fresh
  isolated prefix: Codex 0.159.2 and Claude Code 2.1.296, on Node.js v26.7.0.
- Both real isolated marketplace installs contain 29 skills. Complete installed
  payload bytes match source hash
  `sha256:e73e4efcf35eb6a9e2c916ae44e8d663583763d65f5b5557a3261ef8d2d55884`.
  Both `verify:installed-native` commands exited 0 after actual cache inspection.
- Each host used separate fresh HOME, USERPROFILE, APPDATA, LOCALAPPDATA,
  CODEX_HOME and CLAUDE_CONFIG_DIR. No normal user-home CLI upgrade or manual
  package-cache edit occurred.
- Routing regressions were observed RED before implementation and GREEN after.
  `npm ci`, `npm test` (116/116), `verify:pack`, `verify:upstream`,
  `audit:public` and `git diff --check` passed. Logs remain outside public payload.
- This receipt proves packaging fidelity. It does not prove fresh-session skill
  invocation, account model access or effective per-role effort. Native agent
  definitions, CLI session profiles and Markdown attachments are separate;
  the bundle does not automatically register or create all of them.
- No push, pull request or merge was performed. Publication remains owner-controlled.

## Campaign phases synchronization: 2026-10-04

Payload commit: `d63ddb21d7c422ba91b5e95e73e9737f6b8be49b`, based on
`33e42a38642d2dcfdb380a263a9203cfc5fa509c`. The coordinator extends campaigns beyond
discovery with three referenced phases: branch integration (conflict inventory,
per-area decisions, plumbing-based merge commit, completeness and
semantic-conflict checks), operational residue (configuration, stored data, work
in flight, external artifacts and deployments, with a proposal and separate owner
approval for every action outside files) and workspace closure (inventory of
unique work including ignored files, secret-bearing files never archived in Git).
A delegation reference holds the canonical brief and return contract. Specialist
routing adds a route chooser, evidence blind spots, triangulation for removals, a
hidden-consumer checklist and history, non-code consumer and runtime evidence
routes. Two independent clean-room reviews preceded the payload. The lock records
this payload commit and directory SHA-256
`a536efb6733829769187c932ec7a4dfe9a068d8feb6bb291ba611aa2298bb177`.
This historical campaign receipt was superseded by the role-routing receipt
above; its payload revision and validation evidence remain the recorded snapshot.

- Fresh isolated WSL Ubuntu-24.04 installations using Node.js 22.23.1, Codex CLI
  0.141.0 and Claude Code 2.1.201 succeeded through official marketplace commands.
- Both actual native caches contain all 29 skills and match the source tree hash
  `sha256:b0357546f5b5f5dd8d85180875c0b5ef932e8f6b3d0fe66af189e157f0ba69db`.
  Both native verifiers (`verify-installed-native`, host cache scan) passed
  against the refreshed receipt in the same WSL process.
- Fresh HOME, npm global prefix, CODEX_HOME and CLAUDE_CONFIG_DIR isolated every
  native command. Normal profiles were untouched; no installed cache was patched.
- Repository checks were run against the final metadata commit; command/status
  logs remain outside the public payload. No fresh-session skill invocation or
  behavioral correctness claim is made here. Remote publication remains separate.

## Earlier disconnected-code safeguard synchronization: 2026-10-01

Payload commit: `723d93389aab2b5eb6ffd4ce5366d0e754d8c1fc`, based on
`4c7ca24f095d0f71424a20c41f38e3c990ead34e`. Disconnected code now requires
owner clarification about reference documents, their authority and currency,
and intended integration before cleanup classification. Missing documentation
can be resolved through explicit owner intent; unresolved intent defers the action.
Disconnected status alone does not establish legacy or dead code: a new feature
may still await integration. The documentation/intent context is recorded in
reports and handoffs. The lock records this payload commit and directory SHA-256
`ec0290324a8fbfc403e603f4271cb732d850bb3bcbbcc63c31c78cb915aad7ac`.
This historical disconnected-code safeguard receipt was superseded by the
campaign phases receipt above; its inventory and hash remain the recorded snapshot.

- Fresh isolated WSL Ubuntu-24.04 installations using Node.js 22.23.1, Codex CLI
  0.141.0 and Claude Code 2.1.201 succeeded through official marketplace commands.
- Both actual native caches contain all 29 skills and match the source tree hash
  `sha256:9e75692e38f2cdbf28bc1df71e67a00e91b18d88755f28fc27ebe34b40ca13dc`.
  `locateInstalledPayload` and `inspectInstalledPayload` observed installed roots,
  inventories and bytes before receipt refresh; both native verifiers then passed
  against that refreshed receipt in the same WSL process.
- Fresh HOME, npm global prefix, CODEX_HOME and CLAUDE_CONFIG_DIR isolated every
  native command. Normal profiles were untouched; no installed cache was patched.
- Existing CI commands are replayed separately against the final metadata commit
  in a full-history isolated WSL checkout. Durable command/status logs remain
  outside the public payload. No fresh-session skill invocation or behavioral
  correctness claim is made here. Remote publication remains separate.

## Earlier action rationale synchronization: 2026-10-01

Payload commit: `4d09e6571f3e77ba5d033510e91d8e79c4400fd7`, based on
`dd6cf156e117ad5ce162ccd925359036fd5f4c5b`. Before batch approval, each file
now gets a distinct action proposal with reasons, primary evidence and snapshot,
behavior/wiring impact and uncertainty. Incomplete proposals block approval and execution;
material changes require renewed approval. The lock
records this payload commit and directory SHA-256
`5cbec3ce61c4b3495e71ec734ed2ec5ba26bfac95720133765e1bf7b4853e8b2`.
This historical action rationale receipt was superseded by the disconnected-code
safeguard receipt; its inventory and hash remain the recorded snapshot.

- Fresh isolated WSL Ubuntu-24.04 installations using Node.js 22.23.1, Codex CLI
  0.141.0 and Claude Code 2.1.201 succeeded through official marketplace commands.
- Both actual native caches contain all 29 skills and match the source tree hash
  `sha256:50482b8953ebb5df63ef6dd3c0dc77d37b17865f95737ddb6f0d6b6c13ba6230`.
  Cache roots were located with `locateInstalledPayload` and inventories/bytes
  independently inspected with `inspectInstalledPayload` before receipt refresh.
- HOME, npm global prefix, CODEX_HOME and CLAUDE_CONFIG_DIR were fresh temporary
  directories. Normal profiles were untouched; no installed cache was patched.
- Existing CI commands are replayed separately against the final metadata commit
  with a full-history isolated WSL checkout. Durable command/status logs remain
  outside the public payload. This receipt itself makes no fresh-session skill
  invocation or behavioral correctness claim. Remote publication remains separate.

## Earlier campaign and controller synchronization: 2026-10-01

Payload commit: `8612af774e407e8800c0225d4b1b63983152a030`. The coordinator,
routing and report now distinguish campaigns, variable macro-runs, batches and
commits. The controller checks primary evidence before technical decisions,
commits and run handoffs. README and pipeline SVG describe the same hierarchy.
The lock records that payload commit and its directory SHA-256. This historical section records the campaign payload receipt; the disconnected-code
safeguard section was then current; the campaign phases section above owns the current receipt.

- Fresh isolated Codex 0.159.2 and Claude Code 2.1.260 installations contain 29
  skills with matching source/cache tree hash
  `sha256:8d884fb3757bac22be51723b32b501b6ce0fd1b404cc79fd45f25e3fad0f22af`.
- `verify-installed-native.mjs` passed for each actual cache against the refreshed
  receipt. Ordinary profiles and existing isolated validation profiles were not
  changed. No installed cache was patched by hand.
- Packaging verification, public audit and diff whitespace checks passed. The
  refreshed SVG rendered and was visually inspected. Workspace skill copies were
  compared byte-for-byte with the personal source and plugin payload.
- The PATH Codex binary was 0.149.0; only its version was probed. Installation used
  the explicitly selected app CLI 0.159.2, recorded in the receipt.
- No unit/behavioral tests, fresh-session invocation or independent agent review
  were performed for this synchronization. Earlier review applies to its recorded
  head, not automatically to this revision. Remote push/CI/merge remain separate.

## Earlier cleanup report-table correction: 2026-10-01

Payload correction commit: `96de8e9986bcbd73356399d994088526b0180cfa`.
The component-decision table now has seven delimiter cells matching its seven
header cells; no field or workflow changed. At that revision the lock recorded
this corrected payload commit and its directory SHA-256. This historical section
superseded the initial addition receipt before the later campaign update.

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
that payload commit and directory SHA-256 for the original coordinator. The correction receipt above superseded this payload hash; this earlier receipt
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

## Historical agent profile pack (removed)

This section records an earlier candidate, not the current payload. Seven host-neutral role contracts adapted Cavecrew at revision `0d95a81d35a9f2d123a5e9430d1cfc43d55f1bb0`.

| Profile | Local payload SHA-256 |
| --- | --- |
| `cleanup` | `c89857b025ad66f81146e68c0bd539cb5147c3ccb2409ad5b55ce04c454f2946` |
| `controller` | `62bf55276eb48d20df0e8352fa451b8cc7a18c82960637e15f1aeeb8f3123529` |
| `implementer` | `f7726498fc6c6ddbcd3d028187a3f9adab19e020c3094c532534228521a641ee` |
| `planner` | `92701ee8d015bf0d2483608f8d68d0c46620cf5c7373a801665c701050b7c4cf` |
| `researcher` | `8d2adaef824a0dc227fc8bb0a84c1642e2fe779abd26350f30d53a5d11bad3d9` |
| `reviewer` | `e88701f78b72f81afc55ea474758248ee2baab5f81f64daa54c46c413a592595` |
| `test-runner` | `a00f02866cea8c71a8ad77d15c971b07fb528945dd418080da107c4a76550a3a` |

Hashes covered the historical UTF-8 payloads and the manifest then in use. The generic profiles and their manifest are no longer distributed.

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

## Historical host boundary

The removed profiles were declarative role contracts, not an executable harness or native registrations. Host orchestration remains responsible for delegation, permissions, lifecycle, and result handling.

Publication completed through GitHub pull request #4; merge and implementation-branch cleanup are complete.

## Excluded skills

| Skill | Objective reason |
| --- | --- |
| _None_ | No requested skills excluded. |
