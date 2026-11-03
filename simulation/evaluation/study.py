"""Prepare, execute and report frozen layout/model studies. Prepare never calls a model."""
import argparse
import hashlib
import inspect
import json
import random
import sys
import uuid
from pathlib import Path
from statistics import mean

SIMULATION_DIR = Path(__file__).resolve().parents[1]
if str(SIMULATION_DIR) not in sys.path:
    sys.path.insert(0, str(SIMULATION_DIR))

from agents.openai_provider import MODEL, MODEL_PRICING, OpenAIProvider
from agents.providers import FakeDecisionProvider
from core.config import ACTIVE_LAYOUT_IDS, DECISION_RUNS_DIR
from core.evidence import METRICS, run_row
from core.export_replay import export_run
from core.grid import build_store
from core.integrity import fingerprint
from core.navigation import GARY2_CURRENT, MODEL_ONLY
from core.run_log import read_run
from core.session import SimulationSession, build_run_start
from core.shopping import SIMPLE_SHOPPING
from evaluation.benchmark import load_benchmark, instantiate_benchmark
from evaluation.run import bootstrap, save_json

BENCHMARK = SIMULATION_DIR / 'benchmarks/two_layouts_15_v2.json'
KINDS = ('layout', 'model', 'assistance')


def provider_spec(name):
    if name=='openrouter':
        from agents.openrouter_provider import OpenRouterProvider, MODEL_PRICING as prices
        return OpenRouterProvider, prices
    if name=='openai':return OpenAIProvider, MODEL_PRICING
    if name=='fake':return FakeDecisionProvider, {}
    raise ValueError('Unsupported study provider')


def metric_definitions(provider):
    if provider!='openrouter':return METRICS
    return {**METRICS,'provider_reported_cost_usd':('OpenRouter-reported charges · run','usd'),
        'provider_reported_cost_per_checkout_usd':('OpenRouter-reported charge per checkout','usd')}


def controls(header):
    """Exact per-arm contract, including frozen model pricing and initial states."""
    return json.loads(json.dumps({key: header.get(key) for key in ('provider', 'model', 'prompt_version', 'config',
        'layout', 'catalogue', 'shoppers', 'engine_fingerprint', 'provider_fingerprint', 'pricing')}))


def template(protocol, arm, repetition):
    grid = build_store(arm['layout_id'])
    shoppers = instantiate_benchmark(protocol['benchmark'], protocol['cohort_size'], grid, protocol['turn_budget'], protocol['shopping_rules'])
    provider, prices = provider_spec(protocol['provider'])
    header = build_run_start(grid, shoppers, run_id='prepared-not-started', provider=protocol['provider'],
        model=arm['model'], max_rounds=protocol['turn_budget'] * protocol['cohort_size'],
        concurrency=protocol['concurrency'], propose_only=False, prompt_variant='informed',
        seed=protocol['seed'] + repetition, requests_per_minute=protocol['requests_per_minute'],
        generation_settings=(provider.settings_for_model(arm['model']) if hasattr(provider,'settings_for_model') else
            provider.generation_settings) if protocol['provider'] != 'fake' else {'decision_source': 'explicit_fixture'},
        pricing=prices[arm['model']] if protocol['provider'] != 'fake' else None,
        navigation_policy=arm['policy'],shopping_rules=protocol['shopping_rules'])
    header['config'].update(api_budget_enforced=False, decision_mode='single_action', action_limit=protocol['turn_budget'])
    header['provider_fingerprint'] = hashlib.sha256(Path(inspect.getsourcefile(provider)).read_bytes()).hexdigest()
    return controls(header)


