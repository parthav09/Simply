# Simulation

Multi-agent project. Run it with the repo virtual environment, from anywhere:

```bash
../.venv/bin/python main.py
```

Or from the repo root:

```bash
.venv/bin/python simulation/main.py
```

## Layout

- `core/` — reads and validates the datasets, then builds customer agents
- `agents/` — profile text for the model, the shopper that moves and grabs, and the Gemini call
- `replay/` — saved run playback
- `ui/` — the grid window (`grid_ui.py`) and its auto driver (`driver.py`)
- `main.py` — starts a run

Run the grid UI:

```bash
.venv/bin/python simulation/ui/grid_ui.py
```

One square is one grid cell. Shelves cannot be walked on, shoppers grab
from the aisle cell beside a shelf, and checkout is at the bottom right.

Run concurrent Gemini shoppers from the terminal:

```bash
.venv/bin/python simulation/run_llm_simulation.py --shoppers 8 --turn-budget 80 --concurrency 4
```

Each round first builds a frozen prompt for every active shopper. Gemini
requests then run concurrently. Once every request has returned, the main
thread validates and applies actions in shopper order. A shopper stops after
checkout or when its own turn budget is exhausted.

Datasets stay in `../data`. Secrets stay in `../.env`.
