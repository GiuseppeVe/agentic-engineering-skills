#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { readFileSync, statSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const SHA = /^[a-f0-9]{40}$/i;
const HASH = /^[a-f0-9]{64}$/i;
const URL = /^https:\/\/github\.com\/[\w.-]+\/[\w.-]+\/pull\/\d+$/i;
const TRUSTED = new Set(['OWNER', 'MEMBER', 'COLLABORATOR']);
const SUCCESS = new Set(['passed', 'applied', 'no_changes']);
const MARKER = /^<!--\s*pr-skills:v1\s+(\{[^\r\n]*\})\s*-->/;
const SELF_CHECK = 'pr-skills-check';
const blocked = (reason) => ({ ready: false, reason });

// Review evidence is a recorded assertion, not proof of the review's quality.
export function assessPreflight({ headBefore, headAfter, workspaceHead, clean, state, checks, review, evidenceExists, prUrl, fallbackEvidenceValid, fallbackReviewValid, trustedPolicy, billingVerified }) {
  if (!SHA.test(headBefore ?? '') || headBefore !== headAfter || headBefore !== workspaceHead) return blocked('PR or workspace head changed');
  if (state !== 'OPEN' || clean !== true) return blocked('PR is not open or worktree is dirty');
  if (!Array.isArray(checks) || checks.some(c => !c || typeof c.name !== 'string' || typeof c.bucket !== 'string')) return blocked('CI results unavailable');
  const independentChecks = checks.filter(c => c.name !== SELF_CHECK);
  if (!Array.isArray(review?.required_checks) || !review.required_checks.length || review.required_checks.some(name => typeof name !== 'string' || !name.trim() || name === SELF_CHECK) || new Set(review.required_checks).size !== review.required_checks.length) return blocked('Declared required CI checks are missing');
  if (!review || review.head_sha !== headBefore || review.outcome !== 'passed' || review.independent !== true ||
      typeof review.reviewer !== 'string' || !review.reviewer.trim() || typeof review.evidence !== 'string' || !review.evidence.trim() ||
      !HASH.test(review.evidence_sha256 ?? '') || evidenceExists !== true) return blocked('Independent review evidence missing, stale or unsuccessful');
  if (trustedPolicy && (!Array.isArray(trustedPolicy.gates) || !trustedPolicy.gates.length ||
      new Set(trustedPolicy.gates.map(g => g?.name)).size !== trustedPolicy.gates.length ||
      trustedPolicy.gates.length !== review.required_checks.length || trustedPolicy.gates.some(g => !g || typeof g.name !== 'string' || !review.required_checks.includes(g.name)))) return blocked('Declared checks do not match trusted CI policy');
  const hostedGreen = independentChecks.length > 0 && independentChecks.every(c => c.bucket === 'pass') && review.required_checks.every(name => independentChecks.some(c => c.name === name));
  if (hostedGreen) return { ready: true, head: headBefore, mode: 'hosted' };
  const fallback = review.billing_fallback;
  const nonGreen = independentChecks.filter(c => c.bucket !== 'pass').map(c => c.name);
  const missing = review.required_checks.filter(name => !independentChecks.some(c => c.name === name));
  if (!fallback || fallback.kind !== 'github_billing' || fallback.head_sha !== headBefore || fallback.pr_url !== prUrl || !URL.test(prUrl ?? '') ||
      fallback.billing_block_confirmed !== true || typeof fallback.confirmed_by !== 'string' || !fallback.confirmed_by.trim() || fallbackEvidenceValid !== true || fallbackReviewValid !== true ||
      !Array.isArray(fallback.billing_blocked_checks) || !fallback.billing_blocked_checks.length || new Set(fallback.billing_blocked_checks).size !== fallback.billing_blocked_checks.length ||
      fallback.billing_blocked_checks.some(name => typeof name !== 'string' || !review.required_checks.includes(name)) ||
      missing.length || !nonGreen.length || independentChecks.some(c => c.bucket !== 'pass' && c.bucket !== 'fail') ||
      new Set(independentChecks.map(c => c.name)).size !== independentChecks.length ||
      [...nonGreen, ...missing].some(name => !fallback.billing_blocked_checks.includes(name)) || fallback.billing_blocked_checks.some(name => !nonGreen.includes(name)) ||
      !Array.isArray(fallback.gates) || fallback.gates.length !== review.required_checks.length ||
      new Set(fallback.gates.map(gate => gate?.name)).size !== review.required_checks.length ||
      fallback.gates.some(gate => !gate || !review.required_checks.includes(gate.name) || gate.head_sha !== headBefore || gate.outcome !== 'passed' || gate.exit_code !== 0 || gate.equivalent !== true ||
        !Array.isArray(gate.commands) || !gate.commands.length || gate.commands.some(value => typeof value !== 'string' || !value.trim()) ||
        !Array.isArray(gate.tool_versions) || !gate.tool_versions.length || gate.tool_versions.some(value => typeof value !== 'string' || !value.trim()) ||
        !Array.isArray(gate.services) || gate.services.some(value => typeof value !== 'string' || !value.trim()) || typeof gate.coverage !== 'string' || !gate.coverage.trim())) return blocked('CI checks missing or not green; billing fallback evidence incomplete');
  const gates = trustedPolicy?.gates;
  if (billingVerified !== true || !Array.isArray(gates) || !gates.length ||
      gates.length !== review.required_checks.length || new Set(gates.map(g => g?.name)).size !== gates.length ||
      gates.some(g => !g || !review.required_checks.includes(g.name) ||
        !Array.isArray(g.commands) || !g.commands.length || g.commands.some(v => typeof v !== 'string' || !v.trim()) ||
        !Array.isArray(g.tool_versions) || !g.tool_versions.length || g.tool_versions.some(v => typeof v !== 'string' || !v.trim()) ||
        !Array.isArray(g.services) || g.services.some(v => typeof v !== 'string' || !v.trim()) || typeof g.coverage !== 'string' || !g.coverage.trim() ||
        !fallback.gates.some(actual => actual.name === g.name && JSON.stringify(actual.commands) === JSON.stringify(g.commands) &&
          JSON.stringify(actual.tool_versions) === JSON.stringify(g.tool_versions) && JSON.stringify(actual.services) === JSON.stringify(g.services) && actual.coverage === g.coverage &&
          (g.runtime_reference_required !== true || (actual.runtime_reference && typeof actual.runtime_reference.runner_image === 'string' && !!actual.runtime_reference.runner_image.trim() &&
            /^\d+\.\d+\.\d+$/.test(actual.runtime_reference.hosted_node_version ?? '') && actual.runtime_reference.local_node_version === actual.runtime_reference.hosted_node_version &&
            /^https:\/\/github\.com\/actions\/runner-images\/(?:releases\/tag|blob)\/[\w%./-]+$/i.test(actual.runtime_reference.reference_url ?? '') &&
            typeof actual.runtime_reference.evidence === 'string' && !!actual.runtime_reference.evidence.trim() && HASH.test(actual.runtime_reference.evidence_sha256 ?? '')))))) return blocked('Billing fallback lacks verified GitHub evidence or trusted complete policy');
  return { ready: true, head: headBefore, mode: 'billing_fallback' };
}

