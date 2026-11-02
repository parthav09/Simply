# Shopper execution review — October 27, 2026

Reviewed Gary-2 main at `93a4d0dac630461cbbb1d3e6e07b156f0b1bb7a3`,
confirmed through its GitHub branch reference, and inspected its current
[agent](https://github.com/ved-2004/Gary-2/blob/93a4d0dac630461cbbb1d3e6e07b156f0b1bb7a3/simulation/agents/llm.py)
and [runner](https://github.com/ved-2004/Gary-2/blob/93a4d0dac630461cbbb1d3e6e07b156f0b1bb7a3/simulation/core/runner.py).

## Findings and changes

Simply previously requested a model decision for every one-cell movement and
every individual grab. The live service hard-coded two concurrent requests for
10–15 shoppers. Its informed prompt supplied a department map but omitted the
assortments visible ahead: product details appeared only next to a shelf.
This combination made navigation expensive and gave the model little local
evidence for approaching particular products.

Gary-2 exposes shelves within six tiles, marks target products, preserves a
public plan and recent history, and submits asynchronous requests. It still
requests individual actions. Its apparent shopping competence also depends on
`adjust_llm_action`, which replaces proposals with target grabs, movement and
checkout. Simply's architecture rules explicitly forbid these replacements.
Gary-2's speed and completion therefore cannot be attributed solely to model
reasoning or copied as an unmodified shopper benchmark.

The new informed revision, `observe-plan-v3`, supplies nearby assortments within
six cells, identifies remaining targets, and retains exact one-cell grabbing
reach. Remote prices and dietary evidence remain unavailable. Informed OpenAI
requests return one public reason and 1–8 explicitly ordered primitive actions.
The prompt asks for needed grabs first and several clear-corridor moves together.
Multiple visible purchases and both checkout actions may share one request.
Baseline prompts retain their frozen single-action contract; Gemini remains
single-action.

Python owns the pending plan and validates every action against the current
observation before applying it. A movement that brings a new assortment within
reach interrupts the tail so the next request can inspect the actual products.
Failure, unexpected state, completion and action limits also discard the tail.
The core never supplies a missing route, purchase, budget decision or checkout.
Valid poor choices, duplicate purchases and overspending remain observable.

Cached plans apply without a network wait, and idle peers may request at the
same time. The default concurrency is ten in the main CLI, session and live
service. Live ticks apply a shopper as soon as its own request is ready, the
same independent pump Gary-2 uses. A slow peer no longer holds back another
shopper's commit or next request. `run()` still waits for a full wave and
commits in roster order for offline compatibility checks.

Waiting ticks do not consume shopper turns or shorten their action allowance.
For planned action runs, `action_planning.action_limit` preserves the smaller of
the requested round limit and turn budget. `requested_max_rounds` retains the
input; `config.max_rounds` bounds scheduler ticks at eight times that input
times the shopper count so one-at-a-time commits cannot clip a peer's
allowance. Historical recordings that used the earlier eight-times-only bound
remain valid. Pause/advance still operates one scheduling tick at a time;
stopping settles already-submitted work and cannot execute a pending tail.

Every primitive remains a separate canonical event and consumes its own turn.
Each event retains the original prompt/response, plan ID, action index and
source request ID. Readers reject changed plan sources, discontinuous indices,
actions differing from the saved response, and duplicated continuation charges.
Tokens and cost are counted once on the source request. Continuations are
explicitly marked as no new request and excluded from unknown-usage counts.
React continues to consume the same canonical states and metrics.

## Verification

The controlled OFFLINE fixture uses the same ten frozen benchmark shoppers and
the same explicit routes, purchases and checkout actions in each execution mode.
It runs the real OpenAI request construction, parsing and metering against a
mocked transport. Fixtures retain `scripted_test` identity. Zero remote API
requests are made; these results measure execution overhead, not model quality.

| Layout | Primitive actions, both modes | Single-action requests | Plan requests | Reduction | Checkouts, both modes |
| --- | ---: | ---: | ---: | ---: | ---: |
| A | 533 | 533 | 128 | 76.0% | 10/10 |
| B | 521 | 521 | 120 | 77.0% | 10/10 |

Per-shopper before/after states, chosen steps, product IDs and outcomes agree
exactly across modes. The fifteen-shopper planned checks also finish 15/15 in
both layouts: A records 758 actions from 179 requests, B records 723 actions
from 163 requests. These are scripted engineering fixtures, not model success
rates or latency measurements.

The regression suite contains 140 tests, including bounded-plan parsing,
physical rejection, interrupted plans, explicit multi-grabs, unchanged bad
choices, unequal plan lengths, per-shopper action limits, stop, proposal-only
isolation, provenance and metering. TypeScript, lint, production build, existing
replay/live contracts and the four full-trip 10/15-shopper legacy workflows pass.
The additional plan verifier compares every exported replay frame and incremental
live frame with Python, including reconnect and final equality.

Reproduce the plan comparison and browser checks without a real key:

```bash
.venv/bin/python simulation/tests/verify_action_plans.py /tmp/simply-plan-check
node simulation/tests/verify_action_plan_replay.cjs /tmp/simply-plan-check
.venv/bin/python -m unittest discover -s simulation/tests
npm run verify:engine --prefix landing
npm run verify:live --prefix landing
npm run typecheck --prefix landing
npm run lint --prefix landing
npm run build --prefix landing
```

Acceptance artifacts from this review are under
`/tmp/simply-action-plans-final-20261027/` and
`/tmp/simply-plan-15-final/`. Existing recordings and published evidence are
unchanged. No new model study or replay was published. Real-model behavior has
not been retested; the user requested continuing with simulation implementation
and offline verification after the live-check approval request.
