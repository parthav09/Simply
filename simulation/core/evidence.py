"""Read-only run history and descriptive comparisons from canonical Python logs."""
import argparse
import copy
import gzip
import hashlib
import json
import math
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

SIMULATION_DIR = Path(__file__).resolve().parents[1]
if str(SIMULATION_DIR) not in sys.path:
    sys.path.insert(0, str(SIMULATION_DIR))

from core.integrity import fingerprint
from core.run_log import read_run

METRICS = {
    'checkout_completion': ('Checkout completion', 'rate'),
    'purchased_unit_fulfillment': ('Requested units purchased', 'rate'),
    'sales_cents': ('Simulated checkout sales', 'cents'),
    'mean_successful_moves': ('Average moves per shopper', 'number'),
    'turns_used': ('Action attempts', 'integer'),
    'invalid_decision_count': ('Invalid replies', 'integer'),
    'grid_rejection_count': ('Rejected actions', 'integer'),
    'provider_failure_count': ('Provider failures', 'integer'),
    'navigation_adjustments': ('Assisted actions', 'integer'),
    'overspending_fraction': ('Shoppers over budget in final basket', 'rate'),
    'checkout_overshoot_cents': ('Simulated purchases above shopper budgets', 'cents'),
    'purchased_off_list_units': ('Off-list units purchased', 'integer'),
    'loop_detections': ('Repeated loops', 'integer'),
    'model_requests': ('Model requests', 'integer'),
    'run_duration_ms': ('Recorded run duration', 'milliseconds'),
    'request_latency_p50_ms': ('Model request latency · median', 'milliseconds'),
    'request_latency_p95_ms': ('Model request latency · 95th percentile', 'milliseconds'),
    'known_estimated_cost_usd': ('Known API estimate · run', 'usd'),
    'cost_per_completed_trip_usd': ('API estimate per checkout', 'usd'),
    'unknown_usage_requests': ('Unknown-usage attempts', 'integer'),
}
FACTORS = {
    'provider': 'Different providers', 'model': 'Different configured models',
    'actual_model': 'Different or unverified actual model versions',
    'cohort': 'Different shopper profiles or shopping lists',
    'catalogue': 'Different products or prices', 'starting_cells': 'Different starting cells',
    'policy': 'Different navigation policies', 'settings': 'Different action limits or model settings',
    'prompt': 'Different prompts', 'engine': 'Different engine versions',
    'provider_code': 'Different provider implementations',
    'store_structure': 'Different store structure or product assortment',
    'metrics': 'Different metric definitions',
}


def _number(value):
    return value if type(value) in (int, float) and math.isfinite(value) else None


