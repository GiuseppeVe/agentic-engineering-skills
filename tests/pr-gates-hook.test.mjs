import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { classifyGhCommand, findPullRequestCommand, pullRequestEvent, splitCommands } from '../plugins/agentic-engineering-skills/hooks/pr-gates.mjs';

const hook = fileURLToPath(new URL('../plugins/agentic-engineering-skills/hooks/pr-gates.mjs', import.meta.url));
const pullUrl = 'https://github.com/acme/widgets/pull/12';
const action = (command, options) => findPullRequestCommand(command, options)?.action ?? null;

test('a non-draft gh pr create is detected', () => {
  for (const command of [
    'gh pr create',
    'gh pr create --fill',
    'gh pr new --fill',
    'gh pr create --title "Add gates" --body "Body"',
    "gh pr create -t 'Add gates' -b 'Body' -B main",
    'gh pr create --draft=false --fill',
    'gh -R acme/widgets pr create --fill',
    'gh --repo acme/widgets pr create --fill',
    'gh pr -R acme/widgets create --fill',
    'gh pr create --repo=acme/widgets --fill',
    'GH_PROMPT_DISABLED=1 gh pr create --fill',
    'gh.exe pr create --fill',
    '/usr/bin/gh pr create --fill',
    'gh pr create --fill 2>&1 | tail -n 1',
    'gh pr create --fill > out.txt',
    'gh pr create --body-file body.md --title x',
  ]) assert.equal(action(command), 'create', command);
});

test('flag values are never read as flags', () => {
  assert.equal(action('gh pr create --title "--draft" --body "-d"'), 'create');
  assert.equal(action('gh pr create -t "-d" -b "--web"'), 'create');
  assert.equal(action('gh pr create --title=--draft --fill'), 'create');
  assert.equal(action('gh pr create --title "run gh pr create --draft; then gh pr ready --undo"'), 'create');
});

test('draft, web, dry-run and help variants do nothing', () => {
  for (const command of [
    'gh pr create --draft',
    'gh pr create -d',
    'gh pr create --fill -d',
    'gh pr create -fd',
    'gh pr create -df',
    'gh pr create --draft=true',
    'gh pr create --title x --draft --body y',
    'gh -R acme/widgets pr create --draft',
    'gh pr create --web',
    'gh pr create -w',
    'gh pr create --dry-run',
    'gh pr create --help',
    'gh pr ready --undo',
    'gh pr ready 12 --undo',
    'gh pr ready --undo 12',
    'gh pr ready --help',
  ]) assert.equal(action(command), null, command);
});

test('gh pr ready is detected with its pull request reference', () => {
  assert.deepEqual(findPullRequestCommand('gh pr ready'), { action: 'ready', ref: null, directory: null });
  assert.equal(findPullRequestCommand('gh pr ready 12').ref, '12');
  assert.equal(findPullRequestCommand('gh pr ready "#12"').ref, '12');
  assert.equal(findPullRequestCommand(`gh pr ready ${pullUrl}`).ref, pullUrl);
  assert.equal(findPullRequestCommand('gh pr ready 12 -R acme/widgets').ref, '12');
  assert.equal(findPullRequestCommand('gh pr ready feature/branch').ref, null);
  assert.equal(findPullRequestCommand('gh pr ready feature/branch').action, 'ready');
});

test('chained commands are read one by one', () => {
  assert.equal(action('git push -u origin HEAD && gh pr create --fill'), 'create');
  assert.equal(action('git push; gh pr ready 12; echo done'), 'ready');
  assert.equal(action('git push\ngh pr create --fill\n'), 'create');
  assert.equal(action('gh pr create --draft --fill && gh pr ready'), 'ready');
  assert.equal(action('gh pr view 12 && gh pr checks 12'), null);
  assert.equal(action('gh pr create --draft --fill; gh pr view'), null);
  assert.deepEqual(findPullRequestCommand('cd ../other && gh pr create --fill'), { action: 'create', ref: null, directory: '../other' });
  assert.equal(findPullRequestCommand('cd /srv/work && cd repo && gh pr ready 3').directory, '/srv/work/repo');
  assert.equal(action('cd "$WORKTREE" && gh pr create --fill'), null, 'an unknown directory means an unknown repository');
});

