"""Build the three self-contained Colab notebooks.

    python3 notebooks/build_colab_notebooks.py

01_finetune_qwen25_7b_impulse_v3.ipynb  QLoRA fine-tune on impulse_teacher_v3 -> downloads adapter ZIP
02_run_layout_A.ipynb                   upload that ZIP -> 10 shoppers on Layout A -> downloads results ZIP
03_run_layout_B.ipynb                   same on Layout B

Every notebook embeds the same frozen Simply core (notebooks/frozen_source.py), so the prompt
and guided_nav_v3 are identical in training data, fine-tuning and both layout runs.
"""
import base64
import hashlib
import io
import sys
import zipfile
import json
from pathlib import Path

import frozen_source

ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = ROOT / 'data/finetuning/impulse_v3'
DATASET_FILES = ('train.jsonl', 'validation.jsonl', 'test.jsonl', 'provenance.jsonl', 'manifest.json')


def md(text):
    return {'cell_type': 'markdown', 'metadata': {}, 'source': text.strip('\n').splitlines(True)}


def code(text, form=False):
    return {'cell_type': 'code', 'metadata': {'cellView': 'form'} if form else {}, 'execution_count': None,
            'outputs': [], 'source': text.strip('\n').splitlines(True)}


def notebook(cells):
    return {'cells': cells, 'nbformat': 4, 'nbformat_minor': 5, 'metadata': {
        'accelerator': 'GPU', 'colab': {'gpuType': 'A100', 'provenance': []},
        'kernelspec': {'display_name': 'Python 3', 'name': 'python3'}, 'language_info': {'name': 'python'}}}


GPU_CHECK = r'''
import subprocess, time
SMI = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                     capture_output=True, text=True).stdout.strip()
print("GPU:", SMI or "none")
assert SMI, "No GPU. Runtime → Change runtime type → A100 GPU."
assert int(SMI.split(",")[1].split()[0]) >= __MIN_MIB__, "__GPU_MESSAGE__"
STAMP = time.strftime("%Y%m%d_%H%M%S")
'''

INSTALL = r'''
# Same install the original working notebook used: plain pip, output shown live.
import subprocess, sys

subprocess.check_call([
    sys.executable, "-m", "pip", "install", "--upgrade",
    "unsloth", "datasets", "peft", "accelerate", "bitsandbytes",
    "sentencepiece", "protobuf",
])
print("Install finished. If Colab shows a 'Restart session' popup, click Restart, then Runtime -> Run all.")
'''

UNPACK = r'''
#@title Unpack the bundled Simply core__WITH_DATA__ (hash-verified; do not edit)
import base64, hashlib, io, shutil, sys, zipfile
from pathlib import Path
BUNDLE_SHA256 = "__BUNDLE_SHA__"
SOURCE_SHA256 = "__SOURCE_SHA__"   # frozen prompt + guided_nav_v3 code; must match across all three notebooks
BUNDLE_B64 = "__B64__"
_blob = base64.b64decode(BUNDLE_B64)
assert hashlib.sha256(_blob).hexdigest() == BUNDLE_SHA256, "Embedded bundle is corrupted"
PROJECT = Path("/content/simply")
if PROJECT.exists():
    shutil.rmtree(PROJECT)
PROJECT.mkdir(parents=True)
with zipfile.ZipFile(io.BytesIO(_blob)) as _z:
    _z.extractall(PROJECT)
del _blob, BUNDLE_B64
(PROJECT / "simulation" / "runs").mkdir(exist_ok=True)
sys.path.insert(0, str(PROJECT / "simulation"))
import evaluation.impulse_eval as ie
print("Simply core unpacked to", PROJECT)
'''

# ---------------------------------------------------------------- notebook 01: fine-tune (kept short on purpose)
FT_INTRO = r"""
# 01 · Fine-tune Qwen2.5-7B-Instruct to make impulse buys (QLoRA, Unsloth)

**Run:** `Runtime → Change runtime type → A100 GPU`, then `Runtime → Run all`. You upload one file: `impulse_v3_dataset.csv` (a file picker opens at step 2; or drag it into the Files panel first).
**Output:** a ZIP downloads at the end (`simply_qwen25_7b_impulse_v3_adapter_*.zip`). You upload it into notebooks 02 and 03.
**Time:** about 60 minutes (install ≈ 4, load ≈ 3, untuned check ≈ 4, train ≈ 38, tuned check ≈ 4, save ≈ 2).

What it does: verifies the uploaded impulse_v3 CSV (hashes, JSON, split leakage) → measures token lengths (no truncation) →
scores the **untuned** model on a fixed validation subset → memory check on the longest example → QLoRA fine-tune
(4-bit NF4, LoRA r=16 on all attention + MLP layers, answer-only loss, validation loss every 50 steps, best checkpoint kept)
→ scores the **tuned** model on the same rows → saves the adapter, checks it against memory → downloads one ZIP.
No paid API calls. Whole-trip results come from notebooks 02/03.

Switches (step 3): `MODE = "smoke"` trains 3 steps only, to test the pipeline (its adapter is rejected by 02/03);
`FULL_DATA = True` uses all 1,753 rows (~80 min of training); `RUN_FINAL_TEST = True` also scores the held-out test split.
"""

