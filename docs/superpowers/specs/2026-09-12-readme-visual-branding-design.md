# README Visual Branding Design

**Date:** 2026-09-12

**Status:** Approved design; implementation pending
**Scope:** Repository presentation only. Skill payloads and workflow behavior remain unchanged.

## Intent

Give `agentic-engineering-skills` a more professional public-facing first impression while preserving its technical character. The repository should communicate a workflow shaped by hands-on engineering experience and made shareable for inspection and adaptation. It must not sound like a course, tutorial, or universal prescription.

## Positioning

Primary message:

> A workflow worth sharing.

Supporting message:

> Practices for turning intent into specifications, plans, implementation, and evidence.

Voice:

- first-person ownership may appear in the README context, but the hero stays concise;
- observational and practical, not instructional or authoritative;
- invite inspection and adaptation;
- distinguish shipped workflow from future experiments;
- avoid language such as “learn”, “必須”, “the correct way”, or “field guide”.

## Visual direction

Use the selected **A3 / Editorial Hybrid** direction with the **B2 / Shared Workflow** positioning.

- warm paper background;
- near-black editorial typography;
- terracotta as the signal color;
- restrained brass/tan supporting detail;
- serif display typography paired with a neutral sans-serif for metadata;
- asymmetrical editorial layout with a compact evidence path;
- no robots, glowing brains, stock imagery, SaaS dashboards, external fonts, or remote assets.

## Hero asset

Create one original static SVG at:

`assets/agentic-engineering-skills-hero.svg`

Target dimensions: approximately `1200 × 420` with a responsive viewBox. The asset must:

- be self-contained and under 1 MB;
- contain no JavaScript, `foreignObject`, base64, remote images, or external fonts;
- include `<title>` and `<desc>` for accessibility;
- remain legible at GitHub thumbnail width;
- use exact, manually authored text;
- show the real workflow in a compact two-line path:

```text
Evidence → Decisions → Spec → Plan
Implement → Test Gaps + TDD → Review → Owner Gate
```

The visual hierarchy is: repository name, shared-workflow claim, then the evidence path. The path is explanatory context, not a set of commands for the visitor.

## README integration

Place the hero immediately after the repository title. Add a concise opening paragraph and a small set of reliable badges only if their URLs are stable and verified. Keep the existing Mermaid workflow because it remains the editable, accessible model of the lifecycle.

The opening should answer quickly:

1. what this is: a composable skills bundle for Codex and Claude Code;
2. why it exists: to make an experience-shaped engineering workflow inspectable and reusable;
3. what it covers: discovery, design, planning, implementation, verification, review, and cleanup;
4. what is not included: Orientated E2E Testing v5.2 remains planned/out of scope until validated.

Do not rewrite the technical installation, provenance, compatibility, or license sections beyond links and wording needed for consistency.

## Acceptance criteria

- Hero renders from a relative Markdown path on GitHub.
- README still communicates its purpose if the image fails to load.
- SVG validates as text, has accessible metadata, and contains no external references.
- Existing Mermaid workflow remains present.
- `npm run verify:pack` and `npm run audit:public` pass.
- No file under `plugins/.../skills/` changes as part of this visual pass.
- The temporary `.superpowers/` brainstorming session is not committed.
- Main branch remains untouched; all work stays on `codex/readme-branding` until explicit integration approval.

## Out of scope

- Orientated E2E Testing v5.2;
- skill content or manifest changes;
- GitHub social-preview upload;
- branch-protection or repository-settings changes;
- a separate logo system or full documentation redesign.
