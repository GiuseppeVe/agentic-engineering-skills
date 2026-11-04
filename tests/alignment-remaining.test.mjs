import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const skillsRoot = path.join(root, "plugins", "agentic-engineering-skills", "skills");

async function skill(name) {
  const directory = path.join(skillsRoot, name);
  return {
    directory,
    source: await readFile(path.join(directory, "SKILL.md"), "utf8"),
  };
}

test("How to Use Codex trigger covers prompt requests without catching coding work", async () => {
  const { source } = await skill("how-to-use-codex");
  const description = source.match(/^description: (.+)$/m)?.[1] ?? "";

  assert.match(description, /write, generate, improve, shorten, or critique a prompt/i);
  assert.match(description, /GPT-5\.6/);
  assert.match(description, /GPT-6 Astra/);
  assert.match(description, /not when they ask to carry out coding work directly/i);
});

test("deslopping cleanup keeps analysis read-only and requires a separate decision for functional cleanup", async () => {
  const { source } = await skill("deslopping-cleanup");

  assert.match(source, /Analysis-only requests stay read-only/i);
  assert.match(source, /functional\s+changes, migrations, new wiring, installs and expanded scope need a separate\s+decision/i);
  assert.match(source, /Skill invocation\s+alone grants no deletion or remote authority/i);
  assert.match(source, /retention registry/i);
});

test("TDD local references resolve and keep behavioral coverage scoped", async () => {
  const { directory, source } = await skill("test-driven-development");
  const references = [...source.matchAll(/\]\(([^)#]+\.md)\)/g)].map(([, file]) => file);

  assert.ok(references.includes("writing-good-tests.md"));
  assert.ok(references.includes("testing-anti-patterns.md"));
  for (const reference of references) {
    await access(path.join(directory, reference));
  }
  await access(path.join(directory, "LICENSE"));
  assert.match(source, /Prototypes, generated code, configuration, and trivial edits need appropriate validation, not automatic test scaffolding/i);
  assert.match(source, /Read \[writing-good-tests\.md\].*\[testing-anti-patterns\.md\]/s);
});
