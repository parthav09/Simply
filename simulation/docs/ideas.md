# Ideas

Running notes for the presentation. Not product evidence: these are observations and open questions, not findings. Written 2026-11-17.

## Persona-versus-behaviour consistency (eval idea)

**Question:** do models act on the profile fields they are given, or on assumptions they infer from the profile (for example "family on a budget")?

### What we saw
Source runs: `or-v3-gpt-6.1-terra-20261117` and `or-v3-gpt-6-luna-20261117` (Layouts A and B, ten fixed profiles, one repetition).

Shopper: Isabella Rossi (C0007). Low price sensitivity (2/5), brand loyalty 1, coupon use "sometimes", impulse probability 0.45, `impulsive`, `uses_shopping_list` false (she still has a written list of 7 must-haves, plus 4 items not on it), stock-up trip, household of 4, $113 budget (largest in the cohort).

| | Terra | Luna |
|---|---|---|
| Off-list units | 12 (A), 12 (B) | 0 (A), 0 (B), 0 (B re-run) |
| Grab stops with an impulse item | 4 of 8 (A), 5 of 8 (B) | 0 of 6 (A), 0 of 7 (B) |
| Off-list spend (A) | about $58 of $113 | none |
| Reasons using "affordable" / "within budget" wording | 10 of 23 | 0 of 10 |

- Expected impulse stops at p=0.45 over 8 stops: about 3.6. Her chance of doing as well or better by luck is 0.52 (A) and 0.26 (B), so she is **not a statistical outlier**.
- The extra off-list volume is mostly **several units at one stop**, not more stops with an impulse.
- Terra's off-list items were cheap, family-appropriate and within budget. No loops or rejected actions (81 of 81 actions applied).

### Terra replicate (2026-11-18)
A second Terra run on Layout A (`or-v3-gpt-6.1-terra-layout-a-replicate-20261118`, same 10 profiles, same settings, same seed) gave the same behaviour: Isabella took 11 off-list units (12 before) with impulse items at 4 of 8 stops both times, and the cohort total was 20 vs 22. Most other shoppers were identical or within one unit. So Terra's multi-unit impulse buying is a stable trait of that model on this profile, not sampling noise. It is still one replicate on one layout, and it says nothing about which model is right. Kept separate from Evidence.

Also found: `evaluation/impulse_eval.py` has a tier rule (impulsive tier: at most 2 extras in the cart). Isabella (p=0.45) falls in that tier and exceeds it. Not yet checked whether Terra's prompt states that cap, so this is a prompt-versus-rule mismatch until confirmed.

### Why different models differ
This is the thing the eval measures, so a gap between models is not a contradiction.
- Terra may be reading the fields that point toward buying (`impulsive`, `uses_shopping_list` false, big budget, stock-up trip). That would be following the profile correctly.
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

## Results section: two things we are still learning (talk track)

Plain-language script for the audience. Both points are open questions, not findings.

### 1. Does the shopper follow who they are, or who the model assumes they are?
"Each simulated shopper comes with a profile: budget, how price-sensitive they are, whether they bring a list, how impulsive they are. We want to know whether the AI actually acts on those fields, or acts on a stereotype it builds from them, like 'a family on a budget'.

One shopper showed it. Isabella is impulsive, has the biggest budget in the group, and has a list of seven must-haves but isn't set to stick to it. One model picked up 12 extra items for her, all cheap and sensible. The other picked up none. Neither is automatically right: we have no real shopper to compare to, and her 45% impulse rate is a number we chose.

Per visit, the first model was close to what we'd expect. The second may be treating the list as the whole job. So this is a difference worth measuring, not a verdict. We re-ran the first model on the same store and shoppers and it did it again (11 extra items against 12), so the pattern is stable for that model, not a fluke. With ten shoppers and a couple of runs we can't say more. The next step is to change one profile field at a time and see whether behaviour moves with it."

### 2. What can the shopper actually see?
"Right now we haven't settled what a shopper can see in the store. In a real shop you notice products within a few steps of you, and a tall aisle doesn't hide the one behind it from the next walkway as much as you'd think.

The idea is to give each shopper a visibility radius: everything within a set number of blocks is visible, including products on the other side of an aisle. That matters for impulse buying, because you can't impulse-buy what you never see, so the layout changes what gets noticed.

We will define the radius in Python and record it in every run, so results stay comparable and older runs still verify under the rule they used."

*Caveat to resolve before building:* the recorded shelf-visibility decision (see AGENTS.md, Nov 17) is that a product is visible and grabbable only from a cell adjacent to the product's cell, with no line of sight. A radius that sees past aisles is a different rule, so it needs to be confirmed as a replacement or as a second, separate rule version. Not implemented.

## Open items
- The user's "spend thrift" wording was ambiguous (frugal vs spendthrift). Confirm which was meant.
- The numbered note list had a blank item 3. Ask what was meant to go there.
- Layout B thrift-wording count not checked.
