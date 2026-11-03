#!/usr/bin/env node
import { createRequire } from 'node:module';
import { inflateSync } from 'node:zlib';
import { copyFileSync, existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { basename, dirname, extname, isAbsolute, join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

export const DEFAULTS = {
  baseUrl: 'http://127.0.0.1:5173',
  outputDir: 'artifacts/marketing-screenshots',
  capture: { locale: 'en-US', timezoneId: 'UTC', colorScheme: 'light' },
  viewports: {
    mobile: { width: 390, height: 844, dpr: 3 },
    tablet: { width: 768, height: 1024, dpr: 2 },
    desktop: { width: 1440, height: 1024, dpr: 2 },
  },
  devices: { phone: { padding: 60, shadow: true }, tablet: { padding: 52, shadow: true } },
  canvases: {
    'landing-hero': { width: 1600, height: 1200, background: '#f7f8fc', align: 'right' },
    'pitch-16x9': { width: 1920, height: 1080, background: '#111827', align: 'center' },
    square: { width: 1600, height: 1600, background: '#f7f8fc', align: 'center' },
  },
  scenes: [],
};

const SAFE_CSS = `
  *, *::before, *::after { animation: none !important; transition: none !important; caret-color: transparent !important; }
  html { scroll-behavior: auto !important; }
`;

function mergeDefaults(input = {}) {
  return {
    ...DEFAULTS,
    ...input,
    capture: { ...DEFAULTS.capture, ...(input.capture ?? {}) },
    viewports: { ...DEFAULTS.viewports, ...(input.viewports ?? {}) },
    devices: { ...DEFAULTS.devices, ...(input.devices ?? {}) },
    canvases: { ...DEFAULTS.canvases, ...(input.canvases ?? {}) },
  };
}

function sceneUrl(scene, baseUrl) {
  if (scene.url) return scene.url;
  if (!scene.route) throw new Error(`Scene "${scene.name ?? 'unnamed'}" needs route or url.`);
  return new URL(scene.route, baseUrl).toString();
}

export function normalizeConfig(input = {}) {
  const config = mergeDefaults(input);
  if (!Array.isArray(config.scenes)) throw new Error('scenes must be an array.');
  config.scenes = config.scenes.map((scene, index) => {
    if (!scene?.name) throw new Error(`Scene ${index + 1} needs a name.`);
    const viewport = scene.viewport ?? 'mobile';
    if (typeof viewport === 'string' && !config.viewports[viewport]) throw new Error(`Unknown viewport "${viewport}".`);
    return {
      ...scene,
      viewport,
      url: sceneUrl(scene, config.baseUrl),
      outputs: scene.outputs ?? ['phone', 'landing-hero', 'pitch-16x9'],
    };
  });
  return config;
}

export function slugify(value) {
  return String(value).trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'scene';
}

export function buildOutputPaths(outputDir, sceneName, outputs = []) {
  const slug = slugify(sceneName);
  const dir = join(outputDir, slug);
  const result = { dir, raw: join(dir, `${slug}--raw.png`) };
  for (const output of outputs) {
    if (output === 'none') result.none = result.raw;
    else if (output === 'phone' || output === 'tablet' || output === 'browser-window') result[output] = join(dir, `${slug}--${output}-transparent.png`);
    else result[output] = join(dir, `${slug}--${output}.png`);
  }
  return result;
}

export function parsePng(buffer) {
  if (!Buffer.isBuffer(buffer) || buffer.length < 33 || !buffer.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]))) {
    throw new Error('File is not a readable PNG.');
  }
  if (buffer.subarray(12, 16).toString('ascii') !== 'IHDR') throw new Error('PNG is missing IHDR.');
  const width = buffer.readUInt32BE(16);
  const height = buffer.readUInt32BE(20);
  const colorType = buffer[25];
  if (!width || !height) throw new Error('PNG has invalid dimensions.');
  return { width, height, hasAlpha: colorType === 4 || colorType === 6 };
}

