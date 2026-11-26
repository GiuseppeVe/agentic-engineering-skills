# Plugin hooks

The plugin bundles the Caveman startup hooks and one PR-gate launcher. Hook configuration lives in [`hooks.json`](../plugins/agentic-engineering-skills/hooks/hooks.json); the startup script lives in the Caveman skill and the launcher in [`pr-gates.mjs`](../plugins/agentic-engineering-skills/hooks/pr-gates.mjs). Codex discovers `hooks/hooks.json` for plugin packages unless an OpenAI extension or compatibility manifest explicitly overrides hook discovery. Claude Code uses the same standard plugin hook file.

## Caveman context at startup

The plugin registers `SessionStart` and `SubagentStart` hooks. Each runs the bundled Caveman context script and supplies the skill's core instructions as additional context for the started session or subagent. Hook availability, approval and delivery depend on the host; the script does not start agents. If a project also registers Caveman startup hooks, both may inject context. Enable and trust the plugin hooks before use.

## PR gates launched when a pull request leaves draft

The plugin registers one `PostToolUse` hook, matched on the shell tools (`Bash|PowerShell`). It acts only when the command that just ran was a successful `gh pr create` without `--draft`, or a `gh pr ready` without `--undo`. Chained commands, quoted bodies, heredocs and a repository flag before the subcommand are read; whenever the command cannot be read with confidence, the hook does nothing.

What it does:

1. It finds the Git root above the working directory of the command.
2. If the root `package.json` has a script named `gates:pr`, it starts `npm run gates:pr -- --pr <number or URL>` in a detached process. The `--pr` argument is passed when the pull request is known from the command or its output and omitted otherwise.
3. It returns one line of additional context that tells the agent the gates were launched and where the log is. The output of the detached run goes to `~/.agentic/pr-gates/<repository>-<timestamp>-<pid>.log`.

Without a `gates:pr` script it prints nothing and writes nothing. The hook never blocks the tool call, always exits 0, and does not wait for the gates. It never verifies their outcome, repeats a reminder or writes a marker: the launch is not a result. What the gates are, where they run and whether they have anything to do for a given pull request is decided by the repository's script, not by the plugin. The reason for the hook is recorded in [decision record 0005](adr/0005-hook-che-lancia-i-gate-della-pr.md).

Limits: only pull requests opened or marked ready through the `gh` command line in a shell tool are seen. A pull request opened in the browser, through an API call or through an MCP tool does not trigger the launch. Each matching command launches once; the hook keeps no state between calls.

## No reminder or verifier hooks

Versions before 1.2.0 shipped reminders after PR creation and after merge, a PR preflight verifier with a billing fallback, and a `pr-skills` comment marker. They are removed and the launcher does not bring them back. The PR phase, the verification rules and the closing report are plain rules in the [`development-process`](../plugins/agentic-engineering-skills/skills/development-process/SKILL.md) skill: guidance, not enforcement. A repository's own git hooks, CI and branch protection remain its gates.

If an earlier local setup still registers a post-PR or post-merge hook, or expects the `pr-skills` marker, that setup belongs to the project or user configuration; this plugin does not change or disable it.

## Requirements and setup

The hook scripts require Node.js 22 or newer and work with Windows and Unix Node runtimes when the host can expand the plugin-root variable in the hook command. The launcher also needs `npm` on the `PATH` of the host session.

Codex requires the user to review and trust plugin-bundled hooks before running them. Enable the plugin, inspect and trust its hook definition in the host controls, then start a fresh session. A listed plugin or skill does not prove hooks are enabled or trusted. Claude Code also needs the plugin and its hook configuration enabled by the host.

## Local verification

From repository root, run the hook contract tests:

```text
node --test tests/plugin-hooks.test.mjs tests/caveman-startup.test.mjs tests/pr-gates-hook.test.mjs
```

They validate the hook manifest, run the startup script with JSON on stdin, check the command detection, and run the launcher against a temporary repository whose `gates:pr` script writes a marker file. Host trust, fresh-session discovery and the delivery of the launcher's context line still need to be checked in the installed Codex or Claude Code environment.
