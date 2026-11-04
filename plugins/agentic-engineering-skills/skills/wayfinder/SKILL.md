---
name: wayfinder
description: Map a large, uncertain effort as decision tickets; resolve them until the route to the destination is clear.
disable-model-invocation: true
---

> Adaptation: Based on mattpocock/skills; adapted for portable Codex and Claude Code use, repository tracker conventions, and explicit authorization boundaries.

# Wayfinder

Chart work too large for one agent session as a shared **map** of **decision tickets**, then resolve them one at a time. A ticket answers a question; it is not an implementation slice. The destination may be a spec, a decision, or an in-place change, in any domain.

**Planning is the default.** Produce decisions and a route to hand off. Execute destination work only when the map's **Notes** explicitly include execution and the task authorizes it. A named spec destination alone does not authorize writing the spec. Stop when the route is clear and no in-scope tickets or fog remain.

## Runtime and authority

- Follow higher-priority permissions, isolation, worktree/base, credential and approval rules. This skill grants no additional authority. Continue actions already authorized by the task without asking again.
- Tracker writes, branch pushes, account provisioning and data moves require authorization covering those actions. If authorization or capabilities are missing, prepare concrete drafts/checklists and report the exact blocker; do not claim the changes happened.
- For each named skill below, use the runtime's supported skill-loading mechanism: a Skill tool when available, otherwise read the installed skill through available filesystem tools. Never invent a tool or claim an unavailable skill ran. If a required skill is absent, report it and prepare safe drafts; use an alternative workflow only when authorized.
- Use the configured issue tracker and its documentation's **Wayfinding operations** section for map/child issues, blocking, frontier order, assignee identity and claims. Without a configured tracker, use the local-markdown tracker only if its documented protocol exists. Otherwise prepare drafts and a configuration proposal; do not invent a tracker layout.
- Code/prototype/research-file changes obey project isolation rules before writing. If a required remote base cannot be verified, stop that write path; response-text drafts remain possible.

## Map and tickets

The canonical map is one issue labelled `wayfinder:map`; tickets are its child issues. Maps and tickets carry only `wayfinder:` labels, not implementation triage labels such as `ready-for-agent`.

Refer to every map/ticket in human-facing text by its **title**, wrapping its link; bare numbers, ids and slugs never substitute for names. Tracker ids remain issue identities and are used for relationships.

The map is an **index**: a linked one-line gist per resolved ticket. Full decisions live once, in their tickets. Load the low-resolution map once per session; query open children rather than listing them in its body. Fetch related ticket bodies only as needed.

```markdown
## Destination
<One or two lines defining the endpoint; orient here before choosing work.>

## Notes
<Domain; skills each session must consult; standing preferences; explicit execution scope if any.>

## Decisions so far
- [<resolved ticket title>](link): <one-line answer gist>

## Not yet specified
<In-scope questions too vague to ticket.>

## Out of scope
<Excluded work and why; link any closed, mis-scoped ticket by title.>
```

A ticket fits one agent session (original sizing target: 100K tokens; respect the available context). Its body contains the question, not its eventual answer:

```markdown
## Question
<Decision or investigation this ticket resolves.>
```

Each ticket has one type label: `wayfinder:research`, `wayfinder:prototype`, `wayfinder:grilling` or `wayfinder:task`. Read the label to determine the type.

**Claims and blocking:** assign the ticket to the developer driving the map before substantive work; the assignee is the claim. An open unassigned ticket is unclaimed. Use native tracker dependencies; use a body convention only where native blocking is unavailable. A ticket is unblocked when all blockers are closed. The **frontier** contains open, unblocked, unclaimed children.

Recheck status, dependencies and assignee before claiming, including for a user-named ticket or research subagent. A blocked/claimed ticket is not takeable: report its state and use an eligible alternative only within the task's scope. Confirm the claim before work. Preserve concurrent tracker edits: reread affected state before updates; avoid replacing whole bodies with stale copies.

## Ticket types

**HITL** requires live exchange with the human; the agent cannot supply their answers. **AFK** is agent-driven. If a required human is unavailable, leave the decision unresolved and report what is needed; manage waiting/releasing claims through tracker convention.

