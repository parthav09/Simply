# Collecting layout and model evidence

## Balanced layout and model experiment

`evaluation.matrix` freezes a two-layout × two-model comparison before collection.
It runs five repetitions of ten fixed profiles in each of four conditions
(200 simulated trips). Models are interleaved within repetition blocks. Each
child remains an ordinary canonical layout study; model contrasts match the
same layout and repetition across children. Both models use `gary2_v2`, so these
results measure assisted system performance. They do not isolate unassisted
model intelligence or the benefit of assistance itself.

```bash
.venv/bin/python -m simulation.evaluation.matrix prepare \
  --directory simulation/runs/studies/my-matrix
.venv/bin/python -m simulation.evaluation.matrix run \
  --directory simulation/runs/studies/my-matrix
# Read-only analysis of saved evidence; no model requests:
.venv/bin/python -m simulation.evaluation.matrix report \
  --directory simulation/runs/studies/my-matrix
.venv/bin/python -m simulation.evaluation.matrix publish \
  --directory simulation/runs/studies/my-matrix
```

The matrix plan, both child protocols, every source recording, source hashes,
primary-metric audits, paired contrasts and a generated `case-study.md` stay in
that directory. Publication adds a compact four-condition summary to Evidence,
with individual recordings and full reports below. Reporting independently
recounts finished shoppers, paid requested products and successful moves from
canonical states/events. It includes unfinished shoppers in all denominators.
Resuming skips completed slots without additional requests. Stopped attempts
are retained and block automatic retries; changed controls require a new study.
Four planned contrasts are reported with block-bootstrap intervals, without
claiming correction for multiple comparisons or validity for real shoppers.

Collection incurs real API charges; preparation and reporting do not. Pilot
runs stay separate from the main matrix. No prior historical recording is
retrospectively enrolled.

The October 29 collection stopped with seven complete runs and one retained
provider-credit interruption. Twelve planned runs were not collected. Its
[published case study](../../landing/public/replays/matrix-48ea3402f27344af949f1002123fe826.md)
is exploratory. An incomplete matrix requires explicit `publish --allow-partial`;
that flag never turns its status into complete or removes the stopped attempt.
To reconstruct published metrics, contrasts, source hashes and audits from
the exported originals without an API key, run:

```bash
.venv/bin/python -m simulation.evaluation.matrix verify \
  --directory landing/public/replays
```

Verification creates only temporary working files, uses no model calls or
writable accounting ledger, and rejects changed source bytes or result values.

Use `evaluation.study` for new studies. It freezes inputs before any requests,
then runs the same identified Python sessions used by the lab. Preparing or
reporting makes no model calls. Execution uses cost tracking without a local
spending cap; it does not alter provider rate or quota limits. The older
`evaluation.run campaign` command retains its explicitly bounded legacy protocol.

## Layout A versus B

First collect a complete-trip pilot in each layout. Both use the same ten
derived benchmark profiles, lists, prices, starting cells, model, prompt,
navigation policy, 120-action limit, and concurrency. Layout placement changes.
New studies freeze one unit per unique product and single-action checkout.
Retained older recordings are not enrolled in the new study.

```bash
.venv/bin/python -m simulation.evaluation.study prepare \
  --directory simulation/runs/studies/layout-pilot-v2 \
  --kind layout --models gpt-6-luna --repetitions 1

# Makes paid requests: execute only when ready to collect the pilot.
.venv/bin/python -m simulation.evaluation.study run \
  --directory simulation/runs/studies/layout-pilot-v2
```

Inspect `report.json`, failures, assistance counts and complete-trip cost. Then
prepare a separate five-repetition study; do not silently fold an exploratory
pilot into the confirmatory result.

```bash
.venv/bin/python -m simulation.evaluation.study prepare \
  --directory simulation/runs/studies/layout-main-v2 \
  --kind layout --models gpt-6-luna --repetitions 5
.venv/bin/python -m simulation.evaluation.study run \
  --directory simulation/runs/studies/layout-main-v2
```

