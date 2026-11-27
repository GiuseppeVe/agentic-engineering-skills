# Release verification report

## Formal verification skills (`statechart` and formal verification lifecycle) and ADR 0009: 2026-11-27

Adds three explicit-invocation skills adapted from pinned `cursor/plugins@b7b93c36be9bcc36a74db438e0fd385d660bc559` (`pstack`, MIT): `statechart` (TLA+/TLC model checking and Mermaid statechart reporting, packaged with its 33 runtime files and excluding the 377 internal upstream test corpus fixtures), `create-formal-verification-skill`, and `maintain-formal-verification-skill`. Records ADR 0009 authorizing project-local formal-verification skills inside product repositories as a narrow exception to ADR 0001, ADR 0002, and ADR 0007 while keeping process skills plugin-only, and adds concise live-verification hygiene rules (doctor-before-drive, owned-process cleanup preserving proof artifacts, and observed dry-run verification) to `development-process/references/daily-workflow.md`.

The payload holds 31 skills for both hosts and 508 files. Upstream hashes, MIT license bytes, and adaptation patches (`manifests/patches/statechart.patch`, `manifests/patches/create-formal-verification-skill.patch`, `manifests/patches/maintain-formal-verification-skill.patch`) were generated and verified against the pinned upstream commit. Payload hashes in `manifests/native-discovery.json` were refreshed to Codex `sha256:76bcac733ebcfe6755fa46f2ea69184814a417058cc4c21124b715b505a10ace`, Claude Code `sha256:486aace51ec165990c956c9286a7c3052efdb9891d0408f63fe2f82dced5ac82`, and full tree `sha256:3ae240f155f6e47745d64f34bc492807dd4045e150a0935b002715862226811b`. Not yet verified in a live host session: first-run `mise`/Java/TLC execution of `statechart` and live invocation inside Codex and Claude Code.

## Shared static analysis presets and fast edit-lint hook: 2026-11-27

Adds canonical, noise-filtered static analysis presets under `standards/static-analysis/` (`base-ts-js.oxlintrc.json`, `react-web.oxlintrc.json`, `ruff.toml`, and `README.md`), records the architectural decision in `docs/adr/0006-analisi-statica-condivisa-e-hook-su-modifica.md`, and registers a second non-blocking `PostToolUse` hook (`plugins/agentic-engineering-skills/hooks/edit-lint.mjs`) matched on `Edit|Write|MultiEdit|apply_patch`. When a consumer repository configures `.oxlintrc.json` and installs local `oxlint` (at repo root or in an enclosing package directory), the hook runs fast syntactic read-only checks on only the edited JS/TS files and returns blocking errors as concise `additionalContext`; it stays silent otherwise, never edits files, and always exits 0.

The payload holds 28 skills for both hosts and 469 files (one added hook script over 1.6.0); no skill was added, removed, or modified, so `manifests/skills.lock.json` is unchanged. Payload hashes in `manifests/native-discovery.json` were refreshed to Codex `sha256:11b29eee42ac3d146ecfc3e78a1b30a81633bb97587ea4959aac22f5f0999570`, Claude Code `sha256:fecd55cbd29f9817fefa633d7eafdeae930c42da876e3786a2b018372731e801`, and full tree `sha256:db4a860f275cfd6c0bd8ffc99c916b49f824115120d7a6ab0b659382f9c3bb58`. Verified locally on Windows: `verify:pack`, `audit:public`, `claude plugin validate .`, preset parsing with Oxlint 1.95.0, and the contract/hook test suite. Not yet verified in a live host session: `PostToolUse` delivery on `Edit|Write|MultiEdit|apply_patch` inside Codex and Claude Code.

## v1.6.0 catalog and invocation parity

Both hosts now share 28 skills. The release retires `ask-matt`, `grill-me`, `ui-ux-pro-max`, `learn-codebase`, `orchestrating-gemini-workers`, and `graphify-start`, including unused patches and exclusive legal files. `graphify` takes over project protocol routing, queries existing graphs for codebase questions, checks findings in source, and loads the build pipeline on request.

`impeccable`, `deslopping-cleanup`, `caveman`, `cleaning-repo-with-knip`, `marketing-screenshots`, and `handoff` require explicit invocation on both hosts. Models can invoke `to-spec` and `graphify`. Caveman starts on explicit request. The PR-gate launcher remains the sole plugin hook.

