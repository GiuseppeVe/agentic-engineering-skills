import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

const lock = JSON.parse(readFileSync(new URL("../skills/sources.lock.json", import.meta.url), "utf8"));
const required = ["name", "source", "revision", "upstreamPath", "license", "status", "dependencies", "packagePath"];
const allowedStatuses = new Set(["vendored", "adapted", "original"]);
const failures = lock.entries.flatMap((entry) => {
  const missing = required.filter((key) => entry[key] === undefined || entry[key] === "");
  if (!/^[0-9a-f]{40}$/.test(entry.revision ?? "")) missing.push("40-character revision");
  if (!allowedStatuses.has(entry.status)) missing.push("allowed status");
  if (!existsSync(resolve(entry.packagePath ?? "", "SKILL.md"))) missing.push("package skill");
  if (["vendored", "adapted"].includes(entry.status)) {
    if (entry.license === "unknown") missing.push("known license");
    if (!entry.noticePath || !existsSync(resolve(entry.noticePath))) missing.push("notice path");
  }
  return missing.length === 0 ? [] : [`${entry.name}: ${missing.join(", ")}`];
});

if (failures.length > 0) {
  console.error(failures.join("\n"));
  process.exitCode = 1;
} else {
  console.log(`Verified ${lock.entries.length} provenance entries.`);
}
