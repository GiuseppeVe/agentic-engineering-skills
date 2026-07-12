const summaryPatterns = {
  tests: /^(?:#|\u2139)?\s*tests\s+(\d+)\s*$/i,
  pass: /^(?:#|\u2139)?\s*pass\s+(\d+)\s*$/i,
  fail: /^(?:#|\u2139)?\s*fail\s+(\d+)\s*$/i,
};

export function parseTestSummary(output) {
  const summary = {};
  for (const rawLine of output.split(/\r?\n/)) {
    const line = rawLine.replace(/^\s+/, "");
    for (const [field, pattern] of Object.entries(summaryPatterns)) {
      const match = line.match(pattern);
      if (match) summary[field] = Number(match[1]);
    }
  }
  return Number.isInteger(summary.tests) && Number.isInteger(summary.pass) && Number.isInteger(summary.fail)
    ? summary
    : null;
}

export function testRunFailure({ exitCode, signal, summary }) {
  if (signal) return `Node test runner terminated by signal ${signal}`;
  if (exitCode !== 0) return `Node test runner exited with code ${exitCode}`;
  if (!summary) return "Node test runner emitted no complete final summary";
  if (summary.tests === 0) return "Node test runner discovered zero tests";
  if (summary.fail !== 0) return `Node test runner reported ${summary.fail} failed tests`;
  return null;
}
