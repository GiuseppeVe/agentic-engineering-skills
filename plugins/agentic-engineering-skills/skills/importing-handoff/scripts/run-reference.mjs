#!/usr/bin/env node
import { createReadStream } from 'node:fs';
import { mkdir, stat, writeFile } from 'node:fs/promises';
import { createServer, get as httpGet } from 'node:http';
import { dirname, extname, isAbsolute, relative, resolve, sep } from 'node:path';

const fail = (message) => { throw new Error(message); };

function args(argv) {
  if (argv[0] !== 'probe') fail('Usage: run-reference.mjs probe --root <directory> --entry <file> --receipt <receipt.json> [--timeout-ms 10000]');
  const result = { mode: 'probe', timeoutMs: 10_000 };
  for (let i = 1; i < argv.length; i += 1) {
    const token = argv[i];
    if (token === '--root') result.root = argv[++i];
    else if (token === '--entry') result.entry = argv[++i];
    else if (token === '--receipt') result.receipt = argv[++i];
    else if (token === '--timeout-ms') result.timeoutMs = Number(argv[++i]);
    else fail(`Unknown argument: ${token}`);
  }
  for (const key of ['root', 'entry', 'receipt']) if (!result[key]) fail(`Missing required --${key === 'timeoutMs' ? 'timeout-ms' : key}`);
  if (!Number.isInteger(result.timeoutMs) || result.timeoutMs < 1 || result.timeoutMs > 300_000) fail('--timeout-ms must be an integer from 1 to 300000');
  return result;
}

function within(root, path) {
  const rel = relative(root, path);
  return rel !== '..' && !rel.startsWith(`..${sep}`) && !isAbsolute(rel);
}

const mime = {
  '.html': 'text/html; charset=utf-8', '.htm': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp',
  '.woff': 'font/woff', '.woff2': 'font/woff2', '.ttf': 'font/ttf', '.ico': 'image/x-icon',
};

function makeServer(root) {
  return createServer(async (request, response) => {
    try {
      if (request.method !== 'GET' && request.method !== 'HEAD') { response.writeHead(405); response.end('Method not allowed'); return; }
      let pathname;
      try { pathname = decodeURIComponent(new URL(request.url ?? '/', 'http://127.0.0.1').pathname); }
      catch { response.writeHead(400); response.end('Bad request'); return; }
      if (pathname.includes('\0')) { response.writeHead(400); response.end('Bad request'); return; }
      const file = resolve(root, `.${pathname}`);
      if (!within(root, file)) { response.writeHead(403); response.end('Forbidden'); return; }
      const info = await stat(file).catch(() => null);
      if (!info?.isFile()) { response.writeHead(404); response.end('Not found'); return; }
      response.writeHead(200, { 'content-type': mime[extname(file).toLowerCase()] ?? 'application/octet-stream', 'content-length': info.size, 'cache-control': 'no-store' });
      if (request.method === 'HEAD') response.end();
      else createReadStream(file).on('error', () => response.destroy()).pipe(response);
    } catch (error) {
      if (!response.headersSent) response.writeHead(500);
      response.end(`Server error: ${error.message}`);
    }
  });
}

function listen(server) {
  return new Promise((accept, reject) => {
    const onError = (error) => { server.off('listening', onListening); reject(error); };
    const onListening = () => { server.off('error', onError); accept(); };
    server.once('error', onError);
    server.once('listening', onListening);
    server.listen(0, '127.0.0.1');
  });
}

function health(url, timeoutMs) {
  return new Promise((accept, reject) => {
    const request = httpGet(url, { headers: { connection: 'close' } }, (response) => {
      response.resume();
      response.once('end', () => accept({ httpStatus: response.statusCode, contentType: response.headers['content-type'] ?? null }));
    });
    request.setTimeout(timeoutMs, () => request.destroy(new Error(`Health check timed out after ${timeoutMs}ms`)));
    request.once('error', reject);
  });
}

function close(server) {
  if (!server?.listening) return Promise.resolve();
  return new Promise((accept, reject) => server.close((error) => error ? reject(error) : accept()));
}

async function save(path, receipt) {
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, `${JSON.stringify(receipt, null, 2)}\n`);
}

async function main(argv) {
  let options;
  let server;
  let receiptPath = argv[argv.indexOf('--receipt') + 1];
  const receipt = { schemaVersion: 1, command: 'probe', status: 'FAILED', failureClass: 'SOURCE_UNRUNNABLE', url: null, health: { httpStatus: null }, cleanup: { status: 'CLOSED' } };
  try {
    options = args(argv);
    receiptPath = resolve(options.receipt);
    const root = resolve(options.root);
    const info = await stat(root).catch(() => null);
    if (!info?.isDirectory()) fail(`Reference root not found or not a directory: ${root}`);
    const entry = resolve(root, options.entry);
    if (!within(root, entry)) fail(`Entry escapes reference root: ${options.entry}`);
    if (!(await stat(entry).catch(() => null))?.isFile()) fail(`Reference entry not found: ${entry}`);
    server = makeServer(root);
    await listen(server);
    const address = server.address();
    const entryUrl = `http://127.0.0.1:${address.port}/${relative(root, entry).split(sep).map(encodeURIComponent).join('/')}`;
    receipt.url = entryUrl;
    receipt.root = root;
    receipt.entry = options.entry;
    receipt.health = await health(entryUrl, options.timeoutMs);
    if (receipt.health.httpStatus !== 200) fail(`Reference health check returned HTTP ${receipt.health.httpStatus}`);
    receipt.status = 'HEALTHY';
    receipt.failureClass = null;
  } catch (error) {
    receipt.error = error.message;
  } finally {
    try { await close(server); }
    catch (error) { receipt.cleanup = { status: 'FAILED', error: error.message }; receipt.status = 'FAILED'; receipt.failureClass = 'SOURCE_UNRUNNABLE'; }
    if (receiptPath) {
      try { await save(resolve(receiptPath), receipt); }
      catch (error) { process.stderr.write(`run-reference: unable to write receipt: ${error.message}\n`); process.exitCode = 1; }
    }
  }
  if (receipt.status !== 'HEALTHY') {
    process.stderr.write(`run-reference: ${receipt.error ?? receipt.cleanup.error ?? 'reference probe failed'}\n`);
    process.exitCode = 1;
  } else process.stdout.write(`${receiptPath}\n`);
}

main(process.argv.slice(2));
