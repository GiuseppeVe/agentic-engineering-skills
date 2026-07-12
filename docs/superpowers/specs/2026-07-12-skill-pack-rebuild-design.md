# Agentic Engineering Skills Pack Rebuild Design

**Date:** 2026-07-12

**Status:** Approved design, pending written-spec review

**Repository:** `GiuseppeVe/agentic-engineering-skills`

## Goal

Rebuild the repository as an installable, stable skill pack that expresses the
author's AI-engineering workflow. The README explains the workflow philosophy;
the repository distributes the exact skills needed to apply it and lets users
fork, modify, remove, or recombine them under the applicable licenses.

The supported installation targets are Codex and Claude Code. Other hosts may
consume the generic Agent Skills layout, but the repository does not claim
verified compatibility with them.

## Product Definition

The primary product is the skill pack, not an executable agent harness.

- The complete pack is the recommended and fully tested installation.
- Selective skill installation is an advanced path.
- The README is the short entry point for philosophy, workflow, installation,
  customization, compatibility, provenance, and licensing.
- Detailed workflow and customization material lives under `docs/`.
- Users may modify installed or forked copies. No proprietary override system
  is introduced.
- Vendored third-party skills are frozen. Upstream update automation is outside
  scope; the repository owner updates them manually only after testing the
  complete workflow.

## Non-Goals

- No TypeScript harness, runner, demo agents, mock orchestration runtime, or
  harness eval suite.
- No promise of plug-and-play support beyond Codex and Claude Code.
- No automatic upstream dependency updates, update bots, latest channel, or
  silent replacement of vendored skills.
- No newly invented substitute skills.
- No publication, merge, branch deletion, history rewrite, or repository
  visibility change without a separate explicit approval.

## Repository Architecture

```text
agentic-engineering-skills/
├── README.md
├── LICENSE
├── THIRD_PARTY_NOTICES.md
├── manifests/
│   └── skills.lock.json
├── .agents/
│   └── plugins/
│       └── marketplace.json
├── .claude-plugin/
│   └── marketplace.json
├── plugins/
│   └── agentic-engineering-skills/
│       ├── .codex-plugin/
│       │   └── plugin.json
│       ├── .claude-plugin/
│       │   └── plugin.json
│       ├── skills/
│       │   ├── brainstorming/
│       │   │   └── SKILL.md
│       │   └── <skill-name>/
│       │       └── SKILL.md
│       └── licenses/
├── docs/
│   ├── workflow.md
│   ├── customization.md
│   ├── compatibility.md
│   ├── provenance.md
│   └── selective-install.md
├── scripts/
└── tests/
```

`plugins/agentic-engineering-skills/` is the single installable payload.
Codex and Claude Code marketplaces point to that payload, whose `skills/`
directory is the canonical skill source. No host-specific skill copies exist.
Skill directories are flat for native discovery. Their `original`, `adapted`,
or `vendor` classification lives in `manifests/skills.lock.json`, not in the
filesystem path.

## Skill Acquisition Rule

No skill content may be invented for this rebuild.

1. Use the skill set available in the current local skill roots when the exact
   requested skill is present.
2. For a requested skill absent from active roots, use only an exact upstream
   source verified against the source documents and immutable revision.
3. The quarantined implementation branch may help locate a candidate, but its
   files and provenance are untrusted until independently verified.
4. If source, revision, path, copyright, or license cannot be verified, exclude
   the skill and report the failed gate.
5. Sanitization must be minimal, reviewable, and preserve the source skill's
   semantics. Every changed line requires a documented reason.

Sanitization may remove private paths, proprietary context, secrets, invalid
local assumptions, or unsupported host-specific wiring. It may adapt tool names
or capability descriptions only where needed for Codex and Claude Code. Any
such change makes the package `adapted`, not `vendor`.

## Approved Skill Inventory

The source specification requests exactly 19 skills.

### Matt Pocock Skills

1. `grill-me`
2. `grilling`
3. `wayfinder`
4. `to-spec`
5. `setup-matt-pocock-skills`
6. `improve-codebase-architecture`
7. `codebase-design`
8. `domain-modeling`

### Obra Superpowers

9. `brainstorming`
10. `writing-plans`
11. `writing-skills`
12. `test-driven-development`
13. `using-git-worktrees`

### Julius Brussee

14. `caveman`
15. `cavecrew`

### Ruflo

16. `swarm-orchestration`

### Claude Mem

17. `learn-codebase`

### Repository-Author Skills

18. `implementing-plans`
19. `cleaning-repo-with-knip`

Only these 19 skills are in scope. Companion files required by one of these
skills may be included, but must be declared as companion content rather than
additional skills.

## Package Classification

Every skill has exactly one classification.

### Original

- Independently authored by the repository owner.
- Covered by the repository MIT license.
- May disclose conceptual influences, but must not claim copied text as
  original.

### Vendor

- Byte-exact copy from a verified immutable upstream revision.
- No local edits, including formatting-only edits.
- Retains applicable copyright, license, notice, and required companion files.

### Adapted

- Derived from verified permissively licensed upstream material.
- Retains upstream copyright and license obligations.
- Carries a clear change notice and an auditable local diff.

## Provenance Manifest

