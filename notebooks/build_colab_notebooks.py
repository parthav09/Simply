"""Build the three self-contained Colab notebooks.

    python3 notebooks/build_colab_notebooks.py

01_finetune_qwen25_7b_impulse_v2.ipynb  QLoRA fine-tune on impulse_teacher_v2 -> downloads adapter ZIP
02_run_layout_A.ipynb                   upload that ZIP -> 10 shoppers on Layout A -> downloads results ZIP
03_run_layout_B.ipynb                   same on Layout B

Every notebook embeds the same frozen Simply core (notebooks/frozen_source.py), so the prompt
and guided_nav_v2 are identical in training data, fine-tuning and both layout runs.
"""
import base64
import hashlib
import json
from pathlib import Path

import frozen_source

ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = ROOT / 'data/finetuning/impulse_v2'
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
import subprocess, sys
PINNED = ["unsloth==2026.11.1", "unsloth_zoo==2026.11.1", "transformers==5.17.0", "peft==0.21.2",
          "accelerate==1.15.0", "bitsandbytes==0.50.2", "datasets==4.8.5", "sentencepiece", "protobuf"]
try:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", *PINNED])
    print("Installed the pinned stack (same versions as the Nov 4 pilot).")
except subprocess.CalledProcessError:
    print("WARNING: pinned install failed; using current releases. Versions are recorded in the output ZIP.")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "--upgrade", "unsloth", "datasets",
                           "peft", "accelerate", "bitsandbytes", "sentencepiece", "protobuf"])
'''

UNPACK = r'''
#@title Unpack the bundled Simply core__WITH_DATA__ (hash-verified; do not edit)
import base64, hashlib, io, shutil, sys, zipfile
from pathlib import Path
BUNDLE_SHA256 = "__BUNDLE_SHA__"
SOURCE_SHA256 = "__SOURCE_SHA__"   # frozen prompt + guided_nav_v2 code; must match across all three notebooks
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

# ---------------------------------------------------------------- notebook 01: fine-tune
FT_INTRO = r'''
# 01 · Fine-tune Qwen2.5-7B-Instruct (QLoRA) to make impulse buys

**Run:** `Runtime → Change runtime type → A100 GPU`, then `Runtime → Run all`. Nothing to upload.
**Output:** your browser downloads `simply_qwen25_7b_impulse_v2_adapter_<time>.zip`. Keep it, you upload it into notebooks 02 and 03.

**What it does**
1. Installs the pinned stack (Unsloth 2026.11.1, Transformers 5.17.0, PEFT 0.21.2).
2. Unpacks the frozen Simply core and the **impulse_teacher_v2** dataset (1,724 train / 251 validation / 360 test decisions),
   then re-checks hashes, split leakage and that every impulse label follows the visible-fact rules.
3. Scores the **untuned** model on a fixed validation subset (offline, per decision).
4. QLoRA SFT on `unsloth/Qwen2.5-7B-Instruct-bnb-4bit` (rank 16, alpha 32, lr 1e-4, 1 epoch, effective batch 8, loss on the answer only).
5. Re-scores the tuned model on the same subset, then once on the untouched test split (every impulse moment, thinned list/checkout/move rows).
6. Packs adapter + reports into one ZIP and downloads it.

**Time:** about 1 h 40 min on an A100 (≈80 min training, ≈15 min of evaluation). Set `FAST_TRAINING_SUBSET = True` in step 5 for ≈55 min of training (see the note beside it). No paid API calls.

**About the data:** a deterministic rule teacher, run through the real Python core with the frozen `informed` prompt and
`guided_nav_v2`. Impulse grabs depend only on things the prompt shows: shopping style (planner / mixed / impulsive),
diet, allergy, alcohol, health, product department and price, budget slack, checkout urgency and extras already taken.
Each base shopper appears in all three styles, so the model sees the same trip with different styles. The 15 benchmark
shoppers used in notebooks 02/03 are **excluded** from training. It teaches these rules, not real human psychology.
'''

