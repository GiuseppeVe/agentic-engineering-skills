# HTML Report Format

Single HTML file in the OS temp directory; location and opening instructions live in [SKILL.md](SKILL.md#2-present-candidates). Tailwind and Mermaid load from CDNs; all other content is static. Only scripts: Tailwind CDN and Mermaid ESM import, with no app code or interactivity beyond Mermaid rendering.

## Scaffold

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Architecture review for {{repo name}}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script type="module">
      import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
      mermaid.initialize({ startOnLoad: true, theme: "neutral", securityLevel: "loose" });
    </script>
    <style>
      .seam { stroke-dasharray: 4 4; }
      .leak { stroke: #dc2626; }
      .deep { background: linear-gradient(135deg, #0f172a, #1e293b); }
    </style>
  </head>
  <body class="bg-stone-50 text-slate-900 font-sans">
    <main class="max-w-5xl mx-auto px-6 py-12 space-y-12">
      <header>...</header>
      <section id="candidates" class="space-y-10">...</section>
      <section id="top-recommendation">...</section>
    </main>
  </body>
</html>
```

## Report fields

Header: repo name, date, compact legend (solid box = module, dashed line = seam, red arrow = leakage, thick dark box = deep module). Start candidates directly, without an introduction.

Each candidate is an `<article>` with:

| Field | Content |
|---|---|
| Title | Short name for the deepening, e.g. "Collapse the Order intake pipeline". |
| Badges | Strength: `Strong` (emerald), `Worth exploring` (amber), or `Speculative` (slate); dependency category: `in-process`, `local-substitutable`, `ports & adapters`, or `mock`. |
| Files | Involved files/modules; monospaced, `font-mono text-sm`. |
| Before / After | Side-by-side custom visuals showing shallowness and deepening; centrepiece of the card. |
| Problem | One sentence: current friction. |
| Solution | One sentence: what changes. |
| Wins | Bullets of ≤6 words each, explaining locality, leverage, and improved tests, e.g. "Tests hit one interface". |
| ADR callout | When applicable, one line in an amber box identifying the conflict and reason to reopen. |

Top recommendation: one larger card with candidate name, one sentence explaining why, and anchor link to its card.

## Diagram patterns

Mix patterns; choose what communicates the structure rather than making every diagram alike. Redraw any diagram that needs a paragraph to explain it.

- **Mermaid graph/flowchart:** dependencies and call flows; sequence diagrams for round-trip counts. Wrap in a styled card, use `classDef` for leakage and deep-module emphasis.
- **Hand-built boxes/arrows:** bordered labelled divs with absolute inline SVG arrows, useful when Mermaid cannot show a thick deep module with faded internals.
- **Cross-section:** horizontal `h-12 border-l-4` bands; many thin pass-through modules become one thick responsibility.
- **Mass diagram:** interface and implementation rectangles. Before: similar height; after: short interface, tall implementation.
- **Call-graph collapse:** nested calls become one module, with internal calls faded inside.

```html
<div class="rounded-lg border border-slate-200 bg-white p-4">
  <pre class="mermaid">
    flowchart LR
      A[OrderHandler] --> B[OrderValidator]
      B --> C[OrderRepo]
      C -.leak.-> D[PricingClient]
      classDef leak stroke:#dc2626,stroke-width:2px;
      class C,D leak
  </pre>
</div>
```

## Style and language

- Editorial layout with whitespace, not a corporate dashboard. Optional `font-serif` headings on stone/slate.
- One emerald or indigo accent, red leakage, amber warnings.
- Diagrams around 320px tall, fitting before/after side by side without scrolling; schematic labels use `text-xs uppercase tracking-wider`.
- Plain, sparse prose using the domain glossary and exact **codebase-design** terms. Do not substitute component/service/unit for module, API/signature for interface, boundary for seam, or layer/wrapper when module is meant.
- Wins name concrete gains: "locality: bugs concentrate in one module", "leverage: one interface, N call sites". Replace vague "cleaner code" or "easier to maintain" with these gains. No hedging or throat-clearing; use bullets where sufficient and cut expendable text.
