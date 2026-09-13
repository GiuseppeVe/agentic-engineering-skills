import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, relative, resolve, sep } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const read = (path) => readFileSync(resolve(root, path), 'utf8');
const json = (path) => JSON.parse(read(path));
const lock = json('manifests/skills.lock.json').skills;
const names = lock.map(({ name }) => name).sort();
const profiles = json('manifests/agent-profiles.json').profiles.map(({ name }) => name).sort();
const docs = [
  'README.md',
  'docs/agent-profiles.md',
  'docs/philosophy.md',
  'docs/workflow.md',
  'docs/customization.md',
  'docs/compatibility.md',
  'docs/provenance.md',
  'docs/release-checklist.md',
  'docs/release-report.md',
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

function section(markdown, heading) {
  const marker = `## ${heading}\n`;
  const start = markdown.indexOf(marker);
  assert.notEqual(start, -1, `missing section: ${heading}`);
  const contentStart = start + marker.length;
  const nextHeading = markdown.indexOf('\n## ', contentStart);
  return markdown.slice(contentStart, nextHeading === -1 ? undefined : nextHeading);
}

function mermaidBlocks(markdown) {
  return [...markdown.matchAll(/^```mermaid\n([\s\S]*?)^```$/gm)].map((match) => match[1]);
}

test('required documentation exists', () => {
  for (const path of docs) assert.ok(existsSync(resolve(root, path)), `missing ${path}`);
});

test('README has required exact section sequence and manifest-derived install commands', () => {
  const source = read('README.md');
  const sections = [...source.matchAll(/^## (.+)$/gm)].map((match) => match[1]);
  assert.deepEqual(sections, [
    'What this repository shares',
    'My working philosophy',
    'How I use the workflow',
    'The quality loop',
    'Supporting skills',
    'Example: choosing a route',
    'Workflow at a glance',
    'Install',
    'Customize',
    'Compatibility',
    'Provenance',
    'License',
  ]);

  const codexMarket = json('.agents/plugins/marketplace.json');
  const claudeMarket = json('.claude-plugin/marketplace.json');
  const codexPlugin = codexMarket.plugins[0].name;
  const claudePlugin = claudeMarket.plugins[0].name;
  assert.deepEqual(fencedCommands(section(source, 'Install')), [
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

test('README keeps the hero-led opening and experience-shaped framing', () => {
  const source = read('README.md');
  const lines = source.split('\n');

  assert.equal(lines[0], '# Agentic Engineering Skills');
  assert.equal(
    lines[2],
    '![Agentic Engineering Skills — shared workflow from evidence to reviewed delivery](assets/agentic-engineering-skills-hero.svg)',
  );
  assert.match(lines[4], /^I share this experience-shaped workflow/);
  assert.equal(lines[5], '');
  assert.equal(lines[6], '## What this repository shares');
  assert.doesNotMatch(lines.slice(0, 6).join('\n'), /Wayfinder|Brainstorming|Grill-me|To Spec|Writing Plans/);
});

test('README documents conditional workflow routing and example', () => {
  const source = read('README.md');
  const routing = section(source, 'How I use the workflow');
  const example = section(source, 'Example: choosing a route');

  for (const [situation, path] of [
    ['Large, uncertain initiative', 'Wayfinder'],
    ['Bounded or creative design', 'Brainstorming'],
    ['Consequential or disputed design', 'Grill-me'],
    ['Agreed design', 'To Spec'],
    ['Multi-step implementation', 'Writing Plans'],
    ['Large implementation', 'Sequential Task Orchestrator'],
    ['Small implementation', 'Codex Implement'],
    ['Claude Code implementation', 'Claude Implement'],
  ]) {
    assert.ok(routing.includes(`| ${situation} | \`${path}\` |`), `missing routing row: ${situation}`);
  }

  assert.match(routing, /composable choices, not mandatory stages/i);
  assert.match(example, /diagram below shows the shared lifecycle/i);
  assert.match(example, /large change spanning multiple modules[\s\S]*Wayfinder[\s\S]*Sequential Task Orchestrator/i);
  assert.match(example, /small, well-understood change[\s\S]*Codex Implement[\s\S]*owner-approval gates/i);
});

test('README explains philosophy, quality signals, and supporting skills', () => {
  const source = read('README.md');
  const philosophy = section(source, 'My working philosophy');
  const quality = section(source, 'The quality loop');
  const supporting = section(source, 'Supporting skills');

  for (const concept of [
    /start from evidence/i,
    /durable specifications and traceable plans/i,
    /isolate implementation work/i,
    /worker output separate from independent evidence/i,
    /faithful to its plan/i,
    /implemented behavior is correct/i,
    /explicit owner control/i,
  ]) assert.match(philosophy, concept);

  assert.match(quality, /`Test Gaps` checks plan fidelity/i);
  assert.match(quality, /`Test-Driven Development` checks implementation correctness/i);
  assert.match(quality, /TDD fix cycle before acceptance/i);

  for (const skill of ['Impeccable', 'UI UX Pro Max', 'Caveman', 'How to Use Codex', 'Cleaning Repo with Knip', 'Improve Codebase Architecture', 'Graph Engineering V5.2']) {
    assert.ok(supporting.includes(`\`${skill}\``), `missing supporting skill: ${skill}`);
  }
  assert.match(supporting, /bounded end-to-end testing and debugging route/i);
  assert.match(supporting, /deterministic pauses instead of broad audits/i);
});

test('README owns the canonical workflow overview without duplicating it in the guide', () => {
  const readme = read('README.md');
  const workflow = read('docs/workflow.md');
  const readmeDiagrams = mermaidBlocks(readme);
  const workflowDiagrams = mermaidBlocks(workflow);

  assert.equal(readmeDiagrams.length, 1, 'README must contain exactly one Mermaid overview');
  assert.equal(workflowDiagrams.length, 1, 'workflow guide must contain only its detailed routing diagram');

  const overview = readmeDiagrams[0];
  const canonicalStages = ['Understand', 'Design', 'Plan', 'Implement', 'Verify', 'Review', 'Clean'];
  const positions = canonicalStages.map((stage) => overview.indexOf(`[${stage}]`));
  assert.ok(positions.every((position) => position >= 0), 'overview must contain every canonical stage');
  assert.deepEqual([...positions].sort((a, b) => a - b), positions, 'overview stages must appear in canonical order');
  assert.match(overview, /Owner approves publication\?/);

  assert.match(readme, /\[workflow guide\]\(docs\/workflow\.md\)/i);
  assert.match(workflowDiagrams[0], /Incoming work/);
  assert.match(workflowDiagrams[0], /Explicit owner approval\?/);
});

test('primary documentation links a complete, auditable workflow philosophy', () => {
  const readme = read('README.md');
  const workflow = read('docs/workflow.md');
  const philosophy = read('docs/philosophy.md');

  assert.match(readme, /\[workflow philosophy\]\(docs\/philosophy\.md\)/i);
  assert.match(workflow, /\[workflow philosophy\]\(philosophy\.md\)/i);

  for (const heading of [
    'Discover before deciding',
    'Preserve intent in durable artifacts',
    'Isolate implementation and separate evidence',
    'Validate behavior, fidelity, and public surface',
    'Treat maintenance as research-led change',
    'Keep advanced tools optional and honest',
    'Keep publication human-approved',
  ]) {
    assert.match(philosophy, new RegExp(`^## ${heading}$`, 'm'), `missing philosophy section: ${heading}`);
  }

  assert.match(philosophy, /provenance/i);
  assert.match(philosophy, /manual fallback/i);
  assert.match(philosophy, /explicit owner approval/i);
  assert.ok((philosophy.match(/^```mermaid$/gm) ?? []).length >= 2, 'expected at least two Mermaid workflow diagrams');

  for (const link of [
    '[Workflow guide](workflow.md)',
    '[Provenance guide](provenance.md)',
    '[Agent profiles](agent-profiles.md)',
    '[Release checklist](release-checklist.md)',
    '[Customization guide](customization.md)',
  ]) assert.ok(philosophy.includes(link), `missing related-work link: ${link}`);
});

test('workflow presents seven phases in order and maps included skills', () => {
  const source = read('docs/workflow.md');
  const phases = [...source.matchAll(/^## (Understand|Design|Plan|Implement|Verify|Review|Clean)$/gm)].map((match) => match[1]);
  assert.deepEqual(phases, ['Understand', 'Design', 'Plan', 'Implement', 'Verify', 'Review', 'Clean']);
  for (const name of names) assert.match(source, new RegExp(`\\b${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`));
  assert.match(source, /not every skill/i);
});

test('aggregate routing guides cover every public skill and agent profile', () => {
  const workflow = read('docs/workflow.md');
  const agentProfiles = read('docs/agent-profiles.md');

  assert.match(workflow, /\[workflow philosophy\]\(philosophy\.md\)/i);
  assert.match(workflow, /every included public skill/i);
  for (const name of names) assert.match(workflow, new RegExp(`\\b${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`));

  assert.match(agentProfiles, /\[workflow philosophy\]\(philosophy\.md\)/i);
  assert.match(agentProfiles, /every included public agent profile/i);
  for (const name of profiles) assert.match(agentProfiles, new RegExp(`\\b${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`));
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
  assert.equal(rows.length, lock.length);
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

test('all relative Markdown links resolve to Git-tracked files', () => {
  const tracked = new Set(execFileSync('git', ['ls-files', '-z'], { cwd: root })
    .toString('utf8')
    .split('\0')
    .filter(Boolean)
    .map((path) => path.replaceAll('\\', '/')));
  for (const path of docs) {
    const source = read(path);
    for (const match of source.matchAll(/\[[^\]]*\]\(([^)]+)\)/g)) {
      const target = match[1].split('#')[0];
      if (!target || /^[a-z]+:/i.test(target)) continue;
      const absoluteTarget = resolve(root, dirname(path), decodeURIComponent(target));
      const repoTarget = relative(root, absoluteTarget).split(sep).join('/');
      assert.ok(existsSync(absoluteTarget), `${path}: broken link ${target}`);
      assert.ok(tracked.has(repoTarget), `${path}: link target is not Git-tracked: ${target}`);
    }
  }
});
