# Evaluating Simply

This is how runs are compared, what is measured, and what the results can and can't claim.
The current numbers are on the Evidence page (`/evaluation`). They are computed in Python by
`evaluation/dashboard.py`; React only displays them.

## How a fair comparison is set up

A **study** (`evaluation/study.py`) compares one thing at a time: layout, model, or the navigation helper.

1. **Prepare.** Freeze everything first: the 10 shopper profiles and their lists, layouts, model,
   prompt, helper version, action limit (120) and seed. The study plan is saved with a hash.
   No model calls happen here.
2. **Run.** Before each run, check that the code and inputs still match the plan. If anything changed,
   stop and make a new study. Arms run in a shuffled order so provider slowdowns don't all land on one arm.
3. **Keep everything.** Failed and stopped runs are saved and never quietly retried.
4. **Report.** Recompute every number from the raw logs, with no API key needed. Check that the
   model that actually answered matches the one requested.

```bash
.venv/bin/python -m simulation.evaluation.study prepare --directory DIR --kind layout|model|assistance
.venv/bin/python -m simulation.evaluation.study run     --directory DIR   # paid: calls the model
.venv/bin/python -m simulation.evaluation.study report  --directory DIR   # free: reads saved logs
.venv/bin/python -m simulation.evaluation.study publish --directory DIR   # copies results to the site
```

## What is measured

| Question | Measures |
|---|---|
| Did the shopper finish? | checkout completion, share of the list actually bought |
| How did they shop? | impulse buys (`off_list_units`), overspend, moves per shopper |
| Did things go wrong? | invalid replies, rejected actions, provider errors, loops |
| How much did the helper do? | number of adjusted actions |
| What did it cost? | API cost per finished trip, latency (p50/p95) |

Choices that matter:

- **Everyone counts.** Shoppers who never finish stay in every average.
- **Cost per trip pools totals.** It's total cost divided by total finished trips, not an average of per-run
  ratios, so a run with zero finishes can't disappear.
- **Unknown stays unknown.** If a provider doesn't report usage, the cost is "unknown", not zero.
- **Estimated vs charged.** Our own token-price estimate and OpenRouter's reported charge are kept separate.

## Guardrail checks

`evaluation/guardrails.py` reads a saved run and marks each shopper **pass**, **review** or **fail**.

- **Fail:** never checked out, provider error, allergen in an unplanned buy, most actions invalid.
- **Review:** some invalid actions, loops or stuck for 30+ turns, over budget, part of the list unbought,
  unplanned buys that break the impulse-tier caps or don't fit the diet.
- **Pass** only means nothing was flagged. It does not mean the behaviour is realistic.

```bash
.venv/bin/python simulation/evaluation/guardrails.py --dashboard landing/public/replays/evidence-dashboard.json
```

## Speed and cost work

| Problem | Change | Caveat |
|---|---|---|
| Shoppers waited for the slowest one | Each shopper asks and applies on its own (`core/rounds.py`) | Faster wall-clock time. Each shopper's decisions are unchanged. |
| The model couldn't see what was ahead | The prompt shows shelves within 6 cells and marks list items | A prompt change changes results, so prompts are versioned |
| Too many requests | Optional plans of 1–8 actions, dropped if the state changes | Offline test with a scripted shopper: ~76% fewer requests. Turned off in studies so each action is one model decision. |
| Wandering | Visit counts in the prompt, plus the navigation helper | The helper gets credit, not the model. The number of adjustments is reported. |
| Cost surprises | Reserve an estimate before each call, settle after, keep the reservation if usage is unknown (`core/budget.py`) | Ordinary runs track cost with no cap. Studies can opt into a budget. |

## Current evidence

- **Luna and Terra** (OpenRouter, `guided_nav_v3`, Nov 17): one run per layout, 10 shoppers each. The first
  Luna Layout B attempt stopped after an OpenAI content-filter error. It is kept but replaced by a completed re-run.
- **Qwen2.5 7B** is an earlier Nov 3 run with `guided_nav_v2`, because OpenRouter no longer serves it. It's labelled as an earlier run.
- Older direct-OpenAI studies (Oct 29) are kept on disk. They can be rebuilt with
  `python -m simulation.evaluation.matrix verify --directory landing/public/replays`.

## What the results can and can't say

- One run per cell: these are **descriptive observations**, not significant differences.
- Shoppers are synthetic, so there is no ground truth for "realistic". "Impulse buy" means "not on the list".
- The navigation helper was tuned on the same 10 profiles that are reported.
- Different providers and dates add differences that aren't about the model.
- Seeds fix the order of runs, not the model's answers.

## Next steps, with more budget

More repeat runs per cell with confidence intervals. A helper on/off comparison (`--kind assistance`).
Held-out shopper profiles. Checking the impulse measure against real shopping data.
