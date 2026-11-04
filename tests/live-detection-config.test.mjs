import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const scripts = path.join(root, 'plugins/agentic-engineering-skills/skills/impeccable/scripts');

test('live payload supplies configured detector exclusions to the page resolver', async () => {
  const project = await mkdtemp(path.join(tmpdir(), 'impeccable-config-test-'));
  let child;
  try {
    await mkdir(path.join(project, '.impeccable/live'), { recursive: true });
    await mkdir(path.join(project, 'public'), { recursive: true });
    await writeFile(path.join(project, 'public', 'index.html'), '<html><body></body></html>');
    await writeFile(path.join(project, '.impeccable', 'config.json'), JSON.stringify({ detector: {
      ignoreRules: ['test-rule'], ignoreValues: [{ rule: 'design-system-font', value: 'Arial' }],
      ignoreFiles: ['public/ignored.html'],
    } }));
    await writeFile(path.join(project, '.impeccable/live/config.json'), JSON.stringify({ files: ['public/*.html'] }));
    child = spawn(process.execPath, [path.join(scripts, 'live-server.mjs')], { cwd: project, stdio: ['ignore', 'pipe', 'pipe'] });
    let output = '';
    const port = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error(`server startup timeout: ${output}`)), 15000);
      child.stdout.on('data', chunk => {
        output += chunk.toString();
        const match = output.match(/localhost:(\d+)/);
        if (match) { clearTimeout(timer); resolve(Number(match[1])); }
      });
      child.stderr.on('data', chunk => { output += chunk.toString(); });
      child.on('exit', code => { clearTimeout(timer); reject(new Error(`server exited ${code}: ${output}`)); });
    });
    const response = await fetch(`http://127.0.0.1:${port}/live.js`);
    assert.equal(response.status, 200);
    const payload = await response.text();
    const parts = payload.split(/\/\/ --- impeccable live script part: [^\n]+ ---\n/);
    const resolver = parts.find(part => part.includes('root.__IMPECCABLE_LIVE_IGNORES__'));
    assert.ok(resolver, 'the live payload must include the resolver');
    const context = vm.createContext({ window: {}, globalThis: {} });
    vm.runInContext(parts[0], context);
    vm.runInContext(resolver, context);
    const resolve = context.window.__IMPECCABLE_LIVE_IGNORES__.resolveDetectIgnores;
    const config = context.window.__IMPECCABLE_PROJECT_IGNORES__;
    const index = resolve({ ignores: config, pathname: '/index.html' });
    assert.deepEqual(JSON.parse(JSON.stringify(index)), { disabledRules: ['test-rule'], disabledValues: [{ rule: 'design-system-font', value: 'arial' }], skipScan: false });
    assert.equal(resolve({ ignores: config, pathname: '/ignored.html' }).skipScan, true);
  } finally {
    if (child && child.exitCode === null && child.signalCode === null) {
      const exited = new Promise(resolve => child.once('exit', resolve));
      child.kill();
      await exited;
    }
    await rm(project, { recursive: true, force: true });
  }
});
