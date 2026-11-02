"""Frozen 2-layout x 2-model evaluation, using canonical study sessions throughout."""
import argparse
import hashlib
import json
import random
import os
import shutil
import sys
import tempfile
import uuid
from collections import Counter
from pathlib import Path
from statistics import mean

SIMULATION_DIR = Path(__file__).resolve().parents[1]
if str(SIMULATION_DIR) not in sys.path:
    sys.path.insert(0, str(SIMULATION_DIR))

from core.evidence import METRICS
from core.integrity import fingerprint
from core.run_log import read_run
from core.shopping import SIMPLE_SHOPPING
from evaluation import study
from evaluation.run import bootstrap, save_json


def prepare(directory, *, repetitions=5, concurrency=5, requests_per_minute=90, seed=20261029, provider='openai'):
    directory = Path(directory)
    if directory.exists():
        raise FileExistsError('Choose a new matrix directory; existing evidence is immutable')
    directory.mkdir(parents=True)
    children = []
    for index, model in enumerate(('gpt-6-luna', 'gpt-6.1-terra')):
        name = f'model-{index}'
        protocol = study.prepare(directory / name, kind='layout', models=[model],
            repetitions=repetitions, concurrency=concurrency, requests_per_minute=requests_per_minute, seed=seed, provider=provider)
        children.append({'directory': name, 'model': model, 'sha256': protocol['sha256']})
    # Interleave models within each repetition. Each child's frozen layout order
    # is preserved; no model is measured exclusively before the other model.
    schedule = []
    for repetition in range(1, repetitions + 1):
        pending = {child['directory']: 2 for child in children}
        rng = random.Random(seed + repetition)
        while any(pending.values()):
            name = rng.choice([key for key, value in pending.items() if value])
            child_protocol = study.load_protocol(directory / name)
            slot = [s for s in child_protocol['schedule'] if s['repetition'] == repetition][2-pending[name]]
            schedule.append({'directory': name, **slot})
            pending[name] -= 1
    plan = {'matrix_version': 1, 'study_id': uuid.uuid4().hex, 'children': children,
        'schedule': schedule, 'repetitions': repetitions, 'cohort_size': 10, 'provider':provider,
        'primary_metrics': ['checkout_completion', 'purchased_unit_fulfillment', 'mean_successful_moves'],
        'scope': 'Development benchmark: assisted system performance, not unassisted model intelligence or real retail impact.',
        'comparisons': 'Layout B minus A within each model; Terra minus Luna within each layout. All four comparisons declared before execution.'}
    if provider=='openrouter':
        plan['pending_models']=[{'model':'Qwen/Qwen3-4B-Instruct-2507','status':'pending',
            'reason':'Exact checkpoint absent from OpenRouter catalogue; user requested leaving it pending. No substitute or inference run.'},
            {'model':'Fine-tuned Qwen','status':'pending','reason':'User will fine-tune later. No trained model or results available.'}]
    plan['sha256'] = fingerprint(plan)
    save_json(directory / 'matrix.json', plan)
    load(directory)
    return plan


def load(directory):
    directory = Path(directory)
    plan = json.loads((directory / 'matrix.json').read_text())
    if plan.get('matrix_version') != 1 or fingerprint({k:v for k,v in plan.items() if k != 'sha256'}) != plan.get('sha256'):
        raise ValueError('Matrix integrity mismatch')
    protocols = []
    for child in plan['children']:
        if child['directory'] not in ('model-0', 'model-1'):
            raise ValueError('Unsupported matrix child')
        protocol = study.load_protocol(directory / child['directory'])
        if protocol['sha256'] != child['sha256']:
            raise ValueError('Child protocol changed')
        if protocol['repetitions'] != plan['repetitions'] or protocol['cohort_size'] != plan['cohort_size'] or any(arm['model'] != child['model'] for arm in protocol['arms']):
            raise ValueError('Matrix metadata differs from frozen child protocols')
        protocols.append(protocol)
    if len(protocols) != 2 or len({p['arms'][0]['model'] for p in protocols}) != 2:
        raise ValueError('Matrix requires two distinct models')
    if any(p['provider']!=plan.get('provider',protocols[0]['provider']) for p in protocols):
        raise ValueError('Matrix providers differ from frozen plan')
    for left, right in zip(protocols[0]['arms'], protocols[1]['arms']):
        a = dict(protocols[0]['contracts'][left['arm_id']]); b = dict(protocols[1]['contracts'][right['arm_id']])
        # Prices must differ with the model; every other control must match.
        for contract in (a, b):
            contract.pop('model'); contract.pop('pricing')
        if a != b:
            raise ValueError('Matrix models have unmatched controls')
    expected = {(child['directory'], slot['arm_id'], slot['repetition'])
        for child, protocol in zip(plan['children'], protocols) for slot in protocol['schedule']}
    actual = [(s['directory'], s['arm_id'], s['repetition']) for s in plan['schedule']]
    if len(actual) != len(expected) or set(actual) != expected:
        raise ValueError('Matrix schedule omits or duplicates a slot')
    if [s['repetition'] for s in plan['schedule']] != sorted(s['repetition'] for s in plan['schedule']):
        raise ValueError('Matrix schedule breaks repetition blocks')
    for child, protocol in zip(plan['children'], protocols):
        if [{k:v for k,v in s.items() if k != 'directory'} for s in plan['schedule'] if s['directory'] == child['directory']] != protocol['schedule']:
            raise ValueError('Matrix schedule changes frozen child order')
    return plan, protocols


