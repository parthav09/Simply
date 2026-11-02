"""Versioned shopper prompts. Baseline preserves the pre-evaluation prompt."""

import json
from collections import Counter
from agents.schema import DECISION_JSON_EXAMPLE, format_allowed_actions

def baseline_prompt(self, observation=None):
    obs = self._unpack_observation(observation)
    profile = obs.customer
    shelves = []
    for shelf in obs.nearby_shelves:
        products = ", ".join(shelf.products) or "empty"
        shelves.append(f"- ({shelf.x}, {shelf.y}) {shelf.aisle}: {products}")
    if not shelves:
        shelves.append("- no shelves in view")
    cart = ", ".join(getattr(item, "name", str(item)) for item in obs.cart) or "empty"
    return "\n".join([
        profile.build_persona_summary(),
        "",
        profile.build_behavioral_directives(),
        "",
        "Requested products: " + (", ".join(profile.get_target_products()) or "none"),
        f"Current state: {obs.phase} at ({obs.x}, {obs.y}).",
        f"Cart: {cart}.",
        "Nearby shelves:",
        *shelves,
        "Choose one step:",
        format_allowed_actions(obs.allowed_steps),
        f"Reply with JSON only: {DECISION_JSON_EXAMPLE}",
    ])


def informed_prompt(shopper, observation=None, *, action_plan=False):
    """Information only: no route solver, purchase override, or budget enforcement."""
    from core.accounting import basket, cents
    from core.perception import SHELF_SIGHT_RADIUS
    from agents.schema import MAX_PLAN_ACTIONS
    from core.shopping import SIMPLE_SHOPPING
    obs = shopper._unpack_observation(observation)
    grid = getattr(shopper, '_grid', None)
    if grid is None:
        raise ValueError('Informed prompts require a core store observation')
    cart = [{'product_id': i.product_id, 'name': i.name, 'quantity': i.quantity} for i in obs.cart]
    totals = basket(cart, list(grid.products.values()))
    quantities = totals['quantities']
    visible = []
    for shelf in grid.shelves:
        if grid.distance_to_shelf(obs.x, obs.y, shelf) == 1:
            visible.extend({'product_id': p['id'], 'name': p['name'], 'unit_price_cents': cents(p['price']),
                            'company': p.get('company', ''), 'dietary_tags': p.get('dietary_tags', ''),
                            'allergens': p.get('allergens', '')} for p in shelf.products)
    profile = obs.customer
    simple = getattr(shopper, 'shopping_rules', None) == SIMPLE_SHOPPING
    if simple:
        visible = [product for product in visible if not quantities.get(product['product_id'], 0)]
    needs = [{'product_id': i.product_id, 'name': i.product_name, 'quantity': i.quantity,
              'remaining': max(0, i.quantity - quantities.get(i.product_id, 0)), 'priority': i.priority,
              'department': i.department, 'max_unit_price_cents': cents(i.max_acceptable_unit_price),
              'preferred_brand': i.preferred_brand} for i in profile.shopping_list]
    history = [{'step': o.decision.step if o.decision else None, 'product_id': o.decision.product_id if o.decision else None,
                'reason': o.decision.reason if o.decision else '', 'applied': o.applied, 'failure': o.failure}
               for o in shopper.decision_history[-8:]]
    moves = {step: (dx, dy) for step, (dx, dy) in {
        'move_up': (0, -1), 'move_down': (0, 1),
        'move_left': (-1, 0), 'move_right': (1, 0)}.items() if step in obs.allowed_steps}
    visited = Counter((t.x_after, t.y_after) for t in shopper.trajectory)
    if shopper.trajectory:
        first = shopper.trajectory[0]
        visited[(first.x_before, first.y_before)] += 1
    else:
        visited[(obs.x, obs.y)] = 1
    remaining_by_id = {n['product_id']: n for n in needs if n['remaining'] > 0}
    nearby_shelves = []
    for shelf in grid.shelves:
        distance = grid.distance_to_shelf(obs.x, obs.y, shelf)
        if distance <= SHELF_SIGHT_RADIUS:
            nearby_shelves.append({
                'department': shelf.department, 'position': [shelf.x, shelf.y], 'distance': distance,
                'has_remaining_target': any(p['id'] in remaining_by_id for p in shelf.products),
                'products': [{'product_id': p['id'], 'name': p['name'],
                              'matches_remaining_list': p['id'] in remaining_by_id} for p in shelf.products],
            })
    nearby_shelves.sort(key=lambda shelf: shelf['distance'])
    for product in visible:
        need = remaining_by_id.get(product['product_id'])
        product['remaining_requested_quantity'] = need['remaining'] if need else 0
        product['matches_remaining_list'] = need is not None
        product['within_item_price_limit'] = (product['unit_price_cents'] <= need['max_unit_price_cents']) if need else None
        product['affordable_with_remaining_budget'] = product['unit_price_cents'] <= cents(profile.budget_per_trip_usd) - totals['known_basket_cents']
    department_locations = []
    for shelf in grid.shelves:
        access = sorted({cell for shelf_cell in shelf.cells() for cell in grid.stand_cells_for(shelf_cell)})
        department_locations.append({'department': shelf.department, 'shelf_cells': shelf.cells(),
                                     'walkable_access_cells': access})
    checkout_distance = min(abs(obs.x-x)+abs(obs.y-y) for x, y in grid.checkout)
    action_limit = min(shopper.turn_budget, getattr(shopper, '_action_limit', None) or shopper.turn_budget)
    turns_remaining = action_limit - shopper.turns_used
    ratio = turns_remaining / max(action_limit, 1)
    if cart:
        checkout_urgency = 'critical' if ratio <= .10 else 'high' if ratio <= .30 else 'medium' if ratio <= .50 else 'low'
    else:
        checkout_urgency = 'high' if ratio <= .10 else 'medium' if ratio <= .30 else 'low'
    map_rows = [''.join('@' if (x,y)==(obs.x,obs.y) else '#' if (x,y) in grid.blocked
                        else 'C' if (x,y) in grid.checkout else '.' for x in range(grid.width))
                for y in range(grid.height)]
    facts = {
        'prompt_revision': 'observe-plan-v5-unique-checkout' if simple else 'observe-plan-v4-soft-budget',
        'position': [obs.x, obs.y], 'phase': obs.phase,
        'coordinate_system': 'Top-left origin (0,0). x increases right; y increases down.',
        'legal_move_destinations': {step: [obs.x+dx, obs.y+dy] for step, (dx,dy) in moves.items()},
        'adjacent_destination_visit_counts': {step: visited[(obs.x+dx, obs.y+dy)] for step, (dx,dy) in moves.items()},
        'cart': cart, 'spend_cents': totals['basket_cents'], 'budget_cents': cents(profile.budget_per_trip_usd),
        'remaining_budget_cents': cents(profile.budget_per_trip_usd) - totals['known_basket_cents'],
        'shopping_list': needs, 'remaining_items': list(remaining_by_id.values()),
        'grabbable_products': visible,
        'nearby_shelves': nearby_shelves, 'shelf_sight_radius': SHELF_SIGHT_RADIUS,
        'your_last_plan': next((o.decision.reason for o in reversed(shopper.decision_history) if o.decision and o.decision.reason), ''),
        'checkout_cells': grid.checkout, 'store_bounds': [grid.width, grid.height],
        'department_locations': department_locations,
        'floor_map': {'legend': '@=you; #=blocked shelf; .=walkable; C=checkout. Row index is y, column index is x.', 'rows': map_rows},
        'checkout_distance_lower_bound': checkout_distance,
        'checkout_actions_still_needed': 1 if simple or obs.phase == 'CheckoutState' else 2,
        'blocked_cells': sorted(grid.blocked),
        'recent_actions': history,
        'recent_positions': [[t.x_after, t.y_after] for t in shopper.trajectory[-12:]],
        'turns_used': shopper.turns_used, 'turns_remaining': turns_remaining,
        'action_limit': action_limit,
        'checkout_urgency': checkout_urgency,
        'allowed_steps': list(obs.allowed_steps),
    }
    if action_plan:
        # The floor map already represents every blocked cell. Avoid transmitting
        # the same geometry twice in each planning request.
        facts.pop('blocked_cells')
    response_instructions = ([
        f'Choose a short plan of 1–{MAX_PLAN_ACTIONS} primitive actions. Use several moves through a clear corridor instead of asking again at every cell. Every action still costs one turn.',
        'The FIRST action must be allowed_steps. Later actions must be physically legal after preceding actions; use floor_map to check every planned destination. The engine never fills in a route for you.',
        'AT A SHELF, plan needed grabs first, one action per remaining unit. You may then grab one off-list item whose matches_remaining_list is false when it fits this shopper and the budget. Skip that extra when checkout_urgency is high or critical.',
        'Movement is interrupted as soon as a new shelf assortment becomes grabbable, so stop to inspect and choose purchases there. Never plan a grab for a product whose details are not currently grabbable_products.',
        'Plans stop on failure, unexpected state changes, completion or the turn limit. Reconsider from the next observation; no automatic purchase, rerouting, or checkout occurs.',
        'Return exactly one JSON object with one short public reason and actions in order. Each action has step and product_id (empty for moves/checkout). No prose outside JSON.',
        'Reply format: {"reason":"Head toward Pantry via the open corridor","actions":[{"step":"move_right","product_id":""},{"step":"move_right","product_id":""}]}',
    ] if action_plan else [
        'Only choose an allowed step. Use product_id for grab/remove; use an empty string for moves/checkout. Return one JSON object with step, product_id and a brief reason.',
        f'Reply with exactly one JSON object, no repeated objects or extra text: {DECISION_JSON_EXAMPLE}',
    ])
    return '\n'.join([
        profile.build_persona_summary(), profile.build_behavioral_directives(),
        'SHOPPING MISSION: collect requested quantities according to your preferences, then pay at checkout before turns run out.',
        'BUDGET: budget_cents and item price limits are personal spending targets, not engine restrictions. Consider them according to this shopper’s personality. You may deliberately overspend for a priority or fitting treat; explain that tradeoff. Do not overspend just because it is permitted. A negative remaining_budget_cents does not block buying or checkout.',
        'You choose every action. Persona preferences guide tradeoffs; shopping is the task, not aimless exploration. Prices are integer cents.',
        'WORK ONE TARGET AT A TIME: use remaining_items to choose a specific product and its department. Keep that destination until it is collected or you deliberately abandon it.',
        'Your reason is one short public plan for your next turn: name the target or checkout and intended destination. Continue your_last_plan unless the recorded outcome or needs changed.',
        'AT A SHELF: inspect grabbable_products. A product with matches_remaining_list true is still needed — prioritize it while considering its price and your spending preferences. Use only an ID in that array.',
        'IMPULSE: matches_remaining_list false means the product is not on the remaining list. You may grab one unit when it fits this shopper — a deal, a treat, or something the profile would actually want. Consider the budget target and say why in the reason. Do not grab an unrelated product, and do not grab a product already in the cart.',
        'Skip extras when checkout_urgency is high or critical, or when remaining_items is empty. Then go to checkout.',
        'LOOK AHEAD: nearby_shelves lists assortments within six cells and marks remaining targets. Use those signs to approach a needed department; only grabbable_products is within reach and has current price and preference evidence.',
        ('Each target is a unique product. Grab at most one unit of any product; products already in your cart are omitted from grabbable_products.' if simple else
         'Each grab adds exactly one unit. Another unit of a needed product is allowed only while remaining_requested_quantity is above zero.'),
        'NAVIGATION: x increases right and y increases down. Each move changes one cell. The floor_map shows barriers; legal_move_destinations gives the actual possible next cells.',
        'Aim for a walkable_access_cell next to the chosen department, never a blocked shelf cell. Follow open corridors around shelf ends; a short detour away from the target may be necessary.',
        'Use recent_positions, recent_actions and adjacent_destination_visit_counts to notice oscillation. If a route repeats without a pickup or progress, choose a different corridor and explain the new destination. Do not repeat a rejected grab from the same position.',
        'FINISH THE TRIP: when the list is satisfied or further shopping is unsuitable, take the basket to a checkout cell. Reserve walking turns plus the checkout actions and a detour margin; start returning early rather than on the last turn.',
        'checkout_distance_lower_bound is straight-line grid distance, NOT a route or a guarantee. Shelf detours can require more moves. With about a quarter of your turns left and a nonempty basket, prioritize reaching checkout over searching for extras.',
        ('One checkout action at a checkout cell pays for your basket and finishes the trip immediately. Empty carts cannot check out.' if simple else
         'Checkout from BrowsingState takes two checkout decisions: the first enters CheckoutState; the second pays and finishes. In CheckoutState, select checkout again to pay. Empty carts cannot check out.'),
        'A failed action still consumes a turn. Unpaid baskets are not completed purchases. Never invent products, coordinates, discounts or dietary evidence; unavailable preference evidence remains unknown.',
        'Current state: ' + json.dumps(facts, separators=(',', ':'), ensure_ascii=False),
        'Available first steps:' if action_plan else 'Choose one step:', format_allowed_actions(obs.allowed_steps),
        *response_instructions,
    ])
