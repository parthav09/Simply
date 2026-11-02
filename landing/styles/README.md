# Simply theme

All pages use one theme. The landing page, live lab, recorded lab, maps, inspector and evaluation page share the same typography, semantic colors and control sizes.

- `tokens.css` owns literal colors, spacing, type sizes, corners, motion and map colors. Light and dark are root theme variants; no page may redefine these tokens.
- `base.css` owns resets, body typography, focus and reduced motion.
- `components.css` owns shared controls, actions, navigation, badges and empty states.
- `marketing.css`, `workspace.css` and `evidence.css` own composition and responsive layout. They use the same tokens and primitives.
- `app/globals.css` is the sole stylesheet entry point. Files declare explicit cascade layers themselves because the installed CSS loader does not support `@import ... layer(...)`.
- `ui/ThemeProvider.tsx` synchronizes the System / Light / Dark setting, local storage, operating-system changes and all theme controls. The root bootstrap applies the saved preference before page content paints.
- `ui/map-theme.ts` maps department identities to tokens. Both map renderers use this mapping.

Use semantic variables such as `var(--color-text-secondary)` and `var(--space-4)`. Do not add per-page palettes, literal UI colors, broad overrides or append-only fixes. Spatial map geometry and sprite offsets can remain pixel values. For a new control, reuse the shared control/action styles before adding a component variant.

## Performance and evidence

`lib/recordings.ts` coalesces requests and caches at most three integrity-checked recordings. A new content hash or source identity always requires validation. Failed requests can be retried. Catalogues refresh after 30 seconds or an explicit retry; a successful live export invalidates the catalogue immediately.

`lib/replay.ts` indexes each saved shopper's event history once and uses binary lookup for seeking. Final live frames come directly from Python's final projection. Static map fixtures are memoized separately from moving shoppers, and the lab display does not rerender on each waiting-clock tick.

Run `npm run verify:ui`, `npm run verify:replay`, `npm run verify:live`, type checks, lint and the production build. The UI benchmark reports projection CPU time only; model latency and network timing are separate.

## Compact store maps

The lab defaults to **Fit**: the full recorded grid and transport controls fit in the available desktop viewport. `MapViewport` measures the available height and constrains the workspace width to the store’s aspect ratio plus the inspector. The map fills the workspace without empty side gutters. A single toolbar holds mode, setup, and run controls as direct buttons; recordings are picked from a list rather than nested dropdowns. The map and inspector share one frame. Shopper selection lives in the inspector. Run totals sit under the map as a metric strip. Zoom changes only its displayed scale; Fit restores the overview and resets internal scrolling. Keyboard arrows focused in the map pan the viewport rather than seek replay events. The inspector scrolls within the adjacent panel.

`lib/map-items.ts` draws one item block per occupied shelf cell, then groups 4–6 neighboring blocks into the original bay. Extra SKUs that share a cell stay on that block and appear in the hover label. The 22 × 14 simulation grid, product coordinates, shopper routes, and historical recordings remain unchanged. Both flat and isometric maps use these blocks and the shared product/department emojis from `ui/map-theme.ts`.
