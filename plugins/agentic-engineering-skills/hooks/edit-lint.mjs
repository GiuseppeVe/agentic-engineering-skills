#!/usr/bin/env node
// PostToolUse hook: after an edit/write/patch tool modifies JS/TS files inside
// a repository that configures `.oxlintrc.json` and installs local `oxlint`,
// run Oxlint in fast syntactic read-only mode on the edited file(s) and return
// only blocking errors as concise additionalContext. Silent on clean files or
// unconfigured repositories; never modifies files; always exits 0.
import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const LINTABLE_EXT = /\.(?:[mc]?[jt]sx?)$/i;
const IGNORED_SEGMENTS = new Set(['node_modules', 'dist', 'dev-dist', 'build', 'coverage', '.git', '.worktrees']);
const MAX_FILES = 10;
const MAX_DIAGNOSTICS = 8;
const LINT_TIMEOUT_MS = 8_000;

export function isSuccessfulToolEvent(input) {
  if (!input || typeof input !== 'object') return false;
  if (input.is_error === true || input.isError === true) return false;
  const response = input.tool_response;
  if (response && typeof response === 'object') {
    if (response.is_error === true || response.isError === true || response.interrupted === true) return false;
    for (const key of ['exitCode', 'exit_code', 'statusCode']) {
      if (response[key] != null && Number(response[key]) !== 0) return false;
    }
    if (response.error) return false;
  }
  return true;
}

// Git Bash on Windows writes C:\x as /c/x.
export function nativePath(value) {
  if (process.platform !== 'win32' || typeof value !== 'string') return value;
  const drive = /^\/([A-Za-z])(\/.*)?$/.exec(value);
  return drive ? `${drive[1].toUpperCase()}:${drive[2] ?? '/'}` : value;
}

export function extractEditedPaths(input) {
  if (!input || typeof input !== 'object') return [];
  const toolInput = input.tool_input;
  const raw = [];

  if (typeof toolInput === 'string') {
    extractPatchPaths(toolInput, raw);
  } else if (toolInput && typeof toolInput === 'object') {
    for (const key of ['file_path', 'path', 'target_file', 'TargetFile']) {
      if (typeof toolInput[key] === 'string' && toolInput[key].trim()) raw.push(toolInput[key].trim());
    }
    if (Array.isArray(toolInput.edits)) {
      for (const edit of toolInput.edits) {
        if (typeof edit?.file_path === 'string' && edit.file_path.trim()) raw.push(edit.file_path.trim());
      }
    }
    for (const key of ['input', 'patch']) {
      if (typeof toolInput[key] === 'string') extractPatchPaths(toolInput[key], raw);
    }
  }

  const base = typeof input.cwd === 'string' && input.cwd ? nativePath(input.cwd) : process.cwd();
  const resolved = [];
  const seen = new Set();
  for (const candidate of raw) {
    const normalized = nativePath(candidate);
    const absolute = path.isAbsolute(normalized) ? path.normalize(normalized) : path.resolve(base, normalized);
    if (!LINTABLE_EXT.test(absolute)) continue;
    if (seen.has(absolute)) continue;
    seen.add(absolute);
    resolved.push(absolute);
    if (resolved.length >= MAX_FILES) break;
  }
  return resolved;
}

function extractPatchPaths(text, out) {
  for (const line of text.split(/\r?\n/)) {
    const match = /^\*\*\*\s+(?:Update|Add)\s+File:\s+(.+?)\s*$/.exec(line);
    if (match?.[1]) out.push(match[1]);
  }
}

export function isIgnoredWithinRepo(gitRoot, filePath) {
  const relativePath = path.relative(gitRoot, filePath);
  if (!relativePath || relativePath.startsWith('..') || path.isAbsolute(relativePath)) return true;
  return relativePath.split(/[\\/]+/).some((segment) => IGNORED_SEGMENTS.has(segment));
}

export function findGitRoot(start) {
  let directory = path.resolve(start);
  for (;;) {
    if (existsSync(path.join(directory, '.git'))) return directory;
    const parent = path.dirname(directory);
    if (parent === directory) return null;
    directory = parent;
  }
}

