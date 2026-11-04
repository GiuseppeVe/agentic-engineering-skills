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
  assert.match(source, /ACTIVE EVERY RESPONSE/);
  assert.match(source, /\/caveman lite\|full\|ultra/);
  assert.match(source, /references\/commit\.md/);
  assert.match(source, /references\/compress\.md/);
  assert.match(source, /references\/utilities\.md/);
  assert.doesNotMatch(source, /wenyan|文言文/i);
});
