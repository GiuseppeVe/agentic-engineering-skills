import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const skillPath = path.join(root, "plugins", "agentic-engineering-skills", "skills", "how-to-use-codex", "SKILL.md");

test("How to Use Codex preserves requested models and verifies current routing guidance", async () => {
  const source = await readFile(skillPath, "utf8");

  assert.match(source, /GPT-6 Astra/);
  assert.match(source, /gpt-6\.1-sol/);
  assert.match(source, /gpt-6-luna/);
  assert.match(source, /not benchmark claims/);
  assert.doesNotMatch(source, /`gpt-5\.6` aliases Sol/);
  assert.match(source, /higher-priority instructions/);
  assert.match(source, /official OpenAI documentation/);
  assert.match(source, /reasoning effort/);
  assert.match(source, /subagent delegation/i);
  assert.match(source, /testing and verification/i);
  assert.match(source, /Do not invent/);
});
