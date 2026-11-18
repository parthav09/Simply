# Fine-tuning assets (Qwen2.5-7B-Instruct, QLoRA)

## Run order (Google Colab, A100)
1. `notebooks/01_finetune_qwen25_7b_impulse_v2.ipynb` → Run all → downloads `simply_qwen25_7b_impulse_v2_adapter_*.zip` (~2 h).
2. `notebooks/02_run_layout_A.ipynb` → Run all → upload that adapter ZIP → downloads `simply_impulse_v2_layout_A_*.zip` (~1 h).
3. `notebooks/03_run_layout_B.ipynb` → same for Layout B.

Each notebook prints a "PASTE THIS INTO THE SIMPLY CHAT" summary. Bring the result ZIPs back to build the replay.
Rebuild the notebooks with `python3 notebooks/build_colab_notebooks.py` (refuses to build if the dataset is stale).

## Contents
| Path | What it is |
|---|---|
| `impulse_v2/` | **Current dataset** `simply_impulse_teacher_v2` (1,724 / 251 / 360). `generate.py` rebuilds it in ~1 min. |
| `../finetuning_demo/` | Original `offline_demo_v1` (234 / 58 / 60). Hash-bound to its location; do not move. |
| `adapters/` | Nov 4 pilot + smoke adapters (git-ignored). Used by the earlier MPS/MLX runs. |
| `docs/` | Walkthrough and interview guide written for the pilot. |
| `legacy/` | Zipped v1 data for the old upload-based notebook. |
| `../../notebooks/frozen_source.py` | The one frozen Simply core (commit `584298d`, `informed` prompt, `guided_nav_v2`) used by the generator and all three notebooks. |
| `../../simulation/evaluation/impulse_eval.py` | Impulse rules, offline per-decision scoring and trip reports. |

## impulse_teacher_v2 in one paragraph
A deterministic teacher drives 35 non-benchmark shoppers × 3 visible styles × 2 layouts (210 trips, all finished)
through the real Python core with the frozen prompt and `guided_nav_v2`. Only proposals that core applied unchanged
become rows. An impulse grab happens only when the prompt allows it (no list item in reach, list not finished,
urgency low/medium) and the item fits the shopper's visible style, diet, allergy, alcohol and health preferences,
department, price and budget slack. Each style is capped: planner 1 cheap healthy-or-treat item, mixed 1,
impulsive 2. Teacher trips average 0.21 / 0.84 / 1.94 impulse units for planner / mixed / impulsive. Splits are by
base shopper. The 15 benchmark shoppers used in the Layout A/B runs never appear in any split.

## Evals
* **Offline, per decision** (notebook 01, before and after training, then test once): JSON validity, observation
  validity, exact agreement; list-grab and checkout recall; impulse grab-vs-pass precision/recall/F1 and grab rate
  by style; rule violations (impulse while a list item is reachable, list complete, urgent, over cap, unfit item).
* **Whole trips** (notebooks 02/03): Python `off_list_units` per trip and by style, share of trips with an impulse,
  impulse spend, proposed vs applied vs assist-overridden vs core-rejected off-list grabs, plus guardrails
  (checkout completion, list fulfillment, invalid decisions).

Limits: the labels are rules, not people. One run per layout is descriptive, with no significance claim.
