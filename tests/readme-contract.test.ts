import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("README contract", () => {
  it("explains public usage and boundaries", () => {
    const readme = readFileSync("README.md", "utf8").toLowerCase();
    for (const phrase of ["quick start", "demo output", "router", "context", "validator", "golden", "design decisions", "security", "advanced tooling", "roadmap"]) {
      expect(readme).toContain(phrase);
    }
  });
});
