# Plugin hooks

The plugin bundles one PR-gate launcher (ratchet lint and full gates) and one fast read-only static-analysis hook for edited JS/TS files. Both hosts use the standard [hook configuration](../plugins/agentic-engineering-skills/hooks/hooks.json) and run the [PR-gate launcher](../plugins/agentic-engineering-skills/hooks/pr-gates.mjs) and the [edit linter](../plugins/agentic-engineering-skills/hooks/edit-lint.mjs).

Invoke `Caveman` explicitly on either host. The plugin retired its startup hooks in v1.6.0.

## PR lint and gates launched when a pull request leaves draft

The plugin registers a `PostToolUse` hook matched on the shell tools (`Bash|PowerShell`). It acts only when the command that just ran was a successful `gh pr create` without `--draft`, or a `gh pr ready` without `--undo`. Chained commands, quoted bodies, heredocs and a repository flag before the subcommand are read; whenever the command cannot be read with confidence, the hook does nothing.

What it does:

1. It finds the Git root above the working directory of the command.
2. It reads two optional scripts from the root `package.json`: `gates:lint` and `gates:pr`. In one detached process it runs `npm run gates:lint` first, then `npm run gates:pr -- --pr <number or URL>`, each only if defined. The lint script takes no arguments: it lints the files the branch changed against its base, the way the repository's CI does. The `--pr` argument is passed to `gates:pr` when the pull request is known from the command or its output and omitted otherwise. A red lint does not skip the gates: each script runs and gets its own `exited with` line in the log.
3. It returns one line of additional context that tells the agent which scripts were launched and where the log is. The output of the detached run goes to `~/.agentic/pr-gates/<repository>-<timestamp>-<pid>.log`.

Without a `gates:lint` or `gates:pr` script it prints nothing and writes nothing. The hook never blocks the tool call, always exits 0, and does not wait for the gates. It never verifies their outcome, repeats a reminder or writes a marker: the launch is not a result. What the gates are, where they run and whether they have anything to do for a given pull request is decided by the repository's script, not by the plugin. The reason for the hook is recorded in [decision record 0005](adr/0005-hook-che-lancia-i-gate-della-pr.md).

Limits: only pull requests opened or marked ready through the `gh` command line in a shell tool are seen. A pull request opened in the browser, through an API call or through an MCP tool does not trigger the launch. Each matching command launches once; the hook keeps no state between calls.

## Fast static check on edited JS/TS files

The plugin registers a second `PostToolUse` hook matched on edit tools (`Edit|Write|MultiEdit|apply_patch`). When a tool call modifies one or more JS/TS files, [`edit-lint.mjs`](../plugins/agentic-engineering-skills/hooks/edit-lint.mjs) checks whether an ancestor up to the Git root contains `.oxlintrc.json` and a local `node_modules/oxlint/bin/oxlint`.

What it does:

1. Without both `.oxlintrc.json` and a local `oxlint` installation, it prints nothing and exits 0.
2. Otherwise it runs Oxlint in fast syntactic read-only mode (`--format json --quiet`, no `--type-aware`, no `--fix`) on only the edited files.
3. If there are zero blocking errors, it prints nothing; if errors are found, it returns a concise `additionalContext` list (up to 8 `file:line:col [rule] message` items) so the agent can fix them immediately before committing.

The hook never blocks, never edits files, keeps no state, and does not replace repository git hooks or CI gates (which run full `--type-aware` analysis). Shared presets live in [`standards/static-analysis/`](../standards/static-analysis/README.md) and the decision is recorded in [decision record 0006](adr/0006-analisi-statica-condivisa-e-hook-su-modifica.md).

## No reminder or verifier hooks

Versions before 1.2.0 shipped reminders after PR creation and after merge, a PR preflight verifier with a billing fallback, and a `pr-skills` comment marker. They are removed and the current hooks do not bring them back. The PR phase, the verification rules and the closing report are plain rules in the [`development-process`](../plugins/agentic-engineering-skills/skills/development-process/SKILL.md) skill: guidance, not enforcement. A repository's own git hooks, CI and branch protection remain its gates.

If an earlier local setup still registers a post-PR or post-merge hook, or expects the `pr-skills` marker, that setup belongs to the project or user configuration; this plugin does not change or disable it.

## Requirements and setup

The hook requires Node.js 22 or newer and work with Windows and Unix Node runtimes. Both hosts replace `${CLAUDE_PLUGIN_ROOT}` in the hook command with the installed plugin folder before running it: Claude Code runs the command through Git Bash on Windows, and Codex 0.172.0 substitutes the text and runs it as `powershell.exe -NoProfile -Command <command>`. The launcher also needs `npm` on the `PATH` of the host session.

On Windows the launcher starts the detached run through a short-lived PowerShell `Start-Process`, not directly. Under the PowerShell that Codex uses, a child started directly inherits the hook's output pipe; Codex then waits for the whole gates run, kills it at the hook timeout and reports `PostToolUse Failed`. `Start-Process` passes no handles, so the hook completes in a few seconds and the gates keep running after it and after the session ends. Starting PowerShell costs one to four seconds, which is why the launcher's timeout is 30 seconds.

Codex requires the user to review and trust plugin-bundled hooks before running them. Enable the plugin, inspect and trust its hook definition in the host controls, then start a fresh session. A listed plugin or skill does not prove hooks are enabled or trusted. Claude Code also needs the plugin and its hook configuration enabled by the host.

## Local verification

From repository root, run the hook contract tests:

```text
node --test tests/plugin-hooks.test.mjs tests/pr-gates-hook.test.mjs tests/edit-lint-hook.test.mjs
```

They validate the hook manifest, check command detection, run the PR-gate launcher against temporary repositories whose `gates:lint` and `gates:pr` scripts write marker files (lint first, gates after a red lint), and run the edit-lint hook against temporary repositories with clean and failing JS/TS files. Host trust, fresh-session discovery and the delivery of hook context lines still need to be checked in the installed Codex or Claude Code environment.