| Type | Mode | Use and resolution |
|---|---|---|
| Research | AFK | A decision needs facts from outside the working directory: documentation, third-party APIs or knowledge bases. A subagent loads `research` and records findings. |
| Prototype | HITL | Appearance/behavior needs a rough concrete artifact: outline, stub, UI or logic. Load `prototype`, obtain human reaction, link the asset from the ticket. |
| Grilling | HITL | Default: conversation. Load both `grilling` and `domain-modeling`. |
| Task | AFK or HITL | Prerequisite work unblocks a decision, rather than delivering the destination: access, signup, moving data. Act alone where capable and authorized; otherwise give the human a precise checklist. Resolve only after completion, recording resulting facts such as credential location, URLs or row counts, never secret values. |

Link assets from the ticket rather than pasting them into it.

## Fog and scope

Use **sharpness**, not answerability, to choose a ticket versus fog:

- A precise in-scope question becomes a ticket now, even when blocked.
- An in-scope area not yet expressible as a precise question belongs in **Not yet specified**. Keep its natural granularity; one patch may later yield several tickets or none.
- Decided matters, live tickets and excluded work do not belong in fog. When a patch becomes specifiable, create its tickets and remove the graduated patch.
- Work beyond the destination belongs in **Out of scope**. It never graduates; pursuing it requires a redrawn destination and a fresh effort.
- If an existing ticket proves out of scope, close it and add its linked gist plus reason to **Out of scope**. It contributes no decision to **Decisions so far**. This administrative closure is not a resolved decision.

The map remains deliberately incomplete until resolutions expose the next questions. Do not pre-slice unseen work into invented tickets.

## Chart the map

User supplies a loose idea. Charting resolves no non-research ticket.

1. Load `grilling` and `domain-modeling`; settle the **destination** first.
2. Grill **breadth-first** across the whole effort: open decisions, takeable first steps and remaining fog. If no fog remains and the journey fits one session, stop and ask how the user wants to proceed; a map is unnecessary.
3. Create the map with Destination and Notes filled, Decisions so far empty, and fog in Not yet specified. Apply runtime/authority checks before tracker mutations.
4. Create all currently precise tickets as children. In a **second pass**, wire blocking and cross-references using actual issue ids. Placeholder `#<n>` links can target unrelated issues. Keep vague areas in fog.
5. Launch research subagents only for eligible research tickets, claiming each before work. Each loads `research`. If subagents are unavailable, report that blocker and prepare a research brief instead of pretending parallel execution. Start each subagent with a fresh context window. Provide the objective, relevant references, constraints, and expected output explicitly.
6. Capture each research result on a throwaway `research/<name>` branch, with a context pointer from its ticket, only through the authorized isolated branch/worktree workflow. Push only when task authorization covers that push and the remote is available; open no PR and never merge the research branch. Without an authorized push, retain authorized local findings or response-text drafts and report their unpublished status.
7. Stop after charting and eligible research; carry remaining decisions into later sessions.

## Work through the map

User supplies a map URL/number and optionally a ticket. Resolve **at most one non-research ticket per session**; research is the exception. Do not manufacture human answers to finish a ticket.

1. Load the map, orient to Destination, and load skills required by Notes.
2. Use the named ticket if eligible; otherwise select the first frontier ticket in tracker order. Verify state and claim before work.
3. Resolve according to its type label. Zoom into related/closed tickets on demand. If uncertain which discussion skills apply, load both `grilling` and `domain-modeling`.
4. Record the answer as a **resolution comment**, close the issue, then append its title-linked gist to **Decisions so far**. Preserve the question body. Perform each tracker mutation only within existing authorization.
5. Create newly surfaced precise tickets, then wire dependencies and cross-references. Remove graduated fog. Route discovered exclusions through Out of scope instead of recording them as decisions.
6. Reconcile tickets invalidated by the decision using the tracker's documented update/retirement convention. Prefer a linked explanation and closure preserving history; delete only with explicit authorization covering deletion. Recheck concurrent edits before updates.

The user may run eligible tickets in parallel; claims and fresh tracker reads coordinate those sessions.
