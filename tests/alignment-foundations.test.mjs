import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const skill = (name, file) => resolve(root, "plugins/agentic-engineering-skills/skills", name, file);

async function assertExists(path) {
  await access(path);
}

test("caveman references and compression runtime resolve inside the plugin", async () => {
  const skillPath = skill("caveman", "SKILL.md");
  const body = await readFile(skillPath, "utf8");
  const linkedPaths = [...body.matchAll(/\]\((references\/[^)]+)\)/g)].map((match) => match[1]);

  assert.deepEqual(linkedPaths.sort(), [
    "references/commit.md",
    "references/compress.md",
    "references/utilities.md",
  ]);
  for (const path of linkedPaths) await assertExists(skill("caveman", path));

  for (const file of [
    "scripts/compress/__init__.py",
    "scripts/compress/__main__.py",
    "scripts/compress/cli.py",
    "scripts/compress/compress.py",
    "scripts/compress/detect.py",
    "scripts/compress/validate.py",
  ]) {
    await assertExists(skill("caveman", file));
  }
});

test("brainstorming visual companion guide and runtime resolve inside the plugin", async () => {
  const skillPath = skill("brainstorming", "SKILL.md");
  const body = await readFile(skillPath, "utf8");

  assert.match(body, /`visual-companion\.md`/);
  for (const file of [
    "visual-companion.md",
    "agents/openai.yaml",
    "scripts/frame-template.html",
    "scripts/helper.js",
    "scripts/server.cjs",
    "scripts/start-server.sh",
    "scripts/stop-server.sh",
  ]) {
    await assertExists(skill("brainstorming", file));
  }
});
