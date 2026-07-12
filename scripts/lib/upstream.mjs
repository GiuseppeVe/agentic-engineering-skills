import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
const exec = promisify(execFile);

export async function checkoutImmutable(repository, revision) {
  if (!/^[0-9a-f]{40}$/i.test(revision)) throw new Error(`invalid immutable revision: ${revision}`);
  const path = await mkdtemp(join(tmpdir(), "skill-upstream-"));
  try {
    await exec("git", ["init", "-q", path]);
    await exec("git", ["-C", path, "fetch", "-q", "--depth=1", repository, revision]);
    await exec("git", ["-C", path, "checkout", "-q", "--detach", "FETCH_HEAD"]);
    const { stdout } = await exec("git", ["-C", path, "rev-parse", "HEAD"]);
    if (stdout.trim().toLowerCase() !== revision.toLowerCase()) throw new Error(`revision mismatch for ${repository}`);
    return { path, cleanup: () => rm(path, { recursive: true, force: true }) };
  } catch (error) { await rm(path, { recursive: true, force: true }); throw error; }
}
