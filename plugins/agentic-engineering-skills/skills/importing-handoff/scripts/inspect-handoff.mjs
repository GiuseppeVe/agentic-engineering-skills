#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { mkdir, readFile, readdir, stat, writeFile } from 'node:fs/promises';
import { dirname, extname, isAbsolute, relative, resolve, sep } from 'node:path';
import { inflateRawSync } from 'node:zlib';

const fail = (message) => { throw new Error(message); };
const sha256 = (data) => createHash('sha256').update(data).digest('hex');

function args(argv) {
  const result = { source: undefined };
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith('--') && !result.source) result.source = token;
    else if (token === '--out') result.out = argv[++i];
    else if (token === '--extract-dir') result.extractDir = argv[++i];
    else fail(`Unknown or misplaced argument: ${token}`);
  }
  if (!result.source) fail('Usage: inspect-handoff.mjs <handoff.zip> --out <manifest.json> --extract-dir <directory>');
  if (!result.out) fail('Missing required --out <manifest.json>');
  if (!result.extractDir) fail('Missing required --extract-dir <directory>');
  return result;
}

function safeArchivePath(raw) {
  if (!raw || raw.includes('\0')) fail(`Unsafe ZIP entry path: ${JSON.stringify(raw)}`);
  const normalized = raw.replaceAll('\\', '/');
  if (normalized.startsWith('/') || /^[A-Za-z]:/.test(normalized)) fail(`ZIP slip rejected: ${raw}`);
  const parts = normalized.split('/').filter((part) => part && part !== '.');
  if (parts.some((part) => part === '..')) fail(`ZIP slip rejected: ${raw}`);
  if (parts.length === 0) return '';
  return parts.join('/');
}

