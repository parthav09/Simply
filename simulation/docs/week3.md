# Week 3: saved trips, replay, and offline comparison

All week 3 execution stays offline, as requested. Fake and scripted providers
exercise logging, replay, metrics, and layout comparison locally. The existing
Gemini integration remains available in the project, but is not used for this
work. No live pilot or further data-transfer approval is required to finish it.

Work in five sessions of 1–2 hours. Read a saved event alongside the code;
explain what it means before changing another part of the simulation. Always
specify `--provider fake` for offline execution; the existing runner default is
Gemini.

## Architecture and ownership

```text
CSV -> immutable Customer + ShoppingItem
                     |
              mutable Shopper state
                     |
Grid.observe -> detached before-state + frozen prompt
                     |
           concurrent provider requests
                     |
       decision schema validation for each result
                     |
       ordered turn consumption + Grid.apply
                     |
    detached after-state -> coordinating-thread callback
                     |
    versioned JSONL -> offline replay / pure summaries / comparison
```

Customer preferences describe a shopper; they do not execute behavior. `Shopper`
owns its mutable cart, requirements, turn count, trajectory, and decision history.
`RoundCoordinator` freezes every prompt before making requests, waits for the
responses, and then commits outcomes in shopper order. Workers do not modify
shoppers or write output. `Grid` decides whether an action can actually be applied.

A valid `grab` response can still be rejected because the selected product is not
on a nearby shelf. An attempted decision consumes a turn even if parsing fails,
the provider times out, or the grid rejects it. A successful movement is therefore
a different measure from turns used. Proposal-only mode records responses but
applies no actions and consumes no turns. A missing Gemini key is a fatal
configuration error: that round makes no commits.

Shoppers can finish checkout, exhaust their own turn budget, or have no allowed
actions. The global round limit bounds the entire run. A finished shopper is
classified as finished even if its last turn also exhausted its budget.

The before/after snapshots are copies, not references to live dataclasses. This
matters because a tuple containing mutable cart items is not a deep snapshot.
Changing a live cart tomorrow must not rewrite yesterday's evidence.

## Five learning sessions

### 1. Trace and serialize

Follow one shopper through `Shopper.prompt`, `RoundCoordinator.run`, and
`Grid.apply`. Read the `run_start` and first `decision` lines in a saved run.
Find the shopper's shopping-list quantities, allowed actions, exact prompt, and
before/after position.

Exercise: explain why source customer data, runtime state, and model decisions
are separate. The snapshot-isolation test mutates a cart quantity, a requirement,
and a nested shelf product list; confirm the saved before-state stays unchanged.

### 2. Record full trips

The full-trip runner accepts `--output PATH` and returns that path from `run()`.
Without a path it creates a unique `trip_<UTC timestamp>_<ID>.jsonl` under
`simulation/runs/`. Existing files are never overwritten. Use another name for a
new experiment.

```bash
.venv/bin/python simulation/run_llm_simulation.py \
  --provider fake --shoppers 50 --max-rounds 2 --concurrency 4 \
  --output simulation/runs/week3_offline_50.jsonl
```

Exercise: locate an unsuccessful decision and distinguish malformed JSON, a
provider exception, and a grid rejection. Fake decisions exercise mechanics;
they are not a realistic shopping policy or a rule-based baseline.

### 3. Replay without executing

```bash
.venv/bin/python -m simulation.replay simulation/runs/week3_offline_50.jsonl
.venv/bin/python -m simulation.replay simulation/runs/week3_offline_50.jsonl --agent C0001
```

Replay prints saved positions, phases, actions, outcomes, cart quantities, and
model reasons, followed by a labeled whole-run summary. It does not import the
current store, read CSVs or credentials, call a model, or apply an action again.
Model reasons are recorded output, not a verified account of the model's causes.
The exact prompt and raw response are available in the JSONL file.

Exercise: replay a saved run after editing a copy of a dataset. The trip must
stay identical. Inspect a copied file with its final record removed: it should
show available evidence and an incomplete-run notice, not pretend it finished.

### 4. Measure precisely

Summaries are calculated from saved values by a shared pure function.

| Measure | Definition |
| --- | --- |
| Checkout completion | Finished shoppers / shoppers started. |
| Mean list completion | Mean of each shopper's fulfilled requested units / requested units. Quantities are summed by product and capped at requested quantities. An empty requested list is fully satisfied. |
| Mean successful moves | Applied movement actions / shoppers started, including unfinished shoppers. |
| Turns used | All attempted action-mode decisions, including failures. Proposal-only runs report zero. |
| Mean turns to checkout | Mean attempted turns for finished shoppers only, with the finished count shown alongside. `N/A` when nobody finished. |
| Failure counts | Invalid decisions, provider exceptions, and grid rejections separately. |

Failed proposal-only attempts are counted in the failure breakdown even though
they consume no turns and are excluded from trip-performance comparisons.

List completion uses the final cart even if the shopper did not check out; it is
not a measure of completed sales. Positions are grid coordinates and turns are
simulation steps, not measured real-world minutes. Revenue is outside this pilot.

