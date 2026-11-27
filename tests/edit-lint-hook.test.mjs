import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { extractEditedPaths, isIgnoredWithinRepo, resolveLintContext, run } from '../plugins/agentic-engineering-skills/hooks/edit-lint.mjs';

const hookScript = fileURLToPath(new URL('../plugins/agentic-engineering-skills/hooks/edit-lint.mjs', import.meta.url));

function makeTempRepo({ withConfig = true, withOxlint = true, mockDiagnostics = [] } = {}) {
  const base = mkdtempSync(path.join(os.tmpdir(), 'edit-lint-hook-'));
  const repo = path.join(base, 'repo');
  mkdirSync(path.join(repo, '.git'), { recursive: true });
  mkdirSync(path.join(repo, 'src'), { recursive: true });
  if (withConfig) {
    writeFileSync(path.join(repo, '.oxlintrc.json'), JSON.stringify({ categories: { correctness: 'error' } }));
  }
  if (withOxlint) {
    const binDir = path.join(repo, 'node_modules', 'oxlint', 'bin');
    mkdirSync(binDir, { recursive: true });
    writeFileSync(
      path.join(binDir, 'oxlint'),
      `process.stdout.write(JSON.stringify({ diagnostics: ${JSON.stringify(mockDiagnostics)} }));\nprocess.exitCode = ${mockDiagnostics.some(d => d.severity === 'error') ? 1 : 0};\n`,
    );
  }
  return { base, repo };
}

function cleanup(dir) {
  try { rmSync(dir, { recursive: true, force: true, maxRetries: 10, retryDelay: 50 }); } catch { /* ignore */ }
}

test('extractEditedPaths handles Claude Edit/Write/MultiEdit and Codex apply_patch', () => {
  const cwd = path.resolve('sample-workspace');
  assert.deepEqual(
    extractEditedPaths({ cwd, tool_input: { file_path: 'src/app.ts' } }),
    [path.resolve(cwd, 'src/app.ts')],
  );
  assert.deepEqual(
    extractEditedPaths({
      cwd,
      tool_input: {
        edits: [
          { file_path: 'src/a.tsx' },
          { file_path: 'docs/readme.md' },
          { file_path: 'src/a.tsx' },
        ],
      },
    }),
    [path.resolve(cwd, 'src/a.tsx')],
  );
  const worktreeRoot = path.resolve(cwd, '.worktrees', 'feat-a');
  assert.equal(isIgnoredWithinRepo(worktreeRoot, path.join(worktreeRoot, 'src', 'app.ts')), false);
  assert.equal(isIgnoredWithinRepo(worktreeRoot, path.join(worktreeRoot, 'node_modules', 'pkg', 'index.js')), true);
  assert.equal(isIgnoredWithinRepo(worktreeRoot, path.join(worktreeRoot, 'dist', 'index.js')), true);
  const patch = [
    '*** Begin Patch',
    '*** Update File: src/worker.mjs',
    '@@',
    '-const a = 1;',
    '+const a = 2;',
    '*** Add File: src/helper.js',
    '+export const ok = true;',
    '*** Delete File: src/old.ts',
    '*** End Patch',
  ].join('\n');
  assert.deepEqual(
    extractEditedPaths({ cwd, tool_input: { input: patch } }),
    [path.resolve(cwd, 'src/worker.mjs'), path.resolve(cwd, 'src/helper.js')],
  );
});

test('hook exits 0 silently when repo has no .oxlintrc.json or no local oxlint', () => {
  for (const opts of [{ withConfig: false, withOxlint: true }, { withConfig: true, withOxlint: false }]) {
    const { base, repo } = makeTempRepo(opts);
    try {
      const target = path.join(repo, 'src', 'index.ts');
      writeFileSync(target, 'export const x = 1;\n');
      assert.equal(resolveLintContext(target), null);
      const res = spawnSync(process.execPath, [hookScript], {
        input: JSON.stringify({ tool_name: 'Edit', cwd: repo, tool_input: { file_path: target } }),
        encoding: 'utf8',
      });
      assert.equal(res.status, 0, res.stderr);
      assert.equal(res.stdout, '');
    } finally {
      cleanup(base);
    }
  }
});

