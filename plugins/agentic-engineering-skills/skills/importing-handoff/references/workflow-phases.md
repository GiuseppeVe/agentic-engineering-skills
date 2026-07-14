# Reference-first workflow

Controller owns state, Git, receipts, and gates. Implementers own assigned files and never run Git. Internal structure may change; observable output may not.

## Controller state

Persist gitignored `.importing-handoff-state.json` with: `schemaVersion`, `phase`, `worktreePath`, `sourcePath`, `sourceSha256`, `artifactDir`, `implementationBaseSha`, `candidateSha`, exact `implementationFiles`, per-slice `{id, observable, ownedFiles, status, commitSha, specApprovedSha, qualityApprovedSha, validationReceipt}`, `deviations`, `integratedGates`, `validatedHeadSha`, and `publicationGate` (`LOCKED|PENDING_USER|LOCALHOST_APPROVED`). Update atomically after each phase/review/receipt. Any implementation change invalidates affected receipts, both reviews, integrated gates, validated SHA, and localhost approval.

## Phases

1. **Immutable intake.** SHA-256 original bytes; extract to unique temporary directory with traversal rejection; inventory entrypoint/runtime/assets/fonts/dependencies/CDNs/network; write manifest; never edit source/extraction.
2. **Runnable reference.** Start isolated loopback server, health/load/behavior check, then prove cleanup. `SOURCE_UNRUNNABLE` stops before target edits.
3. **Contract.** Extract routes, viewports, locales, exact copy/data/assets, defaults, interactions, breakpoints, visibility, geometry, scroll/hover/input, motion, reduced motion, and complete matrix/replay. Unknown required field is `CONTRACT_UNKNOWN`; stop.
4. **Compatibility map.** Read target first. Map routing/callbacks, i18n, signatures, dependencies/network, CSS, security, a11y, lifecycle/cleanup. Adapt seams only. Conflict becomes `APP_BOUNDARY`, never silent output change.
5. **Observable slices.** One complete screen/state family at a time. Assign explicit owned files and cells. Start from complete reference behavior; no placeholder, simplified, sampled, “reference-like,” or deferred observable version. Implementer follows TDD, edits only owned files, reports evidence, runs no Git.
6. **Exact commit and dual review.** Controller verifies changed paths equal owned paths, runs `git add <exact paths>`, commits one slice, then spec review and quality review serially on same SHA. Assert reviewer did not move `HEAD` or dirty tree. Issues return to no-Git implementer; controller stages exact paths, amends, and reruns spec then quality on new SHA. Advance only with both approvals on same SHA.
7. **Differential loop.** Capture reference, capture candidate with same matrix/name/setup, prove both complete, compare every cell, replay interactions, classify, fix, repeat. Slice cannot advance with material difference. Missing/timeout is `INCOMPLETE_MATRIX`. `RASTER_NOISE` is antialias/raster only after inspection; never mask geometry or raise material tolerance.
8. **Integrated gates.** Run typecheck, lint, unit/integration, a11y, full responsive/i18n, reduced motion, build, application gates, and full differential matrix. Any fix returns through affected slice, dual review, differential, then all gates. Set `validatedHeadSha` only when everything covers same SHA.
9. **User localhost gate.** Only after gates: verify clean exact scope, `HEAD == validatedHeadSha`, complete receipt, no pending deviations; start localhost and present finite inspection list. Record user decision. Stop before push, PR, merge, deploy, remote cleanup, or publication. Localhost approval is not publication authorization.

## Resume

Read state first. Verify source SHA, `HEAD`, cleanliness, artifacts, receipt hashes, scope, and review SHAs. Missing/stale/contradictory/empty scope invalidates approval; return to earliest affected phase. Test count or prior conversation never proves fidelity.
