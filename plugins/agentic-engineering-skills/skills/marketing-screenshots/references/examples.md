# Examples

- `Use marketing-screenshots to capture onboarding steps 1–3 as transparent phone mockups and 16:9 pitch-deck images.`
- `Use marketing-screenshots to capture dashboard in mobile viewport and create a transparent device mockup.`
- `Create landing-page hero asset from current dashboard screen. Use transparent phone mockup; leave negative space left for copy.`
- `Capture all configured marketing scenes and regenerate every output preset.`

Set `$skillDir` to the absolute directory containing the loaded SKILL.md; run this capture command from target project root (or add `--project-root PATH`).

```powershell
node "$skillDir/scripts/marketing-screenshots.mjs" capture --url http://127.0.0.1:5173/dashboard --name dashboard --preset mobile --device phone --canvas landing-hero,pitch-16x9
```