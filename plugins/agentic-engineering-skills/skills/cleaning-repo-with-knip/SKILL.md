---
name: cleaning-repo-with-knip
description: Use when removing dead code, unused dependencies, unused exports, or unlisted/missing imports flagged by knip; running a knip cleanup pass on a repo or monorepo; deciding whether a knip result is a real removal or a false positive; or recording knip false positives so future runs stop re-flagging them.
---

# Cleaning a Repo with Knip

## Overview

`knip` finds unused files, dependencies, exports, types, and unlisted/missing
imports. It is fast and deterministic — but **deterministic ≠ correct**. Knip does
static analysis, so it false-positives on dynamic `require`/`import()`, reflection,
string-keyed registries, framework entrypoints (routes, workers, models loaded by
side effect), and monorepo edges.

## When to Use

- Cleaning dead code / unused deps / unused exports a repo has accumulated.
- A knip run returns many findings (dozens to 100+) and per-claim manual triage
  doesn't scale.
- You keep re-seeing the same false positives every run and want them suppressed
  durably.

**When NOT to use:** a handful of obvious findings you can verify and delete in two
minutes — just do it. This runbook earns its cost at volume or when you want a
reviewable, repeatable cleanup with a false-positive ledger.

## Core Principle

**No knip claim is deleted until a verifier confirms it real, and nothing is
deleted off the working branch.** Record false positives with evidence and use an
approved suppression mechanism; a config rule alone does not establish policy
authority.

## Environment Prerequisites

- Use stable Knip `6.40.0` (Node `^20.19.0 || >=22.12.0`). Where Knip is
  already declared, align its manifest and lockfile with that exact version during
  authorized cleanup; analysis-only runs report version drift without editing it.
  Otherwise invoke `npm exec --yes --package=knip@6.40.0 -- knip`; this uses
  npm's tool cache without adding a project or global dependency.
- Knip config located: a root `knip.json`/`knip.ts`, OR per-workspace configs
  (`<ws>/knip.json`). Check workspace discovery before classifying findings.
- Verification commands known (typecheck / lint / test / build). Find them in
  `package.json` scripts before starting.
- Use available researcher, reviewer and implementation roles when delegation
  is authorized. Otherwise verify claims independently in the current session.

When using subagents, start each with a fresh context window. Provide the objective, relevant references, constraints, and expected output explicitly.

## Pipeline

Honor the requested scope: analysis-only runs must not modify files, dependencies,
configuration, or Git state. Apply changes only when authorized.

### 1. Sync the false-positive filter

Use the repository's documented ledger path. In Alfe this is
`docs/development/knip-false-positives.md`; use `Knip_false_positives.md` at the
repo root only when the project has no existing convention. Resolve the path from
the repository root, including when analyzing a workspace.

Read the ledger and the config that owns each workspace. Every ledger entry needs
a matching suppression in that config. During authorized cleanup, reconcile drift
in both directions: add a missing rule for an evidenced ledger entry, and document
a config rule missing from the ledger. The config is the durable suppression
source of truth; the ledger records its rationale. Never silently delete a rule
or invent evidence for an undocumented rule. Report all mismatches; unresolved
rationale remains explicit. Create a missing config only within the authorized
scope. Analysis-only runs report drift and leave both files unchanged.

An explicit repository spec, ADR, or owner decision can define a different policy.
If that policy conflicts with the files or leaves authority unresolved, report the
conflict before reconciling it.

**Where the rule lives (monorepo):** if a per-workspace `<ws>/knip.json` exists, the
rule goes there as a bare field (`ignore`, `ignoreDependencies`, `ignoreBinaries`).
Only a single root config uses the `workspaces.<name>.<field>` form. Pin option
names to the workspace's Knip **major** (v5 and v6 differ). The ledger is the
human-reviewable mirror; the config is the suppression sink.

### 2. Run knip + pre-filter

```bash
# Use the verified installed version after authorized alignment; in analysis-only
# runs, use the existing version and report any drift.
npm exec --yes --package=knip@6.40.0 -- knip --reporter json
node "<skill-directory>/parse-knip.mjs" --in "<saved-knip-report.json>" --fp "<repository-ledger-path>"
```

Save the first command's stdout as UTF-8 JSON using the host's file-output tool;
keep stderr and the exit code separate. Resolve `<skill-directory>` from the
loaded `SKILL.md`, including user-level skills; replace placeholders with actual
paths. Run the parser from the repository root, even for a workspace report.
Exit 1 can mean findings: continue only when stdout is a valid Knip report. Invalid output or an execution/configuration error aborts the run.
The helper supports Knip 6 issue-level file findings and both canonical ledger
categories (`files`, `exports`, etc.) and earlier `unused-*` category names.
Claims include workspace in their identity when reported. Legacy ledger entries
without workspace never suppress claims automatically: a missing workspace in a
report does not prove global ownership. Check entries in `ambiguousLegacy`
against the workspace config and ledger. Resolve them by recording a verified
workspace; until the reporter supplies that workspace, keep claims visible.

(monorepo without a root config: run the same Knip command per workspace.)
This buckets claims by type and drops anything already in the FP ledger. A knip run
failure (config/parse error) **aborts that workspace** before any verification —
in a monorepo, a failing workspace doesn't block the workspaces that parsed cleanly.

