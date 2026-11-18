"""Generate dataset impulse_teacher_v2: core-validated trajectories with style-conditioned impulse buys.

Run from the repository root:
    .venv/bin/python data/finetuning/impulse_v2/generate.py [--output DIR]

* The simulation code is the frozen commit from notebooks/frozen_source.py (benchmarked
  `informed` prompt, guided_nav_v2), never the working tree.
* The teacher only PROPOSES actions; SimulationSession applies them and records canonical
  events. Every kept row is a proposal that core applied unchanged (no assist adjustment).
* Impulse labels come from evaluation/impulse_eval.impulse_context, which reads only facts
  shown in the prompt (style, diet, allergy, alcohol, health, budget, urgency, products).
* The 15 frozen benchmark shoppers (the Layout A/B evaluation cohort) are excluded entirely.
"""
import argparse
import hashlib
import importlib
import json
import random
import sys
import tempfile
from collections import Counter, deque
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'notebooks'))
import frozen_source  # noqa: E402

DATASET = 'simply_impulse_teacher_v2'
SEED = 20261117
TURN_BUDGET = 120
STYLE_PROFILE = {'planner': (True, 0.12), 'mixed': (False, 0.24), 'impulsive': (False, 0.53)}
SPLIT_BASES = {'validation': 4, 'test': 4}            # base customers per held-out split
MAX_TOTAL_TOKENS = 16384 - 256                         # full chat example + generation allowance
TRAIN_KEEP = {'impulse_grab': 1.0, 'impulse_pass': 0.2, 'list_grab': 0.5, 'checkout': 1.0, 'move': 0.12}
EVAL_KEEP = {'impulse_grab': 1.0, 'impulse_pass': 0.12, 'list_grab': 0.25, 'checkout': 0.5, 'move': 0.03}
QWEN_TEMPLATE = ('<|im_start|>system\nYou are Qwen, created by Alibaba Cloud. You are a helpful assistant.<|im_end|>\n'
                 '<|im_start|>user\n{user}<|im_end|>\n<|im_start|>assistant\n{assistant}<|im_end|>\n')

IMPULSE_REASONS = {
    'impulsive': ['Unplanned pick: {name} for ${price} fits my budget; then back to {next}.',
                  'Treating myself to {name} (${price}) since it fits the budget; next {next}.',
                  '{name} caught my eye at ${price} and still fits my budget; continuing to {next}.'],
    'mixed': ['One small extra: {name} at ${price} fits my remaining budget; then {next}.',
              'Adding {name} (${price}) as a single extra within budget; heading to {next} next.'],
    'planner': ['One cheap extra, {name} at ${price}, still leaves plenty of budget; back to {next}.',
                'Allowing a single low-cost extra: {name} (${price}); then {next} on my list.'],
}
HEALTHY_SUFFIX = ' It is a healthy choice.'
MOVE_REASONS = ['Follow an open corridor toward {name} in {department}.',
                'Head for {department} to collect {name}.',
                'Keep moving toward {name} in {department} via the open aisle.']


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def keep(prompt, fraction):
    return int(sha('keep:' + prompt)[:8], 16) / 0xFFFFFFFF < fraction


def load_frozen(directory):
    fingerprint = frozen_source.materialize(directory)
    sys.path.insert(0, str(Path(directory) / 'simulation'))
    modules = {name: importlib.import_module(name) for name in (
        'agents.base', 'agents.customer', 'agents.schema', 'agents.steps', 'core.accounting', 'core.config',
        'core.customers', 'core.grid', 'core.run_log', 'core.session', 'core.shopping', 'core.navigation',
        'evaluation.benchmark', 'evaluation.impulse_eval')}
    assert modules['core.config'].DATA_DIR.resolve() == (Path(directory) / 'data').resolve(), 'not running the frozen copy'
    return fingerprint, modules


