import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("tooling contract", () => {
  it("exposes deterministic public commands", () => {
    const pkg = JSON.parse(readFileSync("package.json", "utf8")) as { scripts: Record<string, string> };
    for (const script of ["demo", "test", "build", "lint", "evals", "maintenance:scan", "audit:public"]) {
      expect(pkg.scripts[script]).toBeTypeOf("string");
    }
  });
});
