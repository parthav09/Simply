<!-- BEGIN:nextjs-agent-rules -->

## This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

## Product and replay boundary
Follow ../AGENTS.md. This folder is the product website. Lab components present
exported Python runs; they cannot generate shopper actions or outcomes. Keep
business logic in simulation/core and React lab UI in landing/ui. Do not add a desktop app. Never
restore a browser shopping policy or fake fallback. Missing recordings must be
shown explicitly. All replay statistics come from the Python export.
The live lab consumes Python's validated committed-event stream through the
same-origin /api/simulation proxy. The proxy transports requests and events;
it contains no model key, shopper policy, state mutations or outcome metrics.

## Shared theme
Use `styles/tokens.css` as the only source of literal UI colors and theme values.
All pages and SVG maps consume semantic tokens. `styles/components.css` owns
shared controls; page styles own layout, not independent palettes. Keep the
System / Light / Dark preference consistent across routes. Do not reintroduce
page-specific token overrides or append-only visual patches. See styles/README.md.
