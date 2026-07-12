import type { AgentFunction, ReviewerOutput } from "../types.js";

export const reviewerAgent: AgentFunction = (context): ReviewerOutput => ({
  kind: "review",
  verdict: "pass",
  summary: `Review completed for: ${context.objective}`,
  evidence: context.evidence
});