FT_IMPORTS = r'''
from unsloth import FastLanguageModel   # must be imported before transformers
import torch, gc, importlib.metadata, inspect, json, math, statistics, threading, time
from collections import Counter

gpu = torch.cuda.get_device_properties(0)
print(f"GPU: {gpu.name}; memory: {gpu.total_memory / 2**30:.1f} GiB")
TRAINING_MODE = "impulse_v2"
MODEL_ID = "unsloth/Qwen2.5-7B-Instruct-bnb-4bit"
MAX_SEQ_LENGTH = 16384
LORA_RANK, LORA_ALPHA, LEARNING_RATE, SEED, EPOCHS = 16, 32, 1e-4, 3407, 1
MAX_NEW_TOKENS = 256          # same as the served decision limit
RUN_TEST_SPLIT = True         # settings are fixed before looking at test; it is scored exactly once
RUN_DIRECTORY = Path(f"/content/simply_qwen25_7b_impulse_v2_{STAMP}")
RUN_DIRECTORY.mkdir(parents=True)
DATA = PROJECT / "training_data"
'''

FT_VERIFY = r'''
def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

manifest = json.loads((DATA / "manifest.json").read_text())
assert manifest["dataset"] == "simply_impulse_teacher_v2" and manifest["model_requests"] == 0
assert manifest["frozen_source_sha256"] == SOURCE_SHA256, "dataset was generated with different Simply code"
for name, digest in manifest["files"].items():
    assert hashlib.sha256((DATA / name).read_bytes()).hexdigest() == digest, f"Changed file: {name}"
raw_data = {s: read_jsonl(DATA / f"{s}.jsonl") for s in ("train", "validation", "test")}
provenance = {(p["split"], p["line"]): p for p in read_jsonl(DATA / "provenance.jsonl")}
assert len(provenance) == sum(map(len, raw_data.values()))
bases, prompts = {}, {}
for split, rows in raw_data.items():
    bases[split], prompts[split] = set(), set()
    for line, row in enumerate(rows, 1):
        meta = provenance[split, line]
        assert [m["role"] for m in row["messages"]] == ["user", "assistant"]
        prompt, target_raw = [m["content"] for m in row["messages"]]
        target = json.loads(target_raw)
        assert set(target) == {"step", "product_id", "reason"}
        facts, profile = ie.observation(prompt), ie.parse_profile(prompt)
        assert target["step"] in facts["allowed_steps"]
        assert hashlib.sha256(prompt.encode()).hexdigest() == meta["prompt_sha256"]
        assert hashlib.sha256(target_raw.encode()).hexdigest() == meta["target_sha256"]
        if meta["label"] in ("impulse_grab", "impulse_pass"):     # labels must follow the visible-fact rule
            state, candidates = ie.impulse_context(facts, profile)
            assert (meta["label"] == "impulse_grab") == (state == "eligible")
            if state == "eligible":
                assert target["product_id"] == candidates[0]["product_id"]
        bases[split].add(meta["base_id"]); prompts[split].add(meta["prompt_sha256"])
    print(split, len(rows), "rows |", dict(Counter(provenance[split, i + 1]["label"] for i in range(len(rows)))))
for a, b in (("train", "validation"), ("train", "test"), ("validation", "test")):
    assert not bases[a] & bases[b] and not prompts[a] & prompts[b], "Split leakage"
print("Data checks passed. Benchmark shoppers excluded:", manifest["excluded_benchmark_shoppers"])
'''

