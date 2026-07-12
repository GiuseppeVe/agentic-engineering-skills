import type { AgentFunction, PlannerOutput } from "../types.js";

export const plannerAgent: AgentFunction = (context): PlannerOutput => ({
  kind: "plan",
  summary: `Plan for: ${context.objective}`,
  actions: ["Define success criteria.", "Execute and verify the smallest safe change."]
});
