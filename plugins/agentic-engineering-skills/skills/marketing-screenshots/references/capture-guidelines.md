# Capture Guidelines

Use running app, not generated UI. Capture from a demo/local account with seeded, sanitized data. Never put passwords, API keys, tokens, or production storage state in config or manifest.

Use `readySelector` for stable meaningful content; use `waitFor` for a specific element. The tool waits DOM readiness, short network idle, fonts, and images, then disables animation/caret. If a requested state cannot be reached, stop and report it; do not capture a nearby screen.

`setup` is an async function receiving `{ page, context }`. Keep it small: click, fill demo data, open modal, select tab. Store reusable auth in a local ignored `storageState` path, never inside this skill.

Inspect every output. Confirm exact route/state, no loading skeleton, no personal data, no dev overlay, no distorted app image. Device assets must keep transparent outer pixels; canvases intentionally use their configured background.