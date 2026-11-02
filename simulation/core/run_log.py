"""Versioned full-trip logs and pure metrics; reading never imports a store or model."""

import json
import gzip
import math
from collections import Counter
from pathlib import Path

SCHEMA_VERSION = 2
OUTCOMES = {"applied", "proposed", "invalid_decision", "provider_exception", "grid_rejected"}
FAILURES = ("invalid_decision", "provider_exception", "grid_rejected")
PHASES = {"BrowsingState", "CheckoutState", "FinishedState"}
MOVEMENT = {"move_left", "move_right", "move_up", "move_down"}


class RunLogError(ValueError):
    """A saved trip is malformed or incompatible with this reader."""


def _summarize_v1(start, events, final_shoppers, status="completed"):
    """Compute quantity-aware metrics from values, without changing the inputs."""
    final_by_id = {s["agent_id"]: s for s in final_shoppers}
    movements = Counter()
    attempts = Counter()
    failures = Counter({kind: 0 for kind in FAILURES})
    applying = start["config"]["mode"] == "actions"
    for event in events:
        if event["outcome"] in FAILURES:
            failures[event["outcome"]] += 1
        if applying:
            attempts[event["agent_id"]] += 1
            if event["outcome"] == "applied" and event["action"]["step"] in MOVEMENT:
                movements[event["agent_id"]] += 1
    rows = []
    for initial in start["shoppers"]:
        agent_id = initial["agent_id"]
        final = final_by_id[agent_id]
        state = final["state"]
        requested = Counter()
        cart = Counter()
        for item in initial["customer"]["shopping_list"]:
            requested[item["product_id"]] += item["quantity"]
        for item in state["cart"]:
            cart[item["product_id"]] += item["quantity"]
        requested_units = sum(requested.values())
        fulfilled_units = sum(min(count, cart[pid]) for pid, count in requested.items())
        finished = state["phase"] == "FinishedState"
        reason = (
            "finished_checkout" if finished else
            "turn_budget_exhausted" if state["turns_used"] >= state["turn_budget"] else
            "action_limit" if state["turns_used"] >= _action_limit(start) else
            "no_allowed_actions" if not state["allowed_steps"] else
            "global_round_limit" if status == "completed" else status
        )
        rows.append({
            "agent_id": agent_id,
            "finished": finished,
            "stop_reason": reason,
            "requested_units": requested_units,
            "fulfilled_units": fulfilled_units,
            "list_completion": fulfilled_units / requested_units if requested_units else 1.0,
            "successful_moves": movements[agent_id],
            "turns_used": attempts[agent_id] if applying else 0,
        })
    finished_rows = [r for r in rows if r["finished"]]
    count = len(rows)
    return {
        "mode": start["config"]["mode"],
        "status": status,
        "shopper_count": count,
        "finished_count": len(finished_rows),
        "checkout_completion": len(finished_rows) / count if count else 0.0,
        "mean_list_completion": sum(r["list_completion"] for r in rows) / count if count else 0.0,
        "mean_successful_moves": sum(movements.values()) / count if count else 0.0,
        "turns_used": sum(attempts.values()),
        "mean_turns_to_checkout": (
            sum(r["turns_used"] for r in finished_rows) / len(finished_rows)
            if finished_rows else None
        ),
        "failures": dict(failures),
        "shoppers": rows,
    }


def summarize(start, events, final_shoppers, status="completed"):
    base = _summarize_v1(start, events, final_shoppers, status)
    if start.get("schema_version", 1) == 1:
        return base
    from core.metrics import enrich_summary
    return enrich_summary(base, start, events, final_shoppers, status)


def summary_text(summary):
    mean = summary["mean_turns_to_checkout"]
    return "\n".join([
        f"Status: {summary['status']} ({summary['mode']})",
        f"Checkout: {summary['finished_count']}/{summary['shopper_count']}",
        f"Mean list completion: {summary['mean_list_completion']:.1%}",
        f"Mean successful moves: {summary['mean_successful_moves']:.2f}",
        f"Turns used: {summary['turns_used']}",
        f"Mean turns to checkout: {mean:.2f}" if mean is not None else "Mean turns to checkout: N/A (0 finished)",
        "Failures: " + ", ".join(f"{k}={v}" for k, v in summary["failures"].items()),
        *[f"  {r['agent_id']}: {r['stop_reason']}, {r['fulfilled_units']}/{r['requested_units']} requested units, "
          f"{r['successful_moves']} moves, {r['turns_used']} turns" for r in summary["shoppers"]],
    ])