test('bodies with substitutions and heredocs do not hide or fake the command', () => {
  const heredocBody = [
    'gh pr create --title "Add gates" --body "$(cat <<\'EOF\'',
    '## Summary',
    "It's ready (really); see `npm test` && gh pr create --draft",
    'EOF',
    ')"',
  ].join('\n');
  assert.equal(action(heredocBody), 'create');
  assert.equal(action(`${heredocBody} --draft`), null);
  const stdinBody = ['gh pr create --title x --body-file - <<EOF', 'text; gh pr ready --undo', 'EOF', 'echo done'].join('\n');
  assert.equal(action(stdinBody), 'create');
  assert.equal(action(['cat > notes.md <<EOF', 'gh pr create --fill', 'EOF'].join('\n')), null);
  assert.equal(action('gh pr create --title "$(git log -1 --format=%s)" --body "$BODY"'), 'create');
});

test('text that only mentions the command does nothing', () => {
  for (const command of [
    'echo "gh pr create"',
    "echo 'gh pr ready'",
    'echo gh pr create',
    'git commit -m "gh pr create --fill"',
    'bash -c "gh pr create --fill"',
    '# gh pr create --fill',
    'ghx pr create',
    'gh pr createx',
    'gh issue create',
    'gh pr list',
    'gh pr merge 12',
    'gh api repos/acme/widgets/pulls -f title=x',
    'if gh pr create --fill; then echo ok; fi',
    'gh pr create $FLAGS',
    'gh pr create "$@"',
    'gh pr $ACTION --fill',
    'gh --unknown x pr create',
    'gh pr create --title "unterminated',
    'gh pr create --body "$(cat <<EOF',
    '',
  ]) assert.equal(action(command), null, command);
  for (const value of [null, undefined, 12, {}, 'x'.repeat(100_001)]) assert.equal(findPullRequestCommand(value), null);
});

test('PowerShell quoting and separators are understood', () => {
  const powershell = { powershell: true };
  assert.equal(action('gh pr create --title "Add `"gates`"" --body $body', powershell), 'create');
  assert.equal(action("git push; gh pr create --title 'It''s ready' --fill", powershell), 'create');
  assert.equal(action('gh pr create --title x --body @"\nline one; gh pr create --draft\n"@', powershell), 'create');
  assert.equal(action("gh pr create --title x --body @'\ntext\n'@ --draft", powershell), null);
  assert.equal(action('gh pr ready 12', powershell), 'ready');
  assert.equal(action('Write-Output "gh pr create"', powershell), null);
  assert.equal(findPullRequestCommand('Set-Location ..\\other; gh pr create --fill', powershell).directory, '..\\other');
});

test('the tokenizer keeps quoted text together and marks dynamic text', () => {
  assert.deepEqual(splitCommands('a "b c" \'d e\' f\\ g && h | i'), [['a', 'b c', 'd e', 'f g'], ['h'], ['i']]);
  assert.deepEqual(splitCommands('a 2>&1; b &'), [['a', '2>&1'], ['b']]);
  assert.equal(splitCommands('a "$(b)"')[0][1], '\0');
  assert.equal(splitCommands("a 'unterminated"), null);
  assert.equal(classifyGhCommand(['gh', 'pr', 'create']).action, 'create');
  assert.equal(classifyGhCommand(['git', 'pr', 'create']), null);
  assert.equal(classifyGhCommand('gh pr create'), null);
});

