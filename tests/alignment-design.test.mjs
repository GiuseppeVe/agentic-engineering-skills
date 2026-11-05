import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import YAML from "yaml";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const skillsRoot = path.join(root, "plugins", "agentic-engineering-skills", "skills");

async function skill(name) {
  return readFile(path.join(skillsRoot, name, "SKILL.md"), "utf8");
}

async function support(name, file) {
  const filePath = path.join(skillsRoot, name, file);
  await access(filePath);
  return readFile(filePath, "utf8");
}

function frontmatter(source) {
  return source.match(/^---\r?\n([\s\S]*?)\r?\n---/u)?.[1] ?? "";
}

test("codebase-design ships deepening and design-it-twice references", async () => {
  const source = await skill("codebase-design");
  assert.match(source, /Adaptation:.*mattpocock\/skills/u);
  assert.match(source, /\[DEEPENING\.md\]\(DEEPENING\.md\)/u);
  assert.match(source, /\[DESIGN-IT-TWICE\.md\]\(DESIGN-IT-TWICE\.md\)/u);
  await support("codebase-design", "DEEPENING.md");
  await support("codebase-design", "DESIGN-IT-TWICE.md");
});

test("domain-modeling follows repository terminology and ADR conventions", async () => {
  const source = await skill("domain-modeling");
  assert.match(source, /CONTEXT-MAP\.md/u);
  assert.match(source, /Preserve the repository's names, layout, and formats/u);
  assert.match(source, /Do not rename `CONTEXT\.md` to `GLOSSARY\.md`/u);
  assert.match(source, /existing project register/u);
  assert.match(source, /when the current task authorizes documentation edits/u);
  assert.match(source, /discussion alone does not authorize a repo edit/u);
  assert.match(source, /GLOSSARY-FORMAT\.md.*fallback/u);
  assert.doesNotMatch(source, /Otherwise use root `GLOSSARY\.md` and the project ADR register/u);
  const glossaryFormat = await support("domain-modeling", "GLOSSARY-FORMAT.md");
  const adrFormat = await support("domain-modeling", "ADR-FORMAT.md");
  assert.match(glossaryFormat, /Context layout/u);
  assert.match(adrFormat, /existing ADR register README or policy/u);
  assert.doesNotMatch(adrFormat, /Use `docs\/architecture\/adr\/README\.md` as the authority/u);
});

test("architecture review discovers local domain docs and supports runtimes without subagents", async () => {
  const source = await skill("improve-codebase-architecture");
  assert.match(source, /disable-model-invocation: true/u);
  assert.match(source, /repository's configured domain-language source/u);
  assert.match(source, /consult Graphify when repository instructions prescribe it or a project Graphify graph is already available/u);
  assert.match(source, /do not require Graphify or initialize a graph in repos that do not use it/u);
  assert.match(source, /If the runtime supports sub-agents.*otherwise explore directly/u);
  assert.match(source, /existing glossary\/context file/u);
  assert.match(source, /Repo edits still require authorization from the current task/u);
  assert.match(source, /discussion alone does not authorize a repo edit/u);
  assert.match(source, /HTML-REPORT\.md/u);
  await support("improve-codebase-architecture", "HTML-REPORT.md");
});

test("wayfinder preserves explicit invocation and repository authority checks", async () => {
  const source = await skill("wayfinder");
  assert.match(source, /disable-model-invocation: true/u);
  assert.match(source, /Follow higher-priority permissions/u);
  assert.match(source, /Use the configured issue tracker/u);
  assert.match(source, /do not invent a tracker layout/u);
  assert.match(source, /at most one non-research ticket per session/u);
});

test("manual-only activation mode remains distinct from ordinary design skills", async () => {
  for (const name of ["improve-codebase-architecture", "wayfinder"]) {
    assert.match(frontmatter(await skill(name)), /disable-model-invocation: true/u, `${name} must require explicit invocation`);
  }
  for (const name of ["codebase-design", "domain-modeling"]) {
    assert.doesNotMatch(frontmatter(await skill(name)), /disable-model-invocation/u, `${name} remains available for model invocation`);
  }
});

test("OpenAI skill metadata preserves the source project activation policy", async () => {
  const expected = {
    "codebase-design": {
      interface: {
        display_name: "Codebase Design",
        short_description: "Vocabulary for deep-module design",
      },
    },
    "domain-modeling": {
      interface: {
        display_name: "Domain Modeling",
        short_description: "Build and sharpen a domain model",
      },
    },
    "improve-codebase-architecture": {
      interface: {
        display_name: "Improve Codebase Architecture",
        short_description: "Find and grill architecture improvements",
      },
      policy: { allow_implicit_invocation: false },
    },
    wayfinder: {
      interface: {
        display_name: "Wayfinder",
        short_description: "Map a large effort as decision tickets",
      },
      policy: { allow_implicit_invocation: false },
    },

  };

  for (const [name, metadata] of Object.entries(expected)) {
    const source = await support(name, "agents/openai.yaml");
    assert.deepEqual(YAML.parse(source), metadata, `${name} metadata must match the source project`);
  }
});
