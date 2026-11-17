# Local Qwen pilot on Apple Silicon

Simply can use the saved Qwen2.5 7B pilot LoRA as a shopper proposer on a Mac's
PyTorch MPS GPU. Python core still validates and applies every shopper action.
The browser requests sessions and displays the canonical stream.

The inspected pilot was trained against
`unsloth/Qwen2.5-7B-Instruct-bnb-4bit`, revision
`bdd404162d94997f390efbfa660eb3f21cbbc81d`. Its weights SHA-256 is
`6a90bf20ce1690761794d8e25f6bf76caf9f3a508a50c3591b5b82f926b5c7d1`.
The unchanged adapter is loaded onto the compatible official
`Qwen/Qwen2.5-7B-Instruct` base pinned in `simulation/models/qwen-base-source.json`.
For this setup that revision is `a09a35458c702b33eeacc393d103063234e8bc28`.

The original CUDA NF4 checkpoint cannot be used directly with MPS. This deployment
uses Quanto int4 weights, float16 activations, and the saved tokenizer/template.
It is not bit-identical to the training quantization or the hosted OpenRouter
endpoint. To measure the adapter's effect, compare with the same local base,
precision, prompts and generation settings, rather than attributing differences
against OpenRouter solely to fine-tuning.

## Start the services

Run from the repository root. All packages are optional and stay inside `.venv`;
model files and caches stay under the ignored `simulation/models/` directory.
The initial official base download is approximately 15 GB.

```bash
.venv/bin/python -m pip install -r requirements-mps.txt
.venv/bin/python simulation/mps_setup.py --adapter data/simply_qwen25_7b_colab_starter/simply_qwen25_7b_pilot_20261104_045543_adapter_lora.zip
.venv/bin/python simulation/mps_server.py --adapter data/simply_qwen25_7b_colab_starter/simply_qwen25_7b_pilot_20261104_045543_adapter_lora.zip
```

Keep that process running; wait for `Ready` at `http://127.0.0.1:8766`.
In a second terminal start the Python simulation bridge:

```bash
.venv/bin/python simulation/serve.py
```

Then open the web app's **Shopper lab → Live → Qwen pilot · MPS**. The button is
enabled only when the local inference service reports the expected ready model.
Choose layout and shopper count, then Start. Reconnecting follows the same run.
The store preview does not load weights, create a run or call the model.

An optional `SIMPLY_MPS_URL` in `.env` can change the inference port; it must
remain a loopback HTTP origin. Services reject cross-origin requests and
unrecognized Host headers. There is no remote or paid model fallback.

## Verify inference without starting a simulation

```bash
.venv/bin/python simulation/check_mps.py
```

This sends one full informed shopper observation and validates the generated
action, but applies nothing and creates no canonical run or performance evidence.
Its diagnostic report goes to `simulation/models/pilot-inference-check.json`.
Every saved LoRA tensor is compared with the loaded parameter at the deployment
dtype before the server becomes ready; all model parameters must be on MPS.

The November 4 check verified 392 LoRA tensors and produced a valid `move_right`
proposal from 4,337 prompt tokens plus 30 output tokens in about 114 seconds on
this M3 Pro. That is a single inference observation, not a whole-run benchmark.
Full shopper runs can take a long time with this tensor-only int4 implementation.

## Run from the CLI

```bash
.venv/bin/python simulation/main.py --provider local_mps --model qwen2.5-7b-pilot-mps --layout costco_back_anchor --shoppers 10 --export-web
```

Use `neighborhood_express` for Layout B. This starts a real local run; the same
Python rules, `guided_nav_v2` assistance and unique single-checkout semantics apply.
Local runs are marked `local_mps`, exported as real model runs, and appear in
history. They are not silently inserted into the controlled baseline estimates.
Fresh controlled base-versus-adapter studies remain a separate evaluation task.

## Authorized two-layout pilot study

The requested local pilot study is
`simulation/runs/studies/qwen25-7b-pilot-mps-ab-20261104`. It freezes the same ten
profiles, seed, 120-action allowance, unique targets and `guided_nav_v2` assistance as
the hosted baseline, with one run on each layout and GPU concurrency 1.

```bash
.venv/bin/python simulation/evaluation/study.py prepare --directory simulation/runs/studies/qwen25-7b-pilot-mps-ab-20261104 --provider local_mps --kind layout --shoppers 10 --repetitions 1 --turn-budget 120 --concurrency 1 --seed 20261029
caffeinate -i .venv/bin/python simulation/evaluation/mps_study.py --directory simulation/runs/studies/qwen25-7b-pilot-mps-ab-20261104
```

Preparation makes health requests but no inference calls. Do not prepare over
an existing protocol. The worker admits one frozen slot at a time and publishes
its final recording, report, history and Evidence table when that slot ends.
`worker-status.json` and `worker.log` in the study directory track progress.
`caffeinate -i` prevents idle sleep only while the worker is alive; closing the
lid, shutting down or losing power can still interrupt it. At the measured local
inference speed the full study may take several days.

Completed slots are never repeated. A provider failure retains the attempt,
exports its partial evidence and stops the worker; it does not retry a slot or
substitute another model. Individual local runs do not enter the pilot headline
row: only the selected frozen pilot study does. Model API costs remain zero and
hardware/compute costs remain unmeasured. Cloud-versus-local differences cannot
be attributed solely to the adapter.

## Memory, performance and accounting

- Tested target: M3 Pro with 18 GB unified memory. Only one GPU generation runs
  at a time; the bridge uses concurrency 1 for this provider.
- Prefill uses 256-token chunks to limit attention memory. Full observations
  exceeding the 16,384-token context including output allowance are rejected,
  never silently shortened. This can be slower than hosted inference.
- Quanto 0.2.7's compiled MPS extension is incompatible with the installed Torch
  build. The service registers the published reference unpack algorithm using
  native PyTorch MPS tensor operations. It does not run the model on CPU.
- Generation is greedy with at most 256 new tokens and one proposal per action.
  Invalid model JSON or physically invalid actions remain genuine failures.
- No model API key is used. Per-token API charges are zero; local hardware and
  electricity costs are not measured. Existing API ledger history is preserved.
- The adapter, base revision, generation settings and packages are frozen in
  run metadata. A changed serving identity aborts a run before applying a reply.
- An inference smoke check is not a completed shopper study or evidence of
  improved shopping performance.

References: [PyTorch MPS](https://docs.pytorch.org/docs/stable/notes/mps.html),
[PEFT model loading](https://huggingface.co/docs/peft/en/package_reference/peft_model),
[Quanto device support](https://github.com/huggingface/optimum-quanto).
