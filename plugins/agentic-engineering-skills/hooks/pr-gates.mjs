#!/usr/bin/env node
// PostToolUse hook: after a shell command opened a non-draft pull request or
// marked one ready, start the repository's own `gates:pr` script in the
// background. It launches and reports where the log is; it never blocks,
// verifies or reminds. Any doubt about the command means: do nothing.
import { spawn, spawnSync } from 'node:child_process';
import { appendFileSync, closeSync, existsSync, mkdirSync, openSync, readFileSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const SCRIPT = 'gates:pr';
const RUN_FLAG = '--run-gates';
const DYNAMIC = '\0';
const PULL_URL = /https:\/\/github\.com\/[\w.-]+\/[\w.-]+\/pull\/\d+/i;
// gh flags that consume the next word, so a value is never read as a flag.
const VALUE_FLAGS = {
  create: {
    long: ['assignee', 'base', 'body', 'body-file', 'head', 'label', 'milestone', 'project', 'recover', 'repo', 'reviewer', 'template', 'title'],
    short: 'aBbFHlmprtTR',
  },
  ready: { long: ['repo'], short: 'R' },
};
const NO_PR_FLAGS = ['--web', '--dry-run', '--help', '--undo'];

// Split shell text into simple commands, each a list of words. Returns null
// when the text cannot be read with confidence. Substituted or expanded text
// becomes DYNAMIC, so it can never pass for a literal word.
export function splitCommands(source, { powershell = false } = {}) {
  if (typeof source !== 'string' || source.length > 100_000) return null;
  const escape = powershell ? '`' : '\\';
  const commands = [];
  const heredocs = [];
  let words = [];
  let word = '';
  let started = false;
  let index = 0;
  const endWord = () => { if (started) words.push(word); word = ''; started = false; };
  const endCommand = () => { endWord(); if (words.length) commands.push(words); words = []; };

  while (index < source.length) {
    const char = source[index];
    const next = source[index + 1];
    if (char === '\r') { index++; continue; }
    if (char === '\n') {
      endCommand();
      index++;
      while (heredocs.length) {
        index = skipHeredocBody(source, index, heredocs.shift());
        if (index === null) return null;
      }
      continue;
    }
    if (char === ' ' || char === '\t') { endWord(); index++; continue; }
    if (char === escape) {
      if (next === undefined) return null;
      if (next === '\n') { index += 2; continue; }
      if (next === '\r' && source[index + 2] === '\n') { index += 3; continue; }
      word += next; started = true; index += 2; continue;
    }
    if (powershell && char === '@' && (next === "'" || next === '"') && !started) {
      const end = source.indexOf(`\n${next}@`, index + 2);
      if (end === -1) return null;
      word += DYNAMIC; started = true; index = end + 3; continue;
    }
    if (char === "'") {
      const end = source.indexOf("'", index + 1);
      if (end === -1) return null;
      word += source.slice(index + 1, end); started = true; index = end + 1; continue;
    }
    if (char === '"') {
      const quoted = readDoubleQuoted(source, index, escape, powershell);
      if (!quoted) return null;
      word += quoted.value; started = true; index = quoted.end; continue;
    }
    if (char === '$' && next === '(') {
      const end = skipSubstitution(source, index + 2, escape, powershell);
      if (end === null) return null;
      word += DYNAMIC; started = true; index = end; continue;
    }
    if (char === '$' && next !== undefined && /[\w{?@*!#$-]/.test(next)) { word += DYNAMIC; started = true; index++; continue; }
    if (char === '`') {
      const end = source.indexOf('`', index + 1);
      if (end === -1) return null;
      word += DYNAMIC; started = true; index = end + 1; continue;
    }
    if (char === '#' && !started) {
      const end = source.indexOf('\n', index);
      index = end === -1 ? source.length : end;
      continue;
    }
    if (char === '<' && next === '<' && !powershell) {
      if (source[index + 2] === '<') return null;
      const heredoc = readHeredocStart(source, index + 2);
      if (!heredoc) return null;
      heredocs.push(heredoc); endWord(); index = heredoc.end; continue;
    }
    if (char === '&' && (source[index - 1] === '>' || source[index - 1] === '<' || next === '>')) { word += char; started = true; index++; continue; }
    if (char === ';' || char === '&' || char === '|' || char === '(' || char === ')') { endCommand(); index++; continue; }
    word += char; started = true; index++;
  }
  if (heredocs.length) return null;
  endCommand();
  return commands;
}

function readDoubleQuoted(source, start, escape, powershell) {
  let value = '';
  for (let index = start + 1; index < source.length;) {
    const char = source[index];
    if (char === '"') {
      if (powershell && source[index + 1] === '"') { value += '"'; index += 2; continue; }
      return { value, end: index + 1 };
    }
    if (char === escape) {
      if (index + 1 >= source.length) return null;
      value += source[index + 1]; index += 2; continue;
    }
    if (char === '$' && source[index + 1] === '(') {
      const end = skipSubstitution(source, index + 2, escape, powershell);
      if (end === null) return null;
      value += DYNAMIC; index = end; continue;
    }
    if (char === '`') {
      const end = source.indexOf('`', index + 1);
      if (end === -1) return null;
      value += DYNAMIC; index = end + 1; continue;
    }
    if (char === '$' && /[\w{]/.test(source[index + 1] ?? '')) { value += DYNAMIC; index++; continue; }
    value += char; index++;
  }
  return null;
}

// Returns the index after the `)` that closes a `$(` opened before `start`.
function skipSubstitution(source, start, escape, powershell, depth = 0) {
  if (depth > 16) return null;
  const heredocs = [];
  let parentheses = 1;
  for (let index = start; index < source.length;) {
    const char = source[index];
    if (char === '\n' && heredocs.length) {
      index++;
      while (heredocs.length) {
        index = skipHeredocBody(source, index, heredocs.shift());
        if (index === null) return null;
      }
      continue;
    }
    if (char === escape) { index += 2; continue; }
    if (char === "'") {
      const end = source.indexOf("'", index + 1);
      if (end === -1) return null;
      index = end + 1; continue;
    }
    if (char === '"') {
      const quoted = readDoubleQuoted(source, index, escape, powershell);
      if (!quoted) return null;
      index = quoted.end; continue;
    }
    if (char === '`') {
      const end = source.indexOf('`', index + 1);
      if (end === -1) return null;
      index = end + 1; continue;
    }
    if (char === '$' && source[index + 1] === '(') {
      const end = skipSubstitution(source, index + 2, escape, powershell, depth + 1);
      if (end === null) return null;
      index = end; continue;
    }
    if (char === '<' && source[index + 1] === '<' && !powershell) {
      if (source[index + 2] === '<') return null;
      const heredoc = readHeredocStart(source, index + 2);
      if (!heredoc) return null;
      heredocs.push(heredoc); index = heredoc.end; continue;
    }
    if (char === '(') parentheses++;
    if (char === ')' && --parentheses === 0) return heredocs.length ? null : index + 1;
    index++;
  }
  return null;
}

function readHeredocStart(source, start) {
  let index = start;
  const stripTabs = source[index] === '-';
  if (stripTabs) index++;
  while (source[index] === ' ' || source[index] === '\t') index++;
  const match = /^(?:'([^'\n]+)'|"([^"\n]+)"|\\?([\w.-]+))/.exec(source.slice(index, index + 200));
  if (!match) return null;
  return { delimiter: match[1] ?? match[2] ?? match[3], stripTabs, end: index + match[0].length };
}

// Returns the index of the line break that ends the delimiter line.
function skipHeredocBody(source, start, { delimiter, stripTabs }) {
  for (let index = start; index <= source.length;) {
    let end = source.indexOf('\n', index);
    if (end === -1) end = source.length;
    let line = source.slice(index, end).replace(/\r$/, '');
    if (stripTabs) line = line.replace(/^\t+/, '');
    if (line === delimiter) return end;
    if (end === source.length) return null;
    index = end + 1;
  }
  return null;
}

// Classify one simple command. Returns { action: 'create' | 'ready', ref }
// for a command that takes a pull request out of draft, otherwise null.
export function classifyGhCommand(words) {
  if (!Array.isArray(words)) return null;
  let index = 0;
  while (index < words.length && /^[A-Za-z_]\w*=/.test(words[index])) index++;
  const program = words[index++];
  if (typeof program !== 'string' || !/^(?:.*[\\/])?gh(?:\.exe)?$/i.test(program)) return null;
  index = skipRepoFlags(words, index);
  if (words[index++] !== 'pr') return null;
  index = skipRepoFlags(words, index);
  const subcommand = words[index++];
  const action = subcommand === 'create' || subcommand === 'new' ? 'create' : subcommand === 'ready' ? 'ready' : null;
  if (!action) return null;

  const { long, short } = VALUE_FLAGS[action];
  const positionals = [];
  for (; index < words.length; index++) {
    const arg = words[index];
    if (/^\d*[<>]/.test(arg)) { if (/^\d*[<>]+&?$/.test(arg)) index++; continue; }
    if (arg === '--') return null;
    if (arg.startsWith('--')) {
      const [name, value] = splitLongFlag(arg);
      if (name.includes(DYNAMIC)) return null;
      if (NO_PR_FLAGS.includes(name)) return null;
      if (name === '--draft') {
        if (action !== 'create' || value !== 'false') return null;
        continue;
      }
      if (value === undefined && long.includes(name.slice(2))) index++;
      continue;
    }
    if (arg.startsWith('-') && arg.length > 1) {
      for (let position = 1; position < arg.length; position++) {
        const flag = arg[position];
        if (flag === DYNAMIC || flag === 'd' || flag === 'w' || flag === 'h') return null;
        if (short.includes(flag)) {
          if (position === arg.length - 1) index++;
          break;
        }
      }
      continue;
    }
    if (arg.includes(DYNAMIC)) return null;
    positionals.push(arg);
  }
  if (action === 'create') return positionals.length ? null : { action, ref: null };
  if (positionals.length > 1) return null;
  return { action, ref: pullReference(positionals[0]) };
}

function skipRepoFlags(words, start) {
  let index = start;
  for (;;) {
    const word = words[index];
    if (word === '-R' || word === '--repo') index += 2;
    else if (typeof word === 'string' && word.startsWith('--repo=')) index++;
    else return index;
  }
}

function splitLongFlag(arg) {
  const equals = arg.indexOf('=');
  return equals === -1 ? [arg, undefined] : [arg.slice(0, equals), arg.slice(equals + 1)];
}

function pullReference(value) {
  if (typeof value !== 'string') return null;
  if (/^#?\d{1,9}$/.test(value)) return value.replace('#', '');
  const url = PULL_URL.exec(value);
  return url && url[0] === value ? value : null;
}

// Find the first command of a shell text that takes a pull request out of
// draft. `directory` is the literal target of a `cd` that precedes it.
export function findPullRequestCommand(command, options) {
  const commands = splitCommands(command, options);
  if (!commands) return null;
  let directory = null;
  for (const words of commands) {
    if (/^(?:cd|pushd|Set-Location|sl)$/i.test(words[0])) {
      const target = words.length === 2 && !words[1].includes(DYNAMIC) && !words[1].startsWith('-') ? words[1] : null;
      if (!target) return null;
      directory = directory && !isAbsolute(target) ? `${directory}/${target}` : target;
      continue;
    }
    const found = classifyGhCommand(words);
    if (found) return { ...found, directory };
  }
  return null;
}

function isAbsolute(target) {
  return target.startsWith('/') || target.startsWith('~') || /^[A-Za-z]:[\\/]/.test(target) || target.startsWith('\\\\');
}

export function isSuccessfulToolEvent(input) {
  if (input?.is_error === true || input?.isError === true) return false;
  const response = input?.tool_response;
  if (response && typeof response === 'object') {
    if (response.is_error === true || response.isError === true || response.interrupted === true) return false;
    for (const key of ['exitCode', 'exit_code', 'statusCode']) {
      if (response[key] != null && Number(response[key]) !== 0) return false;
    }
    if (response.error) return false;
  }
  if (typeof response === 'string' && /(?:exit(?:ed)?(?:\s+with)?\s+code|exit_code)["']?\s*[:=]?\s*[1-9]\d*/i.test(response)) return false;
  return true;
}

function responseText(value) {
  if (typeof value === 'string') return value;
  if (value == null) return '';
  try { return JSON.stringify(value).slice(0, 200_000); } catch { return ''; }
}

// Text the command printed, when the host reports it in a known field.
function printedText(value) {
  if (typeof value === 'string') return value;
  if (!value || typeof value !== 'object') return '';
  return ['stdout', 'stderr', 'output'].map(key => (typeof value[key] === 'string' ? value[key] : '')).join('\n');
}

// Read the hook input of either host. Returns what to launch, or null.
export function pullRequestEvent(input) {
  if (!input || typeof input !== 'object' || !isSuccessfulToolEvent(input)) return null;
  const toolInput = input.tool_input;
  let command = toolInput?.command;
  if (Array.isArray(command)) {
    if (!command.every(part => typeof part === 'string')) return null;
    command = command.length === 3 && /^-(?:l?c|Command)$/i.test(command[1]) ? command[2] : null;
  }
  if (typeof command !== 'string') return null;
  const powershell = /powershell|pwsh/i.test(String(input.tool_name ?? ''));
  const found = findPullRequestCommand(command, { powershell });
  if (!found) return null;

  const output = responseText(input.tool_response);
  const url = PULL_URL.exec(output)?.[0] ?? null;
  // gh prints the pull request URL when it creates one: printed text without it means nothing was opened.
  if (found.action === 'create' && !url && printedText(input.tool_response).trim()) return null;
  const ref = found.ref ?? url ?? (found.action === 'ready' ? /[\w.-]+\/[\w.-]+#(\d{1,9})\b/.exec(output)?.[1] ?? null : null);
  return { action: found.action, ref, cwd: effectiveCwd(input, found.directory) };
}

function effectiveCwd(input, directory) {
  const workdir = input.tool_input?.workdir ?? input.tool_input?.cwd;
  let cwd = typeof input.cwd === 'string' && input.cwd ? input.cwd : process.cwd();
  if (typeof workdir === 'string' && workdir.trim()) cwd = path.resolve(cwd, nativePath(workdir));
  if (directory) {
    if (directory.startsWith('~')) directory = path.join(os.homedir(), directory.slice(1));
    cwd = path.resolve(cwd, nativePath(directory));
  }
  return cwd;
}

// Git Bash on Windows writes C:\x as /c/x.
function nativePath(value) {
  if (process.platform !== 'win32') return value;
  const drive = /^\/([A-Za-z])(\/.*)?$/.exec(value);
  return drive ? `${drive[1].toUpperCase()}:${drive[2] ?? '/'}` : value;
}

// Nearest ancestor that holds `.git` (a folder, or a file in a linked worktree).
export function findGitRoot(start) {
  let directory = path.resolve(start);
  for (;;) {
    if (existsSync(path.join(directory, '.git'))) return directory;
    const parent = path.dirname(directory);
    if (parent === directory) return null;
    directory = parent;
  }
}

export function hasGateScript(root) {
  try {
    const manifest = JSON.parse(readFileSync(path.join(root, 'package.json'), 'utf8'));
    return typeof manifest?.scripts?.[SCRIPT] === 'string' && manifest.scripts[SCRIPT].trim() !== '';
  } catch { return false; }
}

// Start the gates in a detached copy of this script, which runs
// `npm run gates:pr` with its output in a log file. `ref` is reduced to a
// number or a GitHub pull URL, so the Windows command line needs no quoting.
export function launchGates(root, ref, { home = os.homedir(), now = new Date() } = {}) {
  const safeRef = pullReference(ref);
  const directory = path.join(home, '.agentic', 'pr-gates');
  mkdirSync(directory, { recursive: true });
  const name = path.basename(root).replace(/[^\w.-]/g, '_').slice(0, 80) || 'repo';
  const stamp = now.toISOString().replace(/[-:]/g, '').replace(/\.\d+Z$/, 'Z');
  const log = path.join(directory, `${name}-${stamp}-${process.pid}.log`);
  closeSync(openSync(log, 'a'));
  startDetached([fileURLToPath(import.meta.url), RUN_FLAG, log, ...(safeRef ? [safeRef] : [])], root);
  return { log, ref: safeRef };
}

// Codex runs hook commands on Windows through PowerShell. A child that the
// hook starts there with spawn() inherits the hook's stdout pipe, so the host
// waits for the whole gates run and kills it at the hook timeout. On Windows
// the gates are therefore started by a short-lived PowerShell with
// Start-Process, which creates them through ShellExecute and passes no
// handles. The hook waits for that PowerShell (a detached one dies before it
// starts anything) and falls back to plain spawn() only when PowerShell
// itself cannot be started, so the gates never start twice. Plain spawn()
// is the path on the other platforms.
const START_PROCESS = [
  "$list = $env:PR_GATES_ARGS -split \"`n\" | ForEach-Object { '\"' + $_ + '\"' }",
  "Start-Process -FilePath $env:PR_GATES_NODE -ArgumentList ($list -join ' ') -WorkingDirectory $env:PR_GATES_CWD -WindowStyle Hidden",
].join('; ');

function startDetached(args, cwd) {
  const direct = () => {
    const child = spawn(process.execPath, args, { cwd, detached: true, windowsHide: true, stdio: 'ignore' });
    child.on('error', () => {});
    child.unref();
  };
  if (process.platform !== 'win32') return direct();
  const env = { ...process.env, PR_GATES_NODE: process.execPath, PR_GATES_ARGS: args.join('\n'), PR_GATES_CWD: cwd };
  const result = spawnSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command', START_PROCESS], {
    env, windowsHide: true, stdio: 'ignore', timeout: 15_000,
  });
  if (result.error?.code === 'ENOENT') direct();
}

// The detached side: npm is a .cmd file on Windows and needs a shell there.
function runGates(log, ref) {
  const safeRef = pullReference(ref);
  const args = ['run', SCRIPT, ...(safeRef ? ['--', '--pr', safeRef] : [])];
  const descriptor = openSync(log, 'a');
  const options = { stdio: ['ignore', descriptor, descriptor], windowsHide: true };
  const result = process.platform === 'win32'
    ? spawnSync(`npm ${args.join(' ')}`, { ...options, shell: true })
    : spawnSync('npm', args, options);
  const outcome = result.error ? `could not start npm: ${result.error.message}` : `npm run ${SCRIPT} exited with ${result.status ?? result.signal}`;
  appendFileSync(descriptor, `[pr-gates] ${outcome}\n`);
  closeSync(descriptor);
}

export function run(text, options) {
  let input;
  try { input = JSON.parse(text); } catch { return null; }
  const event = pullRequestEvent(input);
  if (!event) return null;
  const root = findGitRoot(event.cwd);
  if (!root || !hasGateScript(root)) return null;
  const { log, ref } = launchGates(root, event.ref, options);
  const context = `[pr-gates] Launched \`npm run ${SCRIPT}\` in the background${ref ? ` for PR ${ref}` : ''} from ${root}. Log: ${log}. The launch is not a result: wait for the final outcome and react to it.`;
  return { hookSpecificOutput: { hookEventName: 'PostToolUse', additionalContext: context } };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    if (process.argv[2] === RUN_FLAG) runGates(process.argv[3], process.argv[4]);
    else {
      const output = run(readFileSync(0, 'utf8'));
      if (output) process.stdout.write(JSON.stringify(output));
    }
  } catch { /* A hook failure must never break a completed tool call. */ }
  process.exitCode = 0;
}