FT_TOKENIZE = r'''
from huggingface_hub import HfApi
from transformers import AutoTokenizer
from datasets import Dataset

MODEL_REVISION = HfApi().model_info(MODEL_ID).sha
tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=MODEL_REVISION)
if tokenizer.pad_token_id is None:
    tokenizer.pad_token = tokenizer.eos_token
reference_template = tokenizer.chat_template

def render_ids(tok, messages, generation_prompt):
    text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=generation_prompt)
    return tok(text, add_special_tokens=False)["input_ids"]

def tokenize_example(row):
    full_ids = render_ids(tokenizer, row["messages"], False)
    prefix_ids = render_ids(tokenizer, row["messages"][:-1], True)
    assert full_ids[:len(prefix_ids)] == prefix_ids, "chat-template prefix mismatch"
    labels = [-100] * len(prefix_ids) + full_ids[len(prefix_ids):]   # loss on the answer only
    return {"input_ids": full_ids, "attention_mask": [1] * len(full_ids), "labels": labels}

tokenized_rows = {s: [tokenize_example(r) for r in rows] for s, rows in raw_data.items()}
length_summary = {}
for split, rows in tokenized_rows.items():
    lengths = [len(r["input_ids"]) for r in rows]
    length_summary[split] = {"count": len(rows), "median": statistics.median(lengths), "max": max(lengths)}
    print(split, length_summary[split])
    assert max(lengths) + MAX_NEW_TOKENS <= MAX_SEQ_LENGTH, "never truncate observations"

# Fixed, label-stratified subset of validation for quick before/after scoring and trainer eval loss.
def label_of(split, index): return provenance[split, index + 1]["label"]
QUOTA = {"impulse_grab": 999, "impulse_pass": 24, "list_grab": 10, "checkout": 8, "move": 4}   # ~84 rows
taken, eval_indices = Counter(), []
for i in range(len(raw_data["validation"])):
    label = label_of("validation", i)
    if taken[label] < QUOTA[label]:
        taken[label] += 1; eval_indices.append(i)
eval_rows = [raw_data["validation"][i] for i in eval_indices]
print("Validation scoring subset:", dict(taken))
# SPEED KNOB: True trains on ~1,150 of 1,724 rows (~30% faster) by thinning the most common label types.
# It keeps every impulse grab and checkout, but changes the grab:pass balance from 1:5.7 to 1:3.5, so the
# tuned model may grab slightly more often. Leave False for the full, as-designed dataset.
FAST_TRAINING_SUBSET = False
if FAST_TRAINING_SUBSET:
    caps, seen, keep_idx = {"impulse_pass": 450, "list_grab": 300, "move": 150}, Counter(), []
    for i in range(len(raw_data["train"])):
        label = label_of("train", i)
        if seen[label] < caps.get(label, 10**9):
            seen[label] += 1; keep_idx.append(i)
    print("Fast subset:", dict(seen), "->", len(keep_idx), "rows")
else:
    keep_idx = list(range(len(raw_data["train"])))
train_dataset = Dataset.from_list([tokenized_rows["train"][i] for i in keep_idx])
eval_dataset = Dataset.from_list([tokenized_rows["validation"][i] for i in eval_indices[:48]])   # in-training eval loss
print("Base revision:", MODEL_REVISION)
'''

FT_LOAD = r'''
model, model_tokenizer = FastLanguageModel.from_pretrained(
    model_name=MODEL_ID, revision=MODEL_REVISION, max_seq_length=MAX_SEQ_LENGTH,
    dtype=None, load_in_4bit=True, full_finetuning=False)
model_tokenizer.chat_template = reference_template
model_tokenizer.pad_token = tokenizer.pad_token
assert render_ids(model_tokenizer, raw_data["train"][0]["messages"], False) == tokenized_rows["train"][0]["input_ids"]
tokenizer = model_tokenizer

def generate_responses(rows, label):
    """Greedy, no repetition penalty: exactly how notebooks 02/03 serve the model."""
    FastLanguageModel.for_inference(model); model.eval()
    responses, started = [], time.time()
    for n, row in enumerate(rows, 1):
        text = tokenizer.apply_chat_template(row["messages"][:-1], tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text, return_tensors="pt", add_special_tokens=False).to(model.device)
        with torch.inference_mode():
            out = model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=False, temperature=None,
                                 top_p=None, top_k=None, repetition_penalty=1.0,
                                 pad_token_id=tokenizer.pad_token_id, eos_token_id=tokenizer.eos_token_id)
        responses.append(tokenizer.decode(out[0, inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip())
        if n % 25 == 0:
            print(f"  {label}: {n}/{len(rows)} ({time.time() - started:.0f}s)", flush=True)
        del inputs, out
    return responses

def offline_eval(rows, label):
    metrics, records = ie.score_offline(rows, generate_responses(rows, label))
    (RUN_DIRECTORY / f"offline_eval_{label}.json").write_text(json.dumps({"metrics": metrics, "records": records}, indent=2))
    keys = ["strict_schema_rate", "observation_valid_rate", "exact_action_agreement", "list_grab_recall",
            "checkout_recall", "off_list_proposals", "rule_violation_rate"]
    print(label, json.dumps({k: metrics[k] for k in keys}, indent=1))
    print("impulse:", json.dumps(metrics["impulse"], indent=1))
    print("impulse by style:", json.dumps(metrics["impulse_by_style"], indent=1))
    return metrics
'''

