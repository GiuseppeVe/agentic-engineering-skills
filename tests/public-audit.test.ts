import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { describe, expect, it } from "vitest";

function runAudit(directory: string) {
  return spawnSync(process.execPath, ["scripts/audit-public.mjs", directory], { encoding: "utf8" });
}

describe("public audit", () => {
  it("rejects forbidden markers and accepts clean fixtures", () => {
    const directory = mkdtempSync(join(tmpdir(), "harness-audit-"));
    try {
      writeFileSync(join(directory, "clean.md"), "Public documentation only.");
      expect(runAudit(directory).status).toBe(0);
      writeFileSync(join(directory, "bad.txt"), "sk_" + "abcdefghijk");
      expect(runAudit(directory).status).not.toBe(0);
    } finally {
      rmSync(directory, { recursive: true, force: true });
    }
  });
});
