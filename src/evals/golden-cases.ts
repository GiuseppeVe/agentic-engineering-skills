import { createMockAgent } from "../agents/mock-agent.js";
import { runHarness } from "../harness/runner.js";
import type { HarnessResult, TaskInput } from "../types.js";

interface GoldenCase {
  name: "planner-success" | "reviewer-success" | "invalid-output-escalates";
  task: TaskInput;
  expectedStatus: HarnessResult["status"];
  expectedAgentId: HarnessResult["agentId"];
}

export const goldenCases: GoldenCase[] = [
  { name: "planner-success", task: { text: "Create a safe release plan" }, expectedStatus: "completed", expectedAgentId: "planner-agent" },
  { name: "reviewer-success", task: { text: "Review this implementation", evidence: ["unit-tests"] }, expectedStatus: "completed", expectedAgentId: "reviewer-agent" },
  { name: "invalid-output-escalates", task: { text: "Create a plan with injected faults" }, expectedStatus: "escalated", expectedAgentId: "planner-agent" }
];

export function runGoldenCase(testCase: GoldenCase): HarnessResult {
  if (testCase.name === "invalid-output-escalates") {
    return runHarness(testCase.task, { agents: { "planner-agent": createMockAgent([{ kind: "plan" }, { kind: "unknown" }]) } });
  }
  return runHarness(testCase.task);
}
