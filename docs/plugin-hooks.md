# Plugin hooks

The plugin bundles Caveman startup hooks and optional `PostToolUse` reminders for GitHub pull request workflows. Hook configuration lives in [`hooks.json`](../plugins/agentic-engineering-skills/hooks/hooks.json); PR scripts live beside it, and the startup script lives in the Caveman skill. Codex discovers `hooks/hooks.json` for plugin packages unless an OpenAI extension or compatibility manifest explicitly overrides hook discovery. Claude Code uses the same standard plugin hook file.

## Caveman context at startup

The plugin registers `SessionStart` and `SubagentStart` hooks. Each runs the bundled Caveman context script and supplies the skill's core instructions as additional context for the started session or subagent. Hook availability, approval and delivery depend on the host; the script does not start agents or execute the PR workflow. If a project also registers Caveman startup hooks, both may inject context. Enable and trust the plugin hooks before use.

## What hooks observe

The post-merge hook recognizes a plain `gh pr merge` command reported by the `Bash` tool only when it includes an explicit PR number or GitHub PR URL, for example `gh pr merge https://github.com/owner/repo/pull/12 --squash --delete-branch`. It ignores shell chains, substitutions, malformed commands, failed tool results, and explicit or URL-derived repository targets that differ from the current `gh repo view`. It then uses read-only `gh pr view` output to confirm the same PR is merged and has merge metadata. Only then does it add a reminder to verify the merge, apply the documented Graphify refresh where applicable, and preserve work safely during cleanup. See [`post-merge.mjs`](../plugins/agentic-engineering-skills/hooks/post-merge.mjs).

The hook emits no reminder for a merge without an explicit PR number or URL, even when its output mentions a PR. GitHub CLI does not guarantee that an identifier appears in non-interactive output, and the checked-out branch can change during branch deletion, including after an interactive prompt without `--delete-branch`. A later lookup by current branch could therefore identify a different PR. Use an explicit selector when a post-merge reminder is needed.

The post-PR hook recognizes successful `gh pr create` calls reported by `Bash`, plus MCP tool names matching `mcp__.*(create_pull_request|pull_request.*create|create_pr)`. In both cases, the tool result must contain a valid GitHub pull request URL. It optionally uses `gh pr view` to read the head branch and adds the configured steps from [`pr-skills.json`](../plugins/agentic-engineering-skills/hooks/pr-skills.json): after CI and an independent review on the current head are verified, Knip first, then Simplify, followed by final-head verification and the `pr-skills:v1` marker instructions. See [`post-pr.mjs`](../plugins/agentic-engineering-skills/hooks/post-pr.mjs).

Both hooks emit context after a tool call. They do not run skills, edit repository files, commit, push, comment, merge, or publish anything. The PR reminder explicitly leaves merge under the normal approval process. The post-merge hook emits no reminder if merge verification fails or returns incomplete merge metadata. The post-PR hook emits no reminder without a valid PR URL, but an unavailable `gh` command or failed head-branch lookup does not suppress an otherwise eligible PR reminder; the branch is simply omitted.

## PR workflow verification

The PR reminder directs the agent to run the bundled `hooks/pr-workflow-check.mjs` from the PR worktree before invoking either skill. Use the installed plugin path for `<checker>`:

```text
node <checker> preflight <GitHub-PR-URL> <review-record.json>
node <checker> marker <GitHub-PR-URL>
```

`preflight` requires a clean worktree at the current open PR head, every non-marker CI check observed passing, a non-empty list of expected CI check names derived from the project policy, all of those expected checks present, and a successful independent review recorded for that same head. It reads the PR head again after checking to catch an update during the verification. Pending, failed, absent, malformed or inaccessible evidence returns `NOT READY`. The exact check name `pr-skills-check` is excluded from this pre-skill check because it depends on the marker produced after the skills; it cannot count as the only CI check. A differently named dependent check is not automatically excluded.

