import assert from "node:assert/strict";
import { access, readFile, readdir } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const skillsRoot = path.join(root, "plugins", "agentic-engineering-skills", "skills");
const planImplementRoot = path.join(skillsRoot, "plan-implement");
const developmentProcessRoot = path.join(skillsRoot, "development-process");
const coordinatorRoot = path.join(skillsRoot, "coordinating-implementation-plans");

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

test("orchestration and process references resolve within their skill packages", async () => {
  await assertMarkdownLinksResolve(planImplementRoot);
  await assertMarkdownLinksResolve(developmentProcessRoot);
  await assertMarkdownLinksResolve(coordinatorRoot);
});

async function planImplementSources() {
  const [skill, protocol, slice] = await Promise.all([
    source(path.join(planImplementRoot, "SKILL.md")),
    source(path.join(planImplementRoot, "references", "runtime-protocol.md")),
    source(path.join(planImplementRoot, "references", "slice-contract.md")),
  ]);
  return { skill, protocol, slice, combined: `${skill}\n${protocol}\n${slice}` };
}

test("plan-implement keeps portable host-neutral protocol and slice contract references", async () => {
  const { skill, protocol, slice } = await planImplementSources();
  assert.match(skill, /references\/runtime-protocol\.md/);
  assert.match(skill, /references\/slice-contract\.md/);
  assert.match(skill, /slice-implementer/);
  assert.doesNotMatch(`${skill}\n${protocol}\n${slice}`, /\b(?:claude|codex|cli)\b/i);
});
