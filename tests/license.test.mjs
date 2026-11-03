import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);
const lock = JSON.parse(await readFile(new URL("manifests/skills.lock.json", root), "utf8"));
const sha256 = value => createHash("sha256").update(value).digest("hex");
const legalPathPattern = /(?:^|\/)(?:LICENSE(?:-[A-Z0-9]+(?:[.-][A-Z0-9]+)*)?|NOTICE|THIRD_PARTY_NOTICES)(?:\.[A-Za-z0-9-]+)?$/i;
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
      assert.match(legal.upstreamPath, legalPathPattern);
      assert.match(legal.sha256, /^[a-f0-9]{64}$/);
      const content = await readFile(new URL(legal.path, root));
      assert.equal(sha256(content), legal.sha256, `${entry.name}: ${legal.path} hash mismatch`);
    }
  }
});

test("legal filenames accept LICENSE-MIT but reject nested paths", () => {
  assert.match("LICENSE-MIT", legalPathPattern);
  assert.match("path/to/LICENSE-APACHE-2.0", legalPathPattern);
  assert.doesNotMatch("LICENSE-MIT/extra", legalPathPattern);
  assert.doesNotMatch("not-a-license.txt", legalPathPattern);
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
    ["https://github.com/tt-a1i/archify", "tt-a1i; Cocoon AI"],
    ["https://github.com/Graphify-Labs/graphify", "Safi Shamsi and Graphify contributors"],
  ]);
  for (const entry of lock.skills.filter(({ sourceType, excluded }) => sourceType !== "original" && !excluded)) {
    const row = rows.get(entry.name);
    assert.ok(row, `${entry.name}: notice row missing`);
    assert.equal(row.length, 8, `${entry.name}: unexpected notice columns`);
    assert.ok(row[1].includes(`(${entry.repository})`), `${entry.name}: source mismatch`);
    assert.equal(row[2], `\`${entry.revision}\``);
    assert.equal(row[3], entry.sourceType);
    assert.equal(row[4], holders.get(entry.repository));
    const expectedLicense = entry.name === "archify"
      ? "MIT for Archify code; separately licensed assets per notice"
      : entry.name === "graphify"
        ? "Apache-2.0; MIT for portions retained under prior license"
        : ["learn-codebase", "impeccable"].includes(entry.name) ? "Apache-2.0" : "MIT";
    assert.equal(row[5], expectedLicense);
    assert.equal(row[6], entry.licenseFiles.map(({ path }) => `\`${path}\``).join("<br>"));
    assert.ok(row[7].trim(), `${entry.name}: modification notice missing`);
  }
  assert.equal(rows.size, lock.skills.filter(({ sourceType, excluded }) => sourceType !== "original" && !excluded).length);
});

test("Archify notice preserves non-commercial, share-alike, and font terms", async () => {
  const archify = lock.skills.find(({ name }) => name === "archify");
  const legal = archify.licenseFiles.find(({ upstreamPath }) => upstreamPath === "THIRD_PARTY_NOTICES.md");
  assert.ok(legal, "Archify third-party notice is retained in the lock");
  const notice = await readFile(new URL(legal.path, root), "utf8");
  assert.match(notice, /CC-BY-NC-SA-4\.0/);
  assert.match(notice, /CC-BY-SA-3\.0/);
  assert.match(notice, /CC-BY-SA-4\.0/);
  assert.match(notice, /SIL Open Font License 1\.1/);
  assert.match(notice, /non-commercial and share-alike conditions remain applicable/i);

  const thirdParty = await readFile(new URL("THIRD_PARTY_NOTICES.md", root), "utf8");
  const row = thirdParty.split("\n").find(line => line.startsWith("| `archify` |"));
  assert.match(row, /MIT for Archify code; separately licensed assets per notice/);
  assert.match(thirdParty, /Archify is not wholly MIT-licensed/i);

  const readme = await readFile(new URL("README.md", root), "utf8");
  assert.match(readme, /Archify's MIT license covers its code, while bundled artwork includes CC-BY-NC-SA-4\.0/);
  assert.match(readme, /pinned Archify asset notice/);
});

test("Impeccable carries its upstream NOTICE and separately pinned MIT attribution", async () => {
  const entry = lock.skills.find(({ name }) => name === "impeccable");
  assert.ok(entry.licenseFiles.some(file => file.upstreamPath === "NOTICE.md" && file.sha256 === "c60a093c2845fd9fb82f9c6f742ece31f379f8190b535309d32d66c45ccffdcb"), "upstream NOTICE absent from lock");
  const metadata = JSON.parse(await readFile(new URL("manifests/supplemental-licenses.json", root), "utf8"));
  const source = metadata.entries.find(item => item.skill === "impeccable");
  assert.equal(source.repository, "https://github.com/ehmo/platform-design-skills");
  assert.equal(source.licenseReferenceRevision, "dc2be825d8b439caea78e9eaa8fb3ac23b0ff3e9");
  assert.deepEqual(source.appliesTo, ["reference/ios.md", "reference/android.md"]);
  assert.equal(source.sha256, "1126322e2cc8d165adc4c792eeb195717de2bcc7b39be1ce77959d78e87ef685");
  assert.equal(sha256(await readFile(new URL(source.path, root))), source.sha256);
  const upstream = await readFile(new URL("plugins/agentic-engineering-skills/licenses/pbakaus-impeccable-NOTICE", root), "utf8");
  assert.match(upstream, /ehmo\/platform-design-skills/);
  assert.match(upstream, /skill\/reference\/ios\.md/);
  assert.match(upstream, /skill\/reference\/android\.md/);
  for (const doc of ["THIRD_PARTY_NOTICES.md", "docs/selective-install.md"]) {
    assert.ok((await readFile(new URL(doc, root), "utf8")).includes(source.path), `${doc} omits supplemental MIT license`);
  }
});

test("modified Impeccable source files carry adaptation notices and data formats have a separate notice", async () => {
  const base = new URL("plugins/agentic-engineering-skills/skills/impeccable/", root);
  const refs = "degraded/asset-producer.md degraded/documenter.md degraded/finish-reviewer.md degraded/manual-edit-applier.md product.md adapt.md adapt.native.md android.md animate.md audit.md audit.native.md bolder.md clarify.md colorize.md craft-floor.md critique.md delight.md distill.md doctor.md document.md extract.md harden.md hooks.md init.md ios.md layout.md live-setup.md live.md new-work.md onboard.md operate.md optimize.md overdrive.md polish.md quieter.md routing.md typeset.md visualize.md".split(" ");
  const scripts = ["impeccable", "impeccable.cmd", "live-browser-dom.js", "live-browser-ignores.js", "live-browser-session.js", "live-browser.js"];
  for (const file of [...refs.map(name => `reference/${name}`), ...scripts.map(name => `scripts/${name}`)]) {
    const text = await readFile(new URL(file, base), "utf8");
    assert.match(text.slice(0, 250), /Adapted from pbakaus\/impeccable \(Apache-2\.0\); modified for cross-host plugin distribution\./, `${file} lacks its file-level modification notice`);
  }
  const notice = await readFile(new URL("plugins/agentic-engineering-skills/licenses/pbakaus-impeccable-ADAPTATIONS-NOTICE", root), "utf8");
  for (const path of ["scripts/VERSION", "scripts/command-metadata.json", "scripts/data/font-index.json.deflate", "skill/scripts/data/font-index.json"]) {
    assert.ok(notice.includes(path), `adaptation notice omits ${path}`);
  }
});
