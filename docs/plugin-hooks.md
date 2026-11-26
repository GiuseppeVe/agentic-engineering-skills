# Plugin hooks

The plugin bundles the Caveman startup hooks and nothing else. Hook configuration lives in [`hooks.json`](../plugins/agentic-engineering-skills/hooks/hooks.json); the startup script lives in the Caveman skill. Codex discovers `hooks/hooks.json` for plugin packages unless an OpenAI extension or compatibility manifest explicitly overrides hook discovery. Claude Code uses the same standard plugin hook file.

## Caveman context at startup

The plugin registers `SessionStart` and `SubagentStart` hooks. Each runs the bundled Caveman context script and supplies the skill's core instructions as additional context for the started session or subagent. Hook availability, approval and delivery depend on the host; the script does not start agents. If a project also registers Caveman startup hooks, both may inject context. Enable and trust the plugin hooks before use.

## No process hooks

The plugin registers no `PostToolUse` hook. Versions before 1.2.0 shipped reminders after PR creation and after merge, a PR preflight verifier with a billing fallback, and a `pr-skills` comment marker. They are removed. The PR phase, the verification rules and the closing report are plain rules in the [`development-process`](../plugins/agentic-engineering-skills/skills/development-process/SKILL.md) skill: guidance, not enforcement. A repository's own git hooks and CI remain its gates.

If an earlier local setup still registers a post-PR or post-merge hook, or expects the `pr-skills` marker, that setup belongs to the project or user configuration; this plugin does not change or disable it.

## Requirements and setup

The startup script requires Node.js 22 or newer and works with Windows and Unix Node runtimes when the host can expand the plugin-root variable in the hook command.

Codex requires the user to review and trust plugin-bundled hooks before running them. Enable the plugin, inspect and trust its hook definition in the host controls, then start a fresh session. A listed plugin or skill does not prove hooks are enabled or trusted. Claude Code also needs the plugin and its hook configuration enabled by the host.

## Local verification

From repository root, run the hook contract tests:

```text
node --test tests/plugin-hooks.test.mjs tests/caveman-startup.test.mjs
```

They validate the hook manifest and run the startup script with JSON on stdin. Host trust and fresh-session discovery still need to be checked in the installed Codex or Claude Code environment.
