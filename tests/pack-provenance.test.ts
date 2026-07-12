import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

type Entry = {
  name: string;
  source: string;
  revision: string;
  upstreamPath: string;
  license: string;
  status: "vendored" | "adapted" | "original";
  dependencies: string[];
  noticePath?: string;
  packagePath: string;
};

const requiredSkills = [
  "grill-me", "grilling", "wayfinder", "to-spec", "setup-matt-pocock-skills",
  "improve-codebase-architecture", "codebase-design", "domain-modeling", "brainstorming",
  "writing-plans", "writing-skills", "test-driven-development", "using-git-worktrees",
  "caveman", "cavecrew", "swarm-orchestration", "learn-codebase", "implementing-plans",
  "cleaning-repo-with-knip"
];

describe("public pack provenance", () => {
  it("maps every public skill to a complete, valid provenance entry", () => {
    const lock = JSON.parse(readFileSync("skills/sources.lock.json", "utf8")) as { entries: Entry[] };
    expect(lock.entries.map((entry) => entry.name).sort()).toEqual([...requiredSkills].sort());
    for (const entry of lock.entries) {
      expect(entry.source).not.toBe("");
      expect(entry.revision).toMatch(/^[0-9a-f]{40}$/);
      expect(entry.upstreamPath).not.toBe("");
      expect(entry.license).not.toBe("unknown");
      expect(entry.dependencies).toBeInstanceOf(Array);
      expect(existsSync(resolve(entry.packagePath, "SKILL.md"))).toBe(true);
      if (entry.status !== "original") {
        expect(entry.noticePath).toBeTruthy();
        expect(existsSync(resolve(entry.noticePath ?? ""))).toBe(true);
      }
    }
  });
});
