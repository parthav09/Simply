# Interview study guide: agent harness, evals, optimization (Simply)

Everything here is taken from your own codebase. Paths are relative to `simulation/`.
Snippets are trimmed with `# ...` but never rewritten.

**One-sentence pitch:** *Simply is a harness that puts LLM "shoppers" in a grid store, lets the model propose one action at a time, and has a Python engine validate, apply, log and score every action, so layout and model comparisons are reproducible and auditable.*

---

## 0. Vocabulary to use in the interview

| Term | What it means in Simply |
|---|---|
| **Harness** | Everything around the model: prompt building, the action contract, validation, state transitions, logging, retries (none), cost metering |
| **Proposal vs. authority** | The model only *proposes* a `Decision`. `core/` is the sole authority that applies it |
| **Eval** | A frozen, hashed protocol (cohort, layouts, policy, model, seeds) that is executed and reported on identically for each arm |
| **Assistance policy** | `model_only` vs `guided_nav_v1/v2`: deterministic Python nudges layered on model proposals, and recorded |
| **Canonical record** | The JSONL run log. Live view, replay, metrics and the dashboard all derive from it |

---

## 1. Architecture in one picture

```
 profile + store state
        │  observe()
        ▼
 agents/prompts.py ──► prompt ──► provider (OpenAI / OpenRouter / local MPS)
                                        │  strict JSON schema
                                        ▼
                               ProposalResult(decision)
                                        │
                      core/rounds.py  _commit()
                         ├─ is_valid_decision()        (reject garbage)
                         ├─ adjusted_action()          (navigation assist, recorded)
                         ├─ grid.apply()  → core/actions.apply_action()   (ONLY mutation point)
                         └─ event_callback → RunWriter (JSONL, flushed)
                                        │
        core/metrics.py  ◄──────────────┘  summaries derived from events
        evaluation/study.py  → frozen protocol → report → dashboard → React replay
```

The rule from `AGENTS.md` that you should be able to say from memory:
**Python owns state, history, accounting and metrics. React only displays. The model never mutates anything.**

---

## 2. The harness, layer by layer

### 2.1 Observation → prompt (`agents/shopper.py`, `agents/prompts.py`)

The shopper computes which actions are legal *right now* and the prompt only offers those.

```python
# agents/shopper.py
def allowed_steps(self, state=None):
    state = state or self.state
    if isinstance(state, FinishedState):
        return []

    possible = set(MOVES)
    shelves = getattr(state, "nearby_shelves", [])
    if any(shelf.products for shelf in shelves):
        possible.add("grab")
    if state.cart:
        possible.add("remove")
        possible.add("checkout")
    return [step for step in STEP_DESCRIPTIONS if step in possible]
```

`informed_prompt` is "information only". It gives the model facts (floor map, legal destinations, visit counts, remaining items, checkout urgency) but no route solver and no purchase override:

```python
# agents/prompts.py (docstring + the facts it builds)
def informed_prompt(shopper, observation=None, *, action_plan=False):
    """Information only: no route solver, purchase override, or budget enforcement."""
    # ...
    facts = {
        'prompt_revision': 'observe-plan-v5-unique-checkout' if simple else 'observe-plan-v4-soft-budget',
        'position': [obs.x, obs.y], 'phase': obs.phase,
        'legal_move_destinations': {step: [obs.x+dx, obs.y+dy] for step, (dx,dy) in moves.items()},
        'adjacent_destination_visit_counts': {step: visited[(obs.x+dx, obs.y+dy)] for step, (dx,dy) in moves.items()},
        'remaining_items': list(remaining_by_id.values()),
        'grabbable_products': visible,
        'checkout_urgency': checkout_urgency,
        # ...
    }
```

Talking points:
- **Prompt versioning** (`prompt_revision`) lets old recordings keep their meaning.
- Facts are **JSON-serialized into the prompt** so the model reasons over structured state.
- `matches_remaining_list` marks whether a visible product is on the shopper's list. That is how impulse buys (off-list grabs) are made detectable.
- **Soft budgets:** the prompt says budgets are "personal spending targets, not engine restrictions", so overspending is *measured*, not blocked.

### 2.2 The action contract (`agents/schema.py`, `agents/openai_provider.py`)

Two layers of defense: a strict JSON schema sent to the API, then Python validation of what came back.