def audit(path):
    """Recompute primary counts from final carts/events independently of summaries."""
    run = read_run(path); header = run['start']; states = {s['agent_id']: s['state'] for s in header['shoppers']}
    if header['config'].get('shopping_rules') != SIMPLE_SHOPPING:
        raise ValueError('Independent matrix audit requires unique-product shopping rules')
    for event in run['events']:
        states[event['agent_id']] = event['after']
    requested = purchased = finished = moves = 0
    unfinished = []; missed = []; profiles = []
    for shopper in header['shoppers']:
        targets = {item['product_id'] for item in shopper['customer']['shopping_list']}
        state = states[shopper['agent_id']]; paid = state['phase'] == 'FinishedState'
        cart = {item['product_id'] for item in state['cart']}
        requested += len(targets); purchased += len(targets & cart) if paid else 0; finished += paid
        own = [e for e in run['events'] if e['agent_id'] == shopper['agent_id']]
        charges = [e.get('telemetry', {}).get('estimated_cost_micros') for e in own]
        submitted = [e.get('telemetry', {}).get('request_submitted') for e in own]
        profile = {'profile_id': shopper['customer']['customer_id'], 'agent_id': shopper['agent_id'],
            'profile_sha256': fingerprint(shopper['customer']),
            'requested_products': len(targets), 'purchased_products': len(targets & cart) if paid else 0,
            'metrics': {'checkout_completion': int(paid),
                'purchased_unit_fulfillment': len(targets & cart)/len(targets) if paid and targets else int(not targets),
                'mean_successful_moves': sum(e['outcome']=='applied' and e['action'] and e['action']['step'].startswith('move_') for e in own),
                'model_requests': sum(submitted) if all(type(n) is bool for n in submitted) else None,
                'estimated_cost_usd': sum(charges)/1e6 if all(type(n) is int for n in charges) else None}}
        profiles.append(profile)
        if targets-cart:
            missed.append({'agent_id':shopper['agent_id'], 'paid':paid, 'turns_used':state['turns_used'],
                'product_ids':sorted(targets-cart)})
        if not paid:
            unfinished.append({'agent_id':shopper['agent_id'], 'turns_used':state['turns_used'],
                'uncollected_targets':sorted(targets-cart), 'unpaid_cart_products':sorted(cart)})
    moves = sum(e['outcome'] == 'applied' and e['action'] and e['action']['step'].startswith('move_') for e in run['events'])
    summary = run['summary']; count = len(header['shoppers'])
    calculated = {'checkout_completion': finished/count, 'purchased_unit_fulfillment': purchased/requested if requested else 1,
                  'mean_successful_moves': moves/count}
    if any(abs(summary[key]-value) > 1e-12 for key, value in calculated.items()):
        raise ValueError('Independent primary-metric audit failed')
    examples = {}
    adjustments = Counter(); provider_codes = Counter()
    for event in run['events']:
        reason = event.get('telemetry',{}).get('navigation',{}).get('adjustment')
        if reason:
            adjustments[reason] += 1
        code=event.get('telemetry',{}).get('provider_error_code')
        if code:
            provider_codes[code] += 1
        if event['outcome'] != 'applied':
            examples.setdefault(event['outcome'], {'sequence':event['sequence'], 'agent_id':event['agent_id'],
                'outcome':event['outcome'], 'action':event['action'], 'failure':event['failure']})
    return {'finished': finished, 'shoppers': count, 'requested_unique_units': requested,
            'purchased_requested_units': purchased, 'successful_moves': moves,
            'unfinished':unfinished, 'missed_requested_products':missed,
            'failure_examples':list(examples.values()), 'adjustment_reasons':dict(adjustments),
            'provider_error_codes':dict(provider_codes), 'profiles':profiles}


