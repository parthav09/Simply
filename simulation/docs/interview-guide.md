# Interview guide: agent harness, evals, cost

Use this to explain Simply in your own words. Paths are relative to `simulation/`.

## The 30-second pitch

> Simply puts LLM "shoppers" in a simulated store. The model suggests one action at a time. Python
> checks it, applies it, logs it and scores it. Because Python owns everything, I can replay any run,
> recompute every number from the log, and compare models and store layouts fairly, including
> what each one costs.

## Words to know

| Word | Plain meaning in Simply |
|---|---|
| Agent | A model that takes many steps toward a goal (finishing a shopping trip) |
| Harness | Everything around the model: prompt, reply checking, applying actions, logging, cost tracking |
| Eval | A fixed, repeatable test with fixed inputs and measures, run the same way for each option |
| Ablation | Turning one part off to see how much it mattered (e.g. the navigation helper) |
| Guardrail | An automatic check that flags a run as pass, review or fail |

## 1. Walk through one decision

Be able to draw this from memory:

```text
prompt (agents/prompts.py) → model reply → is_valid_decision (agents/schema.py)
  → adjusted_action (core/navigation.py) → apply_action (core/actions.py) → RunWriter (core/run_log.py)
```

- **The reply is checked twice.** First its format (strict JSON, only legal steps), then whether it's physically
  possible (is the shelf next to you? already in the cart?).
- **No repair, no retry, no fallback.** A bad reply is logged as a failure and costs a turn.
- **Only `apply_action` changes state.** That's why the replay and the metrics can be trusted.
- **The log can't be overwritten.** Files are opened with `"x"` (fail if the file exists), and each event's "before"
  must match the previous event's "after".

## 2. The navigation helper, explained honestly

`adjusted_action` can replace the model's move: grab a list item that's in reach, or head to checkout
when turns run low. Both the original suggestion and the change are saved.

- It's a **pure function** of saved facts, so every recorded adjustment can be re-checked later.
- **The catch:** results measure model + helper. Say this before the interviewer does.
- **How to test it:** run the same model with the helper on and off (`--kind assistance`).
- **Is the helper overfit?** It was tuned on the same 10 profiles. That's fair to admit, and store layouts shape
  real shoppers too.

## 3. Making an eval trustworthy

1. **Freeze inputs before running** (`evaluation/study.py`, `prepare`). The plan is saved with a hash.
2. **Refuse to run if code or inputs changed.** The engine fingerprint is checked.
3. **Same 10 shoppers in every arm, shuffled run order.**
4. **Same prompt and helper for every model**, so only the model differs.
5. **Keep every failed or stopped run.** Never quietly retry.
6. **Check which model actually answered.** A version change stops the study.
7. **Recompute everything from the logs** (`report`), with no API key needed.

Measures to name: completion and list fulfilment (did it work), impulse buys and overspend (behaviour),
invalid and rejected actions and loops (reliability), helper adjustments, and cost per finished trip plus latency.
Details are in [evals.md](evals.md).

**Cost per trip** is total cost ÷ total finished trips. Averaging per-run ratios would hide runs where nobody finished.

## 4. Cost and speed (what the job cares about)

| Lever | What I did | What could get worse |
|---|---|---|
| Waiting | Each shopper asks and applies on its own instead of waiting for the slowest | Nothing changes per shopper. Ordering is logged. |
| Number of calls | Optional 1–8 action plans, dropped if the state changes: ~76% fewer calls in an offline test | Stale plans. Turned off in studies so each action is one decision. |
| Model choice | Compare a cheap model and an expensive one on cost per finished trip and quality together | Cheaper isn't the same quality. Report both. |
| Cost tracking | Reserve an estimate before each call, settle after, keep "unknown" when usage is missing | The estimate can differ from the provider's bill, so both are kept. |
| Self-hosting | Fine-tuned Qwen on a Mac: no API fees, but slow (~21 s per decision) | Hardware cost isn't measured, and it differs from the hosted version. |

How to frame it: *"For every optimisation: what was the bottleneck, what changed, which metric shows
it helped, and what could get worse?"*

## 5. Fine-tuning in plain words

- **SFT:** show the model (prompt → correct answer) pairs and train it to copy the answer.
- **LoRA:** freeze the big model and train small extra weight matrices. **QLoRA:** the same, with the frozen
  model stored in 4-bit to save memory.
- **Loss only on the answer**, not on the long prompt.
- **Labels come from a rule-based teacher**, because there's no real shopper data.
- **Split by shopper**, not by step. Neighbouring steps of one trip are almost identical, so a random split leaks.
- **Single-step accuracy isn't trip success.** In a real trip, one wrong turn leads to situations the model never saw.
- **Fair test:** the same base model with and without the adapter, under the same rules.

Details are in [data/finetuning/README.md](../../data/finetuning/README.md).

## 6. Likely questions

**How do you handle bad model output?** Strict schema, strict parser, check against legal steps, then physical
checks. The failure is logged and costs a turn. No repair and no retry.

**Why not let the model change state directly?** One source of truth. Accounting and metrics can't depend on the
model, and replay can't invent results.

**How do you compare two models fairly?** Same shoppers, layout, prompt, helper and limits. Shuffled order.
Check the model that answered. Report cost and latency next to quality.

**Runs aren't deterministic. How is this reproducible?** You can't make the model deterministic, so you
fix the *conditions* and make the *analysis* reproducible: frozen inputs, a saved prompt and reply for every step,
and metrics recomputed from the log.

**How would you keep this cheap and accurate in production?** A fixed eval set run on every prompt or model
change (a regression gate). Track cost per successful task, not per call. Guardrail checks on live runs. Use a
cheaper model where it meets the quality bar. Watch for provider or model drift.

**What are the weaknesses?** One run per cell. Synthetic shoppers with no ground truth. "Impulse buy" means
"not on the list". The helper influences results. Different providers and dates. Say these first.

**What would you do with more budget?** More repeat runs with confidence intervals, a helper on/off study,
held-out shoppers, and checking the impulse measure against real shopping data.

**Did you vibe-code this?** Explain one design choice and why you made it (e.g. single authority, frozen
fingerprint, no retries). Be clear about what AI helped with and what you decided.

## 7. Self-quiz (answer without looking)

1. Which function is the only one that changes shopper state? (`apply_action`)
2. What happens when the model returns an illegal step? (logged as a failure, turn used, no fallback)
3. Why is `adjusted_action` a pure function? (so saved adjustments can be re-checked)
4. Why open the log with `"x"`? (never overwrite a result)
5. Why store money in whole cents? (no rounding drift between run, replay and export)
6. What stops a study after the prompt is edited? (the fingerprint check)
7. What does "~76% fewer calls" *not* tell you? (anything about decision quality)
8. Why isn't single-step accuracy enough for the fine-tuned model? (errors build up over a trip)

## 8. Five-minute demo

1. Open one run log in `runs/` and show a decision: before, prompt, reply, action, result, after.
2. Show a navigation adjustment: the model said X, Python applied Y, and both were saved.
3. Run `study report` to show numbers recomputed with no model calls.
4. Open `/evaluation` and point out that the numbers come from `evaluation/dashboard.py`.