class RunWriter:
    """One coordinating thread writes; exclusive creation protects existing evidence."""

    def __init__(self, path, start):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.start = start
        self.events = []
        self.failed = False
        self.handle = self.path.open("x", encoding="utf-8")
        try:
            self._write(start)
            self.flush()
        except BaseException:
            self.handle.close()
            raise

    def _write(self, record):
        try:
            self.handle.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
        except BaseException:
            self.failed = True
            raise

    def append(self, event, round_number):
        record = {"type": "decision", "sequence": len(self.events) + 1,
                  "round": round_number, **event}
        self._write(record)
        self.events.append(record)

    def flush(self):
        try:
            self.handle.flush()
        except BaseException:
            self.failed = True
            raise

    def finish(self, final_shoppers, rounds_completed, status="completed", error=None):
        summary = summarize(self.start, self.events, final_shoppers, status)
        self._write({"type": "run_end", "status": status, "error": error,
                     "rounds_completed": rounds_completed, "shoppers": final_shoppers,
                     "summary": summary})
        self.flush()
        return summary

    def close(self):
        self.handle.close()


def _require(condition, message):
    if not condition:
        raise RunLogError(message)


def _fields(record, required):
    _require(set(required) <= record.keys(), "missing fields: " + ", ".join(sorted(set(required) - record.keys())))


def _int(value, minimum=0):
    return type(value) is int and value >= minimum


def _action_limit(start):
    planning = start.get('config', {}).get('action_planning') or {}
    if 'action_limit' in planning:
        return planning['action_limit']
    return start.get('config', {}).get('action_limit', math.inf)


def _items(items):
    _require(isinstance(items, list), "expected an item list")
    for item in items:
        _require(isinstance(item, dict) and isinstance(item.get("product_id"), str)
                 and _int(item.get("quantity"), 1), "items need a product_id and positive quantity")


def _state(state):
    _require(isinstance(state, dict), "expected a state object")
    _require(state.get("phase") in PHASES, "unknown shopper phase")
    _require(type(state.get("x")) is int and type(state.get("y")) is int,
             "state coordinates must be integers")
    _require(_int(state.get("turns_used")) and _int(state.get("turn_budget"), 1),
             "invalid turn counters")
    _require(state["turns_used"] <= state["turn_budget"], "turns exceed budget")
    _items(state.get("cart"))
    _items(state.get("requirements"))
    _require(isinstance(state.get("nearby_shelves"), list), "missing nearby shelves")
    _require(isinstance(state.get("allowed_steps"), list)
             and all(isinstance(s, str) for s in state["allowed_steps"]), "invalid allowed steps")


