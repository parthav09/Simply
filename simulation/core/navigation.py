"""Versioned Gary-2 action assistance, using only frozen run facts.

This selects an action; core.actions remains the only state mutation boundary.
The same pure function validates recorded adjustments without loading a store.
"""
from collections import Counter

from agents.base import Decision
from agents.steps import MOVES

MODEL_ONLY = 'model_only'
GARY2 = 'gary2_v1'
GARY2_CURRENT = 'gary2_v2'
ASSISTED = (GARY2, GARY2_CURRENT)
POLICIES = (MODEL_ONLY, *ASSISTED)


def adjusted_action(proposal, before, layout, visits, policy=GARY2, action_limit=None):
    allowed = set(before['allowed_steps'])
    x, y = before['x'], before['y']
    counts = {step: visits.get((x + dx, y + dy), 0)
              for step, (dx, dy) in MOVES.items() if step in allowed}
    least = min(counts, key=lambda step: (counts[step], step)) if counts else None
    owned = Counter()
    needed = Counter()
    for item in before['cart']:
        owned[item['product_id']] += item['quantity']
    for item in before['requirements']:
        needed[item['product_id']] += item['quantity']
    remaining = needed - owned
    limit = min(before['turn_budget'], action_limit or before['turn_budget']) if policy == GARY2_CURRENT else before['turn_budget']
    turns_left = limit - before['turns_used']
    reachable = [product for shelf in layout['shelves']
                 if shelf['offsets'] and min(abs(x - shelf['x'] - dx) + abs(y - shelf['y'] - dy)
                                            for dx, dy in shelf['offsets']) == 1
                 for product in shelf['products']]
    if policy == GARY2_CURRENT:
        # Gary-2 inspects adjacent shelves left, right, up, then down. Preserve
        # that priority when multiple Simply shelf groups are within reach.
        reachable = []
        seen = set()
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            for shelf in layout['shelves']:
                if not any((shelf['x'] + sx, shelf['y'] + sy) == (x + dx, y + dy)
                           for sx, sy in shelf['offsets']):
                    continue
                for product in shelf['products']:
                    if product['id'] not in seen:
                        reachable.append(product)
                        seen.add(product['id'])

    def choose(step, reason, product_id=None):
        if step == proposal.step and product_id == proposal.product_id:
            return proposal, None
        return Decision(step, product_id, f'Navigation assist: {reason}. Model proposed {proposal.step}: {proposal.reason}'), reason

    # Gary-2 prioritizes checkout near its iteration limit, then reachable targets.
    if owned and 'checkout' in allowed and turns_left <= 15:
        return choose('checkout', 'checkout with few turns remaining')
    if 'grab' in allowed:
        for product in reachable:
            if remaining[product['id']] > 0:
                return choose('grab', 'pick up a reachable list item', product['id'])
    # Gary-2 keeps an unowned off-list grab while targets remain and checkout is not urgent.
    if (policy == GARY2 and proposal.step == 'grab' and proposal.product_id and remaining
            and not owned[proposal.product_id] and not remaining[proposal.product_id]
            and turns_left / before['turn_budget'] > .10):
        return proposal, None
    if proposal.step == 'grab' and owned[proposal.product_id] and not remaining[proposal.product_id] and least:
        return choose(least, 'avoid picking up an already owned item')
    if owned and (not remaining or turns_left / limit < .30):
        if 'checkout' in allowed:
            return choose('checkout', 'checkout after shopping or as turns run low')
        checkouts = layout['checkout']
        if checkouts:
            tx, ty = min(checkouts, key=lambda cell: abs(cell[0] - x) + abs(cell[1] - y))
            candidates = []
            if tx != x:
                candidates.append('move_right' if tx > x else 'move_left')
            if ty != y:
                candidates.append('move_down' if ty > y else 'move_up')
            candidates = [step for step in candidates if step in counts]
            if candidates:
                return choose(min(candidates, key=lambda step: counts[step]), 'head toward checkout')
        if least:
            return choose(least, 'find an open route toward checkout')
    if least and not reachable:
        if proposal.step in ('remove', 'checkout') and 'checkout' not in allowed:
            return choose(least, 'keep exploring away from shelves and checkout')
        if proposal.step in counts and not owned and remaining and counts[proposal.step] > counts[least]:
            return choose(least, 'avoid revisiting a busier cell')
    return proposal, None


def recorded_visits(start, events, agent_id):
    initial = next(s['state'] for s in start['shoppers'] if s['agent_id'] == agent_id)
    visits = Counter({(initial['x'], initial['y']): 1})
    for event in events:
        if event['agent_id'] == agent_id and event['outcome'] == 'applied':
            visits[event['after']['x'], event['after']['y']] += 1
    return visits
