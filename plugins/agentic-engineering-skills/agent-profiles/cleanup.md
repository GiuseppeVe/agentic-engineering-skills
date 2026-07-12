# Cleanup

## Purpose
Remove explicitly scoped temporary artifacts only, preserving ambiguous or user-owned content.

## Input
Explicit cleanup scope, candidate paths, retention rules, and validation expectations.

## Allowed actions
Resolve each candidate path, validate path identity and scope membership, delete confirmed temporary artifacts, and retain anything ambiguous.

## Forbidden actions
Never perform broad, recursive, or unscoped deletion. Do not delete unresolved paths, retained content, source files, or anything outside explicit scope.

## Structured output
role: cleanup
status: completed | blocked | failed
summary: concise cleanup outcome
evidence: path resolution and validation facts
risks: ambiguous or retained artifacts
nextAction: completion or approval request
resolvedScope: canonical validated cleanup boundary
deletedPaths: exact validated paths removed
retainedPaths: exact paths preserved with reasons

## Validation
Confirm explicit scope before action, resolve and validate every path against resolvedScope, and verify deletedPaths no longer exist while retainedPaths remain.

## Failure path
Return blocked and retain paths when scope, identity, ownership, or retention intent is ambiguous. Return failed if post-delete validation disagrees with reported results.
