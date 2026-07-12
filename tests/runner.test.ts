import { describe, expect, it } from "vitest";
import { createMockAgent } from "../src/agents/mock-agent.js";
import { runHarness } from "../src/harness/runner.js";

describe("runHarness", () => {
  it("retries invalid output once then escalates", () => {
    let calls = 0;
    const invalid = createMockAgent([{ kind: "plan" }, { kind: "plan" }]);
    const result = runHarness({ text: "Create a plan" }, {
      agents: { "planner-agent": (context) => { calls += 1; return invalid(context); } }
    });
    expect(calls).toBe(2);
    expect(result.status).toBe("escalated");
    expect(result.validationEvents).toHaveLength(2);
    expect(result.validationEvents.every((event) => event.type === "validation")).toBe(true);
  });

  it("uses routed planner agent with bounded context and complete trace", () => {
    const result = runHarness({ text: "Create a strength plan", state: { ignoredHistory: "not a top-level field" } });
    expect(result.agentId).toBe("planner-agent");
    expect(result.output).toMatchObject({ kind: "plan" });
    expect(Object.keys(result.context).sort()).toEqual(["budget", "constraints", "evidence", "objective", "state"]);
    expect(result.trace.map((event) => event.type)).toEqual(expect.arrayContaining(["classification", "route", "context", "validation", "final"]));
    expect(result).toMatchObject({ taskId: expect.any(String), classification: "plan", reason: expect.any(String) });
  });
});
