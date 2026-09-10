import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const skillPath = path.join(root, "plugins", "agentic-engineering-skills", "skills", "caveman", "SKILL.md");

test("Caveman exposes current communication rules", async () => {
  const source = await readFile(skillPath, "utf8");

  assert.match(source, /Cuts token usage ~75%/);
  assert.match(source, /Preserve user's dominant language\./);
  assert.match(source, /No self-reference\./);
  assert.match(source, /No causal arrows \(→\) either/);
  assert.match(source, /never invent new abbreviations/);
  assert.match(source, /Clarity register: mix ASD-STE100 Simplified Technical English into caveman/);
  assert.match(source, /One idea per sentence\./);
});
