---
name: simplify
description: Review the changed code for reuse, simplification, efficiency, and altitude cleanups, then apply the fixes. Quality only - it does not hunt for bugs; use a code review for that. Use when the user asks to simplify, clean up, or tidy recent changes.
---

# Simplify

Review the code changed in the current task and apply cleanups. Scope is quality, not correctness: do not hunt for bugs, and do not change behavior.

## Scope

1. Determine the changed code: `git diff` (unstaged + staged) and, if the work is already committed, `git diff <base>...HEAD`. If the user named files or a range, use that instead.
2. Read each changed file in full around the hunks, not just the diff lines.
3. Touch only code introduced or modified by the change. Leave unrelated debt alone; list it as a follow-up instead.

## What to look for

- **Reuse**: new code that duplicates an existing helper, utility, component, type, or constant. Search the repo (names, similar logic) before concluding something is new. Replace the duplicate with the existing one, or upgrade the existing one if it almost fits.
- **Simplification**: needless abstraction, wrappers with one caller, dead parameters, unused exports/imports/variables, redundant state, deep nesting that early returns would flatten, copy-pasted branches that can share code, over-defensive checks for cases that cannot occur.
- **Efficiency**: repeated work in loops, N+1 queries or calls, redundant re-computation or re-renders, sequential awaits that could run in parallel, unbounded data loaded when a slice suffices. Fix only when the improvement is clear and safe.
- **Altitude**: code at the wrong level of abstraction or in the wrong place - business logic in UI/handlers, low-level details leaking into high-level flow, logic placed far from its data, helpers that belong in a shared module (or the reverse: a shared module bloated by one caller's needs).
- **Consistency**: match the surrounding code's naming, comment density, error handling, and idioms. Remove comments that restate the code.

## Procedure

1. List findings briefly, each with file and reason.
2. Apply the fixes directly with minimal, behavior-preserving edits.
3. Before deleting anything made obsolete, check references (search the repo, dynamic usage, config, tests). "Legacy" alone is not a reason to delete. If the repo keeps a registry of intentionally retained code, respect it.
4. Run the smallest relevant checks (typecheck, lint, affected tests) and report exact commands as pass, fail, or not run.
5. Report: what was changed, what was deliberately left alone, remaining debt, and checks run.

## Rules

- No new dependencies, no convention changes, no drive-by refactors outside the change.
- If a cleanup would alter behavior or public contracts, do not apply it; flag it to the user.
- If the project requires isolated worktrees or branches for code edits, follow that before editing.
