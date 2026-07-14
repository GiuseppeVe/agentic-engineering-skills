#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { mkdir, readFile, rm, stat, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';

function args(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i += 2) {
    if (!argv[i]?.startsWith('--') || argv[i + 1] === undefined) throw new Error(`Invalid argument: ${argv[i] ?? ''}`);
    out[argv[i].slice(2)] = argv[i + 1];
  }
  return out;
}

const sha256 = (value) => createHash('sha256').update(value).digest('hex');
const clean = (value) => String(value).replace(/[^a-z0-9._-]+/gi, '-').replace(/^-|-$/g, '').slice(0, 48) || 'cell';

async function emit(path, value) {
  await mkdir(dirname(resolve(path)), { recursive: true });
  await writeFile(path, `${JSON.stringify(value, null, 2)}\n`);
}

function matrixCells(contract) {
  const matrix = contract.matrix;
  if (!matrix || !Array.isArray(matrix.routes) || !Array.isArray(matrix.languages) || !Array.isArray(matrix.viewports) || !Array.isArray(matrix.states)) {
    throw new Error('Contract matrix must define routes, languages, viewports, and states');
  }
  if ([matrix.routes, matrix.languages, matrix.viewports, matrix.states].some((values) => values.length === 0)) {
    throw new Error('Contract matrix dimensions cannot be empty');
  }
  const generated = [];
  for (const route of matrix.routes) for (const language of matrix.languages) for (const viewport of matrix.viewports) for (const state of matrix.states) {
    if (typeof route !== 'string' || typeof language !== 'string' || typeof state !== 'string' || !viewport || typeof viewport !== 'object') {
      throw new Error('Invalid contract matrix cell value');
    }
    const setup = { route, language, viewport, state };
    generated.push({ id: `${route}::${language}::${viewport.name ?? `${viewport.width}x${viewport.height}`}::${state}`, ...setup });
  }
  if (Array.isArray(matrix.cells)) {
    if (matrix.cells.length !== generated.length) throw new Error('Contract matrix.cells is not the complete Cartesian matrix');
    return matrix.cells.map((cell, index) => {
      const expected = generated[index];
      if (cell.route !== expected.route || cell.language !== expected.language || cell.state !== expected.state || JSON.stringify(cell.viewport) !== JSON.stringify(expected.viewport)) {
        throw new Error(`Contract matrix.cells differs from Cartesian matrix at index ${index}`);
      }
      return { id: String(cell.id || expected.id), route: cell.route, language: cell.language, viewport: cell.viewport, state: cell.state };
    });
  }
  return generated;
}

async function main() {
  const opt = args(process.argv.slice(2));
  if (!opt.contract || !opt.side || !opt.runner || !opt['out-dir'] || !opt.receipt) throw new Error('Required: --contract --side --runner --out-dir --receipt');
  if (!['reference', 'candidate'].includes(opt.side)) throw new Error('--side must be reference or candidate');
  const timeoutMs = Number(opt['timeout-ms'] ?? 30000);
  if (!Number.isInteger(timeoutMs) || timeoutMs <= 0) throw new Error('--timeout-ms must be a positive integer');
  const runner = JSON.parse(opt.runner);
  if (!Array.isArray(runner) || runner.length === 0 || runner.some((part) => typeof part !== 'string')) throw new Error('--runner must be a non-empty JSON argv array');

  const contractBytes = await readFile(opt.contract);
  const contract = JSON.parse(contractBytes.toString('utf8'));
  if (contract.completion?.complete === false) throw new Error('Contract is incomplete');
  const cells = matrixCells(contract);
  const seen = new Set();
  if (cells.some((cell) => seen.has(cell.id) || !seen.add(cell.id))) throw new Error('Contract matrix contains duplicate cell IDs');
  const outDir = resolve(opt['out-dir']);
  await mkdir(outDir, { recursive: true });
  const results = [];

  for (let index = 0; index < cells.length; index += 1) {
    const cell = cells[index];
    const outputPath = resolve(outDir, `${String(index + 1).padStart(4, '0')}-${clean(cell.id)}.png`);
    await rm(outputPath, { force: true });
    const setup = { route: cell.route, language: cell.language, viewport: cell.viewport, state: cell.state };
    const child = spawnSync(runner[0], runner.slice(1), {
      env: { ...process.env, HANDOFF_CELL_JSON: JSON.stringify({ id: cell.id, ...setup }), HANDOFF_OUTPUT_PATH: outputPath, HANDOFF_SIDE: opt.side },
      timeout: timeoutMs,
      encoding: 'utf8',
      maxBuffer: 1024 * 1024,
    });
    let capture;
    try {
      const info = await stat(outputPath);
      capture = info.isFile() ? await readFile(outputPath) : null;
    } catch {
      capture = null;
    }
    const timedOut = child.error?.code === 'ETIMEDOUT';
    const status = timedOut ? 'TIMEOUT' : child.status !== 0 ? 'RUNNER_FAILED' : capture?.length > 0 ? 'CAPTURED' : 'MISSING';
    results.push({
      id: cell.id,
      setup,
      status,
      outputPath,
      sha256: status === 'CAPTURED' ? sha256(capture) : null,
      bytes: status === 'CAPTURED' ? capture.length : 0,
      runner: { exitCode: child.status, signal: child.signal, error: child.error?.message ?? null, stderr: child.stderr?.slice(-4000) || '' },
    });
  }

  const missing = results.filter((cell) => cell.status !== 'CAPTURED').length;
  const receipt = {
    schemaVersion: 1,
    kind: 'handoff-capture-receipt',
    status: missing ? 'INCOMPLETE' : 'COMPLETE',
    failureClass: missing ? 'INCOMPLETE_MATRIX' : null,
    side: opt.side,
    candidateSha: opt.side === 'candidate' ? (opt['candidate-sha'] ?? null) : null,
    sourceSha256: contract.sourceSha256 ?? null,
    contractSha256: sha256(contractBytes),
    setup: contract.setup ?? null,
    summary: {
      expected: cells.length,
      captured: cells.length - missing,
      missing,
      timeouts: results.filter((cell) => cell.status === 'TIMEOUT').length,
      runnerFailures: results.filter((cell) => cell.status === 'RUNNER_FAILED').length,
    },
    cells: results,
  };
  await emit(opt.receipt, receipt);
  if (missing) {
    console.error(`INCOMPLETE_MATRIX: ${missing} of ${cells.length} captures missing`);
    process.exitCode = 1;
  }
}

try {
  await main();
} catch (error) {
  const receipt = (() => { try { return args(process.argv.slice(2)).receipt; } catch { return null; } })();
  const value = { schemaVersion: 1, kind: 'handoff-capture-receipt', status: 'INCOMPLETE', failureClass: 'INCOMPLETE_MATRIX', summary: { expected: 0, captured: 0, missing: 0, timeouts: 0, runnerFailures: 0 }, cells: [], errors: [error.message] };
  if (receipt) await emit(receipt, value).catch(() => {});
  console.error(`INCOMPLETE_MATRIX: ${error.message}`);
  process.exitCode = 1;
}
