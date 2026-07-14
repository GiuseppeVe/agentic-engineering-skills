# Failure policy

Absence of evidence is failure, not low risk.

## Taxonomy

| Class | Predicate | Action |
|---|---|---|
| `SOURCE_UNRUNNABLE` | Reference cannot start/load/exercise/cleanly stop | Repair runner or obtain runnable source; stop before edits |
| `CONTRACT_UNKNOWN` | Required observable cannot be determined | Investigate; stop port |
| `APP_BOUNDARY` | Target contract conflicts with preserved output | Adapt seam, else ledger + independent approval |
| `IMPORT_DEFECT` | Candidate materially differs from valid reference | Fix and rerun matrix |
| `REFERENCE_DEFECT` | Immutable runnable reference reproducibly contains defect | Ledger + independent approval; never silently improve |
| `RASTER_NOISE` | Direct inspection proves antialias/raster-only difference | Record evidence; may pass cell |
| `INCOMPLETE_MATRIX` | Expected capture missing/errors/times out or key sets differ | Rerun complete matrix; always block |

Classify completeness first, then reference validity, boundary, and import fidelity. Only `APP_BOUNDARY`/`REFERENCE_DEFECT` enter ledger. Implementer cannot approve. Missing reviewer/evidence, timeout, ambiguous verdict, or SHA drift remains `PENDING`.

## Comparator policy

Same matrix, keys, setup, replay, viewport, locale, waits, bounds, and names on both sides. Missing/error/timeout is `INCOMPLETE_MATRIX`, nonzero. Copy, data, color, visibility, geometry, breakpoint, state, interaction, or motion difference is material. No geometry mask or material threshold. Non-exact pixels become `RASTER_NOISE` only after direct inspection. Unit/DOM/type/lint/build never substitutes for differential evidence.

## Rationalizations

| Rationalization | Response |
|---|---|
| "Stakeholder approved prototype/target, so deviation is approved." | Approval of inputs is not approval of exact deviation row. Keep `PENDING` until independent approver names row, source SHA, candidate SHA, and cells. |
| "No commit authorized; use `uncommitted` as approved SHA." | No exact candidate SHA means no approval. Keep ledger `PENDING` and verdict incomplete. |
| “Deadline: ship best usable version.” | Deadline changes verdict to `INCOMPLETE`, not contract. No simplified version. |
| “Browser/capture unavailable.” | Required evidence missing: `INCOMPLETE_MATRIX`. |
| “Structural/unit tests pass.” | Target mechanics are not observable equivalence. |
| “Interaction conflicts with callback, remove it.” | Preserve interaction, adapt seam; else `APP_BOUNDARY` + independent approval. |
| “Responsive appearance is residual low risk.” | Uncaptured viewport is incomplete. |
| “Many tests green; visual fixes later.” | Test count does not establish contract/fidelity. |
| “State says complete.” | Empty scope, stale SHA, missing receipt/review invalidates state. |
| “Full matrix expensive; sample cells.” | Every contracted cell remains required. |
| “Raise tolerance/mask unstable area.” | Fix determinism or prove raster-only noise. |
| “Reference bug obvious; improve it.” | `REFERENCE_DEFECT` needs evidence, ledger, independent approval. |

## Red flags — stop

- Target edit before healthy reference/complete contract
- Placeholder, approximation, simplified/reference-like rewrite
- Different matrix names/setup/waits/bounds between sides
- Sampled matrix presented as complete
- Missing/timeout cell with `PASS`
- Observable deleted for route/callback/i18n/CSS/lifecycle boundary
- Implementer approves deviation or runs Git
- Approval inferred from role/brief, same-person reviewer, or non-SHA value such as `uncommitted`
- Broad staging, mixed slice, or out-of-scope path
- Spec/quality SHAs differ or approval retained after fix
- Localhost before gates; publication action after localhost gate

Any red flag invalidates completion; return to earliest affected phase.

## Quick reference

| Observation | Result |
|---|---|
| Reference fails | `SOURCE_UNRUNNABLE` / stop |
| Behavior unknown | `CONTRACT_UNKNOWN` / stop |
| Target conflict | `APP_BOUNDARY` / adapt or ledger |
| Candidate mismatch | `IMPORT_DEFECT` / fix |
| Reference flaw | `REFERENCE_DEFECT` / ledger |
| Antialias-only | `RASTER_NOISE` / document |
| Missing/timeout | `INCOMPLETE_MATRIX` / stop |
| Complete matrix + all gates/reviews same SHA | `PASS`, then localhost gate |

## Common mistakes

- Treating source as production-ready instead of behavioral evidence.
- Reimplementing from screenshots without running/replaying reference.
- Translating/replacing controlled copy during boundary adaptation.
- Capturing default only; omit hover/input/scroll/transition/reduced motion.
- Implementing all screens before first comparison instead of converging one slice.
- Persisting heavy screenshots/logs instead of five audit artifacts.
- Treating localhost approval as publication authorization.
