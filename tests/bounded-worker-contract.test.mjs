import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const pluginRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "plugins", "agentic-engineering-skills");
const workers = [
  ["Claude", "claude-skills/claude-implement/agents/worker.md"],
  ["Codex", "skills/codex-implement/agents/terra-worker.md"],
];

for (const [host, relativePath] of workers) {
  test(`${host} worker permits only approved, in-scope shared contract changes`, async () => {
    const source = await readFile(path.join(pluginRoot, relativePath), "utf8");
    assert.doesNotMatch(source, /never (?:change|modify) (?:a )?shared (?:interface|contract)\b/i,
      "an unconditional shared-interface ban blocks approved packets");
    const permission = source.split(/\.\s+/).find((sentence) => /shared interface or contract/i.test(sentence));
    assert.ok(permission, "the worker must state when shared contracts may change");
    assert.match(permission, /may be changed only when/i);
    assert.match(permission, /explicitly specified in the approved (?:packet or plan|plan or packet)/i);
    assert.match(permission, /every affected file is in `Allowed files`/i);
    assert.match(source, /modify only `Allowed files`/i);
  });

  test(`${host} worker blocks missing authority and preserves architecture and plan decisions`, async () => {
    const source = await readFile(path.join(pluginRoot, relativePath), "utf8");
    const blocked = source.split(/\.\s+/).find((sentence) => /return `BLOCKED`/i.test(sentence));
    assert.ok(blocked, "the worker must explain when to return BLOCKED");
    assert.match(blocked, /excluded file/i);
    assert.match(blocked, /scope expansion/i);
    assert.match(blocked, /unspecified shared[- ]interface (?:or contract )?change/i);
    assert.match(blocked, /(?:new or unresolved|unresolved or new) (?:design, )?architecture, or plan decision/i);
    assert.match(source, /never change architecture or plan decisions/i);
  });
}

test("Codex dispatch applies the same approved shared-contract boundary as its workers", async () => {
  const source = await readFile(path.join(pluginRoot, "skills/codex-implement/SKILL.md"), "utf8");
  const dispatch = source.match(/^## Packet dispatch\s+([\s\S]*?)(?=^## )/m)?.[1];
  assert.ok(dispatch, "packet dispatch instructions must exist");
  assert.doesNotMatch(dispatch, /a required shared interface, contract, or non-allowed file means `BLOCKED`/i,
    "dispatch cannot block every shared-contract change");
  const permission = dispatch.split(/\.\s+/).find((sentence) => /shared interface or contract/i.test(sentence));
  assert.ok(permission, "dispatch must state when shared contracts may change");
  assert.match(permission, /may be changed only when/i);
  assert.match(permission, /explicitly specified in the approved (?:packet or plan|plan or packet)/i);
  assert.match(permission, /every affected file is in `Allowed files`/i);
  const blocked = dispatch.split(/\.\s+/).find((sentence) => /return `BLOCKED`/i.test(sentence));
  assert.ok(blocked, "dispatch must preserve the blocked path");
  assert.match(blocked, /excluded file/i);
  assert.match(blocked, /scope expansion/i);
  assert.match(blocked, /unspecified shared[- ]interface (?:or contract )?change/i);
  assert.match(blocked, /(?:new or unresolved|unresolved or new) (?:design, )?architecture, or plan decision/i);
});

test("Codex red flags block unapproved or out-of-scope shared changes, not approved changes", async () => {
  const source = await readFile(path.join(pluginRoot, "skills/codex-implement/SKILL.md"), "utf8");
  const redFlags = source.match(/^## Red flags\s+([\s\S]*?)(?=^## )/m)?.[1];
  assert.ok(redFlags, "red flag instructions must exist");
  const sharedRow = redFlags.split(/\r?\n/).find((line) => /shared-interface/i.test(line));
  assert.ok(sharedRow, "red flags must identify shared-interface escapes");
  assert.match(sharedRow, /unspecified in the approved (?:packet or plan|plan or packet)/i);
  assert.match(sharedRow, /files outside `Allowed files`/i);
  assert.match(sharedRow, /block packet/i);
});
