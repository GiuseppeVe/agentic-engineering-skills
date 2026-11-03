#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import { emitHookOutput, isSuccessfulToolEvent, parseHookInput, safeInline, shellWords } from './hook-lib.mjs';

const REPOSITORY = /^(?:github\.com\/)?([\w.-]+\/[\w.-]+)$/i;
const PR_URL = /^https:\/\/github\.com\/([\w.-]+)\/([\w.-]+)\/pull\/(\d+)$/i;
const MERGE_FLAGS = new Set(['--merge', '--squash', '--rebase', '--delete-branch', '--auto', '--admin', '-m', '-s', '-r', '-d']);

export function parseMergeCommand(command) {
  const words = shellWords(command);
  if (!words || words.shift()?.toLowerCase() !== 'gh') return null;
  let repository;
  const args = [];
  for (let i = 0; i < words.length; i++) {
    const token = words[i];
    let selected;
    if (token === '--repo' || token === '-R') selected = words[++i];
    else if (token.startsWith('--repo=')) selected = token.slice(7);
    else if (token.startsWith('-R=')) selected = token.slice(3);
    else if (token.startsWith('-R') && token.length > 2) selected = token.slice(2);
    else { args.push(token); continue; }
    const match = selected?.match(REPOSITORY);
    if (repository || !match) return null;
    repository = match[1];
  }
  if (args.shift()?.toLowerCase() !== 'pr' || args.shift()?.toLowerCase() !== 'merge') return null;
  let id;
  for (const token of args) {
    if (MERGE_FLAGS.has(token)) continue;
    if (!id && (/^\d+$/.test(token) || PR_URL.test(token))) {
      id = token;
      if (PR_URL.test(token)) {
        const [, owner, name] = token.match(PR_URL);
        const urlRepository = `${owner}/${name}`;
        if (repository && repository.toLowerCase() !== urlRepository.toLowerCase()) return null;
        repository = urlRepository;
      }
      continue;
    }
    return null;
  }
  return { id, repository };
}

export function postMergeContext(input, { lookup = lookupPullRequest, currentRepository = getCurrentRepository } = {}) {
  if (input?.tool_name !== 'Bash' || !isSuccessfulToolEvent(input)) return null;
  const command = parseMergeCommand(input?.tool_input?.command);
  // The merge may have switched branches before this hook runs.
  if (!command?.id) return null;

  if (command.repository) {
    const current = currentRepository();
    if (!current || current.toLowerCase() !== command.repository.toLowerCase()) return null;
  }
  const pr = lookup(command.id, command.repository);
  const urlMatch = typeof pr?.url === 'string' ? pr.url.match(PR_URL) : null;
  if (!urlMatch || pr.state !== 'MERGED' || !pr.mergedAt || !/^[\da-f]{7,64}$/i.test(pr.mergeCommit?.oid ?? '') || !pr.baseRefName || !pr.headRefName) return null;
  const selectedNumber = command.id.match(PR_URL)?.[3] ?? command.id;
  if (selectedNumber.replace(/^0+/, '') !== urlMatch[3].replace(/^0+/, '')) return null;
  if (command.repository && `${urlMatch[1]}/${urlMatch[2]}`.toLowerCase() !== command.repository.toLowerCase()) return null;
  return `PR merged: ${pr.url}; merge commit ${pr.mergeCommit.oid}; base ${safeInline(pr.baseRefName, 100)}; head ${safeInline(pr.headRefName, 100)}. Verify the merge commit is on its base and run required post-merge checks; apply the documented Graphify refresh only where applicable. Check the exact branch/worktree status and ownership before cleanup. Preserve dirty, shared, active, pinned, or uncertain worktrees; never force, reset, or clean. Respect the applicable approval gates. Report verification, cleanup or preservation, and reasons.`;
}

function lookupPullRequest(id, repository) {
  const args = ['pr', 'view'];
  if (id) args.push(id);
  if (repository) args.push('--repo', repository);
  args.push('--json', 'state,url,mergedAt,mergeCommit,baseRefName,headRefName');
  const result = spawnSync('gh', args, { encoding: 'utf8', timeout: 10_000, windowsHide: true });
  if (result.error || result.status !== 0) return null;
  try { return JSON.parse(result.stdout); } catch { return null; }
}

function getCurrentRepository() {
  const result = spawnSync('gh', ['repo', 'view', '--json', 'nameWithOwner', '--jq', '.nameWithOwner'], { encoding: 'utf8', timeout: 10_000, windowsHide: true });
  return result.error || result.status !== 0 ? null : result.stdout.trim();
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const input = parseHookInput(readFileSync(0, 'utf8'));
    emitHookOutput(postMergeContext(input));
  } catch { /* Hook failure must not break completed tool call. */ }
}
