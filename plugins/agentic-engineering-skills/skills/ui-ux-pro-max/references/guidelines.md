# UI guidelines by concern

Load only categories relevant to the changed UI. These are implementation references; the single delivery checklist lives in SKILL.md. Platform requirements and project conventions determine exact controls, units, breakpoints, and checks.

## Priority routing

| Priority | Concern | Search |
|---|---|---|
| Critical | Accessibility; touch and interaction | `ux`; web-specific `web` |
| High | Performance; layout; navigation; style consistency | `ux`, `product`, `style` |
| Medium | Typography/color; forms/feedback; motion | `typography`, `color`, `ux` |
| Context-dependent | Charts/data visualization | `chart` |

Concrete blockers take priority over cosmetic improvements, regardless of table order.

## Accessibility

- Use semantic controls before custom roles. Web fields need associated labels; native controls need platform accessibility names, hints where useful, and state announcements.
- Keep keyboard and reading order logical; preserve system shortcuts, visible focus, and skip-to-content navigation where applicable. Drag operations need keyboard or visible control alternatives.
- Manage modal focus, Escape/cancel/back behavior, and return focus to the invoker. Announce async feedback without unexpectedly moving focus.
- Text contrast: normal text 4.5:1, including secondary text; large text 3:1 (at least 18pt regular or 14pt bold). Essential non-text control indicators 3:1. Measure actual foreground/background pairs in each theme.
- Convey errors, selections, and chart distinctions with text, shapes, patterns, or icons as well as color. Decorative imagery stays hidden from assistive technology; meaningful imagery gets useful alternatives.
- Support browser zoom, system text scaling/Dynamic Type, and reduced motion. Enlarged text must remain readable and operable, with wrapping or an accessible full-text expansion.

## Touch and interaction

- Aim for at least 44×44pt iOS or 48×48dp Android targets; use the platform's applicable requirements for web. Expand hit areas when visual icons are smaller, leaving comfortable separation (8px/dp is a useful starting point).
- Primary actions work through click/tap rather than hover alone. Provide visible alternatives for critical gesture-only actions; preserve back-swipe, pinch zoom, and other system gestures.
- Give prompt press feedback. During async actions expose progress and prevent unintended duplicate submissions; disabled state needs semantics as well as appearance.
- Keep swipe/drag affordances clear, drag thresholds deliberate, and nested gesture regions non-conflicting. Avoid precision-dependent targets near notches, edges, or system bars.
- Use haptics sparingly for meaningful native feedback. Web pointer/hover states should match the actual control semantics.

## Performance

- Use appropriate responsive image formats/sizes; defer below-fold images and heavy media while prioritizing important visible content. Declare dimensions or aspect ratio to avoid layout shift.
- Reserve space for asynchronously loaded content. Split code by route/feature where useful; audit third-party scripts and preload only critical fonts/resources.
- Use appropriate font-display and fallback metrics. Batch DOM reads and writes to reduce layout thrashing.
- Profile long lists before choosing virtualization; item count alone is insufficient. Keep frame work near 16ms for 60fps and move expensive work off the main thread where appropriate.
- Provide timely input feedback, useful loading states, offline/error messaging, and slow-network fallbacks. Debounce/throttle high-frequency work without making interaction sluggish.

## Style and icons

- Match style to product, audience, and existing visual language. Use one coherent elevation, radius, spacing, color, and icon system across related screens.
- Use approved vector icons for structural controls instead of emoji. Keep family, stroke, sizing, optical alignment, and filled/outline meanings consistent. Project-approved `lucide-react` takes precedence over catalog suggestions.
- Use official brand assets with correct proportions, spacing, and usage rules. Vector is preferred for scalable icons; photographs and other raster content remain appropriate when optimized.
- Keep the main task visually prominent and secondary actions subordinate; complex screens may need several contextual actions rather than an arbitrary one-button rule.
- Prefer established platform controls and idioms. Styling and blur should clarify hierarchy and state without reducing readability or responsiveness.

## Layout and responsive behavior

- Web viewport configuration should preserve zoom. Use fluid layouts and project breakpoints, content-based adaptation, and appropriate dynamic viewport units.
- Prevent unintended horizontal overflow; use deliberate accessible scrolling for wide tables or other content that requires it. Keep text readable at narrow widths and high zoom.
- Reserve content insets for fixed/sticky headers, tab bars, and CTAs; account for safe areas and OS chrome. Avoid nested scrolling that traps navigation or gestures.
- Reuse a spacing scale (often 4/8 units), consistent content widths/gutters, and a defined overlay layering system.
- Adapt priority, density, orientation, and gutters to device class. Keep long-form text to a comfortable measure (roughly 60–75 characters on wider screens); never hide essential content merely to fit.

## Typography and themes

- Use project type styles or native Dynamic Type/Material roles. Body sizes around 16px and line heights around 1.5 are starting points, not replacements for testing the actual font/platform.
- Choose complementary heading/body fonts; use a consistent size/weight hierarchy and tabular figures for changing numeric columns, prices, or timers.
- Use semantic tokens such as text, surface, primary, error, and focus, with explicit mappings per supported theme. Dark mode needs separate contrast checks rather than simple inversion.
- Borders, focus indicators, selected/disabled states, and overlays must remain distinguishable in each supported theme. Choose scrim strength from actual content legibility, not a fixed opacity requirement.
- Prefer wrapping to truncation. If truncation is essential, provide an accessible way to read the complete content; hover-only tooltips do not cover touch or keyboard users.

## Motion

- Motion should explain state changes and spatial continuity. Micro-interactions around 150–300ms are common defaults; adapt to platform conventions, task, and reduced-motion settings.
- Prefer transform/opacity when suitable; avoid expensive layout animation without measurement. Use coherent duration/easing tokens and appropriate native physics where helpful.
- Keep animation interruptible and input responsive. State changes may be immediate when that is clearer or requested by reduced motion; essential feedback must remain available.
- Use stagger, shared-element transitions, parallax, or press scaling only when they help comprehension. Prevent clipping, disorientation, jitter, and content shifts.

## Forms and feedback

- Give each field a persistent associated label, useful helper text, appropriate input type/keyboard, and autocomplete where applicable. Place actionable validation beside the field and connect it accessibly.
- Validate at a useful time; avoid noisy keystroke-by-keystroke errors. Preserve entered values after failure and focus or announce the issue without losing user context.
- Show progress for long operations; make retries safe and completion clear. Include meaningful empty, offline, error, and success states.
- Support paste and password managers; reveal complexity progressively. Use confirmations or undo appropriate to destructive actions and prevent repeated submission while requests run.

## Navigation

- Make current location, selected state, hierarchy, and back behavior predictable. Keep navigation consistent across related screens and maintain deep-link behavior where applicable.
- Native bottom navigation generally has 3–5 primary destinations; choose the platform pattern that fits the actual information architecture. Overflow destinations need clear access.
- Preserve expected system back gestures and state when returning. Keep modal and nested-navigation escape paths clear.

## Charts and data

- Match chart type to the analytical question, data volume, distribution, and scale; use honest axes, units, and time granularity. Avoid 3D/pie decoration that obscures comparisons.
- Use readable labels, legends, and tooltips with keyboard/touch access. Distinguish series with more than color and include a textual summary or accessible data table.
- Handle empty, loading, and error states with recovery. Keep drill-down/back paths and filter state predictable.
- Limit density; emphasize relevant trends with restrained gridlines and effects. Offer data export when the product needs it rather than importing a library solely because the catalog recommends one.
