import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { normalize, parseFpText, filterClaims, findUnhandled } from "../plugins/agentic-engineering-skills/skills/cleaning-repo-with-knip/parse-knip.mjs";

const report = { issues: [
  { file: "frontend/package.json", workspace: "frontend", dependencies: [{ name: "tailwindcss" }] },
  { file: "backend/package.json", workspace: "backend", dependencies: [{ name: "tailwindcss" }] },
] };

test("workspace-specific ledger suppresses only that workspace", () => {
  const rules = parseFpText("## dependencies :: frontend :: tailwindcss\n- knip-rule: ignoreDependencies\n");
  const result = filterClaims(normalize(report), rules);
  assert.deepEqual(result.suppressed.map(c => c.id), ["unused-dependency :: frontend :: tailwindcss"]);
  assert.deepEqual(result.claims.map(c => c.id), ["unused-dependency :: backend :: tailwindcss"]);
  assert.deepEqual(result.ambiguousLegacy, []);
});

test("ambiguous legacy entry leaves all workspaces visible", () => {
  const rules = parseFpText("## unused-dependency :: tailwindcss\n- knip-rule: ignoreDependencies\n");
  const result = filterClaims(normalize(report), rules);
  assert.equal(result.suppressed.length, 0);
  assert.deepEqual(result.claims.map(c => c.workspace), ["frontend", "backend"]);
  assert.deepEqual(result.ambiguousLegacy, ["unused-dependency :: tailwindcss"]);
});

test("legacy entry never suppresses even a single scoped finding", () => {
  const rules = parseFpText("## dependencies :: tailwindcss\n- knip-rule: ignoreDependencies\n");
  const result = filterClaims(normalize({ issues: [report.issues[1]] }), rules);
  assert.deepEqual(result.claims.map(c => c.workspace), ["backend"]);
  assert.equal(result.suppressed.length, 0);
  assert.deepEqual(result.ambiguousLegacy, ["unused-dependency :: tailwindcss"]);
});

test("legacy entry cannot suppress an unscoped finding whose file belongs to a workspace", () => {
  const rules = parseFpText("## dependencies :: tailwindcss\n- knip-rule: ignoreDependencies\n");
  const result = filterClaims(normalize({ issues: [{ file: "backend/package.json", dependencies: [{ name: "tailwindcss" }] }] }), rules);
  assert.equal(result.claims.length, 1);
  assert.equal(result.suppressed.length, 0);
  assert.deepEqual(result.ambiguousLegacy, ["unused-dependency :: tailwindcss"]);
});

test("legacy entry remains ambiguous if unscoped and scoped findings coexist", () => {
  const rules = parseFpText("## dependencies :: tailwindcss\n- knip-rule: ignoreDependencies\n");
  const result = filterClaims(normalize({ issues: [report.issues[1], { dependencies: [{ name: "tailwindcss" }] }] }), rules);
  assert.equal(result.claims.length, 2);
  assert.equal(result.suppressed.length, 0);
  assert.deepEqual(result.ambiguousLegacy, ["unused-dependency :: tailwindcss"]);
});

test("Knip 6 duplicate-export groups normalize to a comma-separated symbol identity", () => {
  const fixture = { files: [], issues: [{
    file: "frontend/src/CoachShell.tsx",
    duplicates: [[{ name: "CoachShell" }, { name: "default" }]],
  }] };
  const result = filterClaims(normalize(fixture), new Map());
  assert.deepEqual(result.claims.map(c => c.id), ["duplicate-export :: frontend/src/CoachShell.tsx#CoachShell,default"]);
});

test("Knip 5 enum and class member maps normalize with parent symbols", () => {
  const fixture = { files: [], issues: [{
    file: "src/status.ts",
    enumMembers: { Status: [{ name: "legacy" }] },
    classMembers: { Base: [{ name: "oldMethod" }] },
  }] };
  const result = filterClaims(normalize(fixture), new Map(), findUnhandled(fixture));
  assert.deepEqual(result.claims.map(c => c.id), [
    "unused-enumMember :: src/status.ts#Status.legacy",
    "unused-classMember :: src/status.ts#Base.oldMethod",
  ]);
  assert.deepEqual(result.unhandled, []);
});

test("empty Knip 5 member maps do not become unsupported findings", () => {
  const fixture = { files: [], issues: [{
    file: "src/status.ts",
    enumMembers: {},
    classMembers: {},
  }] };
  const result = filterClaims(normalize(fixture), new Map(), findUnhandled(fixture));
  assert.equal(result.claims.length, 0);
  assert.deepEqual(result.unhandled, []);
});

test("unscoped Knip 5 finding cannot be suppressed from file path alone", () => {
  const rules = parseFpText("## dependencies :: backend :: tailwindcss\n- knip-rule: ignoreDependencies\n");
  const fixture = { files: [], issues: [{
    file: "backend/src/server.ts",
    dependencies: [{ name: "tailwindcss" }],
  }] };
  const result = filterClaims(normalize(fixture), rules);
  assert.equal(result.claims.length, 1);
  assert.equal(result.suppressed.length, 0);
});

test("unsupported Knip categories and cycles remain visible with raw data", () => {
  const fixture = { files: [], issues: [{ file: "src/a.ts", cycles: [["src/a.ts", "src/b.ts"]], dependencies: [] }], extraCycles: [["x", "y"]] };
  const result = filterClaims(normalize(fixture), new Map(), findUnhandled(fixture));
  assert.equal(result.claims.length, 0);
  assert.equal(result.counts.unhandled, 2);
  assert.deepEqual(result.unhandled, [
    { source: "report", category: "extraCycles", value: [["x", "y"]] },
    { source: "issue", file: "src/a.ts", workspace: null, category: "cycles", value: [["src/a.ts", "src/b.ts"]] },
  ]);
});

test("command line reports unknown categories rather than a false clean result", () => {
  const script = fileURLToPath(new URL("../plugins/agentic-engineering-skills/skills/cleaning-repo-with-knip/parse-knip.mjs", import.meta.url));
  const fixture = { files: [], issues: [{ file: "src/a.ts", cycles: [["src/a.ts", "src/b.ts"]] }] };
  const result = spawnSync(process.execPath, [script], { input: JSON.stringify(fixture), encoding: "utf8" });
  assert.equal(result.status, 0);
  const parsed = JSON.parse(result.stdout);
  assert.equal(parsed.counts.unhandled, 1);
  assert.equal(parsed.unhandled[0].category, "cycles");
  assert.deepEqual(parsed.unhandled[0].value, [["src/a.ts", "src/b.ts"]]);
});

test("the command line rejects a JSON object that is not a Knip report", () => {
  const script = fileURLToPath(new URL("../plugins/agentic-engineering-skills/skills/cleaning-repo-with-knip/parse-knip.mjs", import.meta.url));
  const result = spawnSync(process.execPath, [script], { input: "{}", encoding: "utf8" });
  assert.equal(result.status, 2);
  assert.match(result.stderr, /invalid knip JSON report shape/);
});
