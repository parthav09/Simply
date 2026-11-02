"""Independent shopper commits: apply each ready decision without waiting for peers."""

import atexit
from collections import Counter
from concurrent.futures import ALL_COMPLETED, FIRST_COMPLETED, ThreadPoolExecutor, wait as wait_futures
from dataclasses import dataclass, replace
from time import perf_counter

from agents.base import Decision, DecisionSnapshot, ProposalResult, RoundOutcome
from agents.base import MissingProviderApiKeyError
from agents.schema import MAX_PLAN_ACTIONS, is_valid_decision
from agents.state import FinishedState
from agents.steps import MOVES, STEP_DESCRIPTIONS
from core.decision_log import observation_to_dict
from core.budget import BudgetExhaustedError
from core.perception import grabbable_product_ids
from core.navigation import MODEL_ONLY, ASSISTED, POLICIES, adjusted_action


@dataclass(frozen=True)
class PendingPlan:
    actions: tuple
    prompt: str
    raw_response: str | None
    expected_state: dict
    plan_id: str
    index: int
    length: int
    source_request_id: str | None


@dataclass
class InFlight:
    shopper: object
    future: object
    snapshot: DecisionSnapshot
    before: dict
    use_plan: bool


def state_snapshot(shopper, observation):
    """Detach mutable state now, before another action can change it."""
    return {
        **observation_to_dict(observation),
        "turns_used": shopper.turns_used,
        "turn_budget": shopper.turn_budget,
    }


def unpack_decision_result(result):
    if isinstance(result, ProposalResult):
        return result.decision, result.raw_response
    if isinstance(result, Decision):
        return result, None
    return None, None


