# Interview study guide: agent harnesses, evals, and optimization

This guide uses Simply as an example for an interview about agent engineering. It is a map for learning the code and explaining the tradeoffs; tailor ownership claims to the work you actually did, and don't claim every part of Simply unless that is accurate.

## The 60-second explanation

> Simply simulates shoppers navigating a store. A model sees a shopper profile and an observation and proposes an action. A Python harness validates the proposal, optionally applies a recorded navigation assist, and passes the resulting action to the simulation engine. The engine is authoritative for state and writes an event history. We can replay the same run in React and calculate metrics from the recording. For comparisons, we freeze the cohort, layout, model, policy and other controls, preserve failures, and report the limitations. An important nuance is that assisted results measure the model **plus the harness**, not the model alone.

**Words to know:** An *agent* uses model decisions to act over multiple steps; the *harness* supplies context, tools, control flow, validation and observability; an *eval* defines a repeatable task, measurements and comparison; an *ablation* changes one component to estimate its contribution. A seed can control study order without making a hosted model deterministic.

## What to read, in order

Links are relative to this README. Spend the first hour on the first six files; follow the others for depth.

| Order | File and functions | What to learn |
|---|---|---|
| 1 | [core/session.py](../../core/session.py): `SimulationSession.step`, `build_run_start` | Session lifecycle and what gets frozen in a run. |
| 2 | [agents/prompts.py](../../agents/prompts.py): `informed_prompt` | How observations, profile, legal moves and remaining list become model context. |
| 3 | [agents/schema.py](../../agents/schema.py): `parse_decision`, `is_valid_decision` | The action contract and handling malformed output. |
| 4 | [core/rounds.py](../../core/rounds.py): `tick`, `_submit_due`, `_commit` | Concurrent requests, action validation, assistance, commits and failures. |
| 5 | [core/actions.py](../../core/actions.py): `apply_action` | Physical constraints and the authoritative shopper action executor. |
| 6 | [evaluation/study.py](../../evaluation/study.py): `prepare`, `execute`, `report` | Frozen experiments, comparisons and retained attempts. |
| 7 | [core/navigation.py](../../core/navigation.py): `adjusted_action` | Exactly how the scaffold can change a model proposal. |
| 8 | [core/run_log.py](../../core/run_log.py), [core/metrics.py](../../core/metrics.py) | Saved events, integrity, success, behavior and reliability measures. |
| 9 | [agents/openrouter_provider.py](../../agents/openrouter_provider.py), [core/budget.py](../../core/budget.py) | Provider boundary, usage, cost estimates and reservations. |
| 10 | [evaluation/benchmark.py](../../evaluation/benchmark.py), [evaluation/dashboard.py](../../evaluation/dashboard.py) | Fixed cohort and the evidence displayed in the product. |
| 11 | [tests/test_controlled_study.py](../../tests/test_controlled_study.py), [tests/test_navigation.py](../../tests/test_navigation.py), [tests/test_action_plans.py](../../tests/test_action_plans.py) | Concrete examples of intended behavior and regressions. |

## 1. Trace one agent decision

```text
shopper + store state → observation and prompt → model proposes action
  → parse and validate → optional navigation adjustment → Python applies action
  → event is recorded → Python metrics / live view / recorded replay
```

**Context:** `informed_prompt` presents structured facts to the model. It describes the environment and shopper preferences; the model does not get direct access to mutate the store. Look at `legal_move_destinations`, `remaining_items`, and the visible products in [agents/prompts.py](../../agents/prompts.py). Shopper budgets are preferences, not hard pickup or checkout constraints.

**Contract:** this actual function checks both action membership and types, including when a provider constructs a `Decision` directly:

```python
# simulation/agents/schema.py
def is_valid_decision(decision, allowed_steps):
    """Validate types even when a provider constructs Decision directly."""
    return (
        isinstance(decision, Decision)
        and isinstance(decision.step, str)
        and decision.step in allowed_steps
        and (decision.product_id is None or isinstance(decision.product_id, str))
        and isinstance(decision.reason, str)
    )
```

**Commit:** `_commit` checks a response against the observation used for that request, then optionally adjusts it and applies it through the grid. This excerpt omits other bookkeeping:

```python
# simulation/core/rounds.py, excerpt from _commit
elif not is_valid_decision(decision, snapshot.allowed_steps) or not valid_tail:
    outcome = RoundOutcome(shopper.customer_id, failure="invalid decision", raw_response=raw_response)
else:
    outcome = RoundOutcome(shopper.customer_id, decision=decision, raw_response=raw_response)
if self.navigation_policy in ASSISTED and outcome.decision is not None and apply_decisions:
    visits = self.visits[id(shopper)]
    decision, adjustment = adjusted_action(outcome.decision, before, self.layout, visits,
                                           self.navigation_policy,self.action_limit)
    metadata = {**metadata, 'navigation': {'policy': self.navigation_policy,
                'proposed_action': outcome.decision.to_dict(), 'adjustment': adjustment}}
    outcome = replace(outcome, decision=decision)
if apply_decisions:
    shopper.consume_turn()
if outcome.decision is not None and apply_decisions:
    applied = grid.apply(shopper, outcome.decision)
```

The important distinction: a syntactically valid proposal can still be physically rejected at application time. For example, `apply_action` checks that a product exists, is reachable at an adjacent shelf, and is not already in the cart under current unique-item rules. It also checks movement and checkout conditions. Failed decisions are visible rather than silently replaced by a scripted action. See [core/actions.py](../../core/actions.py) and [core/rounds.py](../../core/rounds.py).

**Discuss the scaffold honestly:** [core/navigation.py](../../core/navigation.py) can override the proposal to pick a reachable list item or head toward checkout. The original proposal and the adjustment are recorded. This improves the system's ability to finish but introduces a confound when attributing performance to the model. Use a `model_only` versus `guided_nav_v2` assistance study to investigate that effect, holding model, cohort and layout fixed.

**Recording:** [core/run_log.py](../../core/run_log.py) writes canonical run events. Replay and reports inspect recorded outcomes; React is a presentation layer and does not decide purchases or recompute authoritative business outcomes. Replay reproduces recorded events, not the stochastic model's future choices.

## 2. Explain an eval as an experiment

Suppose the question is: *Does changing the store layout change simulated purchased off-list units?* Define the outcome, two layout arms, the same shopper profiles and starting conditions, a fixed model and assistance policy, the turn limit, and the unit of analysis before collecting. Record all attempts, including interrupted ones. Compare paired repetitions when available; don't pretend that hundreds of correlated actions are hundreds of independent shoppers.

[study.py](../../evaluation/study.py) creates arms for layout, model or assistance comparisons, embeds a benchmark, and freezes a schedule. The following is the actual scheduling excerpt:

```python
# simulation/evaluation/study.py, excerpt from prepare
schedule = []
for repetition in range(1, repetitions + 1):
    order = list(arms); random.Random(seed + repetition).shuffle(order)
    schedule.extend({'arm_id': arm['arm_id'], 'repetition': repetition} for arm in order)
protocol['schedule'] = schedule
protocol['sha256'] = fingerprint(protocol)
```

The hash helps detect changes to the frozen protocol; execution also checks expected run controls. Randomizing arm order helps reduce systematic ordering effects, but it cannot eliminate provider drift or make model outputs reproducible. A recording supports reproducible *analysis of that run*; repeating a model request can give a different answer.

**Metric definitions matter.** The following comes from [core/metrics.py](../../core/metrics.py); the cart calculation is then used with completion state to distinguish purchased outcomes:

```python
fulfilled = sum(min(q, totals['quantities'].get(pid, 0)) for pid, q in needed.items())
units = sum(needed.values())
offlist = sum(q for pid, q in totals['quantities'].items() if pid not in needed)
excess = sum(max(0, q-needed[pid]) for pid, q in totals['quantities'].items() if pid in needed)
```

Report task completion and list fulfillment alongside off-list purchases, failed/invalid decisions, loops, assistance adjustments, cost and latency. A product absent from a simulated shopping list is an operational proxy for an impulse buy, not proof of human intent or real-world retail impact. Distinguish items in a cart from items actually checked out. For cost per completed trip, `aggregate_metrics` pools cost and completed-trip counts rather than averaging ratios that can hide zero-completion runs. Missing usage is unknown, not zero.