FT_DATA = r"""
import csv, hashlib, json, sys, shutil
from collections import Counter
from pathlib import Path
import evaluation.impulse_eval as ie

MODE = "pilot"          # "smoke" = 3 optimizer steps to test the pipeline; its adapter is rejected by notebooks 02/03
FULL_DATA = False       # True = all 1,753 rows (~80 min of training)
RUN_FINAL_TEST = False  # True = also score the held-out test split once (~12 min)
assert MODE in ("pilot", "smoke")

DATA = PROJECT / "training_data"
manifest = json.loads((DATA / "dataset_meta.json").read_text())
assert manifest["dataset"] == "simply_impulse_teacher_v3" and manifest["model_requests"] == 0
SOURCE_SHA256 = manifest["frozen_source_sha256"]       # ties this adapter to the exact prompt/code used in notebooks 02/03
assert hashlib.sha256(CSV_PATH.read_bytes()).hexdigest() == manifest["csv_sha256"], "dataset CSV changed or is the wrong file"
csv.field_size_limit(sys.maxsize)
data, provenance = {"train": [], "validation": [], "test": []}, {}
with open(CSV_PATH, newline="", encoding="utf-8") as handle:
    for row in csv.DictReader(handle):
        split = row["split"]
        data[split].append({"messages": [{"role": "user", "content": row["prompt"]}, {"role": "assistant", "content": row["response"]}]})
        provenance[split, len(data[split])] = row               # label, base_id, prompt_sha256, target_sha256 per row
assert {k: len(v) for k, v in data.items()} == manifest["examples"], "row counts differ from the expected dataset"

bases, prompts = {}, {}
for split, rows in data.items():                          # schema, allowed steps, hashes, split leakage
    bases[split], prompts[split] = set(), set()
    for line, row in enumerate(rows, 1):
        meta = provenance[split, line]
        assert [m["role"] for m in row["messages"]] == ["user", "assistant"]
        prompt, answer = (m["content"] for m in row["messages"])
        action = json.loads(answer)
        assert set(action) == {"step", "product_id", "reason"} and all(isinstance(v, str) for v in action.values())
        assert action["step"] in ie.observation(prompt)["allowed_steps"]
        assert hashlib.sha256(prompt.encode()).hexdigest() == meta["prompt_sha256"]
        assert hashlib.sha256(answer.encode()).hexdigest() == meta["target_sha256"]
        bases[split].add(meta["base_id"]); prompts[split].add(meta["prompt_sha256"])
for a, b in (("train", "validation"), ("train", "test"), ("validation", "test")):
    assert not bases[a] & bases[b] and not prompts[a] & prompts[b], "split leakage"
label_of = lambda split, i: provenance[split, i + 1]["label"]
print("Data checks passed:", {s: len(r) for s, r in data.items()}, "| benchmark shoppers excluded:", len(manifest["excluded_benchmark_shoppers"]))

CAPS = {"impulse_pass": 400, "list_grab": 140, "checkout": 60, "move": 60}   # training subset; impulse_grab: keep all
seen, keep = Counter(), []
for i in range(len(data["train"])):
    label = label_of("train", i)
    if FULL_DATA or seen[label] < CAPS.get(label, 10**9):
        seen[label] += 1; keep.append(i)
print(f"Training on {len(keep)} of {len(data['train'])} rows:", dict(seen))

EVAL_QUOTA = {"impulse_grab": 999, "impulse_pass": 24, "list_grab": 10, "checkout": 8, "move": 4}   # fixed validation subset
taken, eval_idx = Counter(), []
for i in range(len(data["validation"])):
    label = label_of("validation", i)
    if taken[label] < EVAL_QUOTA[label]:
        taken[label] += 1; eval_idx.append(i)
eval_rows = [data["validation"][i] for i in eval_idx]
print("Validation scoring subset:", dict(taken))

OUT = Path("/content/impulse_v3_adapter"); shutil.rmtree(OUT, ignore_errors=True); (OUT / "adapter").mkdir(parents=True)
"""

