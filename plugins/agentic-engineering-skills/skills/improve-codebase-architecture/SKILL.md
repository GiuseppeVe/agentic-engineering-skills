---
name: improve-codebase-architecture
description: Scan a codebase for deepening opportunities, present them as a visual HTML report, then grill through whichever one you pick.
disable-model-invocation: true
---

> Adaptation: Derived from mattpocock/skills; repository conventions and available runtime tools are discovered before use.

# Improve Codebase Architecture

Find architectural friction and **deepening opportunities** for testability and AI-navigability.

Load **codebase-design** for vocabulary and principles. Use its terms exactly: module, interface, implementation, depth, deep, shallow, seam, adapter, leverage, locality. Read the repository's configured domain-language source and relevant ADR register before exploring; preserve local filenames and conventions. If no terminology source exists, use `/domain-modeling` to discover or propose the appropriate one before relying on domain names. Repo edits still require authorization from the current task.

## 1. Explore

When using subagents, start each with a fresh context window. Provide the objective, relevant references, constraints, and expected output explicitly.

Before broad source exploration, consult Graphify when repository instructions prescribe it or a project Graphify graph is already available. Otherwise follow the host and repository's normal discovery policy; do not require Graphify or initialize a graph in repos that do not use it.

**Scope first: YAGNI.** Follow a user-named module, subsystem, or pain point. Otherwise inspect a substantial stretch of `git log --oneline` for recurring paths; prioritise these recent-change hot spots. Widen only if changes show no clear concentration.

If the runtime supports sub-agents, delegate an organic exploration; otherwise explore directly. Look for:

- Concepts scattered across many small modules.
- Shallow modules whose interface nearly matches their implementation.
- Pure functions extracted for testability while bugs remain in their callers, losing locality.
- Tight coupling leaking across seams.
- Missing tests or behaviour hard to test through the interface.

Apply the **deletion test** to suspected shallow modules: would deleting it concentrate complexity, or just move it? A "yes, concentrates" is the signal you want.

## 2. Present candidates

Write a single HTML report outside the repo: `<tmpdir>/architecture-review-<timestamp>.html`. Resolve `$TMPDIR`, falling back to `/tmp` or `%TEMP%` on Windows. Open with `xdg-open` (Linux), `open` (macOS), or `start` (Windows); give the absolute path.

Use [HTML-REPORT.md](HTML-REPORT.md) for the scaffold, candidate fields, visuals, and styling. It uses Tailwind and Mermaid via CDN, with side-by-side before/after visuals for every candidate. Explain benefits through locality, leverage, and improved tests. End with a **Top recommendation** and why.

Use domain names from the repository's terminology source where available. Describe the concept first (for example, "Order intake module") instead of defaulting to implementation class names; preserve the repo's established vocabulary.

**ADR conflicts:** surface a contradictory candidate only when observed friction warrants reopening the decision. Mark the conflict clearly with the ADR identifier and reason. Omit merely theoretical refactors an ADR forbids.

Do not propose interfaces yet. After writing the report, ask: "Which of these would you like to explore?"

## 3. Explore the chosen candidate

Load **grilling** once the user selects a candidate. Work through constraints, dependencies, the deepened module's shape, what sits behind the seam, and which tests survive.

Load **domain-modeling** as decisions crystallise:

- Add newly resolved domain terms to the repository's existing glossary/context file only when the current task authorizes documentation edits, creating it lazily when the convention allows. If none exists, follow `/domain-modeling`'s fallback and preserve the chosen filename. In an exploratory discussion without write authorization, present a proposed entry instead; discussion alone does not authorize a repo edit.
- For a load-bearing rejection, offer: "Want me to record this as an ADR so future architecture reviews don't re-suggest it?" Offer only if a future explorer needs the reason to avoid repeating the suggestion. Skip ephemeral ("not worth it right now") or self-evident reasons; apply domain-modeling's ADR gate.

For alternative interfaces, load **codebase-design** and use its design-it-twice parallel sub-agent pattern.