export function inspectPngContent(buffer) {
  const info = parsePng(buffer);
  let offset = 8;
  let bitDepth;
  let colorType;
  let interlace;
  const idat = [];
  while (offset + 12 <= buffer.length) {
    const length = buffer.readUInt32BE(offset);
    const type = buffer.subarray(offset + 4, offset + 8).toString('ascii');
    const data = buffer.subarray(offset + 8, offset + 8 + length);
    if (type === 'IHDR') { bitDepth = data[8]; colorType = data[9]; interlace = data[12]; }
    if (type === 'IDAT') idat.push(data);
    offset += length + 12;
  }
  if (bitDepth !== 8 || interlace !== 0 || ![0, 2, 4, 6].includes(colorType) || !idat.length) return { isBlank: false, inspected: false };
  const bytesPerPixel = colorType === 6 ? 4 : colorType === 2 ? 3 : colorType === 4 ? 2 : 1;
  const rowBytes = info.width * bytesPerPixel;
  let decoded;
  try { decoded = inflateSync(Buffer.concat(idat)); } catch { return { isBlank: false, inspected: false }; }
  let cursor = 0;
  let previous = Buffer.alloc(rowBytes);
  let channelMin = 255;
  let channelMax = 0;
  let opaque = 0;
  let pixels = 0;
  const paeth = (left, up, upperLeft) => {
    const p = left + up - upperLeft;
    const pl = Math.abs(p - left); const pu = Math.abs(p - up); const pul = Math.abs(p - upperLeft);
    return pl <= pu && pl <= pul ? left : pu <= pul ? up : upperLeft;
  };
  for (let row = 0; row < info.height; row += 1) {
    const filter = decoded[cursor++];
    const current = Buffer.alloc(rowBytes);
    for (let index = 0; index < rowBytes; index += 1) {
      const value = decoded[cursor++];
      const left = index >= bytesPerPixel ? current[index - bytesPerPixel] : 0;
      const up = previous[index];
      const upperLeft = index >= bytesPerPixel ? previous[index - bytesPerPixel] : 0;
      current[index] = filter === 0 ? value : filter === 1 ? (value + left) & 255 : filter === 2 ? (value + up) & 255 : filter === 3 ? (value + Math.floor((left + up) / 2)) & 255 : filter === 4 ? (value + paeth(left, up, upperLeft)) & 255 : value;
    }
    for (let index = 0; index < rowBytes; index += bytesPerPixel) {
      const channels = colorType === 0 || colorType === 4 ? [current[index]] : [current[index], current[index + 1], current[index + 2]];
      for (const channel of channels) { channelMin = Math.min(channelMin, channel); channelMax = Math.max(channelMax, channel); }
      const alpha = colorType === 6 ? current[index + 3] : colorType === 4 ? current[index + 1] : 255;
      if (alpha > 0) opaque += 1;
      pixels += 1;
    }
    previous = current;
  }
  const opaqueRatio = pixels ? opaque / pixels : 0;
  const range = channelMax - channelMin;
  return { isBlank: opaqueRatio > .98 && range < 8, inspected: true, opaqueRatio, range };
}
export function validateCaptureInput(file) {
  if (!existsSync(file)) throw new Error(`Raw screenshot not found: ${file}`);
  if (statSync(file).size === 0) throw new Error(`Screenshot is empty: ${file}`);
  const buffer = readFileSync(file);
  const info = parsePng(buffer);
  const content = inspectPngContent(buffer);
  if (content.isBlank) throw new Error('Screenshot appears blank: ' + file);
  return { ...info, content };
}

function escapeXml(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' })[char]);
}

