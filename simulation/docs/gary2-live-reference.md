# Gary-2 execution and Simply's live React lab

Inspected Gary-2 `main` at commit
`93a4d0dac630461cbbb1d3e6e07b156f0b1bb7a3` on October 27, 2026.

Gary-2's live simulation is a Python desktop app using Raylib (`pyray`), not a
live React stream. Its asynchronous OpenAI runner submits decision requests on
an asyncio event loop. The main rendering loop repeatedly resolves completed
requests, applies decisions to the Python engine, submits subsequent requests
and draws the engine's current shopper states. It saves results and trajectories
after a simulation finishes.

The React website imports saved trajectory/result JSON in its replay catalogue.
`SimulationReplay.tsx` advances a playback cursor with `setInterval` and displays
the saved shopper snapshots. The repository's complete tree has website API
routes for its waitlist; it has no Python-to-React simulation streaming endpoint.

Primary code references:

- [Async OpenAI requests](https://github.com/ved-2004/Gary-2/blob/93a4d0dac630461cbbb1d3e6e07b156f0b1bb7a3/simulation/agents/llm.py#L600)
- [Resolve completed decisions and submit subsequent requests](https://github.com/ved-2004/Gary-2/blob/93a4d0dac630461cbbb1d3e6e07b156f0b1bb7a3/simulation/core/runner.py)
- [Live rendering loop and trajectory saving](https://github.com/ved-2004/Gary-2/blob/93a4d0dac630461cbbb1d3e6e07b156f0b1bb7a3/simulation/main.py#L516)
- [Trajectory format](https://github.com/ved-2004/Gary-2/blob/93a4d0dac630461cbbb1d3e6e07b156f0b1bb7a3/simulation/replay/io.py)
- [Static website catalogue](https://github.com/ved-2004/Gary-2/blob/93a4d0dac630461cbbb1d3e6e07b156f0b1bb7a3/landing/lib/replay-catalog.ts)
- [Browser playback cursor](https://github.com/ved-2004/Gary-2/blob/93a4d0dac630461cbbb1d3e6e07b156f0b1bb7a3/landing/components/SimulationReplay.tsx#L594)

Simply keeps the requested React interface and adopts the Python-owned live
action flow. Provider work runs outside rendering. The coordinator commits each ready proposal without waiting for slower peers
and flushes each action to JSONL before publication. Each shopper can request
its next action independently.

`simulation/live/server.py` streams flushed records over local SSE.
`live/protocol.py` validates each record with the existing core log validators
and uses core's `RecordingView`, display transforms and metrics. Reconnects
receive the complete confirmed prefix. React replaces that snapshot and then
accepts contiguous transitions; duplicate, altered or incompatible history is
rejected. A completed stream has the same source hash, states, actions and
metrics as the saved replay export.

The Next.js route is a same-origin transport proxy, not another simulation.
The map, cart, inspector, traffic and totals reuse the replay presentation with
the live cursor following Python's latest committed event. Inspection and
reconnection never call the model. Missing Python service produces an explicit
offline state. Closing a browser does not cancel its Python session.

The SSE browser transport is Simply's addition; Gary-2 does not provide this
browser streaming protocol. New live/model runs use Python-owned `gary2_v1`
action assistance, adapted from Gary-2's `adjust_llm_action`: less-visited moves,
reachable target pickups, duplicate avoidance and checkout steering. Simply
honors requested quantities and its existing two-stage checkout. Each event
retains the original model proposal, raw response, adjustment reason and applied
action. Invalid replies and provider errors do not produce fallback actions.
Historical recordings and model-only experiments retain their original policies.

Assisted runs request one model action per response, with no cached plan bursts.
The React map places static sprites directly at committed grid coordinates;
there is no movement interpolation or walking animation. Replay still selects
ordered saved events, and reconnect restores the latest confirmed state.

Start from the repository root in two terminals:

```bash
npm run simulation:serve --prefix landing
npm run dev --prefix landing
```

Open `/lab`, choose Live simulation, layout A/B and 10–15 shoppers, then Start
live run. The key stays in the root `.env` and is read only by Python. The
shared ledger tracks live UI requests without enforcing its historical $10
campaign limit. Provider rate and quota limits still apply. Pause, resume,
single-round advance and stop operate on the Python session. External command
runs can be observed, with their controls remaining in their owning process.

Canonical JSONL is saved throughout the run. After it ends, Save to recorded
replays explicitly publishes the validated export. Incomplete runs require the
distinct Save partial replay action and retain their stopping status.

Verification commands:

```bash
.venv/bin/python -m unittest discover -s simulation/tests
npm run verify:replay --prefix landing
npm run verify:live --prefix landing
npm run typecheck --prefix landing
npm run lint --prefix landing
npm run build --prefix landing
```
