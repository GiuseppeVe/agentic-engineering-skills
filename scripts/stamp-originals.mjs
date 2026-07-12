import { readFile, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { sha256File } from "./lib/hash.mjs";
const root = resolve(dirname(fileURLToPath(import.meta.url)), ".."), exec = promisify(execFile);
const path = join(root, "manifests/skills.lock.json"), lock = JSON.parse(await readFile(path, "utf8"));
const { stdout } = await exec("git", ["-C", root, "rev-parse", "HEAD"]);
for (const entry of lock.skills.filter(x => x.sourceType === "original")) {
  entry.releaseCommit = stdout.trim();
  entry.localSha256 = await sha256File(join(root, "plugins/agentic-engineering-skills/skills", entry.name, "SKILL.md"));
}
await writeFile(path, `${JSON.stringify(lock, null, 2)}\n`);
