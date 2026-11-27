import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const skillRoot = path.join(root, "plugins", "agentic-engineering-skills", "skills");

async function skill(name) {
  return readFile(path.join(skillRoot, name, "SKILL.md"), "utf8");
}

test("grilling follows the source project’s frontier rounds and waits for confirmation", async () => {
  const grilling = await skill("grilling");

  assert.match(grilling, /frontier/);
  assert.match(grilling, /Ask the whole frontier in one round/);
  assert.match(grilling, /recompute its frontier/);
  assert.match(grilling, /Do not act on the result until the user confirms/);
});

test("to-spec keeps tracker publication behind explicit authorization", async () => {
  const toSpec = await skill("to-spec");

  assert.match(toSpec, /continue the local spec/);
  assert.match(toSpec, /Publish only when existing session authorization and applicable permissions allow tracker writes/);
  assert.match(toSpec, /The skill does not grant tracker-write or setup-mutation permission/);
  assert.match(toSpec, /prepared issue content/);
});
