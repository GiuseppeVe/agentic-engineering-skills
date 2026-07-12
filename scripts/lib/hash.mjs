import { createHash } from "node:crypto";
import { readFile, readdir, lstat } from "node:fs/promises";
import { join, relative } from "node:path";
export async function sha256File(path) {
  return createHash("sha256").update(await readFile(path)).digest("hex");
}

export async function sha256Path(path) {
  const rootInfo = await lstat(path);
  if (rootInfo.isFile()) return sha256File(path);
  if (!rootInfo.isDirectory()) throw new Error(`unsupported filesystem entry: ${path}`);
  const hash = createHash("sha256");
  async function walk(directory) {
    const entries = (await readdir(directory, { withFileTypes: true })).sort((a, b) => a.name.localeCompare(b.name));
    for (const entry of entries) {
      const full = join(directory, entry.name);
      const info = await lstat(full);
      if (info.isDirectory()) await walk(full);
      else if (info.isFile()) hash.update(relative(path, full).replaceAll("\\", "/")).update("\0").update(await readFile(full)).update("\0");
      else throw new Error(`unsupported filesystem entry: ${relative(path, full).replaceAll("\\", "/")}`);
    }
  }
  await walk(path);
  return hash.digest("hex");
}

export function normalizeLf(content) {
  const buffer = Buffer.isBuffer(content) ? content : Buffer.from(content);
  return Buffer.from(buffer.toString("utf8").replace(/\r\n?/g, "\n"), "utf8");
}
