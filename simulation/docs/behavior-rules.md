# Shopper behavior review, October 28, 2026

## Spending and purchases

Simply has no shopper dollar-budget admission check at pickup or checkout. Each
profile has an explicit budget; it is consistently described as a soft target,
not a wallet balance or rejection rule. Valid over-budget pickups and checkout
remain allowed. No code trims a basket, invents an affordable substitute, or
forces removal to satisfy the budget. Over-budget baskets, paid overshoot and
off-list units are measured. An API spending limit is a separate concept.

The informed prompt revision is `observe-plan-v4-soft-budget`. Earlier prompts
and historical recordings retain their original identity. Personas do not establish that generated choices accurately represent real people.

## Current assistance policy

New live/model sessions use `guided_nav_v2`. The earlier `guided_nav_v1` remains supported
exactly for historical provenance validation. The corrected policy:

1. Prioritizes checkout when it is available and at most 15 actions remain.
2. Picks up a reachable outstanding target, in left/right/up/down shelf order.
3. Redirects unnecessary duplicate grabs toward a less-visited legal cell.
4. Heads toward checkout with a nonempty basket when targets are satisfied or
   fewer than 30% of actions remain, even if the proposal is an impulse grab.
5. Uses legal, less-visited cells to avoid certain empty-basket exploration loops.
6. Preserves other valid choices, including fitting off-list grabs when checkout
   urgency does not take precedence. Spending is not an adjustment condition.

The previous impulse-grab exception could bypass checkout urgency. It is retained
only under the historical policy. New runs also use their effective action limit
for urgency when it is shorter than the shopper's turn allowance.

`test_behavior_parity.py` compares 400 common abstract states with expected
decisions stored in `tests/fixtures/nav-policy-parity.json`. It covers
empty and nonempty carts, target/extra grabs, repeated visits, legal directions,
and early/late checkout. Additional tests cover shelf order, shorter action limits,
over-budget purchase/checkout accounting and one-action model-only requests.
These are software parity checks, not 400 live model trials or a realism study.

## Simplified new-run contract

New live, CLI and controlled-study runs freeze `unique_single_checkout_v1`.
Each requested SKU appears once, a pickup adds one unit, duplicate pickups are
rejected, and one checkout action pays and finishes immediately at a checkout
cell. Original customer CSV files are not rewritten. Budgets remain soft.
Prompts omit already-owned products and describe one-action checkout. Python
applies the same semantics for both models and both layouts.

Retained successful A/B recordings keep their original quantity-aware,
two-phase contract. Their identities and bytes are unchanged; they describe
the earlier system. New studies must not mix those rules with the new contract.

## Rules held fixed and historical compatibility

| Behavior | Simply |
|---|---|
| Requested products | Unique canonical product IDs; one unit per SKU in new runs |
| Checkout | One action on a walkable checkout cell in new runs |
| Removal | The model selects the product ID and removes one unit |
| World | Bounded grid and multi-cell shelf groups; physical validity owned by core |
| Invalid replies | Schema/allowed-action failures are recorded; no fallback purchase or move |
| State transport | Python canonical log, SSE to React, and the same recorded replay |

These rules are held fixed across Simply's layout and model arms. No historical
recording is rewritten to pretend otherwise.
