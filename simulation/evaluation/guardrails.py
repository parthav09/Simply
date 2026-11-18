"""Pass / review / fail guardrail checks for canonical run recordings.

Read-only: this module never applies, edits or invents anything. It reads a recording written
by Python core and says, per shopper and per run, whether anything needs a human's attention.

* fail   - a hard rule is broken; the run should not be trusted as a good result as it stands.
* review - something unusual that a person should look at; not proof of a fault.
* pass   - nothing was flagged. This is NOT proof the behaviour is realistic: there is no
           real-shopper ground truth, and several rules below are our own conventions.

Rules and their sources are listed in `RULES`; thresholds are constants so they can be argued
with and changed in one place. The impulse cap/price tiers come from `impulse_eval.TIERS`, a
teacher rule written for the fine-tuning data. A prompt that never states that cap is graded
against a rule the model was not shown, so a cap finding is a flag for review, never a verdict.
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

SIMULATION_DIR = Path(__file__).resolve().parents[1]
if str(SIMULATION_DIR) not in sys.path:
    sys.path.insert(0, str(SIMULATION_DIR))

from evaluation.impulse_eval import TIERS, fits_profile, tier_for  # noqa: E402

REPORT_VERSION = 1
# Share of one shopper's actions that were invalid replies or grid rejections.
INVALID_RATE_REVIEW = 0.05
INVALID_RATE_FAIL = 0.20
# Turns with no cart or phase change in a row before the run is flagged as stuck.
NO_PROGRESS_REVIEW = 30

RULES = {
    'checkout_incomplete': ('fail', 'Shopper never finished checkout',
        'The recording ends without a completed checkout for this shopper.'),
    'provider_exception': ('fail', 'Model provider error',
        'At least one request failed at the provider (not a bad reply from the model).'),
    'allergen_conflict': ('fail', 'Allergen in an unplanned purchase',
        'A paid off-list product lists the shopper\'s declared allergen in the catalogue data.'),
    'invalid_reply_rate_high': ('fail', 'Most actions invalid or rejected',
        f'More than {INVALID_RATE_FAIL:.0%} of the shopper\'s actions were invalid replies or grid rejections.'),
    'invalid_reply_rate': ('review', 'Some actions invalid or rejected',
        f'More than {INVALID_RATE_REVIEW:.0%} of the shopper\'s actions were invalid replies or grid rejections.'),
    'impulse_cap': ('review', 'More unplanned items than the impulse tier allows',
        'Paid off-list units exceed impulse_eval.TIERS for the shopper\'s impulse probability '
        '(and any off-list item below probability 0.10). A teacher rule, not necessarily in the prompt.'),
    'impulse_price': ('review', 'Unplanned item above the tier price ceiling',
        'A paid off-list product costs more than impulse_eval.TIERS allows for the tier.'),
    'diet_or_alcohol_mismatch': ('review', 'Unplanned item may not fit the shopper\'s diet',
        'Catalogue tags do not show the item fits the diet or alcohol preference (unknown counts as not fitting). '
        'Tags are catalogue metadata and are not independently verified.'),
    'over_budget': ('review', 'Final basket above the shopper\'s budget',
        'Budgets are soft preferences in Simply, so this is recorded for review, not rejected.'),
    'above_acceptable_price': ('review', 'Listed item bought above the acceptable price',
        'A listed product was paid above the shopper\'s stated maximum acceptable unit price.'),
    'list_incomplete': ('review', 'Finished with part of the list unbought',
        'Checkout finished but fewer listed units were paid than requested.'),
    'loop_detected': ('review', 'Repeated action loop',
        'Python core\'s loop detector fired for this shopper.'),
    'stuck': ('review', f'No progress for {NO_PROGRESS_REVIEW}+ turns',
        'The cart and phase did not change for a long stretch of consecutive turns.'),
}
SEVERITY_ORDER = {'fail': 2, 'review': 1, 'pass': 0}


def _split(value):
    return {part for part in (value or '').split(';') if part}


def _finding(check, detail, **values):
    return {'check': check, 'severity': RULES[check][0], 'detail': detail, **values}


def check_shopper(customer, shopper, events, catalogue):
    """Findings for one shopper. `catalogue` maps product id to the recorded catalogue entry."""
    findings = []
    listed = {item['product_id'] for item in customer['shopping_list']}
    finished = bool(shopper.get('finished'))
    if not finished:
        findings.append(_finding('checkout_incomplete',
            f"Stopped: {shopper.get('stop_reason', 'unknown')} after {shopper.get('turns_used')} turns"))

    outcomes = Counter(event['outcome'] for event in events)
    if outcomes['provider_exception']:
        findings.append(_finding('provider_exception', f"{outcomes['provider_exception']} provider exception(s)",
            count=outcomes['provider_exception']))
    bad = outcomes['invalid_decision'] + outcomes['grid_rejected']
    rate = bad / len(events) if events else 0.0
    if rate > INVALID_RATE_FAIL:
        findings.append(_finding('invalid_reply_rate_high', f'{bad} of {len(events)} actions ({rate:.0%})', count=bad, rate=round(rate, 4)))
    elif rate > INVALID_RATE_REVIEW:
        findings.append(_finding('invalid_reply_rate', f'{bad} of {len(events)} actions ({rate:.0%})', count=bad, rate=round(rate, 4)))

    # Off-list purchases only count when the shopper actually paid.
    cart = events[-1]['after']['cart'] if events else []
    extras = [(item['product_id'], item['quantity']) for item in cart if item['product_id'] not in listed] if finished else []
    extra_units = sum(quantity for _, quantity in extras)
    probability = customer['impulse_buy_probability']
    tier = tier_for(probability)
    cap = TIERS[tier]['cap'] if tier else 0
    if extra_units > cap:
        findings.append(_finding('impulse_cap',
            f"{extra_units} off-list units against a cap of {cap} ({tier or 'below-threshold'} tier, probability {probability})",
            units=extra_units, cap=cap, tier=tier or 'none', probability=probability))
    if tier:
        ceiling = TIERS[tier]['max_price_cents']
        dear = [pid for pid, _ in extras if round(float(catalogue[pid]['price']) * 100) > ceiling]
        if dear:
            findings.append(_finding('impulse_price', f'{len(dear)} off-list product(s) above ${ceiling / 100:.2f}', products=dear))
    allergy = customer.get('food_allergy') or 'none'
    profile = {'drinks_alcohol': bool(customer.get('drinks_alcohol')), 'diet': customer.get('diet_type') or 'omnivore', 'allergy': allergy}
    hits = [pid for pid, _ in extras if allergy != 'none' and allergy in _split(catalogue[pid].get('allergens'))]
    if hits:
        findings.append(_finding('allergen_conflict', f'Allergy "{allergy}" listed on {len(hits)} paid off-list product(s)', products=hits))
    misfit = [pid for pid, _ in extras if pid not in hits and not fits_profile(catalogue[pid], profile)]
    if misfit:
        findings.append(_finding('diet_or_alcohol_mismatch', f'{len(misfit)} off-list product(s) not shown to fit diet "{profile["diet"]}"', products=misfit))

    if finished and shopper.get('overshoot_cents'):
        findings.append(_finding('over_budget',
            f"${shopper['overshoot_cents'] / 100:.2f} over the ${shopper['budget_cents'] / 100:.2f} budget", cents=shopper['overshoot_cents']))
    if shopper.get('above_acceptable_price_purchases'):
        findings.append(_finding('above_acceptable_price', f"{shopper['above_acceptable_price_purchases']} purchase(s)",
            count=shopper['above_acceptable_price_purchases']))
    if finished and shopper.get('fulfilled_units', 0) < shopper.get('requested_units', 0):
        findings.append(_finding('list_incomplete', f"{shopper['purchased_fulfilled_units']} of {shopper['requested_units']} listed units paid"))
    if shopper.get('loop_detections'):
        findings.append(_finding('loop_detected', f"{shopper['loop_detections']} loop detection(s)", count=shopper['loop_detections']))
    if (shopper.get('longest_no_progress_turns') or 0) >= NO_PROGRESS_REVIEW:
        findings.append(_finding('stuck', f"{shopper['longest_no_progress_turns']} turns in a row", turns=shopper['longest_no_progress_turns']))
    return findings


def verdict(findings):
    return max((f['severity'] for f in findings), key=SEVERITY_ORDER.get, default='pass')


def check_run(path):
    """Guardrail report for one canonical run file."""
    from core.run_log import read_run

    run = read_run(path)
    header, summary = run['start'], run['summary']
    catalogue = {product['id']: product for product in header['catalogue']}
    customers = {s['agent_id']: s['customer'] for s in header['shoppers']}
    events = defaultdict(list)
    for event in run['events']:
        events[event['agent_id']].append(event)
    shoppers = []
    for shopper in summary['shoppers']:
        agent = shopper['agent_id']
        findings = check_shopper(customers[agent], shopper, events[agent], catalogue)
        shoppers.append({'shopper_id': agent, 'name': customers[agent]['first_name'], 'verdict': verdict(findings), 'findings': findings})
    counts = Counter(s['verdict'] for s in shoppers)
    by_check = defaultdict(list)
    for s in shoppers:
        for f in s['findings']:
            by_check[f['check']].append(s['name'])
    return {'run_id': header['run_id'], 'model': header.get('model'), 'layout_id': header['layout']['id'],
        'navigation_policy': header.get('config', {}).get('navigation_policy'), 'status': summary['status'],
        'verdict': verdict([f for s in shoppers for f in s['findings']]),
        'shoppers_total': len(shoppers), 'shoppers_pass': counts['pass'], 'shoppers_review': counts['review'], 'shoppers_fail': counts['fail'],
        'checks': [{'check': check, 'severity': RULES[check][0], 'shoppers': names} for check, names in
                   sorted(by_check.items(), key=lambda kv: (-SEVERITY_ORDER[RULES[kv[0]][0]], kv[0]))],
        'shoppers': shoppers}


def rules_table():
    return [{'check': check, 'severity': severity, 'label': label, 'description': description}
            for check, (severity, label, description) in RULES.items()]


def build_dashboard_report(dashboard_path, replay_dir):
    """Checks for every run behind the Results table's default view, in the order it shows them."""
    dashboard = json.loads(Path(dashboard_path).read_text())
    view = next(v for v in dashboard['views'] if v['id'] == dashboard['default_view'])
    rows = []
    for model in view['models']:
        for layout in dashboard['layouts']:
            cell = model['cells'][layout['id']]
            for run_id in cell['run_ids'] if cell['status'] == 'recorded' else []:
                report = check_run(Path(replay_dir) / f'{run_id}.source.jsonl')
                rows.append({'model_id': model['id'], 'model_label': model['label'], 'layout_id': layout['id'],
                    'layout_label': layout['label'], **{k: v for k, v in report.items() if k != 'shoppers'},
                    'flagged': [{'shopper_id': s['shopper_id'], 'name': s['name'], 'verdict': s['verdict'],
                                 'findings': [{'check': f['check'], 'severity': f['severity'], 'detail': f['detail']} for f in s['findings']]}
                                for s in report['shoppers'] if s['findings']]})
    return {'report_version': REPORT_VERSION, 'source': 'evidence-dashboard.json default view',
        'view': view['id'], 'thresholds': {'invalid_rate_review': INVALID_RATE_REVIEW, 'invalid_rate_fail': INVALID_RATE_FAIL,
            'no_progress_review': NO_PROGRESS_REVIEW, 'impulse_tiers': TIERS},
        'rules': rules_table(), 'runs': rows}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('runs', nargs='*', type=Path, help='Canonical run .jsonl files to check')
    parser.add_argument('--dashboard', type=Path, help='evidence-dashboard.json: check every run behind its default view')
    parser.add_argument('--replay-dir', type=Path, help='Directory holding <run_id>.source.jsonl (with --dashboard)')
    parser.add_argument('--out', type=Path, help='Write the dashboard report JSON here (with --dashboard)')
    args = parser.parse_args(argv)
    if args.dashboard:
        if not args.replay_dir or not args.out:
            parser.error('--dashboard needs --replay-dir and --out')
        report = build_dashboard_report(args.dashboard, args.replay_dir)
        args.out.write_text(json.dumps(report, indent=1, ensure_ascii=False) + '\n')
        print(f"Wrote {len(report['runs'])} run reports to {args.out}")
        return 0
    if not args.runs:
        parser.error('give run files, or --dashboard')
    for path in args.runs:
        report = check_run(path)
        print(f"{report['model']} · {report['layout_id']} · {report['run_id'][:8]}: {report['verdict'].upper()} "
              f"({report['shoppers_pass']} pass, {report['shoppers_review']} review, {report['shoppers_fail']} fail of {report['shoppers_total']})")
        for s in report['shoppers']:
            for f in s['findings']:
                print(f"  {f['severity']:6} {s['name']:10} {f['check']}: {f['detail']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
