# Start your first Simply fine-tune in Colab

Start with **Qwen3-4B-Instruct-2507 + QLoRA supervised fine-tuning**. Use
`Simply_Qwen3_4B_QLoRA_Colab.ipynb` and the existing
`data/simply_qwen_finetuning_demo.zip` bundle.

This is a learning experiment. No model has been trained by this notebook's
author, and no tuned-model performance is claimed.

## Why this model and method

Qwen3-4B-Instruct-2507 produces direct non-thinking responses and has an official
Unsloth Colab example. Four billion parameters is a practical first size for a
Colab experiment; it is not a demonstrated optimum for Simply. Earlier discussion
mentioned 8B as a possible experimental checkpoint. Start at 4B now that the
first-run environment is Colab, then compare larger models after the workflow works.

| Method | What changes | First experiment |
|---|---|---|
| Full fine-tuning | All model weights | High resource demand; little justification with this narrow demo |
| LoRA | Small adapters; base stays frozen at normal precision | Useful with more GPU memory |
| QLoRA | Small adapters; frozen base loaded in 4-bit | Recommended starting method for this Qwen3 checkpoint |

QLoRA is a memory-efficient LoRA setup, not an alternative to supervised
fine-tuning. The task is still SFT: learn an action from an observation/answer pair.
It does not require reinforcement learning for this first experiment.

Unsloth supports newer Qwen families too. Its current Qwen3.5 guide advises
against 4-bit QLoRA for that family because of quantization differences. The
recommendation here applies specifically to the selected **Qwen3** checkpoint.

## Is the data enough?

There are 234 training decisions, but only four training missions across two
layouts, and 210 training targets are movements. The 58 validation and 60 test
decisions come from just one mission group each. This is enough to practice
loading, masking, training, comparing responses and saving an adapter. It cannot
establish a reliable replacement agent, independent layout generalization, or
realistic human shopping behavior.

Use the demo now. After a pilot, collect more diverse examples targeting observed
failures. A planning target of roughly 1,000–3,000 curated decisions is a reasonable
next pilot; 5,000–10,000 can support a broader experiment. These are planning
estimates, not minimums or performance guarantees. Independent missions and good
labels matter more than filling a row quota. Reserve holdout missions first.

## First run

1. In [Colab](https://colab.research.google.com/), use **File → Upload notebook**
   and select `Simply_Qwen3_4B_QLoRA_Colab.ipynb`.
2. Select **Runtime → Change runtime type → GPU**. Try the available T4; L4/A100
   offers more memory headroom if you have access. GPU availability and fit vary.
3. Leave `TRAINING_MODE = "smoke"`. Run the installation cell; if Colab requests a
   restart, restart and continue at step 2 of the notebook without reinstalling.
4. Run cells in order. Upload `simply_qwen_finetuning_demo.zip` when asked.
5. Review data checks, token lengths and the untuned model's validation replies.
6. Let the memory check try the longest training observation. It makes no optimizer
   update. If it fails, use more GPU memory; do not silently truncate data.
7. Run the three-step smoke training and compare replies. Download the adapter zip.
8. Start a fresh runtime, change `TRAINING_MODE` to `"pilot"`, and run one epoch
   from the original base checkpoint. Do not continue training the smoke adapter
   if you want a clean comparison of experiment settings.

The notebook uses public model weights and local GPU inference. It needs no
OpenAI key, does not invoke Luna/Terra, and does not publish to Hugging Face.
Colab may charge for your chosen GPU plan; no duration or cost is promised.

## Starting settings

| Setting | Value | Reason |
|---|---|---|
| Model | `unsloth/Qwen3-4B-Instruct-2507-unsloth-bnb-4bit` | Direct-answer checkpoint with Unsloth support |
| Method | QLoRA SFT | Train adapters with a 4-bit frozen base |
| Context | 16,384 tokens | Preserve the full existing observation and target |
| Per-device batch | 1 | Reduce peak GPU memory |
| Accumulation | 1 smoke / 8 pilot | Effective batch 1 / 8 on one GPU |
| LoRA rank / alpha | 16 / 32 | Small initial adapter experiment |
| Learning rate | `1e-4` | Starting value to evaluate, not a tuned optimum |
| Training | 3 steps smoke / 1 epoch pilot | Check the setup before repeating the corpus |
| Loss | Assistant tokens only | Learn action responses rather than reproduce prompts |
| Packing | Off | Keep the first run easy to inspect |

With the official Qwen tokenizer, the longest current training example has
15,234 tokens. The training median is 7,554. A generic tutorial's 2,048-token
limit would truncate these observations and can remove the answer. The notebook
measures lengths again with the actual loaded tokenizer and refuses truncation.
The exact context requirement can change if inputs or chat templates change.

## What counts as success

For the smoke run: training completes, loss is finite, JSON replies can be
inspected, and the downloaded adapter contains weights, tokenizer and metadata.
Improved quality is not expected from three steps.

For the pilot: compare the same fixed validation prompts before/after tuning.
The notebook records strict schema compliance, observation-valid actions,
teacher action agreement and rough generation latency. Agreement with one rule
teacher is not a whole-trip success metric; multiple routes can be valid.

After settings are fixed, enable the reserved test evaluation once. Eventually
evaluate tuned and untuned Qwen through Simply's Python core on larger held-out
cohorts with frozen inputs and matched assistance policies. Completion, fulfillment,
rejections, loops, correction rate, latency and compute costs matter together.

The notebook trains and tests individual decisions. It does not add a live
Qwen provider, execute shopping actions outside Python, or alter existing recordings.

## Save and deployment

The downloadable result is an **adapter**, not a standalone model. Keep it with
the exact base-model revision, tokenizer/chat template, dataset hashes and package
versions recorded in `experiment.json`. The notebook saves these automatically.
Test that combination first; consider merged or GGUF export later. A Qwen provider
integration and full-trip evaluation are separate future changes to Simply.

## Validation and references

Local checks validate notebook JSON/cell syntax, all 352 data rows, assistant-only
token boundaries, action checks and exact token lengths. GPU package installation,
model loading, training and inference have not been run here. To validate those,
upload the notebook to a Colab GPU runtime and execute its numbered steps.

- [Official model card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)
- [Unsloth quantized checkpoint](https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-unsloth-bnb-4bit)
- [Official Unsloth Colab example](https://colab.research.google.com/github/unslothai/notebooks/blob/main/nb/Qwen3_(4B)-Instruct.ipynb)
- [Unsloth fine-tuning guide](https://unsloth.ai/docs/get-started/fine-tuning-llms-guide)
- [LoRA settings guide](https://unsloth.ai/docs/get-started/fine-tuning-llms-guide/lora-hyperparameters-guide)
- [Qwen3.5-specific guidance](https://unsloth.ai/docs/models/qwen3.5/fine-tune)
