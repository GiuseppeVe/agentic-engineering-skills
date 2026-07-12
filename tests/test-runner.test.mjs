import test from "node:test";
import assert from "node:assert/strict";
import { parseTestSummary, testRunFailure } from "../scripts/lib/runner-summary.mjs";

test("parses Node TAP and spec final summaries", () => {
  assert.deepEqual(parseTestSummary("# tests 12\n# pass 12\n# fail 0\n"), { tests: 12, pass: 12, fail: 0 });
  assert.deepEqual(parseTestSummary("\u2139 tests 3\n\u2139 pass 3\n\u2139 fail 0\n"), { tests: 3, pass: 3, fail: 0 });
});

test("rejects missing, incomplete, and zero-test summaries", () => {
  assert.equal(parseTestSummary(""), null);
  assert.equal(parseTestSummary("# tests 1\n# pass 1\n"), null);
  assert.match(testRunFailure({ exitCode: 0, signal: null, summary: null }), /no complete final summary/);
  assert.match(testRunFailure({ exitCode: 0, signal: null, summary: { tests: 0, pass: 0, fail: 0 } }), /zero tests/);
});

test("rejects child failure, signal, and reported failures", () => {
  assert.match(testRunFailure({ exitCode: 2, signal: null, summary: null }), /code 2/);
  assert.match(testRunFailure({ exitCode: null, signal: "SIGTERM", summary: null }), /SIGTERM/);
  assert.match(testRunFailure({ exitCode: 0, signal: null, summary: { tests: 2, pass: 1, fail: 1 } }), /1 failed/);
  assert.equal(testRunFailure({ exitCode: 0, signal: null, summary: { tests: 2, pass: 2, fail: 0 } }), null);
});
