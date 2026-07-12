import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const workflowPath = new URL("../.github/workflows/ci.yml", import.meta.url);

test("CI uses constrained GitHub Actions triggers and permissions", async () => {
  const workflow = await readFile(workflowPath, "utf8");

  assert.match(workflow, /^on:\n  push:\n  pull_request:\n  workflow_dispatch:\s*$/m);
  assert.doesNotMatch(workflow, /^\s*schedule:/m);
  assert.match(workflow, /^permissions:\n  contents: read$/m);
  assert.match(workflow, /^\s*runs-on: ubuntu-latest$/m);
  assert.match(workflow, /^\s*timeout-minutes: 15$/m);
  assert.match(workflow, /uses: actions\/setup-node@v4[\s\S]*node-version: 22/);
});

test("CI runs release gates in required order", async () => {
  const workflow = await readFile(workflowPath, "utf8");
  const commands = [
    "npm ci",
    "npm test",
    "npm run verify:pack",
    "npm run verify:upstream",
    "npm run audit:public",
    'python "${CODEX_HOME:-$HOME/.codex}/skills/.system/plugin-creator/scripts/validate_plugin.py" plugins/agentic-engineering-skills',
    "claude plugin validate .",
  ];

  let previous = -1;
  for (const command of commands) {
    const current = workflow.indexOf(command);
    assert.ok(current > previous, `missing or out-of-order CI command: ${command}`);
    previous = current;
  }
});
