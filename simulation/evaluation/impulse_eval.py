"""Impulse-buy rules, offline decision scoring and trip reports for the Qwen QLoRA work.

* `impulse_context` is the single definition of when an off-list ("impulse") grab is
  appropriate. It reads ONLY facts the frozen `informed` prompt shows the model
  (persona text + `Current state`), so the v2 teacher's labels are learnable.
* `score_offline` scores model responses against teacher rows, per decision.
* `trip_report` summarises a canonical run file. Impulse totals are Python core's own
  `off_list_units`; this module never applies or invents actions.
"""
import json
import re
from collections import Counter, defaultdict

TREAT_DEPARTMENTS = ('Snacks', 'Bakery', 'Beverages', 'Frozen', 'Prepared Meals')
HEALTHY_DEPARTMENTS = ('Produce', 'Dairy & Eggs')
URGENT = ('high', 'critical')
# Visible style -> how far an unplanned item may go. Rates in the source CSV:
# planner ~0.12, mixed ~0.24, impulsive ~0.53 mean impulse_buy_probability.
TIERS = {
    'impulsive': {'cap': 2, 'max_price_cents': 800},
    'mixed': {'cap': 1, 'max_price_cents': 400},
    'planner': {'cap': 1, 'max_price_cents': 250},
}
STATES = ('not_at_shelf', 'list_item_reachable', 'list_complete', 'urgent', 'cap_reached',
          'no_fitting_candidate', 'eligible')


def observation(prompt):
    return json.loads(prompt.split('Current state: ', 1)[1].split('\nChoose one step:', 1)[0])


def parse_profile(prompt):
    """Persona facts printed by Customer.build_persona_summary / build_behavioral_directives."""
    head = prompt.split('Current state: ', 1)[0]

    def find(pattern):
        match = re.search(pattern, head)
        if not match:
            raise ValueError(f'Persona field missing: {pattern}')
        return match.group(1)

    return {
        'shopper_id': find(r'You are shopper .*? \(([^)]+)\)\.'),
        'style': find(r'Style (\w+),'),
        'diet': find(r'diet ([^,]+),'),
        'allergy': find(r'allergy ([^,]+),'),
        'drinks_alcohol': 'does not drink alcohol' not in head,
        'health': int(find(r'health (\d)/5')),
        'price_sensitivity': int(find(r'price sensitivity (\d)/5')),
    }


def _split(value):
    return {part for part in (value or '').split(';') if part}


def fits_profile(product, profile):
    """Diet / allergy / alcohol compatibility from the product's visible tags. Unknown is not a fit."""
    tags, allergens = _split(product.get('dietary_tags')), _split(product.get('allergens'))
    if 'alcohol_21plus' in tags and (not profile['drinks_alcohol'] or profile['diet'] == 'halal'):
        return False
    if profile['allergy'] != 'none' and (not allergens or 'unspecified' in allergens or profile['allergy'] in allergens):
        return False
    diet = profile['diet']
    if diet == 'vegan':
        return 'vegan' in tags
    if diet == 'vegetarian':
        return bool(tags & {'vegan', 'vegetarian'})
    if diet == 'pescatarian':
        return bool(tags & {'vegan', 'vegetarian', 'pescatarian'})
    if diet == 'halal':
        return 'contains_pork' not in tags and bool(tags - {'unspecified'})
    return True


def product_departments(facts):
    departments = {}
    for shelf in sorted(facts['nearby_shelves'], key=lambda s: s['distance']):
        for product in shelf['products']:
            departments.setdefault(product['product_id'], shelf['department'])
    return departments


def extras_in_cart(facts):
    listed = {item['product_id'] for item in facts['shopping_list']}
    return sum(item['quantity'] for item in facts['cart'] if item['product_id'] not in listed)


def budget_slack_cents(facts):
    """Remaining budget after reserving the visible price ceilings of what is still needed."""
    reserved = sum(item['max_unit_price_cents'] * item['remaining'] for item in facts['remaining_items'])
    return facts['remaining_budget_cents'] - reserved


