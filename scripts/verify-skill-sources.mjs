import { readFileSync } from "node:fs";

const lock = JSON.parse(readFileSync(new URL("../skills/sources.lock.json", import.meta.url), "utf8"));
const required = ["name", "source", "revision", "license", "status", "dependencies"];
const failures = lock.entries.flatMap((entry) => {
  const missing = required.filter((key) => entry[key] === undefined || entry[key] === "");
  if (["vendored", "adapted"].includes(entry.status) && entry.license === "unknown") missing.push("known license");
  return missing.length === 0 ? [] : [`${entry.name}: ${missing.join(", ")}`];
});

if (failures.length > 0) {
  console.error(failures.join("\n"));
  process.exitCode = 1;
} else {
  console.log(`Verified ${lock.entries.length} provenance entries.`);
}
