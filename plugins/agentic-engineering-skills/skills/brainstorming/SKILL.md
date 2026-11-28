---
name: brainstorming
description: Use to resolve open product, behavior, scope, or contract decisions before writing a spec or plan.
---

# Brainstorming

> **Adaptation:** Based on `obra/superpowers`; adjusted for portable Codex and Claude Code skill-pack use.

Identify the decisions that materially affect the expected outcome, scope, or
contracts. Reuse decisions already recorded in the request, spec, or ADRs.
When the outcome is already defined, follow the authorized workflow for the task.

Inspect enough context to identify which choices matter. Ask focused questions
about unresolved decisions and group related questions where practical.
Present alternatives when they have a meaningful trade-off. Recommend a choice
and explain the trade-off. Use reversible assumptions for routine details
within the agreed scope and state assumptions that affect the result.

When a mockup or diagram would help resolve a decision, offer the
[visual companion](visual-companion.md) and use it with the user's agreement.

When behavior depends on state or on the order of events, follow the
[behavior model](../development-process/references/behavior-model.md)
before any plan: the owner approves the diagrammed behavior.

Summarize the expected outcome, agreed decisions, constraints, and any open
questions. When a standalone spec is needed, use the
[`to-spec` template](../to-spec/SKILL.md).
Follow the repository's review and authorization rules for spec approval,
planning, and execution.
