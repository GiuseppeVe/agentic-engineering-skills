import { describe, expect, it } from "vitest";
import { goldenCases, runGoldenCase } from "../src/evals/golden-cases.js";

describe("golden cases", () => {
  it("runs all named cases through runHarness", () => {
    expect(goldenCases.map((testCase) => testCase.name)).toEqual(["planner-success", "reviewer-success", "invalid-output-escalates"]);
    for (const testCase of goldenCases) {
      const result = runGoldenCase(testCase);
      expect(result.status).toBe(testCase.expectedStatus);
      expect(result.agentId).toBe(testCase.expectedAgentId);
    }
  });
});
