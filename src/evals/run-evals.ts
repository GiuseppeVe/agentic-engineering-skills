import { goldenCases, runGoldenCase } from "./golden-cases.js";

let failures = 0;
for (const testCase of goldenCases) {
  const result = runGoldenCase(testCase);
  const passed = result.status === testCase.expectedStatus && result.agentId === testCase.expectedAgentId;
  console.log(`${passed ? "PASS" : "FAIL"} ${testCase.name}`);
  if (!passed) failures += 1;
}
if (failures > 0) process.exitCode = 1;
