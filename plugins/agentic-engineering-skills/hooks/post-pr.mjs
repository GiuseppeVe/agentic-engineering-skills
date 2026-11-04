#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { claimPrReminder, emitHookOutput, githubPullUrl, isSuccessfulToolEvent, parseHookInput, safeInline } from './hook-lib.mjs';

const DEFAULT_STEPS = [
  { skill: 'cleaning-repo-with-knip', role: 'ottimizza, non solo analizza: applica le correzioni sicure sulle modifiche della PR dopo aver verificato riferimenti, compatibilità e registro delle conservazioni; i finding fuori perimetro restano follow-up' },
  { skill: 'simplify', role: 'dopo Knip, sulle sole modifiche della PR: solo semplificazioni che preservano il comportamento' },
];
const MCP_CREATE = /^mcp__[\w.-]+__(?:create_pull_request|pull_request[_a-z]*create|create_pr)$/i;
const PR_URL = /^https:\/\/github\.com\/[\w.-]+\/[\w.-]+\/pull\/\d+$/i;

export function isPullRequestCreate(input) {
  if (input?.tool_name === 'Bash') {
    const words = prCreateWords(input?.tool_input?.command);
    return words?.[0]?.toLowerCase() === 'gh' && words[1]?.toLowerCase() === 'pr' && words[2]?.toLowerCase() === 'create';
  }
  return typeof input?.tool_name === 'string' && MCP_CREATE.test(input.tool_name);
}

