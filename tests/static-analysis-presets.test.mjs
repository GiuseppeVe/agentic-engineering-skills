import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const standardsDir = path.join(root, 'standards', 'static-analysis');

test('base JS/TS Oxlint preset defines high-signal correctness rules and disables verified noisy rules', () => {
  const base = JSON.parse(readFileSync(path.join(standardsDir, 'base-ts-js.oxlintrc.json'), 'utf8'));
  assert.equal(base.categories.correctness, 'error');
  assert.equal(base.categories.suspicious, 'off');

  for (const requiredError of [
    'eqeqeq',
    'no-empty',
    'no-unsafe-finally',
    'no-unsafe-optional-chaining',
    'import/no-duplicates',
    'typescript/no-floating-promises',
    'typescript/no-misused-promises',
    'typescript/await-thenable',
    'typescript/no-base-to-string',
    'typescript/no-misused-spread',
    'typescript/require-array-sort-compare',
  ]) {
    const cfg = base.rules[requiredError];
    const level = Array.isArray(cfg) ? cfg[0] : cfg;
    assert.equal(level, 'error', `${requiredError} must be error`);
  }

  for (const disabledNoise of [
    'no-underscore-dangle',
    'no-unmodified-loop-condition',
    'typescript/unbound-method',
    'unicorn/no-thenable',
    'unicorn/no-array-fill-with-reference-type',
  ]) {
    assert.equal(base.rules[disabledNoise], 'off', `${disabledNoise} must stay off`);
  }
});

test('React web preset extends base and enables React 19 hooks and keyboard a11y rules', () => {
  const react = JSON.parse(readFileSync(path.join(standardsDir, 'react-web.oxlintrc.json'), 'utf8'));
  assert.deepEqual(react.extends, ['./base-ts-js.oxlintrc.json']);
  assert.equal(react.rules['react/react-in-jsx-scope'], 'off');
  for (const requiredError of [
    'react/rules-of-hooks',
    'react/set-state-in-effect',
    'react/refs',
    'react/immutability',
    'react/jsx-key',
    'jsx-a11y/click-events-have-key-events',
    'jsx-a11y/no-static-element-interactions',
    'jsx-a11y/interactive-supports-focus',
  ]) {
    assert.equal(react.rules[requiredError], 'error', `${requiredError} must be error`);
  }
});

test('Ruff Python preset targets real correctness rules', () => {
  const ruff = readFileSync(path.join(standardsDir, 'ruff.toml'), 'utf8');
  for (const code of ['"F"', '"B"', '"E711"', '"E712"', '"E722"', '"S110"', '"BLE001"']) {
    assert.ok(ruff.includes(code), `ruff.toml missing ${code}`);
  }
});