def run_row(path):
    """Validate before exposing metrics. Never return prompts, profiles or credentials."""
    path = Path(path)
    run = read_run(path)
    header, summary, events = run['start'], run['summary'], run['events']
    if header['config']['mode'] != 'actions':
        raise ValueError('Proposal-only recording')
    config = header['config']
    policy = config.get('navigation_policy', 'model_only')
    resources = summary.get('resources') or {}
    known_cost = _number(resources.get('known_estimated_cost_usd'))
    cost_known = known_cost is not None and resources.get('unknown_cost_attempts') == 0
    finished = summary['finished_count']
    counts = summary['failures']
    metrics = {key: _number(summary.get(key)) for key in METRICS}
    metrics.update({
        'invalid_decision_count': counts['invalid_decision'],
        'grid_rejection_count': counts['grid_rejected'],
        'provider_failure_count': counts['provider_exception'],
        'navigation_adjustments': sum(bool(e.get('telemetry', {}).get('navigation', {}).get('adjustment')) for e in events),
        'checkout_overshoot_cents': sum(s['checkout_overshoot_cents'] for s in summary['shoppers'])
            if all(type(s.get('checkout_overshoot_cents')) is int for s in summary['shoppers']) else None,
        'purchased_off_list_units': sum(s['off_list_units'] for s in summary['shoppers'] if s['finished'])
            if all(type(s.get('off_list_units')) is int for s in summary['shoppers']) else None,
        'model_requests': sum(e['telemetry']['request_submitted'] for e in events)
            if all(type(e.get('telemetry', {}).get('request_submitted')) is bool for e in events) else None,
        'known_estimated_cost_usd': known_cost,
        'cost_per_completed_trip_usd': known_cost / finished if cost_known and finished else None,
        'unknown_usage_requests': _number(resources.get('unknown_usage_requests')),
        'run_duration_ms': _number((summary.get('performance') or {}).get('run_duration_ms')),
        'request_latency_p50_ms': _number((summary.get('performance') or {}).get('request_latency_p50_ms')),
        'request_latency_p95_ms': _number((summary.get('performance') or {}).get('request_latency_p95_ms')),
    })
    if header['provider']=='openrouter':
        metrics['provider_reported_cost_usd']=_number(resources.get('provider_reported_cost_usd'))
        metrics['provider_reported_cost_per_checkout_usd']=(metrics['provider_reported_cost_usd']/finished
            if metrics['provider_reported_cost_usd'] is not None and finished else None)
    versions = sorted({e.get('telemetry', {}).get('model_version') for e in events
                       if isinstance(e.get('telemetry', {}).get('model_version'), str)})
    verified_versions = bool(versions) and all(e.get('telemetry', {}).get('model_version')
        for e in events if e['outcome'] != 'provider_exception')
    layout = header['layout']
    fixtures = [{k: shelf.get(k) for k in ('department', 'shape', 'offsets')}
                | {'products': sorted(p['id'] for p in shelf['products'])} for shelf in layout['shelves']]
    structure = {'width': layout['width'], 'height': layout['height'], 'entrance': layout['entrance'],
                 'checkout': layout['checkout'], 'exit': layout['exit'],
                 'fixtures': sorted(fixtures, key=lambda value: json.dumps(value, sort_keys=True))}
    normalized_config = {**config, 'navigation_policy': policy}
    return {
        'run_id': header['run_id'], 'recorded_at': header['recorded_at'],
        'provider': header['provider'], 'model': header['model'], 'model_versions': versions,
        'kind': 'model' if header['provider'] in ('openai', 'gemini', 'openrouter') else 'fixture',
        'layout_id': layout['id'], 'shopper_count': len(header['shoppers']),
        'status': summary['status'], 'warnings': run['warnings'], 'navigation_policy': policy,
        'shopping_rules': config.get('shopping_rules', 'quantity_two_phase_v1'),
        'action_limit': config.get('action_limit', config.get('turn_budget')),
        'finished_count': finished, 'metrics': metrics, 'cost_complete': cost_known,
        'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'source_file': path.name,
        'controls': {
            'provider': header['provider'], 'model': header['model'],
            'actual_model': fingerprint(versions) if verified_versions else None,
            'cohort': fingerprint([s['customer'] for s in header['shoppers']]),
            'catalogue': fingerprint(header['catalogue']),
            'starting_cells': fingerprint([(s['state']['x'], s['state']['y']) for s in header['shoppers']]),
            'policy': policy, 'settings': fingerprint(normalized_config),
            'prompt': header.get('prompt_version'), 'engine': header.get('engine_fingerprint'),
            'provider_code': header.get('provider_fingerprint'),
            'store_structure': fingerprint(structure), 'metrics': header.get('metrics_version', 1),
        },
    }


def compare_rows(baseline, candidate):
    reasons = []
    if candidate['run_id'] != baseline['run_id']:
        for key, label in FACTORS.items():
            left, right = baseline['controls'].get(key), candidate['controls'].get(key)
            if left is None or right is None or left != right:
                reasons.append(label)
    if baseline['status'] != 'completed' or candidate['status'] != 'completed':
        reasons.append('An incomplete or stopped recording is included')
    if baseline['warnings'] or candidate['warnings']:
        reasons.append('A recording has reader warnings')
    if baseline['kind'] == 'fixture' or candidate['kind'] == 'fixture':
        reasons.append('Scripted test fixtures are not model evaluations')
    differences = {}
    for key in METRICS:
        first, second = baseline['metrics'][key], candidate['metrics'][key]
        if key == 'known_estimated_cost_usd' and not (baseline['cost_complete'] and candidate['cost_complete']):
            first = second = None
        differences[key] = {'absolute': second - first if first is not None and second is not None else None,
                            'relative_percent': (second - first) / abs(first) * 100
                            if first is not None and second is not None and first != 0 else None}
    return {'run_id': candidate['run_id'], 'baseline_id': baseline['run_id'],
            'matched_controls': not reasons, 'reasons': reasons, 'differences': differences}


