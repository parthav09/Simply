"""Matrix contracts and independent outcome audit. Never dispatch real API calls."""
import copy
import json
import hashlib
import shutil
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents.base import Decision, ProposalResult
from core.integrity import fingerprint
from evaluation import matrix, study


class MatrixStudyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.directory = self.root / 'matrix'
        self.no_network = patch('urllib.request.urlopen', side_effect=AssertionError('No real API transport'))
        self.no_network.start(); self.addCleanup(self.no_network.stop)

    def prepare(self, repetitions=1):
        original = study.prepare
        def short(directory, **kwargs):
            return original(directory, **kwargs, turn_budget=2)
        with patch('evaluation.matrix.study.prepare', short):
            return matrix.prepare(self.directory, repetitions=repetitions)

    @staticmethod
    def fixture(provider, prompt, allowed_steps, shopper_id, *, action_plan):
        decision = Decision(allowed_steps[0], reason='Explicit offline matrix contract test')
        return ProposalResult(json.dumps(decision.to_dict()), decision,
            {'request_submitted': False, 'estimated_cost_micros': 0,
             'model_version': 'OFFLINE-'+provider.model, 'usage': {'promptTokenCount':0, 'candidatesTokenCount':0}})

    def test_prepare_freezes_balanced_schedule_and_report_never_creates_runs(self):
        plan = self.prepare(repetitions=5)
        self.assertEqual(len(plan['schedule']),20)
        self.assertEqual(len({(s['directory'],s['arm_id'],s['repetition']) for s in plan['schedule']}),20)
        self.assertFalse(list(self.directory.rglob('*.jsonl')))
        result = matrix.report(self.directory)
        self.assertEqual(result['status'],'incomplete')
        self.assertEqual(len(result['comparisons']),4)
        self.assertTrue(all(c['metrics']['checkout_completion']['blocks']==0 for c in result['comparisons']))
        self.assertTrue(all(c['metrics']['checkout_completion'] is None for c in result['conditions']))

    def test_real_contracts_execute_offline_and_resume_without_new_requests(self):
        self.prepare()
        with patch('agents.openai_provider.OpenAIProvider._request', self.fixture), patch('evaluation.study.DECISION_RUNS_DIR',self.root/'accounting'):
            result = matrix.execute(self.directory)
        self.assertEqual(result['status'],'completed')
        self.assertEqual(len(result['runs']),4)
        self.assertEqual(sum(c['trips'] for c in result['conditions']),40)
        self.assertTrue(all(c['metrics']['checkout_completion']==0 for c in result['conditions']))
        self.assertTrue(all(c['metrics']['cost_per_completed_trip_usd'] is None for c in result['conditions']))
        for comparison in result['comparisons']:
            self.assertEqual(comparison['complete_repetitions'],[1])
            self.assertEqual(len(comparison['profile_pairs']),10)
            self.assertTrue(all(p['baseline']['checkout_completion']==0 and p['candidate']['checkout_completion']==0
                for p in comparison['profile_pairs']))  # Unfinished shoppers are not filtered out.
        for row in result['runs']:
            profiles=row['audit']['profiles']
            self.assertEqual(sum(p['metrics']['mean_successful_moves'] for p in profiles),row['audit']['successful_moves'])
            self.assertEqual(sum(p['metrics']['model_requests'] for p in profiles),row['metrics']['model_requests'])
            self.assertEqual(sum(p['metrics']['estimated_cost_usd'] for p in profiles),row['metrics']['known_estimated_cost_usd'])
        before = {p:p.read_bytes() for p in self.directory.rglob('*.jsonl')}
        with patch('agents.openai_provider.OpenAIProvider._request', side_effect=AssertionError('Must not repeat requests')):
            resumed = matrix.execute(self.directory)
        self.assertEqual(resumed,result)
        self.assertTrue(all(p.read_bytes()==value for p,value in before.items()))

    def test_changed_matrix_or_child_controls_are_rejected_before_execution(self):
        plan = self.prepare()
        changed = copy.deepcopy(plan); changed['schedule'].pop()
        (self.directory/'matrix.json').write_text(json.dumps(changed))
        with self.assertRaisesRegex(ValueError,'integrity'):
            matrix.execute(self.directory)
        changed['sha256']=fingerprint({k:v for k,v in changed.items() if k!='sha256'})
        (self.directory/'matrix.json').write_text(json.dumps(changed))
        with self.assertRaisesRegex(ValueError,'omits or duplicates'):
            matrix.execute(self.directory)
        changed = copy.deepcopy(plan); changed['repetitions'] += 1
        changed['sha256']=fingerprint({k:v for k,v in changed.items() if k!='sha256'})
        (self.directory/'matrix.json').write_text(json.dumps(changed))
        with self.assertRaisesRegex(ValueError,'metadata differs'):
            matrix.execute(self.directory)

    def test_independent_audit_includes_paid_over_budget_trip_in_both_layouts(self):
        from test_simple_shopping import SimpleShoppingTests
        case = SimpleShoppingTests(); case.setUp(); self.addCleanup(case.doCleanups)
        for layout in ('costco_back_anchor','neighborhood_express'):
            session, _, _ = case.setup_trip(layout); session.run()
            counts = matrix.audit(session.path)
            self.assertEqual(counts['finished'],1)
            self.assertEqual(counts['purchased_requested_units'],counts['requested_unique_units'])
            self.assertEqual(counts['profiles'][0]['metrics']['purchased_unit_fulfillment'],1)

    def test_profile_audit_keeps_unpaid_carts_zero_and_unknown_charges_unknown(self):
        from test_simple_shopping import SimpleShoppingTests
        from core.run_log import read_run
        case=SimpleShoppingTests(); case.setUp(); self.addCleanup(case.doCleanups)
        session,_,_=case.setup_trip(); session.run()
        run=read_run(session.path)
        # Remove the payment event: the cart is full but no product has been purchased.
        run['events']=run['events'][:-1]
        run['events'][0]['telemetry'].update(request_submitted=True,estimated_cost_micros=None)
        run['summary'].update(checkout_completion=0,purchased_unit_fulfillment=0)
        with patch('evaluation.matrix.read_run',return_value=run):
            audited=matrix.audit(session.path)
        p=audited['profiles'][0]
        self.assertEqual(p['purchased_products'],0)
        self.assertEqual(p['metrics']['purchased_unit_fulfillment'],0)
        self.assertEqual(p['metrics']['checkout_completion'],0)
        self.assertEqual(p['metrics']['model_requests'],1)
        self.assertIsNone(p['metrics']['estimated_cost_usd'])

    def test_profile_pairing_uses_identity_rejects_drift_and_preserves_unknown_costs(self):
        metric={'checkout_completion':0,'purchased_unit_fulfillment':0,'mean_successful_moves':4,
            'model_requests':5,'estimated_cost_usd':None}
        p={'profile_id':'one','profile_sha256':'a'*64,'requested_products':2,'metrics':metric}
        q={**copy.deepcopy(p),'profile_id':'two'}
        baseline={'run_id':'left','repetition':1,'audit':{'shoppers':2,'profiles':[p,q]}}
        candidate={'run_id':'right','repetition':1,'audit':{'shoppers':2,'profiles':[copy.deepcopy(q),copy.deepcopy(p)]}}
        candidate['audit']['profiles'][1]['metrics'].update(mean_successful_moves=1,estimated_cost_usd=.2)
        pairs=matrix.profile_pairs([(baseline,candidate)])
        self.assertEqual(pairs[0]['profile_id'],'one')
        self.assertEqual(pairs[0]['difference']['mean_successful_moves'],-3)
        self.assertIsNone(pairs[0]['difference']['estimated_cost_usd'])
        candidate['audit']['profiles'][0]['profile_sha256']='b'*64
        with self.assertRaisesRegex(ValueError,'profile or shopping list differs'):
            matrix.profile_pairs([(baseline,candidate)])

    def test_stopped_repetition_is_visible_but_never_paired(self):
        self.prepare()
        with patch('agents.openai_provider.OpenAIProvider._request',self.fixture),patch('evaluation.study.DECISION_RUNS_DIR',self.root/'accounting'):
            completed=matrix.execute(self.directory)
        original=study.report
        def stopped(directory):
            report=original(directory)
            if Path(directory).name=='model-0':
                report['runs'][0]['status']='aborted'
                report['status']='incomplete'
            return report
        with patch('evaluation.matrix.study.report',stopped):
            result=matrix.report(self.directory)
        self.assertEqual(len(result['runs']),len(completed['runs']))
        self.assertEqual(sum(len(c['profile_pairs']) for c in result['comparisons']),20)
        self.assertEqual(len(result['runs'][0]['audit']['profiles']),10)

    def test_export_verification_rebuilds_without_api_and_rejects_source_tampering(self):
        plan=self.prepare()
        with patch('agents.openai_provider.OpenAIProvider._request',self.fixture),patch('evaluation.study.DECISION_RUNS_DIR',self.root/'accounting'):
            result=matrix.execute(self.directory)
        public=self.root/'public'; public.mkdir()
        def save(name,value):
            path=public/name; path.write_text(json.dumps(value)); return path
        for child in plan['children']:
            protocol=study.load_protocol(self.directory/child['directory'])
            save(f"study-{protocol['study_id']}.protocol.json",protocol)
        save(f"matrix-{plan['study_id']}.protocol.json",plan)
        for row in result['runs']:
            shutil.copyfile(self.directory/row['file'],public/f"{row['run_id']}.source.jsonl")
        path=save(f"matrix-{plan['study_id']}.json",result)
        save('index.json',{'matrix':{'url':'/replays/'+path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'protocol_url':f"/replays/matrix-{plan['study_id']}.protocol.json"}})
        with patch('agents.openai_provider.OpenAIProvider._request',side_effect=AssertionError('Verification must never request a model')):
            self.assertEqual(matrix.verify_export(public)['verified_runs'],4)
        changed=copy.deepcopy(result)
        changed['comparisons'][0]['profile_pairs'][0]['difference']['mean_successful_moves']+=1
        path.write_text(json.dumps(changed))
        save('index.json',{'matrix':{'url':'/replays/'+path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'protocol_url':f"/replays/matrix-{plan['study_id']}.protocol.json"}})
        with self.assertRaisesRegex(ValueError,'source reconstruction: comparisons'):
            matrix.verify_export(public)
        path.write_text(json.dumps(result))
        save('index.json',{'matrix':{'url':'/replays/'+path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'protocol_url':f"/replays/matrix-{plan['study_id']}.protocol.json"}})
        source=next(public.glob('*.source.jsonl')); before=source.read_bytes()
        source.write_bytes(before+b' ')
        with self.assertRaisesRegex(ValueError,'recording integrity'):
            matrix.verify_export(public)
        self.assertEqual(source.read_bytes(),before+b' ')


if __name__ == '__main__':
    unittest.main()
