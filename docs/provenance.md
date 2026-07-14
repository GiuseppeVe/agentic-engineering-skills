# Provenance

`manifests/skills.lock.json` is source of truth. `vendor` means byte-identical pinned upstream content; `adapted` means pinned ancestry plus stored patch and change notice; `original` means repository-authored MIT material with release commit and local hash.

| Skill | Status | Acquisition source |
| --- | --- | --- |
| `brainstorming` | adapted | `obra/superpowers@d884ae04edebef577e82ff7c4e143debd0bbec99` |
| `cavecrew` | adapted | `JuliusBrussee/caveman@0d95a81d35a9f2d123a5e9430d1cfc43d55f1bb0` |
| `caveman` | vendor | `JuliusBrussee/caveman@0d95a81d35a9f2d123a5e9430d1cfc43d55f1bb0` |
| `cleaning-repo-with-knip` | original | Repository release `46a201b669a90debebdc3eaa976bc5dfa9a83c1a` |
| `codebase-design` | vendor | `mattpocock/skills@391a2701dd948f94f56a39f7533f8eea9a859c87` |
| `domain-modeling` | vendor | `mattpocock/skills@391a2701dd948f94f56a39f7533f8eea9a859c87` |
| `grill-me` | adapted | `mattpocock/skills@391a2701dd948f94f56a39f7533f8eea9a859c87` |
| `grilling` | vendor | `mattpocock/skills@391a2701dd948f94f56a39f7533f8eea9a859c87` |
| `implementing-plans` | original | Repository release `46a201b669a90debebdc3eaa976bc5dfa9a83c1a` |
| `improve-codebase-architecture` | adapted | `mattpocock/skills@391a2701dd948f94f56a39f7533f8eea9a859c87` |
| `importing-handoff` | original | Repository release recorded in lock |
| `learn-codebase` | adapted | `thedotmack/claude-mem@312d640b0188753acd92a1a82d95a84d5c7c43db` |
| `setup-matt-pocock-skills` | adapted | `mattpocock/skills@391a2701dd948f94f56a39f7533f8eea9a859c87` |
| `swarm-orchestration` | adapted | `ruvnet/ruflo@7ef4d4e655d81c0451f6f40f35729cce6c9928e7` |
| `test-driven-development` | vendor | `obra/superpowers@d884ae04edebef577e82ff7c4e143debd0bbec99` |
| `to-spec` | adapted | `mattpocock/skills@391a2701dd948f94f56a39f7533f8eea9a859c87` |
| `using-git-worktrees` | vendor | `obra/superpowers@d884ae04edebef577e82ff7c4e143debd0bbec99` |
| `wayfinder` | adapted | `mattpocock/skills@391a2701dd948f94f56a39f7533f8eea9a859c87` |
| `writing-plans` | adapted | `obra/superpowers@d884ae04edebef577e82ff7c4e143debd0bbec99` |
| `writing-skills` | vendor | `obra/superpowers@d884ae04edebef577e82ff7c4e143debd0bbec99` |

Exact paths, hashes, patches, and legal-file mappings live in [lock manifest](../manifests/skills.lock.json). Licensing summary: [Third-Party Notices](../THIRD_PARTY_NOTICES.md).

## Cavecrew agent-profile adaptation

Seven role contracts (`cleanup`, `controller`, `implementer`, `planner`, `researcher`, `reviewer`, and `test-runner`) adapt the pinned Cavecrew role model from `JuliusBrussee/caveman@0d95a81d35a9f2d123a5e9430d1cfc43d55f1bb0`. Repository-authored payloads normalize roles into host-neutral contracts and a common result envelope. Canonical repository manifest `manifests/agent-profiles.json` records provenance and exact payload hashes. Installed plugin manifest `plugins/agentic-engineering-skills/manifests/agent-profiles.json` mirrors same seven entries with paths relative to plugin root. These adaptations extend existing `cavecrew` notice; they are not additional vendor copies or native host registrations.
