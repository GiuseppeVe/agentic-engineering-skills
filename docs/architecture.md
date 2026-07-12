# Architecture

`runHarness` is public core. It classifies text, chooses a named deterministic agent, constructs a five-field context envelope, validates agent output, retries a recoverable invalid response once, then either completes or escalates.

```mermaid
flowchart LR
  T[Task] --> R[Router]
  R --> C[Bounded context]
  C --> A[Named deterministic agent]
  A --> V[Validator]
  V -->|valid| O[Completed trace]
  V -->|first invalid| A
  V -->|second invalid| E[Escalated trace]
```

Agents receive only `objective`, `constraints`, `evidence`, `state`, and `budget`. Provider adapters are deliberately outside this reference path.
