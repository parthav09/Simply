# How Simply works

## The one rule

**The model suggests. Python decides. React only shows.**

- A language model reads what a shopper can see and suggests one action ("move left", "grab P0012", "checkout").
- Python checks that the action is allowed, applies it, and writes it to a log file.
- The website reads that log and draws it. It never decides anything itself.

Because everything goes through one place, the live view, the replay and the metrics all
show the same numbers.

## One decision, step by step

```text
shopper state → prompt → model suggests an action
   → is it a legal action?            (agents/schema.py)
   → navigation helper may adjust it  (core/navigation.py, adjustment recorded)
   → Python applies it                (core/actions.py, the only place state changes)
   → written to the log               (core/run_log.py)
   → live stream / replay / metrics
```

| Step | File | What to know |
|---|---|---|
| Build the prompt | `agents/prompts.py` | Gives the model facts (map, position, list, nearby shelves). No route solving. |
| Check the reply | `agents/schema.py` | Strict JSON. A bad reply is recorded as a failure, never repaired or retried. |
| Run many shoppers | `core/rounds.py` | Each shopper asks the model on its own and doesn't wait for slower shoppers. |
| Adjust (optional) | `core/navigation.py` | The navigation helper (see below). |
| Apply | `core/actions.py` | Walls, shelf reach, duplicate pickups and checkout rules live here. |
| Record | `core/run_log.py` | Append-only JSONL. A new file every run, so old results can't be overwritten. |
| Measure | `core/metrics.py` | Every number is computed from the log. Money is stored in whole cents. |

Every failure is kept in the log: provider error, invalid reply, or an action the store
rejected. A failed action still uses up a turn.

## The navigation helper

Models are bad at walking a grid. A small Python helper (`adjusted_action`) can replace the
model's action, for example to grab a list item that is right there or to head to
checkout when turns are running out.

- The model's original suggestion and the reason for the change are both saved.
- The helper is versioned (`guided_nav_v1`, `v2`, `v3`). New runs use `v3`. Old versions stay so
  old runs can still be checked.
- `v3` leaves the shopper's own unplanned grabs (impulse buys) alone unless checkout is urgent.
- **Honest caveat:** results measure the model *plus* the helper, not the model alone.
  `model_only` runs turn the helper off.

## Shopping rules for new runs (`unique_single_checkout_v1`)

- One unit of each product. Picking up the same product twice is rejected.
- One checkout action pays and ends the trip.
- Budgets are preferences, not limits. Overspending is allowed and measured.
- An **impulse buy** is a paid item that wasn't on the shopper's list (`off_list_units`).

## Live view and replay

- `simulation/live/server.py` streams each saved event to the browser (server-sent events).
  Next.js only passes them through.
- Reconnecting shows the same run again. It never starts a new model run.
- Replay loads an exported run and jumps between saved states. Playback can't change results.
- `npm run verify:replay` checks that the browser shows exactly what Python computed.

## What is fixed per run

The run header stores the model ID, its price, the prompt version, the helper version, the
shopping rules, the store layout and a hash of the agent code. Studies refuse to continue if any
of these changed.

## Limits of the simulation

- Synthetic shoppers and a grid store: no crowds, queues or stock-outs.
- Shoppers are an LLM playing a persona, not real people.
