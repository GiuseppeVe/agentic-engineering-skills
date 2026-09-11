---
name: how-to-use-codex
description: Use when a user says "scrivi un prompt per Codex", "genera un prompt per Codex", or asks to write, generate, improve, shorten, or critique a prompt for Codex, a GPT-5.6 coding agent, or a GPT-6 Astra coding agent; not when they ask to carry out coding work directly.
---

# How to Use Codex

## Goal

Create one paste-ready prompt. Input: task + supplied context. Output: task-specific prompt plus material missing decisions. GPT-5.6 and GPT-6 Astra work best with a lean outcome contract: goal, context, hard constraints, authority, proof, success criteria, output shape. State rules once. Do not narrate steps unless they encode real requirements.

## Current Official Guidance

When model availability, pricing, API controls, or current prompting guidance matters, read the current official OpenAI documentation before recommending settings. Do not invent model names, settings, availability, pricing, or runtime capabilities. Preserve the user's explicitly requested model. Cite the fetched official page when current facts affect the recommendation. Refresh this section when OpenAI publishes a newer model guide.

## Build Prompt

Match prompt language to user. First classify task: `answer/explain/review/diagnose/plan` or `change/build/fix`.

Write only applicable sections, in this order:

```text
<task>
Goal: [observable outcome].
Context: [repo/path, relevant domain facts, sources, current behavior].
Scope: [included work]. Exclude: [out-of-scope work].
Requirements: [hard functional/nonfunctional constraints and acceptance criteria].
Authority: [safe local actions allowed]. Ask before [external, destructive, costly, or scope-expanding actions].
Validation: [tests/checks and required evidence].
Deliverable: [exact final-answer structure, e.g. findings ranked with evidence; or files changed, validation results, remaining caveats].
</task>
```

For `answer/explain/review/diagnose/plan`, authority defaults to inspect and report only: no changes. For `change/build/fix`, allow in-scope local edits and non-destructive validation. Always require confirmation for external writes, destructive actions, purchases, credentials, installs, commit/push, or material scope expansion unless user explicitly authorizes them.

## Keep It Lean

- Include context that changes decisions: paths, interfaces, expected behavior, constraints, links/files, examples that fix measured gaps.
- Convert vague quality words into observable checks. `Fast` -> latency budget; `safe` -> rollback/backup condition; `good CSV` -> fields, escaping, encoding, row set.
- Say how important unknowns work: inspect first; ask only if ambiguity materially changes outcome, safety, or scope. Do not invent missing product decisions.
- Request evidence, not process theatre: exact tests/checks, inspected artifact, diff, benchmark, or citations as needed.
- Short output: say what must remain, then what may be omitted. Never use generic "be concise" alone.
- Do not repeat policy, tool instructions, or examples. Expose/request only task-relevant tools or sources.

## GPT-5.6 Model Choice

Recommend separately from prompt when requested. `gpt-5.6` aliases Sol.

| Tier | Use for |
|---|---|
| Sol | complex reasoning/coding, uncertain architecture, high-value review |
| Terra | normal coding workload needing intelligence/cost balance |
| Luna | simple, bounded, high-volume/cost-sensitive API work |

Codex UI availability is account/runtime-specific. Never promise Luna, Pro mode, exact reasoning controls, or a model picker exists. If user controls API: start `medium`; use `low` for latency; raise to `high`/`xhigh` only after measured quality gain; reserve `max` and Pro mode for hard quality-first work. Prompt stays outcome-focused; never ask model to "think harder."

## GPT-6 Astra Model Choice

Recommend separately from prompt when requested. Verify the current model page before making a current recommendation. GPT-6 Astra is intended for the hardest end-to-end work; choose a simpler available model when task scope and measured quality allow it.

- Preserve the user's explicitly requested model and effective reasoning level during migration unless official guidance requires a change.
- GPT-6 Astra does not support `none` reasoning effort. Start with `low` for routine work; raise effort only when task complexity or measured quality justifies it.
- Codex UI availability is account/runtime-specific. Never promise a model picker, Pro mode, exact controls, pricing, or access.
- Keep prompts outcome-focused. Do not ask a model to "think harder."

For API callers, verify the current official model page for Responses API, tool-calling, unsupported parameters, processing tiers, prompt caching, and reasoning controls before writing request code.

## Subagent Delegation

- Delegate parallelizable work when it can save time or improve quality.
- Give each subagent a bounded packet: goal, context, constraints, authority, validation, and deliverable.
- Keep delegation prompts legible. Include exact paths, acceptance criteria, and evidence required from the subagent.
- Do not delegate when shared state, sequencing, or coordination cost makes independent work unsafe.

## Testing and Verification

- Match verification depth to change risk. Do not add tests that only mirror a reversible, low-impact change.
- Run tests appropriate to the requested change and report exact checks and results.
- Broaden testing only when new changes, failures, or unresolved concerns justify it.

## Return

Output prompt first in one Markdown code block. Then, if useful, give a model recommendation and material missing decisions. Do not expand prompt with optional boilerplate.

## Sources

Only when model availability, pricing, API controls, or current guidance is material, refresh facts from the official OpenAI documentation: https://developers.openai.com/api/docs/guides/latest-model and https://developers.openai.com/api/docs/models.




