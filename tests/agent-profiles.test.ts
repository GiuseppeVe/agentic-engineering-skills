import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const profiles = ["controller", "planner", "implementer", "reviewer", "test-runner", "researcher", "cleanup"];

describe("agent pack", () => {
  it("publishes seven complete host-neutral profiles", () => {
    for (const profile of profiles) {
      const content = readFileSync(`agent-profiles/${profile}.md`, "utf8");
      for (const section of ["## Input", "## Allowed actions", "## Structured output", "## Validation", "## Failure path", "## Provenance"]) {
        expect(content).toContain(section);
      }
    }
  });
});