FT_MODEL = r"""
from unsloth import FastLanguageModel        # import before transformers
import gc, importlib.metadata, inspect, math, statistics, time
import torch
from datasets import Dataset
from huggingface_hub import HfApi

MODEL_ID, MAX_SEQ_LENGTH = "unsloth/Qwen2.5-7B-Instruct-bnb-4bit", 16384
REVISION = HfApi().model_info(MODEL_ID).sha
model, tokenizer = FastLanguageModel.from_pretrained(model_name=MODEL_ID, revision=REVISION,
    max_seq_length=MAX_SEQ_LENGTH, dtype=None, load_in_4bit=True)      # 4-bit NF4 base, frozen
if tokenizer.pad_token_id is None:
    tokenizer.pad_token = tokenizer.eos_token

def ids(messages, generation_prompt):
    text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=generation_prompt)
    return tokenizer(text, add_special_tokens=False)["input_ids"]

def tokenize(row):                                # loss only on the assistant's JSON answer
    full, prefix = ids(row["messages"], False), ids(row["messages"][:-1], True)
    assert full[:len(prefix)] == prefix, "chat template prefix mismatch"
    labels = [-100] * len(prefix) + full[len(prefix):]
    assert any(l != -100 for l in labels), "no answer tokens to learn from"
    return {"input_ids": full, "attention_mask": [1] * len(full), "labels": labels}

rows = [tokenize(data["train"][i]) for i in keep]
eval_tokenized = [tokenize(data["validation"][i]) for i in eval_idx[:48]]
lengths = [len(r["input_ids"]) for r in rows]
length_summary = {"rows": len(rows), "median": statistics.median(lengths), "max": max(lengths)}
print("Token lengths:", length_summary, "(never truncated)")
assert max(lengths) + 256 <= MAX_SEQ_LENGTH, "example too long for the context window"
print("Learned text of the first example:", tokenizer.decode([t for t in rows[0]["labels"] if t != -100]))
train_dataset, eval_dataset = Dataset.from_list(rows), Dataset.from_list(eval_tokenized)

def generate_responses(rows_to_score, label):
    # Greedy, no repetition penalty: exactly how notebooks 02/03 serve the model.
    FastLanguageModel.for_inference(model); model.eval()
    out, started = [], time.time()
    for n, row in enumerate(rows_to_score, 1):
        text = tokenizer.apply_chat_template(row["messages"][:-1], tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text, return_tensors="pt", add_special_tokens=False).to(model.device)
        with torch.inference_mode():
            gen = model.generate(**inputs, max_new_tokens=256, do_sample=False, temperature=None, top_p=None, top_k=None,
                                 repetition_penalty=1.0, pad_token_id=tokenizer.pad_token_id, eos_token_id=tokenizer.eos_token_id)
        out.append(tokenizer.decode(gen[0, inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip())
        if n % 25 == 0:
            print(f"  {label}: {n}/{len(rows_to_score)} ({time.time() - started:.0f}s)", flush=True)
        del inputs, gen
    return out

def offline_eval(rows_to_score, label):
    metrics, records = ie.score_offline(rows_to_score, generate_responses(rows_to_score, label))
    (OUT / f"offline_eval_{label}.json").write_text(json.dumps({"metrics": metrics, "records": records}, indent=2))
    keys = ("strict_schema_rate", "observation_valid_rate", "exact_action_agreement", "list_grab_recall", "checkout_recall",
            "off_list_proposals", "rule_violation_rate")
    print(label, json.dumps({k: metrics[k] for k in keys}), "\nimpulse:", json.dumps(metrics["impulse"]),
          "\nby tier:", json.dumps(metrics["impulse_by_tier"]))
    return metrics

baseline = offline_eval(eval_rows, "validation_untuned")
"""

