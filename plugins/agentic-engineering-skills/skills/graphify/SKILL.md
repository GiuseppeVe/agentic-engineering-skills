---
name: graphify
description: Answer questions about a codebase, architecture, file relationships, or project content. Query the existing Graphify graph when available. Build or update a knowledge graph when explicitly requested.
---

> **Adaptation:** From Graphify-Labs/graphify's pinned Codex skill and references, with project protocol routing for both hosts.

# Graphify

## Route the request

1. Check the project instructions for a Graphify protocol. Look for
   `docs/development/GRAPHIFY.md` or the path named by the repository.
   Follow its guidance for the graph location, query commands, and verification.
2. For a codebase question, check for the existing graph at the configured path,
   defaulting to `graphify-out/graph.json` at the project root.
3. If the graph exists, query it before broad source exploration. If it is
   missing or unusable, trace the question directly in source.
4. Build or update the graph only when the user explicitly requests that
   operation. A codebase question alone authorizes read-only investigation.

## Query an existing graph

Use the project command when specified. With the default protocol, run from the
project root:

```text
graphify query "<question>"
graphify path "<concept A>" "<concept B>"
graphify explain "<node>"
```

Use [query guidance](references/query.md) for graph vocabulary, traversal
options, and a read-only NetworkX fallback when the CLI is unavailable.
Use graph `source_location` values to locate the relevant files. Verify
material claims against current source, especially inferred relationships.
Report stale coverage or unresolved edges when they affect the answer.

## Explicit graph operations

- For `/graphify --help` or `-h`, return the Usage block from
  [full build and commands](references/full-build.md).
- For a requested build, load [full build and commands](references/full-build.md).
  It covers installation, extraction, clustering, and export.
- For incremental updates and reclustering, use [update](references/update.md).
- For requested corpus additions or watching, use [add and watch](references/add-watch.md).
- For requested repository hook integration, use [hooks](references/hooks.md).

Respect the project protocol for these operations and preserve existing outputs
when an operation cannot complete.
