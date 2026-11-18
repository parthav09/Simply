# Fine-tuning assets (Qwen2.5-7B-Instruct, QLoRA)

## Run order (Google Colab, A100)
1. `notebooks/01_finetune_qwen25_7b_impulse_v3.ipynb` → Run all → downloads `simply_qwen25_7b_impulse_v3_adapter_*.zip` (~2 h).
2. `notebooks/02_run_layout_A.ipynb` → Run all → upload that adapter ZIP → downloads `simply_impulse_v2_layout_A_*.zip` (~1 h).
3. `notebooks/03_run_layout_B.ipynb` → same for Layout B.

Each notebook prints a "PASTE THIS INTO THE SIMPLY CHAT" summary. Bring the result ZIPs back to build the replay.
Rebuild the notebooks with `python3 notebooks/build_colab_notebooks.py` (refuses to build if the dataset is stale).

## Contents
| Path | What it is |
|---|---|
| `impulse_v3/` | **Current dataset** `simply_impulse_teacher_v3` (1,753 / 292 / 284). `generate.py` rebuilds it in ~1 min. |
| `impulse_v2/` | Superseded first attempt (guided_nav_v2 prompt). History only. |
| `../finetuning_demo/` | Original `offline_demo_v1` (234 / 58 / 60). Hash-bound to its location; do not move. |
| `adapters/` | Nov 4 pilot + smoke adapters (git-ignored). Used by the earlier MPS/MLX runs. |
| `docs/` | Walkthrough and interview guide written for the pilot. |
| `legacy/` | Zipped v1 data for the old upload-based notebook. |
| `../../notebooks/frozen_source.py` | The one frozen Simply core (commit `0967ac3`: impulse-aware `informed` prompt, `guided_nav_v3`) used by the generator and all three notebooks. |
| `../../simulation/evaluation/impulse_eval.py` | Impulse rules, offline per-decision scoring and trip reports. |

## impulse_teacher_v3 in one paragraph
A deterministic teacher drives 35 non-benchmark shoppers x 3 styles x 2 layouts (210 trips, all finished) through the
real Python core with the frozen impulse-aware prompt (it shows `impulse_buy_probability` and `shopping_style`) and
`guided_nav_v3`. Only proposals that core applied unchanged become rows. An unplanned grab happens only when the prompt
allows it (urgency low/medium, more than 15 turns and 30% left; allowed after the list is complete) and the item fits
the visible probability tier (>=0.40 up to 2 items, >=0.20 one, >=0.10 one cheap, <0.10 none), diet, allergy, alcohol,
health, department, price and budget slack. Teacher grab rate by tier: 23% / 12% / 4% / 0%. Splits are by base shopper;
the 15 benchmark shoppers used in the Layout A/B runs never appear. Frozen source: commit `0967ac3` + this work's CUDA
serving and eval modules (`notebooks/frozen_source.py`).

`impulse_v2/` (guided_nav_v2 prompt, style-only rules) is superseded and kept only as history; its generator no longer
reproduces because the shared rules in `impulse_eval.py` moved to v3.

## Evals
* **Offline, per decision** (notebook 01, before and after training, then test once): JSON validity, observation
  validity, exact agreement; list-grab and checkout recall; impulse grab-vs-pass precision/recall/F1 and grab rate
  by style; rule violations (impulse while a list item is reachable, list complete, urgent, over cap, unfit item).
* **Whole trips** (notebooks 02/03): Python `off_list_units` per trip and by style, share of trips with an impulse,
  impulse spend, proposed vs applied vs assist-overridden vs core-rejected off-list grabs, plus guardrails
  (checkout completion, list fulfillment, invalid decisions).

Limits: the labels are rules, not people. One run per layout is descriptive, with no significance claim.