```python
# agents/openai_provider.py: structured output, enum restricted to legal steps
def response_schema(allowed):
    return {'type':'object','properties':{
        'step':{'type':'string','enum':list(allowed)},
        'product_id':{'type':'string'},'reason':{'type':'string'}},
        'required':['step','product_id','reason'],'additionalProperties':False}
```

```python
# agents/schema.py: never trust provider output
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

`parse_decision` is strict as well: unknown keys → `None`, wrong types → `None`. **There is deliberately no "repair" step.** An invalid reply is recorded as `invalid_decision`, and the shopper loses a turn. The provider module's docstring says it: *"No retries or action repairs."*

### 2.3 The provider boundary

`agents/providers.py` is a small factory; every backend returns the same `ProposalResult`:

```python
def build_provider(name,ledger,run_id,seed=42,bucket='manual',stage_limit_usd=None,requests_per_minute=0,model=None):
    if model is not None and name not in ('openai','openrouter','local_mps'):raise ValueError('Model selection requires a supported model provider')
    # ... local_mps, openrouter, gemini, openai ...
    if name=='fake':return FakeDecisionProvider()
    raise ValueError(f'Unsupported provider: {name}')
```

- `FakeDecisionProvider` (picks the first allowed step) is an **explicit test fixture**, never a fallback for a failed live model. Say this: *"no scripted fallback, ever."*
- Each provider records telemetry (latency, token usage, cost estimate, returned model version), which is what the evals later verify.

Cost safety lives in `core/budget.py`: **reserve → call → settle**, backed by SQLite.

```python
# core/budget.py: CampaignLedger.reserve (conservative pre-call estimate)
tokens = len(prompt.encode('utf-8')) + extra_bytes + 4096
amount = round(tokens * max(pricing['input_usd_per_million'], ...) + max_output_tokens*pricing['output_usd_per_million']) + 100
# ...
db.execute('INSERT INTO requests (id,run_id,reserved,actual,usage,created,bucket) VALUES (?,?,?,?,?,?,?)', ...)
```

If the response never reports usage, the **full reservation stays on the ledger** ("unknown-charge reservations"). `acquire_slot` paces requests across processes and "never retries a failed request".

### 2.4 The authoritative mutation point (`core/actions.py`)

Every state change goes through one function. Physical rules live here, not in the prompt:

```python
# core/actions.py
def apply_action(shopper, decision, product_id=None, grid=None):
    # ...
    allowed = grid.observe(shopper).allowed_steps if grid else shopper.allowed_steps()
    success = False
    if step in allowed:
        if step in MOVES:
            dx, dy = MOVES[step]
            if grid is None or grid.walkable(state.x + dx, state.y + dy):
                state.x += dx; state.y += dy; success = True
        elif step == 'grab' and product_id and grid is not None:
            # ... product must be on a shelf at distance 1; duplicates rejected under unique rules
```

Versioned shopping rules (`core/shopping.py`): `unique_single_checkout_v1` = one unit per SKU, duplicate pickups rejected, one checkout action finishes the trip. Old runs keep `quantity_two_phase_v1`, so **history stays readable**.

### 2.5 The loop: `SimulationSession` and `RoundCoordinator`

`core/session.py` constructs the run and writes the header (which freezes everything that matters):

```python
# core/session.py: the engine fingerprint hashes the agent source files into the run header
digest = hashlib.sha256()
for filename in ('shopper.py', 'customer.py', 'schema.py', 'steps.py', 'prompts.py'):
    digest.update(filename.encode())
    digest.update((SIMULATION_DIR / 'agents' / filename).read_bytes())
```

```python
# core/session.py: one scheduler tick
def step(self):
    active = self.active()
    if (not active and not self.coordinator.in_flight) or self._ticks >= self.max_rounds:
        self.finish()
        return False
    # ...
    outcomes = self.coordinator.tick(self.grid, active, apply_decisions=not self.propose_only,
                         event_callback=lambda e:self._record(e, tick), wait_all=self.propose_only)
