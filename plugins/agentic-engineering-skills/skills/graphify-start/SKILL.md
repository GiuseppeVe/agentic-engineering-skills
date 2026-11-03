---
name: graphify-start
description: Use only when explicitly invoked by name.
disable-model-invocation: true
---

# Graphify Start

First, check the current repository for a project-specific Graphify protocol, such as `docs/development/GRAPHIFY.md`. If one exists, follow its relevant instructions and verify graph-based conclusions against source files.

If no project-specific protocol exists, use the installed `graphify` skill as the default: check for an existing `graphify-out/graph.json` and query it for relevant codebase questions. Verify conclusions against source files. Build or update the graph only when the task requires it; do not automatically rebuild the whole graph.

The original Alfe skill pointed to Alfe's `docs/development/GRAPHIFY.md#protocollo-graphify`. That repository-specific protocol is not assumed here; this fallback makes the skill usable in other repositories.