def impulse_context(facts, profile):
    """(state, candidates). The teacher grabs candidates[0] exactly when state == 'eligible'."""
    grabbable = facts['grabbable_products']
    if 'grab' not in facts['allowed_steps'] or not grabbable:
        return 'not_at_shelf', []
    if any(p['matches_remaining_list'] for p in grabbable):
        return 'list_item_reachable', []          # prompt + guided_nav_v2: list items first
    if not facts['remaining_items']:
        return 'list_complete', []                # prompt: skip extras when the list is done
    if facts['checkout_urgency'] in URGENT:
        return 'urgent', []                       # prompt: skip extras when urgency is high/critical
    tier = TIERS.get(profile['style'])
    if tier is None or extras_in_cart(facts) >= tier['cap']:
        return 'cap_reached', []
    departments = product_departments(facts)
    appeal = HEALTHY_DEPARTMENTS if profile['health'] >= 4 else TREAT_DEPARTMENTS
    slack, budget = budget_slack_cents(facts), facts['budget_cents']
    candidates = []
    for product in grabbable:
        price = product['unit_price_cents']
        if departments.get(product['product_id']) not in appeal or not fits_profile(product, profile):
            continue
        if price > tier['max_price_cents']:
            continue
        if profile['style'] == 'impulsive' and price > slack + budget // 4:
            continue
        if profile['style'] == 'mixed' and slack - price < budget // 5:
            continue
        if profile['style'] == 'planner' and (slack - price < budget // 2 or departments.get(product['product_id']) != appeal[0]):
            continue
        candidates.append(product)
    candidates.sort(key=lambda p: (p['unit_price_cents'], p['product_id']))
    return ('eligible' if candidates else 'no_fitting_candidate'), candidates


def check_action(text, facts):
    """(action dict or None, observation-valid). Same contract as the earlier notebooks."""
    try:
        action = json.loads(text)
    except (TypeError, ValueError):
        return None, False
    if not isinstance(action, dict) or set(action) != {'step', 'product_id', 'reason'}:
        return None, False
    if not all(isinstance(value, str) for value in action.values()):
        return None, False
    step, product_id = action['step'], action['product_id']
    owned = {item['product_id'] for item in facts['cart']}
    valid = step in facts['allowed_steps']
    if step.startswith('move_'):
        valid = valid and not product_id and step in facts['legal_move_destinations']
    elif step == 'grab':
        valid = valid and product_id in {p['product_id'] for p in facts['grabbable_products']} and product_id not in owned
    elif step == 'remove':
        valid = valid and product_id in owned
    elif step == 'checkout':
        valid = valid and not product_id and bool(owned) and facts['position'] in facts['checkout_cells']
    else:
        valid = False
    return action, bool(valid)


def is_off_list_grab(action, facts):
    if not action or action.get('step') != 'grab':
        return False
    product = next((p for p in facts['grabbable_products'] if p['product_id'] == action.get('product_id')), None)
    return product is not None and not product['matches_remaining_list']


def moment_kind(facts, profile, target):
    if target['step'] == 'checkout':
        return 'checkout'
    state, _ = impulse_context(facts, profile)
    if state == 'list_item_reachable':
        return 'list_grab'
    if state != 'not_at_shelf':
        return 'impulse_decision'
    return 'move'


def _rate(numerator, denominator):
    return numerator / denominator if denominator else None


def score_offline(rows, responses):
    """rows: dataset rows ({'messages': [user, assistant]}); responses: raw model texts."""
    if len(rows) != len(responses):
        raise ValueError('One response per row is required')
    records = []
    for row, text in zip(rows, responses):
        prompt, target_raw = row['messages'][0]['content'], row['messages'][1]['content']
        facts, profile, target = observation(prompt), parse_profile(prompt), json.loads(target_raw)
        action, valid = check_action(text, facts)
        state, candidates = impulse_context(facts, profile)
        model_impulse = is_off_list_grab(action, facts)
        violation = None
        if model_impulse:
            if state != 'eligible':
                violation = state
            elif action['product_id'] not in {p['product_id'] for p in candidates}:
                violation = 'unfit_or_over_budget_product'
        records.append({
            'kind': moment_kind(facts, profile, target), 'style': profile['style'], 'state': state,
            'strict_schema': action is not None, 'observation_valid': valid,
            'exact_agreement': bool(action) and (action['step'], action['product_id']) == (target['step'], target['product_id']),
            'step_agreement': bool(action) and action['step'] == target['step'],
            'teacher_impulse': is_off_list_grab(target, facts), 'model_impulse': model_impulse,
            'model_list_grab': bool(action) and action['step'] == 'grab' and any(
                p['product_id'] == action['product_id'] and p['matches_remaining_list'] for p in facts['grabbable_products']),
            'violation': violation, 'target': target, 'response': text})
    n = len(records)
    metrics = {
        'examples': n,
        'strict_schema_rate': _rate(sum(r['strict_schema'] for r in records), n),
        'observation_valid_rate': _rate(sum(r['observation_valid'] for r in records), n),
        'exact_action_agreement': _rate(sum(r['exact_agreement'] for r in records), n),
        'step_agreement': _rate(sum(r['step_agreement'] for r in records), n),
        'by_kind': {}, 'impulse': {}, 'impulse_by_style': {},
    }
    for kind in ('move', 'list_grab', 'impulse_decision', 'checkout'):
        own = [r for r in records if r['kind'] == kind]
        metrics['by_kind'][kind] = {'n': len(own), 'exact_agreement': _rate(sum(r['exact_agreement'] for r in own), len(own))}
    metrics['list_grab_recall'] = _rate(sum(r['model_list_grab'] for r in records if r['kind'] == 'list_grab'),
                                        metrics['by_kind']['list_grab']['n'])
    metrics['checkout_recall'] = _rate(sum(bool(r['step_agreement']) for r in records if r['kind'] == 'checkout'),
                                       metrics['by_kind']['checkout']['n'])
    moments = [r for r in records if r['kind'] == 'impulse_decision']
    tp = sum(r['teacher_impulse'] and r['model_impulse'] for r in moments)
    fp = sum(not r['teacher_impulse'] and r['model_impulse'] for r in moments)
    fn = sum(r['teacher_impulse'] and not r['model_impulse'] for r in moments)
    precision, recall = _rate(tp, tp + fp), _rate(tp, tp + fn)
    metrics['impulse'] = {
        'moments': len(moments), 'teacher_grab_rate': _rate(sum(r['teacher_impulse'] for r in moments), len(moments)),
        'model_grab_rate': _rate(sum(r['model_impulse'] for r in moments), len(moments)),
        'precision': precision, 'recall': recall,
        'f1': (2 * precision * recall / (precision + recall)) if precision and recall else (0.0 if moments else None),
        'grab_vs_pass_agreement': _rate(sum(r['teacher_impulse'] == r['model_impulse'] for r in moments), len(moments)),
    }
    for style in sorted({r['style'] for r in moments}):
        own = [r for r in moments if r['style'] == style]
        metrics['impulse_by_style'][style] = {'moments': len(own),
            'teacher_grab_rate': _rate(sum(r['teacher_impulse'] for r in own), len(own)),
            'model_grab_rate': _rate(sum(r['model_impulse'] for r in own), len(own))}
    proposals = [r for r in records if r['model_impulse']]
    metrics['off_list_proposals'] = len(proposals)
    metrics['rule_violations'] = dict(Counter(r['violation'] for r in proposals if r['violation']))
    metrics['rule_violation_rate'] = _rate(sum(bool(r['violation']) for r in proposals), len(proposals))
    return metrics, records


def trip_report(path):
    """Impulse and guardrail summary of one canonical run file (Python-authored totals)."""
    from agents.schema import parse_decision
    from core.accounting import cents
    from core.run_log import read_run

    run = read_run(path)
    header, summary = run['start'], run['summary']
    customers = {s['agent_id']: s['customer'] for s in header['shoppers']}
    lists = {agent: {item['product_id'] for item in c['shopping_list']} for agent, c in customers.items()}
    prices = {p['id']: cents(p['price']) for p in header['catalogue']}
    events = defaultdict(list)
    for event in run['events']:
        events[event['agent_id']].append(event)
    trips = []
    for shopper in summary['shoppers']:
        agent = shopper['agent_id']
        proposed = applied = overridden = rejected = 0
        for event in events[agent]:
            raw = event.get('raw_response')
            proposal = parse_decision(raw, event['before']['allowed_steps']) if isinstance(raw, str) else None
            if proposal is None or proposal.step != 'grab' or proposal.product_id in lists[agent]:
                continue
            proposed += 1
            action = event.get('action') or {}
            if event.get('failure') or event.get('outcome') != 'applied':
                rejected += 1
            elif (action.get('step'), action.get('product_id')) != ('grab', proposal.product_id):
                overridden += 1
            else:
                applied += 1
        off_list = shopper.get('off_list_units')
        impulse = (off_list if shopper['finished'] else 0) if type(off_list) is int else None
        cart = events[agent][-1]['after']['cart'] if events[agent] else []
        extra = [(i['product_id'], i['quantity']) for i in cart if i['product_id'] not in lists[agent]]
        spend = None
        if impulse is not None:
            if shopper['finished'] and sum(q for _, q in extra) != impulse:
                raise ValueError(f'{agent}: cart extras do not reconcile to Python off_list_units')
            spend = sum(prices[pid] * q for pid, q in extra) if shopper['finished'] else 0
        trips.append({'shopper_id': agent, 'style': customers[agent]['shopping_style'],
            'finished': shopper['finished'], 'requested_units': shopper['requested_units'],
            'purchased_units': shopper['purchased_fulfilled_units'], 'impulse_units': impulse,
            'impulse_spend_cents': spend, 'impulse_products': [pid for pid, _ in extra] if shopper['finished'] else [],
            'proposed_off_list_grabs': proposed, 'applied_off_list_grabs': applied,
            'overridden_by_assist': overridden, 'rejected_by_core': rejected,
            'loop_detections': shopper.get('loop_detections'), 'turns_used': shopper['turns_used']})

    def aggregate(group):
        n = len(group)
        impulses = [t['impulse_units'] for t in group]
        spends = [t['impulse_spend_cents'] for t in group]
        requested = sum(t['requested_units'] for t in group)
        known = n and None not in impulses
        return {'trips': n, 'checkout_completion': _rate(sum(t['finished'] for t in group), n),
            'purchased_unit_fulfillment': _rate(sum(t['purchased_units'] for t in group), requested),
            'impulse_units_per_trip': _rate(sum(impulses), n) if known else None,
            'impulse_trip_share': _rate(sum(i > 0 for i in impulses), n) if known else None,
            'impulse_spend_per_trip_usd': (sum(spends) / 100 / n) if n and None not in spends else None,
            'proposed_off_list_grabs': sum(t['proposed_off_list_grabs'] for t in group),
            'applied_off_list_grabs': sum(t['applied_off_list_grabs'] for t in group),
            'overridden_by_assist': sum(t['overridden_by_assist'] for t in group),
            'rejected_by_core': sum(t['rejected_by_core'] for t in group)}

    return {'run_id': header['run_id'], 'layout_id': header['layout']['id'],
        'model': header.get('model'), 'status': summary['status'],
        'navigation_policy': header.get('config', {}).get('navigation_policy'),
        'overall': aggregate(trips),
        'by_style': {style: aggregate([t for t in trips if t['style'] == style])
                     for style in sorted({t['style'] for t in trips})},
        'failures': summary.get('failures'), 'trips': trips,
        'impulse_source': 'Python summary off_list_units (finished trips only; unfinished count as 0)'}