```

`core/rounds.py` is the concurrency core. It is an **independent pump**: apply whichever shoppers' requests have finished, submit requests for idle shoppers, and never block on a slow peer.

```python
# core/rounds.py
def tick(self, grid, shoppers, apply_decisions=True, event_callback=None, wait_all=False):
    """Independent pump: apply ready work, submit idle shoppers, do not block on peers."""
    # ...
    self._submit_due(grid, shoppers, apply_decisions, acted)
    if wait_all and self.in_flight:
        wait_futures([flight.future for flight in self.in_flight.values()], return_when=ALL_COMPLETED)
        committed.extend(self._resolve(grid, apply_decisions, event_callback, started, block=False))
    elif self.in_flight:
        committed.extend(self._resolve(grid, apply_decisions, event_callback, started, block=not committed))
```

Detail worth knowing: `state_snapshot()` "detaches mutable state **now**, before another action can change it", so each request is tied to the state it was asked about.

`_commit()` is the heart of it. In order:

```python
# core/rounds.py :: _commit (condensed order of operations)
if error is not None:
    outcome = RoundOutcome(shopper.customer_id, failure=str(error) or type(error).__name__, ...)
elif not is_valid_decision(decision, snapshot.allowed_steps) or not valid_tail:
    outcome = RoundOutcome(shopper.customer_id, failure="invalid decision", ...)
else:
    outcome = RoundOutcome(shopper.customer_id, decision=decision, ...)

if self.navigation_policy in ASSISTED and outcome.decision is not None and apply_decisions:
    decision, adjustment = adjusted_action(outcome.decision, before, self.layout, visits, ...)
    metadata = {**metadata, 'navigation': {'policy': self.navigation_policy,
                'proposed_action': outcome.decision.to_dict(), 'adjustment': adjustment}}

if apply_decisions:
    shopper.consume_turn()                       # failed actions still cost a turn
if outcome.decision is not None and apply_decisions:
    applied = grid.apply(shopper, outcome.decision)
    outcome = replace(outcome, applied=applied, failure=None if applied else "action rejected by grid")
```

Outcome statuses written to the log: `provider_exception`, `invalid_decision`, `proposed`, `applied`, `grid_rejected`. Interview line: *"every failure mode is a first-class, recorded outcome, not an exception swallowed."*

### 2.6 Navigation assist (`core/navigation.py`), the part you must discuss honestly

`adjusted_action` is a **pure function**: `(proposal, frozen run facts) → (decision, reason|None)`. It can override the model:

```python
# core/navigation.py
# Prioritize checkout near the action limit, then reachable targets.
if owned and 'checkout' in allowed and turns_left <= 15:
    return choose('checkout', 'checkout with few turns remaining')
if 'grab' in allowed:
    for product in reachable:
        if remaining[product['id']] > 0:
            return choose('grab', 'pick up a reachable list item', product['id'])
```

and `choose` records what happened to the original proposal:

```python
def choose(step, reason, product_id=None):
    if step == proposal.step and product_id == proposal.product_id:
        return proposal, None
    return Decision(step, product_id, f'Navigation assist: {reason}. Model proposed {proposal.step}: {proposal.reason}'), reason
```

Why it matters:
- **Reproducibility/audit:** because it is pure and uses only frozen run facts, `recorded_visits(...)` can re-validate every recorded adjustment later without loading a store.
- **Confound:** assistance makes results measure *model + scaffold*. Your own doc (`docs/agent-execution-optimization.md`) notes that apparent competence can depend on programmed adjustments, so the model alone can't take credit. The studies are therefore labeled as **assisted system performance**, not raw model intelligence.
- `model_only` vs `guided_nav_v2` is a built-in ablation axis (`KINDS = ('layout', 'model', 'assistance')`).
- Impulse buys are protected: a test (`test_impulse_grab_of_an_unowned_off_list_item_is_kept`) pins that behavior for v1.

### 2.7 Action plans (an optimization, off in live runs)

The provider can return 1–8 actions per request. Python still executes **one validated action per commit** and discards the tail if reality diverges:

```python
# core/rounds.py :: _apply_cached_plan
if pending.expected_state != before:
    self.pending_plans.pop(id(shopper), None)   # state drifted → drop the plan
    return None
```
```python
# core/rounds.py :: _commit  (plan interruption)
elif decision.step in MOVES:
    # ...
    if grabbable_product_ids(grid, shopper.state.x, shopper.state.y) - old_visible:
        stop = 'new_grabbable_products'          # stop to look at newly reachable products
