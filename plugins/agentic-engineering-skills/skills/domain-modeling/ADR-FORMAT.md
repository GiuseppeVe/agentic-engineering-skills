# ADR Format

Use the three-condition gate in [SKILL.md](SKILL.md#during-the-session) before offering an ADR.

Follow the repository's existing ADR register README or policy for format, status, numbering, approval and changelog. Do not create a parallel register. Use this file only as a fallback when the project has no ADR format guidance; follow repository-specific approval rules before treating a decision as accepted.

## Generic template

Use only when compatible with the project register; its README or policy takes precedence.

```md
# {Short title of the decision}

{1-3 sentences: context, decision, and why.}
```

A paragraph is enough. Include optional sections only when valuable:

- **Status** frontmatter: `proposed | accepted | deprecated | superseded by ADR-NNNN`, when revisiting decisions.
- **Considered Options**, when rejected alternatives are worth remembering.
- **Consequences**, for non-obvious downstream effects.

## Qualifying decision types

These still need all three conditions:

- Architectural shape, such as a monorepo or event-sourced write model with a projected read model.
- Integration patterns between contexts, such as domain events versus synchronous HTTP.
- Technology choices with meaningful lock-in: database, message bus, auth provider, deployment target; not every library.
- Ownership and scope, including explicit exclusions: a context owns Customer data, others reference IDs.
- Deliberate deviations from the expected approach, such as manual SQL instead of an ORM.
- Constraints code cannot reveal, such as compliance restrictions or a partner's response-time contract.
- Non-obvious rejected alternatives, to prevent future re-suggestions without their original context.