// Classify a single shell command without expanding or executing its arguments.
// Unlike the merge parser, quoted PR bodies can contain substitutions and newlines.
function prCreateWords(command) {
  if (typeof command !== 'string' || command.length > 20_000) return null;
  const source = command.trim();
  const words = [];
  let word = '';
  let started = false;
  for (let index = 0; index < source.length;) {
    const char = source[index];
    if (char === ' ' || char === '\t') {
      if (started) words.push(word);
      word = ''; started = false; index++; continue;
    }
    if (char === "'" || char === '"') {
      const quoted = readQuoted(source, index, 0);
      if (!quoted) return null;
      word += quoted.value; started = true; index = quoted.end; continue;
    }
    // Operators, expansions and newlines outside quotes can alter the command.
    if (/[$`\\\r\n;&|<>()[\]{}#]/.test(char)) return null;
    word += char; started = true; index++;
  }
  if (started) words.push(word);
  return words;
}

function readQuoted(source, start, depth) {
  if (depth > 32) return null;
  const quote = source[start];
  let value = '';
  for (let index = start + 1; index < source.length;) {
    const char = source[index];
    if (char === quote) return { value, end: index + 1 };
    if (quote !== "'" && char === '\\') {
      if (++index === source.length) return null;
      const escaped = source[index++];
      if (escaped === '\n') continue;
      value += '$`"\\'.includes(escaped) ? escaped : `\\${escaped}`;
      continue;
    }
    if (quote === '"' && (char === '`' || source.startsWith('$(', index))) {
      const end = readSubstitution(source, index, depth + 1);
      if (end === null) return null;
      // Dynamic text must never masquerade as the literal gh/pr/create prefix.
      value += '\0'; index = end; continue;
    }
    value += char; index++;
  }
  return null;
}

function readSubstitution(source, start, depth) {
  if (depth > 32) return null;
  const backtick = source[start] === '`';
  let parentheses = 1;
  for (let index = start + (backtick ? 1 : 2); index < source.length;) {
    const char = source[index];
    if (char === '\\') { index += 2; continue; }
    if (backtick) {
      if (char === '`') return index + 1;
      index++; continue;
    }
    // Heredocs and comments need a full shell grammar; fail closed instead.
    if (char === '#' || source.startsWith('<<', index)) return null;
    if (char === "'" || char === '"') {
      const quoted = readQuoted(source, index, depth + 1);
      if (!quoted) return null;
      index = quoted.end; continue;
    }
    if (char === '`') {
      const end = readSubstitution(source, index, depth + 1);
      if (end === null) return null;
      index = end; continue;
    }
    if (char === '(') parentheses++;
    if (char === ')' && --parentheses === 0) return index + 1;
    index++;
  }
  return null;
}

export function postPrContext(input, { lookupBranch = getHeadBranch, steps = loadSteps() } = {}) {
  if (!isSuccessfulToolEvent(input) || !isPullRequestCreate(input)) return null;
  const url = githubPullUrl(input?.tool_response);
  if (!url || !PR_URL.test(url)) return null;
  const branch = safeBranch(lookupBranch(url));
  const renderedSteps = normalizeSteps(steps);
  const list = renderedSteps.map((step, index) => `${index + 1}. skill \`${step.skill}\`${step.role ? ` (${safeInline(step.role, 300)})` : ''}`).join('\n');
  const verifier = fileURLToPath(new URL('./pr-workflow-check.mjs', import.meta.url));
  const billingGuide = fileURLToPath(new URL('./billing-fallback.md', import.meta.url));
  const context = [
    `[pr-skills] Aperta la PR ${url}${branch ? ` (branch \`${branch}\`)` : ''}.`,
    'Segui le istruzioni del progetto e lavora nel worktree della PR. Prima completa i gate CI e una review indipendente sulla stessa head corrente; non avviare le skill mentre i risultati sono mancanti, in attesa o negativi.',
    `Usa il verifier del plugin ${JSON.stringify(verifier)} con Node: pr-workflow-check.mjs preflight <URL-PR> <review-record.json>. Il record deve attestare head_sha, outcome passed, independent true, required_checks, reviewer, evidence e evidence_sha256; conserva evidenza e record fuori dai file non ignorati del worktree. Ricava required_checks dalla policy CI del progetto, escludendo il controllo del marcatore; il verifier deve rispondere READY prima di avviare la sequenza.`,
    `Se GitHub CI è bloccata per billing, segui ${JSON.stringify(billingGuide)}: il verifier può restituire READY LOCAL BILLING FALLBACK solo con policy attendibile, annotazioni GitHub, gate locali completi e review indipendente del dossier; questo non rende verde la CI hosted né autorizza il merge.`,
    'Solo dopo READY, esegui in sequenza:',
    list,
    'Applica, committa e pusha solo le correzioni autorizzate sul branch della PR. Dopo ogni nuova head ripeti gate, review indipendente e preflight prima di rieseguire le skill; prosegui finché la head finale non è verificata.',
    'Dopo Knip e Simplify conclusi con successo e dopo i gate e la review sulla head finale, registra se autorizzato un commento con il marcatore in prima riga:',
    '<!-- pr-skills:v1 {"commit_sha":"<sha40>","knip":"passed","simplify":"no_changes"} -->',
    'Per ogni skill usa solo passed, applied o no_changes se conclusa; failed, blocked o not_run non sono successi. Verifica il marcatore con pr-workflow-check.mjs marker <URL-PR>; se il progetto richiede npm run pr:skills-check, esegui anche quello. Il verifier del plugin non sostituisce gli altri gate.',
    'Le verifiche sono puntuali: se la sessione termina o la head cambia, riavvia il ciclo sulla head corrente. Nessun merge da questa istruzione.',
  ].join('\n');
  if (!claimPrReminder(input.session_id, url)) return null;
  return context;
}

function safeBranch(value) {
  if (typeof value !== 'string') return undefined;
  const branch = value.trim();
  return /^[A-Za-z0-9._/-]{1,200}$/.test(branch) ? branch : undefined;
}

function normalizeSteps(steps) {
  if (!Array.isArray(steps) || steps.length === 0) return DEFAULT_STEPS;
  const valid = steps.filter(step => step && typeof step.skill === 'string' && /^[a-z0-9][a-z0-9-]{0,79}$/i.test(step.skill));
  return valid.length ? valid.map(step => ({ skill: step.skill, role: typeof step.role === 'string' ? step.role : '' })) : DEFAULT_STEPS;
}

function loadSteps() {
  try {
    const config = JSON.parse(readFileSync(resolve(dirname(fileURLToPath(import.meta.url)), 'pr-skills.json'), 'utf8'));
    return normalizeSteps(config.steps);
  } catch { return DEFAULT_STEPS; }
}

function getHeadBranch(url) {
  const result = spawnSync('gh', ['pr', 'view', url, '--json', 'headRefName', '--jq', '.headRefName'], { encoding: 'utf8', timeout: 10_000, windowsHide: true });
  return result.error || result.status !== 0 ? undefined : result.stdout.trim() || undefined;
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const input = parseHookInput(readFileSync(0, 'utf8'));
    emitHookOutput(postPrContext(input));
  } catch { /* Hook failure must not break completed tool call. */ }
}
