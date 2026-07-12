import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { resolve, relative, extname, join } from "node:path";

const root = resolve(process.argv[2] ?? process.cwd());
const excludedDirectories = new Set([".git", "node_modules", "dist", "coverage"]);
const excludedExtensions = new Set([".png", ".jpg", ".jpeg", ".gif", ".pdf", ".zip", ".lock"]);
const forbidden = [
  ["secret-prefix", /\b(?:sk|ghp|github_pat|AIza)_[A-Za-z0-9_-]{8,}\b/],
  ["private-url", /https?:\/\/(?:localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+)/i],
  ["source-project-identifier", /\balfe(?:[_ -]?ai|[_ -]?app)?\b/i]
];
const logExtensions = new Set([".log", ".jsonl", ".transcript"]);

function filesIn(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const path = join(directory, entry.name);
    if (excludedDirectories.has(entry.name)) return [];
    if (entry.isDirectory()) return excludedDirectories.has(entry.name) ? [] : filesIn(path);
    return entry.isFile() ? [path] : [];
  });
}

const findings = [];
for (const file of filesIn(root)) {
  const extension = extname(file).toLowerCase();
  const path = relative(root, file);
  if (logExtensions.has(extension)) findings.push(`${path}: transcript-or-log-extension`);
  if (excludedExtensions.has(extension) || statSync(file).size > 1_000_000) continue;
  const text = readFileSync(file, "utf8");
  for (const [rule, pattern] of forbidden) {
    if (pattern.test(text)) findings.push(`${path}: ${rule}`);
  }
}

if (findings.length > 0) {
  console.error(findings.join("\n"));
  process.exitCode = 1;
} else if (existsSync(root)) {
  console.log("Public audit passed.");
}
