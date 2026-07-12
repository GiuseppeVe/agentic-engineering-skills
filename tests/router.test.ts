import { describe, expect, it } from "vitest";
import { routeTask } from "../src/harness/router.js";

describe("routeTask", () => {
  it.each([
    ["Create a release plan", "plan", "planner-agent"],
    ["Review this pull request", "review", "reviewer-agent"],
    ["Translate this paragraph", "unsupported", "mock-agent"]
  ] as const)("routes %s", (text, kind, agentId) => {
    const route = routeTask({ text });
    expect(route).toMatchObject({ kind, agentId });
    expect(route.reason).not.toEqual("");
  });
});