class ImpulseTeacherV2:
    """Deterministic, visible-fact teacher. Proposes only; core applies."""
    model = provider_id = 'scripted_test'
    supports_action_plans = False
    generation_settings = {'decision_source': 'offline_impulse_teacher_v2'}

    def __init__(self, m):
        self.m = m

    def path_to(self, facts, goals):
        start, goals, rows = tuple(facts['position']), {tuple(c) for c in goals}, facts['floor_map']['rows']
        frontier, visited = deque([(start, ())]), {start}
        while frontier:
            cell, steps = frontier.popleft()
            if cell in goals:
                return steps
            for step, (dx, dy) in self.m['agents.steps'].MOVES.items():
                x, y = cell[0] + dx, cell[1] + dy
                if (x, y) not in visited and 0 <= y < len(rows) and 0 <= x < len(rows[y]) and rows[y][x] != '#':
                    visited.add((x, y))
                    frontier.append(((x, y), (*steps, step)))
        return None

    def next_target(self, facts):
        """Nearest shelf of a needed department, preferring shelves the prompt marks as holding a target."""
        marked = {tuple(shelf['position']) for shelf in facts['nearby_shelves'] if shelf['has_remaining_target']}
        options = []
        for item in facts['remaining_items']:
            for department in facts['department_locations']:
                if department['department'] != item['department']:
                    continue
                path = self.path_to(facts, department['walkable_access_cells'])
                if path:  # empty path: already beside this shelf and the item is not on it
                    seen = 0 if any(tuple(cell) in marked for cell in department['shelf_cells']) else 1
                    options.append((seen, len(path), item['product_id'], path, item))
        best = min(options, key=lambda o: o[:3]) if options else None
        return (best[1], best[2], best[3], best[4]) if best else None

    def decide(self, facts, prompt):
        Decision, ie = self.m['agents.base'].Decision, self.m['evaluation.impulse_eval']
        allowed, cart = facts['allowed_steps'], facts['cart']
        limit, left = facts['action_limit'], facts['turns_remaining']
        # Mirror guided_nav_v2 checkout timing so the assist never needs to adjust a teacher action.
        if cart and 'checkout' in allowed and (left <= 15 or not facts['remaining_items'] or left / limit < .30):
            return Decision('checkout', reason='My shopping is done for this trip; pay once and finish.')
        reachable = [p for p in facts['grabbable_products'] if p['matches_remaining_list']]
        if reachable and 'grab' in allowed:
            product = min(reachable, key=lambda p: p['product_id'])
            reason = f"Collect the requested {product['name']}."
            if product['unit_price_cents'] > facts['remaining_budget_cents']:
                reason = f"Prioritize the requested {product['name']} despite exceeding my spending target."
            return Decision('grab', product['product_id'], reason)
        profile = ie.parse_profile(prompt)
        state, candidates = ie.impulse_context(facts, profile)
        target = self.next_target(facts)
        if state == 'eligible':
            product = candidates[0]
            templates = IMPULSE_REASONS[profile['style']]
            reason = templates[int(sha(prompt)[:4], 16) % len(templates)].format(
                name=product['name'], price=f"{product['unit_price_cents'] / 100:.2f}",
                next=target[3]['name'] if target else 'checkout')
            if profile['health'] >= 4:
                reason += HEALTHY_SUFFIX
            return Decision('grab', product['product_id'], reason)
        if cart and (not facts['remaining_items'] or left / limit < .30 or target is None):
            path = self.path_to(facts, facts['checkout_cells'])
            if not path and 'checkout' in allowed:
                return Decision('checkout', reason='At checkout; pay once and finish.')
            if not path:
                raise ValueError('Teacher cannot reach checkout')
            return Decision(path[0], reason='Shopping is done; follow the open corridor to checkout.')
        if target is None:
            raise ValueError('Teacher has no route to a remaining target')
        _, _, path, item = target
        template = MOVE_REASONS[int(sha(prompt)[:4], 16) % len(MOVE_REASONS)]
        return Decision(path[0], reason=template.format(name=item['name'], department=item['department']))

    def __call__(self, prompt, allowed_steps):
        schema, base = self.m['agents.schema'], self.m['agents.base']
        facts = self.m['evaluation.impulse_eval'].observation(prompt)
        decision = self.decide(facts, prompt)
        raw = json.dumps(decision.to_dict(), ensure_ascii=False)
        if schema.parse_decision(raw, allowed_steps) != decision:
            raise ValueError('Teacher produced an invalid action')
        return base.ProposalResult(raw, decision, {'request_submitted': False, 'estimated_cost_micros': 0,
                                                   'decision_source': 'offline_impulse_teacher_v2'})


