"""All-run history must be validated, read-only and honest about comparability."""
import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agents.base import Decision,ProposalResult
from core.evidence import EvidenceStore,compare_rows,history_payload,run_row,update_published_history,write_history
from core.export_replay import export_run
from core.session import SimulationSession
from core.grid import build_store
from core.customers import instantiate_agents
from agents.state import CartItem
from core.run_log import read_run
from live.server import RunManager,handler_for


class TestProvider:
    provider_id=model='scripted_test'
    def request(self,prompt,allowed_steps,shopper_id):
        decision=Decision(allowed_steps[0],reason='OFFLINE history test')
        return ProposalResult(json.dumps(decision.to_dict()),decision,{
            'request_submitted':False,'estimated_cost_micros':0,'model_version':'OFFLINE-test-model',
            'usage':{'promptTokenCount':1}})


class EvidenceHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'runs';self.root.mkdir()
        self.public=Path(self.temp.name)/'public';self.public.mkdir()

    def make_run(self,name='a',run=True):
        session=SimulationSession(shopper_count=1,max_rounds=2,decide=TestProvider(),output_path=self.root/f'{name}.jsonl')
        if run:session.run()
        return session

    def test_history_matches_canonical_metrics_and_never_calls_a_provider(self):
        session=self.make_run();expected=read_run(session.path)
        with patch('urllib.request.urlopen',side_effect=AssertionError('history is read only')):
            snapshot=EvidenceStore(self.root).snapshot()
        self.assertEqual(snapshot['counts'],{'runs':1,'model_runs':0,'fixtures':1,'completed':1})
        row=snapshot['runs'][0]
        self.assertEqual(row['metrics']['checkout_completion'],expected['summary']['checkout_completion'])
        self.assertEqual(row['metrics']['turns_used'],2)
        self.assertIsNone(row['metrics']['cost_per_completed_trip_usd'])
        self.assertNotIn('prompt',row);self.assertNotIn('raw_response',json.dumps(row))
        self.assertFalse(snapshot['comparisons'][row['run_id']][0]['matched_controls'])

    def test_cache_reuses_intact_rows_and_refreshes_after_a_log_changes(self):
        session=self.make_run(run=False);store=EvidenceStore(self.root)
        with patch('core.evidence.read_run',wraps=read_run) as reader:
            self.assertEqual(store.snapshot()['runs'][0]['status'],'incomplete')
            store.snapshot();self.assertEqual(reader.call_count,1)
            session.finish('cancelled','OFFLINE stopped test')
            self.assertEqual(store.snapshot()['runs'][0]['status'],'cancelled')
            self.assertEqual(reader.call_count,2)

    def test_duplicate_copies_deduplicate_but_conflicting_identities_are_quarantined(self):
        session=self.make_run();shutil.copyfile(session.path,self.root/'copy.jsonl')
        self.assertEqual(len(EvidenceStore(self.root).snapshot()['runs']),1)
        row=run_row(session.path);changed={**row,'source_sha256':'0'*64,'source_file':'other.jsonl'}
        snapshot=history_payload([row,changed],'test')
        self.assertEqual(snapshot['runs'],[]);self.assertEqual(len(snapshot['issues']),1)

    def test_corruption_is_reported_and_missing_metrics_do_not_become_zero(self):
        session=self.make_run();(self.root/'invalid.jsonl').write_text('{broken}\n')
        snapshot=EvidenceStore(self.root).snapshot()
        self.assertEqual(len(snapshot['runs']),1);self.assertEqual(len(snapshot['issues']),1)
        row=run_row(session.path);candidate=copy.deepcopy(row);candidate['metrics']['sales_cents']=None
        self.assertIsNone(compare_rows(row,candidate)['differences']['sales_cents']['absolute'])

    def test_comparison_discloses_policy_cohort_and_action_limit_changes(self):
        row=run_row(self.make_run().path);baseline=copy.deepcopy(row);baseline['kind']='model'
        candidate=copy.deepcopy(baseline);candidate['run_id']='another-test-run'
        self.assertTrue(compare_rows(baseline,candidate)['matched_controls'])
        candidate['controls']['policy']='gary2_v1';candidate['controls']['cohort']='other';candidate['controls']['settings']='other'
        result=compare_rows(baseline,candidate)
        self.assertFalse(result['matched_controls']);self.assertEqual(len(result['reasons']),3)
        candidate['status']='cancelled';self.assertIn('An incomplete or stopped recording is included',compare_rows(baseline,candidate)['reasons'])

    def test_export_history_is_integrity_bound_and_retains_explicitly_exported_local_rows(self):
        first=self.make_run('a');second=self.make_run('b')
        snapshot=EvidenceStore(self.root).snapshot()
        write_history(self.public,snapshot['runs'],'exported_saved_runs')
        export_run(first.path,self.public,allow_test=True)
        index=json.loads((self.public/'index.json').read_text())
        history=json.loads((self.public/'history.json').read_text())
        self.assertEqual(len(history['runs']),2)
        selected=next(row for row in history['runs'] if row['run_id']==first.run_id)
        self.assertIsNotNone(selected['published'])
        self.assertIsNone(next(row for row in history['runs'] if row['run_id']==second.run_id)['published'])
        self.assertTrue(index['history']['sha256'])
        (self.public/'history.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'history integrity'):update_published_history(self.public)

    def test_http_history_is_read_only_and_includes_unpublished_fixtures(self):
        from http.server import ThreadingHTTPServer
        from threading import Thread
        from urllib.request import urlopen
        self.make_run();manager=RunManager(self.root,destination=self.public)
        server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(manager))
        thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with urlopen(f'http://127.0.0.1:{server.server_port}/evidence') as response:payload=json.load(response)
            self.assertEqual(len(payload['runs']),1);self.assertEqual(payload['runs'][0]['kind'],'fixture')
            self.assertEqual(manager.sessions,{})
        finally:server.shutdown();server.server_close();thread.join()

    def test_history_export_cli_runs_from_repository_root(self):
        session=self.make_run()
        result=subprocess.run([sys.executable,'-m','simulation.core.evidence','--root',str(self.root),
            '--destination',str(self.public)],cwd=Path(__file__).resolve().parents[2],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        exported=json.loads((self.public/'history.json').read_text())
        self.assertEqual(exported['runs'][0]['run_id'],session.run_id)

    def test_published_record_is_retained_when_original_moves(self):
        session=self.make_run();export_run(session.path,self.public,allow_test=True)
        session.path.rename(self.root.parent/'moved.jsonl')
        history=RunManager(self.root,destination=self.public).history()
        self.assertEqual(len(history['runs']),1)
        self.assertEqual(history['runs'][0]['run_id'],session.run_id)
        self.assertIsNotNone(history['runs'][0]['published'])

    def test_unknown_request_cost_stays_unknown_even_after_successful_checkout(self):
        class UnknownCostProvider(TestProvider):
            calls=0
            def request(self,*args,**kwargs):
                self.calls+=1
                if self.calls==1:raise RuntimeError('OFFLINE transport failure with unknown billing')
                result=super().request(*args,**kwargs)
                return ProposalResult(result.raw_response,result.decision,
                    {**result.telemetry,'estimated_cost_micros':100,'request_submitted':True})
        grid=build_store();shoppers=grid.spawn(instantiate_agents(count=1))
        shopper=shoppers[0];shopper.state.x,shopper.state.y=grid.checkout[0]
        shopper.state.cart=[CartItem(item.product_id,item.name,item.quantity) for item in shopper.state.requirements]
        session=SimulationSession(shopper_count=1,max_rounds=3,grid=grid,shoppers=shoppers,
            decide=UnknownCostProvider(),navigation_policy='gary2_v1',output_path=self.root/'unknown.jsonl')
        session.run();row=run_row(session.path)
        self.assertEqual(row['finished_count'],1)
        self.assertFalse(row['cost_complete'])
        self.assertEqual(row['metrics']['known_estimated_cost_usd'],.0002)
        self.assertIsNone(row['metrics']['cost_per_completed_trip_usd'])
        self.assertIsNone(compare_rows(row,row)['differences']['known_estimated_cost_usd']['absolute'])


if __name__=='__main__':unittest.main()
