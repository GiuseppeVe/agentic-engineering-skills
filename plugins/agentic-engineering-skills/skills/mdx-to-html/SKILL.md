---
name: mdx-to-html
description: Use when a reviewable MDX specification or document must become a standalone, browser-viewable HTML artifact while preserving readable structure and visual review surfaces.
disable-model-invocation: true
---

# MDX to HTML

Convert an explicit existing `.mdx` path into a separate local review artifact, including after `to-spec`. Preserve source unchanged. Output beside it as `<basename>.review.html` (e.g. `feature.mdx` → `feature.review.html`).

## Conversion contract

Produce complete `<!doctype html>` HTML with semantic body and inline CSS. No React, executable JSX/JavaScript expressions, imports/exports, remote assets, CDN, build server, or runtime fetches.

| Source | Review output |
| --- | --- |
| Headings, lists, links, blockquotes | Semantic HTML; stable heading anchors |
| Tables | Responsive wrapper; preserve column labels |
| `- [ ]` / `- [x]` | Read-only visual checkbox state |
| Fenced code | Escaped `<pre><code>`; preserve language label |
| Mermaid fence | Static SVG when tooling exists; otherwise readable source plus visible note |
| Known JSX callout | Styled semantic `<aside>` with children |
| Unknown JSX | Styled fallback with readable children; name component in Conversion notes |
| `import`, `export`, dynamic `{expression}` | Never execute; preserve static text where possible; visibly flag unsupported content and record it |

Whenever an import is removed, a prop/expression cannot be evaluated, Mermaid cannot become SVG, or JSX uses a fallback, show **both an in-context marker and Conversion notes at page end**. This remains required when a request asks for no notes or polished-only output. Never imply dynamic MDX rendered successfully.

## Procedure and checks

1. Read source; inventory Markdown, Mermaid, JSX, imports, and dynamic expressions.
2. Convert static Markdown; map only known JSX. Preserve readable children and record exact limitations for unknown/dynamic parts.
3. Write standalone HTML. Keep source order and text except necessary HTML escaping. Use readable system fonts, restrained colors, max-width column, clear headings/anchors/callouts, horizontal scroll for tables/code, and print CSS.
4. Verify source unchanged; no executable JSX/import/export remains; page opens offline; headings, tables, tasks, code, markers, and notes stay readable.

Renaming MDX or opening it raw is not conversion. Never execute MDX JavaScript, use Mermaid CDN, or silently drop unsupported imports, props, or components.

Example: `Use mdx-to-html on docs/specs/feature.mdx. Create feature.review.html beside it; preserve source and report unsupported content in Conversion notes.`
