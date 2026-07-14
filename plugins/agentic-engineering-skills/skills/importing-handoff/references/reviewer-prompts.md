# Reviewer prompt contracts

Dispatch fresh, read-only reviewers with raw evidence. They never edit, mutate Git, approve own work, or weaken matrix/comparator.

## Contract reviewer

```text
Review observable contract from running frontend handoff.
Source SHA: {{SOURCE_SHA}}; manifest: {{MANIFEST}}; health receipt: {{HEALTH}};
contract: {{CONTRACT}}; runnable reference evidence: {{EVIDENCE}}.
Verify routes, locales, exact copy/data/assets, viewports, defaults, interactions,
breakpoints, visibility, geometry, motion/reduced motion, replay, and matrix keys.
Return exactly:
Status: APPROVED | ISSUES
Source-SHA: <sha>
Contract-complete: yes | no
Matrix: <expected>; <covered>; <missing keys>
Findings:
- [CONTRACT_UNKNOWN] <field/cell> — <evidence> — <action>
```

Missing behavior is `CONTRACT_UNKNOWN`, never inference.

## Spec reviewer

```text
Review committed observable slice against contract.
Candidate SHA: {{SHA}}; repository: {{REPO}}; files: {{FILES}};
slice/cells: {{SLICE}}; compatibility: {{MAP}}; approved deviations: {{DEVIATIONS}};
reference/candidate/validation receipts: {{RECEIPTS}}.
Verify exact copy, data, assets, default/state behavior, interactions, geometry,
responsive visibility, breakpoints, motion/reduced motion, lifecycle, identical
matrix keys/setup, complete receipts, and exact owned scope.
Return exactly:
Status: APPROVED | ISSUES
Reviewed-SHA: <sha>
Scope: <files>
Matrix: <expected>; <compared>; <missing>; <material differences>
Findings:
- [IMPORT_DEFECT|APP_BOUNDARY|INCOMPLETE_MATRIX] <location/cell> — <evidence> — <action>
```

## Quality reviewer

Dispatch only after spec approval.

```text
Review quality of spec-approved slice.
Candidate SHA: {{SHA}}; spec-approved SHA: {{SPEC_SHA}}; repository: {{REPO}};
files: {{FILES}}; target conventions/gates: {{CONVENTIONS}}; compatibility: {{MAP}}.
First require both SHAs equal. Assess correctness risk, maintainability, conventions,
dependency/network policy, CSS isolation, security, a11y, tests, cleanup/lifecycle.
Do not re-litigate contract or propose simplification.
Return exactly:
Status: APPROVED | ISSUES
Reviewed-SHA: <sha>
Scope: <files>
Findings:
- [BLOCKER|IMPORTANT] <file:line> — <evidence> — <action>
```

Any fix invalidates both reviews; rerun spec then quality on new SHA.

## Deviation reviewer

Reviewer must be independent from implementer.

```text
Review proposed deviation only; do not implement.
Row: {{ROW}}; class: {{APP_BOUNDARY_OR_REFERENCE_DEFECT}};
source SHA: {{SOURCE_SHA}}; candidate SHA: {{SHA}};
reference/constraint evidence: {{EVIDENCE}}; affected cells/gates: {{AFFECTED}};
alternatives attempted: {{ALTERNATIVES}}.
Test whether boundary adapter preserves output. For REFERENCE_DEFECT require
reproducible defect in immutable runnable reference.
Return exactly:
Status: APPROVED | REJECTED | NEEDS_EVIDENCE
Reviewed-source-SHA: <sha>
Reviewed-candidate-SHA: <sha>
Deviation-ID: <id>
Reason: <evidence>
Conditions: <none or bounded conditions>
Affected-cells: <exact keys>
```

Approval binds exact row/SHAs/cells. Timeout, missing field/evidence, same implementer/reviewer identity, or SHA drift leaves ledger `PENDING`.
Do not infer deviation approval from stakeholder authority, prototype approval, target contracts, deadline language, or a general instruction to ship. Only explicit independent approval of this exact deviation row and exact source/candidate SHAs counts; `uncommitted` is never a SHA.
