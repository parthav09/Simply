# Simply architecture rules

## One authoritative simulation
Python core is the sole authority for action application, state transitions,
run history, accounting, and outcome metrics. The configured provider (default
GPT-6 Luna; GPT-6.1 Terra is selectable for testing) proposes decisions. The React lab displays the same identified run
and ordered events. It must never generate purchases, routes, checkout outcomes,
or experiments. Playback, seeking, filtering, and animation cannot change
business state. No recording means an honest empty state, never a scripted fallback.

## Folder responsibilities
- `landing/`: React/Next.js product website, recorded showcase and evidence.
- `landing/ui/`: React lab map, playback controls, inspector and report views.
  Components own display state, never shopping logic or business state.
- `simulation/core/`: working session, physical validation, actions, accounting,
  logs, export and shared metrics. No UI or website imports.
- `simulation/agents/`: profiles/state types, prompts, response schema and model
  integration. Mutations delegate to core; no independent action executor.
- `simulation/evaluation/`: frozen inputs, controlled probes and study orchestration.
- `simulation/ui/`: deprecated compatibility helpers only. Do not add a desktop UI.

## Product workflow
Use a run → record → React replay pattern, with Simply's own design and
validation. Run the model simulation from a Python command, save canonical
records, explicitly export selected recordings, and display them in the web app.
The product is a React web app, not a Pygame/Tkinter desktop application.
The local Python service may stream flushed canonical records into the lab.
React may request a Python session or lifecycle control through the local API;
it must not apply shopper actions or invent outcomes. Live and replay views use
the same Python state and metrics. Reconnecting never starts a new model run.
Simply's SSE bridge adapts the Python-owned live flow to React; React never
owns simulation state.
New live/model sessions use the versioned Python-owned navigation assist
(`guided_nav_v2`; `guided_nav_v1` stays valid for older recordings):
avoid repeated routes, collect reachable list items and steer toward checkout.
Use one model proposal per action; do not burst through multi-action plans in
live runs. Record original proposals and every applied adjustment. No browser
shopping policy or budget enforcement. Model-only experiments and historical
recordings retain their frozen policy. Fixtures keep their identity and stay
explicit test tools, never a fallback for a live model.

Live and ordinary CLI sessions track API costs without an app-enforced spending
cap. Preserve ledger history and unknown-charge reservations. Explicit controlled
studies may opt into their frozen campaign budgets; never silently apply those
budgets to manual runs. Provider rate and quota limits remain separate.
Shopper dollar budgets and acceptable prices are soft preferences: record valid
overspending, never reject a physical pickup or checkout solely for its price.
New controlled layout/model studies use evaluation.study, frozen inputs, one
decision per action, and identical assistance policies across model arms.
New live, CLI and study runs use unique product targets (one unit per SKU),
reject duplicate pickups, and finish payment in one checkout action. Freeze
`unique_single_checkout_v1` in each run. Legacy quantity/two-phase rules exist
only for reading historical evidence and explicitly identified regression fixtures.

Run Python, architecture, type, lint, build and React replay equivalence checks
when changing engine, evidence, export or presentation. Preserve pre-existing
uncommitted work. Never print credentials or put them in exported evidence.

## Current experiment scope
New runs use Layout A (costco_back_anchor) and Layout B (neighborhood_express),
with 10–15 shoppers (default 10). Comparisons use the same frozen cohort across
both layouts. Smaller explicit offline fixtures are allowed. Preserve historical
recordings and their original counts/layouts while retained; never relabel them
to fit new scope. The user-requested cleanup retains only the newest successful
Layout A run and newest successful Layout B run. Older run artifacts and project
archives were removed; never restore them as fallback evidence. Preserve the API
accounting ledger independently of recording cleanup.
The subsequently authorized October 29 experiments retain every canonical study
attempt and both separate pilots, including the provider-credit interruption.
Do not apply the earlier two-recording cleanup to these study sources. The user
confirmed no further paid collection after credits were exhausted. Published
findings remain exploratory and the planned five-repetition matrix is incomplete.

## Model selection
Live OpenAI runs may explicitly select GPT-6 Luna or GPT-6.1 Terra. Freeze the
model and its matching price snapshot per run. Never change an active run from
a dropdown or label a historical run as a different model. Store previews are
explicitly not started and must make no model requests or saved run records.

## OpenRouter migration and current collection
The user subsequently authorized OpenRouter collection with the configured
OPEN_ROUTER_KEY (OPENROUTER_API_KEY is also supported). New web/CLI sessions
default to OpenRouter; direct OpenAI remains explicitly selectable. Freeze dated
model IDs and the standard OpenAI endpoint, disable fallbacks and response-healing
plugins, and retain returned serving identities. Keep frozen token-price estimates
separate from OpenRouter-reported charges. Never print credentials.
The current authorized study is exactly FOUR runs: Luna once on A, once on B;
Terra once on A, once on B; ten fixed profiles per run, one repetition only.
This supersedes the earlier proposed five/two repetitions for this new study.
Keep this study separate from the historical direct-OpenAI matrix and retain its
records, including any failures. The exact Qwen/Qwen3-4B-Instruct-2507 baseline is
pending because it was absent from the OpenRouter catalogue; the user explicitly
chose to run Luna/Terra and leave Qwen pending. Fine-tuned Qwen is future work.

The latest user request uses the existing direct-OpenAI results for Evidence;
do not launch the pending OpenRouter study as part of that dashboard update.
The headline table defaults to the earliest intact main-study repetition (one
Luna and Terra run on each layout), with explicit completed/all-attempt averages.
Show Qwen 4B baseline and fine-tuned Qwen as N/A until real records exist.
Distribution views retain every existing recording separately; never pool pilots,
historical cohorts or the OpenRouter rate-limit attempt into headline estimates.

