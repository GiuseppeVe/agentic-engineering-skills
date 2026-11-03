---
name: domain-modeling
description: Use when discussing codebase terminology, writing or editing its glossary or context docs, or recording or editing an ADR.
---

> Adaptation: Derived from mattpocock/skills; domain-document conventions are discovered per repository, with bundled formats used only as fallbacks.

# Domain Modeling

Actively challenge terms, probe relationships with edge cases, and record resolved language and decisions as they crystallise. Merely reading a glossary for vocabulary does not require this skill.

## Locate the context

- Read repository instructions and any configured domain-document guidance first.
- Discover existing maps and terminology sources, such as `GLOSSARY-MAP.md`, `CONTEXT-MAP.md`, `GLOSSARY.md`, `CONTEXT.md`, or context-specific equivalents. Follow their links and infer the relevant context; ask if unclear.
- Find the existing ADR register and its README or equivalent policy. Common locations include `docs/architecture/adr/`, `docs/adr/`, and context-local registers. Follow that register's status, numbering, and approval rules.
- Preserve the repository's names, layout, and formats. Do not rename `CONTEXT.md` to `GLOSSARY.md`, or create a parallel glossary/map/ADR register.
- If no domain-language convention exists, infer single- versus multi-context layout from the repo. For a single context, propose a root `GLOSSARY.md`; for a clear multi-context repo, propose a root `GLOSSARY-MAP.md` linking context glossaries. Use the bundled format as a fallback, and ask before writing if the convention remains ambiguous.
- Create a terminology document only when the first term is resolved and the current task authorizes documentation edits. Record ADRs in the existing project register only when its local policy permits, the decision qualifies, and the task authorizes that write.

## During the session

1. **Challenge conflicts immediately.** Compare user language with the glossary and stated behaviour with code; surface contradictions for resolution. For example: "The glossary defines cancellation as whole-Order, but you described partial cancellation. Which is right?"
2. **Sharpen vague or overloaded terms.** Propose a precise canonical term; distinguish concepts such as Customer and User instead of calling both account.
3. **Stress-test relationships.** Invent concrete edge cases that force precision about concept boundaries.
4. **Record each resolved term immediately when the current task authorizes documentation edits**, using the repository's established glossary/context format. If none exists, use [GLOSSARY-FORMAT.md](GLOSSARY-FORMAT.md) as the fallback for the terminology document chosen above. Keep it to domain terms: no implementation details, specifications, scratch notes, or implementation decisions. In an exploratory discussion without write authorization, present a proposed entry instead; discussion alone does not authorize a repo edit.
5. **Offer ADRs sparingly:** only when all three hold:
   - **Hard to reverse:** changing the decision later has meaningful cost.
   - **Surprising without context:** a future reader would ask why.
   - **Real trade-off:** genuine alternatives were considered and one chosen for specific reasons.

If any ADR condition is missing, skip it. For qualifying decisions, use [ADR-FORMAT.md](ADR-FORMAT.md).
