import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import test from "node:test";

const root = new URL("../", import.meta.url);
const lock = JSON.parse(await readFile(new URL("manifests/skills.lock.json", root), "utf8"));
const sha256 = value => createHash("sha256").update(value).digest("hex");

test("repository license is canonical MIT for GiuseppeVe", async () => {
  const license = await readFile(new URL("LICENSE", root), "utf8");
  assert.match(license, /^MIT License\r?\n\r?\nCopyright \(c\) 2026 GiuseppeVe\r?\n/);
  assert.match(license, /Permission is hereby granted, free of charge/);
  assert.match(license, /THE SOFTWARE IS PROVIDED "AS IS"/);
});

test("every third-party entry joins exact pinned legal files", async () => {
  for (const entry of lock.skills.filter(({ sourceType, excluded }) => sourceType !== "original" && !excluded)) {
    assert.ok(Array.isArray(entry.licenseFiles) && entry.licenseFiles.length > 0, `${entry.name}: missing licenseFiles`);
    for (const legal of entry.licenseFiles) {
      assert.match(legal.path, /^plugins\/agentic-engineering-skills\/licenses\//);
      assert.match(legal.upstreamPath, /(?:^|\/)(?:LICENSE|NOTICE)(?:\.[A-Za-z0-9-]+)?$/i);
      assert.match(legal.sha256, /^[a-f0-9]{64}$/);
      const content = await readFile(new URL(legal.path, root));
      assert.equal(sha256(content), legal.sha256, `${entry.name}: ${legal.path} hash mismatch`);
    }
  }
});

test("Apache-2.0 license and NOTICE match pinned claude-mem blobs", () => {
  const entry = lock.skills.find(({ name }) => name === "learn-codebase");
  assert.deepEqual(entry.licenseFiles, [
    { upstreamPath: "LICENSE", path: "plugins/agentic-engineering-skills/licenses/thedotmack-claude-mem-LICENSE", sha256: "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30" },
    { upstreamPath: "NOTICE", path: "plugins/agentic-engineering-skills/licenses/thedotmack-claude-mem-NOTICE", sha256: "35003c303ee484c77872fd45eb5d590ce679d1ae7ac5bb672d33069cca66685b" },
  ]);
});

test("third-party notice table covers every third-party skill", async () => {
  const notice = await readFile(new URL("THIRD_PARTY_NOTICES.md", root), "utf8");
  for (const entry of lock.skills.filter(({ sourceType, excluded }) => sourceType !== "original" && !excluded)) {
    assert.ok(notice.includes(`| \`${entry.name}\` |`), `${entry.name}: notice row missing`);
    assert.match(notice, new RegExp(entry.revision));
    assert.match(notice, new RegExp(entry.sourceType));
  }
});
