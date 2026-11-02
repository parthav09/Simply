"""A moved ledger or missing model metadata must never manufacture evidence."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SIMULATION_DIR=Path(__file__).resolve().parents[1]
if str(SIMULATION_DIR) not in sys.path:sys.path.insert(0,str(SIMULATION_DIR))
from agents.providers import FakeDecisionProvider
from agents.base import ProposalResult
from core.budget import CampaignLedger, read_ledger_snapshot
from core.run_log import read_run
from core.session import SimulationSession
from evaluation.benchmark import load_benchmark
from evaluation.run import compatible, make_report, run_campaign, save_campaign
from compare_runs import compare_runs


class ReportBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.ledger_path=self.root/'accounting/ledger.sqlite3'
        benchmark=load_benchmark(SIMULATION_DIR/'benchmarks/two_layouts_15_v2.json')
        self.manifest={'study_id':'OFFLINE-budget-report','provider':'fake','seed':42,
                       'benchmark_sha256':benchmark['sha256'],'ledger':str(self.ledger_path),
                       'layouts':['costco_back_anchor','neighborhood_express'],
                       'requested_shopper_count':10,'attempts':[]}
        self.manifest_path=self.root/'campaign.json'

    def save(self):self.manifest_path.write_text(json.dumps(self.manifest))

    def test_missing_ledger_stays_unknown_and_is_not_created(self):
        self.save();report=make_report(self.root)
        self.assertFalse(self.ledger_path.parent.exists())
        self.assertIsNone(read_ledger_snapshot(self.ledger_path))
        self.assertEqual(report['campaign_budget_evidence']['source'],'unavailable')
        self.assertTrue(all(v is None for v in report['campaign_budget'].values()))
        self.assertIn('campaign budget ledger or saved snapshot',report['missing_evidence'])

    def test_existing_ledger_is_read_without_rewriting_or_resetting_it(self):
        ledger=CampaignLedger(self.ledger_path,limit_usd=.01)
        ledger.reserve('OFFLINE-fixture','example')
        expected=ledger.snapshot();before=hashlib.sha256(self.ledger_path.read_bytes()).hexdigest()
        self.save()
        with patch('evaluation.run.CampaignLedger',side_effect=AssertionError('report must not open a writable ledger')):
            report=make_report(self.root)
        self.assertEqual(report['campaign_budget'],expected)
        self.assertEqual(report['campaign_budget_evidence']['source'],'ledger')
        self.assertEqual(hashlib.sha256(self.ledger_path.read_bytes()).hexdigest(),before)

    def test_saved_snapshot_survives_a_moved_ledger_and_detects_tampering(self):
        ledger=CampaignLedger(self.ledger_path,limit_usd=.01)
        ledger.reserve('OFFLINE-fixture','example');expected=ledger.snapshot()
        save_campaign(self.manifest_path,self.manifest,ledger)
        self.ledger_path.rename(self.ledger_path.with_suffix('.retained'))
        report=make_report(self.root)
        self.assertEqual(report['campaign_budget'],expected)
        self.assertEqual(report['campaign_budget_evidence']['source'],'saved_snapshot')
        self.assertTrue(report['campaign_budget_evidence']['recorded_at'])
        self.assertFalse(self.ledger_path.exists())
        self.manifest['budget_snapshot']['values']['known_estimated_usd']=1
        self.save()
        with self.assertRaisesRegex(ValueError,'snapshot integrity'):make_report(self.root)

    def test_corrupt_ledger_is_retained_and_never_becomes_zero_spend(self):
        self.ledger_path.parent.mkdir();self.ledger_path.write_bytes(b'OFFLINE corrupt ledger fixture')
        self.save();report=make_report(self.root)
        self.assertEqual(report['campaign_budget_evidence']['source'],'unavailable')
        self.assertIsNone(report['campaign_budget']['known_estimated_usd'])
        self.assertEqual(self.ledger_path.read_bytes(),b'OFFLINE corrupt ledger fixture')

    def test_resume_cannot_silently_reset_or_switch_a_campaign_ledger(self):
        benchmark=SIMULATION_DIR/'benchmarks/two_layouts_15_v2.json';self.save()
        with patch('evaluation.run.CampaignLedger',side_effect=AssertionError('must reject before creating accounting files')):
            with self.assertRaisesRegex(ValueError,'ledger is missing'):run_campaign(self.root,benchmark,provider='fake')
            with self.assertRaisesRegex(ValueError,'ledger differs'):run_campaign(self.root,benchmark,provider='fake',ledger_path=self.root/'replacement.sqlite3')
        self.assertFalse(self.ledger_path.exists());self.assertFalse((self.root/'replacement.sqlite3').exists())

    def test_resume_rejects_a_reset_ledger_even_at_the_original_path(self):
        ledger=CampaignLedger(self.ledger_path);ledger.reserve('OFFLINE-fixture','example')
        save_campaign(self.manifest_path,self.manifest,ledger)
        self.ledger_path.rename(self.ledger_path.with_suffix('.retained'))
        CampaignLedger(self.ledger_path)
        with self.assertRaisesRegex(ValueError,'history was reset'):
            run_campaign(self.root,SIMULATION_DIR/'benchmarks/two_layouts_15_v2.json',provider='fake')
        self.assertEqual(read_ledger_snapshot(self.ledger_path)['requests'],0)
        report=make_report(self.root)
        self.assertEqual(report['campaign_budget_evidence']['source'],'saved_snapshot')
        self.assertEqual(report['campaign_budget']['requests'],1)
        self.assertGreater(report['campaign_budget']['unresolved_reserved_usd'],0)


class ModelVersionComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name);self.runs=[]
        for layout in ('costco_back_anchor','neighborhood_express'):
            session=SimulationSession(layout,shopper_count=2,max_rounds=2,decide=FakeDecisionProvider(),output_path=root/f'{layout}.jsonl')
            session.run();self.runs.append(read_run(session.path))

    def modeled(self):
        # These are in-memory contract inputs, never published model recordings.
        runs=copy.deepcopy(self.runs)
        for run in runs:
            run['start']['provider']='openai'
            for event in run['events']:
                event['telemetry']['request_submitted']=True
                event['telemetry']['model_version']='OFFLINE-model-version-fixture'
        return runs

    def test_unmeasured_latency_does_not_become_zero_in_paired_report(self):
        root=Path(self.temp.name)/'missing-latency';root.mkdir()
        class UnmeasuredProvider(FakeDecisionProvider):
            def __call__(self,prompt,allowed_steps):
                proposal=super().__call__(prompt,allowed_steps)
                return ProposalResult(proposal.raw_response,proposal.decision,{'request_submitted':False})
        attempts=[]
        for layout in ('costco_back_anchor','neighborhood_express'):
            session=SimulationSession(layout,shopper_count=2,max_rounds=1,decide=UnmeasuredProvider(),output_path=root/f'{layout}.jsonl')
            session.run()
            attempts.append({'file':session.path.name,'layout':layout,'stage':'main','repetition':1})
        manifest={'study_id':'OFFLINE-missing-latency','provider':'fake','cohort_size':2,'ledger':str(root/'missing.sqlite3'),'benchmark_sha256':'OFFLINE-fixture',
                  'layouts':['costco_back_anchor','neighborhood_express'],'attempts':attempts}
        (root/'campaign.json').write_text(json.dumps(manifest))
        report=make_report(root)
        latency=[row for row in report['paired'] if row['metric'].startswith('request_latency')]
        self.assertEqual(len(latency),2)
        for row in latency:
            self.assertIsNone(row['mean_difference']);self.assertIsNone(row['ci95'])
            self.assertEqual(row['blocks'],0);self.assertEqual(row['missing_blocks'],1)
            self.assertEqual(row['status'],'unassessed')

    def test_real_provider_comparisons_require_returned_model_versions(self):
        left,right=self.modeled();compatible(left,right)
        right['events'][0]['telemetry'].pop('model_version')
        for compare in (compatible,compare_runs):
            with self.assertRaisesRegex(ValueError,'verified actual model versions'):compare(left,right)

    def test_changed_actual_versions_are_rejected_by_both_commands(self):
        left,right=self.modeled();right['events'][0]['telemetry']['model_version']='OFFLINE-different-version'
        for compare in (compatible,compare_runs):
            with self.assertRaisesRegex(ValueError,'actual model versions'):compare(left,right)

    def test_cli_comparison_rejects_changed_starting_cells_and_engine(self):
        left,right=self.runs
        changed=copy.deepcopy(right);changed['start']['shoppers'][0]['state']['x']+=1
        with self.assertRaisesRegex(ValueError,'starting cells'):compare_runs(left,changed)
        changed=copy.deepcopy(right);changed['start']['engine_fingerprint']='different'
        with self.assertRaisesRegex(ValueError,'engine_fingerprint'):compare_runs(left,changed)


if __name__=='__main__':unittest.main()