function phoneSvg(rawDataUri, raw, output, frame = {}) {
  const padding = frame.padding ?? Math.max(30, Math.round(raw.width * 0.05));
  const top = Math.round(padding * 1.55);
  const width = raw.width + padding * 2;
  const height = raw.height + top + padding;
  const scale = Math.min(output.width / width, output.height / height);
  const x = (output.width - width * scale) / 2;
  const y = (output.height - height * scale) / 2;
  const radius = Math.max(42, Math.round(raw.width * 0.075));
  const screenX = x + padding * scale;
  const screenY = y + top * scale;
  const screenW = raw.width * scale;
  const screenH = raw.height * scale;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${output.width}" height="${output.height}" viewBox="0 0 ${output.width} ${output.height}">
<defs><filter id="shadow" x="-30%" y="-20%" width="160%" height="170%"><feDropShadow dx="0" dy="${Math.max(8, padding / 3)}" stdDeviation="${Math.max(8, padding / 4)}" flood-color="#0f172a" flood-opacity=".26"/></filter><clipPath id="screen"><rect x="${screenX}" y="${screenY}" width="${screenW}" height="${screenH}" rx="${Math.max(18, radius * scale * .62)}"/></clipPath></defs>
<rect width="100%" height="100%" fill="transparent"/>
<rect x="${x}" y="${y}" width="${width * scale}" height="${height * scale}" rx="${radius * scale}" fill="#111827" filter="${frame.shadow === false ? '' : 'url(#shadow)'}"/>
<rect x="${x + Math.max(3, padding * .12) * scale}" y="${y + Math.max(3, padding * .12) * scale}" width="${(width - Math.max(6, padding * .24)) * scale}" height="${(height - Math.max(6, padding * .24)) * scale}" rx="${Math.max(10, (radius - 4) * scale)}" fill="#334155"/>
<image href="${escapeXml(rawDataUri)}" x="${screenX}" y="${screenY}" width="${screenW}" height="${screenH}" preserveAspectRatio="xMidYMid meet" clip-path="url(#screen)"/>
<rect x="${output.width / 2 - Math.max(22, raw.width * scale * .1)}" y="${y + top * scale * .35}" width="${Math.max(44, raw.width * scale * .2)}" height="${Math.max(8, raw.width * scale * .028)}" rx="99" fill="#0b1120"/>
</svg>`;
}

function tabletSvg(rawDataUri, raw, output, frame = {}) {
  const padding = frame.padding ?? Math.max(36, Math.round(raw.width * 0.055));
  const width = raw.width + padding * 2;
  const height = raw.height + padding * 2;
  const scale = Math.min(output.width / width, output.height / height);
  const x = (output.width - width * scale) / 2;
  const y = (output.height - height * scale) / 2;
  const screenX = x + padding * scale;
  const screenY = y + padding * scale;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${output.width}" height="${output.height}" viewBox="0 0 ${output.width} ${output.height}"><defs><filter id="shadow" x="-30%" y="-20%" width="160%" height="170%"><feDropShadow dy="18" stdDeviation="20" flood-opacity=".23"/></filter><clipPath id="screen"><rect x="${screenX}" y="${screenY}" width="${raw.width * scale}" height="${raw.height * scale}" rx="${Math.max(14, padding * scale * .55)}"/></clipPath></defs><rect width="100%" height="100%" fill="transparent"/><rect x="${x}" y="${y}" width="${width * scale}" height="${height * scale}" rx="${Math.max(24, padding * scale)}" fill="#1f2937" filter="${frame.shadow === false ? '' : 'url(#shadow)'}"/><image href="${escapeXml(rawDataUri)}" x="${screenX}" y="${screenY}" width="${raw.width * scale}" height="${raw.height * scale}" preserveAspectRatio="xMidYMid meet" clip-path="url(#screen)"/></svg>`;
}

function browserSvg(rawDataUri, raw, output) {
  const chrome = Math.max(48, Math.round(raw.width * .06));
  const scale = Math.min(output.width / raw.width, output.height / (raw.height + chrome));
  const width = raw.width * scale;
  const height = (raw.height + chrome) * scale;
  const x = (output.width - width) / 2;
  const y = (output.height - height) / 2;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${output.width}" height="${output.height}" viewBox="0 0 ${output.width} ${output.height}"><defs><filter id="shadow" x="-30%" y="-20%" width="160%" height="170%"><feDropShadow dy="16" stdDeviation="18" flood-opacity=".24"/></filter><clipPath id="screen"><rect x="${x}" y="${y + chrome * scale}" width="${width}" height="${raw.height * scale}" rx="0"/></clipPath></defs><rect width="100%" height="100%" fill="transparent"/><rect x="${x}" y="${y}" width="${width}" height="${height}" rx="${Math.max(10, 16 * scale)}" fill="#e5e7eb" filter="url(#shadow)"/><circle cx="${x + 24 * scale}" cy="${y + chrome * scale / 2}" r="${6 * scale}" fill="#fb7185"/><circle cx="${x + 44 * scale}" cy="${y + chrome * scale / 2}" r="${6 * scale}" fill="#fbbf24"/><circle cx="${x + 64 * scale}" cy="${y + chrome * scale / 2}" r="${6 * scale}" fill="#34d399"/><image href="${escapeXml(rawDataUri)}" x="${x}" y="${y + chrome * scale}" width="${width}" height="${raw.height * scale}" preserveAspectRatio="xMidYMid meet" clip-path="url(#screen)"/></svg>`;
}

