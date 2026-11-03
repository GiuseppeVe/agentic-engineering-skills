# Search reference

Load when choosing a CLI domain/stack, invoking unfamiliar flags, or persisting a design system. Run searches from the intended project directory. Replace `python3` with a verified available interpreter when needed. Resolve `<skill-directory>` to this installed skill's directory; installation paths vary by host.

## Routing and available catalogs

The CLI's parser/configuration is authoritative; run `--help` for supported choices. Current `core.py` exposes these domains:

| Domain | Use for |
|---|---|
| `product` | Product/industry patterns |
| `style` | Visual styles, effects, AI prompt and CSS keywords |
| `color` | Product palettes; verify resulting contrast |
| `typography` | Heading/body font pairings |
| `google-fonts` | Font-family metadata; recommendations do not authorize downloads |
| `landing` | Landing-page structure and CTA placement |
| `chart` | Chart selection, data characteristics, accessible alternatives |
| `ux` | General UX/accessibility; inspect result platform |
| `icons` | Icon lookup; project-approved family still wins |
| `react` | React/Next.js performance; not a React Native stack substitute |
| `web` | Web/DOM interface accessibility and interaction (`app-interface.csv`; every current row is Platform=Web) |

There is no supported `prompt` domain: use `style` for prompt/CSS keywords. For web keyboard/DOM accessibility use `web`; use `ux` for general UX and inspect each result's Platform field. For native accessibility use the matching registered stack only when it matches the actual app; use project/platform guidance for native safe areas. The catalog does not provide a dedicated native safe-area domain.

Only `--stack react-native` is registered here, despite other CSV files and stale script help examples mentioning more stacks. Never infer the project's framework from this limit; do not pass unsupported `--stack nextjs`, `--stack react`, or Flutter/Vue stack values.

## Commands

Run these commands from the project root, replacing `<skill-directory>` with this skill's installed directory.

```bash
python3 "<skill-directory>/scripts/search.py" --help
python3 "<skill-directory>/scripts/search.py" "keyboard focus labels" --domain ux -n 3
python3 "<skill-directory>/scripts/search.py" "keyboard focus labels" --domain web
python3 "<skill-directory>/scripts/search.py" "minimalism CSS prompt" --domain style
python3 "<skill-directory>/scripts/search.py" "rerender memo" --domain react
python3 "<skill-directory>/scripts/search.py" "trend comparison" --domain chart --json
python3 "<skill-directory>/scripts/search.py" "list navigation" --stack react-native
python3 "<skill-directory>/scripts/search.py" "wellness dashboard calm" --design-system -p "Project Name" -f markdown
```

`-n`/`--max-results` limits results; `--json` works for domain/stack search. Design-system output supports `-f ascii` (default) or `-f markdown`. Choose one mode per call: design-system takes precedence over stack, which takes precedence over domain. Keep queries focused; refine keywords rather than loading every catalog.

### Windows PowerShell

Run from the project root with a quoted resolved path; `python` here must already be verified:

```powershell
python "<skill-directory>/scripts/search.py" "keyboard focus" --domain ux
```

If Python is missing, use the manual guidelines and report the search unavailable. Package installation is outside this skill's automatic workflow.

## Optional persistence

Use only when the user requested saved design artifacts. Inspect existing output first; generation can replace `MASTER.md` and the selected page file. Preserve manual rules rather than treating regeneration as a harmless lookup.

```bash
python3 "<skill-directory>/scripts/search.py" "wellness dashboard calm" --design-system --persist -p "Project Name" --page "dashboard" --output-dir "<project-directory>"
```

The implementation writes under `design-system/<project-slug>/`, where the slug is project name lowercased with spaces replaced by hyphens. Example above creates:

- `<project-directory>/design-system/project-name/MASTER.md`
- `<project-directory>/design-system/project-name/pages/dashboard.md`

Without `--output-dir`, the current directory is used. Without `-p`, project slug is `default`. Page names are lowercased and spaces replaced by hyphens. Use simple safe names; do not put path separators in project/page names.

Read the actual project folder's Master, then the requested page override if present. Page rules override Master only for specified deviations; otherwise inherit Master. Generated file prose may omit the project slug: resolve paths from actual output, not those stale examples. This precedence never supersedes project instructions or accessibility requirements.