def prepare(directory, *, kind='layout', models=None, layout=ACTIVE_LAYOUT_IDS[0], policy=GARY2_CURRENT,
            shoppers=10, repetitions=5, turn_budget=120, concurrency=2, seed=42, provider='openai', requests_per_minute=0):
    if kind not in KINDS or provider not in ('openai', 'openrouter', 'fake'):
        raise ValueError('Unsupported study kind or provider')
    if any(type(v) is not int for v in (shoppers, repetitions, turn_budget, concurrency, seed, requests_per_minute)):
        raise ValueError('Study settings must be integers')
    if not 10 <= shoppers <= 15 or not 1 <= repetitions <= 50 or not 1 <= turn_budget <= 120 or not 1 <= concurrency <= 15 or requests_per_minute < 0:
        raise ValueError('Invalid study settings')
    if layout not in ACTIVE_LAYOUT_IDS or policy not in (GARY2_CURRENT, MODEL_ONLY):
        raise ValueError('Unsupported layout or policy')
    models = list(models or ([MODEL, 'gpt-6.1-terra'] if kind == 'model' else [MODEL]))
    if provider == 'fake':
        models = ['fake']  # Explicit engineering fixture; never label fake behavior as a model.
        if kind == 'model':
            raise ValueError('A fake provider cannot compare real model performance')
    if len(models) != (2 if kind == 'model' else 1) or len(set(models)) != len(models):
        raise ValueError('Model comparisons need two distinct models; other studies need one')
    if provider != 'fake' and any(model not in provider_spec(provider)[1] for model in models):
        raise ValueError('Unsupported model')
    variants = ([(name, models[0], policy) for name in ACTIVE_LAYOUT_IDS] if kind == 'layout' else
                [(layout, model, policy) for model in models] if kind == 'model' else
                [(layout, models[0], name) for name in (MODEL_ONLY, GARY2_CURRENT)])
    arms = [{'arm_id': f'arm-{n}', 'layout_id': name, 'model': model, 'policy': nav,
             'label': name if kind == 'layout' else model if kind == 'model' else nav}
            for n, (name, model, nav) in enumerate(variants)]
    protocol = {'study_version': 1, 'study_id': uuid.uuid4().hex, 'kind': kind, 'provider': provider,
        'cohort_size': shoppers, 'repetitions': repetitions, 'turn_budget': turn_budget,
        'concurrency': concurrency, 'seed': seed, 'requests_per_minute': requests_per_minute,
        'benchmark': load_benchmark(BENCHMARK), 'arms': arms,
        'primary_metrics': ['checkout_completion', 'purchased_unit_fulfillment', 'mean_successful_moves'],
        'api_budget_enforced': False,
        'shopping_rules': SIMPLE_SHOPPING,
        'interpretation': 'Compare simulated outcomes conditional on this frozen cohort. No prediction of real customers or retail revenue.'}
    protocol['contracts'] = {arm['arm_id']: template(protocol, arm, 1) for arm in arms}
    schedule = []
    for repetition in range(1, repetitions + 1):
        order = list(arms); random.Random(seed + repetition).shuffle(order)
        schedule.extend({'arm_id': arm['arm_id'], 'repetition': repetition} for arm in order)
    protocol['schedule'] = schedule
    protocol['sha256'] = fingerprint(protocol)
    directory = Path(directory); directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'protocol.json').open('x') as handle:
        json.dump(protocol, handle, indent=2, allow_nan=False)
    return protocol


def load_protocol(directory):
    protocol = json.loads((Path(directory) / 'protocol.json').read_text())
    if protocol.get('study_version') != 1 or fingerprint({k: v for k, v in protocol.items() if k != 'sha256'}) != protocol.get('sha256'):
        raise ValueError('Study protocol integrity mismatch')
    return protocol


def expected(protocol, arm, repetition):
    contract = json.loads(json.dumps(protocol['contracts'][arm['arm_id']]))
    contract['config']['seed'] = protocol['seed'] + repetition
    return contract


def slot_path(directory, slot):
    return Path(directory) / f"repeat-{slot['repetition']:02d}-{slot['arm_id']}.jsonl"