class RoundCoordinator:
    def __init__(self, decide, max_workers=4, navigation_policy=MODEL_ONLY, layout=None, action_limit=None, allow_action_plans=True):
        if isinstance(max_workers, bool) or not isinstance(max_workers, int) or max_workers < 1:
            raise ValueError("max_workers must be a positive integer")
        self.decide = decide
        if navigation_policy not in POLICIES or (navigation_policy in ASSISTED and layout is None):
            raise ValueError('Invalid navigation policy or missing frozen layout')
        self.navigation_policy = navigation_policy
        self.layout = layout
        self.action_limit = action_limit
        self.allow_action_plans = allow_action_plans
        self.visits = {}
        self.max_workers = max_workers
        self.pending_plans = {}
        self.in_flight = {}
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._closed = False
        atexit.register(self.close)

    def close(self):
        if self._closed:
            return
        self._closed = True
        self.executor.shutdown(wait=False, cancel_futures=True)

    def settle(self, grid, apply_decisions=True, event_callback=None):
        """Apply already-submitted work without starting new requests."""
        started = perf_counter()
        committed = []
        while self.in_flight:
            committed.extend(self._resolve(grid, apply_decisions, event_callback, started, block=True))
        return tuple(committed)

    def uses_plans(self, shopper):
        return (self.allow_action_plans and self.navigation_policy == MODEL_ONLY and getattr(self.decide, 'supports_action_plans', False)
                and getattr(shopper, 'prompt_variant', 'baseline') == 'informed')

    def request(self, shopper, payload):
        snapshot, use_plan = payload
        started = perf_counter()
        try:
            method = self.decide.request_plan if use_plan else getattr(self.decide, 'request', None)
            result = (method(snapshot.prompt, snapshot.allowed_steps, shopper_id=shopper.customer_id)
                      if method else self.decide(snapshot.prompt, snapshot.allowed_steps))
            metadata = result.telemetry or {} if isinstance(result, ProposalResult) else {}
            return result, (perf_counter()-started)*1000, None, metadata
        except Exception as error:
            metadata = getattr(error, 'telemetry', {'request_submitted': False} if isinstance(error, BudgetExhaustedError) else {})
            return None, (perf_counter()-started)*1000, error, metadata

    def run(self, grid, shoppers, apply_decisions=True, event_callback=None):
        """Compatibility wave: every participating shopper acts once, independently."""
        return self.tick(grid, shoppers, apply_decisions, event_callback, wait_all=True)

    def tick(self, grid, shoppers, apply_decisions=True, event_callback=None, wait_all=False):
        """Gary-2 style pump: apply ready work, submit idle shoppers, do not block on peers."""
        if self._closed:
            return ()
        started = perf_counter()
        committed = []
        acted = set()
        for shopper in shoppers:
            if id(shopper) in self.in_flight:
                continue
            outcome = self._apply_cached_plan(grid, shopper, apply_decisions, event_callback, started)
            if outcome is not None:
                committed.append(outcome)
                acted.add(id(shopper))
        self._submit_due(grid, shoppers, apply_decisions, acted)
        if wait_all and self.in_flight:
            wait_futures([flight.future for flight in self.in_flight.values()], return_when=ALL_COMPLETED)
            committed.extend(self._resolve(grid, apply_decisions, event_callback, started, block=False))
        elif self.in_flight:
            committed.extend(self._resolve(grid, apply_decisions, event_callback, started, block=not committed))
        return tuple(committed)

    def _submit_due(self, grid, shoppers, apply_decisions, already_acted):
        for shopper in shoppers:
            key = id(shopper)
            if key in self.in_flight or key in already_acted or key in self.pending_plans:
                continue
            if isinstance(shopper.state, FinishedState) or shopper.out_of_turns:
                continue
            observation = grid.observe(shopper)
            self.visits.setdefault(key, Counter({(observation.x, observation.y): 1}))
            if not observation.allowed_steps:
                continue
            use_plan = self.uses_plans(shopper)
            snapshot = DecisionSnapshot(
                prompt=shopper.prompt(observation, action_plan=use_plan),
                allowed_steps=tuple(observation.allowed_steps),
            )
            future = self.executor.submit(self.request, shopper, (snapshot, use_plan))
            self.in_flight[key] = InFlight(
                shopper, future, snapshot, state_snapshot(shopper, observation), use_plan)

    def _apply_cached_plan(self, grid, shopper, apply_decisions, event_callback, started):
        if isinstance(shopper.state, FinishedState) or shopper.out_of_turns:
            self.pending_plans.pop(id(shopper), None)
            return None
        observation = grid.observe(shopper)
        if not observation.allowed_steps:
            return None
        before = state_snapshot(shopper, observation)
        pending = self.pending_plans.get(id(shopper))
        if not apply_decisions or not pending:
            return None
        if pending.expected_state != before:
            self.pending_plans.pop(id(shopper), None)
            return None
        self.pending_plans.pop(id(shopper))
        snapshot = DecisionSnapshot(prompt=pending.prompt, allowed_steps=tuple(observation.allowed_steps))
        result = ProposalResult(pending.raw_response, pending.actions[0], {
            'request_submitted': False, 'estimated_cost_micros': 0,
            'plan_id': pending.plan_id, 'plan_action_index': pending.index,
            'plan_length': pending.length, 'source_request_id': pending.source_request_id,
            'decision_source': 'model_plan_continuation',
        }, continuation=pending.actions[1:])
        return self._commit(
            grid, shopper, snapshot, before, result, 0.0, None, result.telemetry,
            apply_decisions, event_callback, started, from_plan=True)

    def _resolve(self, grid, apply_decisions, event_callback, started, block):
        if not self.in_flight:
            return []
        futures = [flight.future for flight in self.in_flight.values()]
        if block and not any(future.done() for future in futures):
            wait_futures(futures, return_when=FIRST_COMPLETED)
        committed = []
        completed = [flight for flight in list(self.in_flight.values()) if flight.future.done()]
        try:
            for flight in completed:
                self.in_flight.pop(id(flight.shopper), None)
                result, latency_ms, error, metadata = flight.future.result()
                if isinstance(error, MissingProviderApiKeyError):
                    for pending in self.in_flight.values():
                        pending.future.result()
                    self.in_flight.clear()
                    raise error
                committed.append(self._commit(
                    grid, flight.shopper, flight.snapshot, flight.before, result, latency_ms, error, metadata,
                    apply_decisions, event_callback, started, from_plan=False))
        except BaseException:
            if hasattr(self.decide, 'cancelled'):
                self.decide.cancelled.set()
            for flight in self.in_flight.values():
                flight.future.cancel()
            raise
        return committed

    def _commit(self, grid, shopper, snapshot, before, result, latency_ms, error, metadata,
                apply_decisions, event_callback, started, from_plan):
        decision, raw_response = unpack_decision_result(result)
        continuation = result.continuation if isinstance(result, ProposalResult) else ()
        valid_tail = (isinstance(continuation, tuple) and len(continuation) < MAX_PLAN_ACTIONS
                      and all(is_valid_decision(d, STEP_DESCRIPTIONS) for d in continuation)
                      and ((self.navigation_policy == MODEL_ONLY and self.allow_action_plans) or not continuation))
        if self.uses_plans(shopper) and isinstance(result, ProposalResult) and not from_plan:
            metadata = {**metadata, 'plan_id': f'{shopper.customer_id}:{shopper.turns_used+1}',
                        'plan_action_index': 0, 'plan_length': 1+len(continuation) if valid_tail else 1,
                        'source_request_id': metadata.get('request_id'),
                        'decision_source': 'model_plan'}
        if error is not None:
            outcome = RoundOutcome(shopper.customer_id, failure=str(error) or type(error).__name__, raw_response=raw_response)
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
            outcome = replace(outcome, applied=applied, failure=None if applied else "action rejected by grid")
            if applied and self.navigation_policy in ASSISTED:
                self.visits[id(shopper)][shopper.state.x, shopper.state.y] += 1
        shopper.record_decision_outcome(outcome)
        after = state_snapshot(shopper, grid.observe(shopper))
        if valid_tail and continuation and apply_decisions and outcome.applied:
            stop = None
            if isinstance(shopper.state, FinishedState) or shopper.out_of_turns:
                stop = 'finished_or_turn_limit'
            elif decision.step in MOVES:
                dx, dy = MOVES[decision.step]
                old_visible = grabbable_product_ids(grid, shopper.state.x-dx, shopper.state.y-dy)
                if grabbable_product_ids(grid, shopper.state.x, shopper.state.y) - old_visible:
                    stop = 'new_grabbable_products'
            if stop:
                metadata = {**metadata, 'plan_interrupted': stop}
            else:
                self.pending_plans[id(shopper)] = PendingPlan(
                    continuation, snapshot.prompt, raw_response, after,
                    metadata.get('plan_id', f'{shopper.customer_id}:{shopper.turns_used}'),
                    metadata.get('plan_action_index', 0)+1,
                    metadata.get('plan_length', 1+len(continuation)),
                    metadata.get('source_request_id', metadata.get('request_id')))
        elif continuation and apply_decisions:
            metadata = {**metadata, 'plan_interrupted': 'action_failed'}
        if event_callback is not None:
            status = ("provider_exception" if error is not None else
                      "invalid_decision" if outcome.decision is None else
                      "proposed" if not apply_decisions else
                      "applied" if outcome.applied else "grid_rejected")
            event_callback({
                "agent_id": shopper.customer_id, "before": before,
                "prompt": snapshot.prompt, "raw_response": outcome.raw_response,
                "action": outcome.decision.to_dict() if outcome.decision else None,
                "outcome": status, "failure": outcome.failure,
                "telemetry": {**metadata, "provider_latency_ms": latency_ms,
                    "round_provider_wait_ms": (perf_counter()-started)*1000,
                    "round_wait_complete": not self.in_flight,
                    "prompt_bytes": len(snapshot.prompt.encode("utf-8")),
                    "response_bytes": len((outcome.raw_response or "").encode("utf-8"))},
                "after": after,
            })
        return outcome
