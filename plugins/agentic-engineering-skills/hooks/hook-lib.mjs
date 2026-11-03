import { createHash } from 'node:crypto';
import { chmodSync, closeSync, lstatSync, mkdirSync, openSync, unlinkSync } from 'node:fs';
import os from 'node:os';
import path from 'node:path';

export function parseHookInput(text) {
  if (typeof text !== 'string' || text.length > 1_000_000) return null;
  try {
    const value = JSON.parse(text);
    return value && typeof value === 'object' && !Array.isArray(value) ? value : null;
  } catch {
    return null;
  }
}

// Parse only inert, single-command shell text. Hook classification never runs the supplied command.
export function shellWords(command) {
  if (typeof command !== 'string' || command.length > 20_000) return null;
  if (/[$`\\\n\r]/.test(command)) return null;

  const words = [];
  let word = '';
  let quote = null;
  let started = false;
  for (const char of command) {
    if (quote) {
      if (char === quote) quote = null;
      else word += char;
      started = true;
    } else if (char === '"' || char === "'") {
      quote = char;
      started = true;
    } else if (/\s/.test(char)) {
      if (started) words.push(word);
      word = '';
      started = false;
    } else {
      if (/[;&|<>()[\]]/.test(char)) return null;
      word += char;
      started = true;
    }
  }
  if (quote) return null;
  if (started) words.push(word);
  return words;
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
  if (typeof response === 'string' && /(?:exit(?:ed)?(?:\s+with)?\s+code|exit_code)\s*[:=]?\s*[1-9]\d*/i.test(response)) return false;
  return true;
}

export function githubPullUrl(value) {
  const text = typeof value === 'string' ? value : stringifyResponse(value);
  return text.match(/https:\/\/github\.com\/[\w.-]+\/[\w.-]+\/pull\/\d+/i)?.[0];
}

export function stringifyResponse(value) {
  if (typeof value === 'string') return value;
  if (value == null) return '';
  try { return JSON.stringify(value).slice(0, 100_000); } catch { return ''; }
}

export function hookOutput(context) {
  return context ? { hookSpecificOutput: { hookEventName: 'PostToolUse', additionalContext: context } } : null;
}

export function emitHookOutput(context) {
  const output = hookOutput(context);
  if (output) process.stdout.write(JSON.stringify(output));
}

export function safeInline(value, maxLength = 160) {
  if (typeof value !== 'string') return '';
  return value.replace(/[\u0000-\u001f\u007f`*_{}\[\]()<>!|:]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, maxLength);
}
const DEDUP_TTL_MS = 14 * 24 * 60 * 60 * 1000;

// Claim one reminder per session/PR with an atomic exclusive file. Only digests
// appear in paths; marker files contain no session or repository data.
export function claimPrReminder(sessionId, pullUrl, now = Date.now()) {
  if (typeof sessionId !== 'string' || !sessionId.trim() || sessionId.length > 10_000) return true;
  if (typeof pullUrl !== 'string' || !pullUrl) return true;
  try {
    const root = path.join(os.tmpdir(), 'agentic-engineering-skills-pr-reminders-v1');
    mkdirSync(root, { recursive: true, mode: 0o700 });
    ensurePrivateDirectory(root);
    const sessionDirectory = path.join(root, digest(sessionId));
    try { mkdirSync(sessionDirectory, { mode: 0o700 }); }
    catch (error) { if (error?.code !== 'EEXIST') throw error; }
    ensurePrivateDirectory(sessionDirectory);
    const marker = path.join(sessionDirectory, digest(pullUrl));
    if (createMarker(marker)) return true;

    const markerStat = lstatSync(marker);
    if (!markerStat.isFile() || markerStat.isSymbolicLink()) return true;
    if (now - markerStat.mtimeMs < DEDUP_TTL_MS) return false;
    try { unlinkSync(marker); } catch (error) { if (error?.code !== 'ENOENT') return false; }
    return createMarker(marker);
  } catch {
    // Temporary storage failure must not suppress a useful workflow reminder.
    return true;
  }
}

function ensurePrivateDirectory(directory) {
  const details = lstatSync(directory);
  if (!details.isDirectory() || details.isSymbolicLink()) throw new Error('Unsafe hook dedup directory');
  if (process.platform !== 'win32') chmodSync(directory, 0o700);
}

function createMarker(marker) {
  let descriptor;
  try {
    descriptor = openSync(marker, 'wx', 0o600);
    return true;
  } catch (error) {
    if (error?.code === 'EEXIST') return false;
    throw error;
  } finally {
    if (descriptor !== undefined) closeSync(descriptor);
  }
}

function digest(value) {
  return createHash('sha256').update(value, 'utf8').digest('hex');
}
