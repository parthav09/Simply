# Fine-tuning Qwen2.5 7B

Goal: teach a small open model to make shopper decisions in Simply's format, including sensible
impulse buys, and then compare it with the hosted models in the same simulation.

Method: **QLoRA supervised fine-tuning.** The base model is frozen and stored in 4-bit, and a small set
of adapter weights is trained on (prompt → correct action) examples. Loss is computed only on the
answer tokens.

## Run order (Google Colab, A100)

1. `notebooks/01_finetune_qwen25_7b_impulse_v3.ipynb`: trains and downloads the adapter ZIP (~2 h).
2. `notebooks/02_run_layout_A.ipynb`: uploads the adapter and runs 10 shoppers on Layout A (~1 h).
3. `notebooks/03_run_layout_B.ipynb`: the same on Layout B.

Rebuild the notebooks with `python3 notebooks/build_colab_notebooks.py`. It refuses to build if the dataset is out of date.
Results come back as ZIPs in `colab_runs/`.

## Where the training data comes from (`impulse_v3/`)

There's no real shopper data, so a **rule-based teacher** plays the shopper. It drives 35 shoppers × 3 shopping
styles × 2 layouts (210 trips) through the real Python engine. Only actions the engine accepted unchanged
become training rows: 1,753 for training, 292 for validation and 284 for testing.

- An unplanned grab is allowed only when the shopper has time left and the item fits their impulse
  level, diet, allergies and budget. The teacher's grab rate by impulse level is 23% / 12% / 4% / 0%.
- Splits are made **by shopper**, so the same person never appears in both training and test.
- The 15 benchmark shoppers used in the Layout A/B runs never appear in the training data.

`python impulse_v3/generate.py` rebuilds it in about a minute.

## How it is evaluated

- **Per decision** (notebook 01, before and after training): valid JSON, legal action, agreement with the
  teacher, list-item and checkout recall, and impulse grab precision/recall.
- **Whole trips** (notebooks 02/03): checkout completion, list fulfilment, invalid actions, and impulse buys
  per trip, computed by Python.

Matching the teacher on single steps isn't the same as finishing trips. In a real trip, one wrong turn
leads to situations the model never saw in training, so whole-trip results are the ones that count.

## Limits

- The labels come from rules, not people. The model learns to copy the teacher, not real shoppers.
- One run per layout gives descriptive results only.
- To isolate the adapter's effect, compare against the **same base model without the adapter**. A hosted Qwen also
  differs in serving setup.

## Other folders

| Path | What it is |
|---|---|
| `impulse_v2/` | First attempt, replaced by v3. Kept for history. |
| `../finetuning_demo/` | The earliest small demo dataset (352 rows, movement-heavy). |
| `adapters/` | Nov 4 pilot adapters (git-ignored). Used by the local Mac runs (`simulation/docs/local-qwen.md`). |
| `legacy/` | Zipped demo data for the older notebooks `Simply_Qwen3_4B_QLoRA_Colab.ipynb` and `Simply_Qwen2_5_7B_QLoRA_Colab.ipynb`. |
| `notebooks/frozen_source.py` | The frozen copy of Simply's engine that every notebook uses. |
| `simulation/evaluation/impulse_eval.py` | The impulse rules and scoring. |
