import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { chmodSync, copyFileSync, existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, statSync, utimesSync, writeFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { postMergeContext } from '../plugins/agentic-engineering-skills/hooks/post-merge.mjs';
import { postPrContext } from '../plugins/agentic-engineering-skills/hooks/post-pr.mjs';

const hookDirectory = fileURLToPath(new URL('../plugins/agentic-engineering-skills/hooks/', import.meta.url));

const mergedPr = {
  state: 'MERGED',
  url: 'https://github.com/acme/widget/pull/12',
  mergedAt: '2026-11-02T09:00:00Z',
  mergeCommit: { oid: 'abcdef1234567890' },
  baseRefName: 'main',
  headRefName: 'feature',
};

test('successful gh pr merge emits safe reminder only after verified merge', () => {
  const called = [];
  const reminder = postMergeContext({
    tool_name: 'Bash',
    tool_input: { command: 'gh pr merge 12 --squash' },
    tool_response: { exit_code: 0 },
  }, {
    currentRepository: () => 'acme/widget',
    lookup: (...args) => { called.push(args); return mergedPr; },
  });

  assert.deepEqual(called, [['12', undefined]]);
  assert.match(reminder, /PR merged: https:\/\/github\.com\/acme\/widget\/pull\/12/);
  assert.match(reminder, /merge commit abcdef1234567890/);
  assert.match(reminder, /never force, reset, or clean/i);
  assert.doesNotMatch(reminder, /gh pr merge|git (?:reset|clean)/i);

  const hostileMetadata = postMergeContext({
    tool_name: 'Bash', tool_input: { command: 'gh pr merge 12' }, tool_response: { exit_code: 0 },
  }, { lookup: () => ({ ...mergedPr, baseRefName: '[evil](https://example.test)' }) });
  assert.doesNotMatch(hostileMetadata, /\[evil\]|https:\/\/example\.test/);
});

test('merge without an explicit PR selector never looks up the post-merge branch', () => {
  const cases = [
    { command: 'gh pr merge --squash --delete-branch', response: { exit_code: 0 } },
    { command: 'gh pr merge -s -d', response: { exit_code: 0, stderr: 'Merged pull request acme/widget#12\nMerged pull request acme/widget#13' } },
    { command: 'gh pr merge --squash', response: { exit_code: 0, stderr: 'Merged pull request acme/widget#12' } },
    { command: 'gh pr merge', response: { exit_code: 0 } },
    { command: 'gh pr merge -s -d', response: { exit_code: 0, stderr: 'Merged pull request someone/else#12' } },
  ];
  for (const { command, response } of cases) {
    const calls = [];
    const reminder = postMergeContext({
      tool_name: 'Bash', tool_input: { command }, tool_response: response,
    }, {
      currentRepository: () => 'acme/widget',
      lookup: (...args) => { calls.push(args); return mergedPr; },
    });
    assert.equal(reminder, null, command);
    assert.deepEqual(calls, [], command);
  }
});

test('explicit PR selectors verify the same merged PR and repository', () => {
  const input = (command) => ({ tool_name: 'Bash', tool_input: { command }, tool_response: { exit_code: 0 } });
  const currentRepository = () => 'acme/widget';
  const url = 'https://github.com/acme/widget/pull/12';
  const cases = [
    { command: 'gh pr merge 12 --squash --delete-branch', args: ['12', undefined] },
    { command: `gh pr merge ${url} --squash -d`, args: [url, 'acme/widget'] },
    { command: 'gh pr merge 12 --squash --repo acme/widget', args: ['12', 'acme/widget'] },
  ];
  for (const { command, args } of cases) {
    const calls = [];
    const lookup = (...actual) => { calls.push(actual); return mergedPr; };
    const reminder = postMergeContext(input(command), { currentRepository, lookup });
    assert.match(reminder ?? '', /PR merged: https:\/\/github\.com\/acme\/widget\/pull\/12/, command);
    assert.deepEqual(calls, [args], command);
    assert.equal(postMergeContext(input(command), {
      currentRepository, lookup: () => ({ ...mergedPr, url: 'https://github.com/acme/widget/pull/13' }),
    }), null, command);
  }
  assert.equal(postMergeContext(input(`gh pr merge ${url} --squash`), {
    currentRepository, lookup: () => ({ ...mergedPr, url: 'https://github.com/someone/else/pull/12' }),
  }), null);
  assert.equal(postMergeContext(input(`gh pr merge ${url} --squash`), {
    currentRepository: () => 'someone/else', lookup: () => mergedPr,
  }), null);
});

test('failed, errored, or non-merged command produces no reminder', () => {
  const input = { tool_name: 'Bash', tool_input: { command: 'gh pr merge 12' } };
  assert.equal(postMergeContext({ ...input, tool_response: { exit_code: 1 } }, { lookup: () => mergedPr }), null);
  assert.equal(postMergeContext({ ...input, tool_response: 'Process exited with code 1' }, { lookup: () => mergedPr }), null);
  assert.equal(postMergeContext({ ...input, is_error: true }, { lookup: () => mergedPr }), null);
  assert.equal(postMergeContext(input, { lookup: () => ({ ...mergedPr, state: 'OPEN', mergedAt: null }) }), null);
});

test('cross-repository merge target and shell injection are ignored', () => {
  const lookup = () => mergedPr;
  const input = (command) => ({ tool_name: 'Bash', tool_input: { command }, tool_response: { exit_code: 0 } });
  assert.equal(postMergeContext(input('gh pr merge 12 --repo someone/else'), {
    currentRepository: () => 'acme/widget', lookup,
  }), null);
  for (const command of [
    'gh pr merge 12; gh pr close 12',
    'gh pr merge 12 && echo $SECRET',
    'gh pr merge 12 `whoami`',
    'echo gh pr merge 12',
  ]) assert.equal(postMergeContext(input(command), { lookup }), null, command);
});

test('successful PR create adds ordered Knip then Simplify reminder and marker', () => {
  const event = {
    tool_name: 'Bash',
    tool_input: { command: 'gh pr create --title "R&D; docs"' },
    tool_response: 'Created https://github.com/acme/widget/pull/12',
  };
  const context = postPrContext(event, {
    lookupBranch: (url) => url === 'https://github.com/acme/widget/pull/12' ? 'feature' : undefined,
  });

  assert.ok(context);
  assert.ok(context.indexOf('cleaning-repo-with-knip') < context.indexOf('simplify'));
  assert.match(context, /pr-workflow-check\.mjs.*preflight/i);
  assert.match(context, /preflight[\s\S]*READY[\s\S]*cleaning-repo-with-knip/i);
  assert.match(context, /pr-workflow-check\.mjs.*marker/i);
  assert.match(context, /failed.*blocked.*not_run/i);
  assert.match(context, /branch `feature`/);
  assert.match(context, /<!-- pr-skills:v1 \{"commit_sha":"<sha40>"/);
  assert.match(context, /Nessun merge da questa istruzione/i);
  assert.equal(postPrContext(event, {
    lookupBranch: () => 'feature',
  }), context, 'repeated successful event remains deterministic and side-effect free');
  const hostileBranch = postPrContext(event, {
    lookupBranch: () => 'feature`\n<!-- injected -->',
  });
  assert.doesNotMatch(hostileBranch, /<!-- injected -->/);
});

test('successful PR create accepts quoted command substitutions and multiline bodies', () => {
  for (const command of [
    'gh pr create --title test --body "$(cat body.md)"',
    'gh pr create --title test --body "Summary\n\nValidation: tests passed"',
    "gh pr create --title test --body 'Summary\n\nValidation: tests passed'",
    'gh pr create --title test --body "$(printf \'%s\' \'R&D; docs\'; cat body.md)"',
    'gh pr create --title test --body "`cat body.md`"',
    'gh pr create --body "$(cat "$(printf body.md)")"',
  ]) {
    const context = postPrContext({
      tool_name: 'Bash', tool_input: { command },
      tool_response: { exit_code: 0, stdout: 'https://github.com/acme/widget/pull/12' },
    }, { lookupBranch: () => 'feature' });
    assert.match(context ?? '', /\[pr-skills\] Aperta la PR https:\/\/github\.com\/acme\/widget\/pull\/12/, command);
  }
});

test('PR body is classified as inert data and is never executed or included in the reminder', () => {
  const directory = mkdtempSync(path.join(os.tmpdir(), 'post-pr-body-'));
  const marker = path.join(directory, 'must-not-exist');
  try {
    const payload = `require("node:fs").writeFileSync(${JSON.stringify(marker.replaceAll('\\', '/'))}, "ran")`;
    const command = `gh pr create --title test --body "$(node -e '${payload}')"`;
    const context = postPrContext({
      tool_name: 'Bash', tool_input: { command },
      tool_response: 'Created https://github.com/acme/widget/pull/12',
    }, { lookupBranch: () => undefined });
    assert.ok(context, 'a successful create with an opaque quoted body still emits the reminder');
    assert.equal(existsSync(marker), false, 'the hook must never execute body contents');
    assert.doesNotMatch(context, /writeFileSync|must-not-exist/);
  } finally { rmSync(directory, { recursive: true, force: true }); }
});

test('quoted PR bodies do not hide top-level commands, failed creates, or missing URLs', () => {
  const base = {
    tool_name: 'Bash', tool_input: { command: 'gh pr create --body "$(cat body.md)"' },
    tool_response: 'https://github.com/acme/widget/pull/12',
  };
  assert.equal(postPrContext({ ...base, tool_response: { exit_code: 1, stdout: base.tool_response } }), null);
  assert.equal(postPrContext({ ...base, tool_response: 'created without a URL' }), null);
  for (const command of [
    'echo gh pr create --body "$(cat body.md)"',
    'gh pr create --body "$(cat body.md)"; gh pr merge 12',
    'gh pr create --body "$(cat body.md)" && gh pr merge 12',
    'gh pr create --body "$(cat body.md)" | cat',
    'gh pr create --body "$(cat body.md)"\ngh pr merge 12',
    'gh pr create --body "$(cat body.md)" > output.txt',
    'gh pr create --body "unterminated',
    '"g\\h" pr create --body test',
    'gh pr create --body "$(cat body.md)" || gh pr merge 12',
    'gh pr create --body "$(cat body.md)" & gh pr merge 12',
    'gh pr create --body "$(cat "$(printf body.md)")"; gh pr merge 12',
    'gh pr create --body "$(cat body.md"',
    '"$(printf gh)" pr create --body test',
  ]) assert.equal(postPrContext({ ...base, tool_input: { command } }, { lookupBranch: () => undefined }), null, command);
});

test('failed PR create, invalid output, and injected commands emit nothing', () => {
  const base = { tool_name: 'Bash', tool_input: { command: 'gh pr create' } };
  assert.equal(postPrContext({ ...base, isError: true, tool_response: 'https://github.com/acme/widget/pull/12' }), null);
  assert.equal(postPrContext({ ...base, tool_response: 'created draft with no URL' }), null);
  assert.equal(postPrContext({
    ...base,
    tool_input: { command: 'gh pr create; gh pr merge 12' },
    tool_response: 'https://github.com/acme/widget/pull/12',
  }), null);
});

test('known MCP create tool uses text response fixture and never merges automatically', () => {
  const context = postPrContext({
    tool_name: 'mcp__github__create_pull_request',
    tool_input: { title: 'Feature' },
    tool_response: { content: [{ type: 'text', text: 'Created https://github.com/acme/widget/pull/12' }] },
  }, { lookupBranch: () => undefined });
  assert.match(context, /https:\/\/github\.com\/acme\/widget\/pull\/12/);
  assert.match(context, /Nessun merge da questa istruzione/);
  assert.equal(postPrContext({
    tool_name: 'mcp__github__get_pull_request',
    tool_response: { content: [{ type: 'text', text: 'https://github.com/acme/widget/pull/12' }] },
  }), null);
});

test('hook input is JSON-compatible and rejects malformed JSON without throwing', async () => {
  const { parseHookInput } = await import('../plugins/agentic-engineering-skills/hooks/hook-lib.mjs');
  assert.deepEqual(parseHookInput('{"tool_name":"Bash","tool_input":{"command":"gh pr create"}}'), {
    tool_name: 'Bash', tool_input: { command: 'gh pr create' },
  });
  assert.equal(parseHookInput('{not json'), null);
  const { hookOutput } = await import('../plugins/agentic-engineering-skills/hooks/hook-lib.mjs');
  assert.deepEqual(hookOutput('Reminder'), {
    hookSpecificOutput: { hookEventName: 'PostToolUse', additionalContext: 'Reminder' },
  });
});

test('plugin hooks contract discovers PostToolUse Bash and known MCP handlers from plugin root', () => {
  const manifest = JSON.parse(readFileSync(path.join(hookDirectory, 'hooks.json'), 'utf8'));
  const handlers = manifest.hooks.PostToolUse;
  const merge = handlers.find(handler => handler.matcher === 'Bash');
  const pr = handlers.find(handler => handler.matcher.includes('mcp__'));

  assert.ok(merge);
  assert.ok(pr);
  assert.deepEqual(Object.keys(manifest.hooks).sort(), ['PostToolUse', 'SessionStart', 'SubagentStart'].sort());
  for (const [handler, script] of [[merge, 'post-merge.mjs'], [pr, 'post-pr.mjs']]) {
    const command = handler.hooks[0].command;
    assert.match(command, /^node /);
    assert.match(command, new RegExp(`\\$\\{CLAUDE_PLUGIN_ROOT\\}\\/hooks\\/${script.replace('.', '\\.')}\\"`));
    assert.equal(handler.hooks[0].type, 'command');
  }
});

test('installed hook entrypoints consume stdin JSON and use fake gh found on PATH', async () => {
  const temp = mkdtempSync(path.join(os.tmpdir(), 'agent-skills-hook-'));
  const fakeBin = path.join(temp, 'bin');
  const hookCwd = path.join(temp, 'repo');
  const isolatedTemp = path.join(temp, 'private-temp');
  const fakeGh = path.join(fakeBin, process.platform === 'win32' ? 'gh.exe' : 'gh');
  const fakeGhScript = [
    "const args = process.argv.slice(2);",
    "if (args[0] !== 'view') process.exit(2);",
    "if (args.includes('headRefName')) process.stdout.write('feature/one\\n');",
    "else process.stdout.write(JSON.stringify({ state:'MERGED', url:'https://github.com/acme/widget/pull/12', mergedAt:'2026-11-02T09:00:00Z', mergeCommit:{oid:'abcdef1234567890'}, baseRefName:'main', headRefName:'feature/one' }));",
  ].join('\n');

  try {
    requireDirectory(fakeBin);
    requireDirectory(hookCwd);
    requireDirectory(isolatedTemp);
    copyFileSync(process.execPath, fakeGh);
    if (process.platform !== 'win32') chmodSync(fakeGh, 0o755);
    writeFileSync(path.join(hookCwd, 'pr'), fakeGhScript);

    const env = {
      ...process.env,
      PATH: `${fakeBin}${path.delimiter}${process.env.PATH ?? ''}`,
      TMPDIR: isolatedTemp,
      TMP: isolatedTemp,
      TEMP: isolatedTemp,
    };
    const invoke = (script, event) => spawnSync(process.execPath, [path.join(hookDirectory, script)], {
      cwd: hookCwd,
      env,
      encoding: 'utf8',
      input: JSON.stringify(event),
      timeout: 10_000,
      windowsHide: true,
    });

    const merge = invoke('post-merge.mjs', {
      tool_name: 'Bash', tool_input: { command: 'gh pr merge 12' }, tool_response: { exit_code: 0 },
    });
    assert.equal(merge.status, 0, merge.stderr);
    assert.match(JSON.parse(merge.stdout).hookSpecificOutput.additionalContext, /merge commit abcdef1234567890/);

    const pr = invoke('post-pr.mjs', {
      tool_name: 'Bash', tool_input: { command: 'gh pr create' },
      tool_response: 'Created https://github.com/acme/widget/pull/12',
    });
    assert.equal(pr.status, 0, pr.stderr);
    const context = JSON.parse(pr.stdout).hookSpecificOutput.additionalContext;
    assert.match(context, /branch `feature\/one`/);
    assert.match(context, /Nessun merge da questa istruzione/);

    const sessionEvent = {
      session_id: 'session-secret-one',
      tool_name: 'Bash', tool_input: { command: 'gh pr create' },
      tool_response: 'Created https://github.com/acme/widget/pull/12',
    };
    const runParallel = (event) => invokeAsync(path.join(hookDirectory, 'post-pr.mjs'), event, env, hookCwd);
    const concurrent = await Promise.all(Array.from({ length: 8 }, () => runParallel(sessionEvent)));
    assert.ok(concurrent.every(result => result.status === 0), concurrent.map(result => result.stderr).join('\n'));
    assert.equal(concurrent.filter(result => result.stdout).length, 1, 'atomic marker lets one concurrent process emit reminder');

    const differentSession = await runParallel({ ...sessionEvent, session_id: 'session-secret-two' });
    assert.ok(differentSession.stdout, 'same URL in another session gets reminder');
    const differentUrl = await runParallel({
      ...sessionEvent,
      tool_response: 'Created https://github.com/acme/widget/pull/13',
    });
    assert.ok(differentUrl.stdout, 'different URL in same session gets reminder');
    const noSessionFirst = await runParallel({ ...sessionEvent, session_id: undefined });
    const noSessionSecond = await runParallel({ ...sessionEvent, session_id: undefined });
    assert.ok(noSessionFirst.stdout && noSessionSecond.stdout, 'missing session id does not suppress reminders');

    const mergeEvent = {
      session_id: sessionEvent.session_id,
      tool_name: 'Bash', tool_input: { command: 'gh pr merge 12' }, tool_response: { exit_code: 0 },
    };
    const mergeAgain = invoke('post-merge.mjs', mergeEvent);
    const mergeAgainTwo = invoke('post-merge.mjs', mergeEvent);
    assert.ok(mergeAgain.stdout && mergeAgainTwo.stdout, 'PR reminder dedup does not affect post-merge hook');

    const stateRoot = path.join(isolatedTemp, 'agentic-engineering-skills-pr-reminders-v1');
    const sessionDirs = readdirSync(stateRoot);
    assert.equal(sessionDirs.length, 2, 'session state isolated by digest');
    assert.ok(sessionDirs.every(name => /^[a-f0-9]{64}$/.test(name)));
    const markerNames = sessionDirs.flatMap(name => readdirSync(path.join(stateRoot, name)));
    assert.equal(markerNames.length, 3, 'one empty marker for each session and URL pair');
    assert.ok(markerNames.every(name => /^[a-f0-9]{64}$/.test(name)));
    assert.doesNotMatch([...sessionDirs, ...markerNames].join(' '), /session-secret|acme|widget|pull/i);
    for (const session of sessionDirs) {
      for (const marker of readdirSync(path.join(stateRoot, session))) {
        assert.equal(statSync(path.join(stateRoot, session, marker)).size, 0, 'marker contains no input data');
      }
    }
    if (process.platform !== 'win32') {
      assert.equal(statSync(stateRoot).mode & 0o777, 0o700);
      for (const session of sessionDirs) {
        assert.equal(statSync(path.join(stateRoot, session)).mode & 0o777, 0o700);
        for (const marker of readdirSync(path.join(stateRoot, session))) {
          assert.equal(statSync(path.join(stateRoot, session, marker)).mode & 0o777, 0o600);
        }
      }
    }

    const sessionDigest = createHash('sha256').update(sessionEvent.session_id).digest('hex');
    const url = 'https://github.com/acme/widget/pull/12';
    const urlDigest = createHash('sha256').update(url).digest('hex');
    const markerPath = path.join(stateRoot, sessionDigest, urlDigest);
    const expired = new Date(Date.now() - 15 * 24 * 60 * 60 * 1000);
    utimesSync(markerPath, expired, expired);
    const retriedExpired = await runParallel(sessionEvent);
    assert.ok(retriedExpired.stdout, 'expired same-pair marker allows reminder again');

    const invalidTemp = path.join(temp, 'not-a-directory');
    writeFileSync(invalidTemp, 'fixture');
    const fallbackEnv = { ...env, TMPDIR: invalidTemp, TMP: invalidTemp, TEMP: invalidTemp };
    const tempFailure = await invokeAsync(path.join(hookDirectory, 'post-pr.mjs'), sessionEvent, fallbackEnv, hookCwd);
    assert.equal(tempFailure.status, 0, tempFailure.stderr);
    assert.ok(tempFailure.stdout, 'temporary state failure fails open and preserves reminder');
  } finally {
    rmSync(temp, { recursive: true, force: true });
  }
});

function requireDirectory(directory) {
  mkdirSync(directory, { recursive: true });
}

function invokeAsync(script, event, env, cwd) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [script], { cwd, env, windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'] });
    let stdout = '';
    let stderr = '';
    child.stdout.setEncoding('utf8').on('data', chunk => { stdout += chunk; });
    child.stderr.setEncoding('utf8').on('data', chunk => { stderr += chunk; });
    child.on('error', reject);
    child.on('close', (status, signal) => resolve({ status, signal, stdout, stderr }));
    child.stdin.end(JSON.stringify(event));
  });
}