```

Measured **offline** (mocked transport, scripted fixture): ~76–77% fewer requests with identical per-shopper outcomes (A: 533→128, B: 521→120 requests). Be precise: `docs/agent-execution-optimization.md` says this "measure[s] execution overhead, not model quality". Current live/study runs use one proposal per action (`allow_action_plans=False` in `evaluation/study.py`).

### 2.8 The log (`core/run_log.py`)

Append-only JSONL, exclusive-create so evidence can't be overwritten, flushed per event so the UI can stream:

```python
class RunWriter:
    """One coordinating thread writes; exclusive creation protects existing evidence."""
    def __init__(self, path, start):
        # ...
        self.handle = self.path.open("x", encoding="utf-8")   # "x" = fail if exists
```

`read_run()` replays and **validates** the entire log: each event's `before` must equal the previous `after`, nothing may follow `run_end`, and a truncated final line is recovered with a warning. `finish()` refuses to write `run_end` unless the final state matches what the log recorded ("Never assert a state transition that did not reach the log").

---

## 3. Evals

### 3.1 Design principles (the answers to "how do you make an eval trustworthy?")

1. **Freeze inputs before collecting** (`evaluation/study.py::prepare`): fixed cohort of 10 shoppers, both layouts, seed, policy, turn budget. Nothing calls a model during `prepare`.
2. **Hash the protocol** and verify on load:
```python
protocol['sha256'] = fingerprint(protocol)
# ...
def load_protocol(directory):
    protocol = json.loads((Path(directory) / 'protocol.json').read_text())
    if protocol.get('study_version') != 1 or fingerprint({k: v for k, v in protocol.items() if k != 'sha256'}) != protocol.get('sha256'):
        raise ValueError('Study protocol integrity mismatch')
```
3. **Refuse to run if code or inputs drifted:**
```python
for arm in protocol['arms']:
    if template(protocol, arm, 1) != expected(protocol, arm, 1):
        raise ValueError('Code or inputs changed since preparation; prepare a new study directory')
```
and again per session: `controls(session.header) != expected(...)` → cancel *before* any model request.
4. **Same cohort across arms; randomized order within a repetition** (seeded shuffle, so time-of-day/provider drift isn't aligned with one arm):
```python
for repetition in range(1, repetitions + 1):
    order = list(arms); random.Random(seed + repetition).shuffle(order)
```
5. **Identical assistance and one decision per action across model arms**, so a model comparison isn't confounded by scaffolding.
6. **Retain failures; never auto-retry:** `'Stopped attempt retained; no automatic retry...'`. Partial runs stay in the evidence.
7. **Verify what actually served you:** the report raises if decisions lack returned model-version evidence or the version drifts within a study (`'Actual model version drift within the frozen study'`).
8. **Descriptive, not inferential, when n is small.** The report's own limitations say fewer than five paired repetitions give "descriptive differences without a confidence interval", that actions within a run aren't independent, and that seeds fix pairing/order, not model output.

### 3.2 Metrics (`core/metrics.py`, `core/evidence.py::METRICS`)

All metrics are computed from the log, by pure functions of `(start, events, final)`:

```python
# core/metrics.py: impulse measure used in the product UI
offlist = sum(q for pid, q in totals['quantities'].items() if pid not in needed)
excess  = sum(max(0, q-needed[pid]) for pid, q in totals['quantities'].items() if pid in needed)
# ...
'off_list_units': offlist, 'excess_list_units': excess,
'list_completion': fulfilled/units if units else 1.0,
'checkout_overshoot_cents': overshoot if old['finished'] else 0,
```

Behavior-quality metric, loop detection by repeated signatures:

```python
def loop_metrics(events):
    # signature = (x, y, phase, cart contents, action or outcome)
    for n in range(1, 5):
        if len(signatures) >= 3*n and signatures[-n:] == signatures[-2*n:-n] == signatures[-3*n:-2*n]:
            loops += 1
            break
    return {'loop_detections': loops, 'longest_no_progress_turns': longest}
