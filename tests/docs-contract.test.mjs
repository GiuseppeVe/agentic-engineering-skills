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

function cells(row) {
  return row.slice(1, -1).split('|').map((cell) => cell.trim().replaceAll('`', ''));
}

function fencedCommands(markdown) {
  return [...markdown.matchAll(/^```text\n([\s\S]*?)^```$/gm)].flatMap((match) => match[1].trim().split('\n'));
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
  assert.deepEqual(fencedCommands(source), [
    'codex plugin marketplace add GiuseppeVe/agentic-engineering-skills',
    `codex plugin add ${codexPlugin}@${codexMarket.name}`,
    'claude plugin marketplace add GiuseppeVe/agentic-engineering-skills',
    `claude plugin install ${claudePlugin}@${claudeMarket.name}`,
  ]);
  assert.match(source, /`codex plugin list --available --json`/);
  assert.match(source, /`claude plugin list`/);
  assert.match(source, /fresh host session/i);
  assert.match(source, /invoke one included skill/i);
});

test('workflow presents seven phases in order and maps included skills', () => {
  const source = read('docs/workflow.md');
  const phases = [...source.matchAll(/^## (Understand|Design|Plan|Implement|Verify|Review|Clean)$/gm)].map((match) => match[1]);
  assert.deepEqual(phases, ['Understand', 'Design', 'Plan', 'Implement', 'Verify', 'Review', 'Clean']);
  for (const name of names) assert.match(source, new RegExp(`\\b${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`));
  assert.match(source, /not every skill/i);
});

test('compatibility names exactly two verified hosts', () => {
  const source = read('docs/compatibility.md');
  const rows = tableRows(source);
  assert.equal(rows.length, 2);
  assert.deepEqual(rows.map(cells).map(([host, status]) => ({ host, status })), [
    { host: 'Codex', status: 'Verified' },
    { host: 'Claude Code', status: 'Verified' },
  ]);
  assert.match(source, /`codex plugin list --available --json`/);
  assert.match(source, /`claude plugin list`/);
  assert.match(source, /fresh corresponding host session/i);
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
    const [, dependencyCell, licenseCell, lostStage] = cells(row);
    const dependencies = dependencyCell === 'None' ? [] : dependencyCell.split(';').map((value) => value.trim());
    const licenses = licenseCell.split(';').map((value) => value.trim());
    assert.deepEqual(dependencies, skill.dependencies, `wrong dependencies for ${skill.name}`);
    assert.deepEqual(licenses, skill.licenseFiles?.map(({ path }) => path) ?? ['LICENSE'], `wrong licenses for ${skill.name}`);
    assert.match(lostStage, /^(Understand|Design|Plan|Implement|Verify|Review|Clean):\s*\S/);
  }
});

test('selective legal sets exactly join third-party notices', () => {
  const selective = new Map(tableRows(read('docs/selective-install.md')).map((row) => {
    const [name, , legal] = cells(row);
    return [name, legal.split(';').map((value) => value.trim())];
  }));
  const noticeRows = tableRows(read('THIRD_PARTY_NOTICES.md'));
  const noticeLegal = new Map(noticeRows.map((row) => {
    const rowCells = cells(row);
    return [rowCells[0], rowCells[6].split('<br>').map((value) => value.trim())];
  }));
  for (const skill of lock.filter(({ sourceType }) => sourceType !== 'original')) {
    assert.deepEqual(selective.get(skill.name), noticeLegal.get(skill.name), `notice mismatch for ${skill.name}`);
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
