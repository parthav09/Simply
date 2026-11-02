# Simulation and evaluation

For new layout, model and navigation-assistance results, use the
[frozen study workflow](docs/controlled-studies.md) in `evaluation/study.py`.
Preparation makes no requests. New study runs use cost tracking without an
app-enforced cap; the older `evaluation.run campaign` retains its explicitly
bounded historical protocol. The [Gary-2 review](docs/gary2-behavior-audit.md)
documents `gary2_v2`, soft shopper budgets and remaining behavior differences.

`core/session.py` is the shared execution path. `main.py` runs the simulation
from a command, exports recordings, or inspects saved evidence in the terminal. GPT-6 Luna through OpenRouter is the default CLI/web model; direct OpenAI remains available with `--provider openai`;
`--provider gemini` explicitly selects the retained Gemini integration.

## Commands (from the repository root)

For live React viewing, start `npm run simulation:serve --prefix landing` and
`npm run dev --prefix landing` in separate terminals, then open `/lab`. The live
tab starts or follows a Python run and streams committed actions while model
requests are pending. Recorded replay remains available in its own tab. See
`docs/gary2-live-reference.md` for the inspected Gary-2 code and browser adaptation.

```bash
.venv/bin/python simulation/main.py --provider openrouter --shoppers 10 --export-web
npm run dev --prefix landing
.venv/bin/python simulation/main.py --replay simulation/runs/YOUR_RUN.jsonl
.venv/bin/python -m simulation.replay simulation/runs/YOUR_RUN.jsonl --agent C0001
.venv/bin/python -m simulation.core.export_replay simulation/runs/YOUR_RUN.jsonl
```

Common options: `--layout`, `--shoppers` (10–15, default 10; smaller offline fixtures are permitted), `--turn-budget`, `--max-rounds`,
`--concurrency` (default 10), `--prompt baseline|informed`, `--seed`, `--output`, `--ledger`, and
`--requests-per-minute`. Zero disables admission pacing; pacing never retries a
failed action. For the low-quota Gemini key, use `--requests-per-minute 8`.
The seed controls experimental grouping/order. OpenAI Responses has no request
seed option; this limitation is explicitly recorded rather than faked.

New live/model sessions use `gary2_v2` navigation assistance and one model
proposal per action. Python favors less-visited cells, collects reachable list
items, avoids fulfilled duplicate pickups and steers stocked carts toward
checkout when lists are complete or turns run low. Each requested product is limited to one unit.
Every adjustment records the original proposal and its reason; provider errors
and invalid replies remain failures. The map shows the latest committed grid
position directly, with no slide or walk animation.

Injected evaluation/test providers retain `model_only` unless assistance is
explicitly selected. Multi-action plan support remains available for those
controlled experiments and historical evidence; it is disabled in new assisted
live/model runs. Test fixtures never replace an unavailable model.

Configure `OPENROUTER_API_KEY` or `OPEN_ROUTER_KEY` in the repository `.env` or process environment. Direct OpenAI uses `OPENAI_API_KEY`.
Gemini uses `GEMINI_API_KEY`. A missing key aborts before turn consumption; an
unavailable provider/model never silently falls back to fixtures.

## Core and UI boundary

The core owns the store, carts, quantities, turns, checkout, and evidence.
Providers return proposals. React replays the exported actions and states through
its map, playback controls, timeline, and shopper inspector. No display
contains a shopping policy or computes independent business outcomes.

The old `ui/grid_ui.py` prints migration instructions. It no longer executes a
separate Tkinter shopping loop. The old Pygame prototype was retired. The lab UI
is in `landing/ui/`. `run.py` is a legacy proposal-only inspection tool, not the
complete-trip launcher.

## Evidence and metric versions

New JSONL files use run schema 2 with an explicit metrics version. Readers retain
schema 1's original summaries and early schema 2 metric interpretation. Inputs are
snapshotted; source CSV changes cannot alter replay. Exclusive file creation
protects existing runs. Interrupted files remain readable and clearly incomplete.

Money uses integer cents and the saved catalogue selling price. Basket value is
separate from checked-out sales. Fulfillment is capped at requested quantities.
Off-list purchases are not claimed to prove impulse intent. Overspending is
allowed and measured. The frozen navigation policy distinguishes assisted
checkout/routes from model-only experiments.

API latency excludes admission pacing where available. Provider execution wait,
round wait, total execution duration, raw provider usage, normalized token counts,
and estimated cost remain distinguishable. Missing usage is unknown, not zero.
Live commits occur in stable shopper order as their proposals become available.
`round_provider_wait_ms` records elapsed round wait at each commit; its maximum
is the observed complete-round duration, with `round_wait_complete` on the last
commit. An interrupted round keeps only its confirmed prefix.

## Prepare the frozen benchmark

```bash
.venv/bin/python -m simulation.evaluation.run prepare
```

The committed `benchmarks/two_layouts_15_v2.json` contains fifteen fixed profiles selected
across style and budget bands, affordable derived lists, shared starting cells,
source fingerprints and reference-route bounds. Every derived list fits within
80% of budget and within 96 reference actions in both layouts. A reference
route establishes feasibility only; it never acts for the model.

