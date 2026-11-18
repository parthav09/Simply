import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation import guardrails as g

ROOT = Path(__file__).resolve().parents[2]
CATALOGUE = {
    'L1': {'id': 'L1', 'price': 3.00, 'dietary_tags': 'vegan;vegetarian', 'allergens': 'none'},
    'S1': {'id': 'S1', 'price': 3.50, 'dietary_tags': 'vegan;vegetarian', 'allergens': 'none'},
    'S2': {'id': 'S2', 'price': 3.50, 'dietary_tags': 'vegan;vegetarian', 'allergens': 'none'},
    'S3': {'id': 'S3', 'price': 3.50, 'dietary_tags': 'vegan;vegetarian', 'allergens': 'none'},
    'EXP': {'id': 'EXP', 'price': 12.00, 'dietary_tags': 'vegan;vegetarian', 'allergens': 'none'},
    'NUT': {'id': 'NUT', 'price': 3.00, 'dietary_tags': 'vegan;vegetarian', 'allergens': 'peanut'},
    'HAM': {'id': 'HAM', 'price': 3.00, 'dietary_tags': 'contains_pork', 'allergens': 'none'},
}


def customer(**overrides):
    base = {'first_name': 'Test', 'impulse_buy_probability': 0.5, 'diet_type': 'omnivore', 'food_allergy': 'none',
            'drinks_alcohol': True, 'shopping_list': [{'product_id': 'L1', 'quantity': 1}]}
    base.update(overrides)
    return base


def shopper(**overrides):
    base = {'finished': True, 'stop_reason': 'finished_checkout', 'turns_used': 40, 'requested_units': 1, 'fulfilled_units': 1,
            'purchased_fulfilled_units': 1, 'budget_cents': 10000, 'overshoot_cents': 0, 'above_acceptable_price_purchases': 0,
            'loop_detections': 0, 'longest_no_progress_turns': 5}
    base.update(overrides)
    return base


def events(cart, n=20, **counts):
    rows = [{'outcome': 'applied', 'after': {'cart': cart}} for _ in range(n)]
    for outcome, count in counts.items():
        rows[:count] = [{'outcome': outcome, 'after': {'cart': cart}} for _ in range(count)]
    return rows


def checks(findings):
    return {f['check'] for f in findings}


