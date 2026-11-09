# Simply: Qwen fine-tuning, from first principles to interview answers

This guide explains the existing Simply workflow and the proposed fine-tuning experiment. Read it alongside [the hands-on Colab instructions](README.md) and [the synthetic dataset description](../data/finetuning_demo/README.md). The examples are simplified for learning; the notebook and source files are authoritative for implementation details.

## 1. First, know what actually happened

As documented in the repository at the time this guide was written:

| Item | Status | What you can honestly say |
|---|---|---|
| Simply simulation | Implemented | Python owns the simulated store, validation, state changes, accounting and recordings. A model proposes decisions. |
| Qwen2.5-7B-Instruct | OpenRouter/Phala provider and two-layout study prepared; repository README says collection has not started | “I prepared a hosted Qwen baseline.” Check current canonical recordings before claiming measured results. |
| Qwen3-4B-Instruct-2507 | Separate 4-bit checkpoint selected for a Colab training experiment | “I prepared a QLoRA notebook for Qwen3 4B.” This is a different model from Qwen2.5 7B. |
| Fine-tuning dataset | 352 synthetic decision examples generated and checked | Labels come from a deterministic rule-based teacher, not human shoppers or Qwen. |
| GPU training and tuned full-trip comparison | Not documented as completed | Do not claim a trained adapter, deployment, performance uplift, or results. |

The local preflight reports tokenization, masking and action checks; it explicitly says GPU execution was not run. The prepared baseline study has a protocol and report, but a protocol is not proof of completed runs. Check the latest records if the project changes. If asked “Did you fine-tune it?”, a defensible answer is:

> “I prepared and locally validated the data and training pipeline, but I have not yet completed and evaluated GPU fine-tuning. I can explain exactly how the planned QLoRA experiment works and what evidence I would need before claiming improvement.”

**Key comparison rule:** a fine-tuned Qwen3 4B adapter must first be compared with its own compatible *untuned Qwen3 4B base*, under matched conditions. A comparison to Qwen2.5 7B changes model family and size too; it cannot isolate the effect of fine-tuning.

## 2. The big picture: what are we trying to teach?

Simply simulates a shopper in a store. On each decision, the model sees information such as the shopper's task, current position, cart, map and permitted actions. It proposes one action. Python checks and applies it, records the result, and constructs the next observation. React displays Python's run; it does not decide what to buy or update shopping state.

```text
                     TRAINING (proposed)
Python fixture → observation + rule-teacher action → tokenize + mask
               → frozen Qwen3 4B + trainable adapters → saved adapter

                     EVALUATION (future)
held-out observation → base OR base+adapter → one proposed action
                    → Python validation/state transition → next observation
                    → full-trip metrics and canonical record → React replay
```

The desired skill is an **observation-to-action policy**: given the current situation, output a useful, valid action as JSON. Training examples contain a prompt and the teacher's desired answer. Learning to imitate those answers is called **supervised fine-tuning (SFT)** or, in this sequential decision setting, **behavior cloning**. It does not by itself teach a model from rewards, and this notebook is not reinforcement learning.

Fine-tuning changes learned parameters. Prompting supplies instructions or context to existing parameters. Retrieval supplies relevant external information at inference. Structured output constrains or checks response format. These can work together; none guarantees the action is sensible or physically valid. Python remains the authority even if the model produces syntactically valid JSON.

## 3. Trace one example from store to optimizer

The demo generates a full prompt and a teacher response in a JSONL record. This example is intentionally abbreviated; never train on the shortened preview:

```json
{"messages": [
  {"role": "user", "content": "Full profile, mission, map, cart, observation and allowed actions..."},
  {"role": "assistant", "content": "{\"step\":\"grab\",\"product_id\":\"P0001\",\"reason\":\"Collect the requested bananas.\"}"}
]}
```

