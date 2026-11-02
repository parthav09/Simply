"""Audit the exact published demo pair against canonical Python trip records."""
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
    def test_pinned_demos_are_intact_successful_matching_cohort_runs(self):
        public = ROOT / 'landing/public'
        selected = json.loads((ROOT / 'landing/data/demo-recordings.json').read_text())
        catalog = json.loads((public / 'replays/index.json').read_text())
        self.assertEqual(set(selected), {'costco_back_anchor', 'neighborhood_express'})
        cohorts = []
        studies = []
        for layout_id, run_id in selected.items():
            with self.subTest(layout=layout_id):
                entry = next(entry for entry in catalog['runs'] if entry['run_id'] == run_id)
                source = public / entry['evidence_url'].lstrip('/')
                bundle_path = public / entry['url'].lstrip('/')
                self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), entry['sha256'])
                self.assertEqual(hashlib.sha256(bundle_path.read_bytes()).hexdigest(), entry['bundle_sha256'])
                # read_run checks movement, blocked shelves, reachable pickups,
                # duplicate products, checkout position, state chains and accounting.
                run = read_run(source)
                self.assertEqual(run['start']['schema_version'], 2)
                self.assertEqual(run['start']['layout']['id'], layout_id)
                self.assertEqual(run['start']['provider'], 'openai')
                self.assertEqual(run['start']['model'], 'gpt-6.1-terra')
                self.assertEqual(run['start']['config']['shopping_rules'], 'unique_single_checkout_v1')
                self.assertFalse(run['warnings'])
                self.assertEqual(run['summary']['status'], 'completed')
                self.assertEqual(run['summary']['shopper_count'], 10)
                self.assertEqual(run['summary']['finished_count'], 10)
                self.assertEqual(run['summary']['mean_list_completion'], 1)
                self.assertTrue(all(count == 0 for count in run['summary']['failures'].values()))
                self.assertTrue(all(event['outcome'] == 'applied' for event in run['events']))
                for shopper in run['start']['shoppers']:
                    events = [event for event in run['events'] if event['agent_id'] == shopper['agent_id']]
                    self.assertEqual(sum(event['action']['step'] == 'checkout' for event in events), 1)
                    self.assertEqual(events[-1]['after']['phase'], 'FinishedState')
                    self.assertTrue(any(event['action']['step'] == 'grab' for event in events))
                self.assertEqual(build_bundle(source), json.loads(bundle_path.read_text()),
                                 'Published replay differs from canonical Python projection')
                cohorts.append([shopper['customer'] for shopper in run['start']['shoppers']])
                studies.append(entry['study'])
        self.assertEqual(cohorts[0], cohorts[1])
        self.assertEqual(studies[0], studies[1])
        self.assertEqual(studies[0]['repetition'], 1)