Original datasets stay unchanged. Original budget-pressure trips are separate
from the feasible benchmark. The previous three-layout benchmark is retained as
legacy evidence; new experiments use Layout A and Layout B.

## Run and publish an evaluation

```bash
.venv/bin/python -m simulation.evaluation.run campaign --provider openai
.venv/bin/python -m simulation.evaluation.run report
.venv/bin/python -m simulation.evaluation.run publish
```

The campaign freezes its manifest before execution. It uses the same selected
10–15 benchmark shoppers across both layouts with baseline and informed prompts,
then 20 paired behavioral probes (40 decisions). Its main target is the selected
cohort × two layouts × five repetitions. Select the count with `--shoppers`
(default 10). If that protocol cannot fit the budget, retain the pilot rather
than silently reducing the cohort.

Paired runs hold profiles, lists, catalogue, settings and starting cells fixed.
Execution order rotates using recorded seeds. Comparisons reject changed inputs,
engine/provider fingerprints or returned model versions. Baseline-versus-informed
comparisons are separate. Repetition-block bootstrap intervals are conditional on
this fixed cohort; individual actions are not independent experimental samples.

`--directory` chooses a new campaign location. Completed attempts can be reused
on resumption. Aborted attempts are never silently retried. After an explicit
provider/configuration revision, choose a new directory and link the predecessor:

```bash
.venv/bin/python -m simulation.evaluation.run campaign --provider openai \
  --directory simulation/runs/evaluation-luna-v2 \
  --replaces simulation/runs/evaluation-v1
```

Reports keep run IDs, stopping reasons and incomplete attempts. Source evidence
and `report.json`/`report.md` remain local until explicitly published.

Preference recordings use a frozen version-three protocol containing all 40
cases, prompts, profile variants and products. The offline reader re-parses the
original replies and recomputes adherence and paired scores; edited actions or
summary counters are rejected. Reports link the original decision evidence by
SHA-256. Publishing includes that recording alongside the report. A truncated
final record retains intact earlier decisions and an incomplete status. Legacy
preference protocols are preserved separately and cannot silently resume a new
campaign.

Stopping a session blocks queued model requests, including when pacing is off.
Already dispatched calls may finish within the provider timeout. A keyboard
interrupt cancels queued work before shutdown waits, preserves completed rounds,
and records cancellation. An interrupted state mutation that never reached the
log remains a partial recording rather than an invented final state.

## Budget controller

The persistent campaign ledger under `simulation/runs/` is shared across providers
and execution modes. Its historical filename is `gemini_campaign.sqlite3`; it now
also records OpenAI requests. Ordinary CLI and live sessions use tracking only:
the old $10 campaign limit does not block their requests. Atomic reservations
and retained reservations for unknown charges still support accounting. Cached
reads/writes and reasoning tokens are accounted for when reported. Provider rate
and quota limits remain independent of this local ledger.

The older `evaluation.run campaign` command retains its frozen $10 campaign budget. The
baseline, informed/probe and main stages have separate admission allowances.
The controller stops rather than silently shortening an experiment. An insufficient
allowance or quota yields a pilot/incomplete report, not a claim of completion.
New `evaluation.study` and `evaluation.matrix` sessions track API costs without
that local cap. Provider billing credits, rate limits and quota still apply.

Report generation opens an existing ledger read-only. If it has moved or become
unreadable, a hashed campaign checkpoint supplies its recorded totals and time;
without either source, totals remain unknown. Reports never create an empty
ledger to replace missing accounting evidence. Resuming execution requires the
original ledger path and rejects spending history reduced below its saved
checkpoint. A saved report snapshot does not authorize a fresh spending budget.

Both schema-two comparison commands verify engine/provider controls, shared
starting cells and actual returned model versions. Missing version evidence in
a real provider response blocks a controlled comparison; it is not filled from
the requested model name.

## Offline verification

```bash
.venv/bin/python -m unittest discover -s simulation/tests -v
node landing/scripts/verify-replay.cjs
.venv/bin/python simulation/main.py --provider fake --shoppers 15 --max-rounds 2
```

Test fixtures are deliberately scripted and identified as such. Offline checks
establish software contracts; real-model task success requires a live campaign.
Neither scripted tests nor model preference checks validate real customer behavior.

## Testing Terra

The React lab can select `gpt-6-luna` or `gpt-6.1-terra` before a new run.
For a command-line run, use `--provider openai --model gpt-6.1-terra`. Both
models use the same engine, informed observations and decision parser. The
selected model and its own price snapshot are frozen in the run header;
reservations and usage charges use that snapshot. Ordinary runs track cost
without enforcing the historical campaign cap.
Existing recordings and sessions never change models when the dropdown changes.

The informed prompt states the top-left coordinate system and each legal move
destination. These are observations, not a route solver or purchase override.
The baseline prompt remains byte-for-byte verified against its frozen requests.
