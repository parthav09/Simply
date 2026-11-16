"""Audit the pinned landing impulse showcase against its canonical Python trip record."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'simulation'))
from core.export_replay import build_bundle
from core.run_log import read_run


class LandingDemoTests(unittest.TestCase):
    def test_pinned_impulse_showcase_is_an_intact_completed_run_with_recorded_off_list_purchases(self):
        public = ROOT / 'landing/public'
        selected = json.loads((ROOT / 'landing/data/impulse-showcase.json').read_text())
        catalog = json.loads((public / 'replays/index.json').read_text())
        entry = next(entry for entry in catalog['runs'] if entry['run_id'] == selected['run_id'])
        source = public / entry['evidence_url'].lstrip('/')
        bundle_path = public / entry['url'].lstrip('/')
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), entry['sha256'])
        self.assertEqual(hashlib.sha256(bundle_path.read_bytes()).hexdigest(), entry['bundle_sha256'])
        # read_run checks movement, reachable pickups, duplicate products, checkout and accounting.
        run = read_run(source)
        self.assertEqual(run['start']['schema_version'], 2)
        self.assertEqual(run['start']['config']['shopping_rules'], 'unique_single_checkout_v1')
        self.assertFalse(run['warnings'])
        self.assertEqual(run['summary']['status'], 'completed')
        self.assertEqual(run['summary']['shopper_count'], 10)
        self.assertEqual(build_bundle(source), json.loads(bundle_path.read_text()),
                         'Published replay differs from canonical Python projection')
        # The receipt shopper must have checked out with recorded off-list purchases, and the
        # off-list cart items must reconcile exactly with Python's off_list_units.
        shopper = next(s for s in run['start']['shoppers'] if s['agent_id'] == selected['shopper_id'])
        metric = next(s for s in run['summary']['shoppers'] if s['agent_id'] == selected['shopper_id'])
        self.assertTrue(metric['finished'])
        self.assertGreater(metric['off_list_units'], 0)
        planned = {item['product_id'] for item in shopper['customer']['shopping_list']}
        events = [e for e in run['events'] if e['agent_id'] == selected['shopper_id']]
        cart = events[-1]['after']['cart']
        self.assertEqual(sum(i['quantity'] for i in cart if i['product_id'] not in planned), metric['off_list_units'])
