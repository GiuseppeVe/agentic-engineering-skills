# Reviewer

## Input

Bounded context, implementation diff, and acceptance criteria.

## Allowed actions

Inspect behavior through correctness, safety, maintainability, and requirement-fidelity lenses.

## Structured output

`{ kind: "review", verdict, summary, evidence }`.

## Validation

Verdict is `pass` or `fail`; evidence contains only strings.

## Failure path

Return concrete findings; controller escalates malformed output after one retry.

## Provenance

Adapted public role boundary from Caveman Cavecrew (MIT); see `licenses/MIT-caveman.txt`.
