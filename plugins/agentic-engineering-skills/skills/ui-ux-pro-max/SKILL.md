---
name: ui-ux-pro-max
description: Use only when the user explicitly invokes `ui-ux-pro-max` for web or mobile design, implementation, or review.
disable-model-invocation: true
---

> **Adaptation:** Based on `nextlevelbuilder/ui-ux-pro-max-skill`; adapted for portable Codex and Claude Code use.

# UI/UX Pro Max

## Invocation and scope

Use only when the user explicitly invokes `ui-ux-pro-max`. Covers visual design, interaction, accessibility, responsive behavior, and UI review for web and mobile. Backend-only or infrastructure tasks do not need it.

Project instructions, existing design systems, and actual framework take precedence over catalog recommendations. Reuse project components, tokens, and approved icon family; retain `lucide-react` where required. Recommendations do not authorize dependency changes.

## Workflow

1. Identify the requested outcome, product, audience, platform, actual stack, and existing UI path. Read relevant project instructions and existing design rules before choosing a direction.
2. Choose the smallest useful route:
   - New design or explicit style exploration: generate recommendations with `--design-system`.
   - Existing component, bug, accessibility review, or performance fix: inspect the affected behavior; use a targeted domain search only when useful. Keep the existing design system.
   - Native implementation: use the matching supported stack. This installation exposes only `react-native`; that is a catalog limit, not the project's stack. For other frameworks use applicable domain results and project guidance.
3. If a search is useful, check an available Python interpreter (`python3 --version`, or `python --version`). If absent, report the unavailable search and continue manual review with [guidelines](references/guidelines.md). Installation requires a separate user request; do not install automatically.
4. Run only relevant searches with the bundled script. [Search reference](references/search.md) lists supported domains, flags, persistence paths, and portable path syntax. Read it before unfamiliar searches or persistence.

```bash
python3 "<skill-directory>/scripts/search.py" "dashboard keyboard focus" --domain ux
```

For a new design, combine product, industry, and tone:

```bash
python3 "<skill-directory>/scripts/search.py" "wellness dashboard calm readable" --design-system -p "Project Name"
```

Search results are recommendations, not accessibility proof. Validate applicability to the actual platform; use [guidelines](references/guidelines.md) for the affected categories. Persistence is optional; use `--persist` only when saving design artifacts is requested, after checking existing files.

## Delivery checklist

Apply to the changed UI and supported platforms/themes; report checks performed and gaps.

- [ ] Meaningful controls have accessible names, roles, states, and logical focus/reading order. Web keyboard access and visible focus work; modal focus enters, stays, and returns correctly.
- [ ] Normal text, including secondary text, meets 4.5:1; large text meets 3:1. Essential non-text UI indicators meet 3:1. Meaning does not rely on color alone; meaningful images have alternatives and decorative images are ignored.
- [ ] Forms have associated labels, actionable errors, and preserved input. Loading, empty, error, success, and disabled states behave correctly where applicable.
- [ ] Touch targets and gestures fit platform requirements; critical actions have visible alternatives. Fixed UI respects safe areas and does not cover content.
- [ ] Layout supports relevant viewport sizes, orientation, zoom/text scaling, and long content. Reduced-motion behavior works without removing essential feedback.
- [ ] Tokens, icon family, typography, and interaction states stay consistent. Verify contrast independently in each supported theme.
- [ ] Images/async content reserve space; loading, list rendering, and motion remain responsive. Run relevant project checks and inspect the rendered result when available.
