import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, writeFile, mkdir, rm, readFile, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { sha256File, sha256Path, normalizeLf } from "../scripts/lib/hash.mjs";
import { checkoutImmutable } from "../scripts/lib/upstream.mjs";
import { verifyLocalEntries, compareLockDirectories } from "../scripts/lib/manifest.mjs";

test("checks out a real immutable superpowers revision", { timeout: 120000 }, async () => {
  const checkout = await checkoutImmutable("https://github.com/obra/superpowers", "d884ae04edebef577e82ff7c4e143debd0bbec99");
  try { assert.equal(await sha256File(join(checkout.path, "skills/brainstorming/SKILL.md")), "e14914605f640e0841758e45d0ab2a53243b59b921f929e47921c99668f2e61d"); }
  finally { await checkout.cleanup(); }
});

test("immutable checkout disables Git line-ending conversion", async () => {
  const source = await readFile(new URL("../scripts/lib/upstream.mjs", import.meta.url), "utf8");
  assert.match(source, /core\.autocrlf=false/);
  assert.match(source, /core\.eol=lf/);
  assert.match(source, /core\.safecrlf=false/);
});

test("patch input LF normalization is idempotent across source line endings", () => {
  const lf = Buffer.from("first\nsecond\n");
  const crlf = Buffer.from("first\r\nsecond\r\n");
  const cr = Buffer.from("first\rsecond\r");
  assert.deepEqual(normalizeLf(lf), normalizeLf(crlf));
  assert.deepEqual(normalizeLf(lf), normalizeLf(cr));
  assert.deepEqual(normalizeLf(normalizeLf(crlf)), normalizeLf(crlf));
});

test("detects local tampering and excluded entries", async () => {
  const root = await mkdtemp(join(tmpdir(), "pack-"));
  await mkdir(join(root, "plugins/p/skills/a"), { recursive: true });
  const file = join(root, "plugins/p/skills/a/SKILL.md");
  await writeFile(file, "clean");
  const hash = await sha256File(file);
  await verifyLocalEntries([{ name: "a", localSha256: hash }], root, "plugins/p/skills");
  await writeFile(file, "tampered");
  await assert.rejects(verifyLocalEntries([{ name: "a", localSha256: hash }], root, "plugins/p/skills"), /tamper/i);
  assert.doesNotThrow(() => compareLockDirectories([{ name: "a" }, { name: "excluded", excluded: true, exclusionReason: "license missing" }], ["a"]));
  assert.throws(() => compareLockDirectories([{ name: "a" }, { name: "excluded", excluded: true, exclusionReason: "license missing" }], ["a", "excluded"]), /mismatch/i);
  await mkdir(join(root, "tree/sub"), { recursive: true });
  await writeFile(join(root, "tree/sub/file"), "content");
  assert.match(await sha256Path(join(root, "tree")), /^[a-f0-9]{64}$/);
  await rm(root, { recursive: true, force: true });
});

test("adapted and original local imports retain provenance contracts", async () => {
  const lock = JSON.parse(await readFile(new URL("../manifests/skills.lock.json", import.meta.url), "utf8"));
  const byName = new Map(lock.skills.map(entry => [entry.name, entry]));
  const adapted = {
    brainstorming: "obra/superpowers",
    cavecrew: "JuliusBrussee/caveman",
    "learn-codebase": "thedotmack/claude-mem",
    "swarm-orchestration": "ruvnet/ruflo",
    "to-spec": "mattpocock/skills",
    wayfinder: "mattpocock/skills",
    "writing-plans": "obra/superpowers"
  };
  for (const [name, upstream] of Object.entries(adapted)) {
    const entry = byName.get(name);
    assert.equal(entry.sourceType, "adapted");
    assert.match(entry.sha256, /^[a-f0-9]{64}$/);
    assert.equal(await sha256File(new URL(`../plugins/agentic-engineering-skills/skills/${name}/SKILL.md`, import.meta.url)), entry.localSha256);
    assert.match(await readFile(new URL(`../plugins/agentic-engineering-skills/skills/${name}/SKILL.md`, import.meta.url), "utf8"), new RegExp(`Adaptation:[^\\n]+${upstream.replace("/", "\\/")}`));
    const patchUrl = new URL(`../${entry.patchPath}`, import.meta.url);
    assert.ok((await stat(patchUrl)).size > 0);
    assert.doesNotMatch(await readFile(patchUrl, "utf8"), /(?:C:\\\\Users|\\\\wsl\.localhost|\/home\/[^/]+)/);
  }
  for (const name of ["implementing-plans", "cleaning-repo-with-knip"]) {
    const entry = byName.get(name);
    assert.equal(entry.sourceType, "original");
    assert.equal("revision" in entry, false);
    assert.equal("repository" in entry, false);
    assert.equal(await sha256File(new URL(`../plugins/agentic-engineering-skills/skills/${name}/SKILL.md`, import.meta.url)), entry.localSha256);
  }
});

test("all skill frontmatter is closed and adaptation notices stay in Markdown body", async () => {
  const lock = JSON.parse(await readFile(new URL("../manifests/skills.lock.json", import.meta.url), "utf8"));
  for (const entry of lock.skills) {
    const source = await readFile(new URL(`../plugins/agentic-engineering-skills/skills/${entry.name}/SKILL.md`, import.meta.url), "utf8");
    const normalized = source.replace(/\r\n/g, "\n");
    assert.ok(normalized.startsWith("---\n"), `${entry.name} must open YAML frontmatter`);
    const closing = normalized.indexOf("\n---\n", 4);
    assert.ok(closing > 4, `${entry.name} must close YAML frontmatter`);
    const frontmatter = normalized.slice(4, closing);
    const body = normalized.slice(closing + 5);
    assert.match(frontmatter, /^name:\s*[^\n]+$/m, `${entry.name} frontmatter requires name`);
    assert.match(frontmatter, /^description:\s*(?:>|[^\n]+)$/m, `${entry.name} frontmatter requires description`);
    assert.doesNotMatch(frontmatter, /Adaptation:/, `${entry.name} adaptation notice must not be YAML`);
    if (entry.sourceType === "adapted") assert.match(body, /Adaptation:/, `${entry.name} adaptation notice must be Markdown body`);
  }
});
