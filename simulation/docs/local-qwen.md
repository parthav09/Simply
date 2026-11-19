# Running the fine-tuned Qwen on a Mac

The fine-tuned Qwen2.5 7B adapter (a small set of LoRA weights) can run on an Apple Silicon GPU as
the shopper model. Python still checks and applies every action. There are no API fees. Hardware and
electricity costs are not measured.

There are two ways to run it. **MLX is the faster one**: about 21 s per decision, against about 114 s for MPS,
each measured once on an M3 Pro. Each way is recorded as a separate serving setup, because a 4-bit
model on a Mac is not identical to the one trained in Colab or one served by a hosted API.

## MLX (recommended)

```bash
python3 -m venv simulation/models/mlx-venv
simulation/models/mlx-venv/bin/python -m pip install -r requirements-mlx.txt
ADAPTER=data/finetuning/adapters/simply_qwen25_7b_pilot_20261104_045543_adapter_lora.zip
.venv/bin/python simulation/mps_setup.py --adapter $ADAPTER          # downloads the base model (~15 GB)
simulation/models/mlx-venv/bin/python -m mlx_lm convert \
  --hf-path simulation/models/huggingface/hub/models--Qwen--Qwen2.5-7B-Instruct/snapshots/a09a35458c702b33eeacc393d103063234e8bc28 \
  --mlx-path simulation/models/qwen25-7b-mlx-int4 -q --q-bits 4 --q-group-size 64
simulation/models/mlx-venv/bin/python simulation/mlx_adapter.py --adapter $ADAPTER
simulation/models/mlx-venv/bin/python simulation/mlx_server.py  --adapter $ADAPTER   # wait for "Ready"
```

Then run `.venv/bin/python simulation/serve.py` and pick **Qwen pilot · MLX** in the lab.

## MPS (PyTorch)

```bash
ADAPTER=data/finetuning/adapters/simply_qwen25_7b_pilot_20261104_045543_adapter_lora.zip
.venv/bin/python -m pip install -r requirements-mps.txt
.venv/bin/python simulation/mps_setup.py  --adapter $ADAPTER
.venv/bin/python simulation/mps_server.py --adapter $ADAPTER          # wait for "Ready"
.venv/bin/python simulation/check_mps.py                              # one test decision, saves nothing
```

## Command line

```bash
.venv/bin/python simulation/main.py --provider local_mps --model qwen2.5-7b-pilot-mlx \
  --layout costco_back_anchor --shoppers 10 --export-web
```

## Safety and honesty rules

- The server listens only on `127.0.0.1` and handles one generation at a time.
- It never falls back to a paid API or the CPU, and it never cuts prompts short. A prompt that is too long is an error.
- The adapter file is never changed. Its hash, the base model version, the tokenizer and the package versions are saved in each run.
- A changed setup stops the run before any reply is applied.
- Local runs are kept separate from hosted and OpenAI results. Differences can come from quantization and
  hardware, not just from fine-tuning.