1. The deterministic `scripted_test` teacher selects an action from a fixture observation. Python core applies it, checks the transition and records provenance. The teacher is a narrow list collector, not a person or language model. `model_only` names the no-navigation-assistance execution policy; it does not identify the teacher as an LLM.
2. The tokenizer's **chat template** turns the conversation into token IDs with role boundaries. Tokenization breaks text into vocabulary units, not necessarily words. The model predicts a probability distribution for each next token.
3. The notebook constructs labels for the full token sequence. It sets the prompt and assistant-generation prefix labels to `-100`, meaning those positions are excluded from loss; assistant response tokens are the targets. The full prompt still conditions the predictions and contributes to activations and gradients flowing to adapters.
4. Under **teacher forcing**, when predicting each answer token, the model sees the true preceding answer tokens. For a target token with predicted probability `p`, cross-entropy contributes `-log(p)`. Training reduces the aggregate loss over unmasked answer tokens. It is not directly optimizing trip completion.
5. Backpropagation computes gradients through the frozen model into trainable adapter weights. The optimizer updates the adapters; the base weights stay frozen. Repeat over examples, then save the adapter and experiment metadata.
6. At inference the answer is generated token by token from the model's own preceding output. Parse it, validate it, and let Python apply it. One plausible response is not proof the full trip succeeds.

The notebook builds labels explicitly with `transformers.Trainer`; it does not rely on a TRL `assistant_only_loss` switch. It verifies that the templated generation prefix matches the full conversation prefix and prints the unmasked text. A broken boundary could train on the wrong text or omit part of the answer.

## 4. SFT, LoRA and QLoRA: three different ideas