`to-spec` makes key user scenarios optional. Wayfinder uses scoped research subagents and throwaway prototypes. Deslopping Cleanup points to native delegation, review and shared verification guidance. The Knip guide uses the repository's configured tooling. Only the three changed original skill payloads are stamped for this release.

Fresh isolated Windows installs on 2026-11-27 verified 28 skills and 468 files per host. Both Claude marketplace and plugin validations exited 0. Full plugin payload hash is `sha256:4e393d771320a46578aa93f7b90834d291d810476840160b01ca5e331a6c178b` on both hosts.

| Host | Version | Installed discovery tree |
| --- | --- | --- |
| Codex | `codex-cli 0.159.2` | `sha256:4aac6d83b9f041331e7e832906e92209a8809e1e301f008ec5223e75af308c86` |
| Claude Code | `2.1.330 (Claude Code)` | `sha256:423e4a0971daed95ba308a294ad2164f4429a11d54e62a1195518f76dbb6ec69` |

The [native discovery receipt](../manifests/native-discovery.json) records the install and listing commands, exit codes, inventories, and hashes. Evidence covers the host installations, manifest-selected skills, and installed bytes. Model invocation and live hook execution are outside this verification.

## Lightweight verification, English uniformity, and 2-level slice plan implementation: 2026-11-27

Version 1.5.0 refines the core verification and plan-execution workflow and records the architectural boundaries in factory decision records 0007 and 0008. `development-process` is rewritten in English and split into `references/daily-workflow.md` (mandate and Git boundaries, lightweight L1–L3 verification with anti-green-washing rules, PR phase, and closing report) and `references/program-orchestration.md` (multi-package delegation, plan and package lifecycle, and convergence limits), retiring `PROCESSO.md` and `ORCHESTRAZIONE.md`. `test-driven-development` adds a compact bug-fix red-reproduction loop, adds modern oracle selection guidance (unit, cross-package contract, property-based, and real-format/real-runtime) to `writing-good-tests.md`, fixes its broken `writing-for-agents` reference, and drops the overloaded generic task-reviewer role. `writing-plans` adds `**Risk:** standard | high` and optional `## Slice N:` grouping, aligns acceptance oracles with `test-driven-development`, removes hardcoded model presets and dangling skill references, and routes multi-task plans to `plan-implement`. `plan-implement` replaces `plan-orchestrator` and absorbs `task-implement` into a 2-level controller that delegates contiguous module tasks to persistent slice-implementer subagents, verifies deterministic L1–L3 checks, triggers clean-room host-native code review checkpoints on `risk: high` slices and shared contracts, commits accepted slices when authorized, keeps a lightweight slice handoff contract, and retains DeepSeek/Vibe routing references under `plan-implement/references/`. `coordinating-implementation-plans` (explicit-only on both hosts) and `master-orchestrator` are unified in English, `simplify` points correctness findings to host-native code review, and `retro` adds a deterministic-check promotion question and operational metrics.

The payload holds 34 skills for both hosts and 522 files (one skill fewer than 1.4.0 after absorbing `task-implement` into `plan-implement`, with cross-host `agents/openai.yaml` metadata added to the updated core skills). The `test-driven-development`, `writing-plans`, and `retro` patches were regenerated and round-trip verified against their pinned upstream hashes; `coordinating-implementation-plans`, `development-process`, `master-orchestrator`, `plan-implement`, and `simplify` are stamped at the payload commit while untouched original skills retain their earlier release commits.

