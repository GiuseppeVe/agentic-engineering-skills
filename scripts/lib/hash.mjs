import { createHash } from "node:crypto";
import { readFile, readdir, stat } from "node:fs/promises";
import { join, relative } from "node:path";
export async function sha256File(path) {
  return createHash("sha256").update(await readFile(path)).digest("hex");
}

export async function sha256Path(path) {
  if (!(await stat(path)).isDirectory()) return sha256File(path);
  const hash = createHash("sha256");
  async function walk(directory) {
    const entries = (await readdir(directory, { withFileTypes: true })).sort((a, b) => a.name.localeCompare(b.name));
    for (const entry of entries) {
      const full = join(directory, entry.name);
      if (entry.isDirectory()) await walk(full);
      else if (entry.isFile()) hash.update(relative(path, full).replaceAll("\\", "/")).update("\0").update(await readFile(full)).update("\0");
    }
  }
  await walk(path);
  return hash.digest("hex");
}