FT_BASELINE = r'''
baseline = offline_eval(eval_rows, "validation_untuned")
'''

FT_TRAIN = r'''
FastLanguageModel.for_training(model)
model = FastLanguageModel.get_peft_model(
    model, r=LORA_RANK, target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    lora_alpha=LORA_ALPHA, lora_dropout=0, bias="none", use_gradient_checkpointing="unsloth",
    random_state=SEED, use_rslora=False, loftq_config=None)
model.print_trainable_parameters()
assert all("lora_" in n for n, p in model.named_parameters() if p.requires_grad), "base weights must stay frozen"

from transformers import DataCollatorForSeq2Seq, Trainer, TrainingArguments, set_seed
collator = DataCollatorForSeq2Seq(tokenizer=tokenizer, padding=True, pad_to_multiple_of=8,
                                  label_pad_token_id=-100, return_tensors="pt")
# Memory check on the longest example before committing ~80 minutes.
longest = max(tokenized_rows["train"], key=lambda r: len(r["input_ids"]))
batch = {k: v.to(model.device) for k, v in collator([longest]).items()}
model.train(); model.zero_grad(set_to_none=True)
with torch.autocast(device_type="cuda", dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16):
    loss = model(**batch).loss
loss.backward(); model.zero_grad(set_to_none=True); del batch, loss; gc.collect(); torch.cuda.empty_cache()
print("Longest example fits:", len(longest["input_ids"]), "tokens")

set_seed(SEED)
arguments = TrainingArguments(
    output_dir=str(RUN_DIRECTORY / "checkpoints"), per_device_train_batch_size=1, per_device_eval_batch_size=1,
    gradient_accumulation_steps=8, num_train_epochs=EPOCHS, learning_rate=LEARNING_RATE, warmup_ratio=0.05,
    weight_decay=0.01, lr_scheduler_type="linear", optim="adamw_8bit",
    fp16=not torch.cuda.is_bf16_supported(), bf16=torch.cuda.is_bf16_supported(), logging_steps=5,
    eval_strategy="steps", eval_steps=72, prediction_loss_only=True, save_strategy="steps", save_steps=72,
    save_total_limit=2, load_best_model_at_end=True, metric_for_best_model="eval_loss", greater_is_better=False,
    report_to="none", seed=SEED, data_seed=SEED, dataloader_num_workers=0, remove_unused_columns=False)
options = dict(model=model, args=arguments, train_dataset=train_dataset, eval_dataset=eval_dataset, data_collator=collator)
options["processing_class" if "processing_class" in inspect.signature(Trainer.__init__).parameters else "tokenizer"] = tokenizer
trainer = Trainer(**options)
assert not globals().get("TRAINING_FINISHED", False), "Already trained; restart the runtime to train again."
training_result = trainer.train()
TRAINING_FINISHED = True
assert math.isfinite(training_result.metrics["train_loss"]), "Training loss is not finite"
print(training_result.metrics)
(RUN_DIRECTORY / "training_metrics.json").write_text(json.dumps(training_result.metrics, indent=2))
(RUN_DIRECTORY / "training_log.json").write_text(json.dumps(trainer.state.log_history, indent=2))
'''