## November 3 Qwen authorization (supersedes earlier Qwen-pending scope)
The user explicitly authorized replacing the earlier Qwen-pending restriction
and executing exactly TWO paid OpenRouter Qwen2.5 7B Instruct baseline runs:
one on Layout A and one on Layout B, ten fixed synthetic shopper profiles per
run, one repetition. Sending these synthetic simulation profiles and prompts
to OpenRouter / Phala is authorized. Use the prepared frozen study
`simulation/runs/studies/qwen25-7b-ab-20261102` if its controls still match.
Retain all attempts and charges. Compare the recorded results with existing
direct-OpenAI Luna/Terra evidence, explicitly identifying transport and collection
date differences; do not launch new Luna/Terra runs. The downloaded pilot LoRA
adapter is not part of hosted OpenRouter inference. This authorization replaces
the conflicting earlier statements that Qwen must remain pending or that only
the four Luna/Terra OpenRouter runs are authorized.

## November 4 local Qwen MPS serving
The user authorized serving their saved Qwen2.5 7B pilot LoRA locally through
PyTorch MPS on their Mac. Keep the downloaded adapter unchanged and freeze its
hash, tokenizer/template, training base identity, deployment base revision,
quantization and package versions in each local run. The CUDA NF4 training base
is not directly portable to MPS; the compatible official base with Quanto int4
is a distinct deployment, not bit-identical to Colab or OpenRouter. Use the
`local_mps` provider and `qwen2.5-7b-pilot-mps` model identity. No paid API fallback,
silent CPU inference, truncated observations or invented model outcomes. Local
API fees are zero; hardware, electricity and compute costs remain unmeasured.
Keep inference services on loopback and one generation at a time. Previews load
no model and make no inference requests. Local recorded trips remain distinct
from the controlled OpenRouter baseline and the historical OpenAI studies.

## November 4 MPS pilot layout study
The user subsequently authorized exactly one recorded simulation per active
layout using the served fine-tuned MPS pilot: ten fixed profiles, one repetition,
120 actions per shopper, `guided_nav_v2` assistance and `unique_single_checkout_v1`.
Use `evaluation.study` with `local_mps`, freeze the serving identity, and record
every attempt. Publish finished recordings into Evidence automatically; never
export a changing live snapshot under a final run ID. Retain stopped attempts
and do not automatically retry a failed slot or collect additional repetitions.
This local study makes no paid API calls. Compare it descriptively with existing
results, explicitly preserving hardware and quantization differences.

## November 16 local Qwen attempts and impulse-focused UI
Prompts and assistance stay at their benchmarked values (`informed`, `guided_nav_v2`).
An impulse-aware prompt/assist rework was tried and fully reverted at the user's
request; do not reintroduce it without asking. Two replacement local studies were
started and stopped at the user's request, retaining their partial records:
`qwen25-7b-pilot-mps-ab-20261116` (13 Layout B decisions; MPS is out of scope and
not selected in Evidence) and `qwen25-7b-pilot-mlx-ab-20261116` (32 Layout B
decisions, force-quit; Layout A never started). Evidence still selects the Nov 8
MLX study. The Nov 4 MPS attempt (38 decisions) is retained unchanged. A complete
fine-tuned Qwen MLX Layout B result still needs a new replacement study.
The product UI centres on impulse buys (Python `off_list_units`). React may filter
recorded grabs whose product is absent from the shopper's list for display, but
totals and evidence measures come from Python (`evaluation/dashboard.py`).

## November 16 navigation policy renaming
At the user's request every reference to the earlier reference-project naming was
removed. The assist policy ids are `guided_nav_v1` and `guided_nav_v2`
(constants `GUIDED_V1`, `GUIDED_CURRENT` in `core/navigation.py`); behavior is
unchanged. Saved recordings, protocols, reports and published evidence were
rewritten to the new ids, and their content hashes, protocol fingerprints and
the evidence index were regenerated. This supersedes the earlier "never relabel
historical recordings" rule for this identifier rename only: counts, layouts,
models, prompts, decisions and outcomes are untouched. Do not reintroduce the
old names.

## November 17 decisions: impulse behaviour, replays and shelf visibility
The user reopened the impulse-behaviour work ("get back to work about improving
that behaviour") and approved building on the uncommitted `guided_nav_v3` assist
and impulse-aware prompt edits, replacing the earlier "do not reintroduce"
restriction. `guided_nav_v1` and `guided_nav_v2` are frozen history: recordings
validate their recorded adjustments with the same pure function, so they must
not be deleted. Two OpenRouter Luna/Terra studies (`or-impulse-*-20261117`) froze
the prompt and v3 at launch; do not edit `agents/prompts.py`, `core/` or
`evaluation/study.py` while a study is running, because the engine fingerprint
would no longer match. The Qwen2.5 7B OpenRouter run failed with HTTP 404 (no
endpoint) and is retained; do not retry or substitute without a new instruction.
The Replays tab shows a fixed, documented selection
(`landing/data/replay-selection.json`, guarded by a Python test): the two best
completed runs per model per layout where they exist, chosen by list fulfilment and
failed actions, never by impulse outcome.
Shelf visibility decision (not yet implemented): a product is grabbable and visible
only from a cell adjacent to the product's own cell, with no line-of-sight rule and
no shelf front/back. Implement it as a new frozen rule version recorded in each run,
with the navigation assist updated in the same change, and keep older recordings
verifiable under the old shelf-level rule.