def aggregate_metrics(rows, definitions=METRICS):
    metrics = {}
    for metric in definitions:
        values = [row['metrics'][metric] for row in rows]
        if metric in ('known_estimated_cost_usd', 'cost_per_completed_trip_usd') and any(not row['cost_complete'] for row in rows):
            values = []
        metrics[metric] = mean(values) if values and all(value is not None for value in values) else None
    # Pool the numerator and denominator. Averaging per-run ratios would discard
    # zero-checkout runs or overweight runs with fewer completed shoppers.
    finished = sum(row['finished_count'] for row in rows)
    costs = [row['metrics']['known_estimated_cost_usd'] for row in rows]
    metrics['cost_per_completed_trip_usd'] = (sum(costs) / finished if finished and costs
        and all(row['cost_complete'] for row in rows) and all(value is not None for value in costs) else None)
    if 'provider_reported_cost_per_checkout_usd' in definitions:
        charges=[row['metrics']['provider_reported_cost_usd'] for row in rows]
        metrics['provider_reported_cost_per_checkout_usd']=(sum(charges)/finished
            if finished and charges and all(n is not None for n in charges) else None)
    return metrics


def report(directory):
    directory = Path(directory); protocol = load_protocol(directory)
    definitions=metric_definitions(protocol['provider'])
    retained = []; missing = []; slots = {}; versions = {}
    for slot in protocol['schedule']:
        path = slot_path(directory, slot)
        if not path.is_file():
            missing.append(path.name); continue
        run = read_run(path); header = run['start']
        arm = next(a for a in protocol['arms'] if a['arm_id'] == slot['arm_id'])
        experiment = {'study_id': protocol['study_id'], 'stage': 'main', 'arm_id': arm['arm_id'],
                      'repetition': slot['repetition'], 'protocol_sha256': protocol['sha256']}
        if controls(header) != expected(protocol, arm, slot['repetition']) or header.get('experiment') != experiment:
            raise ValueError(f'Saved run differs from frozen study: {path.name}')
        row = run_row(path)
        observed = set(row['model_versions'])
        if protocol['provider'] in ('openai','openrouter'):
            responses = [e for e in run['events'] if e['outcome'] != 'provider_exception']
            if any(not e.get('telemetry', {}).get('model_version') for e in responses):
                raise ValueError('Returned decisions lack actual model version evidence')
            versions.setdefault(arm['model'], set()).update(observed)
            if len(versions[arm['model']]) > 1:
                raise ValueError('Actual model version drift within the frozen study')
        retained.append({**row, 'arm_id': arm['arm_id'], 'repetition': slot['repetition'],
            'file': path.name, 'summary': run['summary']})
        if row['status'] == 'completed' and not row['warnings']:
            slots[(arm['arm_id'], slot['repetition'])] = row
    ids = [row['run_id'] for row in retained]
    if len(ids) != len(set(ids)):
        raise ValueError('Study contains duplicate run identities')
    arms = []
    for arm in protocol['arms']:
        own = [row for row in retained if row['arm_id'] == arm['arm_id']]
        arms.append({**arm, 'layout_id': arm['arm_id'], 'store_layout_id': arm['layout_id'],
            'completed_runs': sum(row['status'] == 'completed' and not row['warnings'] for row in own),
            'recorded_runs': len(own), 'metrics': aggregate_metrics(own,definitions)})
    left, right = protocol['arms']; paired = []
    blocks = [(slots[(left['arm_id'], n)], slots[(right['arm_id'], n)])
              for n in range(1, protocol['repetitions'] + 1)
              if (left['arm_id'], n) in slots and (right['arm_id'], n) in slots]
    for key in definitions:
        differences = []
        for a, b in blocks:
            if key in ('known_estimated_cost_usd', 'cost_per_completed_trip_usd') and not (a['cost_complete'] and b['cost_complete']):
                continue
            first, second = a['metrics'][key], b['metrics'][key]
            if first is not None and second is not None:
                differences.append(second - first)
        paired.append({'comparison': f"{right['arm_id']} minus {left['arm_id']}", 'metric': key,
            'mean_difference': mean(differences) if differences else None, 'ci95': bootstrap(differences),
            'blocks': len(differences), 'missing_blocks': protocol['repetitions'] - len(differences),
            'status': 'assessed' if differences else 'unassessed'})
    complete = len(slots) == len(protocol['schedule']) and not missing
    result = {'report_version': 1, 'study_kind': protocol['kind'], 'study_id': protocol['study_id'],
        'protocol_sha256': protocol['sha256'], 'status': 'completed' if complete else 'pilot_or_incomplete',
        'cohort_size': protocol['cohort_size'], 'repetitions': protocol['repetitions'], 'provider': protocol['provider'],
        'metric_definitions': {key: {'label': label, 'unit': unit} for key, (label, unit) in definitions.items()},
        'arms': arms, 'paired': paired, 'runs': retained, 'missing_evidence': missing,
        'limitations': [protocol['interpretation'],
            'Arm means include all retained attempts, including stopped runs and unfinished shoppers. Paired differences use only intact completed run pairs; missing pairs stay counted.',
            'Completed run means the configured action window ended; it does not mean every shopper checked out.',
            'Fewer than five paired repetitions provide descriptive differences without a confidence interval. Five is a starting point, not a power calculation.',
            '95% intervals use 10,000 repetition-block bootstrap samples, conditional on this fixed derived cohort. Actions and shoppers within a run are not independent repetitions.',
            'OpenAI request seeds are unsupported. The frozen seed controls run pairing and order, not deterministic model output.',
            'Both arms request exactly one model decision per action. Model-only and assisted runs are separate policies; report the assistance count.',
            'Shopper budgets are soft preferences; overspending and off-list purchases are measured rather than blocked.',
            'Unknown API costs remain unknown. Arm cost per checkout pools all retained run costs divided by all completed checkouts, including costs of failed and unfinished trips; other arm metrics are run means.',
            'Inventory is replenished; movement is independent; crowd blocking and checkout queues are not modeled.']}
    save_json(directory / 'report.json', result)
    return result