- **SFT** specifies the objective: learn from prompt/desired-response examples using next-token prediction.
- **LoRA** specifies what is trainable. For a frozen weight matrix `W₀`, the effective transformation includes a learned low-rank update: `W = W₀ + (α/r)BA`, where `A` and `B` are small trainable matrices and `r` is rank. For a `d_out × d_in` matrix, the adapter uses roughly `r(d_in + d_out)` parameters instead of `d_out × d_in` for a full update. Example: a 4096 × 4096 matrix has about 16.8 million entries; rank 16 uses about 131,000 adapter entries. This is illustrative, not Simply's exact total.
- **QLoRA** uses a quantized frozen base and trains LoRA adapters through it. Four-bit storage substantially reduces base-weight memory; calculations, adapters, gradients, activations and optimizer state need not all be four-bit. Quantization can introduce error. The [QLoRA paper](https://arxiv.org/abs/2305.14314) describes NF4, double quantization and paged optimizers; do not assume every implementation enables every paper technique without checking its actual configuration.

Think of a frozen base as a general language model and the adapter as a small learned adjustment for this particular behavior. Adapters are not a database of facts and cannot repair poor or misleading labels automatically. Their savings reduce memory needs, not necessarily inference latency or the amount of data needed.

## 5. What exactly is in Simply's dataset?

The manifest reports six synthetic mission groups, each represented on both layouts. Every fixture has one shopper and two unique targets. Groups 1–4 train, group 5 validates and group 6 tests:

| Split | Decision rows | Independent mission groups | Purpose |
|---|---:|---:|---|
| Train | 234 | 4 | Compute gradient updates. |
| Validation | 58 | 1 | Compare candidates and choose settings. |
| Test | 60 | 1 | Final reserved check after choices are fixed. |

There are 352 decisions, **not 352 independent shopping missions**. Nearby steps on one route share much of their state. Both layouts of a mission stay in the same split to reduce leakage. The same catalog, layouts and profile templates still appear across splits, so this cannot demonstrate generalization to unseen stores, products or real people. A single validation or test mission gives very uncertain coverage.

The training set contains 210 movement actions, 16 pickups and 8 checkouts. Always predicting the broad “movement” category would get about 89.7% on that broad training-label category, without choosing a correct direction or completing a trip. That number is **class composition, not measured model accuracy**. The data lacks substantial examples of removal, recovery, impulse purchases and realistic preference-sensitive tradeoffs. More repeated moves do not equal more diverse evidence.

The files separate full `train.jsonl`, `validation.jsonl` and `test.jsonl` from `provenance.jsonl`, fixture recordings and a manifest. Provenance lets you trace an example to its mission and source without adding that audit information to the model input. Python validation shows that a recorded action was legal in its state; it does not show that it was optimal or human-like. Soft budget preferences must not be converted into hard price rejection rules.

**Leakage example:** If step 18 of a trip goes into training and step 19 into test, the model sees almost the same shopper, mission, map and route in both. The resulting score overstates performance on a new mission. Split by the unit you want to generalize to, before generating or selecting examples. To claim unseen-layout generalization, reserve truly unseen layouts as well; a grouped mission split alone is insufficient.

## 6. Read the prepared notebook like an engineer

The notebook selects `unsloth/Qwen3-4B-Instruct-2507-unsloth-bnb-4bit`, resolves and records a model revision, loads it in 4-bit, then inserts LoRA into attention projections (`q_proj`, `k_proj`, `v_proj`, `o_proj`) and feed-forward projections (`gate_proj`, `up_proj`, `down_proj`). It asserts that trainable parameter names are LoRA parameters. These choices define an experiment; they are not measured optimal settings.

| Setting | Prepared value | What it controls / tradeoff |
|---|---|---|
| Context | 16,384 tokens | Space for long input and output. Longer sequences increase activation memory and compute. |
| Rank / alpha | 16 / 32 | Rank controls adapter capacity and parameter count; alpha scales the update. More capacity may overfit or cost more. |
| Learning rate | 0.0001 | Update size. Too high can destabilize or overfit; too low can learn slowly. |
| Batch per device | 1 | Examples processed in each forward/backward pass; helps peak memory. |
| Gradient accumulation | 1 smoke, 8 pilot | Accumulate gradients across microbatches before an optimizer update; effective batch is 1 or 8 on one device, subject to any incomplete last batch. It does not make eight examples fit simultaneously. |
| Smoke / pilot | 3 optimizer steps / 1 epoch | Smoke tests mechanics; pilot makes one pass over training data. Neither proves useful performance. |
| Optimizer / schedule | 8-bit AdamW, linear schedule, 5% warmup | Optimizer state and learning-rate trajectory; an 8-bit optimizer does not mean all training computation is 8-bit. |
| Precision | BF16 when supported, otherwise FP16 | Compute precision chosen according to GPU support; distinct from 4-bit base storage. |
| Gradient checkpointing | Unsloth mode | Trades extra recomputation for lower activation memory. |
| Packing | Off | Keeps examples separate and easier to inspect; potentially less throughput. |

The preflight measured a training median of 7,554 tokens and maximum of 15,234 with the official tokenizer. The notebook remeasures using the actual loaded tokenizer and reserves 128 generated tokens within the context limit. A generic 2,048-token tutorial could discard critical observation details or the answer. Silently truncating to avoid out-of-memory would change the task; use a suitable GPU or deliberately redesign and revalidate the representation.

The notebook compares the untuned and tuned model on a **small fixed validation subset selected by action type**, not every validation row during that comparison. It also checks validation loss during the pilot. Strict schema checks whether the JSON has the expected fields and string values. Observation-valid checks use facts extracted from the prompt, not a full engine rollout. Teacher agreement compares `step` and `product_id`, not the explanation. Generation timing is a rough local measurement, not a production latency benchmark.

## 7. Run it safely and understand every stage

Use the detailed [Colab walkthrough](README.md); no paid API call is needed for this local GPU training workflow. Model downloads and your selected Colab plan may have costs and availability constraints.

1. Upload the notebook and the provided `simply_qwen_finetuning_demo.zip`; select a GPU. Inspect package installation and restart only if the notebook instructs you to.
2. Leave `TRAINING_MODE = "smoke"`. Inspect dataset counts, hashes, full prompt lengths, template boundary and decoded unmasked target. Establish the base model's fixed validation responses before attaching/train­ing adapters.
3. Run the longest-example memory check. It executes a forward/backward pass and clears gradients without an optimizer update. Passing it is useful but does not guarantee the complete run will fit or perform well.
4. Run the three-step smoke test. Look for finite loss, actual adapter updates, and parseable responses. Three steps are a wiring check, not a meaningful claim of improvement. Download the adapter and reports.
5. Start a fresh runtime from the original base for the one-epoch pilot. Do not continue the smoke adapter if comparing a clean pilot against the base. Compare the same fixed validation prompts and investigate individual errors. Select settings using validation; keep the test untouched until decisions are fixed.
6. Save the adapter together with the compatible base revision, tokenizer/chat-template hash, dataset hashes, settings, package versions, seed and reports. An adapter alone is not the full model. Confirm loading and inference in a fresh process.
7. A future Simply integration must route model proposals through Python core and record runs. Compare the same untuned base against base plus adapter on held-out complete trips before claiming improvement.

If training runs out of memory, check sequence lengths, GPU capacity and activation memory first. Increase available memory or explicitly redesign the input and regenerate/validate all splits. If loss is NaN, inspect precision, gradients, learning rate, data and library compatibility. If loss falls but JSON or trips worsen, inspect masking, overfitting, class imbalance and state distribution; loss is only a proxy. Package versions may change, so preserve exact versions and troubleshoot against the run's environment.

## 8. How to prove improvement without fooling yourself

Start by defining the target and the claim. An initial claim could be: “On held-out synthetic missions using this interface, the tuned model improved complete-trip performance relative to the same untuned base.” Do not equate that with real-world shopper realism.

**Offline, single decision:** report strict parse/schema rate, validity against the observation, exact action and product agreement with the teacher, per-action breakdown and example counts. A valid alternative route can disagree with the teacher. A correct JSON object can still be strategically poor. Validation loss is useful for choosing a checkpoint but is not the business outcome.

**Full rollout:** freeze the same base revision, held-out shopper/mission/layout inputs, prompts, decoding, action limits, Python rules and assistance policy. Run both arms, record original proposal and any Python navigation adjustment, and retain failures and interrupted attempts. Report paid completion, list fulfillment, invalid actions/rejections, loops, assistance rate, latency, token usage and compute or provider cost. If assistance is on, results measure the **model plus assistance system**, not the isolated model. Consider a separately controlled assistance-off comparison if it is safe and feasible.

**Why rollout matters:** offline evaluation gives the model states from the teacher's route. In a real rollout, a wrong turn changes the next observation. The model can enter unfamiliar states, make further mistakes and loop. This distribution shift and compounding error can produce poor trip completion despite good single-step agreement. Evaluate recoveries and full trajectories, not just clean teacher states.

Use paired comparisons on the same held-out missions and report the number of independent missions and variation, not only the number of actions. With very few independent missions, avoid confident population claims. Freeze the test and publish all attempts. If a test result informs further tuning, it has become development evidence; use a new untouched test for a final claim. For cost, compare the complete inference and training economics on the same workload; token-price estimates and provider-reported charges are distinct.

## 9. Interview questions and model answers

**1. What problem does fine-tuning solve here?**  
It might make a smaller open-weight model better at turning Simply observations into one valid, useful action in the expected format. That is a hypothesis; baseline and controlled evaluation must establish whether it improves complete trips enough to justify its costs.

**2. Why not just prompt the model?**  
Prompting is the necessary first baseline and may be sufficient. Fine-tuning can adapt output behavior from repeated examples, but adds data, training, versioning and evaluation costs. Compare a strong prompt-only base to the adapter on the same tasks before choosing.

**3. Why QLoRA?**  
The selected Colab experiment uses a 4-bit frozen base plus low-rank trainable adapters to reduce memory. It is a practical starting choice, not proof that this checkpoint or quantization is optimal. Long context and activations still consume substantial memory.

**4. What receives gradients?**  
Loss is computed on assistant answer tokens. Gradients propagate through operations involving the frozen base into LoRA parameters. The optimizer updates those adapters; frozen base weights do not change. Prompt tokens are context even though their own positions are masked from loss.

**5. What is the loss actually maximizing?**  
The likelihood of teacher answer tokens conditional on the observation and preceding ground-truth answer tokens. Lower loss is not directly the same as more completed trips, correct strategy, or human realism.

**6. Why use a chat template?**  
It formats roles and special tokens as the checkpoint expects. Training and inference should use compatible templates; otherwise role boundaries and loss masking can change. The notebook checks token-prefix alignment and stores a template hash.

**7. What is the source of labels?**  
A deterministic offline rule teacher generates actions in synthetic fixtures, which Python core applies and records. These are not human, Qwen, Luna or Terra demonstrations. Legal actions need not be best actions.

**8. How do you prevent leakage?**  
Group both layouts of a mission together and split missions before training. Keep the final test out of model selection. For a new-store claim, hold out stores/layouts; for a new-person claim, independently hold out shopper groups. Existing shared catalogs and layouts limit the present demo.

**9. Why might a high accuracy be misleading?**  
Movement dominates the dataset. A broad move/non-move predictor can appear strong while getting directions, pickups and checkout wrong. Report exact actions, class coverage, meaningful baselines and full-trip outcomes; distinguish training distribution from measured test accuracy.

**10. How do you evaluate action validity?**  
First parse the exact schema, then check the action against the current observation. Ultimately let Python core validate and apply it during full trips. Format compliance is necessary but does not prove legality, usefulness or completion.

**11. What if the model improves teacher agreement but completes fewer trips?**  
The teacher-state offline distribution differs from model-generated rollout states. Errors compound, and multiple valid routes can disagree with the teacher. Inspect trajectories, failure categories, action distributions and assistance adjustments.

**12. Can the 7B hosted baseline prove the 4B fine-tune helped?**  
No. It is a different Qwen generation, size and serving path. Compare the same Qwen3 4B base before and after adaptation first. Other model comparisons can answer a broader system-selection question with appropriate caveats.

**13. What does an adapter contain, and how is it deployed?**  
It contains learned adapter weights and configuration, not the complete original model. Load it with the compatible base revision and tokenizer/template. Record hashes and versions, then integrate the model as an action proposer while Python retains state authority. Merging/exporting is a separate tested deployment decision.

**14. Why do you need both a validation and test split?**  
Validation guides choices such as learning rate, rank and checkpoint; repeated selection can overfit it. The untouched test provides a later check after choices are frozen. One held-out mission in this demo is only a limited pipeline check.

**15. What is your biggest limitation?**  
The corpus is small and heavily movement-biased, with only six synthetic mission groups from a narrow scripted teacher. The GPU training and base-versus-tuned full-trip experiment remain pending. It cannot establish realistic human behavior or a performance gain.

**16. Is this reinforcement learning?**  
No. SFT imitates supplied responses using supervised token loss. RL would optimize a policy using a reward signal and an RL procedure; Python validating teacher actions does not by itself turn SFT into RL.

**17. What would you do next?**  
Complete the smoke and clean pilot, improve labels and coverage, reserve independent holdouts, and run matched base-versus-adapter full-trip experiments. Analyze failure modes and economics before considering deployment. Retain failed runs and document uncertainty.

## 10. A two-minute explanation to practice

“Simply has a Python simulation that owns the store state and validates every action. A model receives an observation and proposes a single JSON action. I prepared a supervised fine-tuning experiment that teaches a Qwen3 4B model to imitate actions from a deterministic synthetic teacher. The dataset has 352 decision rows but only six mission groups, so I split by mission and treat it as a pipeline demo, not evidence of human behavior.

The notebook applies the model's chat template and computes loss only on assistant response tokens. It loads a frozen four-bit base and trains small LoRA adapters, which reduces memory compared with updating every model weight. It preserves the long observations and records the base revision, tokenizer, dataset hashes and settings.

I haven't completed GPU training or a tuned full-trip evaluation. To test the hypothesis, I would compare the same Qwen3 base and adapter on held-out missions with identical prompts, Python rules and assistance, reporting completion, fulfillment, failures, latency and cost. The app's separately prepared Qwen2.5 7B baseline is a different model and cannot isolate the effect of the 4B fine-tune.”

## 11. Source map and further reading

Project sources: [Colab notebook](Simply_Qwen3_4B_QLoRA_Colab.ipynb), [notebook setup and limitations](README.md), [dataset and generation](../data/finetuning_demo/README.md), [manifest](../data/finetuning_demo/manifest.json), [tokenization preflight](colab_preflight.json), [OpenRouter provider](../simulation/agents/openrouter_provider.py), and [project status](../README.md).

Primary technical references: [Qwen3 4B model card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507), [Qwen2.5 7B model card](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct), [LoRA paper](https://arxiv.org/abs/2106.09685), [QLoRA paper](https://arxiv.org/abs/2305.14314), and [Hugging Face SFT documentation](https://huggingface.co/docs/trl/sft_trainer). The notebook's explicit masking implementation is the source of truth for this project; framework APIs and package behavior can change.