Fresh isolated native installs on Windows (separate temporary host profiles with `HOME`, `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, `CODEX_HOME`, and `CLAUDE_CONFIG_DIR` redirected) passed `verify:installed-native` for Codex CLI 0.159.2 (`sha256:a27fbf7d4c72addc88f584f188daff207f4cba86835f52c57f6a21f8f9b7677d`) and Claude Code 2.1.330 (`sha256:e876f7b7d68a084bd62441f00af440a62c79d6a55542f910caa3c38440c2201f`). Both caches contained 34 skills and 522 files, with full payload hash `sha256:5a17c00feae601dbb92212bf6cd1b2d2a971e664f702f1f77b893363da3bcd04`. Both Claude marketplace and plugin validation exited 0. The checks covered installation, skill discovery, and installed bytes.

## PR-gate launcher on Codex for Windows: 2026-11-27

Version 1.4.1 fixes the PR-gate launcher under Codex on Windows. Codex 0.172.0 substitutes `${CLAUDE_PLUGIN_ROOT}` in the hook command, sets `CLAUDE_PLUGIN_ROOT`, `PLUGIN_ROOT`, `CLAUDE_PLUGIN_DATA` and `PLUGIN_DATA`, runs the command as `powershell.exe -NoProfile -Command <command>`, and waits until the hook's output pipe closes. The detached child that 1.4.0 started with `spawn()` inherited that pipe, so Codex waited for the whole `gates:pr` run, killed it at the 10-second timeout and printed `hook: PostToolUse Failed`; a gates run shorter than the timeout finished and hid the problem. The launcher now starts the run on Windows through a short-lived PowerShell `Start-Process`, which passes no handles, and falls back to `spawn()` only when PowerShell cannot be started. The `PostToolUse` timeout is 30 seconds because starting PowerShell takes one to four seconds on a loaded machine. No skill changed: the lock and the patches are unchanged, and the payload still holds 35 skills and 521 files.

Evidence on Windows with isolated host profiles (`HOME`, `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, `CODEX_HOME` and `CLAUDE_CONFIG_DIR` redirected), the plugin installed from the local marketplace and its hooks trusted through `hooks.state` entries taken from the app-server `hooks/list` hashes. With 1.4.0, `codex exec` running a fake `gh pr create` that prints a pull request URL, in a throwaway repository whose `gates:pr` script waits 20 seconds, printed `hook: PostToolUse Failed` and the gates were killed after they started. With 1.4.1 two such runs printed `hook: SessionStart Completed` and `hook: PostToolUse Completed`, and each gates run started with `--pr <url>` and finished 20 seconds later, after `codex exec` had exited. A new Windows test runs the hook the way Codex does and requires its output to close before a 20-second gate finishes; against 1.4.0 the output stayed open 21.8 seconds. The three hook commands, run through Git Bash with `CLAUDE_PLUGIN_ROOT` set as Claude Code does on Windows, completed and the gates run finished; `claude plugin validate .` and `claude plugin validate plugins/agentic-engineering-skills` exited 0. Fresh isolated installs passed `verify:installed-native` for Codex 0.172.0 (`sha256:84b61abd0407735782600ef328b0b94ce84d271745dd124d221966a8e75a752b`) and Claude Code 2.1.330 (`sha256:41bbd235a9b8cd99167dbbc025c4911c53bd7f7dd9b5830b261ae0458f4d9aef`).

Not verified: a live Claude Code session (the isolated profile has no login, so the hooks ran outside the host), `SubagentStart` inside Codex, Codex on Linux or macOS (the launcher there is unchanged), and the `SessionStart` failure reported from a non-isolated profile, which did not reproduce in the isolated one.

## Outcome-first specs, plans and briefs: 2026-11-27

Version 1.4.0 makes the expected outcome the first thing a reader meets in each workflow artifact. `to-spec` opens the spec with an `## Expected Outcome` section and checks it against the requirements during self-review. `writing-plans` keeps the architecture and stack lines in the plan header, follows it with `## Expected Outcome`, `## Requirements Inventory` and `## File Structure`, gives each task an `**Expected outcome:**` line, and checks that each task outcome follows from its REQs. Its task template is contract-based and holds no sample implementation code: each task names its files and ownership, its contracts and constraints, its expected outcome and the REQs it satisfies, and the plan gives exact code or data shapes only when they encode an agreed contract, a decision or a test case whose details affect correctness. `plan-orchestrator` opens the implementation brief and the clean-room review packet with the task outcome, asks the reviewer to rerun the final-state checks of its task, and requires the plan outcome to be verified on the integrated result before completion; its T3 DeepSeek routing reference passes the same brief. `task-implement` starts from the task outcome, derives it for older plans, and opens each worker brief with the packet outcome. `brainstorming` is reduced to resolving open decisions and now depends on `to-spec`. `how-to-use-codex` is retired from the shared plugin: nothing else in the payload referenced it.

The payload holds 35 skills for both hosts and 521 files, one fewer than 1.3.0. The `brainstorming`, `to-spec` and `writing-plans` patches were regenerated and their hashes recorded; `plan-orchestrator` and `task-implement` are stamped at the payload commit, and the other original skills keep their release commits.