export function composeSvg({ kind, rawDataUri, raw, output, frame }) {
  if (kind === 'phone') return phoneSvg(rawDataUri, raw, output, frame);
  if (kind === 'tablet') return tabletSvg(rawDataUri, raw, output, frame);
  if (kind === 'browser-window') return browserSvg(rawDataUri, raw, output);
  throw new Error(`Unknown device kind "${kind}".`);
}

function canvasSvg({ canvas, rawDataUri, raw, device }) {
  const output = { width: canvas.width, height: canvas.height };
  const deviceWidth = Math.round(canvas.width * (canvas.deviceScale ?? .55));
  const deviceHeight = Math.round(canvas.height * .88);
  const deviceSvg = composeSvg({ kind: device, rawDataUri, raw, output: { width: deviceWidth, height: deviceHeight }, frame: {} });
  const data = `data:image/svg+xml;base64,${Buffer.from(deviceSvg).toString('base64')}`;
  const x = canvas.align === 'left' ? canvas.width * .08 : canvas.align === 'right' ? canvas.width - deviceWidth - canvas.width * .08 : (canvas.width - deviceWidth) / 2;
  const y = (canvas.height - deviceHeight) / 2;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${canvas.width}" height="${canvas.height}" viewBox="0 0 ${canvas.width} ${canvas.height}"><defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="${escapeXml(canvas.background ?? '#f8fafc')}"/><stop offset="1" stop-color="${escapeXml(canvas.backgroundEnd ?? canvas.background ?? '#f8fafc')}"/></linearGradient></defs><rect width="100%" height="100%" fill="url(#bg)"/><image href="${data}" x="${x}" y="${y}" width="${deviceWidth}" height="${deviceHeight}"/></svg>`;
}

function projectRequire(projectRoot) {
  for (const packageFile of [join(projectRoot, 'frontend', 'package.json'), join(projectRoot, 'package.json')]) {
    if (existsSync(packageFile)) return createRequire(packageFile);
  }
  throw new Error(`Cannot locate package.json under ${projectRoot}; pass --project-root.`);
}

async function loadChromium(projectRoot) {
  try {
    return projectRequire(projectRoot)('@playwright/test').chromium;
  } catch (error) {
    throw new Error(`Playwright unavailable from ${projectRoot}. Install it in the app or pass --project-root. ${error.message}`);
  }
}

async function renderSvgToPng(projectRoot, svg, output, path, transparent) {
  const chromium = await loadChromium(projectRoot);
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: output, deviceScaleFactor: 1 });
    await page.setContent(`<style>html,body{margin:0;width:100%;height:100%;background:transparent;overflow:hidden}svg{display:block}</style>${svg}`);
    await page.screenshot({ path, omitBackground: transparent });
  } finally {
    await browser.close();
  }
}

function warningForText(text) {
  const warnings = [];
  if (/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i.test(text)) warnings.push('Visible email detected; confirm it is demo or sanitized data.');
  if (/\b(?:api[_ -]?key|token|secret|password|bearer)\b/i.test(text)) warnings.push('Potential credential/debug text detected; inspect before marketing use.');
  return warnings;
}

export async function waitForImageReadiness(page, timeoutMs = 5_000) {
  try {
    await page.waitForFunction(() => [...document.images].every((image) => image.complete), undefined, { timeout: timeoutMs });
    return { timedOut: false };
  } catch (error) {
    if (/timeout/i.test(String(error?.message))) return { timedOut: true };
    throw error;
  }
}
async function waitForStablePage(page, scene) {
  await page.waitForLoadState('domcontentloaded');
  await page.waitForLoadState('networkidle', { timeout: 1_500 }).catch(() => {});
  await page.evaluate(async () => { await document.fonts?.ready; });
  const imageReadiness = await waitForImageReadiness(page, scene.imageTimeoutMs ?? 5_000);
  if (scene.waitFor) await page.locator(scene.waitFor).waitFor({ state: 'visible' });
  if (scene.readySelector) await page.locator(scene.readySelector).waitFor({ state: 'visible' });
  return imageReadiness;
}

