'use client';

import { B, Code, DeckShell, type Slide } from './kit';
import { BeforeAfter, LiveReplay, LoraLab, Pipeline, ResultsBars, RunCheckBars } from './widgets';

/**
 * Technical interview draft. Dense by design. Numbers are quoted from Python-written sources
 * (evidence-dashboard.json, run-checks.json, the adapter ZIP's experiment.json and offline evals,
 * impulse_v3/manifest.json, recorded runs). Code is condensed from the named files.
 */

const slides: Slide[] = [
  // ── 0 · Opening ──────────────────────────────────────────────────────────
  { section: 'Overview', title: 'title', body: <div className="pz-two">
      <div><p className="pz-eyebrow">Simply · technical walkthrough</p>
        <h1>An evaluation harness for persona-conditioned LLM agents.</h1>
        <p className="pz-lede">Shoppers on a grid store; a model proposes one action per call; Python validates, optionally assists, applies, records and scores; React replays verified records.</p></div>
      <div className="pz-card"><p className="pz-eyebrow">Agenda · 30 min</p><ol>
        <li>Problem formulation & data</li><li>Agent interface: prompt, schema, validation</li><li>Harness: scheduler, assist, recording, replay</li><li>Results & cost accounting</li><li>QLoRA fine-tuning of Qwen2.5 7B</li><li>Evals, guardrails, threats to validity</li></ol>
        <p className="pz-caption">Stack: Python 3.11 core (no UI imports) · OpenRouter / OpenAI providers · Unsloth + PEFT on a Colab A100 · Next.js 16 / React replay · SSE live bridge.</p></div>
    </div>,
    notes: 'Frame it as a harness, not a product: the contribution is the execution and evaluation machinery and what it lets me measure. Mention the authority boundary up front, since every later slide depends on it.' },

  { section: 'Overview', title: 'Formulation', steps: 1, body: <div className="pz-two">
      <div><h2>Formulation: a finite-horizon sequential decision problem.</h2>
        <table className="pz-table"><tbody>
          <tr><th>State s</th><td>position, cart, phase, turns used; frozen layout, catalogue and profile</td></tr>
          <tr><th>Observation o</th><td>prompt: persona text + “Current state” JSON (32 keys) + legal step menu</td></tr>
          <tr><th>Action a</th><td>{'{move_left|right|up|down, grab(product_id), remove(product_id), checkout}'}</td></tr>
          <tr><th>Transition</th><td>deterministic, owned by Python (grid.py, shopping.py); illegal → rejected</td></tr>
          <tr><th>Horizon</th><td>120 actions per shopper; ends at paid checkout or limit</td></tr>
          <tr><th>Policy π</th><td>LLM(o) → one action, optionally adjusted by guided_nav_v3</td></tr>
        </tbody></table>
        <p className="pz-caption">No reward is optimised. Inference-time conditioning only; fine-tuning is supervised (behaviour cloning).</p></div>
      <B at={1}><div><h3>Metrics (computed in Python, metrics.py / dashboard.py)</h3>
        <code className="pz-formula">completion = finished trips / trips</code>
        <code className="pz-formula">fulfilment = Σ paid listed units / Σ requested units</code>
        <code className="pz-formula">impulse/trip = Σ off_list_units (paid only) / trips</code>
        <code className="pz-formula">cost/checkout = Σ provider charge / finished trips</code>
        <code className="pz-formula">adjusted = assist-changed decisions / decisions</code>
        <p>Completion ≠ fulfilment: a shopper can pay for a partial list. Impulse counts only checked-out carts, so an abandoned basket adds nothing.</p></div></B>
    </div>,
    notes: 'This is the MDP framing an interviewer will look for. Be explicit that there is no reward and no RL. Observation is a projection of state: the model does not see the full grid state, only what Python puts in the prompt.' },

  { section: 'Overview', title: 'Data', steps: 2, body: <div className="pz-two">
      <div><h2>Inputs: synthetic, frozen and fingerprinted.</h2>
        <table className="pz-table"><thead><tr><th>File</th><th>Shape</th><th>Role</th></tr></thead><tbody>
          <tr><th>customer_profiles_50.csv</th><td>50 × 41</td><td>persona pool</td></tr>
          <tr><th>shopping_lists_50.csv</th><td>497 rows</td><td>priority, qty, max price</td></tr>
          <tr><th>products.csv</th><td>303 × 25</td><td>price, dept, diet tags, allergens</td></tr>
          <tr><th>two_layouts_15_v2.json</th><td>15 shoppers</td><td>frozen benchmark cohort</td></tr>
        </tbody></table>
        <B at={1}><p><b>Cohort construction:</b> style/budget bands, original priority order, lists trimmed to ≤ 80% of budget and acceptable prices, and a greedy route proving feasibility in ≤ 96 turns. Runs use the default 10. Isabella’s raw list has 15 rows; her frozen list has 11.</p></B>
        <B at={2}><p><b>Fingerprints:</b> each run_start stores input, layout, engine and provider fingerprints plus a cohort SHA-256, so two runs are comparable only if they match.</p></B></div>
      <Code file="two_layouts_15_v2.json · customers[C0007].shopping_list[0]">{`
{
  "list_id": "L0007",
  "product_id": "P0035",
  "product_name": "Large Eggs",
  "department": "Dairy & Eggs",
  "quantity": 2,
  "priority": "must_have",
  "on_written_list": true,
  "expected_unit_price": 4.29,
  "max_acceptable_unit_price": 5.19,
  "substitute_allowed": true,
  "preferred_brand": "Eggland's Best"
}`}</Code>
    </div>,
    notes: 'Reference paths prove feasibility only; they never pick model actions. Prices and budgets are soft preferences: overspending is recorded, never rejected.' },

  { section: 'Overview', title: 'Environment', steps: 1, body: <div className="pz-two">
      <div><h2>Environment: a 22 × 14 grid with versioned rules.</h2>
        <ul><li>15 shelf groups on slots x ∈ {'{1,5,9,13,17}'}, y ∈ {'{1,5,9}'}; front row zone differs by layout (front_impulse in A, front_essential in B); a Snacks feature display at (17, 9) in both.</li>
          <li>Entrance cells (1–7, 12), checkout (16–20, 12). Grab only from a cell adjacent to the shelf group.</li>
          <li><b>unique_single_checkout_v1:</b> one unit per SKU, duplicate pickups rejected, checkout pays in one action and requires a non-empty cart on a checkout cell.</li>
          <li>Inventory replenished, no crowd blocking, no queues: the only variable between A and B is department order.</li></ul></div>
      <B at={1}><Code file="simulation/core/grid.py · layout definitions (condensed)">{`
("costco_back_anchor", "Layout A — Anchor loop",
 "Staples at the back, with snacks and bakery near the entrance.",
 list(DEPARTMENTS)),
("neighborhood_express", "Layout B — Express essentials",
 "Daily essentials near the entrance for shorter shopping trips.",
 ["Pet", "Baby", "Household", "Health & Beauty", "Frozen",
  "Snacks", "Pantry", "Beverages", "Prepared Meals",
  "Ramen & Noodles", "Produce", "Dairy & Eggs", "Meat & Seafood", "Bakery"]),
...
zone = "back_anchor" if y <= 5 and department in ranked[:6] else "mid_store"
if y == 9:
    zone = "front_essential" if layout_id == "neighborhood_express" else "front_impulse"`}</Code></B>
    </div>,
    notes: 'Shelf visibility today is shelf-level adjacency. The open design decision is product-level adjacency as a new frozen rule version, with older runs still verifiable under the old rule.' },

  // ── 1 · Agent interface ──────────────────────────────────────────────────
  { section: 'Agent', title: 'Prompt', wide: true, body: <div className="pz-two">
      <div><h2>Observation = prompt. ~8k tokens in, ~35 out.</h2>
        <ol><li>Persona summary and behavioural directives (customer.py)</li><li>Mission, budget policy (soft), “work one target at a time”</li><li><b>Current state</b> JSON: position, cart, spend/budget, remaining_items, grabbable_products, nearby_shelves, department_locations, floor_map, legal_move_destinations, adjacent visit counts, recent actions/positions, turns, checkout_urgency, allowed_steps</li><li>Step menu and reply contract</li></ol>
        <table className="pz-table"><thead><tr><th>Per request</th><th>Input tok</th><th>Output tok</th><th>p50 / p95</th></tr></thead><tbody>
          <tr><th>Terra A</th><td>7,994</td><td>34.3</td><td>1.98 / 2.91 s</td></tr>
          <tr><th>Luna A</th><td>7,769</td><td>39.4</td><td>1.24 / 1.98 s</td></tr>
          <tr><th>Qwen tuned A</th><td>6,050</td><td>30.7</td><td>0.97 / 1.39 s</td></tr></tbody></table>
        <p className="pz-caption">Token counts differ by tokenizer. prompt_revision observe-plan-v5-unique-checkout, variant informed.</p></div>
      <Code file="Current state (trimmed, impulse_v3 training row)">{`
{
  "position": [8, 10],
  "cart": [{"product_id": "P0166", "name": "Instant Coffee", "quantity": 1}, ...],
  "budget_cents": 10631, "remaining_budget_cents": 7786,
  "remaining_items": [{"product_id": "P0115", "name": "Chicken Broth",
     "priority": "must_have", "max_unit_price_cents": 280}, ...],
  "grabbable_products": [{"product_id": "P0070", "name": "100% Whole Wheat Bread",
     "unit_price_cents": 379, "dietary_tags": "vegan;vegetarian",
     "allergens": "wheat/gluten", "matches_remaining_list": false,
     "affordable_with_remaining_budget": true}, ...],
  "turns_used": 54, "turns_remaining": 66, "action_limit": 120,
  "checkout_urgency": "low",
  "allowed_steps": ["move_left", "move_right", "move_up", "move_down", "grab", "checkout"]
}
→ {"step": "grab", "product_id": "P0079",
   "reason": "Unplanned pick: Corn Tortillas for $2.79 fits my budget; ..."}`}</Code>
    </div>,
    notes: 'The model is stateless between calls; the harness reconstructs context each turn (recent actions, positions, last plan). That is external memory, not model memory. Most of the prompt is a stable prefix, which is why prompt caching matters for cost.' },

  { section: 'Agent', title: 'Validation', steps: 1, body: <div className="pz-two">
      <div><h2>Three gates: schema, observation, physics.</h2>
        <p><b>1 · Structured output.</b> response_format json_schema, strict: true, max_tokens 256, reasoning off. Exactly {'{step, product_id, reason}'}, all strings.</p>
        <p><b>2 · Observation-valid.</b> The step must be in allowed_steps; a grab must name a grabbable, unowned product; checkout needs a non-empty cart on a checkout cell.</p>
        <p><b>3 · Physical apply.</b> grid.apply can still reject (reachability, duplicate SKU).</p>
        <B at={1}><table className="pz-table"><thead><tr><th>Outcome</th><th>Meaning</th><th>Luna A/B</th><th>Tuned A/B</th></tr></thead><tbody>
          <tr><th>applied</th><td>committed</td><td>—</td><td>—</td></tr>
          <tr><th>invalid_decision</th><td>failed gate 1/2</td><td>12 / 9</td><td>35 / 66</td></tr>
          <tr><th>grid_rejected</th><td>failed gate 3</td><td>1 / 0</td><td>1 / 1</td></tr>
          <tr><th>provider_exception</th><td>transport/API error</td><td>0 / 0</td><td>0 / 0</td></tr></tbody></table>
          <p className="pz-caption">Terra: 0 invalid, 0 rejected on both layouts. Each failure still consumes a turn.</p></B></div>
      <Code file="simulation/evaluation/impulse_eval.py · check_action (same contract)">{`
def check_action(text, facts):
    try:
        action = json.loads(text)
    except (TypeError, ValueError):
        return None, False
    if not isinstance(action, dict) or set(action) != {'step', 'product_id', 'reason'}:
        return None, False
    step, product_id = action['step'], action['product_id']
    owned = {item['product_id'] for item in facts['cart']}
    valid = step in facts['allowed_steps']
    if step.startswith('move_'):
        valid = valid and not product_id and step in facts['legal_move_destinations']
    elif step == 'grab':
        valid = valid and product_id in {p['product_id'] for p in facts['grabbable_products']} \\
                      and product_id not in owned
    elif step == 'remove':
        valid = valid and product_id in owned
    elif step == 'checkout':
        valid = valid and not product_id and bool(owned) \\
                      and facts['position'] in facts['checkout_cells']
    return action, bool(valid)`}</Code>
    </div>,
    notes: 'Schema validity is not physical validity. Separating the failure classes matters: an invalid reply is a model-quality signal, a provider exception is infrastructure, a grid rejection is a physics mismatch. Collapsing them would hide which system failed.' },

  // ── 2 · Harness ──────────────────────────────────────────────────────────
  { section: 'Harness', title: 'Pipeline', wide: true, body: <div><h2>One decision through the harness.</h2><Pipeline/></div>,
    notes: 'Walk the seven stages quickly; the next slides go deeper on scheduling, the assist and recording.' },

  { section: 'Harness', title: 'Scheduler', steps: 1, body: <div className="pz-two">
      <div><h2>Scheduler: no barrier, one writer.</h2>
        <ul><li><b>ThreadPoolExecutor</b> (default 10 workers; OpenRouter runs 2 at 60 req/min). I/O-bound calls, so threads are enough despite the GIL.</li>
          <li><b>in_flight</b> map: at most one pending request per shopper; idle shoppers are submitted each tick.</li>
          <li><b>tick()</b> resolves ready futures and only blocks if nothing committed: a 20 s call never stalls a 1 s one.</li>
          <li>Workers return (proposal, latency, error, telemetry). Only the owning thread mutates state, so no locks on shopper state.</li>
          <li>Observation is snapshotted before submit, binding each proposal to the state it saw.</li></ul>
        <B at={1}><p className="pz-note">Shoppers are independent (no shared stock, no queues), so commit order does not change outcomes. Scarce inventory would need reservations and conflict resolution.</p></B></div>
      <Code file="simulation/core/rounds.py · RoundCoordinator.tick (condensed)">{`
def tick(self, grid, shoppers, apply_decisions=True, event_callback=None, wait_all=False):
    """Independent pump: apply ready work, submit idle shoppers,
    do not block on peers."""
    committed, acted = [], set()
    for shopper in shoppers:
        if id(shopper) in self.in_flight:
            continue
        ...
    self._submit_due(grid, shoppers, apply_decisions, acted)
    if wait_all and self.in_flight:
        wait_futures([f.future for f in self.in_flight.values()],
                     return_when=ALL_COMPLETED)
        committed.extend(self._resolve(grid, apply_decisions,
                                       event_callback, started, block=False))
    elif self.in_flight:
        committed.extend(self._resolve(grid, apply_decisions, event_callback,
                                       started, block=not committed))
    return tuple(committed)`}</Code>
    </div>,
    notes: 'Why threads not asyncio: provider SDK calls are blocking and the work is network-bound; a small pool is simple and the single-writer rule removes races. Reconnecting the browser never starts a new run.' },

  { section: 'Harness', title: 'Assist', steps: 2, body: <div className="pz-two">
      <div><h2>guided_nav_v3: a pure, versioned override.</h2>
        <table className="pz-table"><thead><tr><th>Priority</th><th>Rule</th></tr></thead><tbody>
          <tr><th>1</th><td>owned items, checkout allowed, ≤ 15 turns left → checkout</td></tr>
          <tr><th>2 (v3)</th><td>keep the model’s reachable, unowned off-list grab while turns &gt; 15 and &gt; 30%</td></tr>
          <tr><th>3</th><td>a reachable list item → grab it</td></tr>
          <tr><th>4</th><td>grabbing an owned item → least-visited move</td></tr>
          <tr><th>5</th><td>list done or &lt; 30% turns → checkout / head to nearest checkout</td></tr>
          <tr><th>6</th><td>no shelf in reach → avoid busier cells</td></tr></tbody></table>
        <B at={1}><table className="pz-table"><thead><tr><th>Adjusted</th><th>A</th><th>B</th></tr></thead><tbody>
          <tr><th>Terra</th><td>6.1% (31/510)</td><td>5.4%</td></tr><tr><th>Luna</th><td>8.4%</td><td>4.7%</td></tr>
          <tr><th>Qwen base</th><td>38.7%</td><td>35.6%</td></tr><tr><th>Qwen tuned</th><td>13.1%</td><td>14.3%</td></tr></tbody></table></B>
        <B at={2}><p className="pz-note">The adjusted fraction is itself a quality signal, and the main confound: results are for model + assist. Proper ablation = same cohort with policy model_only.</p></B></div>
      <Code file="simulation/core/navigation.py · adjusted_action (condensed)">{`
def adjusted_action(proposal, before, layout, visits, policy, action_limit=None):
    ...
    def choose(step, reason, product_id=None):
        if step == proposal.step and product_id == proposal.product_id:
            return proposal, None
        return Decision(step, product_id,
            f'Navigation assist: {reason}. Model proposed {proposal.step}: {proposal.reason}'), reason

    if owned and 'checkout' in allowed and turns_left <= 15:
        return choose('checkout', 'checkout with few turns remaining')
    if (policy == GUIDED_V3 and proposal.step == 'grab' and proposal.product_id
            and 'grab' in allowed and not owned[proposal.product_id]
            and not remaining[proposal.product_id]
            and any(p['id'] == proposal.product_id for p in reachable)
            and turns_left > 15 and turns_left / limit > .30):
        return proposal, None          # v3: keep the shopper's own impulse grab
    if 'grab' in allowed:
        for product in reachable:
            if remaining[product['id']] > 0:
                return choose('grab', 'pick up a reachable list item', product['id'])
    ...`}</Code>
    </div>,
    notes: 'Real example: Terra A decision 140, Mia proposed move_down; applied move_right, "head toward checkout". v1/v2 replaced impulse grabs with list grabs, which erased the measured behaviour; v3 fixed that. v1 and v2 remain in code because old recordings verify against them.' },

  { section: 'Harness', title: 'Record', steps: 1, body: <div className="pz-two">
      <div><h2>Canonical JSONL: the run is the evidence.</h2>
        <p><b>run_start:</b> schema_version, metrics_version, config (policy, rules, limits, generation), layout, catalogue, shoppers, pricing, input/layout/engine/provider fingerprints.</p>
        <p><b>decision</b> (one per action): before/after state, full prompt, raw_response, applied action, outcome, failure, telemetry (proposal + adjustment + usage), elapsed_ms.</p>
        <p><b>run_end:</b> summary metrics. Records are flushed line by line; a logging failure stops execution.</p>
        <B at={1}><p className="pz-note">Live SSE streams flushed lines only (LiveProjection rejects an “Unflushed record”), so live and replay read the same bytes and reconnecting never restarts a run.</p></B></div>
      <Code file="decision record (Terra A run b0ba564d…, sequence 140, trimmed)">{`
{
  "type": "decision", "sequence": 140, "round": 140, "agent_id": "C0002",
  "before": {"x": 4, "y": 3, "phase": "BrowsingState", "turns_used": 14,
             "turn_budget": 120, "cart": [...], "requirements": [...],
             "allowed_steps": ["move_left", "move_right", "move_up", "move_down", "remove"]},
  "prompt": "You are shopper Mia Brown (C0002). …",
  "raw_response": "{\\"step\\":\\"move_down\\",\\"product_id\\":\\"\\",\\"reason\\":\\"The ramen is collected; …\\"}",
  "action": {"step": "move_right", "product_id": "",
             "reason": "Navigation assist: head toward checkout. Model proposed move_down: …"},
  "outcome": "applied", "failure": null,
  "telemetry": {
    "navigation": {"policy": "guided_nav_v3",
                   "proposed_action": {"step": "move_down", ...},
                   "adjustment": "head toward checkout"},
    "usage": {"promptTokenCount": 5641, "candidatesTokenCount": 33, ...},
    "provider_reported_cost_usd": ..., "serving_provider": ..., "request_seed": ...,
    "api_latency_ms": ..., "admission_wait_ms": ..., "prompt_bytes": ...
  },
  "after": {...}, "elapsed_ms": 293031.4
}`}</Code>
    </div>,
    notes: 'Storing the prompt and raw response makes every decision auditable and lets me re-score offline without new API calls. The before/after states make replay a lookup, not a re-simulation.' },

  { section: 'Harness', title: 'Verify', steps: 2, body: <div className="pz-two">
      <div><h2>Verification: recompute, don’t trust.</h2>
        <ol className="pz-steps">
          <li><b>Integrity:</b> SHA-256 of each source JSONL, bundle, dashboard and index; React refuses a mismatch.</li>
          <B at={1} as="li"><b>Assist re-check:</b> re-run the pure assist on every recorded state with recorded visit counts; the raw reply must parse to the recorded proposal, and the result must equal the recorded action and adjustment.</B>
          <B at={2} as="li"><b>Cross-language equivalence:</b> verify:replay checks Python and TypeScript reconstruct identical frames (25 frames, seeking, identity, failure isolation, no browser policy).</B></ol>
        <p className="pz-caption">Deterministic replay ≠ deterministic inference: request seeds are unsupported, so a fresh run is a new sample.</p></div>
      <Code file="simulation/core/run_log.py · navigation check (condensed)">{`
proposal = Decision(proposed['step'], proposed['product_id'] or None, proposed['reason'])
_require(is_valid_decision(proposal, record['before']['allowed_steps']),
         'invalid original navigation proposal')
if record['raw_response'] is not None:
    _require(parse_decision(record['raw_response'],
                            record['before']['allowed_steps']) == proposal,
             'navigation proposal differs from model response')
expected, adjustment = adjusted_action(
    proposal, record['before'], start['layout'],
    recorded_visits(start, events, record['agent_id']),
    policy, start['config'].get('action_limit'))
_require(record['action'] == expected.to_dict()
         and navigation.get('adjustment') == adjustment,
         'navigation adjustment contradicts recorded history')`}</Code>
    </div>,
    notes: 'This is why adjusted_action is a pure function of explicit inputs: it makes the override auditable after the fact. The same idea, recompute instead of trust, applies to dashboard metrics: dashboard.py cross-checks per-trip sums against run summaries.' },

  { section: 'Harness', title: 'Providers', steps: 1, body: <div className="pz-two">
      <div><h2>Providers & cost accounting.</h2>
        <ul><li>Provider adapters (openrouter, openai, local MLX/MPS/CUDA) return a proposal plus telemetry; none mutates state.</li>
          <li>Dated model IDs and the serving provider are frozen; fallbacks and response-healing plugins disabled; returned serving identity recorded.</li>
          <li><b>Two ledgers:</b> estimated = tokens × frozen price snapshot; provider-reported = OpenRouter charge. Unknown-usage requests are reserved, not zeroed.</li>
          <li>No app-enforced spend cap on manual runs; controlled studies opt into frozen budgets. Rate and quota limits are separate.</li></ul>
        <B at={1}><table className="pz-table"><thead><tr><th>Per run (A)</th><th>Input tok</th><th>Estimated</th><th>Reported</th></tr></thead><tbody>
          <tr><th>Terra</th><td>4,076,838</td><td>$5.1832</td><td>$5.1832</td></tr>
          <tr><th>Luna</th><td>4,715,971</td><td>$0.6014</td><td>$0.6014</td></tr></tbody></table></B></div>
      <Code file="run_start.config.generation + pricing (Terra A)">{`
"generation": {
  "max_tokens": 256, "reasoning": {"effort": "none"},
  "response_format": "strict_json_schema", "stream": false,
  "request_seed_supported": false,
  "provider": {"only": ["openai"], "order": ["openai"],
               "ignore": ["openai/flex", "openai/fast"],
               "allow_fallbacks": false, "require_parameters": true},
  "plugins": []
},
"pricing": {
  "model": "gpt-6.1-terra", "as_of": "2026-10-29",
  "input_usd_per_million": 1.0, "cached_usd_per_million": 0.05,
  "output_usd_per_million": 5.0,
  "cost_basis": "frozen token-price estimate; OpenRouter-reported charge recorded separately"
}`}</Code>
    </div>,
    notes: 'Without pinning, OpenRouter could route to a different backend or variant and silently change the system under test. Shopper basket dollars are simulated and never mixed with API dollars.' },

  { section: 'Harness', title: 'Replay demo', wide: true, body: <div><h2 className="pz-inline">Recorded runs, replayed from verified JSONL. <small>Same decision counter on both layouts.</small></h2><LiveReplay/></div>,
    notes: 'Demo: Terra, then switch to Qwen tuned to show wandering and invalid replies. Nothing here calls a model.' },

  // ── 3 · Results ──────────────────────────────────────────────────────────
  { section: 'Results', title: 'Results', wide: true, body: <div><h2 className="pz-inline">Latest runs: OpenRouter, guided_nav_v3, 10 shoppers, n = 1 per cell. <small>Switch the measure.</small></h2><ResultsBars/></div>,
    notes: 'Impulse/trip A/B: Luna 1.5/0.4, Terra 2.2/2.0, base 0/0, tuned 0.3/0.5. Fulfilment: Luna 96/100, Terra 100/100, base 28/32, tuned 36/40. Requests/trip: Terra 51/41, Luna 61/51. Qwen base row is Nov 3 under v2: different date and assist version.' },

  { section: 'Results', title: 'Tables', steps: 1, body: <div><h2>Same data, as a table.</h2>
      <table className="pz-table"><thead><tr><th>A / B</th><th>Impulse / trip</th><th>Completion</th><th>Fulfilment</th><th>Requests / trip</th><th>$ / checkout (reported)</th><th>Invalid</th><th>Adjusted</th></tr></thead><tbody>
        <tr><th>GPT-6 Luna</th><td>1.5 / 0.4</td><td>100 / 100%</td><td>96.2 / 100%</td><td>60.7 / 51.3</td><td>0.060 / 0.051</td><td>12 / 9</td><td>8.4 / 4.7%</td></tr>
        <tr><th>GPT-6.1 Terra</th><td>2.2 / 2.0</td><td>100 / 100%</td><td>100 / 100%</td><td>51.0 / 41.0</td><td>0.518 / 0.395</td><td>0 / 0</td><td>6.1 / 5.4%</td></tr>
        <tr><th>Qwen2.5 7B base*</th><td>0 / 0</td><td>60 / 90%</td><td>28.3 / 32.1%</td><td>100.3 / 93.9</td><td>0.094 / 0.060</td><td>0 / 0</td><td>38.7 / 35.6%</td></tr>
        <tr><th>Qwen2.5 7B tuned</th><td>0.3 / 0.5</td><td>90 / 100%</td><td>35.8 / 39.6%</td><td>98.8 / 93.0</td><td>no API fee</td><td>35 / 66</td><td>13.1 / 14.3%</td></tr>
      </tbody></table>
      <p className="pz-caption">* Nov 3, guided_nav_v2, OpenRouter/Phala (endpoint since withdrawn). Source: evidence-dashboard.json, view openrouter_v3.</p>
      <B at={1}><div className="pz-two"><p><b>Layout:</b> B needs fewer requests for both frontier models (Terra 51 → 41, Luna 61 → 51) and both take fewer impulse items on B (Luna 1.5 → 0.4). Consistent with essentials near the entrance, but n = 1.</p><p><b>Model:</b> Terra ≈ 8–9× the cost of Luna per checkout, +0.7–1.6 impulse items/trip, and perfect fulfilment. A cost–behaviour trade-off, not a ranking.</p></div></B>
    </div>,
    notes: 'Be precise about what one run per cell means: descriptive, no interval, no significance claim.' },

  { section: 'Results', title: 'Earlier study', steps: 1, body: <div className="pz-two">
      <div><p className="pz-eyebrow">Oct 29 · direct OpenAI · Terra · guided_nav_v2 · 2 paired reps × 10 profiles</p><h2>Layout B: 19.5% fewer requests per completed trip.</h2>
        <code className="pz-formula">100 × (1 − 785 / 975) = 19.487%</code>
        <code className="pz-formula">cost: $9.380412 / 20 vs $7.688224 / 20 → 18.040% lower</code>
        <code className="pz-formula">moves/shopper: 42.00 vs 32.95 → 21.548% fewer</code>
        <p>20/20 checkouts per layout; fulfilment 99.06% vs 100%. Equal denominators make request and per-trip reductions identical.</p></div>
      <B at={1}><div className="pz-card"><p className="pz-eyebrow">Why moves ≠ requests</p><p>Requests include grabs, checkout and invalid replies; moves count only successful steps. Different numerators, so 21.5% vs 19.5%.</p><p className="pz-eyebrow">Pseudoreplication</p><p>20 trips per layout are 10 profiles × 2 repetitions, not 20 independent people. Pair within profile and repetition.</p><p className="pz-eyebrow">Collection ledger</p><p>Planned 200 trips / 20 runs; attempted 80 / 8; completed 70. One provider-credit interruption retained.</p></div></B>
    </div>,
    notes: 'This is the resume bullet. It is a different collection (date, transport, assist version) from Nov 17 and is never pooled with it.' },

  // ── 4 · Fine-tuning ──────────────────────────────────────────────────────
  { section: 'Fine-tuning', title: 'Teacher', steps: 1, body: <div className="pz-two">
      <div><h2>Labels: a deterministic rule teacher, run through the real core.</h2>
        <ul><li>Decision order mirrors guided_nav_v3 checkout timing, so the assist never needs to adjust a teacher action (every row is applied unchanged).</li>
          <li><b>Impulse probability only selects a tier</b>; there is no sampling. Within a tier, the teacher always takes the cheapest eligible candidate.</li>
          <li>Eligibility states: not_at_shelf · urgent · low_probability · cap_reached · no_fitting_candidate · list_first · eligible.</li></ul>
        <B at={1}><table className="pz-table"><thead><tr><th>Tier</th><th>p</th><th>Cap</th><th>Max price</th><th>Teacher grab rate</th></tr></thead><tbody>
          <tr><th>impulsive</th><td>≥ 0.40</td><td>2</td><td>$8.00</td><td>23%</td></tr><tr><th>mixed</th><td>≥ 0.20</td><td>1</td><td>$4.00</td><td>12%</td></tr>
          <tr><th>planner</th><td>≥ 0.10</td><td>1 cheap</td><td>$2.50</td><td>4%</td></tr><tr><th>—</th><td>&lt; 0.10</td><td>0</td><td>—</td><td>0%</td></tr></tbody></table>
          <p className="pz-caption">Plus diet/allergy/alcohol fit, treat vs healthy departments (health ≥ 4), and budget slack after reserving remaining list prices.</p></B></div>
      <Code file="data/finetuning/impulse_v3/generate.py · teacher (condensed)">{`
if cart and 'checkout' in allowed and (left <= 15 or not facts['remaining_items']
                                       or left / limit < .30):
    return Decision('checkout', reason='My shopping is done ...')
reachable = [p for p in facts['grabbable_products'] if p['matches_remaining_list']]
if reachable and 'grab' in allowed:
    product = min(reachable, key=lambda p: p['product_id'])
    return Decision('grab', product['product_id'], f"Collect the requested {product['name']}.")
state, candidates = ie.impulse_context(facts, profile)
if state == 'eligible':
    product = candidates[0]                  # cheapest fitting candidate
    reason = templates[int(sha(prompt)[:4], 16) % len(templates)].format(...)
    return Decision('grab', product['product_id'], reason)
...
return Decision(path[0], reason=...)         # BFS path to the next target`}</Code>
    </div>,
    notes: 'Reason text is picked from templates by a hash of the prompt, so the dataset is reproducible byte for byte (generator SHA and file hashes in the manifest). This is behaviour cloning of a rule policy, not distillation from a model.' },

  { section: 'Fine-tuning', title: 'Dataset', steps: 1, body: <div className="pz-two">
      <div><h2>Dataset: 210 trips → 2,329 rows, split by shopper.</h2>
        <table className="pz-table"><thead><tr><th>Label</th><th>Sample rate (train)</th><th>Train</th><th>Val</th><th>Test</th><th>Trained</th></tr></thead><tbody>
          <tr><th>impulse_pass</th><td>0.20</td><td>767</td><td>141</td><td>127</td><td>200</td></tr>
          <tr><th>list_grab</th><td>0.50</td><td>444</td><td>62</td><td>66</td><td>120</td></tr>
          <tr><th>move</th><td>0.12</td><td>291</td><td>23</td><td>25</td><td>250</td></tr>
          <tr><th>checkout</th><td>1.00</td><td>126</td><td>24</td><td>27</td><td>50</td></tr>
          <tr><th>impulse_grab</th><td>1.00</td><td>125</td><td>42</td><td>39</td><td>125 (all)</td></tr>
          <tr><th>total</th><td></td><td>1,753</td><td>292</td><td>284</td><td>745</td></tr></tbody></table>
        <p className="pz-caption">35 non-benchmark base shoppers × 3 style variants × 2 layouts; split unit = base customer; the 15 benchmark shoppers excluded. max_total_tokens 16,128.</p></div>
      <B at={1}><div><p><b>Why split by shopper:</b> consecutive states in a trip are near-duplicates; a row split leaks.</p>
        <p><b>Why down-sample moves:</b> raw trips are mostly moves; at 12% they still dominate unless capped.</p>
        <p><b>The retrain (01b):</b> the first adapter used 60 moves / 400 passes and navigated badly; v3b used 250 moves / 200 passes and 2 epochs. That is the recorded adapter.</p>
        <p><b>Leakage checks:</b> the notebook refuses to train if the CSV hash or the split-overlap check fails.</p></div></B>
    </div>,
    notes: 'Label counts and sample rates are from impulse_v3/manifest.json; trained caps are from notebook 01b. The class imbalance trade-off: impulse grabs are rare (125) and kept in full.' },

  { section: 'Fine-tuning', title: 'LoRA', wide: true, body: <div><h2 className="pz-inline">QLoRA: frozen 4-bit base + trainable low-rank adapters. <small>Drag r.</small></h2>
      <div className="pz-two"><LoraLab/>
        <div><code className="pz-formula">h = W₀x + (α/r)·B A x,  B ∈ ℝ^(d×r), A ∈ ℝ^(r×k), B₀ = 0</code>
          <code className="pz-formula">params/layer = r · Σ(d + k) = 16 · 90,112 = 1,441,792</code>
          <code className="pz-formula">× 28 layers = 40,370,176 ≈ 0.53% of 7.6B</code>
          <table className="pz-table"><thead><tr><th>Projection</th><th>d × k</th><th>r(d + k)</th></tr></thead><tbody>
            <tr><th>q_proj, o_proj</th><td>3,584 × 3,584</td><td>114,688 each</td></tr>
            <tr><th>k_proj, v_proj</th><td>3,584 × 512 (GQA)</td><td>65,536 each</td></tr>
            <tr><th>gate, up, down</th><td>3,584 ↔ 18,944</td><td>360,448 each</td></tr></tbody></table>
          <p>392 tensors = 28 × 7 × 2. 40.37M × 4 bytes (fp32) = 161.5 MB = the saved file. NF4 stores the frozen base at 4 bits with per-block scales; compute in bf16.</p></div></div></div>,
    notes: 'B starts at zero so training starts from the base model exactly. alpha/r = 2 scales the update. k/v are small because Qwen2.5 7B uses grouped-query attention with 4 KV heads of 128 dims. Double-check: the adapter file size matches the parameter count, which is a nice sanity check to mention.' },

  { section: 'Fine-tuning', title: 'Training', steps: 1, body: <div className="pz-two">
      <div><h2>Training run (frozen in experiment.json).</h2>
        <dl className="pz-kv">
          <div><dt>Base</dt><dd>Qwen2.5-7B-Instruct<small>unsloth bnb-4bit · revision pinned</small></dd></div>
          <div><dt>Adapter</dt><dd>r 16 · α 32<small>dropout 0 · all 7 projections</small></dd></div>
          <div><dt>Optimiser</dt><dd>AdamW 8-bit<small>lr 1e-4 linear · wd 0.01 · clip 1.0</small></dd></div>
          <div><dt>Batch</dt><dd>1 × 4<small>grad accumulation · 2 epochs</small></dd></div>
          <div><dt>Precision</dt><dd>bf16 compute<small>NF4 frozen base</small></dd></div>
          <div><dt>Context</dt><dd>16,384<small>median 8,521 · max 15,599</small></dd></div>
          <div><dt>Selection</dt><dd>best eval loss<small>eval / save every 50 steps</small></dd></div>
          <div><dt>Run</dt><dd>3,569 s · loss 0.100<small>A100-SXM4-40GB · seed 3407</small></dd></div></dl></div>
      <B at={1}><div><Code file="experiment.json (adapter ZIP, excerpt)">{`
{
  "method": "QLoRA_SFT", "variant": "v3b_more_movement",
  "base_model": "unsloth/Qwen2.5-7B-Instruct-bnb-4bit",
  "base_revision": "bdd40416…", "rows_trained": 745,
  "assistant_output_only_loss": true, "load_in_4bit": true,
  "chat_template_sha256": "cd8e9439…", "adapter_sha256": "066abcfe…",
  "lora_tensors": 392,
  "packages": {"unsloth": "2026.11.6", "transformers": "5.17.0",
               "peft": "0.21.3", "bitsandbytes": "0.50.2",
               "torch": "2.14.1+cu130"}
}`}</Code>
        <p><b>Answer-only loss:</b> labels are −100 on prompt tokens; only the ~35-token action JSON is scored. No packing, no truncation.</p></div></B>
    </div>,
    notes: 'Throughput was 0.417 samples/s; the long rows dominate. Hindsight: plain LoRA on a bf16 base would make the adapter portable to my Mac deployments (MPS Quanto int4, MLX), which are recorded as separate model identities because the base weights differ.' },

  { section: 'Fine-tuning', title: 'Offline', steps: 1, body: <div className="pz-two">
      <div><h2>Offline eval: same 88 validation rows, before vs after.</h2>
        <BeforeAfter rows={[['Step agreement', 0.227, 0.864], ['Exact action agreement', 0.227, 0.830], ['Observation-valid', 0.818, 0.989], ['Strict schema', 0.989, 1], ['Impulse decisions (66)', 0.288, 0.818], ['List grabs (10)', 0, 0.7], ['Checkout (8)', 0, 1]]}/></div>
      <B at={1}><div><p><b>Definitions:</b> strict schema = valid JSON with exactly the three keys; observation-valid = passes check_action; step agreement = same step as teacher; exact = same step and product.</p>
        <p><b>Impulse:</b> model grab rate 0% → 57.6% vs teacher 63.6% on the 66 impulse moments.</p>
        <p className="pz-note">Caveat: the subset is 75% impulse moments and has only 4 move rows, so it barely measures navigation, the thing that fails online.</p></div></B>
    </div>,
    notes: 'Teacher agreement also penalises alternative valid routes. Per-step metrics are necessary but not sufficient; the task metric is the full trip.' },

  { section: 'Fine-tuning', title: 'Online', steps: 1, body: <div className="pz-two">
      <div><h2>Online eval: full trips on unseen benchmark shoppers.</h2>
        <BeforeAfter rows={[['Fulfilment A', 0.283, 0.358], ['Fulfilment B', 0.321, 0.396], ['Completion A', 0.6, 0.9], ['Completion B', 0.9, 1]]}/>
        <p className="pz-caption">Base = Nov 3 hosted run (guided_nav_v2); tuned = Colab A100 4-bit, guided_nav_v3. Not a perfectly matched pair.</p></div>
      <B at={1}><div><h3>Why offline ≠ online</h3>
        <ul><li><b>Covariate shift:</b> offline inputs come from teacher trajectories; online the model visits its own states. Errors compound (≈ 93–99 actions per trip vs Terra’s 41–51).</li>
          <li><b>Invalid replies</b> (35 / 66) each burn a turn.</li>
          <li><b>Coverage:</b> only 250 move rows; recovery from mistakes is never demonstrated by a perfect teacher.</li></ul>
        <p><b>Fixes:</b> DAgger-style data (roll out the student, label its states with the teacher), recovery demonstrations, constrained decoding to remove invalid JSON, a matched base-vs-tuned rerun.</p></div></B>
    </div>,
    notes: 'This is the most interesting ML lesson in the project: big offline gains, modest online gains. Frame it as distribution shift and compounding error, with concrete fixes.' },

  // ── 5 · Evals ────────────────────────────────────────────────────────────
  { section: 'Evals', title: 'Guardrails', steps: 1, body: <div className="pz-two">
      <div><h2>Guardrails: read-only audit after the run.</h2>
        <Code file="simulation/evaluation/guardrails.py (condensed)">{`
INVALID_RATE_REVIEW = 0.05
INVALID_RATE_FAIL   = 0.20
NO_PROGRESS_REVIEW  = 30

bad  = outcomes['invalid_decision'] + outcomes['grid_rejected']
rate = bad / len(events)
if rate > INVALID_RATE_FAIL:   findings.append(_finding('invalid_reply_rate_high', ...))
elif rate > INVALID_RATE_REVIEW: findings.append(_finding('invalid_reply_rate', ...))

extras = [(pid, q) for pid, q in final_cart if pid not in listed] if finished else []
tier = tier_for(customer['impulse_buy_probability'])
if sum(q for _, q in extras) > TIERS[tier]['cap']:
    findings.append(_finding('impulse_cap', ...))      # review, never fail
...
def verdict(findings):
    return max((f['severity'] for f in findings),
               key=SEVERITY_ORDER.get, default='pass')`}</Code>
        <B at={1}><p className="pz-note">Steer (assist) vs audit (guardrails). In an eval harness, blocking an allergen at runtime would hide the model’s error; in production you would block.</p></B></div>
      <RunCheckBars/>
    </div>,
    notes: 'Fail: no checkout, provider error, allergen in an unplanned buy, >20% invalid. Review: impulse cap/price, diet mismatch (unknown tags count as not fitting), over budget, above acceptable price, list incomplete, loop, stuck 30+. The impulse cap is a teacher rule the prompt may never have stated, so it can only ever be a review.' },

  { section: 'Evals', title: 'Stability and sensitivity', steps: 2, body: <div className="pz-two">
      <div><h2>Isabella: stable, plausible, sensitive in one direction.</h2>
        <table className="pz-table"><thead><tr><th>Off-list units</th><th>Run 1</th><th>Run 2</th><th>Run 3</th></tr></thead><tbody>
          <tr><th>Terra</th><td>12 (A)</td><td>12 (B)</td><td>11 (A rep.)</td></tr><tr><th>Luna</th><td>0 (A)</td><td>0 (B)</td><td>0 (B re-run)</td></tr>
          <tr><th>Terra, p = 0.05</th><td colSpan={3}>0 (A, one-field probe)</td></tr></tbody></table>
        <B at={1}><code className="pz-formula">X ~ Binomial(n = 8 stops, p = 0.45): E[X] = 3.6</code>
          <code className="pz-formula">P(X ≥ 4) = 0.523 (A, 4/8)   P(X ≥ 5) = 0.260 (B, 5/8)</code>
          <p>Per stop, Terra matches her stated rate. The volume comes from several units at one stop (nine grabs just before checkout).</p></B></div>
      <B at={2}><div className="pz-card"><p className="pz-eyebrow">Eval design</p>
        <p><b>Stability:</b> same input → spread ≈ 1 unit across 3 runs (a noise floor).</p>
        <p><b>Sensitivity:</b> change one field, hold the rest; write the expected direction first; add a null-control field. 0.45 → 0.05 moved 12 → 0.</p>
        <p><b>Run count:</b> rule of three: 0 failures in n runs ⇒ rate &lt; 3/n at 95%. Three runs show reproduction, not a rate.</p>
        <p><b>Floor effect:</b> Luna at 0 can only be tested by raising p.</p></div></B>
    </div>,
    notes: 'Neither model is the baseline: there is no real Isabella and 0.45 is a chosen number. The difference between models is the measurement, not a bug.' },

  { section: 'Evals', title: 'Validity', steps: 1, body: <div className="pz-two">
      <div className="pz-card is-no"><p className="pz-eyebrow">Threats to validity</p><ul>
        <li><b>n = 1 per cell</b> in the latest study; no intervals.</li>
        <li><b>Assist confound:</b> results are model + guided_nav_v3; no model_only ablation yet.</li>
        <li><b>Synthetic personas:</b> no human ground truth; impulse p is chosen.</li>
        <li><b>Prompt vs rule:</b> the impulse cap is graded but may not be stated in the prompt.</li>
        <li><b>Mismatched baseline:</b> Qwen base is Nov 3, guided_nav_v2, a different host.</li>
        <li><b>Non-determinism:</b> no request seeds; serving can vary.</li>
        <li><b>Rule teacher:</b> the student can at best learn my rules.</li></ul></div>
      <B at={1}><div className="pz-card is-yes"><p className="pz-eyebrow">What is solid</p><ul>
        <li>Single authority, canonical records, verified replay and recomputed metrics.</li>
        <li>Frozen, fingerprinted inputs and versioned policies per run.</li>
        <li>All attempts retained, including the aborted Luna B run (OpenAI content filter, 548 actions) and the provider-credit interruption.</li>
        <li>Separate ledgers for simulated sales and API cost.</li></ul></div></B>
    </div>,
    notes: 'Saying this before the interviewer does is the strongest move in the talk.' },

  { section: 'Next', title: 'Next', steps: 1, body: <div className="pz-two">
      <div><h2>Next experiments, each with one variable.</h2><ol className="pz-steps">
        <li><b>Ablation:</b> model_only vs guided_nav_v3 on the same cohort.</li>
        <li><b>Sensitivity grid:</b> one profile field at a time × k repeats per model, with null controls.</li>
        <li><b>Repetitions:</b> ≥ 5 per cell; paired by profile; bootstrap intervals.</li>
        <li><b>Distillation arm:</b> Terra on non-benchmark shoppers, applied-unchanged proposals only; same student and recipe.</li></ol></div>
      <B at={1}><ol className="pz-steps" start={5}>
        <li><b>Student:</b> DAgger rollouts, recovery data, constrained decoding, plain LoRA on bf16 for portable serving, rank sweep 8/16/32.</li>
        <li><b>Shelf visibility v2:</b> product-adjacent visibility as a new frozen rule; old runs still verify under v1.</li>
        <li><b>Scale:</b> shared inventory needs reservations and conflict resolution; a queue-based worker pool keeps the single-writer rule.</li></ol></B>
    </div>,
    notes: 'Paid runs need explicit authorisation; each item names its controlled variable.' },

  { section: 'Next', title: 'end', body: <div className="pz-title"><p className="pz-eyebrow">Summary</p><h1>Model proposes.<br/>Python decides, records, verifies.</h1><p className="pz-lede">Questions. Backup: replay demo (slide 13), results table (15), LoRA maths (19), guardrails (23).</p></div>,
    notes: 'Keep the replay and LoRA slides ready for questions.' },
];

export default function TechDeck() {
  return <DeckShell slides={slides} draft="Technical" dense/>;
}