FT_TRAIN = r"""
from transformers import DataCollatorForSeq2Seq, Trainer, TrainingArguments, set_seed
SEED = 3407
FastLanguageModel.for_training(model)
model = FastLanguageModel.get_peft_model(model, r=16, lora_alpha=32, lora_dropout=0, bias="none", random_state=SEED,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    use_gradient_checkpointing="unsloth")
model.print_trainable_parameters()
assert all("lora_" in n for n, p in model.named_parameters() if p.requires_grad), "base weights must stay frozen"
collator = DataCollatorForSeq2Seq(tokenizer=tokenizer, padding=True, pad_to_multiple_of=8, label_pad_token_id=-100, return_tensors="pt")

# Memory check on the longest example (one forward/backward, no update) before committing ~40 minutes.
longest = max(rows, key=lambda r: len(r["input_ids"]))
batch = {k: v.to(model.device) for k, v in collator([longest]).items()}
model.train(); model.zero_grad(set_to_none=True)
with torch.autocast(device_type="cuda", dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16):
    loss = model(**batch).loss
loss.backward(); model.zero_grad(set_to_none=True); del batch, loss; gc.collect(); torch.cuda.empty_cache()
print("Longest example fits:", len(longest["input_ids"]), "tokens | peak", round(torch.cuda.max_memory_allocated() / 2**30, 1), "GiB")

set_seed(SEED)
smoke, bf16 = MODE == "smoke", torch.cuda.is_bf16_supported()
args = TrainingArguments(output_dir="/content/ckpt", per_device_train_batch_size=1, per_device_eval_batch_size=1,
    gradient_accumulation_steps=4, num_train_epochs=1, max_steps=3 if smoke else -1, learning_rate=1e-4, warmup_steps=0.05,   # transformers 5: a float below 1 is a ratio of total steps
    weight_decay=0.01, lr_scheduler_type="linear", optim="adamw_8bit", bf16=bf16, fp16=not bf16, logging_steps=10,
    eval_strategy="no" if smoke else "steps", eval_steps=50, prediction_loss_only=True,
    save_strategy="no" if smoke else "steps", save_steps=50, save_total_limit=2,
    load_best_model_at_end=not smoke, metric_for_best_model="eval_loss", greater_is_better=False,
    report_to="none", seed=SEED, data_seed=SEED, dataloader_num_workers=0, remove_unused_columns=False)
options = dict(model=model, args=args, train_dataset=train_dataset, eval_dataset=eval_dataset, data_collator=collator)
options["processing_class" if "processing_class" in inspect.signature(Trainer.__init__).parameters else "tokenizer"] = tokenizer
trainer = Trainer(**options)
result = trainer.train()
assert math.isfinite(result.metrics["train_loss"]), "loss is not finite"
print(result.metrics)
"""

FT_SAVE = r"""
import zipfile
from safetensors.torch import load_file
from google.colab import files

tuned = offline_eval(eval_rows, "validation_tuned")
print("\nBefore (untuned) -> after (tuned), same validation rows")
for key in ("strict_schema_rate", "observation_valid_rate", "exact_action_agreement", "list_grab_recall", "checkout_recall", "rule_violation_rate"):
    print(f"  {key}: {baseline[key]} -> {tuned[key]}")
for key in ("model_grab_rate", "teacher_grab_rate", "precision", "recall", "f1"):
    print(f"  impulse {key}: {baseline['impulse'][key]} -> {tuned['impulse'][key]}")
test_metrics = offline_eval(data["test"], "test_tuned") if RUN_FINAL_TEST else None

model.save_pretrained(str(OUT / "adapter")); tokenizer.save_pretrained(str(OUT / "adapter"))
adapter_sha = hashlib.sha256((OUT / "adapter" / "adapter_model.safetensors").read_bytes()).hexdigest()
saved, live = load_file(str(OUT / "adapter" / "adapter_model.safetensors")), dict(model.named_parameters())
mismatch = sum(1 for name, tensor in saved.items()
               if (q := live.get(name.replace(".lora_A.", ".lora_A.default.").replace(".lora_B.", ".lora_B.default."))) is None
               or not torch.equal(q.detach().cpu().to(tensor.dtype), tensor))
print(f"Saved {len(saved)} LoRA tensors, sha256 {adapter_sha[:16]}..., mismatches vs trained model: {mismatch}")
assert saved and mismatch == 0, "saved adapter differs from the trained model"

packages = {}
for name in ("unsloth", "unsloth_zoo", "transformers", "peft", "bitsandbytes", "torch", "datasets", "accelerate"):
    try: packages[name] = importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError: packages[name] = "unavailable"
experiment = {"project": "Simply", "training_mode": "impulse_v3" if MODE == "pilot" else "impulse_v3_smoke",
    "method": "QLoRA_SFT", "base_model": MODEL_ID, "base_revision": REVISION, "dataset": manifest["dataset"],
    "dataset_csv_sha256": manifest["csv_sha256"], "frozen_source_sha256": SOURCE_SHA256, "frozen_commit": manifest["frozen_commit"],
    "rows_trained": len(keep), "full_data": FULL_DATA, "lora_rank": 16, "lora_alpha": 32, "learning_rate": 1e-4, "epochs": 1,
    "gradient_accumulation_steps": 4, "seed": SEED, "max_seq_length": MAX_SEQ_LENGTH, "token_lengths": length_summary,
    "training_arguments": args.to_dict(), "train_metrics": result.metrics, "assistant_output_only_loss": True, "load_in_4bit": True,
    "chat_template_sha256": hashlib.sha256(tokenizer.chat_template.encode()).hexdigest(), "adapter_sha256": adapter_sha,
    "lora_tensors": len(saved), "packages": packages, "gpu": torch.cuda.get_device_name(0),
    "offline_eval": {"validation_untuned": baseline, "validation_tuned": tuned, "test_tuned": test_metrics}}
(OUT / "experiment.json").write_text(json.dumps(experiment, indent=2, default=str))
(OUT / "training_log.json").write_text(json.dumps(trainer.state.log_history, indent=2))
ZIP = Path(f"/content/simply_qwen25_7b_impulse_v3_adapter_{STAMP}.zip")
with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(OUT.rglob("*")):
        if path.is_file(): archive.write(path, str(path.relative_to(OUT)))
print("Created", ZIP, f"({ZIP.stat().st_size / 2**20:.0f} MiB)")
print("\n=== PASTE THIS INTO THE SIMPLY CHAT ===\n" + json.dumps({"mode": MODE, "adapter_sha256": adapter_sha[:16],
    "rows_trained": len(keep), "train_loss": result.metrics["train_loss"],
    "validation_untuned_impulse": baseline["impulse"], "validation_tuned_impulse": tuned["impulse"],
    "validation_tuned_by_tier": tuned["impulse_by_tier"], "tuned_rule_violation_rate": tuned["rule_violation_rate"],
    "tuned_exact_action_agreement": tuned["exact_action_agreement"],
    "test_tuned_impulse": test_metrics["impulse"] if test_metrics else None, "packages": packages}, indent=1, default=str))
files.download(str(ZIP))
"""

