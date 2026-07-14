# Artifact contracts

## Contents

- `source-manifest.json` and reference probe
- `handoff-contract.json`
- Matrix and capture receipt
- `compatibility-map.md`
- `deviation-ledger.md`
- `validation-receipt.json`
- Cross-artifact invariants

Use v1 shapes exactly. Persist five artifacts under `docs/handoffs/<name>/`; keep extraction, screenshots, logs, and side receipts temporary/ignored.

## `source-manifest.json`

```json
{
  "schemaVersion": 1,
  "source": { "kind": "zip", "path": "<absolute>", "filename": "handoff.zip", "size": 1, "sha256": "<64 hex>" },
  "extraction": { "root": "<absolute temp path>", "entries": 1, "zipSlipRejected": 0 },
  "entrypoints": [{ "path": "index.html", "type": "html" }],
  "runtime": { "kind": "static|package", "indicators": [], "packageScripts": {} },
  "inventory": {
    "entries": [{ "path": "index.html", "type": "html", "size": 1, "sha256": "<64 hex>" }],
    "stylesheets": [], "scripts": [], "assets": [], "fonts": [],
    "dependencies": [{ "name": "<name>", "version": "<range>", "scope": "runtime|development" }],
    "cdns": [], "networkRequests": []
  }
}
```

Arrays/objects may be empty, never absent. Archive paths use forward slashes. Hash original bytes. Any rejected traversal or unresolved entrypoint blocks intake.

Temporary reference probe receipt:

```json
{
  "schemaVersion": 1, "command": "<command>", "status": "HEALTHY|FAILED",
  "failureClass": null, "url": "http://127.0.0.1:<port>/index.html",
  "root": "<absolute>", "entry": "index.html",
  "health": { "httpStatus": 200, "contentType": "text/html" },
  "cleanup": { "status": "CLOSED|FAILED" }, "error": null
}
```

Only `HEALTHY`, HTTP 2xx/3xx, and `CLOSED` permit target work. Else `SOURCE_UNRUNNABLE`.

## `handoff-contract.json`

```json
{
  "schemaVersion": 1, "name": "<slug>", "sourceSha256": "<manifest SHA>",
  "source": { "manifest": "<path>", "sha256": "<manifest SHA>" },
  "observables": {
    "copy": ["<exact visible string>"], "assets": ["<source-relative path>"],
    "initialStates": ["default"],
    "interactions": [{ "id": "open-drawer", "action": "click row", "result": "drawer opens" }],
    "breakpoints": [760], "motion": ["drawer-slide"], "reducedMotion": true
  },
  "matrix": {
    "routes": ["/"], "languages": ["en"],
    "viewports": [{ "name": "mobile", "width": 390, "height": 844 }],
    "states": ["default", "drawer"],
    "cells": [{ "id": "root__en__mobile__default", "route": "/", "language": "en", "viewport": { "name": "mobile", "width": 390, "height": 844 }, "state": "default" }]
  },
  "setup": { "reference": "<runner setup>", "candidate": "<runner setup>" },
  "completion": { "complete": true, "expectedCells": 2, "missingFields": [] }
}
```

All fields required. Unknown route, copy/data, asset/font, default, interaction, breakpoint, visibility, geometry, motion, or reduced-motion behavior sets `complete:false`, lists field paths in `missingFields`, classifies `CONTRACT_UNKNOWN`, and blocks port.

## Matrix and capture receipt

`matrix.cells` is complete Cartesian product `routes × languages × viewports × states`. Cell `id` is stable, unique, and consumed verbatim by both sides. Both sides use identical route, setup, replay, waits, dimensions, locale, reduced-motion setting, capture bounds, and filename.

```json
{
  "schemaVersion": 1, "kind": "handoff-capture-receipt",
  "status": "COMPLETE|INCOMPLETE", "failureClass": null, "side": "reference|candidate",
  "candidateSha": "<exact candidate SHA for candidate side; null for reference>",
  "sourceSha256": "<sha>", "contractSha256": "<sha>", "setup": {},
  "summary": { "expected": 2, "captured": 2, "missing": 0, "timeouts": 0, "runnerFailures": 0 },
  "cells": [{
    "id": "root__en__mobile__default",
    "setup": { "route": "/", "language": "en", "viewport": { "name": "mobile", "width": 390, "height": 844 }, "state": "default" },
    "status": "CAPTURED|MISSING|TIMEOUT|RUNNER_FAILED", "outputPath": "<absolute PNG or null>",
    "sha256": "<hash or null>", "bytes": 1, "runner": {}
  }]
}
```

Exactly one record per expected key, including failures. Missing/error/timeout forces `INCOMPLETE`, `INCOMPLETE_MATRIX`, and nonzero exit.

## `compatibility-map.md`

Required headings: `Routing and callbacks`, `Controlled i18n`, `Component signatures`, `Allowed dependencies and network`, `CSS scope`, `Security`, `Accessibility`, `Lifecycle and cleanup`. Each contains:

```markdown
| Reference contract | Target contract | Boundary adapter | Observable preserved | Verification | Status |
|---|---|---|---|---|---|
| <evidence> | <constraint> | <seam-only change> | yes/no | <gate/cells> | MAPPED/APP_BOUNDARY/BLOCKED |
```

`Observable preserved:no` requires ledger entry.

## `deviation-ledger.md`

```markdown
| ID | Class | Contract evidence | Constraint/defect | Proposed deviation | Observable impact | Affected cells/gates | Implementer | Independent approver | Approval | Approved SHA |
|---|---|---|---|---|---|---|---|---|---|---|
| DEV-001 | APP_BOUNDARY | <evidence> | <constraint> | <proposal> | <impact> | <keys> | <id> | <id> | PENDING/APPROVED/REJECTED | <sha> |
```

Only `APP_BOUNDARY` and `REFERENCE_DEFECT` enter ledger. Implementer cannot approve. Approval binds exact row, source SHA, candidate SHA, and affected cells; relevant change invalidates it.

## `validation-receipt.json`

```json
{
  "schemaVersion": 1, "kind": "handoff-validation-receipt",
  "status": "PASS|FAIL", "failureClass": null,
  "policy": { "comparison": "EXACT_SHA256", "geometryMasksAllowed": false, "materialThresholdAllowed": false },
  "sourceSha256": "<sha>",
  "candidateSha": "<exact candidate SHA>",
  "summary": { "expected": 2, "exactMatches": 2, "missing": 0, "setupMismatches": 0, "hashMismatches": 0 },
  "failures": []
}
```

Missing/setup mismatch classifies `INCOMPLETE_MATRIX`; exact-hash mismatch classifies `IMPORT_DEFECT`. Integrated gate/review/deviation evidence wraps this mechanical receipt in controller state; it never rewrites comparator policy.

## Invariants

- Source SHA matches manifest, contract, side receipts, and validation receipt.
- Reference/candidate ordered cell IDs and setup match; expected count equals `completion.expectedCells == matrix.cells.length`.
- Mechanical `PASS` requires every expected cell present with exact SHA-256. Controller completion additionally requires all gates pass and both reviews approve same candidate SHA.
- Non-exact pixels pass only after direct `RASTER_NOISE` review. No geometry masks or material threshold.
- Candidate, spec, quality, approved-deviation, and validated `HEAD` SHAs match.
- Implementer performs no Git. Controller stages exact owned paths and commits one slice at a time.