test('hook is silent on clean files and ignores warnings', () => {
  const { base, repo } = makeTempRepo({
    mockDiagnostics: [
      { severity: 'warning', code: 'eslint(no-unused-vars)', filename: 'src/index.ts', message: 'Unused var', labels: [{ span: { line: 1, column: 7 } }] },
    ],
  });
  try {
    const target = path.join(repo, 'src', 'index.ts');
    writeFileSync(target, 'const unused = 1;\n');
    const out = run(JSON.stringify({ tool_name: 'Write', cwd: repo, tool_input: { file_path: target } }));
    assert.equal(out, null);
  } finally {
    cleanup(base);
  }
});

test('hook reports blocking errors concisely, caps output at 8, never mutates the file, and exits 0', () => {
  const diagnostics = Array.from({ length: 10 }, (_, idx) => ({
    severity: 'error',
    code: 'eslint(no-empty)',
    filename: 'src/bad.ts',
    message: `Empty block ${idx + 1}`,
    labels: [{ span: { line: idx + 1, column: 3 } }],
  }));
  const { base, repo } = makeTempRepo({ mockDiagnostics: diagnostics });
  try {
    const target = path.join(repo, 'src', 'bad.ts');
    const original = 'try { run(); } catch {}\n';
    writeFileSync(target, original);
    const res = spawnSync(process.execPath, [hookScript], {
      input: JSON.stringify({ tool_name: 'Edit', cwd: repo, tool_input: { file_path: target } }),
      encoding: 'utf8',
    });
    assert.equal(res.status, 0, res.stderr);
    assert.equal(readFileSync(target, 'utf8'), original, 'hook must never mutate edited files');
    const parsed = JSON.parse(res.stdout);
    assert.equal(parsed.hookSpecificOutput.hookEventName, 'PostToolUse');
    const ctx = parsed.hookSpecificOutput.additionalContext;
    assert.match(ctx, /\[edit-lint\] 10 static errors/);
    assert.match(ctx, /src\/bad\.ts:1:3 \[eslint\(no-empty\)\] Empty block 1/);
    assert.match(ctx, /\.\.\.and 2 more/);
  } finally {
    cleanup(base);
  }
});

test('hook resolves local oxlint inside a subdirectory when .oxlintrc.json lives at repo root', () => {
  const { base, repo } = makeTempRepo({ withConfig: true, withOxlint: false });
  try {
    const toolsDir = path.join(repo, 'tools');
    const nestedBinDir = path.join(toolsDir, 'node_modules', 'oxlint', 'bin');
    mkdirSync(nestedBinDir, { recursive: true });
    writeFileSync(
      path.join(nestedBinDir, 'oxlint'),
      'process.stdout.write(JSON.stringify({ diagnostics: [] }));\n',
    );
    const target = path.join(toolsDir, 'runner.mjs');
    writeFileSync(target, 'export const ok = true;\n');
    const context = resolveLintContext(target);
    assert.ok(context, 'should locate oxlint under tools/node_modules when config is at repo root');
    assert.equal(context.configPath, path.join(repo, '.oxlintrc.json'));
    assert.equal(context.oxlintEntry, path.join(nestedBinDir, 'oxlint'));
  } finally {
    cleanup(base);
  }
});

test('hook ignores failed or malformed tool events', () => {
  assert.equal(run('not json'), null);
  assert.equal(run(JSON.stringify({ is_error: true, tool_input: { file_path: 'a.ts' } })), null);
  assert.equal(run(JSON.stringify({ tool_response: { exitCode: 1 }, tool_input: { file_path: 'a.ts' } })), null);
});
