"""Frozen study orchestration and reporting; all providers here are offline fixtures."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents.base import Decision, ProposalResult
from core.integrity import fingerprint
from core.run_log import read_run
from evaluation.study import prepare, execute, report, publish, slot_path, expected, aggregate_metrics
from core.evidence import METRICS


class ControlledStudyTests(unittest.TestCase):
    def test_arm_cost_per_checkout_pools_costs_including_zero_checkout_runs(self):
        def row(cost, finished):
            values = {key: 0 for key in METRICS}
            values.update(known_estimated_cost_usd=cost, cost_per_completed_trip_usd=cost/finished if finished else None)
            return {'metrics': values, 'finished_count': finished, 'cost_complete': True}
        rows = [row(1, 0), row(3, 2)]
        self.assertEqual(aggregate_metrics(rows)['cost_per_completed_trip_usd'], 2)
        self.assertEqual(aggregate_metrics(rows)['known_estimated_cost_usd'], 2)
        rows[0]['cost_complete'] = False
        self.assertIsNone(aggregate_metrics(rows)['cost_per_completed_trip_usd'])
        self.assertIsNone(aggregate_metrics([])['checkout_completion'])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.no_network = patch('urllib.request.urlopen', side_effect=AssertionError('No model transport in offline tests'))
        self.no_network.start(); self.addCleanup(self.no_network.stop)

    def prepare(self, name='layout', **kwargs):
        directory = self.root/name
        protocol = prepare(directory, provider=kwargs.pop('provider', 'fake'),
            turn_budget=2, repetitions=kwargs.pop('repetitions', 1), **kwargs)
        return directory, protocol

    def test_prepare_is_unstarted_immutable_and_freezes_only_the_intended_factor(self):
        for kind in ('layout', 'model', 'assistance'):
            directory, protocol = self.prepare(kind, kind=kind, provider='openai')
            self.assertEqual(list(directory.iterdir()), [directory/'protocol.json'])
            contracts = list(protocol['contracts'].values())
            a, b = contracts
            self.assertEqual(a['catalogue'], b['catalogue'])
            self.assertEqual([s['customer'] for s in a['shoppers']], [s['customer'] for s in b['shoppers']])
            self.assertEqual(a['config']['decision_mode'], 'single_action')
            self.assertFalse(a['config']['api_budget_enforced'])
            self.assertEqual(a['config']['concurrency'], b['config']['concurrency'])
            if kind == 'layout':
                self.assertEqual(a['model'], b['model']); self.assertEqual(a['config'], b['config'])
                self.assertNotEqual(a['layout']['id'], b['layout']['id'])
            if kind == 'model':
                self.assertEqual(a['layout'], b['layout']); self.assertEqual(a['config'], b['config'])
                self.assertNotEqual(a['model'], b['model']); self.assertNotEqual(a['pricing'], b['pricing'])
            if kind == 'assistance':
                self.assertEqual(a['layout'], b['layout']); self.assertEqual(a['model'], b['model'])
                self.assertEqual({c['config']['navigation_policy'] for c in contracts}, {'gary2_v2', 'model_only'})
            with self.assertRaises(FileExistsError):
                prepare(directory)

    def test_five_repeated_pairs_include_every_shopper_and_never_duplicate_on_resume(self):
        directory, protocol = self.prepare(repetitions=5)
        result = execute(directory)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(len(result['runs']), 10)
        self.assertTrue(all(row['finished_count'] == 0 and row['metrics']['checkout_completion'] == 0 for row in result['runs']))
        pairs = {row['metric']: row for row in result['paired']}
        self.assertEqual(pairs['checkout_completion']['ci95'], [0, 0])
        self.assertEqual(pairs['checkout_completion']['blocks'], 5)
        self.assertIsNone(pairs['cost_per_completed_trip_usd']['mean_difference'])
        self.assertEqual(pairs['cost_per_completed_trip_usd']['missing_blocks'], 5)
        self.assertEqual(execute(directory)['runs'], result['runs'])
        self.assertFalse((self.root/'gemini_campaign.sqlite3').exists())
        with self.assertRaisesRegex(ValueError, 'explicit --allow-test'):
            publish(directory, self.root/'public')
        exported = publish(directory, self.root/'public', allow_test=True)
        self.assertTrue((self.root/'public'/Path(exported['protocol_url']).name).is_file())

    def test_incremental_execution_resumes_without_repeating_paid_slots(self):
        directory, protocol = self.prepare(repetitions=2)
        first = execute(directory, max_new_runs=1)
        self.assertEqual(len(first['runs']), 1)
        path = slot_path(directory, protocol['schedule'][0]); original = path.read_bytes()
        second = execute(directory, max_new_runs=1)
        self.assertEqual(len(second['runs']), 2)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(execute(directory)['status'], 'completed')
        self.assertEqual(path.read_bytes(), original)
        for value in (0, -1, True):
            with self.assertRaisesRegex(ValueError, 'positive integer'):
                execute(directory, max_new_runs=value)

    def test_missing_and_stopped_slots_remain_visible_and_are_never_retried(self):
        directory, protocol = self.prepare()
        execute(directory)
        slot = protocol['schedule'][0]; path = slot_path(directory, slot)
        lines = path.read_text().splitlines(); path.write_text('\n'.join(lines[:-1])+'\n')
        result = report(directory)
        self.assertEqual(result['status'], 'pilot_or_incomplete')
        self.assertEqual(len(result['runs']), 2)
        self.assertEqual(sum(a['recorded_runs'] for a in result['arms']), 2)
        self.assertTrue(all(row['blocks'] == 0 for row in result['paired']))
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'no automatic retry'):
            execute(directory)
        self.assertEqual(path.read_bytes(), before)
        path.rename(path.with_suffix('.retained'))
        result = report(directory)
        self.assertEqual(result['missing_evidence'], [path.name])
        self.assertEqual(result['status'], 'pilot_or_incomplete')

    def test_protocol_tampering_and_code_drift_fail_before_any_run_is_created(self):
        directory, protocol = self.prepare()
        changed = copy.deepcopy(protocol); changed['cohort_size'] = 15
        (directory/'protocol.json').write_text(json.dumps(changed))
        with self.assertRaisesRegex(ValueError, 'integrity'):
            execute(directory)
        (directory/'protocol.json').write_text(json.dumps(protocol))
        with patch('evaluation.study.template', return_value={}):
            with self.assertRaisesRegex(ValueError, 'Code or inputs changed'):
                execute(directory)
        self.assertEqual(len(list(directory.glob('*.jsonl'))), 0)

    def test_saved_runs_cannot_be_relabelled_to_a_different_protocol(self):
        directory, protocol = self.prepare()
        execute(directory)
        changed = copy.deepcopy(protocol); changed['turn_budget'] = 3
        for contract in changed['contracts'].values():
            contract['config']['action_limit'] = 3
        changed['sha256'] = fingerprint({k:v for k,v in changed.items() if k != 'sha256'})
        (directory/'protocol.json').write_text(json.dumps(changed))
        with self.assertRaisesRegex(ValueError, 'Saved run differs'):
            report(directory)

    def test_model_arm_contracts_work_without_real_model_requests_or_costs(self):
        directory, protocol = self.prepare('models', kind='model', provider='openai')
        def fixture_request(provider, prompt, allowed_steps, shopper_id, *, action_plan):
            self.assertFalse(action_plan)
            decision = Decision(allowed_steps[0], reason='OFFLINE provider contract fixture')
            return ProposalResult(json.dumps(decision.to_dict()), decision,
                {'request_submitted': False, 'estimated_cost_micros': 0,
                 'model_version': 'OFFLINE-'+provider.model, 'usage': {'promptTokenCount': 0, 'candidatesTokenCount': 0}})
        with patch('agents.openai_provider.OpenAIProvider._request', fixture_request), patch('evaluation.study.DECISION_RUNS_DIR', self.root/'accounting'):
            result = execute(directory)
        self.assertEqual(result['study_kind'], 'model')
        self.assertEqual({a['model'] for a in result['arms']}, {'gpt-6-luna', 'gpt-6.1-terra'})
        self.assertTrue(all(row['metrics']['model_requests'] == 0 for row in result['runs']))
        self.assertTrue(all(row['ci95'] is None for row in result['paired']))
        for slot in protocol['schedule']:
            run = read_run(slot_path(directory, slot))
            arm = next(a for a in protocol['arms'] if a['arm_id'] == slot['arm_id'])
            self.assertEqual(run['start']['model'], arm['model'])
            self.assertEqual(run['start']['config'], expected(protocol, arm, slot['repetition'])['config'])
        # These temporary contract fixtures are deliberately never published.
