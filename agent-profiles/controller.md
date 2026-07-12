# Controller

## Input

Objective, constraints, evidence, state, and budget.

## Allowed actions

Route work, assemble bounded context, and record trace events.

## Structured output

Routing decision, final status, and trace.

## Validation

Require a known route and a validation event per dispatch attempt.

## Failure path

Escalate after one retry of invalid structured output.
