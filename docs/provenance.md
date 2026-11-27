# Provenance

`manifests/skills.lock.json` is source of truth. The Caveman payload matches owner-supplied unified skill apart from trailing-whitespace normalization in one reference; its upstream attribution and adaptation patch are preserved here and in the lock rather than inserted into its SKILL.md. `vendor` means byte-identical pinned upstream content; `adapted` means pinned ancestry plus stored patch and change notice; `original` means repository-authored MIT material with release commit and local hash.

| Skill | Status | Acquisition source |
| --- | --- | --- |
| `archify` | adapted | `tt-a1i/archify@208acba8d412335185b2056fedf54b3405df43fb` |
| `brainstorming` | adapted | `obra/superpowers@d884ae04edebef577e82ff7c4e143debd0bbec99` |
| `caveman` | adapted | `JuliusBrussee/caveman@0574b85a19ab7b2b7f42cc3b3838e20f24ab85eb` |
| `cleaning-repo-with-knip` | original | Updated payload recorded in lock |
| `development-process` | original | Owner-supplied general process rules and orchestration guide; payload release recorded in lock |
| `deslopping-cleanup` | original | GiuseppeVe-authored cleanup coordinator and supporting references; payload release recorded in lock |
| `coordinating-implementation-plans` | original | Owner-supplied skill; source file SHA-256 recorded in the source manifest, with no source commit claimed. |
| `codebase-design` | adapted | `mattpocock/skills@391a2701dd948f94f56a39f7533f8eea9a859c87` |
| `domain-modeling` | adapted | `mattpocock/skills@391a2701dd948f94f56a39f7533f8eea9a859c87` |
| `grilling` | adapted | `mattpocock/skills@391a2701dd948f94f56a39f7533f8eea9a859c87` |
| `graphify` | adapted | `Graphify-Labs/graphify@a5957aa6ef51c9be8d054de9783d25046c187f3f` |
| `handoff` | adapted | `mattpocock/skills@4ae2317ddb22b046e26455e4f9c9b3aaaf62212d` |
| `marketing-screenshots` | original | Owner-supplied original material; earlier upstream provenance undocumented |
| `master-orchestrator` | original | Owner-supplied, untracked local snapshot; both host paths and exact source-file hashes recorded in the source manifest. No source commit is claimed. |
| `mdx-to-html` | original | Owner-supplied original material; earlier upstream provenance undocumented |
| `impeccable` | adapted | `pbakaus/impeccable@6496f49a1ea0503ca130d7dd55508dd0d22aa86b`; `scripts/VERSION` is byte-identical to tag `skill-v4.8.0` at `414603bf14c7a344edb466bb1f85690c77ce8b7d` |
| `improve-codebase-architecture` | adapted | `mattpocock/skills@391a2701dd948f94f56a39f7533f8eea9a859c87` |
| `setup-goal` | original | Owner-supplied original material |
| `setup-harness-evaluation` | original | Owner-supplied original material |
| `setup-workflow-comparison` | original | Owner-supplied original material |
| `plan-implement` | original | Repository-original 2-level slice plan coordinator and runtime protocol; payload hash and release recorded in lock |
| `retro` | adapted | `mattpocock/skills@4ae2317ddb22b046e26455e4f9c9b3aaaf62212d` |
| `simplify` | original | GiuseppeVe-authored behavior-preserving code cleanup skill; release recorded in lock after commit |
| `test-driven-development` | adapted | `obra/superpowers@d884ae04edebef577e82ff7c4e143debd0bbec99` |
| `to-spec` | adapted | `mattpocock/skills@391a2701dd948f94f56a39f7533f8eea9a859c87` |
| `wayfinder` | adapted | `mattpocock/skills@391a2701dd948f94f56a39f7533f8eea9a859c87` |
| `writing-for-agents` | original | Owner-supplied original material |
| `writing-plans` | adapted | `obra/superpowers@d884ae04edebef577e82ff7c4e143debd0bbec99` |

For repository-original imports, `manifests/skill-sources.json` records the portable local acquisition root and path. Their lock `releaseCommit` records the payload commit, and `localSha256` records the complete packaged directory. Exact paths, hashes, patches, and legal-file mappings live in [lock manifest](../manifests/skills.lock.json). Licensing summary: [Third-Party Notices](../THIRD_PARTY_NOTICES.md).

For the owner-supplied originals `mdx-to-html` and `marketing-screenshots`, the source leaves earlier upstream provenance undocumented. Both require explicit invocation on Claude Code and Codex.


The `graphify` package combines the eight pinned references in `graphify/skills/codex/` with the build pipeline derived from the sibling `graphify/skill-codex.md`. The local entrypoint incorporates the repository-original protocol routing and links to the build reference. The patch records all local additions.

`plan-implement` replaces the earlier `plan-orchestrator` and `task-implement` skills and is distributed from the shared skill directory to both hosts; no host-specific implementation skill is shipped.

`master-orchestrator` was acquired from an owner-supplied local snapshot of the source project, outside its Git index. The source manifest records SHA-256 for each file in both host variants and deliberately has no origin revision. Packaging combines Claude explicit-only frontmatter with Codex explicit-only metadata and adds a Wayfinder fallback for host-discovered or bundled plugin skills. The lock hash covers the complete packaged directory. Its `releaseCommit` identifies the repository commit containing this complete packaged payload.
