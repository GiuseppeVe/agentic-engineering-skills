# Provenance

`manifests/skills.lock.json` is source of truth. The Caveman payload matches the Alfe unified skill apart from trailing-whitespace normalization in one reference; its upstream attribution and adaptation patch are preserved here and in the lock rather than inserted into its SKILL.md. `vendor` means byte-identical pinned upstream content; `adapted` means pinned ancestry plus stored patch and change notice; `original` means repository-authored MIT material with release commit and local hash.

| Skill | Status | Acquisition source |
| --- | --- | --- |
| `archify` | adapted | `tt-a1i/archify@208acba8d412335185b2056fedf54b3405df43fb` |
| `ask-matt` | adapted | `mattpocock/skills@4ae2317ddb22b046e26455e4f9c9b3aaaf62212d` |
| `brainstorming` | adapted | `obra/superpowers@d884ae04edebef577e82ff7c4e143debd0bbec99` |
| `caveman` | adapted | `JuliusBrussee/caveman@0574b85a19ab7b2b7f42cc3b3838e20f24ab85eb` |
| `cleaning-repo-with-knip` | original | Updated payload recorded in lock |
| `deslopping-cleanup` | original | GiuseppeVe-authored cleanup coordinator and supporting references; payload release recorded in lock |
| `coordinating-implementation-programs` | original | Owner-supplied Alfe skill; source file SHA-256 recorded in the source manifest, with no Alfe commit claimed. |
| `codebase-design` | adapted | `mattpocock/skills@391a2701dd948f94f56a39f7533f8eea9a859c87` |
| `domain-modeling` | adapted | `mattpocock/skills@391a2701dd948f94f56a39f7533f8eea9a859c87` |
| `grill-me` | adapted | `mattpocock/skills@391a2701dd948f94f56a39f7533f8eea9a859c87` |
| `grilling` | adapted | `mattpocock/skills@391a2701dd948f94f56a39f7533f8eea9a859c87` |
| `graphify` | adapted | `Graphify-Labs/graphify@a5957aa6ef51c9be8d054de9783d25046c187f3f` |
| `graphify-start` | original | `GiuseppeVe/alfe_AI_app@445bf4f655eaecc5fe530b2cc72b27bd1b414cea` (`.agents/skills/graphify-start/`) |
| `handoff` | adapted | `mattpocock/skills@4ae2317ddb22b046e26455e4f9c9b3aaaf62212d` |
| `orchestrating-gemini-workers` | original | `GiuseppeVe/alfe_AI_app@2a113cd1dfb10c879a44ce8e6115daea74c8cbc7` (`.agents/skills/orchestrating-gemini-workers/`); upstream provenance undocumented in Alfe |
| `how-to-use-codex` | original | GiuseppeVe-authored Codex prompting and model-guidance skill; release recorded in lock |
| `marketing-screenshots` | original | `GiuseppeVe/alfe_AI_app@2a113cd1dfb10c879a44ce8e6115daea74c8cbc7` (`.agents/skills/marketing-screenshots/`); upstream provenance undocumented in Alfe |
| `master-orchestrator` | original | Owner-supplied, untracked local Alfe snapshot; both host paths and exact source-file hashes recorded in the source manifest. No Alfe commit is claimed. |
| `mdx-to-html` | original | `GiuseppeVe/alfe_AI_app@2a113cd1dfb10c879a44ce8e6115daea74c8cbc7` (`.agents/skills/mdx-to-html/`); upstream provenance undocumented in Alfe |
| `impeccable` | adapted | `pbakaus/impeccable@6496f49a1ea0503ca130d7dd55508dd0d22aa86b` |
| `claude-implement` | original | GiuseppeVe-authored Claude Code workflow, packaged in `claude-skills/claude-implement/` for Claude-only discovery; release recorded in lock |
| `codex-implement` | original | Updated GiuseppeVe-authored Codex workflow; release recorded in lock |
| `improve-codebase-architecture` | adapted | `mattpocock/skills@391a2701dd948f94f56a39f7533f8eea9a859c87` |
| `learn-codebase` | adapted | `thedotmack/claude-mem@312d640b0188753acd92a1a82d95a84d5c7c43db` |
| `setup-goal` | original | `GiuseppeVe/alfe_AI_app@6028e13227a82206dcc3b8f3bd75b845585c2d1d` (`.agents/skills/setup-goal/`) |
| `setup-harness-evaluation` | original | `GiuseppeVe/alfe_AI_app@f7b6d200c34399fc19bc3106443e50dad685d934` (`.agents/skills/setup-harness-evaluation/`) |
| `setup-workflow-comparison` | original | `GiuseppeVe/alfe_AI_app@f7b6d200c34399fc19bc3106443e50dad685d934` (`.agents/skills/setup-workflow-comparison/`) |
| `sequential-task-orchestrator` | original | Universal coordinator and shared runtime protocol; payload hash and release recorded in lock |
| `retro` | adapted | `mattpocock/skills@4ae2317ddb22b046e26455e4f9c9b3aaaf62212d` |
| `simplify` | original | GiuseppeVe-authored behavior-preserving code cleanup skill; release recorded in lock after commit |
| `test-driven-development` | adapted | `obra/superpowers@d884ae04edebef577e82ff7c4e143debd0bbec99` |
| `to-spec` | adapted | `mattpocock/skills@391a2701dd948f94f56a39f7533f8eea9a859c87` |
| `ui-ux-pro-max` | adapted | `nextlevelbuilder/ui-ux-pro-max-skill@314307f156aeab0c6b567bbaa1ce4e7aabd5a636` |
| `wayfinder` | adapted | `mattpocock/skills@391a2701dd948f94f56a39f7533f8eea9a859c87` |
| `writing-for-agents` | original | `GiuseppeVe/alfe_AI_app@445bf4f655eaecc5fe530b2cc72b27bd1b414cea` (`.agents/skills/writing-for-agents/`) |
| `writing-plans` | adapted | `obra/superpowers@d884ae04edebef577e82ff7c4e143debd0bbec99` |