async function captureScene(projectRoot, config, scene, overwrite) {
  const viewport = typeof scene.viewport === 'string' ? config.viewports[scene.viewport] : scene.viewport;
  const outputDir = resolve(projectRoot, config.outputDir);
  const paths = buildOutputPaths(outputDir, scene.name, scene.outputs);
  mkdirSync(paths.dir, { recursive: true });
  if (existsSync(paths.raw) && !overwrite) throw new Error(`Raw screenshot already exists: ${paths.raw}. Use --overwrite to replace it.`);
  const chromium = await loadChromium(projectRoot);
  const browser = await chromium.launch({ headless: true });
  let warnings = [];
  try {
    const context = await browser.newContext({ viewport: { width: viewport.width, height: viewport.height }, deviceScaleFactor: viewport.dpr, locale: scene.locale ?? config.capture.locale, timezoneId: scene.timezoneId ?? config.capture.timezoneId, colorScheme: scene.colorScheme ?? config.capture.colorScheme, reducedMotion: 'reduce', storageState: scene.storageState });
    const page = await context.newPage();
    await page.addStyleTag({ content: SAFE_CSS });
    await page.goto(scene.url, { waitUntil: 'domcontentloaded' });
    if (typeof scene.setup === 'function') await scene.setup({ page, context });
    const readiness = await waitForStablePage(page, scene);
    warnings = [...warningForText(await page.locator('body').innerText().catch(() => '')), ...(readiness.timedOut ? ['Some images did not settle before timeout; inspect output before marketing use.'] : [])];
    const target = scene.selector ? page.locator(scene.selector) : page;
    await target.screenshot({ path: paths.raw, animations: 'disabled', caret: 'hide' });
    await context.close();
  } finally {
    await browser.close();
  }
  const raw = validateCaptureInput(paths.raw);
  return { viewport, paths, raw, warnings };
}

async function composeOutputs(projectRoot, config, scene, capture) {
  const rawDataUri = `data:image/png;base64,${readFileSync(capture.paths.raw).toString('base64')}`;
  const outputs = { raw: capture.paths.raw };
  for (const kind of scene.outputs) {
    if (kind === 'none') { outputs.none = capture.paths.raw; continue; }
    const outputPath = capture.paths[kind];
    if (kind === 'phone' || kind === 'tablet' || kind === 'browser-window') {
      const padding = config.devices[kind]?.padding ?? 60;
      const output = kind === 'browser-window'
        ? { width: capture.raw.width, height: capture.raw.height + 80 }
        : { width: capture.raw.width + padding * 2, height: capture.raw.height + padding * 3 };
      await renderSvgToPng(projectRoot, composeSvg({ kind, rawDataUri, raw: capture.raw, output, frame: config.devices[kind] }), output, outputPath, true);
    } else {
      const canvas = config.canvases[kind];
      if (!canvas) throw new Error(`Unknown canvas preset "${kind}".`);
      const device = scene.canvasDevice ?? 'phone';
      const output = { width: canvas.width, height: canvas.height };
      await renderSvgToPng(projectRoot, canvasSvg({ canvas, rawDataUri, raw: capture.raw, device }), output, outputPath, false);
    }
    const info = validateCaptureInput(outputPath);
    if (kind === 'phone' || kind === 'tablet' || kind === 'browser-window') {
      if (!info.hasAlpha) throw new Error(`${kind} output lost transparency: ${outputPath}`);
    }
    outputs[kind] = outputPath;
  }
  return outputs;
}

export function createManifest({ outputDir, scenes }) {
  return { generatedAt: new Date().toISOString(), outputDir, scenes };
}

function parseArgs(argv) {
  const result = { _: [] };
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (!arg.startsWith('--')) result._.push(arg);
    else if (arg === '--all' || arg === '--overwrite') result[arg.slice(2)] = true;
    else result[arg.slice(2)] = argv[++index];
  }
  return result;
}