def _start(record):
    _require(record.get("type") == "run_start", "first record must be run_start")
    _require(type(record.get("schema_version")) is int
             and record["schema_version"] in (1, SCHEMA_VERSION), "unsupported schema version")
    for field in ("run_id", "recorded_at", "provider", "model", "prompt_version"):
        _require(isinstance(record.get(field), str) and record[field], f"missing {field}")
    if record['schema_version'] == 2:
        from core.integrity import fingerprint
        _require(record.get('layout_fingerprint') == fingerprint(record.get('layout')), 'layout fingerprint mismatch')
        _require(record.get('input_fingerprints', {}).get('catalogue') == fingerprint(record.get('catalogue')), 'catalogue fingerprint mismatch')
        _require(record.get('input_fingerprints', {}).get('shoppers') == fingerprint([s['customer'] for s in record.get('shoppers',[])]), 'shopper fingerprint mismatch')
        ids = [p['id'] for p in record['catalogue']]
        _require(len(ids) == len(set(ids)), 'duplicate catalogue ID')
    config = record.get("config")
    _require(isinstance(config, dict) and config.get("mode") in {"actions", "proposals"},
             "invalid run configuration")
    from core.shopping import LEGACY_SHOPPING, SIMPLE_SHOPPING, SHOPPING_RULES
    rules = config.get('shopping_rules', LEGACY_SHOPPING)
    _require(rules in SHOPPING_RULES, 'unknown shopping rules')
    from core.navigation import MODEL_ONLY, ASSISTED, POLICIES
    policy = config.get('navigation_policy', MODEL_ONLY)
    _require(policy in POLICIES, 'unknown navigation policy')
    _require(policy not in ASSISTED or not config.get('action_planning'),
             'assisted navigation requires one model action per request')
    _require(config.get('decision_mode') != 'single_action' or not config.get('action_planning'),
             'single-action study cannot contain action planning')
    for field in ("turn_budget", "max_rounds", "concurrency"):
        _require(_int(config.get(field), 1), f"invalid {field}")
    planning = config.get('action_planning', {})
    if 'action_limit' in planning:
        shopper_count = len(record.get('shoppers') or ())
        _require(_int(planning['action_limit'], 1) and planning['action_limit'] <= config['turn_budget']
                 and _int(planning.get('requested_max_rounds'), 1)
                 and planning['action_limit'] == min(config['turn_budget'], planning['requested_max_rounds'])
                 and config['max_rounds'] in {
                     planning['requested_max_rounds'] * 8,
                     planning['requested_max_rounds'] * 8 * max(1, shopper_count),
                 },
                 'invalid plan action/scheduling limits')
    if 'action_limit' in config:
        _require(_int(config['action_limit'], 1) and config['action_limit'] <= config['turn_budget'],
                 'invalid action limit')
    _require(isinstance(record.get("layout"), dict)
             and isinstance(record["layout"].get("id"), str), "missing layout snapshot")
    _require(isinstance(record.get("catalogue"), list), "missing catalogue")
    shoppers = record.get("shoppers")
    _require(isinstance(shoppers, list) and shoppers, "missing initial shoppers")
    ids = set()
    for shopper in shoppers:
        _require(isinstance(shopper, dict) and isinstance(shopper.get("agent_id"), str), "invalid shopper")
        _require(shopper["agent_id"] not in ids, "duplicate shopper ID")
        ids.add(shopper["agent_id"])
        _state(shopper.get("state"))
        _require(shopper["state"]["turns_used"] == 0, "run must start with unused turns")
        _require(shopper["state"]["turn_budget"] == config["turn_budget"], "inconsistent turn budget")
        customer = shopper.get("customer")
        _require(isinstance(customer, dict) and customer.get("customer_id") == shopper["agent_id"],
                 "missing customer snapshot")
        _items(customer.get("shopping_list"))
        if rules == SIMPLE_SHOPPING:
            requested = customer['shopping_list']
            _require(len({item['product_id'] for item in requested}) == len(requested)
                     and all(item['quantity'] == 1 for item in requested), 'unique shopping requires one unit per target')
            cart = shopper['state']['cart']
            _require(len({item['product_id'] for item in cart}) == len(cart)
                     and all(item['quantity'] == 1 for item in cart), 'unique shopping cannot start with duplicate items')
            _require(shopper['state']['phase'] != 'CheckoutState', 'single checkout has no intermediate phase')