test('the hook input of both hosts is read, and failed commands are ignored', () => {
  const cwd = path.resolve('some', 'repo');
  const claude = { hook_event_name: 'PostToolUse', tool_name: 'Bash', cwd, tool_input: { command: 'gh pr create --fill' }, tool_response: { stdout: `${pullUrl}\n`, stderr: '', interrupted: false } };
  assert.deepEqual(pullRequestEvent(claude), { action: 'create', ref: pullUrl, cwd });
  assert.deepEqual(pullRequestEvent({ ...claude, tool_name: 'PowerShell' }), { action: 'create', ref: pullUrl, cwd });
  const textResponse = { ...claude, tool_response: JSON.stringify({ output: `${pullUrl}\n`, metadata: { exit_code: 0 } }) };
  assert.equal(pullRequestEvent(textResponse).ref, pullUrl);
  assert.equal(pullRequestEvent({ ...claude, tool_input: { command: ['bash', '-lc', 'gh pr ready 7'] }, tool_response: '' }).ref, '7');
  assert.equal(pullRequestEvent({ ...claude, tool_input: { command: 'gh pr ready', workdir: 'nested' }, tool_response: { stdout: '' } }).cwd, path.join(cwd, 'nested'));
  const ready = { ...claude, tool_input: { command: 'gh pr ready' }, tool_response: { stdout: '✓ Pull request acme/widgets#34 is marked as "ready for review"\n' } };
  assert.equal(pullRequestEvent(ready).ref, '34');
  assert.equal(pullRequestEvent({ ...claude, tool_response: { stdout: '', stderr: '' } }).ref, null, 'no printed text: launch without a reference');

  assert.equal(pullRequestEvent({ ...claude, tool_response: { stdout: '', stderr: 'pull request create failed: GraphQL error' } }), null);
  assert.equal(pullRequestEvent({ ...claude, tool_response: { stdout: pullUrl, exitCode: 1 } }), null);
  assert.equal(pullRequestEvent({ ...claude, tool_response: { stdout: pullUrl, interrupted: true } }), null);
  assert.equal(pullRequestEvent({ ...claude, tool_response: JSON.stringify({ output: 'failed', metadata: { exit_code: 1 } }) }), null);
  assert.equal(pullRequestEvent({ ...claude, is_error: true }), null);
  assert.equal(pullRequestEvent({ ...claude, tool_input: { command: 'gh pr create --draft' } }), null);
  assert.equal(pullRequestEvent({ ...claude, tool_input: {} }), null);
  assert.equal(pullRequestEvent(null), null);
});

function temporaryRepository(scripts) {
  const base = mkdtempSync(path.join(os.tmpdir(), 'pr-gates-hook-'));
  const repository = path.join(base, 'sample repo');
  const home = path.join(base, 'home');
  mkdirSync(path.join(repository, '.git'), { recursive: true });
  mkdirSync(path.join(repository, 'src', 'deep'), { recursive: true });
  mkdirSync(home);
  writeFileSync(path.join(repository, 'package.json'), JSON.stringify({ name: 'sample', private: true, scripts }));
  return { base, repository, home };
}

function runHook(input, home) {
  const started = Date.now();
  const result = spawnSync(process.execPath, [hook], {
    input: typeof input === 'string' ? input : JSON.stringify(input),
    encoding: 'utf8',
    env: { ...process.env, HOME: home, USERPROFILE: home },
    timeout: 20_000,
  });
  return { ...result, elapsed: Date.now() - started };
}

function remove(directory) {
  try { rmSync(directory, { recursive: true, force: true, maxRetries: 20, retryDelay: 100 }); } catch { /* A file still held by the detached run stays in the temporary folder. */ }
}

async function waitFor(file, milliseconds = 60_000) {
  const deadline = Date.now() + milliseconds;
  while (Date.now() < deadline) {
    if (existsSync(file)) return true;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  return false;
}

test('the hook exits 0 fast and silently without a gates:pr script', () => {
  const { base, repository, home } = temporaryRepository({ test: 'node --version' });
  try {
    const input = { tool_name: 'Bash', cwd: repository, tool_input: { command: 'gh pr create --fill' }, tool_response: { stdout: pullUrl } };
    const result = runHook(input, home);
    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stdout, '');
    assert.equal(result.stderr, '');
    assert.ok(result.elapsed < 5_000, `hook took ${result.elapsed} ms`);
    assert.ok(!existsSync(path.join(home, '.agentic')), 'nothing may be written without a gates:pr script');
  } finally { remove(base); }
});