UPLOAD_CSV = r"""
#@title Provide the dataset CSV (impulse_v3_dataset.csv)
# If you already dragged the CSV into the Colab Files panel (/content), it is used; otherwise a file picker opens.
import glob, os, shutil
from pathlib import Path
found = sorted(glob.glob("/content/**/impulse_v3_dataset*.csv", recursive=True))
if not found:
    from google.colab import files
    uploaded = files.upload()
    found = [name for name in uploaded if name.endswith(".csv")]
    assert found, "No CSV uploaded. Re-run this cell and choose impulse_v3_dataset.csv."
    found = [str(Path("/content") / found[0])]
CSV_PATH = Path(found[0])
print("Using", CSV_PATH, f"({CSV_PATH.stat().st_size / 2**20:.0f} MB)")
"""

SMALL_UNPACK = r"""
#@title Unpack the bundled scoring code and dataset fingerprint (hash-verified; do not edit)
import base64, hashlib, io, shutil, sys, zipfile
from pathlib import Path
BUNDLE_SHA256 = "__BUNDLE_SHA__"
BUNDLE_B64 = "__B64__"
_blob = base64.b64decode(BUNDLE_B64)
assert hashlib.sha256(_blob).hexdigest() == BUNDLE_SHA256, "Embedded bundle is corrupted"
PROJECT = Path("/content/simply")
shutil.rmtree(PROJECT, ignore_errors=True); PROJECT.mkdir(parents=True)
with zipfile.ZipFile(io.BytesIO(_blob)) as _z:
    _z.extractall(PROJECT)
del _blob, BUNDLE_B64
sys.path.insert(0, str(PROJECT / "simulation"))
print("Scoring code ready in", PROJECT)
"""


# ---------------------------------------------------------------- notebooks 02/03: layout runs
RUN_INTRO = r'''
# __NUMBER__ · Run the fine-tuned Qwen on Layout __LETTER__ (`__LAYOUT__`)

**Run:** `Runtime → Change runtime type → A100 GPU` (an L4 also works), then `Runtime → Run all`.
When asked, upload the `simply_qwen25_7b_impulse_v3_adapter_*.zip` that notebook 01 downloaded.
**Output:** your browser downloads `simply_impulse_v3_layout___LETTER___<time>.zip`, and the last cell prints a summary
to paste into the Simply chat.

**What it runs:** the same 10 frozen benchmark shoppers used by every earlier Layout A/B study (seed `20261118`, the same as the Nov 17 Luna/Terra impulse studies),
120 actions each, one model decision per action, `guided_nav_v3` assistance, `unique_single_checkout_v1`.
The model only **proposes**. The Python core applies every action and writes the canonical run record.
Impulse buys are counted by Python (`off_list_units`). None of these shoppers were in the training data.

**Time:** about 45–75 min. No paid API calls. If the run stops early, the partial record is still packaged.
'''