Five repetitions are a starting point, not a statistical power calculation.
Inspect the interval width and failure rate before deciding whether more
repetitions are necessary. A new protocol needs a separate directory.

## Comparing models and navigation assistance

Change model only in a fixed layout. The default model study uses Luna and
Terra; both request one decision per action. `model_only` disables policy
adjustments and multi-action plans, so a model-quality comparison is not
confounded by different amounts of Python routing or action batching.

```bash
.venv/bin/python -m simulation.evaluation.study prepare \
  --directory simulation/runs/studies/model-pilot-a \
  --kind model --layout costco_back_anchor \
  --models gpt-6-luna gpt-6.1-terra --policy model_only --repetitions 1
```

Use the same `run --directory ...` command to collect it. For assisted system
performance instead, prepare both models with `--policy gary2_v2`; label that
result as assisted and report the number of adjusted proposals. Compare policies
separately using `--kind assistance --models gpt-6-luna --layout costco_back_anchor`.
An assistance comparison holds the single-action request interface fixed too.
Both configured models use the same generation settings and their own frozen
price snapshots. The report rejects actual model-version drift within an arm.
The seed fixes pair order and scheduling, not deterministic OpenAI responses.

## Reporting and the Evidence tab

```bash
# Read saved records; no new model calls.
.venv/bin/python -m simulation.evaluation.study report \
  --directory simulation/runs/studies/layout-main-v2

# Explicitly publish the report, frozen protocol and every retained replay.
.venv/bin/python -m simulation.evaluation.study publish \
  --directory simulation/runs/studies/layout-main-v2
```

The Evidence tab's controlled-study section displays published layout, model
and assistance reports. Local run history also includes unpublished canonical
logs. Preparation alone creates no run and no result. Existing historical runs
remain descriptive evidence; they are not retroactively enrolled in a study.

The primary outcomes are checkout completion, requested units actually
purchased, and successful movement steps. All shoppers remain in denominators.
The same report shows simulated sales, failures, loops, assistance, overspending,
off-list units purchased, request latency, duration and API costs per completed
trip. Arm cost per checkout pools all retained costs and completed trips; other
arm values are run means. Unknown charges or no checkouts produce an unknown
cost per checkout. Off-list purchases are not automatically
classified as psychological impulse buying.

Arm means include every retained attempt, including stopped recordings. Paired
differences and 95% repetition-block bootstrap intervals use intact completed
pairs only, with excluded/missing pairs counted explicitly. A stopped run makes
the study incomplete and cannot be silently retried. A run can complete its
action window with zero successful shoppers; that is a result, not an exclusion.
Fewer than five complete pairs produce descriptive differences without an interval.
Reports reject changed configuration, missing actual-version evidence in returned
model decisions, protocol substitution and duplicate run identities.

## What can go on a resume

The project can already support an engineering claim about a Python-owned LLM
simulation, live React viewing, inspectable records and verified replay. After
collecting the study, describe the measured outcome with its scope, for example:
“Evaluated two store layouts across 5 paired repetitions with 10 fixed shopper
profiles; measured [observed change] in purchased-list fulfillment and [observed
change] in movement, with checkout completion and uncertainty reported.”
Fill those brackets only from the actual published report. A null result is
still a valid experiment. Simulated sales are not realized retail revenue.

## Fine-tuning later

Save the original model proposal separately from the applied action. Decide
whether training is intended to imitate the model or the assisted policy; mixing
those labels hides what was learned. Split by shopper/cohort and shopping mission
before training. Keep evaluation profiles, lists and held-out store arrangements
out of training and model selection. The current feasible cohort is a development
benchmark, not an independent validation of real shopper behavior.

Compare the untouched open-weight checkpoint with the fine-tuned checkpoint on
the same held-out tasks, prompt/action schema, action limits, decoding settings,
and assistance policy. Report task success, invalid actions, latency, assistance
rate and compute cost together. Record checkpoint, adapter, tokenizer and chat
template hashes when adding that provider. The current implementation does not
yet include an open-weight provider or a training pipeline.
