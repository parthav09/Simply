# Live execution and Simply's React lab

Simply runs the simulation in a Python process and displays it in React. Provider
work runs outside rendering. The coordinator commits each ready proposal without waiting for slower peers
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

The SSE browser transport streams flushed canonical records. New live/model runs
use Python-owned `guided_nav_v2` action assistance: less-visited moves,
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
