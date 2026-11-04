---
name: test-driven-development
description: Use when implementing features, fixing bugs, changing behavior, or refactoring tested code.
---

# Test-Driven Development (TDD)

> Adaptation: obra/superpowers condensed cross-host TDD guidance with behavioral coverage-gap assessment.

Write a behavioral test, observe its expected failure, implement the smallest change, then refactor while green. A passing test alone does not prove it can detect the bug.

## Scope

Use this cycle for new behavior and bug fixes. For refactoring, establish existing tests are green; add coverage for unprotected behavior before restructuring.

Follow applicable project and task instructions when choosing verification. Prototypes, generated code, configuration, and trivial edits need appropriate validation, not automatic test scaffolding or a separate permission request. Time pressure and manual checks do not replace a meaningful regression test for changed behavior.

When delegating TDD work, start each subagent with a fresh context window and provide the objective, relevant references, constraints, and expected output explicitly.

## Coverage gaps

Map changed behavior and acceptance criteria to existing behavioral tests, using the request and available specifications. Check relevant success, boundary, and failure paths; assess whether tests exercise production behavior and detect realistic defects. Prioritize material gaps by impact, reuse existing coverage, and add focused tests when warranted. For existing correct behavior, use safe regression sensitivity evidence when needed; report missing evidence and unresolved gaps.

## RED → GREEN → REFACTOR

1. **Specify.** Identify the observable contract and the realistic production defect the test should catch. Derive expected values independently of implementation helpers or constants.
2. **RED.** Write one focused test with a behavior-based name. Exercise real code; use doubles at external boundaries when necessary. Read [writing-good-tests.md](writing-good-tests.md) for test design and [testing-anti-patterns.md](testing-anti-patterns.md) when writing or changing tests, especially when using mocks or test utilities.
3. **Verify RED.** Run the smallest relevant test command from the project. Observe the assertion fail because behavior is missing or wrong. A syntax, import, fixture, dependency, or infrastructure error is not behavioral RED: repair the harness and rerun. A test passing immediately needs a relevant missing case or verified regression sensitivity; do not count it as observed RED.
4. **GREEN.** Implement only what the failing test requires. Run it again; fix production code rather than weakening a valid expectation. Run affected existing checks and resolve failures introduced by the change. Disclose unrelated failures and blockers.
5. **REFACTOR.** Improve structure without changing behavior. Rerun affected checks; add the next behavior through another verified RED.

## Meaningful test example

Contract: at most three total attempts; stop after success.

```typescript
test('succeeds on third attempt without another call', async () => {
  let attempts = 0;
  const result = await retryOperation(async () => {
    attempts++;
    if (attempts < 3) throw new Error('temporary');
    return 'saved';
  });
  expect(result).toBe('saved');
  expect(attempts).toBe(3);
});
```

Also cover exhaustion separately. Assert outcomes and contract-relevant side effects, not mock existence or private structure. Keep test-only utilities outside production APIs.

## Recovery when implementation already exists

Preserve existing and user work. Establish requirements independently; add the missing behavioral tests. In an isolated copy or narrowly reversible change, reproduce pre-fix behavior or disable only the relevant change; observe expected failures, restore, and rerun green. Never delete unrelated work or apply a blanket reset to recover process order.

Report this as regression verification, not a claim that the original implementation followed test-first order. Resume verified RED before further behavior changes. If safe reproduction is unavailable, report the missing evidence.

## Common mistakes

| Temptation | Required response |
|---|---|
| Tests afterward or manual checks prove TDD | Establish regression sensitivity; report actual sequence. |
| Any failing command counts as RED | Reach the intended behavioral assertion. |
| Assert the imported constant or mock output | Use independently specified observable behavior. |
| Test every method for coverage | Cover meaningful contracts and boundary cases; reuse existing coverage. |

## Completion evidence

Report relevant contracts, observed RED failures, GREEN commands/results, affected checks, and remaining gaps. Tests should detect realistic wrong branches, missing side effects, boundary violations, and error outcomes. Distinguish passed, failed, and not run; never label missing verification complete.
