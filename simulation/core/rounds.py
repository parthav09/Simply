from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from agents.base import Decision, DecisionSnapshot, ProposalResult, RoundOutcome
from agents.llm import MissingGeminiApiKeyError
from agents.state import FinishedState


def unpack_decision_result(result):
    if isinstance(result, ProposalResult):
        return result.decision, result.raw_response
    if isinstance(result, Decision):
        return result, None
    return None, None


class RoundCoordinator:
    def __init__(self, decide, max_workers=4):
        if isinstance(max_workers, bool) or not isinstance(max_workers, int) or max_workers < 1:
            raise ValueError("max_workers must be a positive integer")
        self.decide = decide
        self.max_workers = max_workers

    def run(self, grid, shoppers, apply_decisions=True):
        snapshots = []
        for shopper in shoppers:
            if isinstance(shopper.state, FinishedState) or shopper.out_of_turns:
                continue
            observation = grid.observe(shopper)
            if not observation.allowed_steps:
                continue
            snapshots.append((
                shopper,
                DecisionSnapshot(
                    prompt=shopper.prompt(observation),
                    allowed_steps=tuple(observation.allowed_steps),
                ),
            ))

        results = []
        fatal_error = None
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                (
                    shopper,
                    snapshot,
                    executor.submit(self.decide, snapshot.prompt, snapshot.allowed_steps),
                )
                for shopper, snapshot in snapshots
            ]
            for shopper, snapshot, future in futures:
                try:
                    decision_result = future.result()
                except MissingGeminiApiKeyError as error:
                    fatal_error = fatal_error or error
                    results.append((shopper, snapshot, None, None, error))
                except Exception as error:
                    results.append((shopper, snapshot, None, None, error))
                else:
                    decision, raw_response = unpack_decision_result(decision_result)
                    results.append((shopper, snapshot, decision, raw_response, None))

        if fatal_error is not None:
            raise fatal_error

        outcomes = []
        for shopper, snapshot, decision, raw_response, error in results:
            if apply_decisions:
                shopper.consume_turn()
            if error is not None:
                outcomes.append(RoundOutcome(
                    shopper.customer_id,
                    failure=str(error),
                    raw_response=raw_response,
                ))
            elif not isinstance(decision, Decision) or decision.step not in snapshot.allowed_steps:
                outcomes.append(RoundOutcome(
                    shopper.customer_id,
                    failure="invalid decision",
                    raw_response=raw_response,
                ))
            else:
                outcomes.append(RoundOutcome(
                    shopper.customer_id,
                    decision=decision,
                    raw_response=raw_response,
                ))
        committed = []
        for (shopper, _), outcome in zip(snapshots, outcomes):
            if outcome.decision is None or not apply_decisions:
                shopper.record_decision_outcome(outcome)
                committed.append(outcome)
                continue
            outcome = replace(
                outcome,
                applied=grid.apply(shopper, outcome.decision),
            )
            shopper.record_decision_outcome(outcome)
            committed.append(outcome)
        return tuple(committed)
