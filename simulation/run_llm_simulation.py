"""Run complete Gemini-driven shopper trips from the terminal."""

import argparse
import sys
from pathlib import Path

SIMULATION_DIR = Path(__file__).resolve().parent
if str(SIMULATION_DIR) not in sys.path:
    sys.path.insert(0, str(SIMULATION_DIR))

from agents.state import FinishedState
from agents.llm import MissingGeminiApiKeyError, decide_prompt_with_gemini
from core.customers import instantiate_agents
from core.grid import build_store
from core.rounds import RoundCoordinator


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def run(
    layout_name,
    shopper_count,
    max_rounds,
    turn_budget=120,
    concurrency=4,
    propose_only=False,
):
    grid = build_store(layout_name)
    shoppers = grid.spawn(
        instantiate_agents(count=shopper_count, turn_budget=turn_budget)
    )
    coordinator = RoundCoordinator(
        decide_prompt_with_gemini,
        max_workers=concurrency,
    )
    rounds_run = 0

    for round_number in range(1, max_rounds + 1):
        active = [
            shopper
            for shopper in shoppers
            if not isinstance(shopper.state, FinishedState) and not shopper.out_of_turns
        ]
        if not active:
            break
        rounds_run = round_number
        mode = "proposals" if propose_only else "decisions"
        print(f"Round {round_number}: requesting {mode} for {len(active)} active shoppers")
        outcomes = coordinator.run(grid, active, apply_decisions=not propose_only)
        for outcome in outcomes:
            if outcome.failure:
                print(f"  {outcome.shopper_id}: failed ({outcome.failure})")
            elif propose_only:
                print(
                    f"  {outcome.shopper_id}: proposed {outcome.decision.step} "
                    f"({outcome.decision.reason})"
                )
            else:
                result = "applied" if outcome.applied else "not applied"
                print(f"  {outcome.shopper_id}: {outcome.decision.step} {result}")

    finished = sum(isinstance(s.state, FinishedState) for s in shoppers)
    exhausted = sum(shopper.out_of_turns for shopper in shoppers)
    print(
        f"Finished {finished}/{len(shoppers)} shoppers after {rounds_run} rounds. "
        f"Turn budgets exhausted: {exhausted}."
    )
    if rounds_run == max_rounds and finished + exhausted < len(shoppers):
        print("Stopped at the global --max-rounds safety limit.")
    for shopper in shoppers:
        cart_size = len(shopper.state.cart)
        print(
            f"{shopper.customer_id} {shopper.name}: "
            f"{type(shopper.state).__name__}, {cart_size} cart items, "
            f"{shopper.turns_used}/{shopper.turn_budget} turns"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--layout", default="costco_back_anchor")
    parser.add_argument("--shoppers", type=positive_int, default=1)
    parser.add_argument("--turn-budget", type=positive_int, default=120)
    parser.add_argument("--max-rounds", type=positive_int, default=120)
    parser.add_argument("--concurrency", type=positive_int, default=4)
    parser.add_argument(
        "--propose-only",
        action="store_true",
        help="Record validated LLM proposals without applying them to the grid.",
    )
    args = parser.parse_args()
    try:
        run(
            args.layout,
            args.shoppers,
            args.max_rounds,
            turn_budget=args.turn_budget,
            concurrency=args.concurrency,
            propose_only=args.propose_only,
        )
    except MissingGeminiApiKeyError as error:
        print(f"Gemini configuration error: {error}", file=sys.stderr)
        raise SystemExit(2)
