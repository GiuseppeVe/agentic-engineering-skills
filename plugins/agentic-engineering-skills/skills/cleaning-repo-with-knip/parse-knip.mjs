#!/usr/bin/env node
// parse-knip.mjs — turn `knip --reporter json` into bucketed claims and
// pre-filter anything already recorded in Knip_false_positives.md.
//
// Usage:
//   npm exec --yes --package=knip@6.40.0 -- knip --reporter json | node parse-knip.mjs [--fp Knip_false_positives.md]
//   node parse-knip.mjs --in knip.json --fp Knip_false_positives.md
//
// Output (stdout, JSON):
//   { claims: [ { id, type, target, workspace } ], suppressed: [ ...same shape, +knipRule ],
//     ambiguousLegacy: [legacyId], unhandled: [raw finding groups],
//     counts: { byType: {...}, total, suppressed, unhandled } }
//
// `id` is `<type> :: <workspace> :: <target>` when workspace is known,
// otherwise `<type> :: <target>`. Ledger headers use the same identity.
// This file is the suppression PRE-FILTER; knip.json is the durable suppression
// sink. Keep both in sync (see SKILL.md step 1).

import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

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

// --- Parse Knip_false_positives.md into a Set of identity keys + rule map. ---
// Entry header format: `## <type> :: <target>`
// Followed by `- knip-rule: <rule>` lines.
export function parseFpText(text) {
  const rules = new Map(); // id -> knipRule
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

function parseFpFile(path) {
  if (!path) return new Map();
  try {
    return parseFpText(readFileSync(path, "utf8"));
  } catch (error) {
    if (error.code === "ENOENT") return new Map();
    throw error;
  }
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
  classMembers: "unused-classMember",
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

function isMemberMap(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value) &&
    Object.values(value).every(Array.isArray);
}

export function normalize(knip) {
  const claims = [];
  const push = (type, target, workspace) => {
    if (!target) return;
    const ws = workspace || null;
    const id = ws === null ? `${type} :: ${target}` : `${type} :: ${ws} :: ${target}`;
    claims.push({ id, type, target, workspace: ws });
  };

  for (const f of knip.files ?? []) push("unused-file", f, null);

  for (const issue of knip.issues ?? []) {
    const ws = issue.workspace ?? null;
    const file = issue.file ?? null;
    for (const [key, type] of Object.entries(ITEM_TYPES)) {
      const list = issue[key];
      if (key === "enumMembers" || key === "classMembers") {
        if (!isMemberMap(list)) continue;
        for (const [parent, members] of Object.entries(list)) {
          for (const item of members) {
            const target = `${parent}.${nameOf(item)}`;
            push(type, file ? `${file}#${target}` : target, ws);
          }
        }
        continue;
      }
      if (!Array.isArray(list)) continue;
      for (const item of list) {
        // Knip's JSON reporter emits duplicate exports as groups of symbols.
        const n = key === "duplicates" && Array.isArray(item)
          ? item.map(nameOf).join(",") : nameOf(item);
        if (!n) continue;
        // File-scoped symbols and member maps include source path in identity.
        const fileScoped = ["exports", "types", "nsExports", "nsTypes", "namespaceMembers", "duplicates"].includes(key);
        const target = fileScoped && file ? `${file}#${n}` : n;
        push(type, target, ws);
      }
    }
  }
  return claims;
}

// Preserve unknown reporter data for human triage instead of silently dropping it.
// Empty arrays contain no findings; non-array values on recognized finding keys
// are retained too, because they may represent an unsupported reporter version.
export function findUnhandled(knip) {
  const unhandled = [];
  for (const [category, value] of Object.entries(knip)) {
    if (category === "files" || category === "issues") continue;
    if (Array.isArray(value) && value.length === 0) continue;
    unhandled.push({ source: "report", category, value });
  }
  for (const issue of knip.issues ?? []) {
    for (const [category, value] of Object.entries(issue)) {
      if (category === "file" || category === "workspace") continue;
      if (Object.hasOwn(ITEM_TYPES, category) && Array.isArray(value)) continue;
      if ((category === "enumMembers" || category === "classMembers") && isMemberMap(value)) continue;
      if (Array.isArray(value) && value.length === 0) continue;
      unhandled.push({ source: "issue", file: issue.file ?? null, workspace: issue.workspace ?? null, category, value });
    }
  }
  return unhandled;
}

// A missing workspace in a Knip issue does not prove the finding is global:
// issue.file may still belong to a workspace. Legacy, unscoped entries never
// suppress automatically; report them so their ownership can be verified.
export function filterClaims(all, fpRules, unhandled = []) {
  const claims = [];
  const suppressed = [];
  const ambiguousLegacy = new Set();
  for (const c of all) {
    const legacyId = `${c.type} :: ${c.target}`;
    if (c.workspace !== null && fpRules.has(c.id)) {
      suppressed.push({ ...c, knipRule: fpRules.get(c.id) });
    } else {
      claims.push(c);
      if (fpRules.has(legacyId)) ambiguousLegacy.add(legacyId);
    }
  }
  const byType = {};
  for (const c of claims) byType[c.type] = (byType[c.type] ?? 0) + 1;
  return { claims, suppressed, ambiguousLegacy: [...ambiguousLegacy], unhandled, counts: { byType, total: claims.length, suppressed: suppressed.length, unhandled: unhandled.length } };
}

function main() {
  const fpRules = parseFpFile(arg("--fp"));
  let knip;
  try {
    knip = JSON.parse(readInput());
  } catch (e) {
    process.stderr.write(`parse-knip: could not parse knip JSON: ${e.message}\n`);
    process.exit(2);
  }
  if (!knip || typeof knip !== "object" || Array.isArray(knip) ||
      !(Array.isArray(knip.files) || Array.isArray(knip.issues)) ||
      (knip.files !== undefined && !Array.isArray(knip.files)) ||
      (knip.issues !== undefined && !Array.isArray(knip.issues))) {
    process.stderr.write("parse-knip: invalid knip JSON report shape\n");
    process.exit(2);
  }
  process.stdout.write(JSON.stringify(filterClaims(normalize(knip), fpRules, findUnhandled(knip)), null, 2) + "\n");
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) main();
