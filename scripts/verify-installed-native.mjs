import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { locateInstalledPayload, inspectInstalledPayload } from "./lib/native-receipt.mjs";

const args = new Map();
for (let i = 2; i < process.argv.length; i += 2) args.set(process.argv[i], process.argv[i + 1]);
const host = args.get("--host");
const sourceRoot = resolve(args.get("--source-root") ?? "plugins/agentic-engineering-skills");
const lock = JSON.parse(await readFile(resolve(args.get("--lock") ?? "manifests/skills.lock.json"), "utf8"));
const receipt = JSON.parse(await readFile(resolve(args.get("--receipt") ?? "manifests/native-discovery.json"), "utf8"));
const jsonDocuments = (args.get("--cli-json") ?? "").split(",").filter(Boolean).map(path => readFile(resolve(path), "utf8"));
const searchRoots = (args.get("--search-roots") ?? "").split(",").filter(Boolean);
const installed = await locateInstalledPayload({ host, explicitRoot: args.get("--installed-root"), jsonDocuments: await Promise.all(jsonDocuments), searchRoots });
const source = await inspectInstalledPayload(sourceRoot, { host });
const expected = lock.skills.filter(skill => {
  if (skill.excluded) return false;
  const path = skill.payloadPath?.replace(/^plugins\/agentic-engineering-skills\//, "") ?? `skills/${skill.name}`;
  return source.skillRoots.some(root => path === root || path.startsWith(`${root}/`));
}).map(skill => skill.name).sort();
for (const [label, actual] of [["configured source", source.skills], ["installed", installed.skills]]) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) throw new Error(`${host} ${label} SKILL.md inventory mismatch: expected ${expected.join(", ")}; got ${actual.join(", ")}`);
}
if (JSON.stringify(installed.skillRoots) !== JSON.stringify(source.skillRoots)) throw new Error(`${host} installed manifest skill roots mismatch`);
if (installed.treeHash !== source.treeHash) throw new Error(`${host} installed tree hash mismatch: source ${source.treeHash}; installed ${installed.treeHash}`);
if (installed.fullTreeHash !== source.fullTreeHash) throw new Error(`${host} installed full tree hash mismatch: source ${source.fullTreeHash}; installed ${installed.fullTreeHash}`);
if (receipt.schemaVersion !== 3) throw new Error("native receipt schemaVersion must be 3");
const evidence = receipt.hosts?.[host];
if (JSON.stringify(evidence?.installedPayload?.skills) !== JSON.stringify(expected)) throw new Error(`${host} installed receipt inventory mismatch`);
if (JSON.stringify(evidence?.installedPayload?.skillRoots) !== JSON.stringify(source.skillRoots)) throw new Error(`${host} installed receipt skill roots mismatch`);
if (installed.treeHash !== evidence?.installedPayload?.treeHash) throw new Error(`${host} installed receipt hash mismatch: receipt ${evidence?.installedPayload?.treeHash}; installed ${installed.treeHash}`);
if (installed.fullTreeHash !== evidence?.installedPayload?.fullTreeHash) throw new Error(`${host} installed receipt full tree hash mismatch: receipt ${evidence?.installedPayload?.fullTreeHash}; installed ${installed.fullTreeHash}`);
const result = { schemaVersion: 2, host, locatorBasis: installed.basis, installedRoot: installed.root, skills: installed.skills, skillRoots: installed.skillRoots, treeHash: installed.treeHash, sourceTreeHash: source.treeHash, fullTreeHash: installed.fullTreeHash, sourceFullTreeHash: source.fullTreeHash };
if (args.get("--output")) await writeFile(resolve(args.get("--output")), `${JSON.stringify(result, null, 2)}\n`);
process.stdout.write(`${host} installed payload verified: ${installed.skills.length} skills, ${installed.treeHash}, via ${installed.basis}\n`);
