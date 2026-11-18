# Qwen pilot on Apple MLX

The saved Qwen2.5 7B pilot adapter can run on the Apple GPU with an MLX affine
4-bit base. This is a separate serving identity from the Quanto MPS deployment,
the original CUDA NF4 training base, and hosted inference. No retraining or paid
API calls are involved. MLX still uses GPU and unified memory.

From the repository root, prepare an isolated environment and model once:

```bash
python3 -m venv simulation/models/mlx-venv
simulation/models/mlx-venv/bin/python -m pip install -r requirements-mlx.txt
.venv/bin/python simulation/mps_setup.py --adapter data/finetuning/adapters/simply_qwen25_7b_pilot_20261104_045543_adapter_lora.zip
simulation/models/mlx-venv/bin/python -m mlx_lm convert --hf-path simulation/models/huggingface/hub/models--Qwen--Qwen2.5-7B-Instruct/snapshots/a09a35458c702b33eeacc393d103063234e8bc28 --mlx-path simulation/models/qwen25-7b-mlx-int4 -q --q-bits 4 --q-group-size 64
simulation/models/mlx-venv/bin/python simulation/mlx_adapter.py --adapter data/finetuning/adapters/simply_qwen25_7b_pilot_20261104_045543_adapter_lora.zip
```

The converter checks the pilot configuration and verifies the 392 converted
tensors. The server verifies the loaded tensors and records model, tokenizer,
adapter and package hashes/versions in the serving identity. The original
adapter is unchanged. The 4-bit MLX base is approximately 4 GB on disk.

Start the server and leave it running:

```bash
simulation/models/mlx-venv/bin/python simulation/mlx_server.py --adapter data/finetuning/adapters/simply_qwen25_7b_pilot_20261104_045543_adapter_lora.zip
```

Wait for `Ready`, start `.venv/bin/python simulation/serve.py` separately, and
select **Qwen pilot · MLX** in the lab. A preview does not request inference.
The server listens on `127.0.0.1:8767`, supports one generation at a time,
and does not fall back to a paid API or truncate observations. Local CLI runs
use `--provider local_mps --model qwen2.5-7b-pilot-mlx`; `local_mps` is the
existing local Apple GPU transport, while the model and frozen serving identity
distinguish MLX from historical MPS runs. The controlled MPS pilot remains a
separate study and is not resumed or replaced by this server.

On November 8, a single full 4,337-token shopper observation produced a valid
action in about 21 seconds, versus about 114 seconds in the earlier MPS check.
These are single observations with different output lengths, not full-study
benchmarks. Local compute and electricity costs are unmeasured.
