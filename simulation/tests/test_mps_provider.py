"""Local serving identity, isolation, recording and HTTP contracts; no GPU/model downloads."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import urllib.error
from urllib.request import Request,urlopen
from http.server import ThreadingHTTPServer

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agents.mps_runtime import MODEL,SETTINGS,prepare_adapter
from agents.mps_provider import MPSProvider,MPSRequestError,server_url,NoRedirect
from core.session import SimulationSession
from core.run_log import read_run
from core.evidence import run_row
from core.export_replay import build_bundle
from live.protocol import LiveProjection
from live.server import RunManager
from mps_server import handler_for


IDENTITY={'model':MODEL,'device':'mps','base_model':'Qwen/Qwen2.5-7B-Instruct',
    'base_revision':'a'*40,'adapter_sha256':'b'*64,'training_mode':'pilot','generation':SETTINGS}


class MPSTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    @staticmethod
    def response(base,path,body=None,timeout=5):
        if path=='/health':return {'status':'ready','identity':copy.deepcopy(IDENTITY)}
        return {'identity':copy.deepcopy(IDENTITY),'raw_response':json.dumps({'step':'move_right','product_id':'','reason':'Offline MPS test'}),
            'usage':{'prompt_tokens':100,'completion_tokens':10},'finish_reason':'stop','inference_ms':2}

    def test_identity_and_zero_api_charge_record_without_touching_api_ledger(self):
        with patch('agents.mps_provider.local_json',side_effect=self.response):
            session=SimulationSession(provider_name='local_mps',shopper_count=10,max_rounds=1,
                concurrency=1,allow_action_plans=False,output_path=self.root/'run.jsonl',ledger_path=self.root/'ledger.sqlite3')
            session.run()
        run=read_run(session.path);row=run_row(session.path)
        self.assertEqual(row['kind'],'model');self.assertEqual(row['provider'],'local_mps')
        self.assertEqual(run['start']['config']['generation']['serving_identity'],IDENTITY)
        self.assertEqual(row['metrics']['known_estimated_cost_usd'],0)
        self.assertEqual(row['metrics']['unknown_usage_requests'],0)
        self.assertEqual(session.ledger.snapshot()['requests'],0)
        projection=LiveProjection()
        for line in session.path.read_bytes().splitlines(keepends=True):projection.append(line)
        self.assertEqual(projection.snapshot(),json.loads(build_bundle(session.path)['payload_json']))

    def test_serving_drift_and_transport_errors_abort_without_fallback(self):
        def drift(base,path,body=None,timeout=5):
            result=self.response(base,path,body,timeout)
            if path=='/decision':result['identity']['adapter_sha256']='c'*64
            return result
        with patch('agents.mps_provider.local_json',side_effect=drift):
            provider=MPSProvider(None,'test')
            with self.assertRaises(MPSRequestError):provider.request('prompt',['move_right'],'shopper')
            session=SimulationSession(provider_name='local_mps',shopper_count=10,max_rounds=120,
                concurrency=1,output_path=self.root/'drift.jsonl',ledger_path=self.root/'ledger.sqlite3')
            session.run()
        self.assertEqual(session.status,'aborted')
        events=read_run(session.path)['events']
        self.assertLessEqual(len(events),10)
        self.assertEqual(len({e['agent_id'] for e in events}),len(events))

    def test_preview_does_not_connect_load_model_or_create_recordings(self):
        manager=RunManager(self.root)
        with patch('agents.mps_provider.health',side_effect=AssertionError('Preview must stay offline')):
            view=manager.preview('costco_back_anchor',10,MODEL)
        self.assertEqual(view['source']['provider'],'not-started')
        self.assertEqual(view['source']['model'],MODEL);self.assertEqual(view['events'],[])
        self.assertEqual(list(self.root.iterdir()),[])

    def test_frozen_layout_study_records_both_mps_arms_and_rejects_identity_changes(self):
        from evaluation import study
        directory=self.root/'study'
        with patch('agents.mps_provider.local_json',side_effect=self.response):
            protocol=study.prepare(directory,provider='local_mps',concurrency=1,repetitions=1,turn_budget=1)
            self.assertEqual(len(protocol['schedule']),2)
            self.assertTrue(all(c['config']['generation']['serving_identity']==IDENTITY for c in protocol['contracts'].values()))
            with patch('evaluation.study.DECISION_RUNS_DIR',self.root/'accounting'):
                result=study.execute(directory)
        self.assertEqual(result['status'],'completed');self.assertEqual(len(result['runs']),2)
        self.assertTrue(all(row['provider']=='local_mps' for row in result['runs']))
        def changed(base,path,body=None,timeout=5):
            value=self.response(base,path,body,timeout);value['identity']['adapter_sha256']='c'*64;return value
        with patch('agents.mps_provider.local_json',side_effect=changed):
            with self.assertRaisesRegex(ValueError,'changed since preparation'):study.execute(directory)

    def test_background_worker_admits_exactly_two_slots_and_is_idempotent(self):
        from evaluation import mps_study,study
        directory=self.root/'worker'
        with patch('agents.mps_provider.local_json',side_effect=self.response):
            protocol=study.prepare(directory,provider='local_mps',concurrency=1,repetitions=1)
        counter=[]
        def report(_):return {'status':'completed' if len(counter)==2 else 'pilot_or_incomplete'}
        def advance(_,max_new_runs):
            self.assertEqual(max_new_runs,1);counter.append(1)
        def published(*args):return report(None)
        def status(_,p,state,error=None):return {'state':state}
        with patch.object(study,'report',side_effect=report),patch.object(study,'execute',side_effect=advance) as run,patch.object(mps_study,'publish',side_effect=published),patch.object(mps_study,'update_status',side_effect=status):
            self.assertEqual(mps_study.execute(directory,self.root/'public')['state'],'completed')
            self.assertEqual(run.call_count,2)
            self.assertEqual(mps_study.execute(directory,self.root/'public')['state'],'completed')
            self.assertEqual(run.call_count,2,'Completed slots must never run twice')

    def test_pilot_progress_reads_live_records_without_inference_or_export(self):
        from evaluation import study
        directory=self.root/'studies/pilot';public=self.root/'public';public.mkdir()
        with patch('agents.mps_provider.local_json',side_effect=self.response):
            protocol=study.prepare(directory,provider='local_mps',concurrency=1,repetitions=1,turn_budget=1)
            with patch('evaluation.study.DECISION_RUNS_DIR',self.root/'accounting'):study.execute(directory)
        first,second=[study.slot_path(directory,s) for s in protocol['schedule']]
        # An explicit offline fixture representing a flushed recording before run_end.
        first.write_bytes(b'\n'.join(first.read_bytes().splitlines()[:-1])+b'\n');second.unlink()
        (public/'pilot.protocol.json').write_text(json.dumps(protocol))
        (public/'index.json').write_text(json.dumps({'qwen_pilot':{'protocol_url':'/replays/pilot.protocol.json','sha256':protocol['sha256']}}))
        manager=RunManager(self.root,destination=public)
        with patch('agents.mps_provider.health',side_effect=AssertionError('Progress cannot call a model')):
            progress=manager.pilot_progress()
        self.assertTrue(progress['available']);self.assertEqual(progress['completed_runs'],0)
        self.assertEqual(progress['runs'][0]['status'],'recording')
        self.assertEqual(progress['runs'][0]['decision_count'],10)
        self.assertEqual(progress['runs'][1]['status'],'queued')
        self.assertEqual(list(public.glob('*.source.jsonl')),[],'Progress must not export changing recordings')

    def test_endpoint_cannot_send_prompts_to_remote_hosts_or_redirects(self):
        for value in ['https://example.com','http://192.168.1.2:8766','http://localhost:8766/decision',
                      'http://user:password@localhost:8766','http://localhost:8766?token=x']:
            with patch.dict('os.environ',{'SIMPLY_MPS_URL':value}):
                with self.assertRaises(ValueError):server_url()
        self.assertIsNone(NoRedirect().redirect_request(None,None,None,None,None,None))

    def test_archive_extracts_only_data_and_detects_tampered_local_weights(self):
        import zipfile,hashlib
        archive=self.root/'pilot.zip';template='offline-template'
        with zipfile.ZipFile(archive,'w') as z:
            z.writestr('experiment.json',json.dumps({'training_mode':'pilot',
                'base_model':'unsloth/Qwen2.5-7B-Instruct-bnb-4bit','base_revision':'a'*40,
                'chat_template_sha256':hashlib.sha256(template.encode()).hexdigest()}))
            z.writestr('adapter/adapter_config.json',json.dumps({'peft_type':'LORA','base_model_name_or_path':'unsloth/Qwen2.5-7B-Instruct-bnb-4bit'}))
            for name in ['adapter_model.safetensors','tokenizer.json','tokenizer_config.json']:
                z.writestr('adapter/'+name,b'OFFLINE FIXTURE')
            z.writestr('adapter/chat_template.jinja',template)
            z.writestr('adapter/../../escape.py','raise RuntimeError()')
        path,manifest=prepare_adapter(archive,self.root/'models')
        self.assertFalse((self.root/'escape.py').exists());self.assertEqual(manifest['training_mode'],'pilot')
        (path/'adapter_model.safetensors').write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError,'changed'):prepare_adapter(archive,self.root/'models')

    def test_loopback_http_rejects_origins_hosts_and_identity_mismatch(self):
        class Runtime:
            identity=IDENTITY
            def generate(self,prompt):return {'raw_response':'OFFLINE','identity':self.identity}
        server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(Runtime()));server.daemon_threads=True
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            with urlopen(base+'/health') as response:self.assertEqual(json.load(response)['status'],'ready')
            for headers in [{'Origin':'https://example.com'},{'Host':'example.com'}]:
                with self.assertRaises(urllib.error.HTTPError) as error:urlopen(Request(base+'/health',headers=headers))
                self.assertEqual(error.exception.code,403)
            body={'model':MODEL,'prompt':'OFFLINE','identity':{}}
            with self.assertRaises(urllib.error.HTTPError) as error:
                urlopen(Request(base+'/decision',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'}))
            self.assertEqual(error.exception.code,409)
        finally:server.shutdown();server.server_close();thread.join(2)


if __name__=='__main__':unittest.main()
