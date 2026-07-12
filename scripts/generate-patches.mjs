import { readFile, writeFile, mkdir } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { checkoutImmutable } from "./lib/upstream.mjs";
const exec = promisify(execFile), root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const sources = JSON.parse(await readFile(join(root, "manifests/skill-sources.json"), "utf8"));
for (const source of sources.skills.filter(x => x.sourceType === "adapted")) {
  const checkout = await checkoutImmutable(source.repository, source.revision);
  try {
    const local = join(root, "plugins/agentic-engineering-skills/skills", source.name, "SKILL.md");
    const upstream = join(checkout.path, source.upstreamPath);
    const { stdout } = await exec("git", ["-c", "core.autocrlf=false", "diff", "--no-index", "--", upstream, local], { maxBuffer: 16 * 1024 * 1024 }).catch(e => e.code === 1 ? e : Promise.reject(e));
    if (!stdout.trim()) throw new Error(`adapted skill ${source.name} has empty patch`);
    const before = `a/${source.name}/SKILL.md`, after = `b/${source.name}/SKILL.md`;
    const deterministic = stdout
      .replace(/^diff --git .*$/m, `diff --git ${before} ${after}`)
      .replace(/^--- .*$/m, `--- ${before}`)
      .replace(/^\+\+\+ .*$/m, `+++ ${after}`);
    const patch = join(root, source.patchPath);
    await mkdir(dirname(patch), { recursive: true });
    await writeFile(patch, deterministic);
  } finally { await checkout.cleanup(); }
}