Write the review record outside the non-ignored PR worktree files. Its `evidence` path is absolute or relative to the record, and `evidence_sha256` is the SHA-256 of the non-empty review report:

```json
{
  "head_sha": "<40-character PR head SHA>",
  "outcome": "passed",
  "independent": true,
  "required_checks": ["<required CI check name>"],
  "reviewer": "<independent reviewer or run identifier>",
  "evidence": "<path to review report>",
  "evidence_sha256": "<64-character SHA-256 of the report>"
}
```

Derive `required_checks` from the project’s actual CI policy or required-gate configuration; omit only the self-dependent marker check. The checker verifies that each declared name appears and passes but cannot establish that the declaration is complete. The record and report must reflect an actual independent review with no unresolved findings. The verifier checks their presence, hash and declared outcome; it cannot prove reviewer independence or judge the review itself. Never create a positive record for work not performed. Resolve failed reviews, obtain a new review for the current head, and rerun the preflight.

### Billing-block evidence

Some projects allow equivalent local or cloud checks when a GitHub billing or spending limit is confirmed. The installed hook's adjacent `billing-policies.json` is a trusted, separately maintained configuration; the package ships with an empty inventory. Each approved policy binds a repository and target branch to the complete workflow-file inventory and SHA-256 hashes, plus every applicable gate, its source workflow, exact commands, tool versions, services and coverage. Review this configuration against the project's policy and CI before use. The checker compares its workflow inventory and bytes with both PR base and head; a changed, missing or added workflow blocks verification until the trusted policy is reviewed and updated. For configured projects the declared required-check list must match the policy even on the hosted path. Unconfigured projects retain normal hosted checks but cannot use the billing fallback.

A review record may include `billing_fallback`: `kind: "github_billing"`, the exact `head_sha` and `pr_url`, `billing_block_confirmed: true`, `confirmed_by`, a list of `billing_blocked_checks`, and the path and SHA-256 of block evidence (`block_evidence`, `block_evidence_sha256`). `billing_proofs` supplies one `{ "run_id": 123, "job_id": 456, "check_run_id": 456, "attempt": 1 }` for each blocked gate. `gates` contains one local result per policy gate with the exact policy `name`, `commands`, `tool_versions`, `services` and `coverage`, plus `head_sha`, `outcome: "passed"`, `exit_code: 0`, `equivalent: true`, and a non-empty `evidence` file and its `evidence_sha256`. Paths resolve relative to the record; use actual evidence, never invented results.

An independent reviewer must assess the billing evidence and the complete local gate evidence. Add a `billing_review` object with the same `head_sha`, `outcome: "passed"`, `independent: true`, the `reviewer`, the review report `evidence` and `evidence_sha256`, and `verified_fallback_sha256`. Compute that last value as SHA-256 of UTF-8 `JSON.stringify(record.billing_fallback)` without whitespace or a trailing newline; it binds the independent review to the complete evidence inventory. A missing, altered or stale fallback review blocks the preflight.

For a policy gate marked `runtime_reference_required`, the local gate record must also contain `runtime_reference`: a `runner_image`, concrete matching `hosted_node_version` and `local_node_version` in `major.minor.patch` form, a `reference_url` to an official `actions/runner-images` release or repository file, and an `evidence` file with its `evidence_sha256`. The independent reviewer must verify that the reference actually corresponds to the GitHub image for the relevant run and that the local runtime matches it. If an unpinned hosted runtime cannot be established, the correct result remains `NOT READY`; the checker cannot establish image equivalence from the URL or an attestation alone.

The checker queries GitHub live for each proof. It checks the current run attempt, repository, branch and SHA, the job and check-run association, the GitHub Actions app, and a known explicit billing failure annotation on a job that never started. Passing policy jobs are also checked against GitHub job/check-run details on the same SHA. It rejects missing, pending, skipped, unrelated or unrecognized failures, stale attempts, missing policy gates and altered evidence. The PR head/base, worktree, evidence and policy are checked again before returning. If the proof is complete, it prints `READY LOCAL BILLING FALLBACK (hosted CI is not green)`; this allows the post-PR skill sequence under the project's fallback policy but does not claim hosted CI passed or bypass branch protection.

