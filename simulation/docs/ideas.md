# Ideas

Running notes for the presentation. Not product evidence: these are observations and open questions, not findings. Written 2026-11-17.

## Persona-versus-behaviour consistency (eval idea)

**Question:** do models act on the profile fields they are given, or on assumptions they infer from the profile (for example "family on a budget")?

### What we saw
Source runs: `or-v3-gpt-6.1-terra-20261117` and `or-v3-gpt-6-luna-20261117` (Layouts A and B, ten fixed profiles, one repetition).

Shopper: Isabella Rossi (C0007). Low price sensitivity (2/5), brand loyalty 1, coupon use "sometimes", impulse probability 0.45, `impulsive`, no shopping list, stock-up trip, household of 4, $113 budget (largest in the cohort).

| | Terra | Luna |
|---|---|---|
| Off-list units | 12 (A), 12 (B) | 0 (A), 0 (B), 0 (B re-run) |
| Grab stops with an impulse item | 4 of 8 (A), 5 of 8 (B) | 0 of 6 (A), 0 of 7 (B) |
| Off-list spend (A) | about $58 of $113 | none |
| Reasons using "affordable" / "within budget" wording | 10 of 23 | 0 of 10 |

- Expected impulse stops at p=0.45 over 8 stops: about 3.6. Her chance of doing as well or better by luck is 0.52 (A) and 0.26 (B), so she is **not a statistical outlier**.
- The extra off-list volume is mostly **several units at one stop**, not more stops with an impulse.
- Terra's off-list items were cheap, family-appropriate and within budget. No loops or rejected actions (81 of 81 actions applied).

### Why different models differ
This is the thing the eval measures, so a gap between models is not a contradiction.
- Terra may be reading the fields that point toward buying (`impulsive`, no list, big budget, stock-up trip). That would be following the profile correctly.
- Luna may be under-reading it, for example by treating the list as the whole task.
- Neither model is the baseline. We have no real shopper to compare against, and 0.45 is a number we chose.

### What we cannot claim
- Terra over-buys. Per visit it is close to expected.
- Luna is more realistic. Zero impulses for an impulsive profile is also questionable.
- Terra acts on stereotypes. We saw the wording, not the cause, and a model's stated reason is not a reliable record of why it acted.
- Anything strong from this sample: ten shoppers, one repetition, no request seeding.

### How to answer "is 12 expected?"
> We don't yet know. It is consistent and plausible: it happened in both layouts, the items fit her profile and budget, and nothing looked broken. Her per-visit rate is close to her stated 45%. The other model took none for her, and that gap is exactly what we want to evaluate. One run per layout can't settle it, so the next step is a controlled test that changes one profile field at a time.

Likely follow-ups:
- *"So is Terra wrong?"* Can't say. No ground truth.
- *"Why not trust its reasons?"* Explanations are hints, not proof.
- *"What settles it?"* Vary one field at a time with a few repeats per model.

### Proposed test (not run, not authorized)
- Change one profile field at a time and keep everything else fixed: `price_sensitivity` 1 vs 5, `uses_shopping_list` True vs False, household size.
- A model that acts on a field changes its off-list count when that field changes. One that acts on stereotypes does not move, or moves for the wrong field.
- A few repetitions per model, to separate the field's effect from sampling noise.
- Needs new paid runs, so ask first. Do not touch prompts, `core/` or collection to chase it.

### Basic sanity checks (already satisfied)
No loops, no rejected or invalid actions, spend within budget, items fit diet and price, and each reason names a product and a motive.

### Possible metric (not built)
Pooled impulse rate per shelf visit against stated probability, bucketed by probability. Skip per-shopper outlier flags: most shoppers have 1 to 10 stops. A "shelf visit" needs a Python-owned definition first, and the planned shelf-adjacency rule will change it.

## Open items
- The user's "spend thrift" wording was ambiguous (frugal vs spendthrift). Confirm which was meant.
- The numbered note list had a blank item 3. Ask what was meant to go there.
- Layout B thrift-wording count not checked.