function findNearestInAncestors(startDir, stopDir, relativeTarget) {
  let directory = path.resolve(startDir);
  const boundary = path.resolve(stopDir);
  for (;;) {
    const candidate = path.join(directory, relativeTarget);
    if (existsSync(candidate)) return { dir: directory, target: candidate };
    if (directory === boundary) return null;
    const parent = path.dirname(directory);
    if (parent === directory) return null;
    directory = parent;
  }
}

export function resolveLintContext(filePath) {
  const dir = path.dirname(filePath);
  const gitRoot = findGitRoot(dir);
  if (!gitRoot) return null;
  if (isIgnoredWithinRepo(gitRoot, filePath)) return null;
  const configMatch = findNearestInAncestors(dir, gitRoot, '.oxlintrc.json');
  if (!configMatch) return null;
  const binMatch = findNearestInAncestors(dir, gitRoot, path.join('node_modules', 'oxlint', 'bin', 'oxlint'));
  if (!binMatch) return null;
  return {
    gitRoot,
    configDir: configMatch.dir,
    configPath: configMatch.target,
    oxlintEntry: binMatch.target,
  };
}

export function runOxlintOnGroup(context, files, { execPath = process.execPath, runner = spawnSync } = {}) {
  const result = runner(
    execPath,
    [context.oxlintEntry, '-c', context.configPath, '--format', 'json', '--quiet', ...files],
    {
      cwd: context.configDir,
      encoding: 'utf8',
      timeout: LINT_TIMEOUT_MS,
      windowsHide: true,
      maxBuffer: 8 * 1024 * 1024,
    },
  );
  if (result.error || !result.stdout) return [];
  let parsed;
  try {
    parsed = JSON.parse(result.stdout);
  } catch {
    return [];
  }
  const diagnostics = Array.isArray(parsed?.diagnostics) ? parsed.diagnostics : [];
  return diagnostics
    .filter((entry) => String(entry?.severity ?? '').toLowerCase() === 'error')
    .map((entry) => {
      const span = entry?.labels?.[0]?.span;
      const line = span?.line ?? '?';
      const column = span?.column ?? '?';
      const filename = typeof entry?.filename === 'string' ? entry.filename : path.basename(files[0]);
      const code = entry?.code || 'oxlint';
      const message = String(entry?.message ?? '').replace(/\s+/g, ' ').trim();
      return `${filename}:${line}:${column} [${code}] ${message}`;
    });
}

export function run(text, options = {}) {
  let input;
  try {
    input = JSON.parse(text);
  } catch {
    return null;
  }
  if (!isSuccessfulToolEvent(input)) return null;

  const files = extractEditedPaths(input).filter((filePath) => {
    try {
      return statSync(filePath).isFile();
    } catch {
      return false;
    }
  });
  if (!files.length) return null;

  const groups = new Map();
  for (const filePath of files) {
    const context = resolveLintContext(filePath);
    if (!context) continue;
    const key = `${context.configPath}\0${context.oxlintEntry}`;
    if (!groups.has(key)) groups.set(key, { context, files: [] });
    groups.get(key).files.push(filePath);
  }
  if (!groups.size) return null;

  const findings = [];
  for (const { context, files: groupFiles } of groups.values()) {
    findings.push(...runOxlintOnGroup(context, groupFiles, options));
  }
  if (!findings.length) return null;

  const shown = findings.slice(0, MAX_DIAGNOSTICS);
  const remainder = findings.length - shown.length;
  const header = `[edit-lint] ${findings.length} static error${findings.length === 1 ? '' : 's'} in edited file${files.length === 1 ? '' : 's'} (fix before committing):`;
  const lines = [header, ...shown.map((line) => `- ${line}`)];
  if (remainder > 0) lines.push(`- ...and ${remainder} more`);
  return {
    hookSpecificOutput: {
      hookEventName: 'PostToolUse',
      additionalContext: lines.join('\n'),
    },
  };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const output = run(readFileSync(0, 'utf8'));
    if (output) process.stdout.write(JSON.stringify(output));
  } catch {
    /* A hook failure must never break a completed tool call. */
  }
  process.exitCode = 0;
}
