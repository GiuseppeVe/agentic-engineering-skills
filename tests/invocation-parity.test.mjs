import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { parse } from "yaml";

const skillRoot = new URL("../plugins/agentic-engineering-skills/skills/", import.meta.url);
const invocation = {
  impeccable: false,
  "deslopping-cleanup": false,
  caveman: false,
  "cleaning-repo-with-knip": false,
  "marketing-screenshots": false,
  handoff: false,
  "setup-harness-evaluation": false,
  "setup-workflow-comparison": false,
  "mdx-to-html": false,
  "to-spec": true,
  graphify: true,
};

for (const [name, implicit] of Object.entries(invocation)) {
  test(`${name} has the requested invocation policy on Claude Code and Codex`, async () => {
    const markdown = await readFile(new URL(`${name}/SKILL.md`, skillRoot), "utf8");
    const frontmatter = parse(markdown.match(/^---\r?\n([\s\S]*?)\r?\n---/)[1]);
    assert.equal(frontmatter["disable-model-invocation"], implicit ? undefined : true, "Claude Code");
    const metadata = parse(await readFile(new URL(`${name}/agents/openai.yaml`, skillRoot), "utf8"));
    assert.equal(metadata.policy?.allow_implicit_invocation, implicit, "Codex");
  });
}
