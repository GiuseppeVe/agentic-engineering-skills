import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const skillPath = path.join(root, "plugins", "agentic-engineering-skills", "skills", "how-to-use-codex", "SKILL.md");

test("How to Use Codex reflects current official GPT-6 Astra guidance", async () => {
  const source = await readFile(skillPath, "utf8");

  assert.match(source, /GPT-6 Astra/);
  assert.match(source, /GPT-5\.6 Model Choice/);
  assert.match(source, /gpt-5\.6/);
  assert.match(source, /official OpenAI documentation/);
  assert.match(source, /reasoning effort/);
  assert.match(source, /subagent delegation/i);
  assert.match(source, /testing and verification/i);
  assert.match(source, /Do not invent/);
});
