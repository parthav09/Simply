"""Pure v2 outcome metrics. No current store, UI, provider or credential reads."""
from collections import Counter
from statistics import mean
from core.accounting import basket, cents, resolve_product


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    left = int(position)
    return ordered[left] + (ordered[min(left+1, len(ordered)-1)] - ordered[left]) * (position-left)


def loop_metrics(events):
    signatures, longest, stalled, loops = [], 0, 0, 0
    for e in events:
        before, after = e['before'], e['after']
        changed = before['cart'] != after['cart'] or before['phase'] != after['phase']
        stalled = 0 if changed else stalled + 1
        longest = max(longest, stalled)
        sig = (after['x'], after['y'], after['phase'],
               tuple(sorted((i['product_id'], i['quantity']) for i in after['cart'])),
               e['action']['step'] if e['action'] else e['outcome'])
        signatures.append(sig)
        for n in range(1, 5):
            if len(signatures) >= 3*n and signatures[-n:] == signatures[-2*n:-n] == signatures[-3*n:-2*n]:
                loops += 1
                break
    return {'loop_detections': loops, 'longest_no_progress_turns': longest}


def enrich_summary(base, start, events, final, status):
    catalogue = start['catalogue']
    final_by_id = {s['agent_id']: s['state'] for s in final}
    by_id = {s['agent_id']: s for s in start['shoppers']}
    traffic = Counter(f"{s['state']['x']},{s['state']['y']}" for s in start['shoppers'])
    if start['config']['mode'] == 'actions':
        for e in events:
            if e['outcome'] == 'applied' and e['action']['step'].startswith('move_'):
                traffic[f"{e['after']['x']},{e['after']['y']}"] += 1
    rows = []
    for old in base['shoppers']:
        aid = old['agent_id']; profile = by_id[aid]['customer']; state = final_by_id[aid]
        own = [e for e in events if e['agent_id'] == aid]
        totals = basket(state['cart'], catalogue)
        needed = Counter()
        for item in profile['shopping_list']:
            needed[item['product_id']] += item['quantity']
        fulfilled = sum(min(q, totals['quantities'].get(pid, 0)) for pid, q in needed.items())
        units = sum(needed.values())
        budget = cents(profile['budget_per_trip_usd'])
        overshoot = max(0, totals['known_basket_cents'] - budget) if not totals['unresolved_units'] else None
        offlist = sum(q for pid, q in totals['quantities'].items() if pid not in needed)
        excess = sum(max(0, q-needed[pid]) for pid, q in totals['quantities'].items() if pid in needed)
        maxovershoot = 0; above_price = 0; brand_checks = 0; brand_matches = 0
        for e in own:
            after = basket(e['after']['cart'], catalogue)
            maxovershoot = max(maxovershoot, max(0, after['known_basket_cents']-budget))
            if e['outcome'] != 'applied' or e['action']['step'] != 'grab':
                continue
            product = resolve_product({'product_id': e['action']['product_id']}, catalogue)
            if not product:
                continue
            need = next((i for i in profile['shopping_list'] if i['product_id'] == product['id']), None)
            if need and cents(product['price']) > cents(need['max_acceptable_unit_price']):
                above_price += 1
            if need and need.get('preferred_brand') and product.get('company'):
                brand_checks += 1
                brand_matches += need['preferred_brand'].casefold() == product['company'].casefold()
        positions = {(by_id[aid]['state']['x'], by_id[aid]['state']['y'])}
        positions.update((e['after']['x'], e['after']['y']) for e in own)
        priority = {}
        for name in sorted({i['priority'] for i in profile['shopping_list']}):
            subset = [i for i in profile['shopping_list'] if i['priority'] == name]
            requested = Counter()
            for i in subset:
                requested[i['product_id']] += i['quantity']
            count = sum(requested.values())
            priority[name] = {'requested_units': count, 'fulfilled_units': sum(min(q,totals['quantities'].get(pid,0)) for pid,q in requested.items())}
        reason = old['stop_reason']
        if not old['finished'] and reason in ('aborted', 'cancelled', 'budget_exhausted'):
            reason = status
        rows.append({**old, **{k:v for k,v in totals.items() if k != 'quantities'},
                     'requested_units': units, 'fulfilled_units': fulfilled,
                     'list_completion': fulfilled/units if units else 1.0,
                     'purchased_fulfilled_units': fulfilled if old['finished'] else 0,
                     'checkout_spend_cents': totals['basket_cents'] if old['finished'] else 0,
                     'budget_cents': budget, 'overshoot_cents': overshoot,
                     'max_basket_overshoot_cents': maxovershoot,
                     'checkout_overshoot_cents': overshoot if old['finished'] else 0,
                     'off_list_units': offlist, 'excess_list_units': excess,
                     'above_acceptable_price_purchases': above_price,
                     'brand_checks': brand_checks, 'brand_matches': brand_matches,
                     'diet_consistency': 'unassessed: product metadata is not independently verified',
                     'priority_fulfillment': priority, 'unique_cells': len(positions),
                     'stop_reason': reason, **loop_metrics(own)})
    latency = [e['telemetry'].get('api_latency_ms',e['telemetry']['provider_latency_ms']) for e in events if e.get('telemetry',{}).get('request_submitted',True)]
    known_cost = sum(e.get('telemetry',{}).get('estimated_cost_micros') or 0 for e in events)
    unknown = sum(e.get('telemetry',{}).get('estimated_cost_micros') is None for e in events)
    token_fields = ('promptTokenCount','candidatesTokenCount','thoughtsTokenCount','cachedContentTokenCount')
    if start.get('metrics_version',1)>=2:
        token_fields += ('cacheWriteTokenCount','cacheWrite30mTokenCount','cacheWrite12hTokenCount')
    usage = {field: sum((e.get('telemetry',{}).get('usage') or {}).get(field,0) for e in events) for field in token_fields}
    unknown_usage = sum(not e.get('telemetry',{}).get('usage') for e in events
                        if e.get('telemetry',{}).get('decision_source') != 'model_plan_continuation')
    rounds = {}
    for e in events:
        rounds[str(e['round'])] = max(rounds.get(str(e['round']),0),e.get('telemetry',{}).get('round_provider_wait_ms',0))
    requested = sum(r['requested_units'] for r in rows)
    resolved = [r for r in rows if r['overshoot_cents'] is not None]
    result = {**base, 'shoppers': rows,
            'mean_list_completion': mean(r['list_completion'] for r in rows),
            'unit_fulfillment': sum(r['fulfilled_units'] for r in rows)/requested if requested else 1.0,
            'purchased_unit_fulfillment': sum(r['purchased_fulfilled_units'] for r in rows)/requested if requested else 1.0,
            'sales_cents': sum(r['checkout_spend_cents'] or 0 for r in rows),
            'sales_unresolved_units': sum(r['unresolved_units'] for r in rows if r['finished']),
            'basket_value_cents': sum(r['known_basket_cents'] for r in rows),
            'overspending_fraction': sum(r['overshoot_cents'] > 0 for r in resolved)/len(resolved) if resolved else None,
            'loop_detections': sum(r['loop_detections'] for r in rows),
            'traffic': dict(traffic),
            'performance': {'request_latency_p50_ms': percentile(latency,.5), 'request_latency_p95_ms': percentile(latency,.95),
                            'round_provider_wait_ms': rounds,
                            'run_duration_ms': max((e.get('elapsed_ms',0) for e in events),default=0)},
            'resources': {'usage': usage, 'unknown_usage_requests': unknown_usage,
                          'known_estimated_cost_usd': known_cost/1e6,
                          'unknown_cost_attempts': unknown,
                          'unresolved_reserved_usd': sum(e.get('telemetry',{}).get('reserved_micros',0) for e in events if e.get('telemetry',{}).get('estimated_cost_micros') is None)/1e6}}
    if start['provider']=='openrouter':
        charges=[e.get('telemetry',{}).get('provider_reported_cost_usd') for e in events
                 if e.get('telemetry',{}).get('request_submitted') is True]
        result['resources'].update(provider_reported_cost_usd=sum(charges) if all(n is not None for n in charges) else None,
            unknown_provider_charge_requests=sum(n is None for n in charges))
    return result