export function markerForHead(head, comments) {
  if (!SHA.test(head ?? '') || !Array.isArray(comments)) return blocked('Marker unavailable');
  let latest;
  for (const comment of comments) {
    if (!TRUSTED.has(comment?.authorAssociation) || typeof comment.body !== 'string') continue;
    if (!/^<!--\s*pr-skills:v1\b/.test(comment.body)) continue;
    const match = comment.body.match(MARKER);
    if (!match) { latest = undefined; continue; }
    try {
      const value = JSON.parse(match[1]);
      if (typeof value?.commit_sha !== 'string' || !SHA.test(value.commit_sha)) latest = undefined;
      else if (value.commit_sha === head) latest = value;
    } catch { latest = undefined; }
  }
  if (!latest || !SUCCESS.has(latest.knip) || !SUCCESS.has(latest.simplify)) return blocked('No successful current-head marker');
  return { ready: true, head, knip: latest.knip, simplify: latest.simplify };
}

function command(program, args, { allowed = [0] } = {}) {
  const env = Object.fromEntries(Object.entries(process.env).filter(([key]) => !/^GIT_/i.test(key)));
  const result = spawnSync(program, args, { env, encoding: 'utf8', timeout: 15000, maxBuffer: 2_000_000, windowsHide: true });
  if (result.error || !allowed.includes(result.status)) throw new Error(`${program} command unavailable or unsuccessful`);
  return result.stdout;
}
function view(url, fields) { return JSON.parse(command('gh', ['pr', 'view', url, '--json', fields])); }
function readTrustedPolicy(url, pr) {
  const match = url.match(/^https:\/\/github\.com\/([\w.-]+\/[\w.-]+)\/pull\/(\d+)$/i);
  if (!match || !SHA.test(pr.baseRefOid ?? '') || typeof pr.baseRefName !== 'string') throw new Error('PR base unavailable');
  let document;
  try { document = JSON.parse(readFileSync(resolve(dirname(fileURLToPath(import.meta.url)), 'billing-policies.json'), 'utf8')); }
  catch (error) { if (error.code === 'ENOENT') return null; throw error; }
  if (document?.version !== 1 || !Array.isArray(document.policies)) throw new Error('Invalid policy inventory');
  const matches = document.policies.filter(p => typeof p?.repository === 'string' && p.repository.toLowerCase() === match[1].toLowerCase() && p.base_ref === pr.baseRefName);
  if (!matches.length) return null;
  if (matches.length !== 1) throw new Error('No unique trusted policy');
  const policy = matches[0];
  if (!Array.isArray(policy.workflows) || !policy.workflows.length || policy.workflows.some(w => !w || !/^\.github\/workflows\/[\w.-]+\.ya?ml$/.test(w.path ?? '') || !HASH.test(w.sha256 ?? '')) ||
      new Set(policy.workflows.map(w => w.path)).size !== policy.workflows.length) throw new Error('Invalid workflow policy');
  if (!Array.isArray(policy.gates) || !policy.gates.length || policy.gates.some(g => !g || !policy.workflows.some(w => w.path === g.workflow))) throw new Error('Invalid gate-to-workflow mapping');
  const expected = policy.workflows.map(w => w.path).sort();
  for (const revision of [pr.baseRefOid, pr.headRefOid]) {
    if (!SHA.test(revision ?? '')) throw new Error('Invalid revision');
    const paths = command('git', ['ls-tree', '-r', '--name-only', revision, '--', '.github/workflows/']).split(/\r?\n/).filter(Boolean).sort();
    if (JSON.stringify(paths) !== JSON.stringify(expected)) throw new Error('Workflow inventory changed');
    for (const workflow of policy.workflows) {
      const content = command('git', ['show', `${revision}:${workflow.path}`]);
      if (createHash('sha256').update(content).digest('hex') !== workflow.sha256.toLowerCase()) throw new Error('Workflow changed');
    }
  }
  return policy;
}
function runMatchesPr(run, repo, number, pr) {
  return run?.event === 'pull_request' && run.head_sha === pr.headRefOid && run.head_branch === pr.headRefName &&
    run.repository?.full_name?.toLowerCase() === repo.toLowerCase() && run.head_repository?.full_name?.toLowerCase() === repo.toLowerCase() &&
    Array.isArray(run.pull_requests) && (run.pull_requests.length === 0 || run.pull_requests.some(item => item.number === number));
}
function verifyPassingPolicyJobs(url, pr, checks, policy) {
  const match = url.match(/^https:\/\/github\.com\/([\w.-]+\/[\w.-]+)\/pull\/(\d+)$/i);
  if (!match || !Array.isArray(checks)) return false;
  const root = `repos/${match[1]}`;
  const readApi = path => JSON.parse(command('gh', ['api', path]));
  for (const gate of policy.gates) {
    const entry = checks.find(c => c.name === gate.name);
    if (!entry || entry.bucket !== 'pass') continue;
    const link = typeof entry.link === 'string' && entry.link.match(/^https:\/\/github\.com\/([\w.-]+\/[\w.-]+)\/actions\/runs\/(\d+)\/job\/(\d+)$/i);
    if (!link || link[1].toLowerCase() !== match[1].toLowerCase()) return false;
    const runId = Number(link[2]), jobId = Number(link[3]);
    if (![runId, jobId].every(n => Number.isSafeInteger(n) && n > 0)) return false;
    const run = readApi(`${root}/actions/runs/${runId}`);
    const job = readApi(`${root}/actions/jobs/${jobId}`);
    const checkUrl = typeof job.check_run_url === 'string' && job.check_run_url.match(/^https:\/\/api\.github\.com\/repos\/([\w.-]+\/[\w.-]+)\/check-runs\/(\d+)$/i);
    if (!checkUrl || checkUrl[1].toLowerCase() !== match[1].toLowerCase()) return false;
    const checkId = Number(checkUrl[2]);
    if (!Number.isSafeInteger(checkId) || checkId <= 0) return false;
    const check = readApi(`${root}/check-runs/${checkId}`);
    if (run.id !== runId || !runMatchesPr(run, match[1], Number(match[2]), pr) || run.status !== 'completed' || run.path !== gate.workflow ||
        job.id !== jobId || job.run_id !== runId || job.run_attempt !== run.run_attempt || job.head_sha !== pr.headRefOid || job.name !== gate.name || job.status !== 'completed' || job.conclusion !== 'success' ||
        check.id !== checkId || check.head_sha !== pr.headRefOid || check.name !== gate.name || check.status !== 'completed' || check.conclusion !== 'success' ||
        check.app?.id !== 15368 || check.app?.slug !== 'github-actions' || check.app?.owner?.login !== 'github') return false;
  }
  return true;
}
function verifyGitHubBilling(url, pr, fallback, checks, policy) {
  const match = url.match(/^https:\/\/github\.com\/([\w.-]+\/[\w.-]+)\/pull\/(\d+)$/i);
  const head = pr.headRefOid;
  if (!match || !SHA.test(head ?? '') || typeof pr.headRefName !== 'string' || !pr.headRefName || !Array.isArray(fallback?.billing_proofs) || !Array.isArray(fallback.billing_blocked_checks)) return false;
  const names = fallback.billing_blocked_checks;
  if (fallback.billing_proofs.length !== names.length || !names.length) return false;
  const seen = new Set();
  const readApi = path => JSON.parse(command('gh', ['api', path]));
  const billingMessage = /^(?:The job was not started because your account is locked due to a billing issue\.|The job was not started because recent account payments have failed or your spending limit needs to be increased\. Please check the 'Billing & plans' section in your settings\.?)$/i;
  for (const proof of fallback.billing_proofs) {
    if (!proof || ![proof.run_id, proof.job_id, proof.check_run_id, proof.attempt].every(n => Number.isSafeInteger(n) && n > 0)) return false;
    const root = `repos/${match[1]}`;
    const run = readApi(`${root}/actions/runs/${proof.run_id}`);
    const job = readApi(`${root}/actions/jobs/${proof.job_id}`);
    const check = readApi(`${root}/check-runs/${proof.check_run_id}`);
    const annotations = readApi(`${root}/check-runs/${proof.check_run_id}/annotations`);
    const expectedCheckUrl = `https://api.github.com/repos/${match[1]}/check-runs/${proof.check_run_id}`.toLowerCase();
    if (run.id !== proof.run_id || run.run_attempt !== proof.attempt || !runMatchesPr(run, match[1], Number(match[2]), pr) || run.status !== 'completed' || run.conclusion !== 'failure' ||
        job.id !== proof.job_id || job.run_id !== proof.run_id || job.run_attempt !== proof.attempt || job.head_sha !== head ||
        job.status !== 'completed' || job.conclusion !== 'failure' || job.runner_id !== 0 || !Array.isArray(job.steps) || job.steps.length !== 0 ||
        typeof job.check_run_url !== 'string' || job.check_run_url.toLowerCase() !== expectedCheckUrl ||
        check.id !== proof.check_run_id || check.head_sha !== head || check.name !== job.name || check.status !== 'completed' || check.conclusion !== 'failure' ||
        check.app?.id !== 15368 || check.app?.slug !== 'github-actions' || check.app?.owner?.login !== 'github' ||
        !Array.isArray(annotations) || !annotations.some(a => a?.annotation_level === 'failure' && typeof a.message === 'string' && billingMessage.test(a.message.trim())) ||
        !names.includes(job.name) || !policy.gates.some(g => g.name === job.name && g.workflow === run.path) || seen.has(job.name) || !checks.some(c => c.name === job.name && c.bucket === 'fail')) return false;
    seen.add(job.name);
  }
  return names.every(name => seen.has(name));
}
function validEvidence(recordPath, entry) {
  if (!entry || typeof entry.evidence !== 'string' || !entry.evidence.trim() || !HASH.test(entry.evidence_sha256 ?? '')) return false;
  const evidencePath = resolve(dirname(recordPath), entry.evidence);
  const size = statSync(evidencePath).size;
  if (size < 1 || size > 4_000_000) return false;
  return createHash('sha256').update(readFileSync(evidencePath)).digest('hex') === entry.evidence_sha256.toLowerCase();
}
function readReview(path) {
  const recordPath = resolve(path);
  if (statSync(recordPath).size > 1_000_000) throw new Error('Review record too large');
  const review = JSON.parse(readFileSync(recordPath, 'utf8'));
  const evidenceExists = validEvidence(recordPath, review);
  let fallbackEvidenceValid = false;
  let fallbackReviewValid = false;
  if (review.billing_fallback) {
    const fb = review.billing_fallback;
    try {
      fallbackEvidenceValid = validEvidence(recordPath, { evidence: fb.block_evidence, evidence_sha256: fb.block_evidence_sha256 }) &&
        Array.isArray(fb.gates) && fb.gates.length > 0 && fb.gates.every(gate => validEvidence(recordPath, gate) && (!gate.runtime_reference || validEvidence(recordPath, gate.runtime_reference)));
      const audit = review.billing_review;
      fallbackReviewValid = !!audit && audit.head_sha === review.head_sha && audit.outcome === 'passed' && audit.independent === true &&
        typeof audit.reviewer === 'string' && !!audit.reviewer.trim() && HASH.test(audit.verified_fallback_sha256 ?? '') &&
        createHash('sha256').update(JSON.stringify(fb)).digest('hex') === audit.verified_fallback_sha256.toLowerCase() && validEvidence(recordPath, audit);
    } catch { fallbackEvidenceValid = false; fallbackReviewValid = false; }
  }
  return { review, evidenceExists, fallbackEvidenceValid, fallbackReviewValid };
}
export function runCli(argv) {
  const [mode, url, reviewPath, ...extra] = argv;
  if (!['preflight', 'marker'].includes(mode) || !URL.test(url ?? '') || extra.length || (mode === 'preflight' && !reviewPath) || (mode === 'marker' && reviewPath)) return blocked('Usage: preflight <GitHub PR URL> <review-record.json> | marker <GitHub PR URL>');
  try {
    const before = view(url, mode === 'marker' ? 'headRefOid,state,comments' : 'headRefOid,headRefName,state,baseRefOid,baseRefName');
    if (mode === 'marker') {
      const result = markerForHead(before.headRefOid, before.comments);
      const after = view(url, 'headRefOid,state,comments');
      if (before.state !== 'OPEN' || after.state !== 'OPEN' || before.headRefOid !== after.headRefOid) return blocked('PR head changed or PR closed');
      return result.ready ? markerForHead(after.headRefOid, after.comments) : result;
    }
    const workspaceHead = command('git', ['rev-parse', 'HEAD']).trim();
    const clean = command('git', ['status', '--porcelain']).trim() === '';
    const checks = JSON.parse(command('gh', ['pr', 'checks', url, '--json', 'name,bucket,link'], { allowed: [0, 1, 8] }));
    const review = readReview(reviewPath);
    const trustedPolicy = readTrustedPolicy(url, before);
    const inputs = { headBefore: before.headRefOid, headAfter: before.headRefOid, workspaceHead, clean, state: before.state, checks, prUrl: url, trustedPolicy, ...review };
    let result = assessPreflight(inputs);
    if (!result.ready && review.review?.billing_fallback && review.fallbackEvidenceValid && review.fallbackReviewValid) {
      try {
        if (!trustedPolicy) throw new Error('No trusted policy for billing fallback');
        const billingVerified = verifyGitHubBilling(url, before, review.review.billing_fallback, checks, trustedPolicy) && verifyPassingPolicyJobs(url, before, checks, trustedPolicy);
        result = assessPreflight({ ...inputs, trustedPolicy, billingVerified });
        if (result.ready) {
          const latestChecks = JSON.parse(command('gh', ['pr', 'checks', url, '--json', 'name,bucket,link'], { allowed: [0, 1, 8] }));
          const stable = values => JSON.stringify(values.map(c => [c.name, c.bucket, c.link]).sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b))));
          if (stable(checks) !== stable(latestChecks) || !verifyGitHubBilling(url, before, review.review.billing_fallback, latestChecks, trustedPolicy) || !verifyPassingPolicyJobs(url, before, latestChecks, trustedPolicy)) return blocked('GitHub billing checks changed during preflight');
        }
      } catch { return blocked('Could not verify trusted billing policy or GitHub billing evidence'); }
    }
    const after = view(url, 'headRefOid,headRefName,state,baseRefOid,baseRefName');
    if (before.state !== 'OPEN' || after.state !== 'OPEN' || before.headRefOid !== after.headRefOid || before.headRefName !== after.headRefName || before.baseRefOid !== after.baseRefOid || before.baseRefName !== after.baseRefName) return blocked('PR head or base changed or PR closed');
    if (command('git', ['rev-parse', 'HEAD']).trim() !== workspaceHead || command('git', ['status', '--porcelain']).trim() !== '') return blocked('Workspace changed during preflight');
    if (result.ready && (JSON.stringify(readReview(reviewPath)) !== JSON.stringify(review) || JSON.stringify(readTrustedPolicy(url, after)) !== JSON.stringify(trustedPolicy))) return blocked('Review evidence or CI policy changed during preflight');
    return result;
  } catch { return blocked('Could not verify PR, CI, worktree or review evidence'); }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const result = runCli(process.argv.slice(2));
  const label = result.ready ? (result.mode === 'billing_fallback' ? 'READY LOCAL BILLING FALLBACK (hosted CI is not green)' : 'READY') : 'NOT READY';
  process.stdout.write(`${label}: ${result.ready ? result.head : result.reason}\n`);
  if (!result.ready) process.exitCode = 1;
}
