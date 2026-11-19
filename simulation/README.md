# Simulation: command reference

Run everything from the repository root. See [docs/architecture.md](docs/architecture.md) for how it works.

## Run shoppers

```bash
# Live run (default model: GPT-6 Luna via OpenRouter), then export it for the website
.venv/bin/python simulation/main.py --provider openrouter --shoppers 10 --export-web

# Terra, or direct OpenAI
.venv/bin/python simulation/main.py --provider openrouter --model gpt-6.1-terra
.venv/bin/python simulation/main.py --provider openai

# Offline test with a scripted shopper (no model, labelled as a test)
.venv/bin/python simulation/main.py --provider fake --shoppers 3 --max-rounds 5
```

Common options: `--layout costco_back_anchor|neighborhood_express`, `--shoppers` (10–15), `--turn-budget`,
`--concurrency` (default 10), `--prompt baseline|informed`, `--seed`, `--requests-per-minute`.

Keys go in `.env`: `OPENROUTER_API_KEY` (or `OPEN_ROUTER_KEY`), `OPENAI_API_KEY`, `GEMINI_API_KEY`.
A missing key stops the run. The app never switches to a fake model.

## Inspect and export saved runs

```bash
.venv/bin/python simulation/main.py --replay simulation/runs/RUN.jsonl          # terminal replay, no model calls
.venv/bin/python -m simulation.replay simulation/runs/RUN.jsonl --agent C0001  # one shopper
.venv/bin/python -m simulation.core.export_replay simulation/runs/RUN.jsonl    # publish to the website
```

A partial run needs `--allow-partial`. A test run needs `--allow-test` and stays labelled as a test.

## Studies and Evidence

```bash
.venv/bin/python -m simulation.evaluation.study prepare --directory DIR --kind layout|model|assistance
.venv/bin/python -m simulation.evaluation.study run     --directory DIR   # paid
.venv/bin/python -m simulation.evaluation.study report  --directory DIR   # free
.venv/bin/python -m simulation.evaluation.study publish --directory DIR
.venv/bin/python simulation/evaluation/dashboard.py publish               # rebuild Evidence data
.venv/bin/python simulation/evaluation/dashboard.py verify
.venv/bin/python simulation/evaluation/guardrails.py --dashboard landing/public/replays/evidence-dashboard.json
```

See [docs/evals.md](docs/evals.md) for what these measure. `evaluation/run.py` and `evaluation/matrix.py` are
older study tools, kept so older results can still be rebuilt.

## Cost tracking

Every request reserves an estimated cost in a local SQLite ledger (`core/budget.py`) and settles it after the
reply. If the provider reports no usage, the reservation stays as "unknown". Ordinary runs track cost
with no cap. Provider rate limits still apply.

## Tests

```bash
.venv/bin/python -m unittest discover -s simulation/tests
```

These check the software, not model quality or how realistic the shoppers are.
