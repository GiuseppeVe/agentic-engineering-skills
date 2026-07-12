---
name: to-spec
description: Convert approved design context into a standalone reviewable specification.
upstream: https://github.com/mattpocock/skills
upstream_revision: 391a2701dd948f94f56a39f7533f8eea9a859c87
license: MIT
status: adapted
---

# To Spec

Upstream notice: derived from Matt Pocock Skills under MIT; see `licenses/MIT-mattpocock-skills.txt`. Repository changes: writes local MDX by default and never requires issue publication.

## When to use

Use after design decisions are approved and before detailed implementation planning.

## Inputs

Approved decisions, scope, non-goals, acceptance criteria, risks, and relevant evidence.

## Workflow

Write one standalone MDX document with problem, goal, user stories, architecture, decisions, testing, security, out-of-scope work, and related work. Preserve concrete choices; mark unresolved items explicitly.

## Validation

Readers can implement from the document without relying on chat history. Each requirement has an observable acceptance condition.

## Failure behavior

If a decision is missing, return to discovery. Do not invent product requirements.
