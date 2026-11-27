import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const hookDirectory = path.join(root, 'plugins/agentic-engineering-skills/hooks');
const manifest = JSON.parse(readFileSync(path.join(hookDirectory, 'hooks.json'), 'utf8'));
test('plugin registers only PostToolUse hooks (PR-gate launcher and edit-lint hook)', () => {
  assert.deepEqual(Object.keys(manifest.hooks), ['PostToolUse']);
  assert.match(manifest.description, /repository PR gates/);
  assert.doesNotMatch(manifest.description, /reminder/i);
});

test('PostToolUse registers the PR-gate launcher and the fast edit-lint hook', () => {
  const groups = manifest.hooks.PostToolUse;
  assert.equal(groups.length, 2);

  const [prGatesGroup, editLintGroup] = groups;
  assert.equal(prGatesGroup.matcher, 'Bash|PowerShell');
  assert.equal(prGatesGroup.hooks.length, 1);
  assert.equal(prGatesGroup.hooks[0].type, 'command');
  assert.equal(prGatesGroup.hooks[0].command, 'node "${CLAUDE_PLUGIN_ROOT}/hooks/pr-gates.mjs"');
  // The launcher does not wait for the gates, but on Windows it starts them
  // through a short-lived PowerShell, which a slow machine can hold for seconds.
  assert.ok(
    prGatesGroup.hooks[0].timeout >= 20 && prGatesGroup.hooks[0].timeout <= 30,
    'the launcher must stay a short hook with room for the Windows start',
  );

  assert.equal(editLintGroup.matcher, 'Edit|Write|MultiEdit|apply_patch');
  assert.equal(editLintGroup.hooks.length, 1);
  assert.equal(editLintGroup.hooks[0].type, 'command');
  assert.equal(editLintGroup.hooks[0].command, 'node "${CLAUDE_PLUGIN_ROOT}/hooks/edit-lint.mjs"');
  assert.ok(editLintGroup.hooks[0].timeout <= 10, 'the edit-lint hook must stay short');
});

test('plugin ships no reminder, verifier or marker scripts', () => {
  assert.deepEqual(readdirSync(hookDirectory).sort(), ['edit-lint.mjs', 'hooks.json', 'pr-gates.mjs']);
  assert.doesNotMatch(JSON.stringify(manifest), /post-pr|post-merge|pr-skills|pr-workflow/);
  for (const script of ['pr-gates.mjs', 'edit-lint.mjs']) {
    const source = readFileSync(path.join(hookDirectory, script), 'utf8');
    assert.doesNotMatch(source, /pr-skills|pr-workflow|preflight|claimPrReminder|"decision"|process\.exit\(/);
  }
});