Each skill entry records its name, package status, source repository, immutable
revision, upstream path, upstream SHA-256, local SHA-256, license, direct
dependencies, required companion files, and supported hosts.

That upstream tuple applies only to `vendor` and `adapted` entries. An
`original` entry records `sourceType: original`, its local SHA-256, applicable
repository license, and the release commit that first distributes it. It must
not claim a circular or fabricated upstream revision.

Verification must prove that the revision and path exist, the upstream hash
matches, vendor copies are byte-identical, adapted copies have a change notice,
required licenses are present, dependencies resolve, and human-readable
provenance agrees with the manifest.

## Licensing

Original repository material is licensed under MIT. The initial copyright
holder is the public repository owner name `GiuseppeVe`; the owner may replace
it with a legal name before publication.

The root license does not replace third-party licenses. The repository includes:

- `LICENSE` for original repository material;
- `THIRD_PARTY_NOTICES.md` with source, revision, package status, copyright,
  license, and modification status;
- complete applicable license and NOTICE files under `licenses/`;
- prominent modification notices for adapted Apache-2.0 material;
- license and notice preservation in selective installation instructions.

## Installation and Distribution

### Complete Pack

The complete pack is the supported path.

- Codex receives the shared payload through the repository's Codex marketplace.
- Claude Code receives that same payload through its marketplace entry.
- Both packages expose the same canonical inventory after every requested skill
  passes or fails the inclusion gate. The target inventory is all 19 approved
  skills; a failed legal or source-verification gate reduces both packages in
  the same way and must be reported before release.
- Installation documentation includes discovery and smoke-test commands.

### Selective Installation

Selective installation is documented as advanced use.

- Users choose individual skills manually.
- Required dependencies and license files must accompany selected skills.
- Documentation states which workflow stages are lost when skills are omitted.
- Arbitrary subsets are not claimed to preserve the complete workflow.

### Customization

Users may fork, clone, edit, remove, and redistribute skills under the
applicable licenses. Durable changes should be made in a source clone or fork,
not an internal plugin cache. Reinstallation must not silently overwrite local
changes; destructive replacement requires an explicit force action or user
confirmation.

## README Narrative

The README remains concise and follows this sequence:

1. Problem: coding agents often act before understanding intent and evidence.
2. Philosophy: `Understand -> Design -> Plan -> Implement -> Verify -> Review -> Clean`.
3. Principles: intent before code, bounded relevant context, verifiable plans,
   evidence over claims, risk-proportional tests, independent review, safe
   cleanup, and human control of irreversible actions.
4. Practical workflow: each phase and the skill that supports it.
5. Complete installation for Codex and Claude Code.
6. Advanced selective installation.
7. Fork-based customization.
8. Verified and generic compatibility boundaries.
9. Provenance and licensing.

Long explanations live in `docs/workflow.md`; the README must communicate the
value and adoption path within a few minutes.

## Verification and Release Gates

Tests verify product claims rather than headings or substring presence.

### Pack Integrity

- Valid `SKILL.md` structure and unique names.
- Existing references and resolvable dependencies without cycles.
- Identical skill inventory across Codex and Claude Code packaging.
- Complete-pack discovery of every included skill.

### Provenance and License Compliance

- Real immutable upstream revision and path.
- Verified hashes and byte-exact vendor copies.
- Change notices for adapted copies.
- Required license and NOTICE files.
- Agreement between technical manifest and human documentation.

### Compatibility

- Native manifest validation for Codex and Claude Code.
- Real discovery smoke tests on both supported hosts.
- Host-specific assumptions adapted or explicitly disclosed.
- No compatibility claim for an untested host.

### Public Audit

Audit only Git-tracked release files and reject realistic credentials, private
keys, environment files, personal paths, private URLs, proprietary material,
unresolved legal template text, logs, generated artifacts, and unexpectedly
large files.

### Required CI Order

```text
format/schema
-> pack integrity
-> provenance
-> license compliance
-> Codex validation
-> Claude Code validation
-> public audit
```

Manual release review remains required even when CI is green.

## Recovery Strategy

The existing `impl/agentic-harness-workflow` branch remains an untouched
quarantine reference. Rebuild work occurs on `codex/rebuild-skill-pack`, based
on clean `main` history.

The rebuild selectively imports only verified requested skills and approved
documentation. It removes the TypeScript harness, demo agents, mock runner,
artificial evals, cosmetic tests, and unrelated tooling. The dirty staged
documents in the original `main` worktree remain preserved.

After implementation and verification, the repository owner reviews the full
diff and evidence. Commit, push, pull request, merge, branch cleanup, and public
visibility are separately controlled actions.

## Acceptance Criteria

- Repository contains no TypeScript harness or runtime demo.
- Exactly the approved 19 skills are considered; every included skill passes
  source and license gates, and every excluded skill has a recorded reason.
- No skill is invented.
- Complete Codex and Claude Code installations use the same canonical skill
  content and pass real discovery smoke tests.
- README accurately explains philosophy, workflow, installation,
  customization, compatibility, provenance, and licensing.
- MIT license and third-party notices are complete and non-misleading.
- No upstream update automation exists.
- All required validation and public-audit gates pass.
- No publication or destructive Git action occurs without explicit approval.
