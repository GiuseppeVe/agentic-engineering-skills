import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("pack documentation", () => {
  it("links installation, all packaging states, and provenance", () => {
    const readme = readFileSync("skills/README.md", "utf8").toLowerCase();
    for (const phrase of ["clone or download", "vendored skills", "adapted skills", "original skills", "provenance", "third-party notices"]) {
      expect(readme).toContain(phrase);
    }
  });
});
