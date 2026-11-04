import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { deflateSync } from 'node:zlib';
import test from 'node:test';

import {
  buildOutputPaths,
  composeSvg,
  createManifest,
  inspectPngContent,
  waitForImageReadiness,
  normalizeConfig,
  parsePng,
  validateCaptureInput,
} from '../scripts/marketing-screenshots.mjs';

const PNG_1X1 = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVQIHWP4z8DwHwAFgAI/ScLq7wAAAABJRU5ErkJggg==',
  'base64',
);

function pngChunk(type, data) {
  const length = Buffer.alloc(4);
  length.writeUInt32BE(data.length);
  return Buffer.concat([length, Buffer.from(type), data, Buffer.alloc(4)]);
}

const VALID_SOLID_PNG = Buffer.concat([
  Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
  pngChunk('IHDR', Buffer.from([0, 0, 0, 1, 0, 0, 0, 1, 8, 6, 0, 0, 0])),
  pngChunk('IDAT', deflateSync(Buffer.from([0, 255, 255, 255, 255]))),
  pngChunk('IEND', Buffer.alloc(0)),
]);
test('uses high-resolution default mobile viewport', () => {
  const config = normalizeConfig({});
  assert.deepEqual(config.viewports.mobile, { width: 390, height: 844, dpr: 3 });
});

test('parses scene options and merges capture defaults', () => {
  const config = normalizeConfig({
    baseUrl: 'http://127.0.0.1:5173',
    scenes: [{ name: 'dashboard', route: '/dashboard', viewport: 'desktop', selector: '#app' }],
  });
  assert.equal(config.scenes[0].url, 'http://127.0.0.1:5173/dashboard');
  assert.equal(config.scenes[0].viewport, 'desktop');
  assert.equal(config.scenes[0].selector, '#app');
});

test('creates deterministic scene filenames', () => {
  const paths = buildOutputPaths('/tmp/assets', 'Onboarding Step 01', ['phone', 'landing-hero', 'pitch-16x9']);
  assert.equal(paths.raw.endsWith('onboarding-step-01--raw.png'), true);
  assert.equal(paths.phone.endsWith('onboarding-step-01--phone-transparent.png'), true);
  assert.equal(paths['landing-hero'].endsWith('onboarding-step-01--landing-hero.png'), true);
  assert.equal(paths['pitch-16x9'].endsWith('onboarding-step-01--pitch-16x9.png'), true);
});

test('emits transparent phone SVG with an aspect-preserving screen image', () => {
  const svg = composeSvg({
    kind: 'phone',
    rawDataUri: `data:image/png;base64,${PNG_1X1.toString('base64')}`,
    raw: { width: 1170, height: 2532 },
    output: { width: 1350, height: 2712 },
  });
  assert.match(svg, /preserveAspectRatio="xMidYMid meet"/);
  assert.match(svg, /clipPath/);
  assert.match(svg, /fill="transparent"/);
});

test('uses configured pitch-deck canvas dimensions', () => {
  const config = normalizeConfig({ canvases: { 'pitch-16x9': { width: 1280, height: 720 } } });
  assert.deepEqual(config.canvases['pitch-16x9'], { width: 1280, height: 720 });
});

test('rejects invalid scene configuration', () => {
  assert.throws(() => normalizeConfig({ scenes: [{ name: 'broken' }] }), /route or url/);
});

test('rejects missing raw screenshot before composition', () => {
  assert.throws(() => validateCaptureInput('/does/not/exist.png'), /Raw screenshot not found/);
});

test('reads PNG dimensions and alpha channel', () => {
  const png = parsePng(PNG_1X1);
  assert.equal(png.width, 1);
  assert.equal(png.height, 1);
  assert.equal(png.hasAlpha, true);
});

test('creates secret-free reproducible manifest', () => {
  const manifest = createManifest({
    outputDir: '/tmp/assets',
    scenes: [{ name: 'home', viewport: { width: 390, height: 844, dpr: 3 }, outputs: { raw: '/tmp/assets/home/home--raw.png' } }],
  });
  assert.equal(manifest.scenes[0].name, 'home');
  assert.equal(JSON.stringify(manifest).includes('password'), false);
});

test('validates a readable non-empty input PNG', () => {
  const dir = mkdtempSync(join(tmpdir(), 'marketing-screenshots-'));
  const file = join(dir, 'raw.png');
  try {
    writeFileSync(file, PNG_1X1);
    const info = validateCaptureInput(file);
    assert.equal(info.width, 1);
    assert.equal(existsSync(file), true);
    assert.equal(readFileSync(file).byteLength > 0, true);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test('CLI validate completes without an async wrapper error', () => {
  const dir = mkdtempSync(join(tmpdir(), 'marketing-screenshots-cli-'));
  const file = join(dir, 'raw.png');
  try {
    writeFileSync(file, PNG_1X1);
    const script = fileURLToPath(new URL('../scripts/marketing-screenshots.mjs', import.meta.url));
    const result = spawnSync(process.execPath, [script, 'validate', '--input', file]);
    assert.equal(result.status, 0, result.stderr.toString());
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
test('identifies a single-color screenshot as blank', () => {
  const content = inspectPngContent(VALID_SOLID_PNG);
  assert.equal(content.isBlank, true);
});
test('bounds an image readiness wait that never settles', async () => {
  const page = { waitForFunction: async () => { throw new Error('Timeout 1ms exceeded'); } };
  const result = await waitForImageReadiness(page, 1);
  assert.equal(result.timedOut, true);
});