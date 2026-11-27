# Third-Party Notices

Repository-original material is licensed under the root MIT license. Third-party code and assets retain their applicable upstream terms; copied LICENSE and NOTICE files live under `plugins/agentic-engineering-skills/licenses/`.

**Archify is not wholly MIT-licensed.** Its upstream MIT license covers Archify's own code and content only. Bundled brand artwork and fonts retain their separate terms, including CC-BY-NC-SA-4.0 for Vue artwork, CC-BY-SA terms for Jenkins and Rust artwork, and SIL Open Font License 1.1 for JetBrains Mono. These restrictions remain applicable to the bundled assets; see the [pinned Archify third-party notice](plugins/agentic-engineering-skills/licenses/tt-a1i-archify-THIRD_PARTY_NOTICES) for recorded sources, terms, and trademark limits.

A supplementary modification notice at `plugins/agentic-engineering-skills/licenses/pbakaus-impeccable-ADAPTATIONS-NOTICE` records the adapted command metadata, the byte-identical upstream release VERSION and the compressed font-index representation.

Impeccable's retained upstream NOTICE attributes `reference/ios.md` and `reference/android.md` to [ehmo/platform-design-skills](https://github.com/ehmo/platform-design-skills), under MIT. Retain `plugins/agentic-engineering-skills/licenses/ehmo-platform-design-skills-LICENSE` when redistributing those references. The license text was verified at commit `dc2be825d8b439caea78e9eaa8fb3ac23b0ff3e9`; the revision of the underlying reference content is not established. See `manifests/supplemental-licenses.json`.

## Repository-original skills

`deslopping-cleanup`, its specialist-routing and run-report references, and the
pipeline graphic are original GiuseppeVe material under the repository MIT
license. Specialist names are references, not additional vendor payloads. See
[dependency availability and license review](docs/deslopping-cleanup.md) for scope.
The existing `cleaning-repo-with-knip` runbook is also repository-original MIT
material; its software and helper dependencies are not bundled by this addition.

`plan-implement`, `setup-goal`, `setup-harness-evaluation`, `setup-workflow-comparison`, `simplify`, and `writing-for-agents` are repository-original material imported from the source project and distributed under the repository root [MIT license](LICENSE). Their available provenance is recorded in [provenance](docs/provenance.md).

`marketing-screenshots` and `mdx-to-html` are owner-supplied originals and distributed under the destination repository root [MIT license](LICENSE). The source does not document earlier upstream provenance for these skills, so no upstream authorship or license lineage is asserted.