def _event(record, start, events, states):
    _fields(record, ("sequence", "round", "agent_id", "before", "after", "prompt",
                     "raw_response", "action", "outcome", "failure"))
    _require(record.get("type") == "decision", "expected decision or run_end")
    _require(type(record.get("sequence")) is int and record["sequence"] == len(events) + 1,
             "decision sequence is not contiguous")
    _require(_int(record.get("round"), 1)
             and record["round"] <= start["config"]["max_rounds"], "invalid round")
    if events:
        _require(record["round"] >= events[-1]["round"], "rounds are out of order")
    agent_id = record.get("agent_id")
    _require(isinstance(agent_id, str) and agent_id in states, "unknown shopper ID")
    _state(record.get("before"))
    _state(record.get("after"))
    _require(record["before"] == states[agent_id], "before-state does not match recorded history")
    before, after = record["before"], record["after"]
    _require(before['turns_used'] < _action_limit(start),
             'shopper exceeded the recorded action limit')
    _require(before["phase"] != "FinishedState" and before["turns_used"] < before["turn_budget"],
             "finished or exhausted shopper received a decision")
    _require(before["allowed_steps"], "decision has no allowed actions")
    _require(after["turn_budget"] == before["turn_budget"], "turn budget changed")
    if start['schema_version'] == 2:
        width,height = start['layout']['width'],start['layout']['height']
        _require(0 <= after['x'] < width and 0 <= after['y'] < height, 'position outside recorded store')
    outcome = record.get("outcome")
    _require(isinstance(outcome, str) and outcome in OUTCOMES, "unknown decision outcome")
    _require(isinstance(record.get("prompt"), str), "missing prompt")
    _require(record.get("raw_response") is None or isinstance(record["raw_response"], str),
             "invalid raw response")
    _require(record.get("failure") is None or isinstance(record["failure"], str), "invalid failure")
    if "telemetry" in record:
        telemetry = record["telemetry"]
        _require(isinstance(telemetry, dict), "invalid telemetry")
        latency = telemetry.get("provider_latency_ms")
        _require(type(latency) in (int, float) and math.isfinite(latency) and latency >= 0,
                 "invalid provider latency")
        for field in ("prompt_bytes", "response_bytes"):
            _require(_int(telemetry.get(field)), f"invalid {field}")
    _require(bool(record["failure"]) if outcome in FAILURES else record["failure"] is None,
             "failure message contradicts outcome")
    action = record.get("action")
    if outcome in {"applied", "proposed", "grid_rejected"}:
        _require(isinstance(action, dict) and isinstance(action.get("step"), str)
                 and action["step"] in before["allowed_steps"]
                 and isinstance(action.get("reason"), str)
                 and isinstance(action.get("product_id"), str), "invalid action")
    else:
        _require(action is None, "failed proposal cannot contain a valid action")
    applying = start["config"]["mode"] == "actions"
    _require(after["turns_used"] == before["turns_used"] + int(applying), "invalid turn consumption")
    _require(outcome != "proposed" if applying else outcome not in {"applied", "grid_rejected"},
             "outcome incompatible with run mode")
    if not applying or outcome in {"invalid_decision", "provider_exception", "grid_rejected"}:
        _require({k: v for k, v in before.items() if k != "turns_used"}
                 == {k: v for k, v in after.items() if k != "turns_used"},
                 "failed or proposal-only action mutated state")
    if start['schema_version'] == 2 and outcome == 'applied':
        from core.accounting import resolve_product
        action_step = action['step']
        if action_step in MOVEMENT:
            deltas = {'move_left':(-1,0),'move_right':(1,0),'move_up':(0,-1),'move_down':(0,1)}
            dx,dy = deltas[action_step]
            _require(after['x'] == before['x']+dx and after['y'] == before['y']+dy
                     and after['cart'] == before['cart'] and after['phase'] == before['phase'], 'movement contradicts action')
            blocked={(s['x']+x,s['y']+y) for s in start['layout']['shelves'] for x,y in s['offsets']}
            _require((after['x'],after['y']) not in blocked, 'movement enters shelf')
        else:
            _require((before['x'],before['y']) == (after['x'],after['y']), 'purchase/checkout changed position')
        if action_step == 'grab':
            p=resolve_product({'product_id':action['product_id']},start['catalogue'])
            _require(p is not None, 'purchase product absent from catalogue')
            if start['config'].get('shopping_rules') == 'unique_single_checkout_v1':
                _require(not any(item['product_id'] == p['id'] for item in before['cart']), 'unique shopping cannot grab a duplicate')
            _require(len(after['cart']) == len(before['cart'])+1 and after['cart'][:-1] == before['cart']
                     and after['cart'][-1]['product_id'] == p['id'] and after['cart'][-1]['quantity'] == 1, 'purchase contradicts cart')
            shelf_matches=[s for s in start['layout']['shelves'] if any(v['id']==p['id'] for v in s['products'])]
            _require(any(min(abs(before['x']-(s['x']+x))+abs(before['y']-(s['y']+y)) for x,y in s['offsets'])==1 for s in shelf_matches),'purchase is not reachable')
        if action_step == 'checkout':
            transitions = ({'BrowsingState': 'FinishedState'} if start['config'].get('shopping_rules') == 'unique_single_checkout_v1'
                           else {'BrowsingState':'CheckoutState','CheckoutState':'FinishedState'})
            expected_phase=transitions.get(before['phase'])
            _require(after['phase'] == expected_phase and before['cart'] and after['cart']==before['cart'], 'invalid checkout transition')
            _require(before['phase']=='CheckoutState' or [before['x'],before['y']] in [list(c) for c in start['layout']['checkout']], 'checkout away from register')
        if action_step == 'remove':
            from collections import Counter
            quantities=lambda cart:Counter({pid:sum(i['quantity'] for i in cart if i['product_id']==pid) for pid in {i['product_id'] for i in cart}})
            expected=quantities(before['cart']);expected[action['product_id']]-=1
            _require(expected[action['product_id']]>=0 and +expected==quantities(after['cart']), 'removal contradicts cart')
    # Independent commits: at most one event per shopper per scheduler tick.
    if events and record["round"] == events[-1]["round"]:
        seen = {event["agent_id"] for event in events if event["round"] == record["round"]}
        _require(agent_id not in seen, "duplicate shopper commit")
    _plan_provenance(record, events)
    _navigation_provenance(record, start, events)


