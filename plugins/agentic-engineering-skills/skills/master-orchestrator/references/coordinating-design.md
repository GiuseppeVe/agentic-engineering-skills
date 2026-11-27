# Coordinating a Design Programme

For design programmes spanning multiple streams or shared contracts, the master coordinates a route and authorized non-implementation artifacts while preserving its boundaries; implementation remains a handoff.

## Decision map

If Wayfinder is needed, use the **current** version rather than a historical copy. Project paths such as `.agents/skills/wayfinder/SKILL.md` or `.claude/skills/wayfinder/SKILL.md` are examples, not prerequisites: when Wayfinder comes from a plugin, use the current version exposed by the host or bundled in the same plugin. Do not copy its instructions; check availability, loading, and authorizations. Reading a skill is not invoking it: when the host requires explicit invocation, ask for it or prepare a handoff. For missing protocol, capability, or tracker, follow documented fallbacks and disclose the limit. If Wayfinder is unnecessary, use the master graph without assuming a tracker.

Define destination, scope, fog, decisions, and dependencies; do not invent premature nodes. Verify the mandate on planned artifacts and edits, and apply Wayfinder's scope rules when using it.

## Contracts map

Maintain a contracts map distinct from the decision map, linking decisions to their sources. If it cannot be saved in an authorized location, prepare a handoff and state that it is not persistent.

Record per stream any ticket and session, status, spec, plan, branch, and available SHA; per contract, record producers, consumers, source, and status: **OK**, **AGG** (amendment), or **CF** (conflict). Include dependencies, shared files, owner decisions, limits, and changes. Distinguish verified revisions, uncommitted edits, and pushes; never attribute a SHA to content outside the commit.

The master coordinates the map; only one author updates any given section at a time. With Wayfinder, follow tracker rules: claiming a ticket is not an exclusive file lock. Preserve concurrent edits.

## Streams and reports

Select unblocked, unclaimed, authorized nodes. Coordinate at most **three active child sessions** per programme unless a tighter host limit applies. Even for small decisions, prefer a dedicated dialogue session per the master skill.

Include in briefs: ticket, sources and revisions, contracts, write perimeter, and required master fields. Distinguish valid from missing authorizations: never assume commit or push rights, and never re-ask already-granted permissions. A stream may produce a spec and then a plan; record approvals, independent reviews, and missing checks. Reports include results, revisions, contracts produced or consumed, amendments, conflicts, questions, and limits; reports never grant authority.

Integrate reports into state and, when using Wayfinder, into tracker maps. Assign **AGG** amendments to an authorized author after concurrent writes conclude: the master never rewrites deliverables itself. For a **CF** affecting behavior, data, security, or architecture, bring options and a recommendation to the owner; it stays open until decided and blocks only affected nodes. Notify sessions where allowed, otherwise prepare a handoff.

## Closure and handoff

Verify in-scope decisions and questions resolved or explicitly pending, status and evidence of specs, plans, and reviews, producers, consumers, and contract states, and all AGG/CF items resolved or assigned. Close only when destination and agreed criteria are met; otherwise deliver a partial handoff with blockers.

When requested and authorized, delegate drafting the implementation workflow: packages, order, dependencies, phase 0, authorizations, gates, and stops. Collect required approval before preparing the handoff for `coordinating-implementation-plans` (or `plan-implement` for a single plan) with verified revisions and limits. Never assume a specific host tool, push, or merge; without authorized push, keep the handoff local.