FT_AFTER = r'''
tuned = offline_eval(eval_rows, "validation_tuned")
print("\nBefore → after on the same validation subset")
for key in ("exact_action_agreement", "list_grab_recall", "checkout_recall", "rule_violation_rate"):
    print(f"  {key}: {baseline[key]} → {tuned[key]}")
for key in ("model_grab_rate", "teacher_grab_rate", "precision", "recall", "f1"):
    print(f"  impulse {key}: {baseline['impulse'][key]} → {tuned['impulse'][key]}")
TEST_QUOTA = {"list_grab": 20, "checkout": 8, "move": 8}      # all impulse moments are kept so precision/recall stay unbiased
seen, test_rows = Counter(), []
for i, row in enumerate(raw_data["test"]):
    label = provenance["test", i + 1]["label"]
    if label in TEST_QUOTA:
        if seen[label] >= TEST_QUOTA[label]:
            continue
        seen[label] += 1
    test_rows.append(row)
print("Test rows scored:", len(test_rows), "of", len(raw_data["test"]))
test_metrics = offline_eval(test_rows, "test_tuned") if RUN_TEST_SPLIT else None
'''

FT_SAVE = r'''
from safetensors.torch import load_file
ADAPTER_DIRECTORY = RUN_DIRECTORY / "adapter"
model.save_pretrained(str(ADAPTER_DIRECTORY)); tokenizer.save_pretrained(str(ADAPTER_DIRECTORY))
ADAPTER_SHA256 = hashlib.sha256((ADAPTER_DIRECTORY / "adapter_model.safetensors").read_bytes()).hexdigest()
saved, live = load_file(str(ADAPTER_DIRECTORY / "adapter_model.safetensors")), dict(model.named_parameters())
mismatch = sum(1 for name, tensor in saved.items()
               if (p := live.get(name.replace(".lora_A.", ".lora_A.default.").replace(".lora_B.", ".lora_B.default."))) is None
               or not torch.equal(p.detach().cpu().to(tensor.dtype), tensor))
print(f"Saved {len(saved)} LoRA tensors, sha256 {ADAPTER_SHA256[:16]}…, mismatches vs memory: {mismatch}")
assert saved and mismatch == 0, "saved adapter differs from the trained model"

versions = {}
for package in ["unsloth", "unsloth_zoo", "transformers", "datasets", "peft", "accelerate", "bitsandbytes", "torch"]:
    try: versions[package] = importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError: versions[package] = "unavailable"
experiment = {
    "project": "Simply", "training_mode": TRAINING_MODE, "method": "QLoRA_SFT", "base_model": MODEL_ID,
    "base_revision": MODEL_REVISION, "max_seq_length": MAX_SEQ_LENGTH, "lora_rank": LORA_RANK, "lora_alpha": LORA_ALPHA,
    "learning_rate": LEARNING_RATE, "epochs": EPOCHS, "seed": SEED, "assistant_output_only_loss": True,
    "load_in_4bit": True, "training_arguments": arguments.to_dict(), "packages": versions,
    "chat_template_sha256": hashlib.sha256(tokenizer.chat_template.encode()).hexdigest(),
    "dataset": manifest["dataset"], "dataset_counts": manifest["examples"], "dataset_hashes": manifest["files"],
    "frozen_source_sha256": SOURCE_SHA256, "frozen_commit": manifest["frozen_commit"],
    "token_lengths": length_summary, "gpu": gpu.name, "adapter_sha256": ADAPTER_SHA256, "lora_tensors": len(saved),
    "offline_eval": {"validation_untuned": baseline, "validation_tuned": tuned, "test_tuned": test_metrics},
    "limitation": "Rule-teacher labels; offline scores are per decision. Whole-trip behaviour is measured in notebooks 02/03."}
(RUN_DIRECTORY / "experiment.json").write_text(json.dumps(experiment, indent=2, default=str))

import zipfile
from google.colab import files
ZIP_PATH = Path(f"/content/simply_qwen25_7b_impulse_v2_adapter_{STAMP}.zip")
members = [p for p in sorted(RUN_DIRECTORY.rglob("*")) if p.is_file() and "checkpoints" not in p.parts]
manifest_out = {str(p.relative_to(RUN_DIRECTORY)): hashlib.sha256(p.read_bytes()).hexdigest() for p in members}
(RUN_DIRECTORY / "MANIFEST.json").write_text(json.dumps(manifest_out, indent=2))
with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as archive:
    for p in members + [RUN_DIRECTORY / "MANIFEST.json"]:
        archive.write(p, str(p.relative_to(RUN_DIRECTORY)))
print("Created", ZIP_PATH, f"({ZIP_PATH.stat().st_size / 2**20:.0f} MiB)")
summary = {"adapter_sha256": ADAPTER_SHA256, "train_loss": training_result.metrics["train_loss"],
           "validation_untuned_impulse": baseline["impulse"], "validation_tuned_impulse": tuned["impulse"],
           "test_tuned_impulse": test_metrics["impulse"] if test_metrics else None,
           "test_tuned_exact_action_agreement": test_metrics["exact_action_agreement"] if test_metrics else None}
print("\n=== PASTE THIS INTO THE SIMPLY CHAT ===\n" + json.dumps(summary, indent=1, default=str))
files.download(str(ZIP_PATH))
'''