def execute(directory, *, max_new_runs=None):
    if max_new_runs is not None and (type(max_new_runs) is not int or max_new_runs < 1):
        raise ValueError('max_new_runs must be a positive integer')
    directory = Path(directory); protocol = load_protocol(directory)
    # Check every arm before dispatching anything. Code/data changes require a new study.
    for arm in protocol['arms']:
        if template(protocol, arm, 1) != expected(protocol, arm, 1):
            raise ValueError('Code or inputs changed since preparation; prepare a new study directory')
    report(directory)  # Validate all retained evidence before admitting a new request.
    added = 0
    try:
        for slot in protocol['schedule']:
            path = slot_path(directory, slot)
            if path.exists():
                run = read_run(path)
                if run['summary']['status'] != 'completed' or run['warnings']:
                    raise ValueError('Stopped attempt retained; no automatic retry. Inspect it and prepare a separate replacement study.')
                continue
            arm = next(a for a in protocol['arms'] if a['arm_id'] == slot['arm_id'])
            grid = build_store(arm['layout_id'])
            shoppers = instantiate_benchmark(protocol['benchmark'], protocol['cohort_size'], grid, protocol['turn_budget'], protocol['shopping_rules'])
            session = SimulationSession(arm['layout_id'], protocol['cohort_size'], protocol['turn_budget'],
                protocol['turn_budget'], protocol['concurrency'], grid=grid, shoppers=shoppers,
                decide=FakeDecisionProvider() if protocol['provider'] == 'fake' else None,
                provider_name=protocol['provider'], model_name=arm['model'] if protocol['provider'] != 'fake' else None,
                seed=protocol['seed'] + slot['repetition'], navigation_policy=arm['policy'],
                allow_action_plans=False, shopping_rules=protocol['shopping_rules'], output_path=path, ledger_path=DECISION_RUNS_DIR / 'gemini_campaign.sqlite3',
                requests_per_minute=protocol['requests_per_minute'],
                experiment={'study_id': protocol['study_id'], 'stage': 'main', 'arm_id': arm['arm_id'],
                    'repetition': slot['repetition'], 'protocol_sha256': protocol['sha256']})
            if controls(session.header) != expected(protocol, arm, slot['repetition']):
                session.finish('cancelled', 'Frozen study controls mismatch before dispatch')
                raise ValueError('Session differs from prepared controls; no model request was dispatched')
            print(f"Repeat {slot['repetition']} / {arm['label']} / {session.run_id}", flush=True)
            session.run()
            if session.status != 'completed':
                raise RuntimeError('Study stopped; partial outcomes retained. Inspect report.json before a replacement study.')
            added += 1
            if max_new_runs is not None and added >= max_new_runs:
                break
    finally:
        report(directory)
    return report(directory)


