# Planner

## Input

Bounded context envelope for a planning task.

## Allowed actions

Produce deterministic plan summary and actions; do not access providers or network.

## Structured output

`{ kind: "plan", summary, actions }`.

## Validation

Summary and every action must be non-empty strings.

## Failure path

Return malformed output only in a controlled test; controller retries then escalates.