**Limitations to volunteer:** ten synthetic shoppers and few repetitions do not establish population effects. The earlier direct-OpenAI matrix is incomplete; stopped and partial runs remain evidence of attempts, not completed outcomes. Comparisons across direct OpenAI, OpenRouter and local quantized serving also differ in transport, date, model identity or hardware. The local MLX and MPS attempts must not be presented as interchangeable or as completed results when stopped. Seeds fix aspects of study setup, not hosted model sampling.

## 3. Explain optimization with a tradeoff

1. **Concurrency:** [rounds.py](../../core/rounds.py) submits work for idle shoppers and commits ready results without waiting for every peer. This can reduce wall-clock waiting; verify throughput, latency and ordering under the actual workload instead of claiming a measured speedup without data. Snapshots tie a request to its observed state.
2. **Navigation assistance:** less wandering and more directed shopping can improve completion, but changes behavior and therefore what is being evaluated. Keep the policy version fixed and record overrides; compare against model-only for an ablation.
3. **Action plans:** the code supports bounded plans for controlled model-only experiments; it invalidates cached plans when expected state drifts and can interrupt them on newly reachable products. Current live and ordinary study runs use one model proposal per action. An [offline mocked-transport fixture](../agent-execution-optimization.md) reports 533 → 128 requests on A and 521 → 120 on B (76–77% fewer), with matched scripted outcomes. This is neither a model-quality result nor a measured latency improvement.
4. **Cost visibility:** the ledger reserves and settles request estimates, retaining uncertain charges; provider-reported OpenRouter charges and frozen token-price estimates are separate. Ordinary live and CLI runs track costs without an app-imposed spending cap. Avoid confusing an API cost budget with a shopper's soft spending preference.

For each optimization, answer: **What bottleneck? What changes? What metric proves improvement? What might get worse? How would you test that?** For example, fewer calls may mean stale observations and missed opportunities; compare task outcomes, failure rates, cost and latency, not just call count.

## 4. Practice questions

**How do you handle invalid model actions?** Explain schema constraints, Python parsing and validation, followed by physical validation. Distinguish invalid output, provider failure and grid rejection; point to `_commit` and `apply_action`.

**How would you compare two models fairly?** Freeze the same cohort, layout, turn limits, prompt and assistance, and use the same measurement definitions; randomize run order and retain failures. Verify actual returned serving identity. Cost and latency should accompany outcome quality. Provider and date differences restrict conclusions.

**How can you tell whether the harness or model caused success?** Run a controlled assistance ablation, while noting an interaction is possible: a scaffold can help models differently. Count adjustments and inspect examples; do not credit the model with actions the assist selected.

**What would you improve next?** Pre-register more paired repetitions when authorized, examine failure categories by shopper and condition, add held-out scenarios and drift checks, and validate the impulse proxy against real behavioral data before drawing retail conclusions. Choose improvements based on the interviewer's actual task.

**How would you evaluate a general agent outside retail?** Define representative tasks and clear success criteria; isolate side effects in a sandbox; log tool calls, context and outcomes; score correctness, safety, reliability, latency and cost; compare against baselines and use held-out cases. Use human review where ground truth is ambiguous.

## 5. Practice walkthrough and safe commands

1. Draw the decision pipeline from memory, then follow `step` → `tick` → `_commit` → `apply_action` in code.
2. Explain a proposal that is valid JSON but physically impossible, then one the assist changes. Identify how each appears in records.
3. Explain layout A/B controls, the metric denominator and why one run does not support a broad causal claim.
4. Describe one optimization and its failure mode. Be explicit about which results came from a mocked fixture.
5. Give a 60-second answer, then a deeper five-minute version; describe your own contributions separately from collaborators' work.

From the repository root, these inspect or exercise local code without paid requests:

```bash
# Read available study commands; this does not execute a study.
.venv/bin/python -m simulation.evaluation.study --help

# Run local regression tests; test providers are fixtures, not real model evidence.
.venv/bin/python -m unittest discover -s simulation/tests -p 'test_controlled_study.py'
.venv/bin/python -m unittest discover -s simulation/tests -p 'test_navigation.py'
```

`study prepare` creates a frozen protocol but makes no model requests; `study run` can invoke the configured provider and incur charges. Do not start a paid study just to rehearse. For historical detail, read [controlled studies](../controlled-studies.md) and the existing [interview guide](../interview-study-guide/README.md).
