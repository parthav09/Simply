# One simulation, multiple views

## Permanent rule

`landing/` is the product page and recorded showcase. `simulation/core/` contains
the working simulation logic. `landing/ui/` contains the React lab interface.
The lab is a web app; `simulation/ui/` contains deprecated compatibility helpers.
The Python core is the sole authority for action application, state, accounting,
run history and metrics. Neither UI generates shopper behavior or outcomes.

Profiles + lists + layout → frozen observations/prompts → concurrent model
proposals → validation → independent core action commits → flushed JSONL evidence →
live SSE projection / browser export / React replay / offline evaluation.

A single session worker owns mutable state. Model workers never mutate shoppers.
React owns only selection, scroll, playback cursor, drawing and animation. Browser
replay controls only affect presentation. Live controls request lifecycle changes
in the same Python session. Python interruptions preserve
existing evidence. A logging failure stops further execution.

## Public execution interface

`SimulationSession` exposes start, pause, resume, advance, stop, run, closed,
path, header, error, control_status, join and an ordered updates queue. `preview_configuration` produces
detached ready-state data without creating a run or provider. The CLI runs the
session, then explicitly exports its records. Core has no UI imports or display
requirement. React consumes exported frames or a live canonical-record stream, never a
provider or independent action executor. The local service calls the core session
interface; the Next.js proxy only transports requests and events.

Providers return `ProposalResult(raw_response, decision, telemetry, continuation)`.
New live/model sessions freeze `navigation_policy=guided_nav_v2` and request one
model action per response. `core/navigation.py` selects adjustments
using frozen state: less-visited moves, reachable list pickups, duplicate
avoidance and checkout steering. List quantities remain respected; no shopper
budget is enforced. `core/actions.py` is still the only mutation boundary.
Each decision records its original model proposal and any adjustment. The log
reader recomputes adjustments from frozen layout/state/history and rejects
altered provenance. Provider errors and invalid replies remain failures.

Injected evaluation/test providers default to `model_only`, where explicit
multi-action plans remain supported and individually validated. Historical
records retain their original configuration and outcomes. A missing policy in
an old recording means model-only. Policies are part of comparison settings.
Fake and scripted fixtures remain explicit test tools, never a live fallback.
The map places static sprites directly at the latest committed grid coordinates;
replay controls select saved states without changing business outcomes.

## Replay integrity

A canonical log snapshots its catalogue, layout, profiles, lists and initial
states. Decision records form an ordered before/after chain. The reader verifies
identities, quantities, physical transitions, fingerprints and final summaries.
An incomplete tail is recoverable; malformed earlier evidence is rejected.

The exporter recomputes all summaries from saved evidence and includes per-event
presentation states/metrics. Each bundle contains the original source SHA-256 and
a hashed payload. The catalogue binds the downloaded bundle hash and provider/run
identity. Browser replay validates these and only selects/applies recorded states.
It does not execute movement rules, route search, shopping logic or accounting.

The golden fixture compares all 25 TypeScript frames with independent Python
view snapshots, including backwards seeking and final outcomes. Dependency checks
prevent a UI import into core or restoration of a browser shopper policy.

## Run → record → replay structure

Simply runs a Python simulation from a command, records canonical trajectories
(raw model proposals and adjusted applied actions), and replays them in a
React/Next.js website. The website plays stored snapshots rather than inventing
a fresh trip. Its Python launcher runs without a desktop window.

Versioned Python assistance policies may override model actions to purchase list
items or pursue checkout; model-only experiments remain separate. The current
default provider is GPT-6 Luna; earlier Gemini evidence is retained separately and
is never relabeled as OpenAI output.

## When the UI runs

The UI code already exists before a simulation starts. The run produces the data
that the UI displays; it does not generate the UI's code or layout afterward.
States are captured as actions happen, and the website displays them later. The
policy is a hybrid of model proposals and recorded rules-based assistance, or
model-only when selected.

Simply implements recorded replay and the subsequently requested live React path:

```text
Python command
  observe -> model proposal -> core validation/application -> recorded state
  repeat until stopping condition -> finalize -> explicit browser export

React lab
  load exported recording -> select event N -> show recorded state N
```

| Concern | Simply implementation |
|---|---|
| Actual model request | `simulation/agents/openai_provider.py`: `OpenAIProvider.request` |
| Validate and apply proposals | `simulation/core/rounds.py` and `simulation/core/actions.py` |
| Flush each applied state into evidence | `simulation/core/session.py`: `_record` |
| Finish the run before optional export | `simulation/main.py`: `session.run()`, then `export_run()` |
| Export the saved inputs, states and Python metrics | `simulation/core/export_replay.py` |
| Read saved state at an event | `landing/lib/replay.ts`: `frameAt` |
| Animate and inspect that state | `landing/ui/ReplayWorkspace.tsx` |

Simply's live tab now follows flushed Python records while the run is executing.
Its reconnect snapshot and contiguous transitions share the export's display
state and metrics. The replay tab retains event seeking and playback independently.
The coordinator applies each ready shopper independently and immediately
submits that shopper's next request; it does not wait for slower peers.
See `live-replay-flow.md` for the live SSE bridge.
The configured model proposes actions; Python applies the frozen navigation
policy and enforces physical and accounting rules. Explicit fake fixtures are reserved for tests,
and a missing API key never switches a model run to a scripted provider.

## Evidence boundaries

A completed execution means its configured stopping condition was reached, not
that every shopper checked out. Report actual completion and fulfillment counts.
The environment uses replenished stock, independent movement, no crowd blocking,
and no checkout queues. Product/persona metadata are sample or synthetic data.
Preference consistency is not validated human realism or a revenue forecast.

## Current scope

New model runs and comparisons use Layout A (Anchor loop) and Layout B
(Express essentials), with a fixed cohort of 10–15 shoppers (default 10). The
version-two benchmark freezes fifteen eligible profiles so each selected cohort
can use the same inputs across both layouts. Older benchmarks and recordings
remain readable with their original layout scope and counts.
