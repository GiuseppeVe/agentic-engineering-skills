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
deleted off the working branch.** Every false positive becomes a config rule, not
a memory.

## Environment Prerequisites

- Use stable Knip `6.40.0` (Node `^20.19.0 || >=22.12.0`). Where Knip is
  already declared, align its manifest and lockfile with that exact version.
  Otherwise invoke `npm exec --yes --package=knip@6.40.0 -- knip`; this uses
  npm's tool cache without adding a project or global dependency.
- Knip config located: a root `knip.json`/`knip.ts`, OR per-workspace configs
  (`<ws>/knip.json`). Check workspace discovery before classifying findings.
- Verification commands known (typecheck / lint / test / build). Find them in
  `package.json` scripts before starting.
- When delegation is authorized, use available native subagents for claim
  verification, independent review and bounded edits. Otherwise verify directly;
  report when independent review is unavailable.

When using subagents, start each with a fresh context window. Provide the objective, relevant references, constraints, and expected output explicitly.

## Pipeline

### 1. Sync the false-positive filter

Read `docs/development/knip-false-positives.md` (relative to repo root). Ensure **every** entry has a matching
ignore rule in the config that owns its workspace. Reconcile drift **both**
directions, with this winner policy: ledger entry missing its rule → **add the rule**;
config rule missing its ledger entry → **add the ledger entry** (the config is the
source of truth, the ledger documents it); never silently delete a rule. Report all
mismatches. Create the config if missing.

**Where the rule lives (monorepo):** if a per-workspace `<ws>/knip.json` exists, the
rule goes there as a bare field (`ignore`, `ignoreDependencies`, `ignoreBinaries`).
Only a single root config uses the `workspaces.<name>.<field>` form. Pin the option
names to the workspace's knip **major** (v5 ≠ v6 — some options were renamed). The
`.md` is the human-reviewable mirror; the config is the real, durable suppression sink.

### 2. Run knip + pre-filter

```bash
npm exec --yes --package=knip@6.40.0 -- knip --reporter json
node "<skill-directory>/parse-knip.mjs" --in "<saved-knip-report.json>" --fp docs/development/knip-false-positives.md
```

Run the parser from the repository root, even when the Knip report comes from a workspace.

Save the first command's stdout as UTF-8 JSON using the host's file-output tool;
keep stderr and the exit code separate. Resolve `<skill-directory>` from the
loaded `SKILL.md`, including user-level skills; replace both placeholders with
actual paths. Exit 1 can mean findings: continue only when stdout is a valid
Knip report. Invalid output or an execution/configuration error aborts the run.
The helper supports Knip 6 issue-level file findings and both canonical ledger
categories (`files`, `exports`, etc.) and earlier `unused-*` category names.

(monorepo without a root config: run the same Knip command per workspace.)
This buckets claims by type and drops anything already in the FP ledger. A knip run
failure (config/parse error) **aborts that workspace** before any verification —
in a monorepo, a failing workspace doesn't block the workspaces that parsed cleanly.

### 3. Verify — loop 1 (parallel)

When delegation is authorized, distribute independent claim batches to available
native verifier subagents in parallel; otherwise verify them directly. Each claim
gets a verdict per the contract below. Verification template:

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

1. `git switch -c chore/knip-cleanup` (never delete on `main`).
2. Confirmed TRUEs here are `action: remove` (delete file/dep) or `action: rewrite`
   (drop an unused export but keep a still-referenced symbol — don't blind-delete the
   whole function; unexport, then let knip re-flag if it's now fully dead). Group into
   a **batched plan** by type/risk.
3. **Present the plan; get user approval before deleting.**
4. Apply each approved batch directly or through an authorized native worker.
5. After each batch run the repo's quick verify (`verify:quick` script if present;
   else typecheck + lint of the **affected** workspace) plus any test that exercises
   the touched code. **On failure, revert that batch** and downgrade its claims to
   `UNCERTAIN` with the failure as evidence.

### 5. Re-study — loop 2 (UNCERTAIN)

Each `UNCERTAIN` (from step 3 or a step-4 revert) gets a fresh investigation
and an independent cross-check by available native reviewers when delegation is
authorized. Confirmed `TRUE` → step 4 (same approval + verification gate).
If the cross-check is unavailable or uncertainty remains, report the claim as
`UNCERTAIN`; do not promote it to `TRUE`.

### 6. Report

Present `FALSE_POSITIVE` and still-`UNCERTAIN` claims to the user with evidence.
Discuss each.

### 7. Resolve false positives

Per claim, after discussion:
- **Stays false positive** → append a structured entry to `docs/development/knip-false-positives.md`
  AND apply the `knipRule` (config field, or in-source `@public`/`knip-ignore` tag
  when no by-name field exists). (Both. The `.md` alone suppresses nothing — knip
  never reads prose.)
- **Actually real** → fold into step 4 (approval + verify gate).
- **`report`-only** (unlisted/unresolved) → hand to the user as a fix-or-ignore
  decision; this runbook neither deletes nor auto-adds it.

### 8. Finalize

Emit a diff/summary. Commit `docs/development/knip-false-positives.md` + `knip.json` changes. Leave
`chore/knip-cleanup` for user review/merge — **no auto-merge.**

## Verdict Contract (subagent return schema)

```json
{ "id": "<type> :: <target>", "type": "...", "target": "...",
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

## `docs/development/knip-false-positives.md` Format

Stable identity `<claim-type> :: <target>` so re-runs (and `parse-knip.mjs`) match:

```
## <claim-type> :: <path-or-symbol-or-dependency>
- knip-rule: <ignore | ignoreDependencies | ignoreBinaries | workspaces.<name>.ignore>
- reason: <why knip is wrong — dynamic import / entrypoint / reflection / external consumer>
- evidence: <grep result, file:line, or config reference>
- confirmed: <YYYY-MM-DD>
```

`target` for symbols is `<file>#<symbol>` (matches `parse-knip.mjs` output).

## Out of Scope

claude-flow CLI swarm; Workflow-tool fan-out; auto-merge; auto-fixing missing
imports (report them — fixing is a manual/cleanup-batch decision).
