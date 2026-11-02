# Resume evidence: Simply

Simply now demonstrates agent execution, repeatable evaluation, failure analysis,
and model cost/quality comparisons. It does not yet demonstrate open-weight model
training, held-out generalization, production adoption, or real retail impact.

## What was collected

The frozen October 29 matrix covered two layouts and two models with the same
ten derived profiles, lists, catalogue, prices, starting cells, prompts, 120-action
limit, single-action interface, unique-product rules, and `gary2_v2` assistance.
Models were interleaved within repetition blocks. Source records preserve model
proposals separately from applied adjustments.

Seven runs completed. OpenAI credits were exhausted in the eighth, which remains
included in arm averages. This is **80 attempted simulated trips and 70 completed
checkouts**, not the planned 200 trips. Twelve runs were not collected. Two
separate complete-trip pilots are excluded from main estimates. The original
historical A/B demonstrations are also excluded and retain their own rules.

## Measured observations

**Model comparison in Layout A:** two complete paired repetitions, 20 trips per
model. Both models completed 20/20 checkouts.

| Measure | Luna | Terra |
|---|---:|---:|
| Requested products actually purchased | 96.2264% | 99.0566% |
| Moves per shopper, including all shoppers | 53.70 | 42.00 |
| Estimated API cost per completed trip | $0.05709545 | $0.46902060 |
| Requests with an adjusted action | 7.9378% | 5.6410% |

Luna's observed API estimate per checkout was **87.8267% lower**, calculated as
`100 * (1 - 0.05709545 / 0.46902060)`. Its purchased-list fulfillment was 2.8302
percentage points lower. This is a cost/quality tradeoff, not evidence of model
equivalence or an improvement in unassisted intelligence.

**Layout comparison with Terra:** two complete paired repetitions, 20 trips per
layout. Both layouts completed 20/20 checkouts. Layout B used **32.95 versus 42.00
moves per shopper (21.5476% fewer)** and **$0.38441120 versus $0.46902060 estimated
API cost per checkout (18.0396% lower)**. Purchased-list fulfillment was 100% in B
and 99.0566% in A. These are exploratory observations from this fixed cohort.

Luna's Layout B arm includes the provider-interrupted recording, producing 10/20
completed checkouts and 45.2830% purchased-list fulfillment in its all-attempt
average. This is **not an interpretable model/layout-quality drop**: the credit
interruption prevented payment. Its intact paired comparison has only one pair.
The full source report exposes both summaries rather than dropping the failure.
No comparison has the five complete blocks required for the planned interval.

## Resume wording

Use the engineering bullet and one outcome bullet appropriate to the role:

- Built a Python/React LLM-agent simulation with validated shopping actions,
  live SSE, auditable event records, and deterministic replay; developed frozen
  layout/model evaluations and collected 80 attempted simulated shopping trips.
- Compared Luna and Terra across 20 matched simulated trips per model in a fixed
  layout; observed 87.8% lower estimated API cost per checkout with Luna, alongside
  96.2% versus 99.1% purchased-list fulfillment.
- Across two paired Terra simulation repetitions, measured 21.5% fewer movement steps and
  18.0% lower estimated API cost per checkout for Layout B, with 20/20 completed
  checkouts and 100% requested-product fulfillment.

Keep “simulated,” the comparison scope, and “estimated” for costs. Do not claim
statistical significance, a completed five-repetition study, real revenue uplift,
or a fine-tuned model. The same ten profiles are repeated; trips are not
independent people. Navigation assistance remains part of both model systems.

## Verify every number

- Open the local Evidence page at `http://localhost:3000/evaluation`.
- The headline table groups Luna, Terra, Qwen 4B baseline and fine-tuned Qwen
  into model rows, with metric sub-rows and Layout A/B columns. Its default is
  **one completed run per model/layout** from the earliest intact main-study
  repetition: 4 runs and 40 attempted trips. Qwen rows are **N/A**, not zero.
- Switch “Results shown” to completed-run averages (7 runs, 70 trips, unequal
  cell sample sizes) or all main-study attempts (8 runs, 80 trips, including the
  provider-credit interruption). The earlier resume metrics above use the
  indicated paired/averaged subsets; they do not all describe the default single
  repetition. Every cell discloses its sample count and source recordings.
- The distribution plot retains **13 recordings / 130 attempted trips**: the
  8 main attempts, 2 pilots, 2 historical demonstrations and the separate
  OpenRouter rate-limit interruption. Each run has its own row, trip points and
  median / interquartile range. These ranges are not confidence intervals.
- The [dashboard export](../../landing/public/replays/evidence-dashboard.json)
  contains the three complete table views, all per-trip observations and source
  hashes. All calculations are Python-authored; React only selects views.
- In “Inspect the same profile in both conditions,” choose a layout or model
  comparison and repetition. The outcome chart includes every retained attempt;
  the effort chart uses only intact completed repetition pairs. Choose a profile
  for its paid fulfillment, checkout outcome, moves, submitted requests, trip API
  estimate and original recording links. Expand the paired table for exact values.
  These are descriptive within-profile comparisons, not additional independent
  samples or significance tests. Unknown trip charges remain unknown.
- Read the [case study and source links](../../landing/public/replays/matrix-48ea3402f27344af949f1002123fe826.md).
- Inspect the [full result and per-run audits](../../landing/public/replays/matrix-48ea3402f27344af949f1002123fe826.json).
- Inspect the [frozen matrix plan](../../landing/public/replays/matrix-48ea3402f27344af949f1002123fe826.protocol.json).

```bash
# Rebuild the published result from original recordings; no model calls.
.venv/bin/python -m simulation.evaluation.matrix verify --directory landing/public/replays
# Reconstruct the dashboard from its exported, hashed canonical sources.
.venv/bin/python -m simulation.evaluation.dashboard verify
# Re-export existing local recordings after deliberately adding real results.
# This makes no model calls and never edits the source recordings or ledger.
.venv/bin/python -m simulation.evaluation.dashboard publish
```

Source reconstruction validates hashes and contracts and independently counts
paid requested products, finished shoppers and successful moves. The case study
links exact failed events, missed requested products and unpaid baskets. API
accounting reservations for unknown charges remain intact.
Per-profile measurements live in `runs[].audit.profiles`; frozen-identity matches
and Python-computed differences live in `comparisons[].profile_pairs`. Each pair
retains both source run IDs and its repetition. An unfinished shopper in a completed
run remains eligible; a provider-interrupted run is visible but not paired.

Gary-2 inspired the navigation/recording pattern. Simply's own contributions
include its React SSE/replay bridge, execution/evidence contracts, Python-owned
accounting and metrics, and controlled evaluation workflow.
