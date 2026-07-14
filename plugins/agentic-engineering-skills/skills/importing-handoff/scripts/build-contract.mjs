#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';

const fail = (message) => { throw new Error(message); };

function args(argv) {
  const result = {};
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (token === '--manifest') result.manifest = argv[++i];
    else if (token === '--draft') result.draft = argv[++i];
    else if (token === '--out') result.out = argv[++i];
    else fail(`Unknown argument: ${token}`);
  }
  for (const key of ['manifest', 'draft', 'out']) if (!result[key]) fail(`Missing required --${key} <path>`);
  return result;
}

async function json(path, label) {
  let text;
  try { text = await readFile(path, 'utf8'); }
  catch (error) { fail(`Cannot read ${label} ${path}: ${error.message}`); }
  try { return JSON.parse(text); }
  catch (error) { fail(`Invalid JSON in ${label} ${path}: ${error.message}`); }
}

function present(object, key) {
  if (!Object.hasOwn(object, key)) fail(`CONTRACT_UNKNOWN: missing explicit observable field "${key}"`);
}

function array(object, key, { nonempty = false } = {}) {
  present(object, key);
  if (!Array.isArray(object[key])) fail(`CONTRACT_UNKNOWN: "${key}" must be an array`);
  if (nonempty && object[key].length === 0) fail(`CONTRACT_UNKNOWN: "${key}" must not be empty`);
  return object[key];
}

function strings(object, key, options) {
  const value = array(object, key, options);
  if (value.some((item) => typeof item !== 'string' || item.trim() === '')) fail(`CONTRACT_UNKNOWN: every "${key}" item must be a non-empty string`);
  if (new Set(value).size !== value.length) fail(`CONTRACT_UNKNOWN: "${key}" contains duplicates`);
  return value;
}

function validate(draft) {
  if (!draft || typeof draft !== 'object' || Array.isArray(draft)) fail('CONTRACT_UNKNOWN: draft must be a JSON object');
  present(draft, 'name');
  if (typeof draft.name !== 'string' || !draft.name.trim()) fail('CONTRACT_UNKNOWN: "name" must be a non-empty string');
  const routes = strings(draft, 'routes', { nonempty: true });
  const languages = strings(draft, 'languages', { nonempty: true });
  const screens = strings(draft, 'screens', { nonempty: true });
  const initialStates = strings(draft, 'initialStates', { nonempty: true });
  const states = strings(draft, 'states', { nonempty: true });
  const copy = strings(draft, 'copy');
  const motion = strings(draft, 'motion');
  const assets = array(draft, 'assets');
  const breakpoints = array(draft, 'breakpoints');
  const interactions = array(draft, 'interactions');
  const viewports = array(draft, 'viewports', { nonempty: true });
  present(draft, 'reducedMotion');
  if (typeof draft.reducedMotion !== 'boolean') fail('CONTRACT_UNKNOWN: "reducedMotion" must be boolean');
  for (const route of routes) if (!route.startsWith('/')) fail(`CONTRACT_UNKNOWN: route must start with "/": ${route}`);
  for (const state of initialStates) if (!states.includes(state)) fail(`CONTRACT_UNKNOWN: initial state is absent from states: ${state}`);
  if (breakpoints.some((item) => !Number.isFinite(item) || item < 0)) fail('CONTRACT_UNKNOWN: breakpoints must be non-negative numbers');
  if (new Set(breakpoints).size !== breakpoints.length) fail('CONTRACT_UNKNOWN: breakpoints contains duplicates');
  const viewportNames = new Set();
  for (const viewport of viewports) {
    if (!viewport || typeof viewport !== 'object' || Array.isArray(viewport)) fail('CONTRACT_UNKNOWN: each viewport must be an object');
    if (typeof viewport.name !== 'string' || !viewport.name.trim()) fail('CONTRACT_UNKNOWN: each viewport needs a non-empty name');
    if (!Number.isInteger(viewport.width) || viewport.width < 1 || !Number.isInteger(viewport.height) || viewport.height < 1) fail(`CONTRACT_UNKNOWN: viewport ${viewport.name} needs positive integer width and height`);
    if (viewportNames.has(viewport.name)) fail(`CONTRACT_UNKNOWN: duplicate viewport name: ${viewport.name}`);
    viewportNames.add(viewport.name);
  }
  const interactionIds = new Set();
  for (const interaction of interactions) {
    if (!interaction || typeof interaction !== 'object' || Array.isArray(interaction)) fail('CONTRACT_UNKNOWN: each interaction must be an object');
    for (const key of ['id', 'action', 'result']) if (typeof interaction[key] !== 'string' || !interaction[key].trim()) fail(`CONTRACT_UNKNOWN: interaction requires non-empty "${key}"`);
    if (interactionIds.has(interaction.id)) fail(`CONTRACT_UNKNOWN: duplicate interaction id: ${interaction.id}`);
    interactionIds.add(interaction.id);
  }
  return { name: draft.name, routes, languages, viewports, copy, assets, screens, initialStates, states, interactions, breakpoints, motion, reducedMotion: draft.reducedMotion };
}

function slug(value) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'root';
}

function cellId(cell) {
  const raw = `${cell.route}\0${cell.language}\0${cell.viewport.name}\0${cell.state}`;
  const hash = createHash('sha256').update(raw).digest('hex').slice(0, 10);
  return `${slug(cell.route)}--${slug(cell.language)}--${slug(cell.viewport.name)}--${slug(cell.state)}--${hash}`;
}

async function main() {
  const options = args(process.argv.slice(2));
  const manifestPath = resolve(options.manifest);
  const draftPath = resolve(options.draft);
  const outputPath = resolve(options.out);
  const [manifest, draft] = await Promise.all([json(manifestPath, 'manifest'), json(draftPath, 'draft')]);
  const sourceSha256 = manifest?.source?.sha256;
  if (typeof sourceSha256 !== 'string' || !/^[a-f0-9]{64}$/i.test(sourceSha256)) fail('Manifest missing valid source.sha256');
  const observables = validate(draft);
  const cells = [];
  for (const route of observables.routes) for (const language of observables.languages) for (const viewport of observables.viewports) for (const state of observables.states) {
    const cell = { route, language, viewport: { ...viewport }, state };
    cells.push({ id: cellId(cell), ...cell });
  }
  const contract = {
    schemaVersion: 1,
    name: observables.name,
    sourceSha256: sourceSha256.toLowerCase(),
    source: { ...manifest.source, sha256: sourceSha256.toLowerCase() },
    observables,
    matrix: {
      routes: [...observables.routes], languages: [...observables.languages], viewports: observables.viewports.map((item) => ({ ...item })), states: [...observables.states], cells,
    },
    setup: { identicalMatrixRequired: true, exactObservableComparison: true, geometryMasksAllowed: false, materialThresholdAllowed: false },
    completion: { complete: true, expectedCells: cells.length, missingFields: [] },
  };
  await mkdir(dirname(outputPath), { recursive: true });
  await writeFile(outputPath, `${JSON.stringify(contract, null, 2)}\n`);
  process.stdout.write(`${outputPath}\n`);
}

main().catch((error) => { process.stderr.write(`build-contract: ${error.message}\n`); process.exitCode = 1; });
