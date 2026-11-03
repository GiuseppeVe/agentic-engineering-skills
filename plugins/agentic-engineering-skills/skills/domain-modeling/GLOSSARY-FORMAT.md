# GLOSSARY.md Format

## Template

```md
# {Context Name}

{One or two sentences describing the context and why it exists.}

## Language

**Order**:
{One or two sentences defining the term.}
_Avoid_: Purchase, transaction
```

## Rules

- Pick one canonical term for each concept; list synonyms under `_Avoid_`.
- Define what the term IS in one or two sentences, rather than what it does.
- Include only concepts specific to this project's context. General programming concepts, such as timeouts, error types, and utility patterns, do not belong merely because the project uses them often.
- Group natural clusters under subheadings; use a flat list for one cohesive area.

## Context layout

Follow the context-selection and lazy-creation rules in [SKILL.md](SKILL.md#locate-the-context). In a multi-context repo, root `GLOSSARY-MAP.md` lists contexts, their locations and relationships:

```md
# Glossary Map

## Contexts

- [Ordering](./src/ordering/GLOSSARY.md): receives and tracks customer orders
- [Billing](./src/billing/GLOSSARY.md): generates invoices and processes payments
- [Fulfillment](./src/fulfillment/GLOSSARY.md): manages picking and shipping

## Relationships

- **Ordering → Fulfillment**: `OrderPlaced` events start picking
- **Fulfillment → Billing**: `ShipmentDispatched` events start invoicing
- **Ordering ↔ Billing**: Shared `CustomerId` and `Money` types
```