def profile_pairs(blocks):
    """Pair by frozen profile identity within intact repetition blocks, never by outcome."""
    result = []
    for baseline, candidate in blocks:
        left = {p['profile_id']:p for p in baseline['audit']['profiles']}
        right = {p['profile_id']:p for p in candidate['audit']['profiles']}
        if len(left)!=baseline['audit']['shoppers'] or len(right)!=candidate['audit']['shoppers'] or left.keys()!=right.keys():
            raise ValueError('Paired profile identities differ')
        for profile_id in sorted(left):
            a, b = left[profile_id], right[profile_id]
            if a['profile_sha256']!=b['profile_sha256'] or a['requested_products']!=b['requested_products']:
                raise ValueError('Paired profile or shopping list differs')
            result.append({'profile_id':profile_id, 'repetition':baseline['repetition'],
                'baseline_run_id':baseline['run_id'], 'candidate_run_id':candidate['run_id'],
                'baseline':a['metrics'], 'candidate':b['metrics'],
                'difference':{key:b['metrics'][key]-a['metrics'][key]
                    if a['metrics'][key] is not None and b['metrics'][key] is not None else None for key in a['metrics']}})
    return result


def report(directory):
    directory = Path(directory); plan, protocols = load(directory)
    rows = []; child_reports = []
    for child, protocol in zip(plan['children'], protocols):
        result = study.report(directory / child['directory']); child_reports.append(result)
        for row in result['runs']:
            rows.append({**row, 'file': child['directory']+'/'+row['file'],
                'audit': audit(directory / child['directory'] / row['file'])})
    conditions = []
    for child, protocol in zip(plan['children'], protocols):
        for arm in protocol['arms']:
            own = [r for r in rows if r['model'] == arm['model'] and r['layout_id'] == arm['layout_id']]
            metrics = study.aggregate_metrics(own,study.metric_definitions(protocol['provider']))
            requests = sum(r['metrics']['model_requests'] for r in own) if own and all(r['metrics']['model_requests'] is not None for r in own) else None
            adjustments = sum(r['metrics']['navigation_adjustments'] for r in own)
            metrics['assisted_request_fraction'] = adjustments/requests if requests else None
            conditions.append({'model': arm['model'], 'layout_id': arm['layout_id'], 'policy': arm['policy'],
                'recorded_runs': len(own), 'metrics': metrics,
                'collection_note': ('Includes a run interrupted by exhausted API credits' if any('credit_balance_exhausted' in r['audit']['provider_error_codes'] for r in own)
                    else 'Includes a stopped run' if any(r['status']!='completed' for r in own) else ''),
                'finished': sum(r['audit']['finished'] for r in own), 'trips': sum(r['audit']['shoppers'] for r in own)})
    comparisons = []
    pairs = [(0,1), (2,3), (0,2), (1,3)]
    for left, right in pairs:
        a, b = conditions[left], conditions[right]
        blocks = []
        for repetition in range(1, plan['repetitions']+1):
            pair = [[r for r in rows if r['model'] == arm['model'] and r['layout_id'] == arm['layout_id']
                and r['repetition'] == repetition and r['status'] == 'completed' and not r['warnings']] for arm in (a,b)]
            if all(len(group) == 1 for group in pair):
                blocks.append((pair[0][0], pair[1][0]))
        metrics = {}
        for key in study.metric_definitions(protocols[0]['provider']):
            values = [y['metrics'][key]-x['metrics'][key] for x,y in blocks
                if x['metrics'][key] is not None and y['metrics'][key] is not None
                and (key not in ('known_estimated_cost_usd','cost_per_completed_trip_usd') or (x['cost_complete'] and y['cost_complete']))]
            metrics[key] = {'difference': mean(values) if values else None, 'ci95': bootstrap(values),
                'blocks': len(values), 'missing_blocks': plan['repetitions']-len(values)}
        comparisons.append({'baseline': {'model':a['model'],'layout_id':a['layout_id']},
            'candidate': {'model':b['model'],'layout_id':b['layout_id']}, 'metrics': metrics,
            'complete_repetitions':[x['repetition'] for x,y in blocks], 'profile_pairs':profile_pairs(blocks)})
    completed=sum(r['status']=='completed' and not r['warnings'] for r in rows)
    codes=Counter()
    for row in rows:
        codes.update(row['audit']['provider_error_codes'])
    collection={'planned_runs':len(plan['schedule']), 'recorded_runs':len(rows), 'completed_runs':completed,
        'stopped_runs':len(rows)-completed, 'missing_runs':len(plan['schedule'])-len(rows),
        'attempted_trips':sum(r['audit']['shoppers'] for r in rows),
        'completed_checkouts':sum(r['audit']['finished'] for r in rows), 'provider_error_codes':dict(codes)}
    collection['summary']=f"{completed} of {len(plan['schedule'])} runs completed; {collection['stopped_runs']} stopped and {collection['missing_runs']} not collected."
    if 'credit_balance_exhausted' in codes:
        collection['summary']+=' OpenAI reported exhausted API credits. The interrupted run remains included in arm averages; complete paired comparisons exclude that interrupted pair.'
    result = {'matrix_report_version': 2, 'study_id': plan['study_id'], 'protocol_sha256': plan['sha256'],
        'repetitions': plan['repetitions'], 'cohort_size': plan['cohort_size'],
        'collection':collection,
        'status': 'completed' if all(r['status'] == 'completed' for r in child_reports) else 'incomplete',
        'conditions': conditions, 'comparisons': comparisons, 'runs': rows,
        'limitations': [plan['scope'], f"The same {plan['cohort_size']} derived shopper profiles are repeated; the {len(plan['schedule'])*plan['cohort_size']} planned trips are not independent people.",
            '95% intervals resample complete repetition blocks and are conditional on this cohort; four planned contrasts are not multiplicity-adjusted.',
            'All shoppers and stopped attempts remain in arm totals. Paired contrasts use intact completed pairs only.',
            'Both models use gary2_v2 assistance and one model proposal per action; assistance counts must accompany model comparisons.',
            'Known costs use frozen price snapshots; missing charges remain unknown. Simulated checkout sales are not real revenue.']}
    if 'provider' in plan:
        result['provider']=plan['provider']
    if 'pending_models' in plan:
        result['pending_models']=plan['pending_models']
        result['limitations'].append('OpenRouter requests pin dated model slugs and the standard OpenAI endpoint, disable provider fallback and response-healing plugins, and record the actual serving model/provider. Token-price estimates and OpenRouter-reported charges are separate measurements; credit-purchase fees are excluded.')
    save_json(directory / 'matrix-report.json', result)
    write_summary(directory, result)
    return result


