"""Continue one interrupted MLX run in a new immutable, source-linked recording."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter

SIMULATION_DIR = Path(__file__).resolve().parents[1]
if str(SIMULATION_DIR) not in sys.path:
    sys.path.insert(0, str(SIMULATION_DIR))

from core.config import DECISION_RUNS_DIR
from core.grid import build_store
from core.run_log import read_run
from core.session import SimulationSession
from evaluation import dashboard, study
from evaluation.benchmark import instantiate_benchmark
from evaluation.recover_mlx_state import recover


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(source, directory, output):
    """Verify the entire prefix and serving contract before creating a record."""
    source, directory, output = map(Path, (source, directory, output))
    protocol = study.load_protocol(directory)
    run, grid, shoppers, visits = recover(source, protocol)
    header, events = run['start'], run['events']
    if not events or output.exists():
        raise ValueError('A recorded prefix and a new continuation path are required')
    experiment = header.get('experiment') or {}
    if experiment.get('study_id') != protocol['study_id'] or experiment.get('protocol_sha256') != protocol['sha256']:
        raise ValueError('Source is not part of the frozen study')
    arm = next(a for a in protocol['arms'] if a['arm_id'] == experiment['arm_id'])
    if study.controls(header) != study.expected(protocol, arm, experiment['repetition']):
        raise ValueError('Source differs from the frozen study')
    if study.template(protocol, arm, experiment['repetition']) != study.expected(protocol, arm, experiment['repetition']):
        raise ValueError('Engine, model, or serving identity changed; cannot faithfully continue')
    config = header['config']
    initial_grid = build_store(header['layout']['id'])
    initial_shoppers = instantiate_benchmark(protocol['benchmark'], protocol['cohort_size'], initial_grid,
        config['turn_budget'], config['shopping_rules'])
    continuation = {'stage': 'continuation', 'source_run_id': header['run_id'],
        'source_sha256': digest(source), 'source_event_count': len(events), 'source_study_id': protocol['study_id'],
        'note': 'Historical events replayed without inference; subsequent decisions continue the saved state.'}
    session = SimulationSession(header['layout']['id'], protocol['cohort_size'], config['action_limit'],
        config['turn_budget'], config['concurrency'], grid=initial_grid, shoppers=initial_shoppers,
        provider_name=header['provider'], model_name=header['model'], seed=config['seed'],
        navigation_policy=config['navigation_policy'], allow_action_plans=False,
        shopping_rules=config['shopping_rules'], prompt_variant=header['prompt_variant'],
        requests_per_minute=config.get('requests_per_minute', 0), output_path=output,
        ledger_path=DECISION_RUNS_DIR / 'gemini_campaign.sqlite3', experiment=continuation)
    if study.controls(session.header) != study.controls(header):
        session.finish('cancelled', 'Continuation controls mismatch before dispatch')
        raise ValueError('Continuation controls mismatch; no model request was dispatched')
    # The prior source is immutable. Copy its validated events into the new run,
    # then continue from physical state and prompt/visit histories reconstructed by core.
    for event in events:
        payload = {key: value for key, value in event.items() if key not in ('type', 'sequence', 'round')}
        session.writer.append(payload, event['round'])
    session.writer.flush()
    session.grid = grid
    last = events[-1]['agent_id']
    ids = [s.customer_id for s in shoppers]
    offset = (ids.index(last) + 1) % len(ids)
    order = {shopper.customer_id: index for index, shopper in enumerate(shoppers[offset:] + shoppers[:offset])}
    submit = session.coordinator._submit_due
    def submit_recovered(grid, active, apply_decisions, already_acted):
        # Restore the pending admission order once, while retaining the canonical
        # shopper order required by the final run record.
        session.coordinator._submit_due = submit
        return submit(grid, sorted(active, key=lambda shopper: order[shopper.customer_id]),
            apply_decisions, already_acted)
    session.shoppers = shoppers
    session.coordinator._submit_due = submit_recovered
    session.coordinator.visits = {id(s): visits[s.customer_id] for s in shoppers}
    session._ticks = events[-1]['round']
    session.rounds_completed = session._ticks
    session._started = perf_counter() - events[-1].get('elapsed_ms', 0) / 1000
    # Read back the prefix using the same validator that powers replay and Evidence.
    prefix = read_run(output)
    if prefix['events'] != events:
        session.finish('aborted', 'Continuation prefix verification failed')
        raise ValueError('Copied prefix differs from the saved source')
    return session


def execute(source, directory, output, public):
    session = prepare(source, directory, output)
    print(f'Continuing {session.run_id} from {len(session.writer.events)} recorded events', flush=True)
    try:
        session.run()
    finally:
        # A closed attempt can be published; the existing interrupted recording stays immutable.
        if session.closed:
            from core.export_replay import export_run
            export_run(output, public, allow_partial=session.status != 'completed')
            dashboard.publish(DECISION_RUNS_DIR, public, closed_only=True, closed_paths=[source])
            dashboard.verify(public)
    return session


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--public', type=Path, default=SIMULATION_DIR.parent / 'landing/public/replays')
    args = parser.parse_args()
    try:
        result = execute(args.source, args.directory, args.output, args.public)
        print(json.dumps({'run_id': result.run_id, 'status': result.status, 'summary': result.summary}), flush=True)
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(2, f'Continuation stopped: {error}\n')
