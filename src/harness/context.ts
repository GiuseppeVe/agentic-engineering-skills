import type { ContextEnvelope, TaskInput } from "../types.js";

export function createContextEnvelope(task: TaskInput): ContextEnvelope {
  return {
    objective: task.text,
    constraints: task.constraints ?? [],
    evidence: task.evidence ?? [],
    state: task.state ?? {},
    budget: task.budget ?? { maxAttempts: 2 }
  };
}
