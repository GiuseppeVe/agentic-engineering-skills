---
name: grilling
description: Use when the user wants to stress-test a plan, decision, or idea, or uses a 'grill' trigger phrase.
---

> **Adaptation:** Based on `mattpocock/skills`; adapted for a frontier-based design-tree flow for portable Codex and Claude Code use.

# Grilling

Interview relentlessly until shared understanding. Build a **design tree**: each decision branches into decisions that depend on it.

## Rounds

The **frontier** contains every decision whose prerequisites are settled. Ask the whole frontier in one round, numbering questions and recommending an answer for each. Phrase each question so "yes" accepts the recommendation.

```text
❓ **Q1** - **<title>**: <question, with detail/choices as needed>

➡️ <recommended answer>

---

❓ **Q2** - **<title>**: <question, with detail/choices as needed>

➡️ <recommended answer>
```

Wait for the user's answers, then reshape the tree and recompute its frontier. A question depending on another unanswered question belongs to a later round.

## Facts versus decisions

When using subagents, start each with a fresh context window. Provide the objective, relevant references, constraints, and expected output explicitly.

Find environmental facts yourself: use a sub-agent where the host supports one rather than asking the user for anything you can look up. A running exploration is an unsettled prerequisite: defer only its downstream questions and ask the rest of the frontier now. User owns decisions; put each decision to them and wait.

Finish when the frontier is empty, every branch visited, and no assumptions remain silent. Do not act on the result until the user confirms shared understanding.
