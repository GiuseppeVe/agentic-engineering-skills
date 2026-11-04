import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const browserModule = process.env.IMPECCABLE_TEST_PLAYWRIGHT;
const executablePath = process.env.IMPECCABLE_TEST_BROWSER;
const detector = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../plugins/agentic-engineering-skills/skills/impeccable/scripts/detector/detect-antipatterns-browser.js');

test('live detector applies rule, value and whole-page exclusions without hiding unrelated findings', { skip: !executablePath }, async () => {
  const { chromium } = await import(browserModule ? pathToFileURL(browserModule).href : 'playwright-core');
  const browser = await chromium.launch({ executablePath, headless: true });
  try {
    const page = await browser.newPage();
    await page.setContent(`<html><body style="font-family: Arial">${'<p>Example visible text</p>'.repeat(24)}</body></html>`);
    await page.evaluate(() => { document.documentElement.dataset.impeccableExtension = 'true'; });
    await page.addScriptTag({ content: await readFile(detector, 'utf8') });
    const scan = config => page.evaluate(config => new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('scan timed out')), 5000);
      const listener = event => {
        if (event.data?.source !== 'impeccable-results' || event.data.scanId !== config.scanId) return;
        clearTimeout(timer); window.removeEventListener('message', listener);
        resolve(event.data.findings.flatMap(group => group.findings));
      };
      window.addEventListener('message', listener);
      window.postMessage({ source: 'impeccable-command', action: 'scan', config }, '*');
    }), config);
    const baseline = await scan({ scanId: 'baseline' });
    assert.ok(baseline.some(f => f.type === 'overused-font' && /arial/i.test(f.detail)));
    assert.ok(baseline.some(f => f.type === 'single-font'));
    const ruleFiltered = await scan({ scanId: 'rule', disabledRules: ['overused-font'] });
    assert.ok(!ruleFiltered.some(f => f.type === 'overused-font'));
    assert.ok(ruleFiltered.some(f => f.type === 'single-font'));
    const valueFiltered = await scan({ scanId: 'value', disabledValues: [{ rule: 'overused-font', value: 'arial' }] });
    assert.ok(!valueFiltered.some(f => f.type === 'overused-font'));
    assert.ok(valueFiltered.some(f => f.type === 'single-font'));
    const unrelated = await scan({ scanId: 'other', disabledValues: [{ rule: 'overused-font', value: 'roboto' }] });
    assert.ok(unrelated.some(f => f.type === 'overused-font'));
    await page.evaluate(() => { document.querySelector('p').style.color = 'rgb(255, 0, 0)'; });
    const designSystem = { present: true, hasColors: true, allowedColors: [{ r: 0, g: 0, b: 0 }] };
    const colorBaseline = await scan({ scanId: 'color', designSystem });
    assert.ok(colorBaseline.some(f => f.type === 'design-system-color' && /255, 0, 0/.test(f.ignoreValue)));
    const colorFiltered = await scan({ scanId: 'hsl', designSystem, disabledValues: [{ rule: 'design-system-color', value: 'hsl(0, 100%, 50%)' }] });
    assert.ok(!colorFiltered.some(f => f.type === 'design-system-color' && /255, 0, 0/.test(f.ignoreValue)));
    const skipped = await scan({ scanId: 'skip', skipScan: true });
    assert.deepEqual(skipped, []);
  } finally { await browser.close(); }
});