def _navigation_provenance(record, start, events):
    from agents.base import Decision
    from agents.schema import parse_decision, is_valid_decision
    from core.navigation import ASSISTED, MODEL_ONLY, adjusted_action, recorded_visits
    navigation = record.get('telemetry', {}).get('navigation')
    policy = start['config'].get('navigation_policy', MODEL_ONLY)
    enabled = policy in ASSISTED
    if not enabled or start['config']['mode'] != 'actions' or record['action'] is None:
        _require(navigation is None, 'unexpected navigation adjustment')
        return
    _require(isinstance(navigation, dict) and navigation.get('policy') == policy,
             'missing navigation provenance')
    proposed = navigation.get('proposed_action')
    _require(isinstance(proposed, dict) and set(proposed) == {'step', 'product_id', 'reason'}
             and isinstance(proposed['product_id'], str), 'invalid original navigation proposal')
    proposal = Decision(proposed['step'], proposed['product_id'] or None, proposed['reason'])
    _require(is_valid_decision(proposal, record['before']['allowed_steps']), 'invalid original navigation proposal')
    if record['raw_response'] is not None:
        _require(parse_decision(record['raw_response'], record['before']['allowed_steps']) == proposal,
                 'navigation proposal differs from model response')
    expected, adjustment = adjusted_action(proposal, record['before'], start['layout'],
                                          recorded_visits(start, events, record['agent_id']),
                                          policy,start['config'].get('action_limit'))
    _require(record['action'] == expected.to_dict() and navigation.get('adjustment') == adjustment,
             'navigation adjustment contradicts recorded history')


def _plan_provenance(record, events):
    """A continued action must be traceable to the same saved model response."""
    telemetry = record.get('telemetry', {})
    source = telemetry.get('decision_source')
    if source not in ('model_plan', 'model_plan_continuation'):
        return
    index, length = telemetry.get('plan_action_index'), telemetry.get('plan_length')
    _require(_int(index) and _int(length, 1) and index < length <= 8, 'invalid model plan index')
    _require(isinstance(telemetry.get('plan_id'), str) and telemetry['plan_id'], 'missing model plan ID')
    if source == 'model_plan':
        _require(index == 0, 'model plan must start at its first action')
    else:
        _require(telemetry.get('request_submitted') is False
                 and telemetry.get('estimated_cost_micros') == 0
                 and not telemetry.get('usage') and not telemetry.get('reserved_micros'),
                 'continued action cannot claim another request or cost')
        previous = next((e for e in reversed(events) if e['agent_id'] == record['agent_id']), None)
        prior = previous.get('telemetry', {}) if previous else {}
        _require(previous and prior.get('plan_id') == telemetry['plan_id']
                 and prior.get('plan_action_index') == index-1
                 and prior.get('plan_length') == length
                 and prior.get('source_request_id') == telemetry.get('source_request_id')
                 and not prior.get('plan_interrupted') and previous['outcome'] == 'applied'
                 and previous['prompt'] == record['prompt']
                 and previous['raw_response'] == record['raw_response'], 'continued action lost its model plan source')
    if record['action'] is not None:
        try:
            plan = json.loads(record['raw_response'])
            actions = plan['actions']
            _require(len(actions) == length and record['action'] == {
                **actions[index], 'reason': plan['reason']}, 'action differs from saved model plan')
        except (ValueError, TypeError, KeyError, IndexError) as error:
            raise RunLogError('invalid saved model plan') from error


