import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const hookDirectory = path.join(root, 'plugins/agentic-engineering-skills/hooks');
const manifest = JSON.parse(readFileSync(path.join(hookDirectory, 'hooks.json'), 'utf8'));
test('plugin registers only the PR-gate launcher', () => {
  assert.deepEqual(Object.keys(manifest.hooks), ['PostToolUse']);
  assert.match(manifest.description, /repository PR gates/);
});

test('the only PostToolUse hook is the PR-gate launcher on the shell tools', () => {
  const groups = manifest.hooks.PostToolUse;
  assert.equal(groups.length, 1);
  assert.equal(groups[0].matcher, 'Bash|PowerShell');
  assert.equal(groups[0].hooks.length, 1);
  const [hook] = groups[0].hooks;
  assert.equal(hook.type, 'command');
  assert.equal(hook.command, 'node "${CLAUDE_PLUGIN_ROOT}/hooks/pr-gates.mjs"');
  // The launcher does not wait for the gates, but on Windows it starts them
  // through a short-lived PowerShell, which a slow machine can hold for seconds.
  assert.ok(hook.timeout >= 20 && hook.timeout <= 30, 'the launcher must stay a short hook with room for the Windows start');
});

test('plugin ships no reminder, verifier or marker scripts', () => {
  assert.deepEqual(readdirSync(hookDirectory).sort(), ['hooks.json', 'pr-gates.mjs']);
  assert.doesNotMatch(JSON.stringify(manifest), /post-pr|post-merge|pr-skills|pr-workflow/);
  const source = readFileSync(path.join(hookDirectory, 'pr-gates.mjs'), 'utf8');
  assert.doesNotMatch(source, /pr-skills|pr-workflow|preflight|claimPrReminder|"decision"|process\.exit\(/);
});