def write_summary(directory, result):
    """Keep claims next to their source paths; incomplete collection gets no resume claim."""
    rate_keys = {'checkout_completion','purchased_unit_fulfillment'}
    def display(key, value, difference=False):
        if value is None:
            return 'Unknown'
        if key in rate_keys:
            return f'{value*100:+.2f} pp' if difference else f'{value*100:.2f}%'
        if key.endswith('_usd'):
            return f'${value:.4f}'
        return f'{value:+.2f}' if difference else f'{value:.2f}'
    def label(row):
        return ('Luna' if row['model']=='gpt-6-luna' else 'Terra')+' / Layout '+('A' if row['layout_id']=='costco_back_anchor' else 'B')
    keys = ('checkout_completion','purchased_unit_fulfillment','mean_successful_moves')
    lines = ['# Simply: measured layout and model performance', '',
        f"Collection status: **{result['status']}**. Matrix `{result['study_id']}`. Protocol SHA-256 `{result['protocol_sha256']}`.", '',
        result['collection']['summary'], '',
        'Compare store placement and model choices through paid shopping outcomes, movement, failures, navigation assistance, and API cost. Preserve the evidence needed to distinguish a cheaper system from a better shopping result.', '',
        '## Results', '',
        '| Condition | Checkouts | Requested products purchased | Moves / shopper | API estimate / checkout | Assisted actions / run |',
        '|---|---:|---:|---:|---:|---:|']
    for row in result['conditions']:
        m=row['metrics']
        lines.append(f"| {label(row)} | {row['finished']}/{row['trips']} | {display(keys[1],m[keys[1]])} | {display(keys[2],m[keys[2]])} | {display('cost_per_completed_trip_usd',m['cost_per_completed_trip_usd'])} | {display('navigation_adjustments',m['navigation_adjustments'])} |")
    lines += ['', '## Paired changes', '',
        'Candidate minus baseline. Each cell shows the mean difference and its 95% repetition-block bootstrap interval. Five blocks provide only a small estimate of variability; these are not independent population samples.', '',
        '| Comparison | Checkout completion | Purchased-list fulfillment | Moves / shopper |', '|---|---:|---:|---:|']
    for comparison in result['comparisons']:
        cells=[]
        for key in keys:
            metric=comparison['metrics'][key]
            bounds=' to '.join(display(key,n,True) for n in metric['ci95']) if metric['ci95'] else 'interval unavailable'
            cells.append(f"{display(key,metric['difference'],True)} ({bounds}; {metric['blocks']} pairs)")
        lines.append('| '+label(comparison['candidate'])+' − '+label(comparison['baseline'])+' | '+' | '.join(cells)+' |')
    lines += ['', '## Per-profile comparisons', '',
        'The Evidence page plots paid-list fulfillment against successful movement for every retained trip in the selected repetition, including interrupted attempts. Points can overlap; select a profile to inspect exact values and source recordings.', '',
        'Paired difference charts match the same frozen customer profile and shopping list within a completed repetition block. A completed run may contain unfinished shoppers; they remain in its pairs with zero paid fulfillment. An interrupted run stays visible in the outcome chart but its block is excluded from paired differences. No profile-level p-values are calculated: repeated profiles and actions are not independent experimental repetitions.', '',
        'The result JSON stores each independently audited profile under `runs[].audit.profiles` and each matched observation under `comparisons[].profile_pairs`. API requests count submitted requests, excluding queued cancellations. Trip API estimates sum event charges; any missing charge makes that trip estimate and its paired cost difference unknown. These are per-attempt costs, not cost per completed checkout.', '']
    lines += ['', '## Failures and assistance', '',
        '| Condition | Requests | Invalid replies | Rejected actions | Provider failures | Adjusted proposals | Unknown usage |',
        '|---|---:|---:|---:|---:|---:|---:|']
    diagnostic_keys = ('model_requests','invalid_decision_count','grid_rejection_count','provider_failure_count','navigation_adjustments','unknown_usage_requests')
    for condition in result['conditions']:
        own=[row for row in result['runs'] if row['model']==condition['model'] and row['layout_id']==condition['layout_id']]
        cells=[str(sum(row['metrics'][key] for row in own)) if own and all(row['metrics'][key] is not None for row in own) else 'Unknown' for key in diagnostic_keys]
        lines.append('| '+label(condition)+' | '+' | '.join(cells)+' |')
    lines += ['', 'Representative recorded failures (first example of each outcome in each run; not an exhaustive list of events):', '']
    for row in result['runs']:
        for example in row['audit'].get('failure_examples',[]):
            failure=str(example['failure']).replace('|','/').replace('\n',' ')[:220]
            lines.append(f"- {label(row)}, repeat {row['repetition']}, [{row['run_id'][:12]}]({row['file']}), event {example['sequence']}: `{example['outcome']}` — {failure}.")
        for shopper in row['audit'].get('unfinished',[]):
            lines.append(f"- Unfinished trip in [{row['run_id'][:12]}]({row['file']}): {shopper['agent_id']}, {shopper['turns_used']} actions, {len(shopper['uncollected_targets'])} requested products still uncollected, {len(shopper['unpaid_cart_products'])} products in an unpaid cart. Paid fulfillment counts this trip as zero.")
        for shopper in row['audit'].get('missed_requested_products',[]):
            if shopper['paid']:
                lines.append(f"- Incomplete shopping list at a paid checkout in [{row['run_id'][:12]}]({row['file']}): {shopper['agent_id']}, {shopper['turns_used']} actions, missing requested products {', '.join(shopper['product_ids'])}. Checkout success alone would hide this shortfall.")
    lines += ['', '## Scope and limitations', '']+[f'- {text}' for text in result['limitations']]
    lines += ['', '- Profiles/lists are derived feasible benchmark missions, not a sampled retail population. Layout A and B contain the same products and prices; placement changes.',
        '- Shopper budgets are soft preferences, unique products are limited to one unit, and payment finishes in one checkout action.',
        '- This comparison measures the complete assisted systems. It does not isolate the causal contribution of navigation assistance. No fine-tuned model or real-user deployment was evaluated.',
        '- The two complete-trip pilot recordings are separate from the main experiment and do not enter its averages or intervals.', '',
        '## Verify the result', '',
        'Open the Evidence page at `http://localhost:3000/evaluation`. The top summary reads Python-authored results. Expand individual recordings or controlled studies to inspect saved outcomes. Locally, these files contain the complete evidence:', '',
        '- [Frozen matrix plan](matrix.json): model/layout ordering and hashes of both child protocols.',
        '- [All metrics, contrasts, independent audits, and source hashes](matrix-report.json).',
        '- [Luna protocol](model-0/protocol.json) and [Luna repeated layout report](model-0/report.json).',
        '- [Terra protocol](model-1/protocol.json) and [Terra repeated layout report](model-1/report.json).', '',
        'The independent audit counts finished shoppers, requested unique products actually present in paid carts, and successful movement events. It checks every primary aggregate against the canonical Python summary. Each source below retains original proposals, applied actions, adjustments, API telemetry, and final state.', '',
        '| Source | Model / layout | Repeat | Status | Source SHA-256 |', '|---|---|---:|---|---|']
    for row in result['runs']:
        lines.append(f"| [{row['run_id'][:12]}]({row['file']}) | {label(row)} | {row['repetition']} | {row['status']} | `{row['source_sha256']}` |")
    lines += ['', '## Reproduce', '',
        'Reporting saved evidence makes no API requests. Running a fresh experiment uses the configured API and records its charges; model responses are stochastic, so a rerun need not reproduce identical outcomes.', '',
        '```bash',
        '# Reconstruct exported results from hashed source recordings; no API calls.',
        '.venv/bin/python -m simulation.evaluation.matrix verify --directory landing/public/replays',
        '# Reanalyse the original local study folder when available:',
        f'.venv/bin/python -m simulation.evaluation.matrix report --directory {directory.as_posix()}',
        '# Fresh collection: choose a new directory; existing evidence is never overwritten.',
        '.venv/bin/python -m simulation.evaluation.matrix prepare --directory simulation/runs/studies/new-matrix',
        '.venv/bin/python -m simulation.evaluation.matrix run --directory simulation/runs/studies/new-matrix',
        '.venv/bin/python -m simulation.evaluation.matrix publish --directory simulation/runs/studies/new-matrix',
        '```', '', '## Resume claims', '']
    if result['status'] == 'completed':
        trips=sum(row['trips'] for row in result['conditions'])
        lines += [f'- Built a Python/React LLM-agent simulation and evaluation harness; benchmarked two models across two store layouts in {len(result["runs"])} frozen runs ({trips} simulated trips), tracking checkout success, purchased-list fulfillment, failures, navigation assistance, and API cost.',
            '- Implemented auditable action records, live SSE viewing, deterministic replay, and independent checks of primary outcome metrics; reported paired differences with repetition-block bootstrap intervals.']
    else:
        lines += ['Collection is incomplete. These findings are exploratory; do not claim the planned 200 trips, five completed repetitions, statistical significance, or a general layout improvement.', '',
            f"- Built a Python/React LLM-agent simulation and evaluation harness with live SSE, validated action records, deterministic replay, and frozen layout/model comparisons; collected {result['collection']['attempted_trips']} attempted simulated trips and retained provider-interrupted outcomes."]
    lines += ['', '## Next MLE evidence', '',
        'Use a separate held-out shopper/mission/layout split for the future base-versus-fine-tuned open-weight model comparison. Keep original proposals separate from assisted actions. This experiment adds evaluation evidence; training ownership, production adoption, and real shopper validity remain separate work.', '',
        'Gary-2 inspired the navigation and recording workflow. Simply contributes its own browser SSE/replay bridge, validation contracts, and controlled evaluation implementation.', '']
    (directory / 'case-study.md').write_text('\n'.join(lines))


