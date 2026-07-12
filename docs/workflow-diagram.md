# Workflow diagrams

## Design flow

```mermaid
flowchart LR
  Objective --> Constraints --> Route --> Context --> Validate --> Trace
```

## Maintenance flow

```mermaid
flowchart LR
  Change --> Lint --> Test --> Build --> Evals --> PublicAudit --> HumanReview[Review Knip findings]
```