Fresh isolated native installs on Windows (separate temporary host profiles with `HOME`, `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, `CODEX_HOME` and `CLAUDE_CONFIG_DIR` redirected) passed `verify:installed-native` for Codex 0.172.0 (`sha256:da1dc42cd368e050468ebc30b7ff6c798fb794ea1a7121adc72b8e8cc44cf64e`) and Claude Code 2.1.330 (`sha256:3b9aabc0c2a7b95b12ca74a6d48fbd1520700c887379c130fd9cef137538e115`), repeated after the `writing-plans` task template was restored; `claude plugin validate .` exited 0. This evidence covers installation, inventory and bytes. No model was invoked and the edited skills were not exercised in a live run.

## PR-gate launcher hook, repository-specific notes removed and factory decision records: 2026-11-26

Version 1.3.0 removes the notes tied to one repository from the general skills `development-process`, `coordinating-implementation-plans` and `plan-orchestrator`, and adds `docs/adr/` with the software-factory idea and its first five decision records. It also adds `scripts/worktrees.mjs` to `development-process`: a read-only inventory of the linked worktrees of one repository, wherever they live on disk, with `--remove-merged --yes` as the only writing mode (it removes merged clean worktrees with `git worktree remove`, never with `--force`, and deletes no branch). It was prepared as 1.2.1 and became 1.3.0 before any release, because it now adds behaviour: one `PostToolUse` hook, `hooks/pr-gates.mjs`. After a shell command opens a non-draft pull request or marks one ready, the hook starts the `gates:pr` script of the repository in a detached process, if the root `package.json` defines it, and returns one line naming the log file under `~/.agentic/pr-gates/`. It always exits 0 and neither waits nor verifies; decision record 0005 gives the reason. The payload holds 36 skills for both hosts and 522 files, two more than 1.2.0 (the worktree script and the hook script); no skill was added or removed and no adapted skill changed, so no patch was regenerated. Only `development-process` is stamped again, at the commit that added the hook and changed its PR-phase rule.

Fresh isolated native installs on Windows (separate temporary host profiles), repeated after the hook was added, passed `verify:installed-native` for Codex 0.171.0 (`sha256:ae16e8746d24ad8c8da0e71948133ce63a3ca7e605c396ca4d38203b5a2c19f4`) and Claude Code 2.1.330 (`sha256:ba6e7e9e64cc31a70d0058f7e4fa3b00faeea5506a1093ce76c3385a48bee03d`); `claude plugin validate .` exited 0. Both installed trees contain `hooks/hooks.json` and `hooks/pr-gates.mjs`. This evidence covers installation, inventory and bytes. No model was invoked, no hook was executed in a host session, and the edited skills were not exercised in a live run. The decision records are documentation: no check enforces them.

The worktree script is covered by `tests/worktrees.test.mjs` (classification, porcelain parsing, and both removal paths on temporary repositories) and was run once read-only against a real repository on Windows. Not verified: the removal mode on a real repository, the pull request lookup through `gh` under test (the tests use repositories without a remote, so the squash-merge path is covered only in the pure classifier), and any run on Linux or macOS outside CI.

The hook is covered by `tests/pr-gates-hook.test.mjs`: command detection (draft, undo, chained commands, heredoc bodies, PowerShell quoting, text that only mentions the command), the silent exit without a `gates:pr` script, and a real detached launch against a temporary repository whose `gates:pr` script writes a marker file, with and without `--pr`. These tests ran on Windows; Linux is covered by CI only. Not verified: the hook inside a live Codex or Claude Code session. That leaves open whether each host fires `PostToolUse` for the shell tool with the input shape the script expects, whether the returned context line reaches the agent, how Codex reports a failed command to the hook, and whether a host ends the detached run when the session closes. The first pull request opened from a session with this version installed is the first real evidence.

## Single-source process rules and PR hook removal: 2026-11-26

Version 1.2.0 adds `development-process` (general process rules and orchestration guide) and removes the `PostToolUse` PR hooks, the PR preflight verifier with its billing fallback, the `pr-skills` configuration and their tests. The payload holds 36 skills for both hosts and 520 files; `hooks/` holds only `hooks.json` with the Caveman startup hooks.

Fresh isolated native installs on Windows (separate temporary host profiles) passed `verify:installed-native` for Codex 0.171.0 (`sha256:33e2632d3b74da776c333fb38d2ee53558334201397e54ca90ebb1dd85edad90`) and Claude Code 2.1.330 (`sha256:fda929123bc3b2640218fd740cc0680ebf809ee80f5919d172ea8e0c24e591d4`); `claude plugin validate .` exited 0. This evidence covers installation, inventory and bytes. No model was invoked, no hook was executed in a host session, and the reworded orchestration skills were not exercised in a live run.

## Caveman startup hook smoke: 2026-11-03

Both host runs used an isolated local fake API server and dummy credentials; no real model inference was performed.

- Claude Code 2.1.317 loaded the plugin with `--plugin-dir`. `SessionStart` and `SubagentStart` both exited 0, and Caveman context was observed.
- Codex 0.163.0 installed the plugin through an isolated marketplace. Both startup events were observed, including Caveman context delivered to the subagent. Hook trust was bypassed only for the test process.

These synthetic host checks do not establish persistent hook trust or normal approval through the host UI.

## Generic profile removal: 2026-11-03

The seven optional generic role contracts and their profile manifests have been removed. Skill-specific implementation attachments, host-native role configuration, and the Caveman startup hooks remain separate. A fresh isolated installation for each host confirmed the generic payload and profile manifest are absent while the relevant specialist attachments, 35 Codex skills and 36 Claude Code skills remain present. This checks packaging and inventory, not model invocation or live orchestration.

## Historical unified Caveman candidate: 2026-11-03

That candidate contained 36 skills: 35 for Codex and 36 for Claude Code. `caveman` follows the owner-supplied unified version; `setup-matt-pocock-skills` was removed along with active routes to it. The separate legacy skills named in the cleanup request were already absent. Existing third-party skill attribution remained in place. Generic profiles were subsequently removed.

Fresh isolated native installations and payload comparisons passed for Codex (`sha256:e6457b41007ed11334bda49d5c36ca7c3382e69b7ebcfcd4c1c797f216736db9`) and Claude Code (`sha256:ab5b08666c0304e6a97da80da8b42cdf35ec50d711ba3eec5f954756ac5560f3`). This evidence covers installation, inventory and bytes, not invocation or live hook behavior.

## Implementation program coordinator: 2026-11-03

The prior candidate contained 37 skills: 36 exposed to Codex and 37 to Claude Code. The added `coordinating-implementation-programs` is the byte-identical owner-supplied snapshot. A run requires a host capable of visible subordinate threads and remains subject to host instructions and user authorization.

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

No source-project checkout or normal agent profile was changed; no push, merge or
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

No source-project checkout or normal agent profile was changed; no push, merge or
publication was performed.

## Project skill-set alignment: 2026-11-02

This earlier candidate contained 36 skills: 35 exposed to Codex and 36 to Claude
Code, with `claude-implement` in the Claude-only skill root. This matches the union of the source project
Codex and Claude Code skill directories. Eight obsolete plugin skills were
removed together with their manifest entries and stale routing. The retained
role contracts preserve their separate Cavecrew attribution and license.
Sequential orchestration now routes to the current host-specific workflow:
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
superseded by this schema 3 evidence. No source-project checkout or normal agent profile
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
- No changes were made to the source project, its installed agents or the normal user profiles.
  No release, push or merge has been performed.

## Skill synchronization packaging: 2026-11-02

Payload: uncommitted changes based on `historical-commit-redacted`; no release commit or publish.
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

Payload commit: `historical-commit-redacted`. Implementation
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

Payload commit: `historical-commit-redacted`, based on
`historical-commit-redacted`. The coordinator extends campaigns beyond
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

Payload commit: `historical-commit-redacted`, based on
`historical-commit-redacted`. Disconnected code now requires
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

Payload commit: `historical-commit-redacted`, based on
`historical-commit-redacted`. Before batch approval, each file
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

Payload commit: `historical-commit-redacted`. The coordinator,
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

Payload correction commit: `historical-commit-redacted`.
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

Payload commit: `historical-commit-redacted`, based on
`historical-commit-redacted`. At that revision the lock recorded
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

Latest clean-clone gate validated implementation SHA `historical-commit-redacted`.

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