def execute(directory):
    directory = Path(directory); plan, _ = load(directory)
    report(directory)
    pending = False
    for slot in plan['schedule']:
        path = study.slot_path(directory / slot['directory'], slot)
        if not path.exists():
            pending = True
        elif pending:
            raise ValueError('Out-of-order matrix attempt retained; no new requests admitted')
    for index, slot in enumerate(plan['schedule']):
        path = study.slot_path(directory / slot['directory'], slot)
        if path.exists():
            run = read_run(path)
            if run['summary']['status'] != 'completed' or run['warnings']:
                raise ValueError('Stopped or out-of-order matrix attempt retained; no automatic retry')
            continue
        # Resume the immutable child schedule by exactly one canonical session.
        print(f"Matrix slot {index+1}/{len(plan['schedule'])}", flush=True)
        try:
            study.execute(directory / slot['directory'], max_new_runs=1)
        finally:
            report(directory)
        if not path.exists():
            raise ValueError('Child execution did not fill the expected slot')
    return report(directory)


def verify_export(directory):
    """Rebuild a published result from its hashed sources. No model or writable ledger."""
    directory = Path(directory)
    index = json.loads((directory/'index.json').read_text()); entry = index['matrix']
    def local(url):
        if not isinstance(url,str) or not url.startswith('/replays/') or Path(url).name != url.removeprefix('/replays/'):
            raise ValueError('Unsafe published source link')
        return directory / Path(url).name
    result_path=local(entry['url'])
    if hashlib.sha256(result_path.read_bytes()).hexdigest() != entry['sha256']:
        raise ValueError('Published matrix integrity mismatch')
    saved=json.loads(result_path.read_text()); plan=json.loads(local(entry['protocol_url']).read_text())
    if plan['sha256'] != saved['protocol_sha256']:
        raise ValueError('Published protocol identity mismatch')
    with tempfile.TemporaryDirectory(prefix='simply-verify-matrix-') as temp:
        root=Path(temp); save_json(root/'matrix.json',plan)
        protocols=[]
        for child in plan['children']:
            candidates=[json.loads(path.read_text()) for path in directory.glob('study-*.protocol.json')]
            matches=[p for p in candidates if p.get('sha256')==child['sha256']]
            if len(matches)!=1 or child['directory'] not in ('model-0','model-1'):
                raise ValueError('Missing or ambiguous frozen child protocol')
            child_root=root/child['directory']; child_root.mkdir()
            save_json(child_root/'protocol.json',matches[0]); protocols.append(matches[0])
        load(root)  # Validate protocol hashes and matched controls before source admission.
        allowed={child['directory']+'/'+study.slot_path(Path('.'),slot).name
            for child,protocol in zip(plan['children'],protocols) for slot in protocol['schedule']}
        for row in saved['runs']:
            if row['file'] not in allowed:
                raise ValueError('Published run does not belong to the frozen schedule')
            source=local(saved.get('source_urls',{}).get(row['run_id'],f"/replays/{row['run_id']}.source.jsonl"))
            if hashlib.sha256(source.read_bytes()).hexdigest()!=row['source_sha256']:
                raise ValueError('Published recording integrity mismatch')
            target=root/row['file']
            if target.exists():
                raise ValueError('Duplicate published source slot')
            try:
                os.link(source,target)
            except OSError:
                with source.open('rb') as incoming, target.open('xb') as outgoing:
                    shutil.copyfileobj(incoming,outgoing)
        rebuilt=report(root)
        for key in ('matrix_report_version','study_id','protocol_sha256','status','repetitions','cohort_size','collection','conditions','comparisons','runs','provider','pending_models'):
            if rebuilt.get(key)!=saved.get(key):
                raise ValueError(f'Published result differs from source reconstruction: {key}')
    return {'verified_runs':len(saved['runs']), 'study_id':saved['study_id'], 'api_calls':0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare','run','report','publish','verify'))
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--provider',choices=('openai','openrouter'),default='openai')
    parser.add_argument('--repetitions',type=int,default=5)
    parser.add_argument('--concurrency',type=int,default=5)
    parser.add_argument('--requests-per-minute',type=int,default=90)
    parser.add_argument('--seed',type=int,default=20261029)
    parser.add_argument('--allow-partial', action='store_true', help='Publish an explicitly incomplete matrix without hiding stopped or missing runs')
    args = parser.parse_args()
    if args.allow_partial and args.command!='publish':
        parser.error('--allow-partial applies only to publication')
    if args.command!='prepare' and any(arg.split('=')[0] in ('--provider','--repetitions','--concurrency','--requests-per-minute','--seed') for arg in sys.argv[1:]):
        parser.error('Execution and reporting use frozen settings; configuration flags apply only to prepare')
    try:
        if args.command == 'prepare':
            print('Prepared matrix; no API calls.', prepare(args.directory,provider=args.provider,repetitions=args.repetitions,
                concurrency=args.concurrency,requests_per_minute=args.requests_per_minute,seed=args.seed)['study_id'])
        elif args.command == 'run':
            print(execute(args.directory)['status'])
        elif args.command == 'report':
            print(report(args.directory)['status'])
        elif args.command == 'verify':
            print(json.dumps(verify_export(args.directory)))
        else:
            result = report(args.directory)
            if result['status'] != 'completed' and not args.allow_partial:
                raise ValueError('Inspect incomplete evidence and use --allow-partial to publish its actual status')
            plan, _ = load(args.directory)
            destination = SIMULATION_DIR.parent / 'landing/public/replays'
            for child in reversed(plan['children']):
                study.publish(args.directory / child['directory'], destination)
            result['source_urls'] = {row['run_id']:f"/replays/{row['run_id']}.source.jsonl" for row in result['runs']}
            save_json(destination / f"matrix-{plan['study_id']}.json", result)
            save_json(destination / f"matrix-{plan['study_id']}.protocol.json", plan)
            # Preserve a readable, shareable case study with working source links
            # alongside the machine-readable result. Canonical records stay intact.
            text = (args.directory/'case-study.md').read_text()
            text = text.replace('](matrix.json)',f"](matrix-{plan['study_id']}.protocol.json)")
            text = text.replace('](matrix-report.json)',f"](matrix-{plan['study_id']}.json)")
            for child in plan['children']:
                protocol = study.load_protocol(args.directory/child['directory'])
                text = text.replace(f"]({child['directory']}/protocol.json)",f"](study-{protocol['study_id']}.protocol.json)")
                text = text.replace(f"]({child['directory']}/report.json)",f"](study-{protocol['study_id']}.json)")
            for row in result['runs']:
                text = text.replace(f"]({row['file']})",f"]({row['run_id']}.source.jsonl)")
            (destination/f"matrix-{plan['study_id']}.md").write_text(text)
            index_path = destination / 'index.json'
            index = json.loads(index_path.read_text())
            source_rows = {row['run_id']:row for row in result['runs']}
            for entry in index['runs']:
                if entry['run_id'] in source_rows:
                    entry['study'] = {'matrix_id':plan['study_id'],'repetition':source_rows[entry['run_id']]['repetition']}
            name = f"matrix-{plan['study_id']}.json"
            index['matrix'] = {'url':'/replays/'+name, 'sha256':hashlib.sha256((destination/name).read_bytes()).hexdigest(),
                'protocol_url':f"/replays/matrix-{plan['study_id']}.protocol.json",
                'title':f"{plan.get('provider','openai')} · {result['collection']['completed_runs']}/{len(plan['schedule'])} complete · {plan['study_id'][:8]}"}
            previous=[*index.get('matrices',[])]
            # Keep all historical matrices inspectable, never pool transports.
            for path in sorted(destination.glob('matrix-*.json')):
                if path.name.endswith('.protocol.json') or path.name==name:continue
                old=json.loads(path.read_text())
                previous.append({'url':'/replays/'+path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                    'protocol_url':'/replays/'+path.name.replace('.json','.protocol.json'),
                    'title':f"{old.get('provider','openai')} · {old['collection']['completed_runs']} complete · {old['study_id'][:8]}"})
            index['matrices']=[{row['url']:row for row in previous if row['url']!=index['matrix']['url']}[url]
                for url in dict.fromkeys(row['url'] for row in previous if row['url']!=index['matrix']['url'])]+[index['matrix']]
            save_json(index_path, index)
            print(result['status'])
    except (ValueError, RuntimeError, OSError) as error:
        parser.exit(2, f'Matrix stopped: {error}\n')


if __name__ == '__main__':
    main()
