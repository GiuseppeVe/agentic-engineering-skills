#!/usr/bin/env node
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';

function args(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i += 2) {
    if (!argv[i]?.startsWith('--') || argv[i + 1] === undefined) throw new Error(`Invalid argument: ${argv[i] ?? ''}`);
    out[argv[i].slice(2)] = argv[i + 1];
  }
  return out;
}

function stable(value) {
  if (Array.isArray(value)) return `[${value.map(stable).join(',')}]`;
  if (value && typeof value === 'object') return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${stable(value[key])}`).join(',')}}`;
  return JSON.stringify(value);
}

async function emit(path, value) {
  await mkdir(dirname(resolve(path)), { recursive: true });
  await writeFile(path, `${JSON.stringify(value, null, 2)}\n`);
}

function index(receipt, label, failures) {
  const cells = Array.isArray(receipt.cells) ? receipt.cells : [];
  const map = new Map();
  for (const cell of cells) {
    if (!cell || typeof cell.id !== 'string' || map.has(cell.id)) {
      failures.push({ class: 'INCOMPLETE_MATRIX', side: label, cellId: cell?.id ?? null, reason: 'invalid or duplicate cell ID' });
    } else map.set(cell.id, cell);
  }
  return map;
}

async function main() {
  const opt = args(process.argv.slice(2));
  if (!opt.reference || !opt.candidate || !opt.out) throw new Error('Required: --reference --candidate --out');
  const reference = JSON.parse(await readFile(opt.reference, 'utf8'));
  const candidate = JSON.parse(await readFile(opt.candidate, 'utf8'));
  const failures = [];
  if (reference.status !== 'COMPLETE') failures.push({ class: 'INCOMPLETE_MATRIX', side: 'reference', reason: 'capture receipt is not COMPLETE' });
  if (candidate.status !== 'COMPLETE') failures.push({ class: 'INCOMPLETE_MATRIX', side: 'candidate', reason: 'capture receipt is not COMPLETE' });
  if (reference.side && reference.side !== 'reference') failures.push({ class: 'INCOMPLETE_MATRIX', side: 'reference', reason: 'wrong receipt side' });
  if (candidate.side && candidate.side !== 'candidate') failures.push({ class: 'INCOMPLETE_MATRIX', side: 'candidate', reason: 'wrong receipt side' });
  if (!candidate.candidateSha || typeof candidate.candidateSha !== 'string') failures.push({ class: 'INCOMPLETE_MATRIX', side: 'candidate', reason: 'candidate SHA missing' });
  if (reference.sourceSha256 !== candidate.sourceSha256) failures.push({ class: 'INCOMPLETE_MATRIX', reason: 'source SHA differs', referenceSourceSha256: reference.sourceSha256 ?? null, candidateSourceSha256: candidate.sourceSha256 ?? null });
  if (reference.contractSha256 !== candidate.contractSha256) failures.push({ class: 'INCOMPLETE_MATRIX', reason: 'contract SHA differs', referenceContractSha256: reference.contractSha256 ?? null, candidateContractSha256: candidate.contractSha256 ?? null });
  if (stable(reference.setup ?? null) !== stable(candidate.setup ?? null)) failures.push({ class: 'INCOMPLETE_MATRIX', reason: 'capture setup differs' });

  const refs = index(reference, 'reference', failures);
  const candidates = index(candidate, 'candidate', failures);
  const referenceExpected = reference.summary?.expected;
  const candidateExpected = candidate.summary?.expected;
  if (!Number.isInteger(referenceExpected) || referenceExpected !== refs.size) failures.push({ class: 'INCOMPLETE_MATRIX', side: 'reference', reason: 'expected cell count does not match receipt cells', expected: referenceExpected ?? null, actual: refs.size });
  if (!Number.isInteger(candidateExpected) || candidateExpected !== candidates.size) failures.push({ class: 'INCOMPLETE_MATRIX', side: 'candidate', reason: 'expected cell count does not match receipt cells', expected: candidateExpected ?? null, actual: candidates.size });
  if (referenceExpected !== candidateExpected) failures.push({ class: 'INCOMPLETE_MATRIX', reason: 'expected matrix sizes differ', referenceExpected: referenceExpected ?? null, candidateExpected: candidateExpected ?? null });
  const ids = [...new Set([...refs.keys(), ...candidates.keys()])].sort();
  let exactMatches = 0;
  let missing = 0;
  let setupMismatches = 0;
  let hashMismatches = 0;
  for (const id of ids) {
    const ref = refs.get(id);
    const candidateCell = candidates.get(id);
    if (!ref || !candidateCell || ref.status !== 'CAPTURED' || candidateCell.status !== 'CAPTURED' || !ref.sha256 || !candidateCell.sha256) {
      missing += 1;
      failures.push({ class: 'INCOMPLETE_MATRIX', cellId: id, reason: 'capture missing or incomplete', referenceStatus: ref?.status ?? 'ABSENT', candidateStatus: candidateCell?.status ?? 'ABSENT' });
    } else if (stable(ref.setup) !== stable(candidateCell.setup)) {
      setupMismatches += 1;
      failures.push({ class: 'INCOMPLETE_MATRIX', cellId: id, reason: 'cell setup differs' });
    } else if (ref.sha256 !== candidateCell.sha256) {
      hashMismatches += 1;
      failures.push({ class: 'IMPORT_DEFECT', cellId: id, reason: 'capture SHA-256 differs', referenceSha256: ref.sha256, candidateSha256: candidateCell.sha256 });
    } else exactMatches += 1;
  }
  if (refs.size !== candidates.size) {
    failures.push({ class: 'INCOMPLETE_MATRIX', reason: 'receipt cell counts differ', referenceCells: refs.size, candidateCells: candidates.size });
  }

  const receipt = {
    schemaVersion: 1,
    kind: 'handoff-validation-receipt',
    status: failures.length ? 'FAIL' : 'PASS',
    failureClass: failures.some((failure) => failure.class === 'INCOMPLETE_MATRIX') ? 'INCOMPLETE_MATRIX' : failures.length ? 'IMPORT_DEFECT' : null,
    policy: { comparison: 'EXACT_SHA256', geometryMasksAllowed: false, materialThresholdAllowed: false },
    sourceSha256: reference.sourceSha256 ?? null,
    candidateSha: candidate.candidateSha ?? null,
    summary: { expected: Number.isInteger(referenceExpected) ? referenceExpected : refs.size, exactMatches, missing, setupMismatches, hashMismatches },
    failures,
  };
  await emit(opt.out, receipt);
  if (failures.length) {
    console.error(`${receipt.failureClass}: ${failures.length} comparison failure(s)`);
    process.exitCode = 1;
  }
}

try {
  await main();
} catch (error) {
  const out = (() => { try { return args(process.argv.slice(2)).out; } catch { return null; } })();
  const value = { schemaVersion: 1, kind: 'handoff-validation-receipt', status: 'FAIL', failureClass: 'INCOMPLETE_MATRIX', policy: { comparison: 'EXACT_SHA256', geometryMasksAllowed: false, materialThresholdAllowed: false }, summary: { expected: 0, exactMatches: 0, missing: 0, setupMismatches: 0, hashMismatches: 0 }, failures: [{ class: 'INCOMPLETE_MATRIX', reason: error.message }] };
  if (out) await emit(out, value).catch(() => {});
  console.error(`INCOMPLETE_MATRIX: ${error.message}`);
  process.exitCode = 1;
}