RUN_CONFIG = r'''
LAYOUT = "__LAYOUT__"
LAYOUT_LETTER = "__LETTER__"
SHOPPERS, TURN_BUDGET, RUN_SEED = 10, 120, 20261118   # study seed 20261117 + repetition 1: same as the Nov 17 Luna/Terra impulse studies
NAV_POLICY = "guided_nav_v3"
'''

RUN_ADAPTER = r'''
import json, zipfile
from google.colab import files
print("Upload the adapter ZIP from notebook 01 (simply_qwen25_7b_impulse_v3_adapter_*.zip)")
uploaded = files.upload()
archives = [(n, b) for n, b in uploaded.items() if n.endswith(".zip")]
assert len(archives) == 1, "Upload exactly one adapter ZIP"
ADAPTER_ROOT = Path(f"/content/adapter_{STAMP}")
with zipfile.ZipFile(io.BytesIO(archives[0][1])) as archive:
    for name in archive.namelist():
        assert not name.startswith("/") and ".." not in Path(name).parts, f"unsafe path in ZIP: {name}"
    archive.extractall(ADAPTER_ROOT)
del uploaded, archives
ADAPTER_DIR = ADAPTER_ROOT / "adapter"
experiment = json.loads((ADAPTER_ROOT / "experiment.json").read_text())
assert experiment["training_mode"] == "impulse_v3" and experiment["dataset"] == "simply_impulse_teacher_v3", "not an impulse-v3 adapter"
assert experiment["frozen_source_sha256"] == SOURCE_SHA256, "adapter was trained against different Simply code"
ADAPTER_SHA256 = hashlib.sha256((ADAPTER_DIR / "adapter_model.safetensors").read_bytes()).hexdigest()
assert ADAPTER_SHA256 == experiment["adapter_sha256"], "adapter file differs from the one notebook 01 recorded"
print("Adapter OK:", ADAPTER_SHA256[:16], "| base revision", experiment["base_revision"][:12])
'''

RUN_LOAD = r'''
from unsloth import FastLanguageModel
import torch, importlib.metadata, os, threading, time
from peft import PeftModel
from safetensors.torch import load_file
from transformers import AutoTokenizer

gpu = torch.cuda.get_device_properties(0)
model, _ = FastLanguageModel.from_pretrained(model_name=experiment["base_model"], revision=experiment["base_revision"],
                                             max_seq_length=16384, dtype=None, load_in_4bit=True)
model = PeftModel.from_pretrained(model, str(ADAPTER_DIR), is_trainable=False)
tokenizer = AutoTokenizer.from_pretrained(str(ADAPTER_DIR))
assert hashlib.sha256(tokenizer.chat_template.encode()).hexdigest() == experiment["chat_template_sha256"], "chat template differs from training"
saved, live = load_file(str(ADAPTER_DIR / "adapter_model.safetensors")), dict(model.named_parameters())
mismatch = sum(1 for name, tensor in saved.items()
               if (p := live.get(name.replace(".lora_A.", ".lora_A.default.").replace(".lora_B.", ".lora_B.default."))) is None
               or not torch.equal(p.detach().cpu().to(tensor.dtype), tensor))
assert saved and mismatch == 0, f"{mismatch} LoRA tensors did not load exactly"
FastLanguageModel.for_inference(model); model.eval()
print(f"Loaded base + {len(saved)} LoRA tensors exactly on {gpu.name}")
'''

RUN_SERVE = r'''
from http.server import ThreadingHTTPServer
from agents.cuda_runtime import CUDARuntime, IMPULSE_V3_MODEL, SETTINGS, BASE_MODEL
from mps_server import handler_for
versions = {p: importlib.metadata.version(p) for p in ("unsloth", "transformers", "peft", "bitsandbytes", "torch")}
identity = {"model": IMPULSE_V3_MODEL, "device": "cuda", "base_model": BASE_MODEL, "base_revision": experiment["base_revision"],
    "training_base_model": experiment["base_model"], "training_mode": "impulse_v3", "dataset": experiment["dataset"],
    "adapter_sha256": ADAPTER_SHA256, "chat_template_sha256": experiment["chat_template_sha256"],
    "frozen_source_sha256": SOURCE_SHA256, "generation": SETTINGS, "gpu": gpu.name, "packages": versions,
    "deployment_note": "impulse_v3 QLoRA adapter on the NF4 training base, served on Colab CUDA."}
runtime = CUDARuntime(model, tokenizer, identity)
server = ThreadingHTTPServer(("127.0.0.1", 8768), handler_for(runtime, IMPULSE_V3_MODEL, "CUDA"))
server.daemon_threads = True
threading.Thread(target=server.serve_forever, daemon=True).start()
os.environ["SIMPLY_CUDA_URL"] = "http://127.0.0.1:8768"
from agents.cuda_provider import impulse_v3_health
print("Serving:", impulse_v3_health()["model"])
'''

