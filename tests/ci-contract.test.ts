import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("CI contract", () => {
  it("runs every local verification command once", () => {
    const workflow = readFileSync(".github/workflows/ci.yml", "utf8");
    for (const command of ["npm run lint", "npm test", "npm run build", "npm run evals", "npm run audit:public"]) {
      expect(workflow.match(new RegExp(command, "g"))?.length).toBe(1);
    }
  });
});