For repository-original imports from Alfe, `manifests/skill-sources.json` records the local acquisition path and the historical Alfe repository commit/path. Their lock `releaseCommit` records the payload commit, and `localSha256` records the complete packaged directory. Exact paths, hashes, patches, and legal-file mappings live in [lock manifest](../manifests/skills.lock.json). Licensing summary: [Third-Party Notices](../THIRD_PARTY_NOTICES.md).

Alfe source for these three skills does not document any earlier upstream origin; no upstream authorship or license lineage is inferred. The source `example-log.md` for `orchestrating-gemini-workers` is omitted from the package because its historical model/run results are project-specific and not portable evidence. `mdx-to-html` preserves both host activation contracts: Claude `disable-model-invocation: true` and Codex `allow_implicit_invocation: false`; `marketing-screenshots` and `orchestrating-gemini-workers` retain their source hosts’ implicit-invocation settings.


The `graphify` package combines the eight reference files under the pinned `graphify/skills/codex/` directory with its entrypoint from the sibling `graphify/skill-codex.md`; the patch records this composition and all local additions. `graphify-start` remains a separate Alfe-original router skill.

Claude-only acquisition uses the portable `pluginSkills` root (`AGENTIC_PLUGIN_ROOT`) with local path `claude-skills/claude-implement/`. The lock records its installed `payloadPath`; regeneration and verification preserve this path rather than restoring the skill to the shared Codex directory.

`master-orchestrator` was acquired from an owner-supplied local snapshot of Alfe, outside its Git index. The source manifest records SHA-256 for each file in both host variants and deliberately has no origin revision. Packaging combines Claude explicit-only frontmatter with Codex explicit-only metadata and adds a Wayfinder fallback for host-discovered or bundled plugin skills. The lock hash covers the complete packaged directory. Its `releaseCommit` identifies the repository commit containing this complete packaged payload.
