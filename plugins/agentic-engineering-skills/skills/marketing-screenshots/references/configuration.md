# Configuration

Place `marketing-screenshots.config.mjs` in project root. Start from `marketing-screenshots.config.mjs.example`.

`baseUrl`, `outputDir`, `capture`, `viewports`, `devices`, `canvases`, and `scenes` are optional; defaults exist. A scene needs `name` plus `route` or absolute `url`. It may include `viewport`, `selector` (capture only that element), `readySelector` / `waitFor`, `setup`, `storageState`, `colorScheme`, `locale`, `timezoneId`, `canvasDevice`, and `outputs`.

Viewport names: `mobile` (390×844 @3), `tablet` (768×1024 @2), `desktop` (1440×1024 @2). Canvas names: `landing-hero` (1600×1200), `pitch-16x9` (1920×1080), `square` (1600×1600). Device outputs: `none`, `phone`, `tablet`, `browser-window`.

Use `--project-root PATH` when running profile skill against another project; pass `--output-dir` for a run-specific artifact location.