import assert from "node:assert/strict";
import { access, readFile, readdir } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const skillsRoot = path.join(root, "plugins", "agentic-engineering-skills", "skills");
const orchestratorRoot = path.join(skillsRoot, "sequential-task-orchestrator");
const implementRoot = path.join(skillsRoot, "codex-implement");

async function source(file) {
  return readFile(file, "utf8");
}

async function assertMarkdownLinksResolve(directory) {
  for (const filename of ["SKILL.md", ...await markdownFiles(directory)]) {
    const file = path.join(directory, filename);
    const body = await source(file);
    for (const [, rawTarget] of body.matchAll(/\[[^\]]+\]\(([^)]+)\)/g)) {
      if (/^(?:[a-z]+:|#)/i.test(rawTarget)) continue;
      const target = rawTarget.split("#", 1)[0];
      if (!target) continue;
      await access(path.resolve(path.dirname(file), decodeURIComponent(target)));
    }
  }
}

async function markdownFiles(directory, prefix = "") {
  const entries = await readdir(path.join(directory, prefix), { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const relative = path.join(prefix, entry.name);
    if (entry.isDirectory()) files.push(...await markdownFiles(directory, relative));
    else if (entry.isFile() && entry.name.endsWith(".md")) files.push(relative);
  }
  return files;
}

test("orchestration references resolve within both skill packages", async () => {
  await assertMarkdownLinksResolve(orchestratorRoot);
  await assertMarkdownLinksResolve(implementRoot);
});

async function orchestratorSources() {
  const [skill, protocol] = await Promise.all([
    source(path.join(orchestratorRoot, "SKILL.md")),
    source(path.join(orchestratorRoot, "references", "runtime-protocol.md")),
  ]);
  return { skill, protocol, combined: `${skill}\n${protocol}` };
}

test("orchestrator keeps a single portable runtime reference", async () => {
  const { skill, protocol } = await orchestratorSources();
  assert.match(skill, /references\/runtime-protocol\.md/);
  assert.match(skill, /visible, subordinate subthreads/);
  assert.doesNotMatch(`${skill}\n${protocol}`, /\b(?:claude|codex|cli)\b/i);
});
