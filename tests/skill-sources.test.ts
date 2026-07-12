import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("skill provenance", () => {
  it("records complete, safe provenance", () => {
    const lock = JSON.parse(readFileSync("skills/sources.lock.json", "utf8")) as { entries: Array<Record<string, unknown>> };
    expect(lock.entries.length).toBeGreaterThan(0);
    for (const entry of lock.entries) {
      for (const field of ["name", "source", "revision", "license", "status", "dependencies"]) {
        expect(entry[field]).toBeTruthy();
      }
      if (["vendored", "adapted"].includes(String(entry.status))) expect(entry.license).not.toBe("unknown");
    }
  });
});
