"""Reconstruct an interrupted run using recorded actions, without inference."""
import argparse
from pathlib import Path
import sys

SIMULATION_DIR = Path(__file__).resolve().parents[1]
if str(SIMULATION_DIR) not in sys.path:
    sys.path.insert(0, str(SIMULATION_DIR))

from agents.base import Decision, RoundOutcome
from core.grid import build_store
from core.navigation import recorded_visits
from core.rounds import state_snapshot
from core.run_log import read_run
from core.shopping import SIMPLE_SHOPPING, configure_shopper
from evaluation.benchmark import instantiate_benchmark
from evaluation.study import load_protocol


def recover(path, protocol):
    run = read_run(path)
    header, events = run['start'], run['events']
    if run['end'] is not None or header['model'] != 'qwen2.5-7b-pilot-mlx':
        raise ValueError('Expected an interrupted MLX pilot recording')
    if header['config']['concurrency'] != 1 or header['config']['shopping_rules'] != SIMPLE_SHOPPING:
        raise ValueError('Unsupported continuation settings')
    grid = build_store(header['layout']['id'])
    shoppers = instantiate_benchmark(protocol['benchmark'], protocol['cohort_size'], grid,
        header['config']['turn_budget'], SIMPLE_SHOPPING)
    by_id = {s.customer_id: s for s in shoppers}
    for shopper in shoppers:
        shopper._grid = grid
        shopper.prompt_variant = header['prompt_variant']
        shopper._action_limit = header['config']['action_limit']
        configure_shopper(shopper, SIMPLE_SHOPPING, grid)
    for event in events:
        shopper = by_id[event['agent_id']]
        observation = grid.observe(shopper)
        if state_snapshot(shopper, observation) != event['before']:
            raise ValueError(f"State mismatch at event {event['sequence']}")
        if shopper.prompt(observation) != event['prompt']:
            raise ValueError(f"Prompt history mismatch at event {event['sequence']}")
        if not shopper.consume_turn():
            raise ValueError('Recorded action exceeds turn budget')
        action = event['action']
        decision = Decision(action['step'], action['product_id'] or None, action['reason']) if action else None
        applied = grid.apply(shopper, decision) if decision else None
        if applied != ({'applied': True, 'grid_rejected': False}.get(event['outcome'])):
            raise ValueError(f"Action result mismatch at event {event['sequence']}")
        shopper.record_decision_outcome(RoundOutcome(shopper.customer_id, decision=decision,
            failure=event['failure'], applied=applied, raw_response=event['raw_response']))
        if state_snapshot(shopper, grid.observe(shopper)) != event['after']:
            raise ValueError(f"Result state mismatch at event {event['sequence']}")
    visits = {s.customer_id: recorded_visits(header, events, s.customer_id) for s in shoppers}
    return run, grid, shoppers, visits


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--recording', type=Path, required=True)
    args = parser.parse_args()
    run, _, shoppers, visits = recover(args.recording, load_protocol(args.directory))
    print(f"Verified {len(run['events'])} events and {len(shoppers)} shopper states; no inference requested.")
