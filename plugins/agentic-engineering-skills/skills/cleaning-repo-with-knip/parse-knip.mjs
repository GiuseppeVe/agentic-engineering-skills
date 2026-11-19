#!/usr/bin/env node
// parse-knip.mjs — turn `knip --reporter json` into bucketed claims and
// pre-filter anything already recorded in docs/development/knip-false-positives.md.
//
// Usage:
//   npm exec --yes --package=knip@6.40.0 -- knip --reporter json | node parse-knip.mjs [--fp docs/development/knip-false-positives.md]
//   node parse-knip.mjs --in knip.json --fp docs/development/knip-false-positives.md
//
// Output (stdout, JSON):
//   { claims: [ { id, type, target, workspace } ], suppressed: [ ...same shape, +knipRule ],
//     counts: { byType: {...}, total, suppressed } }
//
// `id` is the stable identity `<type> :: <target>` — the SAME key used by
// docs/development/knip-false-positives.md headers, so re-runs match prior false positives.
// This file is the suppression PRE-FILTER; knip.json is the durable suppression
// sink. Keep both in sync (see SKILL.md step 1).

import { readFileSync } from "node:fs";

function arg(flag) {
  const i = process.argv.indexOf(flag);
  return i !== -1 ? process.argv[i + 1] : undefined;
}

function readInput() {
  const inPath = arg("--in");
  if (inPath) return readFileSync(inPath, "utf8");
  // stdin
  return readFileSync(0, "utf8");
}

// --- Parse docs/development/knip-false-positives.md into a Set of identity keys + rule map. ---
// Entry header format: `## <type> :: <target>`
// Followed by `- knip-rule: <rule>` lines.
function parseFpFile(path) {
  const rules = new Map(); // id -> knipRule
  if (!path) return rules;
  let text;
  try {
    text = readFileSync(path, "utf8");
  } catch {
    return rules; // no FP file yet -> nothing suppressed
  }
  let currentId = null;
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    const header = line.match(/^##\s+(.+?)\s*::\s*(.+?)\s*$/);
    if (header) {
      const category = header[1].trim();
      currentId = `${ITEM_TYPES[category] ?? category} :: ${header[2].trim()}`;
      rules.set(currentId, null);
      continue;
    }
    const rule = line.match(/^-\s*knip-rule:\s*(.+?)\s*$/i);
    if (rule && currentId) rules.set(currentId, rule[1].trim());
  }
  return rules;
}

// --- Normalize knip's JSON reporter output into flat claims. ---
// knip --reporter json shape (defensive across v5/v6):
//   { files?: string[], issues: [ { file, workspace?, files?:[{name}], dependencies:[{name}],
//     devDependencies, optionalPeerDependencies, unlisted, binaries,
//     unresolved, exports, types, enumMembers, duplicates } ] }
const ITEM_TYPES = {
  files: 'unused-file',
  dependencies: "unused-dependency",
  devDependencies: "unused-devDependency",
  optionalPeerDependencies: "unused-peerDependency",
  binaries: "unused-binary",
  unlisted: "unlisted-dependency",
  unresolved: "unresolved-import",
  exports: "unused-export",
  types: "unused-type",
  nsExports: "unused-namespaceExport",
  nsTypes: "unused-namespaceType",
  enumMembers: "unused-enumMember",
  namespaceMembers: "unused-namespaceMember",
  catalog: "unused-catalogEntry",
  catalogReferences: "unresolved-catalogReference",
  duplicates: "duplicate-export",
};

function nameOf(entry) {
  if (typeof entry === "string") return entry;
  if (entry && typeof entry === "object") {
    const name = entry.name ?? entry.symbol ?? entry.specifier ?? JSON.stringify(entry);
    return entry.namespace ? `${entry.namespace}.${name}` : name;
  }
  return String(entry);
}

function normalize(knip) {
  const claims = [];
  const push = (type, target, workspace) => {
    if (!target) return;
    claims.push({ id: `${type} :: ${target}`, type, target, workspace: workspace ?? null });
  };

  for (const f of knip.files ?? []) push("unused-file", f, null);

  for (const issue of knip.issues ?? []) {
    const ws = issue.workspace ?? null;
    const file = issue.file ?? null;
    for (const [key, type] of Object.entries(ITEM_TYPES)) {
      const list = issue[key];
      if (!Array.isArray(list)) continue;
      for (const item of list) {
        const n = nameOf(item);
        // exports/types/enumMembers/duplicates are file-scoped symbols
        const fileScoped = ["exports", "types", "nsExports", "nsTypes", "enumMembers", "namespaceMembers", "duplicates"].includes(key);
        const target = fileScoped && file ? `${file}#${n}` : n;
        push(type, target, ws);
      }
    }
  }
  return claims;
}

// --- Main ---
const fpRules = parseFpFile(arg("--fp"));
let knip;
try {
  knip = JSON.parse(readInput());
} catch (e) {
  process.stderr.write(`parse-knip: could not parse knip JSON: ${e.message}\n`);
  process.exit(2);
}

const all = normalize(knip);
const claims = [];
const suppressed = [];
for (const c of all) {
  if (fpRules.has(c.id)) {
    suppressed.push({ ...c, knipRule: fpRules.get(c.id) });
  } else {
    claims.push(c);
  }
}

const byType = {};
for (const c of claims) byType[c.type] = (byType[c.type] ?? 0) + 1;

process.stdout.write(
  JSON.stringify(
    { claims, suppressed, counts: { byType, total: claims.length, suppressed: suppressed.length } },
    null,
    2
  ) + "\n"
);
