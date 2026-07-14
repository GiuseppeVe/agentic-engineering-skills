#!/usr/bin/env node
import { mkdir, readFile, stat, writeFile } from 'node:fs/promises';
import { dirname, isAbsolute, resolve } from 'node:path';

const REQUIRED_DOCUMENTS = ['source-manifest.json', 'handoff-contract.json', 'compatibility-map.md', 'deviation-ledger.md', 'validation-receipt.json'];

function args(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i += 2) {
    if (!argv[i]?.startsWith('--') || argv[i + 1] === undefined) throw new Error(`Invalid argument: ${argv[i] ?? ''}`);
    out[argv[i].slice(2)] = argv[i + 1];
  }
  return out;
}

const normalized = (value) => String(value).replace(/\\/g, '/').replace(/^\.\//, '');
function glob(pattern) {
  let source = '^';
  const value = normalized(pattern);
  for (let i = 0; i < value.length; i += 1) {
    const char = value[i];
    if (char === '*' && value[i + 1] === '*') { source += '.*'; i += 1; }
    else if (char === '*') source += '[^/]*';
    else if (char === '?') source += '[^/]';
    else source += char.replace(/[|\\{}()[\]^$+?.]/g, '\\$&');
  }
  return new RegExp(`${source}$`);
}

async function emit(path, value) {
  await mkdir(dirname(resolve(path)), { recursive: true });
  await writeFile(path, `${JSON.stringify(value, null, 2)}\n`);
}

async function main() {
  const opt = args(process.argv.slice(2));
  if (!opt.config || !opt.receipt) throw new Error('Required: --config --receipt');
  const configPath = resolve(opt.config);
  const config = JSON.parse(await readFile(configPath, 'utf8'));
  const checks = [];
  const failures = [];
  const check = (id, pass, details) => {
    checks.push({ id, status: pass ? 'PASS' : 'FAIL', ...details });
    if (!pass) failures.push({ class: 'SCOPE_VIOLATION', check: id, ...details });
  };

  const candidateSha = config.candidateSha;
  check('candidate-sha', typeof candidateSha === 'string' && candidateSha.length > 0, { reason: typeof candidateSha === 'string' && candidateSha.length ? undefined : 'candidateSha missing' });

  const files = Array.isArray(config.implementationFiles) ? config.implementationFiles : [];
  const patterns = Array.isArray(config.allowedPaths) ? config.allowedPaths : [];
  const matchers = patterns.map(glob);
  const outside = files.filter((file) => {
    const path = normalized(file);
    return !path || isAbsolute(path) || path.split('/').includes('..') || !matchers.some((matcher) => matcher.test(path));
  });
  check('allowed-paths', files.length > 0 && patterns.length > 0 && outside.length === 0, { outsideAllowedPaths: outside });

  const documents = Array.isArray(config.requiredDocuments) ? config.requiredDocuments : [];
  const documentNames = new Set(documents.map((path) => normalized(path).split('/').pop()));
  const omitted = REQUIRED_DOCUMENTS.filter((name) => !documentNames.has(name));
  const absent = [];
  for (const path of documents) {
    const absolute = isAbsolute(path) ? path : resolve(dirname(configPath), path);
    try { if (!(await stat(absolute)).isFile()) absent.push(path); } catch { absent.push(path); }
  }
  check('required-documents', omitted.length === 0 && absent.length === 0, { omitted, absent });

  let validation = null;
  let validationError = null;
  try {
    if (!config.validationReceipt) throw new Error('validationReceipt missing');
    const path = isAbsolute(config.validationReceipt) ? config.validationReceipt : resolve(dirname(configPath), config.validationReceipt);
    validation = JSON.parse(await readFile(path, 'utf8'));
  } catch (error) { validationError = error.message; }
  check('validation-receipt', !validationError && validation?.status === 'PASS' && validation?.candidateSha === candidateSha, { reason: validationError, status: validation?.status ?? null, receiptSha: validation?.candidateSha ?? null });

  const reviews = Array.isArray(config.reviews) ? config.reviews : [];
  for (const kind of ['spec', 'quality']) {
    const approved = reviews.some((review) => review?.kind === kind && review?.verdict === 'APPROVED' && review?.sha === candidateSha);
    check(`${kind}-review`, approved, { requiredVerdict: 'APPROVED', requiredSha: candidateSha });
  }
  const deviations = Array.isArray(config.deviations) ? config.deviations : null;
  const invalidDeviations = deviations === null ? [{ reason: 'deviations array missing' }] : deviations.filter((deviation) => {
    const classAllowed = ['APP_BOUNDARY', 'REFERENCE_DEFECT'].includes(deviation?.class);
    const independent = typeof deviation?.implementer === 'string' && typeof deviation?.independentApprover === 'string' && deviation.implementer !== deviation.independentApprover;
    return !classAllowed || deviation?.approval !== 'APPROVED' || !independent || deviation?.approvedSha !== candidateSha;
  });
  check('deviation-approvals', invalidDeviations.length === 0, { invalid: invalidDeviations });
  check('implementer-no-commit', config.implementerCommitted === false, { actual: config.implementerCommitted });
  check('controller-exact-stage', config.controllerStagesExact === true, { actual: config.controllerStagesExact });
  check('publication-user-gate', config.publicationGate === 'PENDING_USER', { actual: config.publicationGate });

  const receipt = { schemaVersion: 1, kind: 'import-scope-receipt', status: failures.length ? 'FAIL' : 'PASS', candidateSha: candidateSha ?? null, checks, failures };
  await emit(opt.receipt, receipt);
  if (failures.length) {
    console.error(`SCOPE_VIOLATION: ${failures.length} gate(s) failed`);
    process.exitCode = 1;
  }
}

try {
  await main();
} catch (error) {
  const receipt = (() => { try { return args(process.argv.slice(2)).receipt; } catch { return null; } })();
  const value = { schemaVersion: 1, kind: 'import-scope-receipt', status: 'FAIL', checks: [], failures: [{ class: 'SCOPE_VIOLATION', check: 'configuration', reason: error.message }] };
  if (receipt) await emit(receipt, value).catch(() => {});
  console.error(`SCOPE_VIOLATION: ${error.message}`);
  process.exitCode = 1;
}
