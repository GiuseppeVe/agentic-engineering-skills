import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const event = process.argv[2];
if (!["SessionStart", "SubagentStart"].includes(event)) process.exit(0);
try {
  const path = join(dirname(fileURLToPath(import.meta.url)), "..", "SKILL.md");
  const body = readFileSync(path, "utf8").replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n/, "").trim();
  const context = `Caveman instructions (skill file: ${path}):\n${body}`;
  process.stdout.write(JSON.stringify({hookSpecificOutput: {hookEventName: event, additionalContext: context}}));
} catch (error) {
  process.stderr.write(`Caveman hook: ${error.message}\n`);
  process.exitCode = 1;
}
