---
name: marketing-screenshots
description: Use when capturing real running app UI for marketing/product screenshots, browser/mobile viewports, device/phone mockups, landing pages, pitch decks/presentations, or App Store/product marketing assets.
---

# Marketing Screenshots

Capture real app UI; compose around untouched PNG. Never redraw product UI with image generation.

1. Inspect routes, auth/demo state, Playwright config, and asset policy. Use local fixtures or demo accounts only; follow [capture-guidelines.md](references/capture-guidelines.md) for auth/privacy checks.
2. For repeatable scenes/custom sizes, read [configuration.md](references/configuration.md), then add `marketing-screenshots.config.mjs` at project root. Otherwise use `--url` / `--route`. More prompts: [examples.md](references/examples.md).
3. Start app if required. Use semantic `readySelector` / `waitFor`, not arbitrary sleeps.
4. Capture: script freezes motion, waits for fonts/images, sets locale/timezone/color/viewport/DPR, saves raw PNG first, then device/canvas assets and manifest.
5. Inspect every raw/derived asset. Visible email, credential/debug text, loading states, or wrong route block marketing-ready handoff.

## Commands

Set `$skillDir` to the absolute directory containing **loaded SKILL.md**; resolve scripts/references there (repository/profile/staged copy). Capture/compose: run from target project root or pass `--project-root PATH`. Validate: relative `--input` uses CWD; use project-root CWD or absolute input. Uses app-installed `@playwright/test` Chromium; never auto-install dependencies.

```powershell
node "$skillDir/scripts/marketing-screenshots.mjs" capture --all
node "$skillDir/scripts/marketing-screenshots.mjs" capture --scene landing
node "$skillDir/scripts/marketing-screenshots.mjs" capture --url http://127.0.0.1:5173/ --name landing --preset mobile --device phone --canvas landing-hero,pitch-16x9
node "$skillDir/scripts/marketing-screenshots.mjs" compose --input artifacts/marketing-screenshots/landing/landing--raw.png --device phone --canvas square
node "$skillDir/scripts/marketing-screenshots.mjs" validate --input path/to/output.png
```

Composition never changes raw files. Capture replaces an existing raw PNG only with explicit `--overwrite`.

## Outputs

Deterministic directory: `artifacts/marketing-screenshots/<scene>/`.

- `<scene>--raw.png`
- `<scene>--phone-transparent.png` (or tablet/browser-window)
- `<scene>--landing-hero.png`, `<scene>--pitch-16x9.png`, or `<scene>--square.png`
- `manifest.json`