| Skill | Source | Revision | Status | Copyright holder | License | Legal files | Modification notice |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `archify` | [tt-a1i/archify](https://github.com/tt-a1i/archify) | `208acba8d412335185b2056fedf54b3405df43fb` | adapted | tt-a1i; Cocoon AI | MIT for Archify code; separately licensed assets per notice | `plugins/agentic-engineering-skills/licenses/tt-a1i-archify-LICENSE`<br>`plugins/agentic-engineering-skills/licenses/tt-a1i-archify-THIRD_PARTY_NOTICES` | Packaged skill and supporting assets; retained upstream third-party notices with asset-specific terms. |
| `brainstorming` | [obra/superpowers](https://github.com/obra/superpowers) | `d884ae04edebef577e82ff7c4e143debd0bbec99` | adapted | Jesse Vincent | MIT | `plugins/agentic-engineering-skills/licenses/obra-superpowers-LICENSE` | Adapted for cross-host Agent Skills distribution. |
| `caveman` | [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) | `0574b85a19ab7b2b7f42cc3b3838e20f24ab85eb` | adapted | Julius Brussee | MIT | `plugins/agentic-engineering-skills/licenses/JuliusBrussee-caveman-0574b85-LICENSE` | Merged local Caveman rules with upstream ASD-STE100 clarity guidance for cross-host distribution; removed Wenyan variants. Requires explicit invocation on both hosts. |
| `codebase-design` | [mattpocock/skills](https://github.com/mattpocock/skills) | `391a2701dd948f94f56a39f7533f8eea9a859c87` | adapted | Matt Pocock | MIT | `plugins/agentic-engineering-skills/licenses/mattpocock-skills-LICENSE` | Added host-aligned guidance and host metadata. |
| `domain-modeling` | [mattpocock/skills](https://github.com/mattpocock/skills) | `391a2701dd948f94f56a39f7533f8eea9a859c87` | adapted | Matt Pocock | MIT | `plugins/agentic-engineering-skills/licenses/mattpocock-skills-LICENSE` | Added host-aligned glossary and ADR guidance and host metadata. |
| `grilling` | [mattpocock/skills](https://github.com/mattpocock/skills) | `391a2701dd948f94f56a39f7533f8eea9a859c87` | adapted | Matt Pocock | MIT | `plugins/agentic-engineering-skills/licenses/mattpocock-skills-LICENSE` | Added host metadata and host-aligned review guidance. |
| `graphify` | [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) | `a5957aa6ef51c9be8d054de9783d25046c187f3f` | adapted | Safi Shamsi and Graphify contributors | Apache-2.0; MIT for portions retained under prior license | `plugins/agentic-engineering-skills/licenses/Graphify-Labs-graphify-LICENSE`<br>`plugins/agentic-engineering-skills/licenses/Graphify-Labs-graphify-LICENSE-MIT`<br>`plugins/agentic-engineering-skills/licenses/Graphify-Labs-graphify-NOTICE` | Composed from the pinned Codex references and sibling `skill-codex.md`; the new entrypoint routes through project protocols and the build pipeline lives in a reference. |
| `handoff` | [mattpocock/skills](https://github.com/mattpocock/skills) | `4ae2317ddb22b046e26455e4f9c9b3aaaf62212d` | adapted | Matt Pocock | MIT | `plugins/agentic-engineering-skills/licenses/mattpocock-skills-4ae2317-LICENSE` | Adapted portable host metadata and requires explicit invocation on both hosts. |
| `deslopping-cleanup` | Repository-original | — | original | GiuseppeVe | MIT | `LICENSE` and skill-local `LICENSE` | Original cleanup coordinator; external specialists are referenced, not vendored. |
| `impeccable` | [pbakaus/impeccable](https://github.com/pbakaus/impeccable) | `6496f49a1ea0503ca130d7dd55508dd0d22aa86b` | adapted | Paulo Bakaus | Apache-2.0 | `plugins/agentic-engineering-skills/licenses/pbakaus-impeccable-LICENSE`<br>`plugins/agentic-engineering-skills/licenses/pbakaus-impeccable-NOTICE` | Packaged supporting profiles and scripts. Requires explicit invocation on both hosts. |
| `improve-codebase-architecture` | [mattpocock/skills](https://github.com/mattpocock/skills) | `391a2701dd948f94f56a39f7533f8eea9a859c87` | adapted | Matt Pocock | MIT | `plugins/agentic-engineering-skills/licenses/mattpocock-skills-LICENSE` | Enables Codex model invocation for plugin validation and discovery. |
| `master-orchestrator` | Owner-supplied local snapshot | Untracked; source-file hashes recorded | original | GiuseppeVe | MIT | `LICENSE` | Combined explicit host metadata and added portable Wayfinder discovery. |
| `plan-implement` | Repository-original | — | original | GiuseppeVe | MIT | `LICENSE` | Original skill; coordinates approved implementation plans with slice-implementer subagents, L1–L3 verification, and high-risk review checkpoints. |
| `retro` | [mattpocock/skills](https://github.com/mattpocock/skills) | `4ae2317ddb22b046e26455e4f9c9b3aaaf62212d` | adapted | Matt Pocock | MIT | `plugins/agentic-engineering-skills/licenses/mattpocock-skills-4ae2317-LICENSE` | Adapted host metadata and added deterministic check promotion and operational metric reflection. |
| `simplify` | Repository-original | — | original | GiuseppeVe | MIT | `LICENSE` | Original skill; applies behavior-preserving code quality cleanups. |
| `test-driven-development` | [obra/superpowers](https://github.com/obra/superpowers) | `d884ae04edebef577e82ff7c4e143debd0bbec99` | adapted | Jesse Vincent | MIT | `plugins/agentic-engineering-skills/licenses/obra-superpowers-LICENSE` | Condensed cross-host TDD, bug-reproduction, modern verification oracles, and coverage-gap guidance; patch records changes. |
| `to-spec` | [mattpocock/skills](https://github.com/mattpocock/skills) | `391a2701dd948f94f56a39f7533f8eea9a859c87` | adapted | Matt Pocock | MIT | `plugins/agentic-engineering-skills/licenses/mattpocock-skills-LICENSE` | Enables model invocation on both hosts and focuses the spec on key scenarios. |
| `wayfinder` | [mattpocock/skills](https://github.com/mattpocock/skills) | `391a2701dd948f94f56a39f7533f8eea9a859c87` | adapted | Matt Pocock | MIT | `plugins/agentic-engineering-skills/licenses/mattpocock-skills-LICENSE` | Uses scoped research subagents and throwaway prototypes across hosts. |
| `writing-plans` | [obra/superpowers](https://github.com/obra/superpowers) | `d884ae04edebef577e82ff7c4e143debd0bbec99` | adapted | Jesse Vincent | MIT | `plugins/agentic-engineering-skills/licenses/obra-superpowers-LICENSE` | Adapted for cross-host Agent Skills distribution with slice grouping, risk tags, and `plan-implement` handoff. |

`master-orchestrator` is GiuseppeVe-authored material supplied as an untracked local snapshot and distributed under the root MIT license. Source paths and exact file hashes are recorded in [provenance](docs/provenance.md) and the source manifest; no source-project Git revision is asserted.

## Apache NOTICE

The exact pinned `thedotmack/claude-mem` NOTICE is distributed at `plugins/agentic-engineering-skills/licenses/thedotmack-claude-mem-NOTICE`.
