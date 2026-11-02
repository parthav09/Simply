"""Preference conclusions must be recoverable from actual recorded decisions."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SIMULATION_DIR=Path(__file__).resolve().parents[1]
if str(SIMULATION_DIR) not in sys.path:sys.path.insert(0,str(SIMULATION_DIR))
from core.budget import CampaignLedger
from evaluation.behavior import run_behavior
from evaluation.behavior_records import read_behavior
from evaluation.run import make_report, publish
from verify_product_workflow import OfflineProbeProvider


class BehaviorEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name);self.path=self.folder/'behavior.jsonl'
        self.ledger=CampaignLedger(self.folder/'ledger.sqlite3')
        with patch('evaluation.behavior.build_provider',return_value=OfflineProbeProvider()):
            self.summary=run_behavior(self.path,self.ledger,provider_name='scripted_test')
        self.rows=[json.loads(line) for line in self.path.read_text().split('\n') if line]

    def write(self,rows):
        self.path.write_text('\n'.join(json.dumps(row,ensure_ascii=False) for row in rows)+'\n')

    def manifest(self):
        data={'study_id':'OFFLINE-behavior-evidence','provider':'scripted_test','seed':42,
              'benchmark_sha256':'fixture','ledger':str(self.ledger.path),'attempts':[],
              'layouts':['costco_back_anchor','neighborhood_express'],'requested_shopper_count':10,
              'behavior':self.summary}
        (self.folder/'campaign.json').write_text(json.dumps(data));return data

    def test_frozen_cases_recompute_complete_scores_without_realism_claims(self):
        loaded=read_behavior(self.path)
        self.assertEqual(loaded['summary'],self.summary)
        self.assertEqual(loaded['summary']['attempts'],40)
        self.assertEqual(loaded['summary']['valid_decisions'],40)
        self.assertEqual(loaded['summary']['directional_pairs'],0)
        self.assertEqual(loaded['summary']['ties'],20)
        self.assertEqual(loaded['summary']['categories']['shopping_style']['adherent'],5)
        self.assertEqual(loaded['sha256'],hashlib.sha256(self.path.read_bytes()).hexdigest())

    def test_corrupted_actions_cases_counts_and_order_are_rejected(self):
        for mutate in (
            lambda rows:rows[1].update(valid=False),
            lambda rows:rows[1]['action'].update(step='grab',product_id='unknown'),
            lambda rows:rows[1].update(raw_response='malformed response'),
            lambda rows:rows[1].update(sequence=2),
            lambda rows:rows[0]['cases'][0].update(prompt='altered input'),
            lambda rows:rows[-1]['summary'].update(directional_pairs=20),
        ):
            rows=copy.deepcopy(self.rows);mutate(rows);self.write(rows)
            with self.assertRaises(ValueError):read_behavior(self.path)

    def test_interrupted_tail_recovers_only_the_intact_decisions(self):
        prefix='\n'.join(json.dumps(row) for row in self.rows[:4])+'\n'
        self.path.write_bytes(prefix.encode()+b'{"type":"behavior_ch')
        loaded=read_behavior(self.path)
        self.assertEqual(loaded['summary']['status'],'incomplete')
        self.assertEqual(loaded['summary']['attempts'],3)
        self.assertIsNone(loaded['end']);self.assertTrue(loaded['warnings'])
        self.path.write_bytes(prefix.encode()+b'bad earlier line\n{}\n')
        with self.assertRaisesRegex(ValueError,'Malformed'):read_behavior(self.path)

    def test_reader_needs_no_live_dataset_provider_or_network(self):
        script="""
import builtins,sys,urllib.request
sys.path.insert(0,'simulation')
original=builtins.__import__
def load(name,*args,**kwargs):
    if name in ('core.grid','agents.llm','agents.openai_provider'):
        raise AssertionError('live dependency')
    return original(name,*args,**kwargs)
builtins.__import__=load
urllib.request.urlopen=lambda *a,**k:(_ for _ in ()).throw(AssertionError('network'))
from evaluation.behavior_records import read_behavior
evidence=read_behavior(sys.argv[1]);assert evidence['summary']['attempts']==40
"""
        result=subprocess.run([sys.executable,'-c',script,str(self.path)],cwd=SIMULATION_DIR.parent,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_report_and_publication_preserve_raw_preference_evidence(self):
        manifest=self.manifest();report=make_report(self.folder)
        self.assertEqual(report['behavior'],self.summary)
        self.assertEqual(report['status'],'pilot_or_incomplete')
        public=self.folder/'public';published=publish(self.folder,public)
        source=public/Path(published['behavior_evidence']['url']).name
        self.assertEqual(source.read_bytes(),self.path.read_bytes())
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),published['behavior_evidence']['sha256'])
        manifest['behavior']['directional_pairs']=20
        (self.folder/'campaign.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError,'saved decision evidence'):make_report(self.folder)

    def test_missing_behavior_file_does_not_preserve_an_unverified_score(self):
        self.manifest();self.path.rename(self.folder/'retained-behavior.jsonl')
        report=make_report(self.folder)
        self.assertIsNone(report['behavior'])
        self.assertIn('behavior.jsonl',report['missing_evidence'])
        self.assertEqual(report['status'],'pilot_or_incomplete')


if __name__=='__main__':unittest.main()
