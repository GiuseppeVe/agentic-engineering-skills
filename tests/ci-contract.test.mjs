import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import YAML from "yaml";

const workflowPath = new URL("../.github/workflows/ci.yml", import.meta.url);

async function loadWorkflow() {
  return YAML.parse(await readFile(workflowPath, "utf8"));
}

test("CI has exact triggers, permissions, runner, and timeout", async () => {
  const workflow = await loadWorkflow();
  assert.deepEqual(Object.keys(workflow.on).sort(), ["pull_request", "push", "workflow_dispatch"]);
  assert.deepEqual(workflow.permissions, { contents: "read" });
  assert.deepEqual(Object.keys(workflow.jobs), ["verify"]);
  assert.equal(workflow.jobs.verify["runs-on"], "ubuntu-latest");
  assert.equal(workflow.jobs.verify["timeout-minutes"], 15);
});

test("CI setup and executable gates are unique and ordered", async () => {
  const workflow = await loadWorkflow();
  const steps = workflow.jobs.verify.steps;
  assert.ok(steps.some(step => step.uses === "actions/setup-node@v4" && step.with?.["node-version"] === 22));
  assert.ok(steps.some(step => step.uses === "actions/setup-python@v5" && step.with?.["python-version"] === "3.12"));

  const runs = steps.filter(step => "run" in step).map(step => step.run.trim());
  assert.equal(new Set(runs).size, runs.length, "every executable run step must be unique");
  assert.ok(runs.includes("python -m pip install PyYAML==6.0.2"));
  assert.ok(runs.includes("npm install --global @anthropic-ai/claude-code@2.1.201"));

  const gates = [
    "npm ci",
    "npm test",
    "npm run verify:pack",
    "npm run verify:upstream",
    "npm run audit:public",
    "python scripts/validate_plugin.py plugins/agentic-engineering-skills",
    "claude plugin validate .",
  ];
  assert.deepEqual(runs.filter(command => gates.includes(command)), gates);
  for (const gate of gates) assert.equal(runs.filter(command => command === gate).length, 1, `${gate} must run exactly once`);
});
