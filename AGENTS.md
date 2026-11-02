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
Use Gary-2's run → record → React replay pattern, with Simply's own design and
validation. Run the model simulation from a Python command, save canonical
records, explicitly export selected recordings, and display them in the web app.
The product is a React web app, not a Pygame/Tkinter desktop application.
The local Python service may stream flushed canonical records into the lab.
React may request a Python session or lifecycle control through the local API;
it must not apply shopper actions or invent outcomes. Live and replay views use
the same Python state and metrics. Reconnecting never starts a new model run.
Gary-2's live view is Python/Raylib and its website is recorded replay; Simply's
SSE bridge adapts that Python-owned live flow to React, rather than copying an
existing Gary-2 browser streaming protocol.
New live/model sessions use the versioned Python-owned Gary-2 navigation assist
(`gary2_v2`; preserve `gary2_v1` for historical validation):
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
