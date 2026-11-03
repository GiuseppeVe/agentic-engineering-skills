import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { parse } from "yaml";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const skillRoot = path.join(root, "plugins", "agentic-engineering-skills", "skills");

async function skill(name) {
  return readFile(path.join(skillRoot, name, "SKILL.md"), "utf8");
}

function frontmatter(source) {
  return source.match(/^---\r?\n([\s\S]*?)\r?\n---/m)?.[1] ?? "";
}

test("learn-codebase and UI UX Pro Max require explicit user invocation", async () => {
  const learn = await skill("learn-codebase");
  const ui = await skill("ui-ux-pro-max");

  assert.match(frontmatter(learn), /description: Use only when the user explicitly asks/);
  assert.match(frontmatter(learn), /disable-model-invocation: true/);
  assert.match(learn, /every source file in full/);
  assert.match(frontmatter(ui), /description: Use only when the user explicitly invokes `ui-ux-pro-max`/);
  assert.match(frontmatter(ui), /disable-model-invocation: true/);
  assert.match(ui, /Use only when the user explicitly invokes `ui-ux-pro-max`/);
});

test("Codex invocation policy matches Alfe for all four aligned skills", async () => {
  async function codexPolicy(name) {
    const yamlPath = path.join(skillRoot, name, "agents", "openai.yaml");
    return parse(await readFile(yamlPath, "utf8"))?.policy ?? {};
  }

  assert.equal((await codexPolicy("learn-codebase")).allow_implicit_invocation, false);
  assert.equal((await codexPolicy("ui-ux-pro-max")).allow_implicit_invocation, false);
  assert.equal((await codexPolicy("to-spec")).allow_implicit_invocation, false);
  assert.equal((await codexPolicy("grilling")).allow_implicit_invocation ?? true, true);
});

test("grilling follows Alfe's frontier rounds and waits for confirmation", async () => {
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

test("UI UX instructions and references use bundled assets without host-specific paths", async () => {
  const ui = await skill("ui-ux-pro-max");
  const search = await readFile(path.join(skillRoot, "ui-ux-pro-max", "references", "search.md"), "utf8");
  const uiRoot = path.join(skillRoot, "ui-ux-pro-max");

  await access(path.join(uiRoot, "scripts", "search.py"));
  await access(path.join(uiRoot, "data", "ux-guidelines.csv"));
  await access(path.join(uiRoot, "references", "guidelines.md"));
  assert.match(ui, /<skill-directory>\/scripts\/search\.py/);
  assert.match(ui, /Project instructions, existing design systems, and actual framework take precedence/);
  assert.doesNotMatch(`${ui}\n${search}`, /\.agents\/skills|\.claude\/skills|~\/\.claude/);
  assert.match(search, /installation paths vary by host/);
});
