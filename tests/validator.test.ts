import { describe, expect, it } from "vitest";
import { validateAgentOutput } from "../src/harness/validator.js";

describe("validateAgentOutput", () => {
  it("accepts a well-formed planner output", () => {
    expect(validateAgentOutput({ kind: "plan", summary: "Ship safely", actions: ["Test"] })).toMatchObject({ ok: true });
  });

  it("rejects missing actions and unknown kinds", () => {
    expect(validateAgentOutput({ kind: "plan", summary: "Ship safely" })).toMatchObject({ ok: false, reason: expect.any(String) });
    expect(validateAgentOutput({ kind: "other" })).toMatchObject({ ok: false, reason: expect.any(String) });
  });

  it("accepts a reviewer output", () => {
    expect(validateAgentOutput({ kind: "review", verdict: "pass", summary: "Looks good", evidence: ["tests"] })).toMatchObject({ ok: true });
  });
});
