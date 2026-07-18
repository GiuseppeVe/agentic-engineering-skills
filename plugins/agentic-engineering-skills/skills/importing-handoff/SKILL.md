---
name: importing-handoff
description: Use when integrating a frontend web handoff supplied as a ZIP, executable prototype, Claude Design export, or visual reference into an existing application
---

# Importing Handoff

## Core rule

Treat source as visual/behavioral authority, not automatically production-ready code. Internal structure may change; observable copy, data, assets, geometry, colors, visibility, breakpoints, states, interactions, motion, and reduced motion may not.

**Do not edit target before immutable intake, healthy runnable reference, complete contract, and compatibility map exist.** Never begin with simplified, approximate, “reference-like,” or default-only implementation.

## Load required guidance

- Before work, read [workflow-phases.md](references/workflow-phases.md) and [failure-policy.md](references/failure-policy.md) completely.
- Before creating artifacts or matrix, read [contract-schema.md](references/contract-schema.md) completely.
- Before delegating or reviewing, read [reviewer-prompts.md](references/reviewer-prompts.md) completely.
- Reuse `codex-implement in Codex or claude-implement in Claude Code` controller, persistent state, owned-file isolation, controller-only Git, dual review, same-SHA validation, and user gate. This skill controls import ordering and fidelity evidence.

## Execute

1. Run `scripts/inspect-handoff.mjs` against immutable ZIP; persist `docs/handoffs/<name>/source-manifest.json`. Keep extraction temporary.
2. Run `scripts/run-reference.mjs probe`; stop with `SOURCE_UNRUNNABLE` unless health and cleanup pass.
3. Extract full observable contract; run `scripts/build-contract.mjs`. Unknown required behavior is `CONTRACT_UNKNOWN`, never an inference.
4. Write `compatibility-map.md` and `deviation-ledger.md`. Adapt application seams only. `APP_BOUNDARY` and `REFERENCE_DEFECT` require ledger plus independent approval; implementer cannot approve.
5. Import one complete screen/state family. Start from complete reference behavior, adapting only boundaries.
6. For every slice, run `scripts/capture-matrix.mjs` for reference and candidate with identical cell IDs/setup; run `scripts/compare-receipts.mjs`; replay interactions; fix and repeat before next slice.
7. Run typecheck, lint, unit/integration, a11y, responsive/i18n, reduced-motion, build, application gates, full matrix, spec review, and quality review on same candidate SHA.
8. Run `scripts/verify-import-scope.mjs`. Only then expose localhost for user inspection. Stop before push, PR, merge, deploy, remote cleanup, or publication.

## Non-negotiable gates

- Missing/error/timeout capture = `INCOMPLETE_MATRIX`, never mismatch or success.
- No sampled matrix, geometry mask, or material threshold. Classify `RASTER_NOISE` only after direct proof of raster/antialias-only difference.
- Implementer runs no Git. Controller stages exact owned paths and commits one slice. Any implementation change invalidates receipts and both reviews.
- Prototype/target approval is not deviation approval. Without explicit independent approval bound to exact row, source SHA, candidate SHA, and cells, ledger stays `PENDING`.
- Persist only five audit artifacts: `source-manifest.json`, `handoff-contract.json`, `compatibility-map.md`, `deviation-ledger.md`, `validation-receipt.json`. Ignore/temp extracted ZIPs, screenshots, logs, and side receipts.