```

Money is in **integer cents** (`core/accounting.py::cents` uses `Decimal` with `ROUND_HALF_UP`), so replay and export can't drift by float error.

Metric families to be able to list: **task success** (`checkout_completion`, `purchased_unit_fulfillment`), **behavior** (`purchased_off_list_units`, `checkout_overshoot_cents`, `overspending_fraction`), **reliability** (`invalid_decision_count`, `grid_rejection_count`, `provider_failure_count`, `loop_detections`), **scaffold dependence** (`navigation_adjustments`), **cost/latency** (`known_estimated_cost_usd`, `cost_per_completed_trip_usd`, `request_latency_p50/p95_ms`).

### 3.3 Aggregation choices that show care

```python
# evaluation/study.py::aggregate_metrics
# Pool the numerator and denominator. Averaging per-run ratios would discard
# zero-checkout runs or overweight runs with fewer completed shoppers.
metrics['cost_per_completed_trip_usd'] = (sum(costs) / finished if finished and costs ...
```
Paired comparisons use repetition blocks and a bootstrap (`evaluation.run.bootstrap`):

```python
paired.append({'comparison': f"{right['arm_id']} minus {left['arm_id']}", 'metric': key,
    'mean_difference': mean(differences) if differences else None, 'ci95': bootstrap(differences),
    'blocks': len(differences), 'missing_blocks': protocol['repetitions'] - len(differences), ...
```

Unknown stays unknown: costs with missing usage make the aggregate `None` rather than a guess.

### 3.4 Study lifecycle (CLI)

```bash
python -m simulation.evaluation.study prepare --directory <dir> --kind layout|model|assistance --provider openai
python -m simulation.evaluation.study run     --directory <dir>      # executes frozen schedule, one slot per run
python -m simulation.evaluation.study report  --directory <dir>      # read-only recompute, no API calls
python -m simulation.evaluation.study publish --directory <dir>      # exports to landing/public/replays
```

Execution flags are forbidden after `prepare`: `'Execution/reporting use frozen protocol settings; configuration flags apply only to prepare'`.

### 3.5 From evals to the product

`evaluation/dashboard.py` assembles every recording into the Evidence JSON the React app reads. The architecture rule is that **React filters/display only; totals come from Python.** Replay equivalence checks (`landing/scripts/verify-dashboard.cjs`, `verify-ui.cjs`) enforce that React shows the same numbers as Python.

---

## 4. Optimization story: what was optimized and why

| Problem | Change | Where | Caveat to state |
|---|---|---|---|
| One request per cell moved → slow and expensive | Pump scheduler: apply ready work, don't wait on peers | `core/rounds.py::tick` | Faster wall-clock; each shopper's decisions unchanged |
| Model lacked sight of upcoming shelves | Prompt shows shelves within 6 cells, marks remaining targets | `agents/prompts.py` (`nearby_shelves`) | Prompt revision changes results; versioned in `prompt_revision` |
| Cost uncertainty | Reserve/settle ledger, prompt-cache TTL, token-usage normalization | `core/budget.py`, `openai_provider.py::normalize_usage` | Token-price estimates ≠ provider-reported charges (kept separate for OpenRouter) |
| Wandering/loops | Visit counts in prompt + assist that prefers least-visited cell | `prompts.py`, `navigation.py` | Assist inflates apparent model skill; report `navigation_adjustments` |
| Request volume | 1–8 action plans with state-drift invalidation | `rounds.py::_apply_cached_plan` | Measured offline only; disabled in studies for one-decision-per-action purity |
| Studies not comparable | Frozen protocols + hash + engine fingerprint | `study.py`, `session.py::build_run_start` | Fingerprint covers the agent files; engine changes require a new study |

**How to frame it:** *"I optimized for measurement validity first, then for speed. Anything that changes behavior is versioned and recorded, so an old result never silently changes meaning."*

---

## 5. Likely interview questions, with answers grounded in the code

**Q: What is an agent harness?**
The code that wraps the model: it builds observations into prompts, constrains outputs with a schema, validates proposals, applies them through a single authoritative executor, logs everything, and enforces cost/time limits. In Simply: `prompts.py` → `schema.py` → `rounds._commit` → `actions.apply_action` → `RunWriter`.

**Q: How do you handle bad model output?**
Strict schema at the API, strict parser (`parse_decision`), `is_valid_decision` against the *currently legal* steps, then physical validation in `apply_action`. Failures are recorded (`invalid_decision`, `grid_rejected`) and consume a turn. No repair, no silent retry, no fallback action.

**Q: Why not let the model's output run directly?**
Single source of truth. The model is a proposer; correctness, accounting and metrics can't depend on its mood. It also makes replay deterministic: React replays recorded events and cannot invent outcomes.

**Q: How do you know an eval result is real?**
Frozen/hashed protocol, drift checks before dispatch, same cohort across arms, randomized order, model-version evidence checks, retained failures, and a `report` command that recomputes everything from the raw logs with no API key.

**Q: What are the weaknesses of your evals?**
(Say these proactively.)
- Small n: ten fixed profiles, mostly one repetition; some studies exploratory and the five-repetition matrix is incomplete (credits ran out).
- Assistance confound: `guided_nav_v2` adjusts actions, so results are *system* performance.
- Model seeds aren't supported by the API; the seed controls order/pairing, not outputs.
- Simulated shoppers ≠ real customers; no crowding or queues.
- Comparisons across providers/dates (OpenAI direct vs OpenRouter vs local MPS quantized) carry transport and quantization differences.

**Q: How would you measure the effect of the scaffold?**
Run the `assistance` study kind: same model, `model_only` vs `guided_nav_v2`, identical cohort and layout; compare completion and `navigation_adjustments`.

**Q: How did you make runs reproducible given non-deterministic models?**
You can't make outputs deterministic, so reproduce the *conditions* and make the *analysis* reproducible: frozen inputs and hash, recorded raw prompt/response per event, recomputable metrics. (`temperature .3`, `reasoning effort none`, service tier and cache TTL are frozen in `generation_settings`.)

**Q: Tradeoffs of one-action-per-request vs plans?**
Plans cut requests ~76% (offline) but let the model act on stale assumptions; the drift check (`expected_state != before`) and interrupt-on-new-products mitigate that. For studies, one decision per action keeps arms identical and attributable.

**Q: How do you control cost?**
Reserve before call, settle after, keep full reservation on unknown usage; request pacing across processes; per-run frozen price snapshot; cap enforcement is opt-in for controlled studies only. (Check `AGENTS.md`: ordinary live/CLI runs track costs without a cap.)

**Q: What would you improve next?**
More repetitions with confidence intervals, an ablation across assist levels, LLM-judge or human review of "reason" text for faithfulness, automated regression suite replaying frozen golden runs on every prompt change.

---

## 6. How to demo it in five minutes

1. Open one run JSONL from `runs/` and show a `decision` record: `before`, `prompt`, `raw_response`, `action`, `outcome`, `telemetry`, `after`.
2. Point to a `navigation.adjustment` in telemetry. This shows the model proposed X and the engine applied Y, and both are recorded.
3. Show `protocol.json` (`sha256`, `arms`, `schedule`) in `runs/studies/<study>/`.
4. Run `python -m simulation.evaluation.study report --directory <study>` to show recomputation with no model call.
5. Open the Evidence page in `landing/` and point out that the numbers come from `evaluation/dashboard.py`.

---

## 7. Reading order and self-quiz

Read in this order (about 90 minutes): `core/actions.py` → `agents/schema.py` → `agents/prompts.py` (skim) → `core/rounds.py::_commit` → `core/navigation.py` → `core/session.py::step/finish` → `core/run_log.py::RunWriter/read_run` → `core/metrics.py` → `evaluation/study.py::prepare/execute/report`.

Self-quiz, answer without looking:
1. Which single function mutates shopper state? (`apply_action`)
2. What happens when the model returns an illegal step? (recorded `invalid_decision`, turn consumed, no fallback)
3. Why is `adjusted_action` a pure function? (replay validation from frozen facts; audit)
4. Why `open(path, "x")`? (never overwrite evidence)
5. Why integer cents? (no float drift across execution/replay/export)
6. What stops you running a study after changing the prompt? (`template(...) != expected(...)`)
7. Why pool numerator/denominator for cost per checkout? (zero-checkout runs would vanish from a mean of ratios)
8. What does the offline 76% request reduction *not* tell you? (anything about model quality)

Tests that document the intended behavior: `tests/test_navigation.py`, `tests/test_simple_shopping.py`, `tests/test_controlled_study.py`, `tests/test_action_plans.py`, `tests/test_report_reproducibility.py`.

---

## 8. Honesty notes for you

- Be precise about which parts of Simply you wrote, which you designed, and which you used AI assistance or existing libraries for.
- Don't overstate results. `AGENTS.md` says published findings are exploratory, and the planned five-repetition matrix is incomplete.
- Several study directories were interrupted or stopped by choice (MPS and MLX attempts). If asked, say so plainly; the records were retained on purpose.