class GuardrailTests(unittest.TestCase):
    def test_clean_trip_passes(self):
        findings = g.check_shopper(customer(), shopper(), events([{'product_id': 'L1', 'quantity': 1}]), CATALOGUE)
        self.assertEqual(findings, [])
        self.assertEqual(g.verdict(findings), 'pass')

    def test_unfinished_trip_fails_and_off_list_does_not_count(self):
        cart = [{'product_id': 'L1', 'quantity': 1}] + [{'product_id': 'S1', 'quantity': 5}]
        findings = g.check_shopper(customer(), shopper(finished=False, stop_reason='turn_budget'), events(cart), CATALOGUE)
        self.assertEqual(checks(findings), {'checkout_incomplete'})
        self.assertEqual(g.verdict(findings), 'fail')

    def test_impulse_cap_uses_the_tier_for_the_probability(self):
        cart = [{'product_id': 'L1', 'quantity': 1}] + [{'product_id': f'S{i}', 'quantity': 1} for i in (1, 2, 3)]
        over = g.check_shopper(customer(), shopper(), events(cart), CATALOGUE)       # impulsive cap is 2
        self.assertEqual(checks(over), {'impulse_cap'})
        self.assertEqual(over[0]['units'], 3)
        self.assertEqual(over[0]['cap'], 2)
        within = g.check_shopper(customer(), shopper(), events(cart[:3]), CATALOGUE)
        self.assertEqual(within, [])
        mixed = g.check_shopper(customer(impulse_buy_probability=0.25), shopper(), events(cart[:3]), CATALOGUE)  # mixed cap is 1
        self.assertEqual(checks(mixed), {'impulse_cap'})
        planner_floor = g.check_shopper(customer(impulse_buy_probability=0.05), shopper(),
                                        events([{'product_id': 'L1', 'quantity': 1}, {'product_id': 'S1', 'quantity': 1}]), CATALOGUE)
        self.assertEqual(checks(planner_floor), {'impulse_cap'})   # below 0.10 nothing off-list is expected

    def test_impulse_price_ceiling(self):
        cart = [{'product_id': 'L1', 'quantity': 1}, {'product_id': 'EXP', 'quantity': 1}]
        self.assertIn('impulse_price', checks(g.check_shopper(customer(), shopper(), events(cart), CATALOGUE)))

    def test_allergen_is_a_hard_failure_and_diet_a_review(self):
        nut = [{'product_id': 'L1', 'quantity': 1}, {'product_id': 'NUT', 'quantity': 1}]
        findings = g.check_shopper(customer(food_allergy='peanut'), shopper(), events(nut), CATALOGUE)
        self.assertEqual(checks(findings), {'allergen_conflict'})
        self.assertEqual(g.verdict(findings), 'fail')
        ham = [{'product_id': 'L1', 'quantity': 1}, {'product_id': 'HAM', 'quantity': 1}]
        findings = g.check_shopper(customer(diet_type='vegetarian'), shopper(), events(ham), CATALOGUE)
        self.assertEqual(checks(findings), {'diet_or_alcohol_mismatch'})
        self.assertEqual(g.verdict(findings), 'review')

    def test_invalid_reply_rate_thresholds(self):
        cart = [{'product_id': 'L1', 'quantity': 1}]
        self.assertEqual(g.check_shopper(customer(), shopper(), events(cart, n=100, invalid_decision=5), CATALOGUE), [])
        review = g.check_shopper(customer(), shopper(), events(cart, n=100, invalid_decision=6), CATALOGUE)
        self.assertEqual(checks(review), {'invalid_reply_rate'})
        fail = g.check_shopper(customer(), shopper(), events(cart, n=100, grid_rejected=21), CATALOGUE)
        self.assertEqual(checks(fail), {'invalid_reply_rate_high'})
        self.assertEqual(g.verdict(fail), 'fail')
        exception = g.check_shopper(customer(), shopper(), events(cart, n=100, provider_exception=1), CATALOGUE)
        self.assertEqual(g.verdict(exception), 'fail')

    def test_soft_measures_are_review_only(self):
        cart = [{'product_id': 'L1', 'quantity': 1}]
        findings = g.check_shopper(customer(), shopper(overshoot_cents=500, loop_detections=1, longest_no_progress_turns=31,
                                                       fulfilled_units=0, purchased_fulfilled_units=0), events(cart), CATALOGUE)
        self.assertEqual(checks(findings), {'over_budget', 'loop_detected', 'stuck', 'list_incomplete'})
        self.assertEqual(g.verdict(findings), 'review')

    def test_every_finding_has_a_documented_rule(self):
        for check, (severity, label, description) in g.RULES.items():
            self.assertIn(severity, ('fail', 'review'))
            self.assertTrue(label and description, check)


class RecordedRunTests(unittest.TestCase):
    def test_published_report_covers_the_dashboard_runs(self):
        dashboard = ROOT / 'landing/public/replays/evidence-dashboard.json'
        report_path = ROOT / 'landing/data/run-checks.json'
        if not dashboard.exists() or not report_path.exists():
            self.skipTest('No exported dashboard or run-checks report')
        data = json.loads(dashboard.read_text())
        view = next(v for v in data['views'] if v['id'] == data['default_view'])
        expected = sorted(rid for m in view['models'] for c in m['cells'].values() if c['status'] == 'recorded' for rid in c['run_ids'])
        report = json.loads(report_path.read_text())
        self.assertEqual(report['report_version'], g.REPORT_VERSION)
        self.assertEqual(sorted(r['run_id'] for r in report['runs']), expected)
        for row in report['runs']:
            self.assertEqual(row['shoppers_pass'] + row['shoppers_review'] + row['shoppers_fail'], row['shoppers_total'])

    def test_report_matches_a_fresh_check_of_the_recordings(self):
        dashboard = ROOT / 'landing/public/replays/evidence-dashboard.json'
        report_path = ROOT / 'landing/data/run-checks.json'
        if not dashboard.exists() or not report_path.exists():
            self.skipTest('No exported dashboard or run-checks report')
        fresh = g.build_dashboard_report(dashboard, ROOT / 'landing/public/replays')
        self.assertEqual(json.loads(report_path.read_text()), fresh)


if __name__ == '__main__':
    unittest.main()
