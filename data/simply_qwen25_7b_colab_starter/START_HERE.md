# Simply Qwen2.5 7B fine-tuning starter

This package prepares a QLoRA supervised fine-tuning experiment for **Qwen2.5-7B-Instruct**, the checkpoint family of Simply's prepared OpenRouter / Phala baseline. The included `INTERVIEW_GUIDE.md` explains the implementation, concepts, limitations and interview questions.

## What is in this ZIP?

- `Simply_Qwen2_5_7B_QLoRA_Colab.ipynb`: proposed Colab workflow using `unsloth/Qwen2.5-7B-Instruct-bnb-4bit`.
- `simply_qwen_finetuning_demo.zip`: original synthetic rule-teacher data. Keep it zipped for the notebook upload.
- `INTERVIEW_GUIDE.md`: theory and project-specific interview preparation.

## Start

1. Extract this starter ZIP to your computer. Open [Google Colab](https://colab.research.google.com/), then use File → Upload notebook to open the `.ipynb` file.
2. Choose a GPU runtime. This 7B model with long observations may need more GPU memory than a free runtime provides; no fit or cost is guaranteed.
3. Leave `TRAINING_MODE = "smoke"`; execute the installation cell and restart if prompted. Run the remaining cells in order. Upload the nested `simply_qwen_finetuning_demo.zip` when requested.
4. Inspect data checks, measured Qwen2.5 token lengths, decoded unmasked assistant targets, untuned validation responses, and the longest-example memory check. Stop on any error; do not silently truncate the observations or answers.
5. Run the three-step smoke training and save its adapter and reports. A smoke run validates wiring, not model quality. Start a **fresh runtime from the original base** for the one-epoch pilot; compare the same fixed validation examples before and after tuning.
6. Choose settings on validation; leave the test untouched until decisions are fixed. For a meaningful result, compare the same local base revision with and without the adapter on independent full trips through Python core with matched conditions. Save all failures.

## What this does and does not establish

The dataset has 234 training, 58 validation and 60 test decision rows from six synthetic mission groups. Most train actions are moves. It is a narrow scripted-teacher workflow demo, not human shopping data. No training or rollout results are included. Notebook code syntax and archive contents have been checked locally, but the Qwen2.5 tokenizer, package installation, model loading, memory fit, GPU training and inference have **not** been executed or verified. The notebook measures token lengths and checks masking on the actual tokenizer when run.

The local four-bit checkpoint is a quantized derivative of the official Qwen2.5 7B Instruct model; the hosted endpoint may use another revision, precision, template or decoding setup. Compare base and tuned model in the same local environment to isolate the adapter. The existing hosted provider does not serve this adapter. Python remains responsible for applying every shopping action, and serving the adapter in Simply requires further integration and evaluation.

Reference: [Qwen2.5 model card](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct), [Unsloth quantized checkpoint](https://huggingface.co/unsloth/Qwen2.5-7B-Instruct-bnb-4bit), [QLoRA paper](https://arxiv.org/abs/2305.14314).