test('the hook exits 0 silently on input it cannot use', () => {
  const { base, repository, home } = temporaryRepository({ 'gates:pr': 'node gate.mjs' });
  try {
    for (const input of [
      '',
      'not json',
      '[]',
      { tool_name: 'Bash', cwd: repository, tool_input: { command: 'gh pr create --draft' }, tool_response: { stdout: pullUrl } },
      { tool_name: 'Bash', cwd: repository, tool_input: { command: 'gh pr ready --undo' }, tool_response: { stdout: '' } },
      { tool_name: 'Bash', cwd: repository, tool_input: { command: 'gh pr view 12' }, tool_response: { stdout: pullUrl } },
      { tool_name: 'Bash', cwd: path.join(os.tmpdir(), 'pr-gates-hook-missing-folder'), tool_input: { command: 'gh pr ready' }, tool_response: { stdout: '' } },
    ]) {
      const result = runHook(input, home);
      assert.equal(result.status, 0, result.stderr);
      assert.equal(result.stdout, '');
    }
    assert.ok(!existsSync(path.join(home, '.agentic')));
  } finally { remove(base); }
});

test('the hook launches gates:pr detached with the pull request and reports the log', async () => {
  const { base, repository, home } = temporaryRepository({ 'gates:pr': 'node gate.mjs' });
  const marker = path.join(repository, 'marker.json');
  writeFileSync(path.join(repository, 'gate.mjs'), [
    "import { writeFileSync } from 'node:fs';",
    "console.log('gate output line');",
    "await new Promise(resolve => setTimeout(resolve, 1500));",
    "writeFileSync('marker.json', JSON.stringify({ args: process.argv.slice(2), cwd: process.cwd() }));",
  ].join('\n'));
  try {
    const input = { hook_event_name: 'PostToolUse', tool_name: 'Bash', cwd: path.join(repository, 'src', 'deep'), tool_input: { command: 'git push -u origin HEAD && gh pr create --fill' }, tool_response: { stdout: `${pullUrl}\n`, stderr: '' } };
    const result = runHook(input, home);
    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stderr, '');
    assert.ok(result.elapsed < 5_000, `hook took ${result.elapsed} ms`);
    assert.ok(!existsSync(marker), 'the hook must return before the gates finish');
    const output = JSON.parse(result.stdout);
    assert.deepEqual(Object.keys(output), ['hookSpecificOutput']);
    assert.equal(output.hookSpecificOutput.hookEventName, 'PostToolUse');
    const context = output.hookSpecificOutput.additionalContext;
    assert.match(context, /^\[pr-gates\] Launched `npm run gates:pr` in the background for PR https:/);
    assert.equal(context.split('\n').length, 1);

    const logs = readdirSync(path.join(home, '.agentic', 'pr-gates'));
    assert.equal(logs.length, 1);
    assert.match(logs[0], /^sample_repo-\d{8}T\d{6}Z-\d+\.log$/);
    const log = path.join(home, '.agentic', 'pr-gates', logs[0]);
    assert.ok(context.includes(log), 'the context names the log file');

    assert.ok(await waitFor(marker), 'the detached gates:pr run never wrote its marker');
    const written = JSON.parse(readFileSync(marker, 'utf8'));
    assert.deepEqual(written.args, ['--pr', pullUrl]);
    assert.equal(path.basename(written.cwd), 'sample repo');
    assert.match(readFileSync(log, 'utf8'), /gate output line/);
  } finally { remove(base); }
});

test('the hook launches gates:pr without --pr when the pull request is unknown', async () => {
  const { base, repository, home } = temporaryRepository({ 'gates:pr': 'node gate.mjs' });
  const marker = path.join(repository, 'marker.json');
  writeFileSync(path.join(repository, 'gate.mjs'), "import { writeFileSync } from 'node:fs';\nwriteFileSync('marker.json', JSON.stringify(process.argv.slice(2)));\n");
  try {
    const result = runHook({ tool_name: 'PowerShell', cwd: repository, tool_input: { command: 'gh pr ready' }, tool_response: { stdout: '' } }, home);
    assert.equal(result.status, 0, result.stderr);
    assert.match(JSON.parse(result.stdout).hookSpecificOutput.additionalContext, /in the background from /);
    assert.ok(await waitFor(marker), 'the detached gates:pr run never wrote its marker');
    assert.deepEqual(JSON.parse(readFileSync(marker, 'utf8')), []);
  } finally { remove(base); }
});