The local reports and independent review remain attestations: hashes prove their integrity, not that commands actually ran, versions/services were equivalent, or reviewers were independent. Verify these facts during the review. GitHub does not provide a stable structured billing-block flag; unknown annotation messages or blocked runs without a job/check-run remain `NOT READY`. A marker confirms only the recorded skill outcomes, not CI provenance.

After Knip and Simplify succeed, repeat CI, independent review and `preflight` on the final head after any push. If authorized to comment, record the marker on that head using `passed`, `applied` or `no_changes` for each skill. `marker` accepts only those outcomes in the latest trusted current-head marker and rejects failed, blocked, missing, stale or later malformed trusted markers. It rereads the head and comments before returning READY, so a later negative marker is not hidden by an earlier success. It verifies the marker, not the quality of the underlying work. The receiving repository's own gates still apply; a legacy `pr-skills-check` that merely checks non-empty fields does not replace this stricter verifier.

This verifier is a command the agent must actually run; the hook cannot force its execution or wake a finished session when CI completes. Resume or rerun the cycle when needed. No checker result authorizes a comment, push, merge or other external action.

## Requirements and setup

Hook scripts require Node.js 22 or newer. They call the GitHub CLI as `gh` from the process `PATH`; the post-merge hook needs working authentication and successful read-only lookups to verify the merge. The post-PR hook can emit a reminder from a valid PR URL even when `gh` or its optional branch lookup is unavailable. Its preflight and marker verifier require `gh`, authentication, and a working local Git installation. PR creation/merge itself must already have been performed by the host tool. The scripts pass argument arrays directly to `gh` and do not construct shell commands. This works with Windows and Unix Node runtimes when the host can expand the plugin-root variable in the hook command.

Codex requires the user to review and trust plugin-bundled hooks before running them. Enable the plugin, inspect and trust its hook definition in the host controls, then start a fresh session. A listed plugin or skill does not prove hooks are enabled or trusted. Claude Code also needs the plugin and its hook configuration enabled by the host.

## Coverage limits

These hooks are reminders, not enforcement. They only see successful calls represented as `PostToolUse` input that match the configured tool names and recognized command/result shapes. They do not observe every way a PR can be created or merged, and they cannot guarantee that suggested checks, skills, or marker steps happen. The PR hook deduplicates by pull request URL within a session when input includes `session_id`; post-merge reminders are not deduplicated. If session ID is absent or temporary storage is unavailable, PR reminders may repeat.

For PR deduplication, hooks use session and PR SHA-256 digests as names under a plugin-specific directory in the operating system's temporary directory. Marker files are empty, directory permissions are private where the platform supports POSIX modes, and a marker older than 14 days is treated as expired and recreated when that same session/PR pair is seen again. This is lazy expiration, not a background cleanup: unused expired markers remain until the operating system removes its temporary files. Raw session IDs and PR URLs are not written to that state. This is temporary runtime state, separate per session, not repository data.

Installing this plugin alongside an existing local source-project post-merge hook or Claude `pr-skills` mod can produce duplicate reminders for the same action. This plugin does not change or disable local source-project setup. Review the host's active project/user hooks and mods if duplicate context appears.

## Local verification

From repository root, run the unit and subprocess contract tests:

```text
node --test tests/plugin-hooks.test.mjs
```

Tests validate the hook manifest and exercise each entrypoint with JSON on stdin and a fake `gh` executable on `PATH`. They also run concurrent PR hook processes to verify per-session dedup and temp isolation; they do not contact GitHub or perform a merge. Host trust and fresh-session discovery still need to be checked in the installed Codex or Claude Code environment.