# ---------------------------------------------------------------- notebooks 02/03: layout runs
RUN_INTRO = r'''
# __NUMBER__ · Run the fine-tuned Qwen on Layout __LETTER__ (`__LAYOUT__`)

**Run:** `Runtime → Change runtime type → A100 GPU` (an L4 also works), then `Runtime → Run all`.
When asked, upload the `simply_qwen25_7b_impulse_v2_adapter_*.zip` that notebook 01 downloaded.
**Output:** your browser downloads `simply_impulse_v2_layout___LETTER___<time>.zip`, and the last cell prints a summary
to paste into the Simply chat.

**What it runs:** the same 10 frozen benchmark shoppers used by every earlier Layout A/B study (seed `20261030`),
120 actions each, one model decision per action, `guided_nav_v2` assistance, `unique_single_checkout_v1`.
The model only **proposes**. The Python core applies every action and writes the canonical run record.
Impulse buys are counted by Python (`off_list_units`). None of these shoppers were in the training data.

**Time:** about 45–75 min. No paid API calls. If the run stops early, the partial record is still packaged.
'''

RUN_CONFIG = r'''
LAYOUT = "__LAYOUT__"
LAYOUT_LETTER = "__LETTER__"
SHOPPERS, TURN_BUDGET, RUN_SEED = 10, 120, 20261030   # study seed 20261029 + repetition 1, as in earlier studies
NAV_POLICY = "guided_nav_v2"
'''

RUN_ADAPTER = r'''
import json, zipfile
from google.colab import files
print("Upload the adapter ZIP from notebook 01 (simply_qwen25_7b_impulse_v2_adapter_*.zip)")
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
assert experiment["training_mode"] == "impulse_v2" and experiment["dataset"] == "simply_impulse_teacher_v2", "not an impulse-v2 adapter"
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
from agents.cuda_runtime import CUDARuntime, IMPULSE_MODEL, SETTINGS, BASE_MODEL
from mps_server import handler_for
versions = {p: importlib.metadata.version(p) for p in ("unsloth", "transformers", "peft", "bitsandbytes", "torch")}
identity = {"model": IMPULSE_MODEL, "device": "cuda", "base_model": BASE_MODEL, "base_revision": experiment["base_revision"],
    "training_base_model": experiment["base_model"], "training_mode": "impulse_v2", "dataset": experiment["dataset"],
    "adapter_sha256": ADAPTER_SHA256, "chat_template_sha256": experiment["chat_template_sha256"],
    "frozen_source_sha256": SOURCE_SHA256, "generation": SETTINGS, "gpu": gpu.name, "packages": versions,
    "deployment_note": "impulse_v2 QLoRA adapter on the NF4 training base, served on Colab CUDA."}
runtime = CUDARuntime(model, tokenizer, identity)
server = ThreadingHTTPServer(("127.0.0.1", 8768), handler_for(runtime, IMPULSE_MODEL, "CUDA"))
server.daemon_threads = True
threading.Thread(target=server.serve_forever, daemon=True).start()
os.environ["SIMPLY_CUDA_URL"] = "http://127.0.0.1:8768"
from agents.cuda_provider import impulse_health
print("Serving:", impulse_health()["model"])
'''

