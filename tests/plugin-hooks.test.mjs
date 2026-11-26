import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const hookDirectory = path.join(root, 'plugins/agentic-engineering-skills/hooks');
const manifest = JSON.parse(readFileSync(path.join(hookDirectory, 'hooks.json'), 'utf8'));

test('plugin registers only the Caveman startup hooks', () => {
  assert.deepEqual(Object.keys(manifest.hooks).sort(), ['SessionStart', 'SubagentStart']);
  for (const [event, groups] of Object.entries(manifest.hooks)) {
    const commands = groups.flatMap(group => group.hooks);
    assert.equal(commands.length, 1, `${event} must register one hook`);
    assert.equal(commands[0].type, 'command');
    assert.equal(commands[0].command, `node "\${CLAUDE_PLUGIN_ROOT}/skills/caveman/scripts/context-hook.mjs" ${event}`);
  }
  assert.match(manifest.description, /Caveman startup context/);
  assert.doesNotMatch(manifest.description, /PR|reminder/i);
});

test('plugin ships no process hook scripts or PR verifier', () => {
  assert.deepEqual(readdirSync(hookDirectory), ['hooks.json']);
  assert.doesNotMatch(JSON.stringify(manifest), /PostToolUse|post-pr|post-merge|pr-skills|pr-workflow/);
});
