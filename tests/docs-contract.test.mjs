import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const read = (path) => readFileSync(resolve(root, path), 'utf8');
const json = (path) => JSON.parse(read(path));
const lock = json('manifests/skills.lock.json').skills;
const names = lock.map(({ name }) => name).sort();
const docs = [
  'README.md',
  'docs/workflow.md',
  'docs/customization.md',
  'docs/compatibility.md',
  'docs/provenance.md',
  'docs/selective-install.md',
];

function tableRows(markdown) {
  return markdown.split('\n').filter((line) => /^\| `[^`]+` \|/.test(line));
}

test('required documentation exists', () => {
  for (const path of docs) assert.ok(existsSync(resolve(root, path)), `missing ${path}`);
});

test('README has required exact section sequence and manifest-derived install commands', () => {
  const source = read('README.md');
  const sections = [...source.matchAll(/^## (.+)$/gm)].map((match) => match[1]);
  assert.deepEqual(sections, ['Problem', 'Philosophy', 'Workflow', 'Install', 'Customize', 'Compatibility', 'Provenance', 'License']);

  const codexMarket = json('.agents/plugins/marketplace.json');
  const claudeMarket = json('.claude-plugin/marketplace.json');
  const codexPlugin = codexMarket.plugins[0].name;
  const claudePlugin = claudeMarket.plugins[0].name;
  assert.match(source, new RegExp(`codex plugin install ${codexPlugin.replaceAll('-', '\\-')}`));
  assert.match(source, new RegExp(`/plugin marketplace add ${claudeMarket.name.replaceAll('-', '\\-')}`));
  assert.match(source, new RegExp(`/plugin install ${claudePlugin.replaceAll('-', '\\-')}@${claudeMarket.name.replaceAll('-', '\\-')}`));
});

test('workflow presents seven phases in order and maps included skills', () => {
  const source = read('docs/workflow.md');
  const phases = [...source.matchAll(/^## (Understand|Design|Plan|Implement|Verify|Review|Clean)$/gm)].map((match) => match[1]);
  assert.deepEqual(phases, ['Understand', 'Design', 'Plan', 'Implement', 'Verify', 'Review', 'Clean']);
  for (const name of names) assert.match(source, new RegExp(`\\b${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`));
  assert.match(source, /not every skill/i);
});

test('compatibility names exactly two verified hosts', () => {
  const rows = tableRows(read('docs/compatibility.md'));
  assert.equal(rows.length, 2);
  assert.deepEqual(rows.map((row) => row.split('|')[1].trim().replaceAll('`', '')), ['Codex', 'Claude Code']);
});

test('provenance inventory equals lock inventory', () => {
  const rows = tableRows(read('docs/provenance.md'));
  assert.deepEqual(rows.map((row) => row.split('|')[1].trim().replaceAll('`', '')).sort(), names);
  for (const skill of lock) {
    const row = rows.find((candidate) => candidate.startsWith(`| \`${skill.name}\` |`));
    assert.ok(row?.includes(`| ${skill.sourceType} |`), `wrong source type for ${skill.name}`);
  }
});

test('selective installation has one lock-derived row per skill', () => {
  const source = read('docs/selective-install.md');
  assert.match(source, /\| Skill \| Dependencies \| License files \| Lost workflow stage \|/);
  const rows = tableRows(source);
  assert.equal(rows.length, 19);
  assert.deepEqual(rows.map((row) => row.split('|')[1].trim().replaceAll('`', '')).sort(), names);
  for (const skill of lock) {
    const row = rows.find((candidate) => candidate.startsWith(`| \`${skill.name}\` |`));
    for (const dependency of skill.dependencies) assert.ok(row.includes(`\`${dependency}\``));
    const licenses = skill.licenseFiles?.map(({ path }) => path) ?? ['LICENSE'];
    for (const license of licenses) assert.ok(row.includes(license), `missing ${license} for ${skill.name}`);
    assert.doesNotMatch(row, /\|\s*\|/);
  }
});

test('customization documents lawful source edits and cache warning', () => {
  const source = read('docs/customization.md');
  assert.match(source, /fork/i);
  assert.match(source, /edit[^\n]*source/i);
  assert.match(source, /redistribut/i);
  assert.match(source, /license/i);
  assert.match(source, /do not edit[^\n]*cache/i);
});

test('all relative Markdown links resolve', () => {
  for (const path of docs) {
    const source = read(path);
    for (const match of source.matchAll(/\[[^\]]*\]\(([^)]+)\)/g)) {
      const target = match[1].split('#')[0];
      if (!target || /^[a-z]+:/i.test(target)) continue;
      assert.ok(existsSync(resolve(root, dirname(path), decodeURIComponent(target))), `${path}: broken link ${target}`);
    }
  }
});