### 3. Verify — loop 1 (parallel)

Verify each claim against the contract below. When parallel delegation is available
and authorized, divide independent batches among researchers. Dispatch template:

> You are verifying knip dead-code claims. For EACH claim, decide
> `TRUE` (genuinely unused, safe to remove) | `UNCERTAIN` | `FALSE_POSITIVE`.
> Check real usages: `git grep` the symbol/file/dep, AND check dynamic patterns —
> `require(<computed>)`, `import(...)`, string-keyed registries, reflection, config
> references, framework entrypoints (routes/workers/models loaded by side effect),
> package `exports`/`main`, and external consumers. A grep with zero static hits is
> NOT enough to call something TRUE if a dynamic-load pattern is present.
> Return ONLY JSON matching: {schema}. Claims: {batch}

**Routing the verdicts:**
- `TRUE` with `confidence < 0.8` → treat as `UNCERTAIN` (route to loop 2). A real-but-
  shaky removal earns the cross-check; only confident TRUEs enter cleanup directly.
- Two parallel researchers disagree on a claim → `UNCERTAIN` (loop 2 breaks the tie).
- `unlisted-dependency` / `unresolved-import` claims are **not removals** — they are
  *report-only* (`action: report`). Surface them in step 6; fixing a missing import or
  adding a missing dep is a manual decision, never auto-applied here.

### 4. Clean the TRUE claims

1. Use an authorized dedicated branch and worktree (never delete on `main`).
2. Confirmed TRUEs here are `action: remove` (delete file/dep) or `action: rewrite`
   (drop an unused export but keep a still-referenced symbol — don't blind-delete the
   whole function; unexport, then let knip re-flag if it's now fully dead). Group into
   a **batched plan** by type/risk.
3. **Present the plan; get user approval before deleting.**
4. An authorized implementer applies each batch.
5. After each batch run the repo's quick verify (`verify:quick` script if present;
   else typecheck + lint of the **affected** workspace) plus any test that exercises
   the touched code. **On failure, revert that batch** and downgrade its claims to
   `UNCERTAIN` with the failure as evidence.

### 5. Re-study — loop 2 (UNCERTAIN)

Every `UNCERTAIN` (from step 3 + any step-4 reverts) gets a **fresh**
independent researcher and reviewer cross-checks where available; otherwise
perform a fresh second pass and report the independence limitation. Confirmed `TRUE`
→ folded back into step 4 (same approval + verify gate). Still `UNCERTAIN` →
carried to the report.

### 6. Report

Present `FALSE_POSITIVE` and still-`UNCERTAIN` claims to the user with evidence.
Discuss each.

### 7. Resolve false positives

Per claim, after discussion:
- **Stays false positive** → append a structured entry to the repository ledger
  AND apply the `knipRule` (config field, or in-source `@public`/`knip-ignore` tag
  when no by-name field exists). (Both. The `.md` alone suppresses nothing — knip
  never reads prose.)
- **Actually real** → fold into step 4 (approval + verify gate).
- **`report`-only** (unlisted/unresolved) → hand to the user as a fix-or-ignore
  decision; this runbook neither deletes nor auto-adds it.

### 8. Finalize

Emit a diff/summary. Commit ledger and config changes only when authorized.
Leave the cleanup branch for user review/merge — **no auto-merge.**

## Verdict Contract (subagent return schema)

```json
{ "id": "<type> :: <workspace> :: <target>", "type": "...", "workspace": "...", "target": "...",
  "verdict": "TRUE | UNCERTAIN | FALSE_POSITIVE",
  "action": "remove | rewrite | report | suppress",
  "confidence": 0.0,
  "evidence": "grep result / file:line / dynamic-import or entrypoint note",
  "knipRule": "ignore | ignoreDependencies | ignoreBinaries | workspaces.<name>.<field> | tag:@public | tag:knip-ignore" }
```

- `action`: `TRUE` → `remove`/`rewrite`; `FALSE_POSITIVE` → `suppress`;
  `unlisted-dependency`/`unresolved-import` → `report` (never auto-fixed).
- `knipRule` is **required** when verdict is `FALSE_POSITIVE` (step 7 writes it).
  Not every FP is expressible as a config field — a single unused **export** has no
  by-name config rule. Options, best first: an in-source tag — `/** @public */` if the
  export is a genuine public API surface, else `// knip-ignore` for internal-but-
  dynamically-referenced symbols — then a narrow config `ignore`. Flag that a
  **file-level** `ignore` is lossy — it hides any *future* dead export in that file.

## False-positive ledger format

Use `<claim-type> :: <workspace> :: <target>` when the reporter supplies a
workspace, otherwise `<claim-type> :: <target>`. This is the stable identity
used by `parse-knip.mjs` and the ledger:

```
## <claim-type> :: <workspace> :: <path-or-symbol-or-dependency>
- knip-rule: <ignore | ignoreDependencies | ignoreBinaries | workspaces.<name>.ignore>
- reason: <why knip is wrong — dynamic import / entrypoint / reflection / external consumer>
- evidence: <grep result, file:line, or config reference>
- confirmed: <YYYY-MM-DD>
```

`target` for symbols is `<file>#<symbol>` (matches `parse-knip.mjs` output).

## Out of Scope

auto-merge; auto-fixing missing imports (report them — fixing is a manual/cleanup-batch decision).