def feasible_list(m, customer, grids, start):
    """Same construction rules as the frozen benchmark (priority order, <=80% budget, route <=96)."""
    bm, cents = m['evaluation.benchmark'], m['core.accounting'].cents
    catalogue = grids[0].products
    items, remaining = [], cents(customer.budget_per_trip_usd) * 80 // 100
    for _, item in sorted(enumerate(customer.shopping_list), key=lambda x: (bm.PRIORITIES.get(x[1].priority, 99), x[0])):
        product = catalogue.get(item.product_id)
        if not product or cents(product['price']) > cents(item.max_acceptable_unit_price):
            continue
        price = cents(product['price'])
        quantity = min(item.quantity, remaining // max(price, 1))
        if quantity < 1:
            continue
        candidate = replace(item, quantity=quantity, expected_line_total=price * quantity / 100)
        if all((t := bm.reference_turns(g, items + [candidate], start)) is not None and t <= 96 for g in grids):
            items.append(candidate)
            remaining -= quantity * price
    return tuple(items)


def missions(m):
    layouts = m['core.config'].ACTIVE_LAYOUT_IDS
    grids = [m['core.grid'].build_store(name) for name in layouts]
    starts = m['evaluation.benchmark'].common_start_cells(grids)
    benchmark = m['evaluation.benchmark'].load_benchmark(Path(m['core.config'].SIMULATION_DIR) / 'benchmarks/two_layouts_15_v2.json')
    excluded = {c['customer_id'] for c in benchmark['customers']}
    bases = []
    for index, customer in enumerate(c for c in m['core.customers'].load_customers() if c.customer_id not in excluded):
        start = starts[index % len(starts)]
        items = feasible_list(m, customer, grids, start)
        if items:
            bases.append((replace(customer, shopping_list=items), start))
    # Stratified split by ORIGINAL style; all three style variants of a base stay in one split.
    rng = random.Random(SEED)
    by_style = {}
    for base in bases:
        by_style.setdefault(base[0].shopping_style, []).append(base)
    split_of = {}
    for style in sorted(by_style):
        group = sorted(by_style[style], key=lambda b: b[0].customer_id)
        rng.shuffle(group)
        for i, (customer, _) in enumerate(group):
            split_of[customer.customer_id] = 'validation' if i % 6 == 0 else 'test' if i % 6 == 1 else 'train'
    out = []
    for customer, start in bases:
        for style, (uses_list, probability) in STYLE_PROFILE.items():
            original = style == customer.shopping_style
            variant = customer if original else replace(
                customer, customer_id=f'{customer.customer_id}-{style[0].upper()}', shopping_style=style,
                uses_shopping_list=uses_list, impulse_buy_probability=probability)
            out.append({'customer': variant, 'base_id': customer.customer_id, 'style': style,
                        'original_style': original, 'start': start, 'split': split_of[customer.customer_id]})
    return out, sorted(excluded)


def generate(output):
    output = Path(output)
    if output.exists() and any(p.name.endswith('.jsonl') for p in output.iterdir()):
        raise FileExistsError('Output already has generated files; choose a new --output')
    output.mkdir(parents=True, exist_ok=True)
    from tokenizers import Tokenizer
    tokenizer_path = next((ROOT / 'simulation/models/adapters').glob('*/tokenizer.json'))
    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    with tempfile.TemporaryDirectory() as frozen:
        source_fingerprint, m = load_frozen(frozen)
        ie, Session = m['evaluation.impulse_eval'], m['core.session'].SimulationSession
        plan, excluded = missions(m)
        rows = {s: [] for s in ('train', 'validation', 'test')}
        provenance, trajectories = {s: [] for s in rows}, []
        dropped = Counter()
        for mission in plan:
            for layout in m['core.config'].ACTIVE_LAYOUT_IDS:
                grid = m['core.grid'].build_store(layout)
                shoppers = m['evaluation.benchmark'].instantiate_benchmark(
                    {'customers': [asdict(mission['customer'])], 'starting_cells': [list(mission['start'])]},
                    1, grid, TURN_BUDGET, m['core.shopping'].SIMPLE_SHOPPING)
                path = Path(frozen) / 'runs' / f"{mission['customer'].customer_id}_{layout}.jsonl"
                path.parent.mkdir(exist_ok=True)
                session = Session(layout_name=layout, shopper_count=1, max_rounds=TURN_BUDGET, turn_budget=TURN_BUDGET,
                    concurrency=1, grid=grid, shoppers=shoppers, decide=ImpulseTeacherV2(m), output_path=path,
                    navigation_policy=m['core.navigation'].GUIDED_CURRENT, shopping_rules=m['core.shopping'].SIMPLE_SHOPPING,
                    allow_action_plans=False, experiment={'kind': 'offline_finetuning_dataset', 'dataset': DATASET,
                        'synthetic': True, 'mission': mission['customer'].customer_id, 'split': mission['split']})
                session.run()
                run = m['core.run_log'].read_run(path)
                shopper = run['summary']['shoppers'][0]
                trajectories.append({'mission': mission['customer'].customer_id, 'base_id': mission['base_id'],
                    'style': mission['style'], 'original_style': mission['original_style'], 'layout': layout,
                    'split': mission['split'], 'finished': shopper['finished'], 'turns_used': shopper['turns_used'],
                    'list_completion': shopper['list_completion'], 'off_list_units': shopper['off_list_units'],
                    'events': len(run['events'])})
                for event in run['events']:
                    raw, prompt = event['raw_response'], event['prompt']
                    if not isinstance(raw, str) or not isinstance(prompt, str):
                        dropped[f"no_proposal_{event['outcome']}"] += 1
                        continue
                    proposal = json.loads(raw)
                    applied = event['action'] or {}
                    if event['outcome'] != 'applied' or event['failure']:
                        dropped['core_rejected'] += 1
                        continue
                    if (applied.get('step'), applied.get('product_id')) != (proposal['step'], proposal['product_id']):
                        dropped['assist_adjusted'] += 1
                        continue
                    facts, profile = ie.observation(prompt), ie.parse_profile(prompt)
                    kind = ie.moment_kind(facts, profile, proposal)
                    label = ('impulse_grab' if ie.is_off_list_grab(proposal, facts) else 'impulse_pass') if kind == 'impulse_decision' else kind
                    fraction = (TRAIN_KEEP if mission['split'] == 'train' else EVAL_KEEP)[label]
                    if not keep(prompt, fraction):
                        dropped[f'sampled_out_{label}'] += 1
                        continue
                    tokens = len(tokenizer.encode(QWEN_TEMPLATE.format(user=prompt, assistant=raw), add_special_tokens=False).ids)
                    if tokens > MAX_TOTAL_TOKENS:
                        dropped['over_context'] += 1
                        continue
                    split = mission['split']
                    rows[split].append({'messages': [{'role': 'user', 'content': prompt}, {'role': 'assistant', 'content': raw}]})
                    provenance[split].append({'split': split, 'line': len(rows[split]), 'mission': mission['customer'].customer_id,
                        'base_id': mission['base_id'], 'style': mission['style'], 'original_style': mission['original_style'],
                        'layout': layout, 'sequence': event['sequence'], 'label': label,
                        'impulse_state': ie.impulse_context(facts, profile)[0], 'tokens': tokens,
                        'synthetic': True, 'core_validated': True, 'label_source': 'offline_impulse_teacher_v2',
                        'navigation_policy': m['core.navigation'].GUIDED_CURRENT,
                        'prompt_sha256': sha(prompt), 'target_sha256': sha(raw)})
        hashes = {s: {p['prompt_sha256'] for p in provenance[s]} for s in rows}
        bases = {s: {p['base_id'] for p in provenance[s]} for s in rows}
        for a, b in (('train', 'validation'), ('train', 'test'), ('validation', 'test')):
            if hashes[a] & hashes[b] or bases[a] & bases[b]:
                raise ValueError('Leakage between splits')
        for split in rows:
            # Shuffle training order deterministically; keep eval files in trajectory order.
            order = list(range(len(rows[split])))
            if split == 'train':
                random.Random(SEED).shuffle(order)
            rows[split] = [rows[split][i] for i in order]
            provenance[split] = [{**provenance[split][i], 'line': n + 1} for n, i in enumerate(order)]
            (output / f'{split}.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows[split]))
        (output / 'provenance.jsonl').write_text(''.join(json.dumps(p) + '\n' for s in rows for p in provenance[s]))
        unfinished = [t for t in trajectories if not t['finished']]
        manifest = {
            'dataset': DATASET, 'synthetic': True, 'model_requests': 0, 'label_source': 'offline_impulse_teacher_v2',
            'purpose': 'Teach style-conditioned impulse buying with the frozen informed prompt; not human behavior evidence.',
            'frozen_commit': frozen_source.FROZEN_COMMIT, 'frozen_source_sha256': source_fingerprint,
            'prompt_revision': 'observe-plan-v5-unique-checkout', 'prompt_variant': 'informed',
            'navigation_policy': m['core.navigation'].GUIDED_CURRENT, 'shopping_rules': m['core.shopping'].SIMPLE_SHOPPING,
            'turn_budget': TURN_BUDGET, 'seed': SEED,
            'impulse_rules': {'tiers': ie.TIERS, 'treat_departments': ie.TREAT_DEPARTMENTS,
                              'healthy_departments': ie.HEALTHY_DEPARTMENTS, 'source': 'evaluation/impulse_eval.py'},
            'excluded_benchmark_shoppers': excluded,
            'split_unit': 'base customer (all three style variants and both layouts stay together)',
            'sampling': {'train': TRAIN_KEEP, 'eval': EVAL_KEEP, 'max_total_tokens': MAX_TOTAL_TOKENS},
            'examples': {s: len(r) for s, r in rows.items()},
            'labels': {s: dict(Counter(p['label'] for p in provenance[s])) for s in rows},
            'labels_by_style': {s: {st: dict(Counter(p['label'] for p in provenance[s] if p['style'] == st))
                                    for st in STYLE_PROFILE} for s in rows},
            'base_customers': {s: sorted(b) for s, b in bases.items()},
            'token_lengths': {s: {'max': max(p['tokens'] for p in provenance[s]), 'median': sorted(p['tokens'] for p in provenance[s])[len(provenance[s]) // 2]} for s in rows},
            'dropped_rows': dict(dropped),
            'trajectories': {'count': len(trajectories), 'unfinished': len(unfinished),
                             'finished_off_list_units_by_style': {st: sum(t['off_list_units'] for t in trajectories if t['style'] == st and t['finished']) for st in STYLE_PROFILE},
                             'trips_by_style': dict(Counter(t['style'] for t in trajectories))},
            'trajectory_summaries': trajectories,
            'limitations': [
                'Labels come from a deterministic rule teacher, not people. The model learns these rules, not human impulse psychology.',
                'Impulse depends on visible style, diet/allergy/alcohol tags, health, department, price, budget slack, urgency and extras already taken.',
                'Two of three style variants per base customer are counterfactual (same list and budget, different visible style).',
                'Both layouts and one catalogue appear in every split; no unseen-layout or unseen-SKU claim.',
                'Corridor moves are down-sampled in training; navigation in deployment is still assisted by guided_nav_v2.',
                'The 15 frozen benchmark shoppers are excluded, so the Layout A/B cohort is unseen during training.'],
            'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'files': {name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                      for name in ('train.jsonl', 'validation.jsonl', 'test.jsonl', 'provenance.jsonl')},
        }
        (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    result = generate(args.output)
    print(json.dumps({k: result[k] for k in ('examples', 'labels', 'token_lengths', 'dropped_rows')}, indent=2))
    print(json.dumps({k: v for k, v in result['trajectories'].items()}, indent=2))
