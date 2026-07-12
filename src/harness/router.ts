import type { RoutingDecision, TaskInput } from "../types.js";

const planKeywords = ["plan", "create", "design", "draft"];
const reviewKeywords = ["review", "audit", "inspect", "critique"];

export function routeTask(task: TaskInput): RoutingDecision {
  const normalized = task.text.toLowerCase();
  if (planKeywords.some((keyword) => normalized.includes(keyword))) {
    return { kind: "plan", agentId: "planner-agent", reason: "Matched documented planning keyword." };
  }
  if (reviewKeywords.some((keyword) => normalized.includes(keyword))) {
    return { kind: "review", agentId: "reviewer-agent", reason: "Matched documented review keyword." };
  }
  return { kind: "unsupported", agentId: "mock-agent", reason: "No supported keyword matched." };
}
