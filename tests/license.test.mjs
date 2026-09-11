import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);
const lock = JSON.parse(await readFile(new URL("manifests/skills.lock.json", root), "utf8"));
const sha256 = value => createHash("sha256").update(value).digest("hex");
const canonicalMit = `MIT License

Copyright (c) 2026 GiuseppeVe

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
`;

test("repository license is canonical MIT for GiuseppeVe", async () => {
  const license = await readFile(new URL("LICENSE", root), "utf8");
  assert.equal(license, canonicalMit);
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

test("third-party notice rows exactly join lock entries to legal files", async () => {
  const notice = await readFile(new URL("THIRD_PARTY_NOTICES.md", root), "utf8");
  const rows = new Map(notice.split("\n").filter(line => /^\| `[^`]+` \|/.test(line)).map(line => {
    const cells = line.slice(2, -2).split(" | ");
    return [cells[0].slice(1, -1), cells];
  }).filter(([, cells]) => cells[3] !== "original"));
  const holders = new Map([
    ["https://github.com/obra/superpowers", "Jesse Vincent"],
    ["https://github.com/JuliusBrussee/caveman", "Julius Brussee"],
    ["https://github.com/mattpocock/skills", "Matt Pocock"],
    ["https://github.com/thedotmack/claude-mem", "Alex Newman"],
    ["https://github.com/ruvnet/ruflo", "ruvnet"],
    ["https://github.com/pbakaus/impeccable", "Paulo Bakaus"],
    ["https://github.com/nextlevelbuilder/ui-ux-pro-max-skill", "Next Level Builder"],
  ]);
  for (const entry of lock.skills.filter(({ sourceType, excluded }) => sourceType !== "original" && !excluded)) {
    const row = rows.get(entry.name);
    assert.ok(row, `${entry.name}: notice row missing`);
    assert.equal(row.length, 8, `${entry.name}: unexpected notice columns`);
    assert.ok(row[1].includes(`(${entry.repository})`), `${entry.name}: source mismatch`);
    assert.equal(row[2], `\`${entry.revision}\``);
    assert.equal(row[3], entry.sourceType);
    assert.equal(row[4], holders.get(entry.repository));
    assert.equal(row[5], ["learn-codebase", "impeccable"].includes(entry.name) ? "Apache-2.0" : "MIT");
    assert.equal(row[6], entry.licenseFiles.map(({ path }) => `\`${path}\``).join("<br>"));
    assert.ok(row[7].trim(), `${entry.name}: modification notice missing`);
  }
  assert.equal(rows.size, lock.skills.filter(({ sourceType, excluded }) => sourceType !== "original" && !excluded).length);
});
