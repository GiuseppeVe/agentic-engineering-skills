# Complex Implementation Workflow

## Objective

Implement complex development plans in a verifiable, iterative manner that remains
faithful to the specification provided by the user.

Optimize for:
- functional correctness;
- fidelity to the specification;
- code quality and maintainability;
- test coverage;
- clarity of assumptions;
- minimization of unnecessary changes.

Do not merely follow the plan mechanically: use the judgment necessary to achieve
the requested result while still respecting all explicit constraints.

## General rules

1. Read and analyze the entire specification before modifying the code.
2. Identify:
   - the final objective;
   - technical and functional constraints;
   - repository conventions;
   - dependencies;
   - implicit and explicit acceptance criteria;
   - risks and ambiguities.
3. If a requirement is ambiguous:
   - state the ambiguity explicitly;
   - formulate the adopted assumption;
   - proceed only if the assumption is reasonable and reversible.
4. Do not invent unnecessary requirements, APIs, behaviors, or files.
5. Keep changes focused and avoid refactoring unrelated to the plan.

## Phase 1: planning

Break the plan down into ordered, atomic subtasks.

Each subtask must contain:

- identifier;
- objective;
- files or components involved;
- dependencies;
- verifiable acceptance criteria;
- required tests or checks;
- risks and assumptions.

Acceptance criteria must be derived from the specification and its overall
philosophy. If they are not sufficiently determined, flag this and make the chosen
interpretation explicit.

Before implementing, verify that:
- all specification requirements are covered;
- the order of the subtasks is coherent;
- there are no missing dependencies;
- each subtask has a concrete verification method.

## Phase 2: implementation

For each subtask:

1. Inspect the necessary repository context.
2. Implement only the required behavior.
3. Respect the existing style, architecture, and conventions.
4. Add or update the relevant tests.
5. Run the most specific available checks.
6. Briefly record:
   - changes made;
   - tests run;
   - result;
   - any assumptions.

Whenever possible, delegate independent or exploratory activities to separate
agents. Keep each agent's context proportional to the task and provide only the
necessary information.

## Phase 3: independent review

After each significant group of changes, start one or more review agents with a
clean context and without relying on the conclusions of the agent that wrote the
code.

Each reviewer must independently verify:

- correctness against the specification;
- satisfaction of the acceptance criteria;
- regressions;
- edge cases;
- error handling;
- quality and readability;
- adequacy of the tests;
- compatibility with the existing architecture;
- compliance with the constraints and the overall philosophy of the plan.

The reviewer must produce findings classified as:

- BLOCKER: prevents completion;
- MAJOR: substantial issue;
- MINOR: non-blocking issue;
- NOTE: optional observation or improvement.

Do not consider a subtask complete until its criteria have been verified through
objective evidence: executed commands, exit codes, and test output.