def history_payload(rows, scope, issues=()):
    rows = sorted(rows, key=lambda row: (row['recorded_at'], row['run_id']), reverse=True)
    unique = {}
    conflicts = []
    conflicting_ids = set()
    for row in rows:
        previous = unique.get(row['run_id'])
        if previous and previous['source_sha256'] != row['source_sha256']:
            conflicts.append({'file': row['source_file'], 'reason': 'Conflicting records share a run ID'})
            conflicting_ids.add(row['run_id'])
            continue
        unique.setdefault(row['run_id'], row)
    # Do not present one arbitrarily chosen side of conflicting evidence.
    for identifier in conflicting_ids:
        unique.pop(identifier, None)
    rows = list(unique.values())
    return {'history_version': 1, 'generated_at': datetime.now(timezone.utc).isoformat(),
            'scope': scope, 'runs': rows, 'issues': [*issues, *conflicts],
            'metric_definitions': {key: {'label': label, 'unit': unit} for key, (label, unit) in METRICS.items()},
            'counts': {'runs': len(rows), 'model_runs': sum(r['kind'] == 'model' for r in rows),
                       'fixtures': sum(r['kind'] == 'fixture' for r in rows),
                       'completed': sum(r['status'] == 'completed' for r in rows)},
            'comparisons': {baseline['run_id']: [compare_rows(baseline, row) for row in rows] for baseline in rows}}


class EvidenceStore:
    """Cache validated compact rows by file signature; never execute a provider."""
    def __init__(self, root):
        self.root = Path(root)
        self.cache = {}
        self.lock = threading.Lock()

    def snapshot(self):
        rows, issues = [], []
        with self.lock:
            paths = sorted([*self.root.rglob('*.jsonl'), *self.root.rglob('*.jsonl.gz')])
            self.cache = {path: value for path, value in self.cache.items() if path in paths}
            for path in paths:
                try:
                    stat = path.stat();signature = (stat.st_size, stat.st_mtime_ns)
                    cached = self.cache.get(path)
                    if cached is None or cached[0] != signature:
                        opener = gzip.open if path.suffix == '.gz' else open
                        with opener(path, 'rb') as handle:
                            first = json.loads(handle.readline())
                        if not isinstance(first, dict) or first.get('type') != 'run_start':
                            raise ValueError('Not a canonical run')
                        row = run_row(path)
                        # A growing log may change while being validated. Try it again on refresh.
                        after = path.stat()
                        if (after.st_size, after.st_mtime_ns) != signature:
                            issues.append({'file': path.name, 'reason': 'Recording changed during read; refresh to include it'})
                            continue
                        self.cache[path] = (signature, row)
                    rows.append(self.cache[path][1])
                except (OSError, ValueError, KeyError, TypeError):
                    issues.append({'file': path.name, 'reason': 'Not a valid canonical action run'})
        return history_payload(rows, 'local_saved_runs', issues)


def write_history(destination, rows, scope, issues=()):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    rows = copy.deepcopy(rows)
    index_path = destination / 'index.json'
    index = json.loads(index_path.read_text()) if index_path.exists() else {'schema_version': 1, 'runs': [], 'reports': []}
    published = {entry['run_id']: entry for entry in index['runs']}
    for row in rows:
        entry = published.get(row['run_id'])
        row['published'] = {'url': entry['url'], 'evidence_url': entry['evidence_url']} if entry and entry['sha256'] == row['source_sha256'] else None
    payload = history_payload(rows, scope, issues)
    data = json.dumps(payload, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    temporary = destination / 'history.tmp';temporary.write_text(data);temporary.replace(destination / 'history.json')
    index['history'] = {'url': '/replays/history.json', 'sha256': hashlib.sha256(data.encode()).hexdigest()}
    temporary = index_path.with_suffix('.tmp');temporary.write_text(json.dumps(index, indent=2) + '\n');temporary.replace(index_path)
    return payload


def update_published_history(destination):
    destination = Path(destination);index = json.loads((destination / 'index.json').read_text())
    rows = {}
    if index.get('history'):
        text = (destination / 'history.json').read_text()
        if hashlib.sha256(text.encode()).hexdigest() != index['history']['sha256']:
            raise ValueError('Published history integrity mismatch')
        rows = {row['run_id']: row for row in json.loads(text)['runs']}
    for entry in index['runs']:
        name = Path(entry['evidence_url']).name
        path = destination / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
            raise ValueError('Published source integrity mismatch')
        rows[entry['run_id']] = run_row(path)
    return write_history(destination, list(rows.values()), 'exported_saved_runs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    snapshot = EvidenceStore(args.root).snapshot()
    write_history(args.destination, snapshot['runs'], 'exported_saved_runs', snapshot['issues'])
    print(f"Exported {len(snapshot['runs'])} run summaries; {len(snapshot['issues'])} unsupported or unreadable records identified.")


if __name__ == '__main__':
    main()
