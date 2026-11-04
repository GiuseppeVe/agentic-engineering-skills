import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

const pluginRoot = fileURLToPath(new URL('../plugins/agentic-engineering-skills/', import.meta.url)).split(path.sep).join('/');
const hooks = JSON.parse(readFileSync(path.join(pluginRoot, 'hooks/hooks.json'), 'utf8')).hooks;
for (const event of ['SessionStart', 'SubagentStart']) {
  test(`${event} loads Caveman instructions into the started context`, () => {
    const entries = hooks[event]?.flatMap(group => group.hooks) ?? [];
    const hook = entries.find(item => item.command.includes('caveman/scripts/context-hook.mjs'));
    assert.ok(hook, `missing Caveman hook for ${event}`);
    const match = /^node "\$\{CLAUDE_PLUGIN_ROOT\}\/([^"\r\n]+)" (SessionStart|SubagentStart)$/.exec(hook.command);
    assert.ok(match, `unexpected hook command: ${hook.command}`);
    assert.equal(match[2], event);
    const result = spawnSync(process.execPath, [path.join(pluginRoot, match[1]), event], { input: JSON.stringify({hook_event_name: event}), encoding:'utf8' });
    assert.equal(result.status, 0, result.stderr);
    const output = JSON.parse(result.stdout).hookSpecificOutput;
    assert.equal(output.hookEventName, event);
    assert.match(output.additionalContext, /Respond terse like smart caveman/);
    assert.match(output.additionalContext, /ACTIVE EVERY RESPONSE/);
    assert.doesNotMatch(output.additionalContext, /^---/);
  });
}
