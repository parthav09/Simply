# Simply product website

The product page explains the project and showcases explicitly published Python
recordings. `/lab` streams live Python sessions and retains a recorded replay tab. `/evaluation` displays Python
experiment reports. Shopper decisions and outcome calculations belong to
`simulation/core/`; the lab UI belongs to `landing/ui/`. This is a React web app,
with no desktop application. Python owns every action and records it before the
local live service publishes it. Start the live service in a second terminal with
`npm run simulation:serve`; keep `npm run dev` running for the website.

```bash
npm install
npm run dev
npm run typecheck
npm run lint
npm run verify:replay
npm run build
```

After adding `OPENROUTER_API_KEY` (or `OPEN_ROUTER_KEY`) to the repository-root `.env`, run the default
GPT-6 Luna shoppers and export their recording with:

```bash
npm run simulate:openrouter
```

This uses 10 shoppers by default. Additional options follow `--`, for example
`npm run simulate:openrouter -- --shoppers 15 --layout neighborhood_express`.
The Python core tracks API usage and cost without an app-enforced spending cap
for these runs; the browser reads the resulting recording. The website and lab
use one warm paper and forest-green palette.

From the repository root, publish a selected model recording:

```bash
.venv/bin/python -m simulation.core.export_replay simulation/runs/YOUR_RUN.jsonl
```

A partial run needs `--allow-partial`. Offline fixtures require `--allow-test` and
are labeled as fixtures. The catalogue and files live under `public/replays/`.
The live UI requests a Python session and lifecycle controls through its local
proxy; it never applies actions, invents a result or substitutes a scripted policy.
Live states and metrics come from Python. Recorded playback, seeking and filters
only select saved states. Reconnecting restores the existing run without calls
to the model. See `../simulation/docs/gary2-live-reference.md` for the exact Gary-2
comparison: its live view is a Python desktop window; its website is saved replay.

Build/dev explicitly use Next's webpack pipeline. Fonts are downloaded by
`next/font` during the first build; subsequent builds use its cache. The app's
custom CSS does not require a second Tailwind compiler process.

Older recordings and archived prototypes were removed at the user's request.
The retained evidence is the newest successful run for each layout. API ledger
history is independent and remains intact.

New experiments use Layout A / Anchor loop and Layout B / Express essentials,
with 10–15 shoppers (default 10). Older published recordings retain their actual
inputs; changing this scope never fabricates a replacement recording.
New runs use one unit per unique product and finish with a single checkout
action. Shopper budgets stay soft. Earlier retained replays keep their original
shopping rules.
New layout, model and assistance studies use `simulation/evaluation/study.py`.
See `../simulation/docs/controlled-studies.md` for prepare/run/report/publish.
The Evidence study section displays those Python reports, arm labels, paired
uncertainty, failed attempts and the frozen protocol download.

The live setup includes Luna/Terra model controls. Model selection is fixed
for each run and is recorded with the correct pricing. Terra has higher token
prices. Live runs retain ledger accounting without a local spending cap. Provider
rate and quota limits still apply. Previewing a layout makes no model
calls. The lab shows pending decisions, pause state, actual purchase/failure
feeds and static sprites placed directly at confirmed grid positions. New live
runs use one model proposal per action and Python-owned Gary-2 navigation assistance;
adjustments are identified in the feed and original proposals remain in evidence.
Ended runs keep their final state on screen and restore the same recording after
a page reload. New setup explicitly returns to configuration without model calls.

## Private interview room

Open `/secretstudy23` directly during local development; it has no navigation
link. A server-side password comparison is required before study material is
loaded or serialized. Successful login creates an eight-hour signed HttpOnly,
SameSite=Strict cookie scoped to the route; Log out clears it. The password and
session-signing secret are configured in ignored `landing/.env.local` as
`STUDY_PASSWORD` and `STUDY_SESSION_SECRET`; neither is a public environment value.
Missing configuration fails closed. Keep the signing secret random and private.

The interview workbench includes a systems atlas, source-grounded study walkthrough,
104 multiple-choice questions covering project implementation and the underlying LLM, systems, evaluation and training concepts, 34 additional MLE interview drills with spoken-answer notes, scoring checkpoints and follow-ups, practice and timed modes, automatic scoring,
post-submission explanations, missed-question retries, and browser-local quiz history/export. It makes no model requests and never
changes simulation state. Logout ends access but preserves browser-local notes.

The additional local-only restriction remains: the route returns **404 in
production**, and its development-only imports exclude the study content and client
bundle from production builds. `noindex` is an additional measure, not the access
boundary. Bind the development server to loopback (`npm run dev -- --hostname
127.0.0.1`) and keep it off public tunnels. Hosted password access is not enabled.

Study explanations are an October 29, 2026 snapshot. Their source module paths
are listed with each concept and answer. The resume comparison uses the two intact
Terra layout pairs, not the default single-repetition Evidence table. Update the
learning content deliberately if the engine or published evidence changes.

After a production build, run `node scripts/verify-study-room.cjs` to check the
access gate, absence of private content in public HTML/client chunks, question
coverage, answer shuffling/scoring and referenced source paths.