def _end(record, start, events, states):
    _fields(record, ("status", "error", "rounds_completed", "shoppers", "summary"))
    _require(record.get("status") in ({"completed", "aborted", "cancelled", "budget_exhausted"} if start["schema_version"] == 2 else {"completed", "aborted"}), "invalid terminal status")
    _require(record["error"] is None if record["status"] == "completed"
             else isinstance(record["error"], str) and bool(record["error"]), "invalid terminal error")
    rounds = record.get("rounds_completed")
    _require(_int(rounds) and rounds <= start["config"]["max_rounds"], "invalid completed round count")
    if events:
        _require(rounds >= events[-1]["round"] - int(record["status"] != "completed"),
                 "completed round count contradicts events")
    shoppers = record.get("shoppers")
    _require(isinstance(shoppers, list), "missing final shoppers")
    _require([s.get("agent_id") for s in shoppers if isinstance(s, dict)]
             == [s["agent_id"] for s in start["shoppers"]], "final shopper IDs changed")
    for shopper in shoppers:
        _state(shopper.get("state"))
        _require(shopper["state"] == states[shopper["agent_id"]], "final state contradicts history")
        state = shopper["state"]
        if (record["status"] == "completed" and state["phase"] != "FinishedState"
                and state["turns_used"] < min(state["turn_budget"], _action_limit(start))
                and state["allowed_steps"]):
            _require(rounds == start["config"]["max_rounds"], "active shopper stopped before round limit")
    expected = summarize(start, events, shoppers, record["status"])
    _require(record.get("summary") == expected, "saved summary contradicts recorded history")
    return expected


def read_run(path):
    """Read and validate a log; only a truncated final JSON line is recoverable."""
    start, end = None, None
    events, warnings, states = [], [], {}
    # JSONL records are separated by LF, not by Unicode text separators such as
    # U+2028, which are legal inside a JSON string. Decode each record separately
    # so an interrupted multibyte character cannot hide earlier valid records.
    opener = gzip.open if Path(path).suffix == ".gz" else open
    with opener(path, "rb") as handle:
        lines = handle.readlines()
    for number, raw_line in enumerate(lines, 1):
        try:
            partial_tail = (number == len(lines) and not raw_line.endswith(b"\n")
                            and raw_line.lstrip().startswith(b"{"))
            try:
                line = raw_line.decode("utf-8")
            except UnicodeDecodeError as error:
                if partial_tail and error.reason == "unexpected end of data" and error.end == len(raw_line):
                    warnings.append(f"Line {number}: truncated final record ignored")
                    break
                raise RunLogError("invalid UTF-8") from error
            try:
                record = json.loads(line, parse_constant=_reject_constant)
            except json.JSONDecodeError as error:
                if partial_tail:
                    warnings.append(f"Line {number}: truncated final record ignored")
                    break
                raise RunLogError("invalid JSON") from error
            _require(isinstance(record, dict), "record must be an object")
            _require(end is None, "record follows run_end")
            if start is None:
                _start(record)
                start = record
                states = {s["agent_id"]: s["state"] for s in start["shoppers"]}
            elif record.get("type") == "run_end":
                _end(record, start, events, states)
                end = record
            else:
                _event(record, start, events, states)
                events.append(record)
                states[record["agent_id"]] = record["after"]
        except (RunLogError, TypeError, KeyError, AttributeError) as error:
            raise RunLogError(f"Line {number}: {error}") from error
    _require(start is not None, "missing run_start")
    if end is None:
        warnings.append("Incomplete run: no run_end record")
    final = [{"agent_id": s["agent_id"], "state": states[s["agent_id"]]} for s in start["shoppers"]]
    summary = summarize(start, events, final, end["status"] if end else "incomplete")
    return {"start": start, "events": events, "end": end, "summary": summary, "warnings": warnings}


def _reject_constant(value):
    raise RunLogError(f"non-finite JSON value: {value}")
