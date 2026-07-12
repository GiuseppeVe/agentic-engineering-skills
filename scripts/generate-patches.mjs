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
    const { stdout } = await exec("git", ["diff", "--no-index", "--", upstream, local]).catch(e => e.code === 1 ? e : Promise.reject(e));
    if (!stdout.trim()) throw new Error(`adapted skill ${source.name} has empty patch`);
    const patch = join(root, source.patchPath);
    await mkdir(dirname(patch), { recursive: true });
    await writeFile(patch, stdout);
  } finally { await checkout.cleanup(); }
}
