import { cp, mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { checkoutImmutable } from "./lib/upstream.mjs";
import { sha256File, sha256Path } from "./lib/hash.mjs";
const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const sources = JSON.parse(await readFile(join(root, "manifests/skill-sources.json"), "utf8"));
const lock = JSON.parse(await readFile(join(root, "manifests/skills.lock.json"), "utf8"));
for (const source of sources.skills.filter(x => x.sourceType === "vendor")) {
  const checkout = await checkoutImmutable(source.repository, source.revision);
  try {
    const from = join(checkout.path, source.upstreamPath);
    const to = join(root, "plugins/agentic-engineering-skills/skills", source.name);
    await mkdir(to, { recursive: true });
    if (source.upstreamPath.endsWith("/")) await cp(from, to, { recursive: true });
    else await cp(from, join(to, "SKILL.md"));
    const hash = source.upstreamPath.endsWith("/") ? await sha256Path(to) : await sha256File(join(to, "SKILL.md"));
    const entry = lock.skills.find(x => x.name === source.name);
    if (entry.sha256 !== hash) throw new Error(`upstream hash mismatch for ${source.name}`);
  } finally { await checkout.cleanup(); }
}
await writeFile(join(root, "manifests/skills.lock.json"), `${JSON.stringify(lock, null, 2)}\n`);
