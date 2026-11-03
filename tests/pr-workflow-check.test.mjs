import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { copyFileSync, chmodSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { assessPreflight, markerForHead } from '../plugins/agentic-engineering-skills/hooks/pr-workflow-check.mjs';
const head = 'a'.repeat(40);
const good = { headBefore: head, headAfter: head, workspaceHead: head, clean: true, state: 'OPEN', checks: [{ name: 'tests', bucket: 'pass' }], review: { head_sha: head, outcome: 'passed', independent: true, required_checks: ['tests'], reviewer: 'independent reviewer', evidence: 'review.txt', evidence_sha256: 'c'.repeat(64) }, evidenceExists: true };
const comment = (data, authorAssociation = 'OWNER') => ({ authorAssociation, body: `<!-- pr-skills:v1 ${JSON.stringify(data)} -->` });
const positive = { commit_sha: head, knip: 'passed', simplify: 'no_changes' };
test('preflight permits only matching head, completed CI, and a documented successful independent review', () => {
  assert.equal(assessPreflight(good).ready, true);
  for (const change of [
    { headAfter: 'b'.repeat(40) }, { workspaceHead: 'b'.repeat(40) }, { clean: false }, { state: 'CLOSED' },
    { checks: [] }, { checks: [{ name: 'tests', bucket: 'pending' }] }, { checks: [{ name: 'tests', bucket: 'fail' }] },
    { review: null }, { review: { ...good.review, head_sha: 'b'.repeat(40) } }, { review: { ...good.review, outcome: 'failed' } },
    { review: { ...good.review, reviewer: '' } }, { review: { ...good.review, independent: false } }, { review: { ...good.review, required_checks: [] } }, { review: { ...good.review, required_checks: ['tests', 'build'] } }, { review: { ...good.review, required_checks: ['pr-skills-check'] } }, { evidenceExists: false },
  ]) assert.equal(assessPreflight({ ...good, ...change }).ready, false, JSON.stringify(change));
});
test('self-dependent marker check is excluded but cannot stand in for actual CI', () => {
  assert.equal(assessPreflight({ ...good, checks: [{ name: 'pr-skills-check', bucket: 'pending' }, { name: 'tests', bucket: 'pass' }] }).ready, true);
  assert.equal(assessPreflight({ ...good, checks: [{ name: 'pr-skills-check', bucket: 'pending' }] }).ready, false);
});
test('hosted checks cannot omit a gate from a configured trusted policy', () => {
  const trustedPolicy = { gates: [{ name: 'tests' }, { name: 'security' }] };
  assert.equal(assessPreflight({ ...good, trustedPolicy }).ready, false);
  const full = { ...good, trustedPolicy, checks: [{ name: 'tests', bucket: 'pass' }, { name: 'security', bucket: 'pass' }], review: { ...good.review, required_checks: ['tests', 'security'] } };
  assert.equal(assessPreflight(full).ready, true);
});
test('billing fallback requires GitHub proof, a trusted complete policy, and matching local evidence', () => {
  const url = 'https://github.com/acme/widget/pull/12';
  const fallback = {
    kind: 'github_billing', head_sha: head, pr_url: url,
    confirmed_by: 'reviewer', billing_block_confirmed: true,
    billing_blocked_checks: ['tests'],
    block_evidence: 'billing.txt', block_evidence_sha256: 'd'.repeat(64),
    gates: [{ name: 'tests', head_sha: head, outcome: 'passed', exit_code: 0, equivalent: true,
      commands: ['npm test'], tool_versions: ['node 22'], services: [], coverage: 'full tests',
      evidence: 'tests.txt', evidence_sha256: 'e'.repeat(64) }],
  };
  const input = { ...good, prUrl: url, checks: [{ name: 'tests', bucket: 'fail' }],
    review: { ...good.review, billing_fallback: fallback }, fallbackEvidenceValid: true, fallbackReviewValid: true,
    trustedPolicy: { gates: [{ name: 'tests', commands: ['npm test'], tool_versions: ['node 22'], services: [], coverage: 'full tests' }] }, billingVerified: true };
  const result = assessPreflight(input);
  assert.equal(result.ready, true);
  assert.equal(result.mode, 'billing_fallback');
  const variants = [
    { fallbackEvidenceValid: false }, { fallbackReviewValid: false },
    { billingVerified: false }, { trustedPolicy: null },
    { trustedPolicy: { gates: [...input.trustedPolicy.gates, { name: 'security', commands: ['npm audit'], tool_versions: ['node 22'], services: [], coverage: 'security' }] } },
    { trustedPolicy: { gates: [{ ...input.trustedPolicy.gates[0], commands: ['npm run test:all'] }] } },
    { headAfter: 'b'.repeat(40) }, { clean: false },
    { review: { ...input.review, billing_fallback: { ...fallback, head_sha: 'b'.repeat(40) } } },
    { review: { ...input.review, billing_fallback: { ...fallback, pr_url: 'https://github.com/acme/other/pull/12' } } },
    { review: { ...input.review, billing_fallback: { ...fallback, billing_block_confirmed: false } } },
    { review: { ...input.review, billing_fallback: { ...fallback, gates: [] } } },
    { review: { ...input.review, billing_fallback: { ...fallback, gates: [{ ...fallback.gates[0], outcome: 'failed' }] } } },
    { review: { ...input.review, billing_fallback: { ...fallback, gates: [{ ...fallback.gates[0], exit_code: 1 }] } } },
    { review: { ...input.review, billing_fallback: { ...fallback, gates: [{ ...fallback.gates[0], equivalent: false }] } } },
    { review: { ...input.review, billing_fallback: { ...fallback, gates: [{ ...fallback.gates[0], commands: [] }] } } },
    { checks: [{ name: 'tests', bucket: 'pending' }, { name: 'security', bucket: 'fail' }] },
  ];
  for (const change of variants) assert.equal(assessPreflight({ ...input, ...change }).ready, false, JSON.stringify(change));
  const unpinnedPolicy = { gates: [{ ...input.trustedPolicy.gates[0], runtime_reference_required: true }] };
  assert.equal(assessPreflight({ ...input, trustedPolicy: unpinnedPolicy }).ready, false, 'an unpinned runner needs version evidence');
  const runtime_reference = { runner_image: 'ubuntu-24.04/20261020', hosted_node_version: '22.19.0', local_node_version: '22.19.0', reference_url: 'https://github.com/actions/runner-images/releases/tag/ubuntu24%2F20261020.1', evidence: 'runtime.txt', evidence_sha256: 'a'.repeat(64) };
  const reviewed = { ...input, trustedPolicy: unpinnedPolicy, review: { ...input.review, billing_fallback: { ...fallback, gates: [{ ...fallback.gates[0], runtime_reference }] } } };
  assert.equal(assessPreflight(reviewed).ready, true);
  runtime_reference.local_node_version = '24.1.0';
  assert.equal(assessPreflight(reviewed).ready, false, 'local Node must match the reviewed hosted version');
});
test('only a trusted current-head marker with explicit successful results is accepted', () => {
  assert.equal(markerForHead(head, [comment(positive)]).ready, true);
  for (const bad of [
    { ...positive, knip: 'failed' }, { ...positive, simplify: 'blocked' }, { ...positive, simplify: 'not_run' },
    { ...positive, knip: true }, { ...positive, commit_sha: 'b'.repeat(40) },
  ]) assert.equal(markerForHead(head, [comment(bad)]).ready, false, JSON.stringify(bad));
  assert.equal(markerForHead(head, [comment(positive, 'CONTRIBUTOR')]).ready, false);
  assert.equal(markerForHead(head, [comment(positive), comment({ ...positive, knip: 'failed' })]).ready, false);
  assert.equal(markerForHead(head, [comment(positive), { authorAssociation: 'OWNER', body: '<!-- pr-skills:v1 {broken} -->' }]).ready, false, 'a later malformed trusted marker cannot leave an older success effective');
});


test('a later trusted marker with a malformed commit invalidates earlier success', () => {
  for (const commit_sha of [undefined, null, 42, '', 'a'.repeat(39), 'g'.repeat(40)]) {
    const result = markerForHead(head, [comment(positive), comment({ ...positive, commit_sha })]);
    assert.equal(result.ready, false, `malformed commit ${JSON.stringify(commit_sha)} must block`);
  }
  assert.equal(markerForHead(head, [comment(positive), comment({ ...positive, commit_sha: 'b'.repeat(40) })]).ready, true, 'valid marker for another head does not invalidate success');
  assert.equal(markerForHead(head, [comment({ ...positive, commit_sha: '' }), comment(positive)]).ready, true, 'a subsequent valid marker restores readiness');
  assert.equal(markerForHead(head, [comment(positive), comment({ ...positive, commit_sha: '' }, 'CONTRIBUTOR')]).ready, true, 'untrusted malformed marker is ignored');
});

test('CLI verifies real evidence and fails closed for CI, stale heads and failed markers', () => {
  const dir = mkdtempSync(path.join(os.tmpdir(), 'pr-workflow-check-'));
  const bin = path.join(dir, 'bin');
  const exe = process.platform === 'win32' ? '.exe' : '';
  const sourceChecker = fileURLToPath(new URL('../plugins/agentic-engineering-skills/hooks/pr-workflow-check.mjs', import.meta.url));
  const hookDir = path.join(dir, 'hook');
  const checker = path.join(hookDir, 'pr-workflow-check.mjs');
  const url = 'https://github.com/acme/widget/pull/12';
  const workflow = 'name: CI\non: [pull_request]\njobs:\n  tests:\n    runs-on: ubuntu-latest\n';
  const workflowHash = createHash('sha256').update(workflow).digest('hex');
  const payload = { head, after: head, checks: [{ name: 'tests', bucket: 'pass' }, { name: 'pr-skills-check', bucket: 'pending' }], checksStatus: 8, comments: [comment(positive)], dirty: false,
    run: { id: 101, run_attempt: 1, event: 'pull_request', head_sha: head, head_branch: 'feature/test', status: 'completed', conclusion: 'failure', path: '.github/workflows/ci.yml', repository: { full_name: 'acme/widget' }, head_repository: { full_name: 'acme/widget' }, pull_requests: [] },
    job: { id: 202, run_id: 101, run_attempt: 1, head_sha: head, name: 'tests', status: 'completed', conclusion: 'failure', runner_id: 0, steps: [], check_run_url: 'https://api.github.com/repos/acme/widget/check-runs/303' },
    check: { id: 303, name: 'tests', head_sha: head, status: 'completed', conclusion: 'failure', app: { id: 15368, slug: 'github-actions', owner: { login: 'github' } } },
    greenJob: { id: 204, run_id: 101, run_attempt: 1, head_sha: head, name: 'security', status: 'completed', conclusion: 'success', check_run_url: 'https://api.github.com/repos/acme/widget/check-runs/304' },
    greenCheck: { id: 304, name: 'security', head_sha: head, status: 'completed', conclusion: 'success', app: { id: 15368, slug: 'github-actions', owner: { login: 'github' } } },
    annotations: [{ annotation_level: 'failure', message: "The job was not started because recent account payments have failed or your spending limit needs to be increased. Please check the 'Billing & plans' section in your settings" }] };
  try {
    mkdirSync(bin);
    mkdirSync(hookDir);
    copyFileSync(sourceChecker, checker);
    for (const tool of ['gh', 'git']) { const target = path.join(bin, `${tool}${exe}`); copyFileSync(process.execPath, target); if (process.platform !== 'win32') chmodSync(target, 0o755); }
    writeFileSync(path.join(dir, 'pr'), `
      const fs = require('fs');
      const d = JSON.parse(fs.readFileSync('fixture.json'));
      const args = process.argv.slice(2);
      function changeLocalState(effect) {
        if (effect === 'dirty' || effect === 'workspaceHead') {
          if (effect === 'dirty') d.dirty = true;
          else d.workspaceHead = 'b'.repeat(40);
          fs.writeFileSync('fixture.json', JSON.stringify(d));
        } else if (effect === 'reviewEvidence') {
          fs.writeFileSync('review.txt', 'tampered');
        } else if (effect === 'reviewRecord') {
          const record = JSON.parse(fs.readFileSync('review.json'));
          record.reviewer = 'another reviewer';
          fs.writeFileSync('review.json', JSON.stringify(record));
        } else if (effect === 'policy') {
          const policy = JSON.parse(fs.readFileSync('hook/billing-policies.json'));
          policy.policies[0].gates[0].coverage = 'changed coverage';
          fs.writeFileSync('hook/billing-policies.json', JSON.stringify(policy));
        }
      }
      if (args[0] === 'checks') {
        let n = 0;
        try { n = Number(fs.readFileSync('checks-counter.txt')); } catch {}
        fs.writeFileSync('checks-counter.txt', String(n + 1));
        if (n) changeLocalState(d.checksAfterEffect);
        process.stdout.write(JSON.stringify(n ? (d.checksAfter ?? d.checks) : d.checks));
        process.exit(n ? (d.checksStatusAfter ?? d.checksStatus) : d.checksStatus);
      }
      if (args[0] === 'view') {
        let n = 0;
        try { n = Number(fs.readFileSync('counter.txt')); } catch {}
        fs.writeFileSync('counter.txt', String(n + 1));
        if (n > 1) changeLocalState(d.finalViewEffect);
        process.stdout.write(JSON.stringify({ state: 'OPEN', headRefOid: n > 1 ? (d.finalHead ?? d.after) : n ? d.after : d.head, headRefName: 'feature/test', baseRefOid: '${'c'.repeat(40)}', baseRefName: 'main', comments: n ? (d.commentsAfter || d.comments) : d.comments }));
        process.exit(0);
      }
      process.exit(2);
    `);
    writeFileSync(path.join(dir, 'api'), `const fs=require('fs');const d=JSON.parse(fs.readFileSync('fixture.json'));const p=process.argv[2];if(p.endsWith('/actions/runs/101'))process.stdout.write(JSON.stringify(d.run));else if(p.endsWith('/actions/jobs/202'))process.stdout.write(JSON.stringify(d.job));else if(p.endsWith('/actions/jobs/204'))process.stdout.write(JSON.stringify(d.greenJob));else if(p.endsWith('/check-runs/303/annotations'))process.stdout.write(JSON.stringify(d.annotations));else if(p.endsWith('/check-runs/303'))process.stdout.write(JSON.stringify(d.check));else if(p.endsWith('/check-runs/304'))process.stdout.write(JSON.stringify(d.greenCheck));else process.exit(2);`);
    writeFileSync(path.join(dir, 'ls-tree'), `process.stdout.write('.github/workflows/ci.yml\\n')`);
    writeFileSync(path.join(dir, 'show'), `process.stdout.write(${JSON.stringify(workflow)})`);
    const policy = { version: 1, policies: [{ repository: 'acme/widget', base_ref: 'main', workflows: [{ path: '.github/workflows/ci.yml', sha256: workflowHash }], gates: [{ name: 'tests', workflow: '.github/workflows/ci.yml', commands: ['npm test'], tool_versions: ['node 22'], services: [], coverage: 'full test suite' }] }] };
    writeFileSync(path.join(hookDir, 'billing-policies.json'), JSON.stringify(policy));
    writeFileSync(path.join(dir, 'rev-parse'), `const fs=require('fs'); const d=JSON.parse(fs.readFileSync('fixture.json')); process.stdout.write((process.env.GIT_DIR ? '${'f'.repeat(40)}' : (d.workspaceHead??d.head))+'\\n');`);
    writeFileSync(path.join(dir, 'status'), `const fs=require('fs'); if(JSON.parse(fs.readFileSync('fixture.json')).dirty) process.stdout.write(' M changed.txt\\n');`);
    const evidence = 'Independent review: no unresolved findings.\n';
    writeFileSync(path.join(dir, 'review.txt'), evidence);
    const review = { head_sha: head, outcome: 'passed', independent: true, required_checks: ['tests'], reviewer: 'codex review', evidence: 'review.txt', evidence_sha256: createHash('sha256').update(evidence).digest('hex') };
    writeFileSync(path.join(dir, 'review.json'), JSON.stringify(review));
    const env = { ...process.env, GIT_DIR: 'spoofed', PATH: `${bin}${path.delimiter}${process.env.PATH ?? ''}` };
    const invoke = (mode) => {
      writeFileSync(path.join(dir, 'counter.txt'), '0');
      writeFileSync(path.join(dir, 'checks-counter.txt'), '0');
      writeFileSync(path.join(dir, 'fixture.json'), JSON.stringify(payload));
      const result = spawnSync(process.execPath, [checker, mode, url, ...(mode === 'preflight' ? [path.join(dir, 'review.json')] : [])], { cwd: dir, env, encoding: 'utf8', timeout: 45000, windowsHide: true });
      if (result.error) throw new Error(`${mode} CLI spawn failed (status=${result.status}, signal=${result.signal}, code=${result.error.code}): ${result.error.message}`, { cause: result.error });
      assert.notEqual(result.status, null, `${mode} CLI terminated without an exit status (signal=${result.signal})`);
      return result;
    };
    assert.equal(invoke('preflight').status, 0, 'self-dependent pending check does not deadlock completed CI');
    const incorrectlyReady = [];
    for (const [description, checksAfter, checksStatusAfter, finalHead] of [
      ['a failed required check', [{ name: 'tests', bucket: 'fail' }, { name: 'pr-skills-check', bucket: 'pending' }]],
      ['a pending required check', [{ name: 'tests', bucket: 'pending' }, { name: 'pr-skills-check', bucket: 'pending' }]],
      ['a missing required check', [{ name: 'pr-skills-check', bucket: 'pending' }]],
      ['an additional failed check', [{ name: 'tests', bucket: 'pass' }, { name: 'lint', bucket: 'fail' }, { name: 'pr-skills-check', bucket: 'pending' }]],
      ['malformed check results', [{ name: 'tests' }, { name: 'pr-skills-check', bucket: 'pending' }]],
      ['the final check command is unavailable', [{ name: 'tests', bucket: 'pass' }], 2],
      ['the PR head changes during the final check', [{ name: 'tests', bucket: 'pass' }], 0, 'b'.repeat(40)],
    ]) {
      payload.checksAfter = checksAfter;
      payload.checksStatusAfter = checksStatusAfter;
      payload.finalHead = finalHead;
      const result = invoke('preflight');
      const expectedReason = finalHead ? /PR head or base changed/ : checksStatusAfter === 2 ? /Could not verify PR, CI, worktree or review evidence/ : /Hosted CI checks changed during preflight/;
      if (result.status !== 1 || !result.stdout.startsWith('NOT READY:') || !expectedReason.test(result.stdout)) incorrectlyReady.push({ description, status: result.status, stdout: result.stdout, stderr: result.stderr });
    }
    assert.deepEqual(incorrectlyReady, [], 'final hosted snapshot failures must block');
    delete payload.checksStatusAfter;
    delete payload.finalHead;
    payload.checksAfter = [{ name: 'tests', bucket: 'pass' }, { name: 'pr-skills-check', bucket: 'fail' }];
    assert.equal(invoke('preflight').status, 0, 'the self-dependent check may change without blocking green independent checks');
    payload.checksAfter = [{ name: 'tests', bucket: 'pass' }, { name: 'lint', bucket: 'pass' }, { name: 'pr-skills-check', bucket: 'pending' }];
    assert.equal(invoke('preflight').status, 0, 'an additional passing independent check remains valid');
    payload.checks[0].bucket = 'pending';
    assert.equal(invoke('preflight').status, 1, 'an initially pending check does not become ready from a later green snapshot');
    payload.checks[0].bucket = 'pass';
    delete payload.checksAfter;
    const unnoticedLocalChanges = [];
    for (const [description, effect, when, expectedReason] of [
      ['dirty worktree during the last check lookup', 'dirty', 'checksAfterEffect', /Workspace changed during preflight/],
      ['workspace head changes during the last check lookup', 'workspaceHead', 'checksAfterEffect', /Workspace changed during preflight/],
      ['review evidence changes during the last check lookup', 'reviewEvidence', 'checksAfterEffect', /Review evidence or CI policy changed during preflight/],
      ['review record changes during the last check lookup', 'reviewRecord', 'checksAfterEffect', /Review evidence or CI policy changed during preflight/],
      ['trusted policy changes during the last check lookup', 'policy', 'checksAfterEffect', /Review evidence or CI policy changed during preflight/],
      ['dirty worktree during the final PR view', 'dirty', 'finalViewEffect', /Workspace changed during preflight/],
      ['review evidence changes during the final PR view', 'reviewEvidence', 'finalViewEffect', /Review evidence or CI policy changed during preflight/],
    ]) {
      payload[when] = effect;
      const result = invoke('preflight');
      if (result.status !== 1 || !result.stdout.startsWith('NOT READY:') || !expectedReason.test(result.stdout)) unnoticedLocalChanges.push({ description, status: result.status, stdout: result.stdout, stderr: result.stderr });
      delete payload[when];
      writeFileSync(path.join(dir, 'review.txt'), evidence);
      writeFileSync(path.join(dir, 'review.json'), JSON.stringify(review));
      writeFileSync(path.join(hookDir, 'billing-policies.json'), JSON.stringify(policy));
    }
    assert.deepEqual(unnoticedLocalChanges, [], 'local changes during the final GitHub lookups must block');
    assert.equal(invoke('marker').status, 0);
    payload.commentsAfter = [comment(positive), comment({ ...positive, knip: 'failed' })];
    assert.equal(invoke('marker').status, 1, 'new failed marker on the same head must block');
    delete payload.commentsAfter;
    payload.after = 'b'.repeat(40);
    assert.equal(invoke('preflight').status, 1, 'head changes during checks');
    assert.equal(invoke('marker').status, 1, 'head changes during marker lookup');
    payload.after = head; payload.checks[0].bucket = 'pending';
    assert.equal(invoke('preflight').status, 1, 'CI is pending');
    payload.checks[0].bucket = 'fail';
    const blockEvidence = 'GitHub Actions blocked by billing/spending limit.\n';
    const gateEvidence = 'npm test: full suite passed on current head.\n';
    const fallbackReview = 'Independent review confirms the billing evidence and each local CI-equivalent gate.\n';
    writeFileSync(path.join(dir, 'billing.txt'), blockEvidence);
    writeFileSync(path.join(dir, 'gate.txt'), gateEvidence);
    writeFileSync(path.join(dir, 'fallback-review.txt'), fallbackReview);
    review.billing_fallback = { kind: 'github_billing', head_sha: head, pr_url: url, confirmed_by: 'reviewer', billing_block_confirmed: true,
      billing_blocked_checks: ['tests'], block_evidence: 'billing.txt', block_evidence_sha256: createHash('sha256').update(blockEvidence).digest('hex'),
      billing_proofs: [{ run_id: 101, job_id: 202, check_run_id: 303, attempt: 1 }],
      gates: [{ name: 'tests', head_sha: head, outcome: 'passed', exit_code: 0, equivalent: true, commands: ['npm test'], tool_versions: ['node 22'], services: [], coverage: 'full test suite', evidence: 'gate.txt', evidence_sha256: createHash('sha256').update(gateEvidence).digest('hex') }] };
    const syncBillingReview = () => { review.billing_review = { head_sha: head, outcome: 'passed', independent: true, reviewer: 'independent reviewer', verified_fallback_sha256: createHash('sha256').update(JSON.stringify(review.billing_fallback)).digest('hex'), evidence: 'fallback-review.txt', evidence_sha256: createHash('sha256').update(fallbackReview).digest('hex') }; };
    syncBillingReview();
    writeFileSync(path.join(dir, 'review.json'), JSON.stringify(review));
    const local = invoke('preflight');
    assert.equal(local.status, 0, local.stdout + local.stderr);
    assert.match(local.stdout, /READY LOCAL BILLING FALLBACK.*hosted CI.*not green/i);
    payload.checks[0].bucket = 'pass';
    payload.checksAfter = [{ name: 'tests', bucket: 'fail' }, { name: 'pr-skills-check', bucket: 'pending' }];
    const failedAfterGreen = invoke('preflight');
    assert.equal(failedAfterGreen.status, 1, 'a newly failed hosted check must not switch to an earlier billing fallback');
    assert.match(failedAfterGreen.stdout, /NOT READY: Hosted CI checks changed during preflight/);
    delete payload.checksAfter;
    payload.checks[0].bucket = 'fail';
    policy.policies[0].gates[0].runtime_reference_required = true;
    writeFileSync(path.join(hookDir, 'billing-policies.json'), JSON.stringify(policy));
    assert.equal(invoke('preflight').status, 1, 'an unpinned Node runtime needs reviewed version evidence');
    review.billing_fallback.gates[0].runtime_reference = { runner_image: 'ubuntu-24.04/20261020', hosted_node_version: '22.19.0', local_node_version: '22.19.0', reference_url: 'https://github.com/actions/runner-images/releases/tag/ubuntu24%2F20261020.1', evidence: 'gate.txt', evidence_sha256: createHash('sha256').update(gateEvidence).digest('hex') };
    syncBillingReview(); writeFileSync(path.join(dir, 'review.json'), JSON.stringify(review));
    assert.equal(invoke('preflight').status, 0, 'matching reviewed runtime evidence satisfies an unpinned policy');
    review.billing_fallback.gates[0].runtime_reference.local_node_version = '24.1.0';
    syncBillingReview(); writeFileSync(path.join(dir, 'review.json'), JSON.stringify(review));
    assert.equal(invoke('preflight').status, 1, 'different local Node version must block');
    delete review.billing_fallback.gates[0].runtime_reference;
    delete policy.policies[0].gates[0].runtime_reference_required;
    syncBillingReview(); writeFileSync(path.join(dir, 'review.json'), JSON.stringify(review));
    writeFileSync(path.join(hookDir, 'billing-policies.json'), JSON.stringify(policy));
    payload.annotations = [{ annotation_level: 'failure', message: 'The job was not started because your account is locked due to a billing issue.' }];
    assert.equal(invoke('preflight').status, 0, 'GitHub account-locked billing annotation is also recognized');
    const securityGate = { name: 'security', workflow: '.github/workflows/ci.yml', commands: ['npm audit'], tool_versions: ['node 22'], services: [], coverage: 'full audit' };
    policy.policies[0].gates.push(securityGate);
    writeFileSync(path.join(hookDir, 'billing-policies.json'), JSON.stringify(policy));
    review.required_checks.push('security');
    review.billing_fallback.gates.push({ ...securityGate, head_sha: head, outcome: 'passed', exit_code: 0, equivalent: true, evidence: 'gate.txt', evidence_sha256: createHash('sha256').update(gateEvidence).digest('hex') });
    syncBillingReview();
    writeFileSync(path.join(dir, 'review.json'), JSON.stringify(review));
    payload.checks.push({ name: 'security', bucket: 'pass', link: 'https://github.com/acme/widget/actions/runs/101/job/204' });
    assert.equal(invoke('preflight').status, 0, 'a verified passing policy job may coexist with a billing-blocked job');
    payload.greenJob.head_sha = 'b'.repeat(40);
    assert.equal(invoke('preflight').status, 1, 'a passing job from another head cannot satisfy the policy');
    payload.greenJob.head_sha = head;
    payload.checks.pop();
    review.required_checks.pop(); review.billing_fallback.gates.pop(); policy.policies[0].gates.pop(); syncBillingReview();
    writeFileSync(path.join(dir, 'review.json'), JSON.stringify(review));
    writeFileSync(path.join(hookDir, 'billing-policies.json'), JSON.stringify(policy));
    payload.run.run_attempt = 2;
    assert.equal(invoke('preflight').status, 1, 'old billing attempt must not survive a rerun');
    payload.run.run_attempt = 1;
    payload.run.head_branch = 'different';
    assert.equal(invoke('preflight').status, 1, 'an unrelated branch must not be accepted when GitHub omits PR association');
    payload.run.head_branch = 'feature/test';
    payload.run.path = '.github/workflows/other.yml';
    assert.equal(invoke('preflight').status, 1, 'billing proof from another workflow must block');
    payload.run.path = '.github/workflows/ci.yml';
    payload.check.app.id = 1;
    assert.equal(invoke('preflight').status, 1, 'an annotation from a different GitHub app must block');
    payload.check.app.id = 15368;
    policy.policies[0].workflows[0].sha256 = 'f'.repeat(64);
    writeFileSync(path.join(hookDir, 'billing-policies.json'), JSON.stringify(policy));
    assert.equal(invoke('preflight').status, 1, 'changed workflow must invalidate the trusted policy');
    policy.policies[0].workflows[0].sha256 = workflowHash;
    writeFileSync(path.join(hookDir, 'billing-policies.json'), JSON.stringify(policy));
    payload.job.steps = [{ name: 'Run tests', status: 'completed', conclusion: 'failure' }];
    assert.equal(invoke('preflight').status, 1, 'a started job is not a billing block');
    payload.job.steps = [];
    payload.annotations = [{ annotation_level: 'failure', message: 'Tests failed' }];
    assert.equal(invoke('preflight').status, 1, 'an unrelated GitHub failure must block');
    payload.annotations = [{ annotation_level: 'failure', message: "The job was not started because recent account payments have failed or your spending limit needs to be increased. Please check the 'Billing & plans' section in your settings" }];
    review.billing_review.independent = false;
    writeFileSync(path.join(dir, 'review.json'), JSON.stringify(review));
    assert.equal(invoke('preflight').status, 1, 'fallback evidence needs independent review');
    syncBillingReview();
    review.billing_review.verified_fallback_sha256 = 'f'.repeat(64);
    writeFileSync(path.join(dir, 'review.json'), JSON.stringify(review));
    assert.equal(invoke('preflight').status, 1, 'review must bind the exact fallback record');
    syncBillingReview();
    writeFileSync(path.join(dir, 'review.json'), JSON.stringify(review));
    writeFileSync(path.join(dir, 'gate.txt'), 'tampered');
    assert.equal(invoke('preflight').status, 1, 'tampered local evidence must block');
    writeFileSync(path.join(dir, 'gate.txt'), gateEvidence);
    payload.checks.push({ name: 'security', bucket: 'fail' });
    assert.equal(invoke('preflight').status, 1, 'unrelated failure must block even with fallback');
    payload.checks.pop();
    delete review.billing_fallback;
    writeFileSync(path.join(dir, 'review.json'), JSON.stringify(review));
    payload.checks[0].bucket = 'pass'; payload.dirty = true;
    assert.equal(invoke('preflight').status, 1, 'worktree is dirty');
    payload.dirty = false; writeFileSync(path.join(dir, 'review.txt'), 'tampered');
    assert.equal(invoke('preflight').status, 1, 'review evidence hash differs');
    payload.comments.push(comment({ ...positive, knip: 'failed' }));
    assert.equal(invoke('marker').status, 1, 'latest marker reports a failure');
  } finally { rmSync(dir, { recursive: true, force: true }); }
});