RUN_SIMULATE = r'''
import json, threading, time, traceback
from core.config import DECISION_RUNS_DIR
from core.grid import build_store
from core.session import SimulationSession
from core.shopping import SIMPLE_SHOPPING
from evaluation.benchmark import load_benchmark, instantiate_benchmark

OUT = Path(f"/content/simply_impulse_v3_layout_{LAYOUT_LETTER}_{STAMP}")
OUT.mkdir(parents=True)
RUN_PATH = OUT / f"run_layout_{LAYOUT_LETTER}.jsonl"
benchmark = load_benchmark(PROJECT / "simulation/benchmarks/two_layouts_15_v2.json")
grid = build_store(LAYOUT)
shoppers = instantiate_benchmark(benchmark, SHOPPERS, grid, TURN_BUDGET, SIMPLE_SHOPPING)
print("Shoppers:", [(s.customer.customer_id, s.customer.shopping_style) for s in shoppers])
session = SimulationSession(LAYOUT, SHOPPERS, TURN_BUDGET, TURN_BUDGET, 1, grid=grid, shoppers=shoppers, decide=None,
    provider_name="local_mps", model_name=IMPULSE_V3_MODEL, seed=RUN_SEED, navigation_policy=NAV_POLICY,
    allow_action_plans=False, shopping_rules=SIMPLE_SHOPPING, output_path=RUN_PATH,
    ledger_path=DECISION_RUNS_DIR / "gemini_campaign.sqlite3", requests_per_minute=0,
    experiment={"kind": "qwen_impulse_v3_layout_run", "layout": LAYOUT, "benchmark_sha256": benchmark["sha256"],
                "cohort_size": SHOPPERS, "seed": RUN_SEED, "adapter_sha256": ADAPTER_SHA256})

def watch():
    while True:
        time.sleep(120)
        try:
            print(time.strftime("%H:%M:%S"), "decisions recorded:", sum(1 for _ in RUN_PATH.open()) - 1, flush=True)
        except Exception:
            pass
threading.Thread(target=watch, daemon=True).start()

RUN_ERROR, started = None, time.time()
try:
    session.run()
except BaseException as error:          # keep the partial record and still package it
    RUN_ERROR = f"{type(error).__name__}: {error}"
    traceback.print_exc()
print(f"Finished in {(time.time() - started) / 60:.1f} min | status {session.status} | error {RUN_ERROR}")
'''

RUN_PACKAGE = r'''
import hashlib, json, platform, zipfile
report = ie.trip_report(RUN_PATH)
(OUT / "trip_report.json").write_text(json.dumps(report, indent=2))
(OUT / "served_identity.json").write_text(json.dumps(identity, indent=2))
(OUT / "adapter_experiment.json").write_text(json.dumps(experiment, indent=2))
(OUT / "environment.json").write_text(json.dumps({"python": platform.python_version(), "gpu": gpu.name,
    "packages": versions, "run_error": RUN_ERROR, "status": session.status}, indent=2))
members = sorted(p for p in OUT.iterdir() if p.is_file())
(OUT / "MANIFEST.json").write_text(json.dumps({p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in members}, indent=2))
ZIP_PATH = Path(f"/content/{OUT.name}.zip")
with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as archive:
    for p in members + [OUT / "MANIFEST.json"]:
        archive.write(p, f"{OUT.name}/{p.name}")
print("Created", ZIP_PATH, f"({ZIP_PATH.stat().st_size / 2**20:.1f} MiB)")
summary = {"layout": LAYOUT, "run_id": report["run_id"], "status": report["status"], "model": report["model"],
           "adapter_sha256": ADAPTER_SHA256[:16], "overall": report["overall"], "by_style": report["by_style"], "by_tier": report["by_tier"],
           "failures": report["failures"], "run_error": RUN_ERROR}
print("\n=== PASTE THIS INTO THE SIMPLY CHAT ===\n" + json.dumps(summary, indent=1))
files.download(str(ZIP_PATH))
'''


def fill(template, **values):
    for key, value in values.items():
        template = template.replace(f'__{key}__', str(value))
    return template


def unpack_cell(extra, label):
    data, source_sha = frozen_source.bundle(extra)
    return fill(UNPACK, WITH_DATA=label, BUNDLE_SHA=hashlib.sha256(data).hexdigest(), SOURCE_SHA=source_sha,
                B64=base64.b64encode(data).decode()), source_sha, len(data)