function crc32(buffer) {
  let crc = 0xffffffff;
  for (const byte of buffer) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function parseZip(buffer) {
  let eocd = -1;
  const start = Math.max(0, buffer.length - 65_557);
  for (let offset = buffer.length - 22; offset >= start; offset -= 1) {
    if (buffer.readUInt32LE(offset) === 0x06054b50) { eocd = offset; break; }
  }
  if (eocd < 0) fail('Invalid ZIP: end-of-central-directory record not found');
  const disk = buffer.readUInt16LE(eocd + 4);
  const directoryDisk = buffer.readUInt16LE(eocd + 6);
  const count = buffer.readUInt16LE(eocd + 10);
  const directoryOffset = buffer.readUInt32LE(eocd + 16);
  if (disk !== 0 || directoryDisk !== 0) fail('Unsupported ZIP: multi-disk archives are not allowed');
  if (count === 0xffff || directoryOffset === 0xffffffff) fail('Unsupported ZIP: ZIP64 archive');

  const entries = [];
  const seen = new Set();
  let cursor = directoryOffset;
  let totalSize = 0;
  for (let index = 0; index < count; index += 1) {
    if (cursor + 46 > buffer.length || buffer.readUInt32LE(cursor) !== 0x02014b50) fail('Invalid ZIP: corrupt central directory');
    const flags = buffer.readUInt16LE(cursor + 8);
    const method = buffer.readUInt16LE(cursor + 10);
    const checksum = buffer.readUInt32LE(cursor + 16);
    const compressedSize = buffer.readUInt32LE(cursor + 20);
    const size = buffer.readUInt32LE(cursor + 24);
    const nameLength = buffer.readUInt16LE(cursor + 28);
    const extraLength = buffer.readUInt16LE(cursor + 30);
    const commentLength = buffer.readUInt16LE(cursor + 32);
    const externalAttributes = buffer.readUInt32LE(cursor + 38);
    const localOffset = buffer.readUInt32LE(cursor + 42);
    const nameEnd = cursor + 46 + nameLength;
    if (nameEnd > buffer.length) fail('Invalid ZIP: truncated entry name');
    const rawName = buffer.subarray(cursor + 46, nameEnd).toString('utf8');
    const path = safeArchivePath(rawName);
    const directory = rawName.endsWith('/') || rawName.endsWith('\\');
    const unixMode = externalAttributes >>> 16;
    if ((unixMode & 0o170000) === 0o120000) fail(`Unsafe ZIP entry is a symbolic link: ${rawName}`);
    if (flags & 1) fail(`Unsupported encrypted ZIP entry: ${rawName}`);
    if (!directory && method !== 0 && method !== 8) fail(`Unsupported ZIP compression method ${method}: ${rawName}`);
    if (path && seen.has(path.toLowerCase())) fail(`Duplicate ZIP entry path: ${rawName}`);
    if (path) seen.add(path.toLowerCase());
    totalSize += size;
    if (totalSize > 1_073_741_824) fail('ZIP extraction rejected: uncompressed content exceeds 1 GiB');
    entries.push({ path, directory, flags, method, checksum, compressedSize, size, localOffset });
    cursor = nameEnd + extraLength + commentLength;
  }
  return entries;
}

async function extractZip(buffer, entries, root) {
  await mkdir(root, { recursive: true });
  const existing = await readdir(root);
  if (existing.length) fail(`Extraction directory must be empty: ${root}`);
  for (const entry of entries) {
    if (!entry.path) continue;
    const output = resolve(root, ...entry.path.split('/'));
    const rel = relative(root, output);
    if (rel.startsWith(`..${sep}`) || rel === '..' || isAbsolute(rel)) fail(`ZIP slip rejected: ${entry.path}`);
    if (entry.directory) { await mkdir(output, { recursive: true }); continue; }
    if (entry.localOffset + 30 > buffer.length || buffer.readUInt32LE(entry.localOffset) !== 0x04034b50) fail(`Invalid ZIP local header: ${entry.path}`);
    const nameLength = buffer.readUInt16LE(entry.localOffset + 26);
    const extraLength = buffer.readUInt16LE(entry.localOffset + 28);
    const dataStart = entry.localOffset + 30 + nameLength + extraLength;
    const dataEnd = dataStart + entry.compressedSize;
    if (dataEnd > buffer.length) fail(`Truncated ZIP entry data: ${entry.path}`);
    const compressed = buffer.subarray(dataStart, dataEnd);
    const data = entry.method === 8 ? inflateRawSync(compressed) : Buffer.from(compressed);
    if (data.length !== entry.size) fail(`ZIP size mismatch: ${entry.path}`);
    if (crc32(data) !== entry.checksum) fail(`ZIP checksum mismatch: ${entry.path}`);
    await mkdir(dirname(output), { recursive: true });
    await writeFile(output, data, { flag: 'wx' });
  }
}

const textExtensions = new Set(['.html', '.htm', '.css', '.js', '.mjs', '.cjs', '.jsx', '.ts', '.tsx', '.vue', '.svelte', '.json']);
const assetExtensions = new Set(['.png', '.jpg', '.jpeg', '.gif', '.webp', '.avif', '.svg', '.ico', '.mp4', '.webm', '.mov', '.mp3', '.wav', '.ogg', '.pdf']);
const fontExtensions = new Set(['.woff', '.woff2', '.ttf', '.otf', '.eot']);

function inventory(files) {
  const entrypoints = [];
  const stylesheets = [];
  const scripts = [];
  const assets = [];
  const fonts = [];
  const urls = new Set();
  const networkRequests = new Set();
  let packageJson;
  for (const file of files) {
    const ext = extname(file.path).toLowerCase();
    if (ext === '.html' || ext === '.htm') entrypoints.push({ path: file.path, type: 'html' });
    if (ext === '.css') stylesheets.push(file.path);
    if (['.js', '.mjs', '.cjs', '.jsx', '.ts', '.tsx'].includes(ext)) scripts.push(file.path);
    if (assetExtensions.has(ext)) assets.push(file.path);
    if (fontExtensions.has(ext)) fonts.push(file.path);
    if (file.path === 'package.json') {
      try { packageJson = JSON.parse(file.text); } catch { fail('Invalid package.json in handoff'); }
    }
    if (file.text !== undefined) {
      for (const match of file.text.matchAll(/https?:\/\/[^\s"'`<>)\\]+/g)) urls.add(match[0]);
      for (const match of file.text.matchAll(/(?:fetch\s*\(|axios(?:\.[a-z]+)?\s*\(|\.open\s*\(\s*["'][A-Z]+["']\s*,\s*|new\s+WebSocket\s*\()\s*["'`]([^"'`]+)["'`]/gi)) networkRequests.add(match[1]);
    }
  }
  const dependencyGroups = ['dependencies', 'devDependencies', 'peerDependencies'];
  const dependencies = dependencyGroups.flatMap((scope) => Object.entries(packageJson?.[scope] ?? {}).map(([name, version]) => ({ name, version, scope })));
  const packageScripts = Object.keys(packageJson?.scripts ?? {});
  const indicators = [];
  const names = new Set(dependencies.map((item) => item.name));
  for (const framework of ['react', 'next', 'vue', 'nuxt', 'svelte', '@angular/core', 'vite']) if (names.has(framework)) indicators.push(framework);
  const kind = packageJson ? (indicators.length ? indicators[0] : 'node-web') : 'static';
  const cdns = [...urls].filter((url) => /(?:cdn|unpkg|jsdelivr|cdnjs|fonts\.(?:googleapis|gstatic))/i.test(url));
  for (const url of urls) networkRequests.add(url);
  return {
    entrypoints,
    runtime: { kind, indicators, packageScripts },
    inventory: { entries: files.map(({ text, ...file }) => file), stylesheets, scripts, assets, fonts, dependencies, cdns, networkRequests: [...networkRequests].sort() },
  };
}

async function main() {
  const options = args(process.argv.slice(2));
  const sourcePath = resolve(options.source);
  const outputPath = resolve(options.out);
  const extractionRoot = resolve(options.extractDir);
  const sourceInfo = await stat(sourcePath).catch(() => null);
  if (!sourceInfo?.isFile()) fail(`Handoff ZIP not found or not a file: ${sourcePath}`);
  const zip = await readFile(sourcePath);
  const entries = parseZip(zip);
  await extractZip(zip, entries, extractionRoot);
  const files = [];
  for (const entry of entries.filter((item) => !item.directory && item.path)) {
    const data = await readFile(resolve(extractionRoot, ...entry.path.split('/')));
    files.push({ path: entry.path, type: extname(entry.path).slice(1).toLowerCase() || 'file', size: data.length, sha256: sha256(data), ...(textExtensions.has(extname(entry.path).toLowerCase()) ? { text: data.toString('utf8') } : {}) });
  }
  const observed = inventory(files);
  const manifest = {
    schemaVersion: 1,
    source: { kind: 'zip', path: sourcePath, filename: sourcePath.split(/[\\/]/).pop(), size: zip.length, sha256: sha256(zip) },
    extraction: { root: extractionRoot, entries: entries.length, zipSlipRejected: 0 },
    ...observed,
  };
  if (!manifest.entrypoints.length) fail('No runnable HTML entrypoint found in handoff ZIP');
  await mkdir(dirname(outputPath), { recursive: true });
  await writeFile(outputPath, `${JSON.stringify(manifest, null, 2)}\n`);
  process.stdout.write(`${outputPath}\n`);
}

main().catch((error) => { process.stderr.write(`inspect-handoff: ${error.message}\n`); process.exitCode = 1; });