def publish(directory, destination, allow_test=False):
    directory = Path(directory); destination = Path(destination)
    result = report(directory)
    if result['provider'] == 'fake' and not allow_test:
        raise ValueError('Offline test reports need explicit --allow-test; they do not establish model performance')
    destination.mkdir(parents=True, exist_ok=True)
    for row in result['runs']:
        export_run(directory / row['file'], destination, allow_test=allow_test, allow_partial=row['status'] != 'completed')
    protocol_name = f"study-{result['study_id']}.protocol.json"
    save_json(destination / protocol_name, load_protocol(directory))
    result['protocol_url'] = '/replays/' + protocol_name
    name = f"study-{result['study_id']}.json"; save_json(destination / name, result)
    index_path = destination / 'index.json'
    index = json.loads(index_path.read_text()) if index_path.exists() else {'schema_version': 1, 'runs': [], 'reports': []}
    entry = {'url': '/replays/' + name, 'title': f"{result['study_kind']} · {result['provider']} · {result['status']} · {result['study_id'][:8]}",
             'sha256': hashlib.sha256((destination / name).read_bytes()).hexdigest()}
    index['reports'] = [row for row in index.get('reports', []) if row['url'] != entry['url']] + [entry]
    save_json(index_path, index)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'run', 'report', 'publish'))
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--kind', choices=KINDS, default='layout')
    parser.add_argument('--models', nargs='+')
    parser.add_argument('--layout', choices=ACTIVE_LAYOUT_IDS, default=ACTIVE_LAYOUT_IDS[0])
    parser.add_argument('--policy', choices=(GARY2_CURRENT, MODEL_ONLY), default=GARY2_CURRENT)
    parser.add_argument('--provider', choices=('openai', 'openrouter', 'fake'), default='openai')
    parser.add_argument('--shoppers', type=int, default=10)
    parser.add_argument('--repetitions', type=int, default=5)
    parser.add_argument('--turn-budget', type=int, default=120)
    parser.add_argument('--concurrency', type=int, default=2)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--requests-per-minute', type=int, default=0)
    parser.add_argument('--destination', type=Path, default=SIMULATION_DIR.parent / 'landing/public/replays')
    parser.add_argument('--allow-test', action='store_true')
    parser.add_argument('--max-new-runs', type=int, help='Run at most this many new slots, then retain the study for resumption')
    args = parser.parse_args(argv)
    if args.command != 'prepare' and len(sys.argv if argv is None else argv) > 0:
        supplied = sys.argv[1:] if argv is None else argv
        forbidden = {option.split('=')[0] for option in supplied if option.startswith('--')} - {'--directory', '--destination', '--allow-test', '--max-new-runs'}
        if forbidden:
            parser.error('Execution/reporting use frozen protocol settings; configuration flags apply only to prepare')
    if args.max_new_runs is not None and args.command != 'run':
        parser.error('--max-new-runs applies only to execution')
    try:
        if args.command == 'prepare':
            value = prepare(args.directory, kind=args.kind, models=args.models, layout=args.layout, policy=args.policy,
                shoppers=args.shoppers, repetitions=args.repetitions, turn_budget=args.turn_budget,
                concurrency=args.concurrency, seed=args.seed, provider=args.provider, requests_per_minute=args.requests_per_minute)
            print(f"Prepared {value['kind']} study {value['study_id']}. No model calls or run records created.")
        elif args.command == 'run':
            print(execute(args.directory, max_new_runs=args.max_new_runs)['status'])
        elif args.command == 'report':
            print(report(args.directory)['status'])
        else:
            print(publish(args.directory, args.destination, args.allow_test)['status'])
    except (ValueError, RuntimeError, OSError) as error:
        parser.exit(2, f'Study stopped: {error}\n')


if __name__ == '__main__':
    main()