def write_csv(directory):
    """One CSV with every row (train/validation/test): prompt, response and the per-row metadata the checks need."""
    import csv
    path = directory / 'impulse_v3_dataset.csv'
    csv.field_size_limit(sys.maxsize)
    fields = ['split', 'line', 'label', 'tier', 'style', 'base_id', 'prompt_sha256', 'target_sha256', 'prompt', 'response']
    with open(path, 'w', newline='', encoding='utf-8') as out:
        writer = csv.DictWriter(out, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        meta = {}
        for line in (directory / 'provenance.jsonl').read_text().splitlines():
            row = json.loads(line)
            meta[row['split'], row['line']] = row
        for split in ('train', 'validation', 'test'):
            for number, line in enumerate((directory / f'{split}.jsonl').read_text().splitlines(), 1):
                m = meta[split, number]
                prompt, answer = (x['content'] for x in json.loads(line)['messages'])
                writer.writerow({**{k: m[k] for k in fields[:8]}, 'prompt': prompt, 'response': answer})
    return path


def main():
    out = ROOT / 'notebooks'
    manifest = json.loads((DATASET_DIR / 'manifest.json').read_text())
    _, source_sha = frozen_source.bundle({})
    assert manifest['frozen_source_sha256'] == source_sha, 'dataset is stale: regenerate data/finetuning/impulse_v3'
    csv_path = write_csv(DATASET_DIR)
    meta = {k: manifest[k] for k in ('dataset', 'model_requests', 'frozen_commit', 'frozen_source_sha256', 'examples', 'excluded_benchmark_shoppers')}
    meta['csv_sha256'] = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    small = {'training_data/dataset_meta.json': json.dumps(meta, indent=1).encode(),
             'simulation/evaluation/impulse_eval.py': (ROOT / 'simulation/evaluation/impulse_eval.py').read_bytes()}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(small.items()):
            archive.writestr(zipfile.ZipInfo(name, date_time=(2026, 11, 17, 0, 0, 0)), data, compress_type=zipfile.ZIP_DEFLATED)
    blob = buffer.getvalue()
    unpack_ft = fill(SMALL_UNPACK, BUNDLE_SHA=hashlib.sha256(blob).hexdigest(), B64=base64.b64encode(blob).decode())
    size_ft = len(blob)
    gpu_a100 = fill(GPU_CHECK, MIN_MIB=38000, GPU_MESSAGE='Training needs a 40 GB A100 for 16K-token observations.')
    ft = notebook([md(FT_INTRO), code(gpu_a100), md('### 1 · Install'), code(INSTALL),
        md('### 2 · Unpack the scoring code, then provide the dataset CSV'), code(unpack_ft, form=True), code(UPLOAD_CSV),
        md('### 3 · Verify the data, choose settings and training rows'), code(FT_DATA),
        md('### 4 · Load the 4-bit model, tokenize, and score the untuned model'), code(FT_MODEL),
        md('### 5 · Memory check, then train (QLoRA)'), code(FT_TRAIN),
        md('### 6 · Score the tuned model, save, verify and download the adapter'), code(FT_SAVE)])
    (out / '01_finetune_qwen25_7b_impulse_v3.ipynb').write_text(json.dumps(ft, indent=1) + '\n')
    unpack_run, run_sha, size_run = unpack_cell({}, '')
    assert run_sha == source_sha
    gpu_any = fill(GPU_CHECK, MIN_MIB=22000, GPU_MESSAGE='Use an A100 or L4 GPU runtime.')
    for number, letter, layout in (('02', 'A', 'costco_back_anchor'), ('03', 'B', 'neighborhood_express')):
        values = dict(NUMBER=number, LETTER=letter, LAYOUT=layout)
        nb = notebook([md(fill(RUN_INTRO, **values)), code(gpu_any), code(fill(RUN_CONFIG, **values)),
            md('### 1 · Install'), code(INSTALL), md('### 2 · Unpack Simply core'), code(unpack_run, form=True),
            md('### 3 · Upload and verify the adapter from notebook 01'), code(RUN_ADAPTER),
            md('### 4 · Load base + adapter (exact tensor check)'), code(RUN_LOAD),
            md('### 5 · Serve the model on loopback'), code(RUN_SERVE),
            md(f'### 6 · Run 10 shoppers on Layout {letter} through the Python core'), code(RUN_SIMULATE),
            md('### 7 · Impulse report, package and download'), code(RUN_PACKAGE)])
        (out / f'{number}_run_layout_{letter}.ipynb').write_text(json.dumps(nb, indent=1) + '\n')
    print(f'source {source_sha[:12]} | finetune bundle {size_ft / 2**20:.1f} MiB | run bundle {size_run / 2**20:.2f} MiB')


if __name__ == '__main__':
    main()