RUN_SIMULATE = r'''
import json, threading, time, traceback
from core.config import DECISION_RUNS_DIR
from core.grid import build_store
from core.session import SimulationSession
from core.shopping import SIMPLE_SHOPPING
from evaluation.benchmark import load_benchmark, instantiate_benchmark

OUT = Path(f"/content/simply_impulse_v2_layout_{LAYOUT_LETTER}_{STAMP}")
OUT.mkdir(parents=True)
RUN_PATH = OUT / f"run_layout_{LAYOUT_LETTER}.jsonl"
benchmark = load_benchmark(PROJECT / "simulation/benchmarks/two_layouts_15_v2.json")
grid = build_store(LAYOUT)
shoppers = instantiate_benchmark(benchmark, SHOPPERS, grid, TURN_BUDGET, SIMPLE_SHOPPING)
print("Shoppers:", [(s.customer.customer_id, s.customer.shopping_style) for s in shoppers])
session = SimulationSession(LAYOUT, SHOPPERS, TURN_BUDGET, TURN_BUDGET, 1, grid=grid, shoppers=shoppers, decide=None,
    provider_name="local_mps", model_name=IMPULSE_MODEL, seed=RUN_SEED, navigation_policy=NAV_POLICY,
    allow_action_plans=False, shopping_rules=SIMPLE_SHOPPING, output_path=RUN_PATH,
    ledger_path=DECISION_RUNS_DIR / "gemini_campaign.sqlite3", requests_per_minute=0,
    experiment={"kind": "qwen_impulse_v2_layout_run", "layout": LAYOUT, "benchmark_sha256": benchmark["sha256"],
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
           "adapter_sha256": ADAPTER_SHA256[:16], "overall": report["overall"], "by_style": report["by_style"],
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


def main():
    out = ROOT / 'notebooks'
    manifest = json.loads((DATASET_DIR / 'manifest.json').read_text())
    data = {f'training_data/{name}': (DATASET_DIR / name).read_bytes() for name in DATASET_FILES}
    unpack_ft, source_sha, size_ft = unpack_cell(data, ' and the impulse_v2 dataset')
    assert manifest['frozen_source_sha256'] == source_sha, 'dataset is stale: regenerate data/finetuning/impulse_v2'
    gpu_a100 = fill(GPU_CHECK, MIN_MIB=38000, GPU_MESSAGE='Training needs a 40 GB A100 for 16K-token observations.')
    ft = notebook([md(FT_INTRO), code(gpu_a100), md('### 1 · Install'), code(INSTALL),
        md('### 2 · Unpack Simply core + dataset'), code(unpack_ft, form=True),
        md('### 3 · Settings'), code(FT_IMPORTS), md('### 4 · Verify the dataset'), code(FT_VERIFY),
        md('### 5 · Tokenize (no truncation) and pick the fixed validation subset'), code(FT_TOKENIZE),
        md('### 6 · Load the 4-bit base'), code(FT_LOAD), md('### 7 · Score the untuned model'), code(FT_BASELINE),
        md('### 8 · Add LoRA and train'), code(FT_TRAIN), md('### 9 · Score the tuned model (validation, then test once)'), code(FT_AFTER),
        md('### 10 · Save, verify and download the adapter'), code(FT_SAVE)])
    (out / '01_finetune_qwen25_7b_impulse_v2.ipynb').write_text(json.dumps(ft, indent=1) + '\n')
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
