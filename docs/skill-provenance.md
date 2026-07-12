# Skill and Tool Provenance

This repository imports workflow material deliberately. A public repository, plugin cache, or marketplace listing is not permission by itself. Before a file is copied, its source revision is pinned in `skills/sources.lock.json`; the relevant license and notice are retained.

## Packaging Rules

| Status | Destination | Rule |
| --- | --- | --- |
| `vendored` | `skills/vendor/` | Copy upstream source and required companion files from a pinned revision without obscuring upstream copyright or license. |
| `adapted` | `skills/adapted/` | Start from a pinned permissive upstream source, preserve its notice, and document repository-author changes. |
| `original` | `skills/original/` | Repository-author material sanitized for public release; no proprietary project content. |
| `external-tool` | Not vendored | Installed separately or provided by host; documentation records purpose and license. |

The root `LICENSE` covers original repository material. It does not replace third-party notices.

## Workflow Skills

| Skill | Package status | Repository-author contribution | Upstream source | License |
| --- | --- | --- | --- | --- |
| `grill-me` + `grilling` | Vendored | None planned. | `mattpocock/skills` | MIT |
| `wayfinder` | Adapted | Modified by repository author. | `mattpocock/skills` | MIT |
| `to-spec` | Adapted | Modified by repository author. | `mattpocock/skills` | MIT |
| `setup-matt-pocock-skills` templates | Vendored | Local-first tracker configuration only. | `mattpocock/skills` | MIT |
| `improve-codebase-architecture` | Vendored | Use clean upstream edition. | `mattpocock/skills` | MIT |
| `codebase-design` | Vendored | None planned. | `mattpocock/skills` | MIT |
| `domain-modeling` | Vendored | None planned. | `mattpocock/skills` | MIT |
| `brainstorming` | Adapted | Modified by repository author. | `obra/superpowers` | MIT |
| `writing-plans` | Adapted | Modified by repository author. | `obra/superpowers` | MIT |
| `writing-skills` | Vendored | None planned. | `obra/superpowers` | MIT |
| `test-driven-development` | Vendored | None planned. | `obra/superpowers` | MIT |
| `using-git-worktrees` | Vendored | None planned. | `obra/superpowers` | MIT |
| `caveman` | Vendored | None planned. | `JuliusBrussee/caveman` | MIT |
| `cavecrew` | Adapted | Rewrite host-specific role names into seven public profiles. | `JuliusBrussee/caveman` | MIT |
| `swarm-orchestration` | Adapted | Replace host CLI commands with public capability contracts and deterministic mock support. | `ruvnet/ruflo` | MIT |
| `learn-codebase` | Vendored | Add bounded-scope guidance only. | `thedotmack/claude-mem` | Apache-2.0 + NOTICE |
| `implementing-plans` | Original | Author-created; sanitize host-specific wiring and release only public workflow content. | None | Repository MIT |
| `cleaning-repo-with-knip` | Original | Local workflow material, sanitized for public release. | None | Repository MIT |

`implementing-plans` is original author-created material. `wayfinder`, `to-spec`, `writing-plans`, and `brainstorming` are author-modified permissive-source material. This distinction remains visible in the lockfile and each adapted skill header.

## Source Repositories

- [Matt Pocock skills — MIT](https://github.com/mattpocock/skills/blob/main/LICENSE)
- [Obra Superpowers — MIT](https://github.com/obra/superpowers/blob/main/LICENSE)
- [Julius Brussee Caveman — MIT](https://github.com/JuliusBrussee/caveman/blob/main/LICENSE)
- [Ruflo — MIT](https://github.com/ruvnet/ruflo/blob/main/LICENSE)
- [Claude Mem — Apache-2.0](https://github.com/thedotmack/claude-mem)
- [Knip — ISC](https://github.com/webpro-nl/knip/blob/main/LICENSE)

## Excluded Material

An installed architecture skill matched an unlicensed `mtomcal/dotfiles` variant. It is excluded. This repository uses the separate clean MIT-licensed `mattpocock/skills` edition of `improve-codebase-architecture` instead.

## External Tools

These tools are documented integrations, not copied source code.

| Tool or capability | Repository use | License | Packaging |
| --- | --- | --- | --- |
| Knip | Deterministic maintenance scan via `maintenance:scan`. Findings are reviewed before cleanup. | ISC | npm development dependency; retain package metadata. |
| Git + worktrees | Isolate real repository work before implementation. | GPL-2.0-only | External system prerequisite; no Git source copied. |
| GitHub CLI (`gh`) | Optional issue, PR, push, and merge steps after explicit approval. | MIT | External optional prerequisite; no CLI source copied. |
| Graphviz | Optional DOT-to-SVG rendering for architecture diagrams. | EPL-2.0 | External optional prerequisite; no Graphviz source copied. |
| Browser capability | Optional visual presentation for architecture reports. | Host-provided | No source code or license imported by this repository. |
| Swarm runtime | Optional execution of adapted orchestration workflow. | Host-dependent | Core demo uses deterministic mock agents; runtime is not bundled. |

## Import Gate

Before inclusion, every third-party entry must have:

1. source URL;
2. immutable commit or tag resolved to a commit;
3. license identifier and retained license text/notice where required;
4. package status and destination;
5. direct skill dependencies and companion files;
6. a public-content audit confirming no proprietary material was introduced.

If any item fails the gate, it is not copied. It may be independently rewritten only when no protected expression is reused.