async function readConfig(configPath) {
  if (!configPath || !existsSync(configPath)) return {};
  const module = await import(`${pathToFileURL(configPath).href}?mtime=${statSync(configPath).mtimeMs}`);
  return module.default ?? module.config ?? module;
}

function adHocScene(args) {
  if (!args.url && !args.route) return null;
  return { name: args.name ?? basename(args.route ?? new URL(args.url).pathname) ?? 'capture', route: args.route, url: args.url, viewport: args.preset ?? 'mobile', outputs: [args.device ?? 'phone', ...(args.canvas ? args.canvas.split(',') : [])] };
}

async function commandCapture(args) {
  const projectRoot = resolve(args['project-root'] ?? process.cwd());
  const configFile = args.config ? resolve(projectRoot, args.config) : join(projectRoot, 'marketing-screenshots.config.mjs');
  const config = normalizeConfig({ ...(await readConfig(configFile)), ...(args['output-dir'] ? { outputDir: args['output-dir'] } : {}) });
  const oneOff = adHocScene(args);
  const candidates = oneOff ? [oneOff] : config.scenes.filter((scene) => args.all || !args.scene || scene.name === args.scene);
  if (!candidates.length) throw new Error('No scenes selected. Use --all, --scene NAME, or --url/--route.');
  const records = [];
  for (const scene of candidates) {
    const capture = await captureScene(projectRoot, config, scene, Boolean(args.overwrite));
    const outputs = await composeOutputs(projectRoot, config, scene, capture);
    records.push({ name: scene.name, url: scene.url, viewport: capture.viewport, outputs, warnings: capture.warnings });
  }
  const outputDir = resolve(projectRoot, config.outputDir);
  const manifest = createManifest({ outputDir, scenes: records });
  mkdirSync(outputDir, { recursive: true });
  const manifestPath = join(outputDir, 'manifest.json');
  writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
  console.log(JSON.stringify({ manifest: manifestPath, scenes: records }, null, 2));
}

async function commandCompose(args) {
  const projectRoot = resolve(args['project-root'] ?? process.cwd());
  if (!args.input) throw new Error('compose needs --input RAW.png.');
  const rawPath = resolve(projectRoot, args.input);
  const raw = validateCaptureInput(rawPath);
  const name = args.name ?? basename(rawPath, extname(rawPath)).replace(/--raw$/, '');
  const config = normalizeConfig({ ...(await readConfig(args.config ? resolve(projectRoot, args.config) : join(projectRoot, 'marketing-screenshots.config.mjs'))), ...(args['output-dir'] ? { outputDir: args['output-dir'] } : {}) });
  const scene = { name, outputs: [args.device ?? 'phone', ...(args.canvas ? args.canvas.split(',') : [])] };
  const paths = buildOutputPaths(resolve(projectRoot, config.outputDir), name, scene.outputs);
  mkdirSync(paths.dir, { recursive: true });
  if (rawPath !== paths.raw && !existsSync(paths.raw)) copyFileSync(rawPath, paths.raw);
  const outputs = await composeOutputs(projectRoot, config, scene, { raw, paths: { ...paths, raw: rawPath } });
  console.log(JSON.stringify({ name, outputs }, null, 2));
}

function commandValidate(args) {
  if (!args.input) throw new Error('validate needs --input PNG.');
  const info = validateCaptureInput(resolve(args.input));
  console.log(JSON.stringify(info, null, 2));
}

function usage() {
  console.log('Usage: node marketing-screenshots.mjs <capture|compose|validate> [--project-root PATH] [--config FILE]');
}

if (process.argv[1] && resolve(process.argv[1]) === resolve(new URL(import.meta.url).pathname.replace(/^\/(.:)/, '$1'))) {
  const args = parseArgs(process.argv.slice(2));
  const command = args._[0] ?? 'capture';
  const run = command === 'capture' ? commandCapture : command === 'compose' ? commandCompose : command === 'validate' ? commandValidate : null;
  if (!run) { usage(); process.exitCode = 1; } else Promise.resolve(run(args)).catch((error) => { console.error(`marketing-screenshots: ${error.message}`); process.exitCode = 1; });
}