Exercise: inspect the scripted fixture test. It requests two units, grabs three,
tries an unavailable product, walks to checkout, and checks out. Hand-calculate
completion (100%, capped at two units), moves, one rejection, and all attempted
turns. The test also checks that a cart containing one of two requested units
means 50% completion.

### 5. Compare two layouts offline

Use the same first three customer IDs from the sorted loader, profiles, lists,
catalogue, prompt code, provider, turn budget, round limit, and concurrency. Only
the layout changes. Use `--provider fake`: each run makes at most 120 local
decisions, with no API requests and no credentials required. These runs check
the comparison machinery; they do not evaluate realistic shopper behavior.

```bash
.venv/bin/python simulation/run_llm_simulation.py \
  --layout costco_back_anchor --provider fake \
  --shoppers 3 --turn-budget 40 --max-rounds 40 --concurrency 2 \
  --output simulation/runs/week3_offline_a.jsonl
```

```bash
.venv/bin/python simulation/run_llm_simulation.py \
  --layout neighborhood_express --provider fake \
  --shoppers 3 --turn-budget 40 --max-rounds 40 --concurrency 2 \
  --output simulation/runs/week3_offline_b.jsonl
```

```bash
.venv/bin/python -m simulation.compare_runs \
  simulation/runs/week3_offline_a.jsonl simulation/runs/week3_offline_b.jsonl
```

The two example run files are already saved locally. Replay or compare those
files directly; use new output names if generating another pair, because existing
run files are protected from overwriting.

The comparison rejects changed model, provider, prompt fingerprint, budgets,
concurrency, catalogue, profiles, or shopping lists. It excludes aborted,
incomplete, damaged, and proposal-only runs. Layout-specific catalogue coordinates
are deliberately excluded from the catalogue equality check. Layout geometry and
product placement remain in each file's layout snapshot.

Write a findings note with the question, fixed inputs, summary, two specific
shopper traces, limitations, and one next experiment. A shopper failing to finish
is a finding. Fake-provider loops and a scripted successful trip establish the
engineering behavior and metric arithmetic, not which store layout is superior.
Use the regression fixtures for software examples; they are not model-evaluation results.
The separate TypeScript website simulation is not evidence for these Python runs.

## Saved-run contract (version 1)

A UTF-8 JSONL file contains one start record, decision records, and normally one
end record. Record order is execution order; `sequence` is contiguous across all
rounds and shoppers. Each shopper has at most one event per round.

| Type | Fields |
| --- | --- |
| `run_start` | `schema_version`, `run_id`, `recorded_at`, `provider`, `model`, `prompt_version`, `config`, complete `layout`, coordinate-independent `catalogue`, `shoppers` with customer and initial state snapshots. |
| `decision` | `sequence`, `round`, `agent_id`, `before`, `prompt`, nullable `raw_response`, nullable validated `action`, `outcome`, nullable `failure`, `after`. |
| `run_end` | `status` (`completed` or `aborted`), nullable exception-class `error`, `rounds_completed`, final `shoppers`, and computed `summary` containing each shopper's stopping reason. |

State snapshots contain position, phase, cart items with quantities, nearby
shelves, requirements, allowed steps, turns used, and turn budget. Decision
outcomes are `applied`, `proposed`, `invalid_decision`, `provider_exception`, or
`grid_rejected`. Failed proposals retain raw response text when it exists.

The callback argument is optional:

```python
outcomes = coordinator.run(grid, shoppers, apply_decisions=True,
                           event_callback=record_event)
```

`record_event` runs on the coordinating thread with detached before/after values.
The return remains the existing tuple of `RoundOutcome` objects. The runner adds
round and sequence numbers. The older one-proposal exporter and its format stay
available unchanged.

The start record is flushed immediately and events after each completed round.
Missing credentials produce an aborted record with no committed events for that
round. Write failures stop execution; earlier valid records remain available.
An interruption may leave an incomplete file. Only a truncated final JSON object
without a newline is recoverable; malformed earlier records and unsupported
versions fail with a line number. Readers check state continuity, commit ordering,
turn accounting, and summary agreement. Unicode text separators inside strings
remain part of that record; an interrupted UTF-8 character at the end of the file
does not prevent replaying earlier records. Replay is snapshot playback, not a
promise to regenerate model decisions or resume an interrupted run.

Credentials and environment-file contents are never serialized. Saved prompts
contain the selected shopper summaries and lists. Full local run files stay under
the repository's existing ignored runs directory.

## Verification and optional follow-up

```bash
.venv/bin/python -m unittest discover -s simulation/tests -v
```

The original tests remain, plus focused trip tests for detached snapshots,
ordered callbacks, raw failures, write errors, interrupted files, offline module
execution, malformed evidence, input mismatch, and hand-calculated metrics.
No new dependencies are required.

Use day 6 to finish core work and inspect the least understandable trace. On day
7, choose one observed problem for another offline fixture: for example, a
scripted remove action or a provider failure halfway through a trip. Fake-provider
loops alone do not justify changes to model prompts or memory.
