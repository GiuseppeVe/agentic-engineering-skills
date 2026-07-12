import type { AgentFunction, UnsupportedOutput } from "../types.js";

export const mockAgent: AgentFunction = (): UnsupportedOutput => ({
  kind: "unsupported",
  reason: "Task is outside documented deterministic capabilities."
});

export function createMockAgent(outputs: unknown[]): AgentFunction {
  let index = 0;
  return () => {
    const next = outputs[index];
    index += 1;
    return next ?? mockAgent({ objective: "", constraints: [], evidence: [], state: {}, budget: { maxAttempts: 2 } });
  };
}
