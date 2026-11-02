"""Live records must match replay and arrive before slower shoppers finish."""
import copy
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

SIMULATION_DIR=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SIMULATION_DIR))
from agents.base import Decision
from agents.providers import FakeDecisionProvider
from core.export_replay import build_bundle
from core.session import SimulationSession
from core.run_log import read_run
from live.protocol import LiveProjection
from live.server import RunManager,handler_for
from http.server import ThreadingHTTPServer
from urllib.request import Request,urlopen
from urllib.error import HTTPError


class LiveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def test_all_golden_live_states_and_final_hash_match_saved_export(self):
        path=SIMULATION_DIR/'tests/fixtures/golden.jsonl';projection=LiveProjection()
        with patch('urllib.request.urlopen',side_effect=AssertionError('Replay must not call providers')):
            for line in path.read_bytes().splitlines(keepends=True):projection.append(line)
            payload=json.loads(build_bundle(path,allow_test=True)['payload_json'])
        self.assertEqual(projection.snapshot(),payload)
        with self.assertRaisesRegex(ValueError,'after run end'):projection.append(path.read_bytes().splitlines(keepends=True)[1])

    def test_invalid_or_unflushed_live_records_are_rejected(self):
        rows=(SIMULATION_DIR/'tests/fixtures/golden.jsonl').read_bytes().splitlines(keepends=True)
        p=LiveProjection()
        with self.assertRaisesRegex(ValueError,'Unflushed'):p.append(rows[0].rstrip(b'\n'))
        p.append(rows[0]);record=json.loads(rows[1]);record['sequence']=2
        with self.assertRaises(ValueError):p.append(json.dumps(record).encode()+b'\n')
        p.append(rows[1])
        with self.assertRaises(ValueError):p.append(rows[1])

    def test_fast_shopper_starts_next_request_before_slow_peer_finishes(self):
        slow=threading.Event();release=threading.Event();second_request=threading.Event()
        class Provider:
            model='scripted_test'
            first=None
            calls=[]
            def request(self,prompt,allowed_steps,shopper_id):
                self.calls.append(shopper_id)
                if shopper_id!=self.first:
                    slow.set();release.wait(3)
                if self.calls.count(self.first)==2:
                    second_request.set()
                return Decision(allowed_steps[0])
        provider=Provider();session=SimulationSession(shopper_count=2,max_rounds=2,decide=provider,output_path=self.root/'overlap.jsonl')
        provider.first=session.shoppers[0].customer_id
        session.start()
        try:
            self.assertTrue(slow.wait(2));self.assertTrue(second_request.wait(2))
            self.assertFalse(session.closed)
            self.assertGreaterEqual(provider.calls.count(provider.first),2)
        finally:release.set();session._thread.join(4)
        self.assertEqual(session.status,'completed')

    def test_first_commit_is_flushed_while_second_model_request_is_pending(self):
        slow=threading.Event();release=threading.Event();first_committed=threading.Event()
        class Provider:
            model='scripted_test'
            first=None
            def request(self,prompt,allowed_steps,shopper_id):
                if shopper_id!=self.first:slow.set();release.wait(3)
                return Decision(allowed_steps[0])
        provider=Provider();session=SimulationSession(shopper_count=2,max_rounds=1,decide=provider,output_path=self.root/'trip.jsonl')
        provider.first=session.shoppers[0].customer_id;original=session._record
        def record(event,number):
            original(event,number);first_committed.set()
        session._record=record
        session.start()
        try:
            self.assertTrue(slow.wait(2));self.assertTrue(first_committed.wait(2))
            run=read_run(session.path)
            self.assertEqual(len(run['events']),1);self.assertFalse(session.closed)
            self.assertEqual(run['events'][0]['agent_id'],provider.first)
        finally:release.set();session._thread.join(4)
        self.assertEqual(session.status,'completed')

    def test_pause_reports_pending_round_and_single_advance_requires_settled_pause(self):
        entered=threading.Event();release=threading.Event()
        def decide(prompt,allowed):
            entered.set();release.wait(3);return Decision(allowed[0])
        manager=RunManager(self.root,True)
        session=SimulationSession(shopper_count=1,max_rounds=3,decide=decide,output_path=self.root/'pause.jsonl')
        manager.sessions[session.run_id]=session;session.start()
        try:
            self.assertTrue(entered.wait(2));manager.control(session.run_id,'pause')
            self.assertEqual(manager.state(session.run_id)['status'],'pausing')
            with self.assertRaisesRegex(ValueError,'current round'):manager.control(session.run_id,'advance')
            release.set()
            import time
            deadline=time.monotonic()+2
            while session.control_status!='paused' and time.monotonic()<deadline:time.sleep(.01)
            self.assertEqual(session.rounds_completed,1)
            self.assertEqual(manager.state(session.run_id)['status'],'paused')
        finally:release.set();session.stop();session.join(3)

    def test_http_snapshot_reconnect_and_export_never_restart_provider(self):
        manager=RunManager(self.root,True,self.root/'published')
        session=SimulationSession(shopper_count=2,max_rounds=2,decide=FakeDecisionProvider(),output_path=self.root/'trip.jsonl');session.run()
        server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(manager));server.daemon_threads=True
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            for _ in range(2):
                with urlopen(base+f'/runs/{session.run_id}/events',timeout=5) as response:
                    text=response.read().decode()
                self.assertIn('event: snapshot',text)
                payload=json.loads(next(line[6:] for line in text.splitlines() if line.startswith('data: ')))
                self.assertEqual(payload['run']['final']['sequence'],4)
            self.assertEqual(manager.sessions,{})
            request=Request(base+f'/runs/{session.run_id}/export',data=b'{}',headers={'Content-Type':'application/json'})
            with urlopen(request,timeout=5) as response:self.assertIn('/replays/',json.load(response)['url'])
            request=Request(base+'/runs',data=b'{}',headers={'Content-Type':'application/json','Origin':'https://untrusted.example'})
            with self.assertRaises(HTTPError) as error:urlopen(request,timeout=5)
            self.assertEqual(error.exception.code,403)
        finally:server.shutdown();server.server_close();thread.join(2)

    def test_live_launch_scope_and_offline_provider_are_explicit(self):
        manager=RunManager(self.root)
        for body in ({'shoppers':9},{'provider':'fake'},{'layout':'back_destination'},{'model':'other'}):
            with self.assertRaises(ValueError):manager.create(body)

    def test_preview_has_matching_inputs_without_creating_a_run_or_provider(self):
        manager=RunManager(self.root)
        with patch('agents.providers.build_provider',side_effect=AssertionError('Preview cannot construct a provider')):
            preview=manager.preview('neighborhood_express',10,'gpt-6.1-terra')
        self.assertEqual(preview['source']['provider'],'not-started')
        self.assertEqual(preview['source']['model'],'gpt-6.1-terra')
        self.assertEqual(len(preview['shoppers']),10)
        self.assertEqual(preview['events'],[])
        self.assertEqual(list(self.root.iterdir()),[])
        with self.assertRaises(ValueError):manager.preview('back_destination',10,'gpt-6-luna')

    def test_live_model_choice_reaches_the_core_session(self):
        manager=RunManager(self.root)
        with patch('live.server.SimulationSession') as constructor:
            constructor.return_value.run_id='OFFLINE-fixture'
            constructor.return_value.control_status='running'
            manager.create({'layout':'costco_back_anchor','shoppers':10,'model':'gpt-6.1-terra'})
        self.assertEqual(constructor.call_args.kwargs['model_name'],'gpt-6.1-terra')
        constructor.return_value.start.assert_called_once()

    def test_http_stream_delivers_commit_before_run_finishes(self):
        release_first=threading.Event();release_second=threading.Event()
        class Provider:
            model='scripted_test'
            first=None
            def request(self,prompt,allowed_steps,shopper_id):
                (release_first if shopper_id==self.first else release_second).wait(5)
                return Decision(allowed_steps[0])
        provider=Provider();manager=RunManager(self.root,True)
        session=SimulationSession(shopper_count=2,max_rounds=1,decide=provider,output_path=self.root/'stream.jsonl')
        provider.first=session.shoppers[0].customer_id
        manager.sessions[session.run_id]=session;session.start()
        server=ThreadingHTTPServer(('127.0.0.1',0),handler_for(manager));server.daemon_threads=True
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def receive(response):
            block=[]
            while True:
                line=response.readline().decode()
                if line=='\n':return '\n'.join(block)
                if not line:raise AssertionError('Stream ended before the expected commit')
                block.append(line.rstrip('\n'))
        try:
            with urlopen(f'http://127.0.0.1:{server.server_port}/runs/{session.run_id}/events',timeout=4) as response:
                self.assertIn('event: snapshot',receive(response))
                release_first.set();message=receive(response)
                self.assertIn('event: transition',message)
                payload=json.loads(next(line[6:] for line in message.splitlines() if line.startswith('data: ')))
                self.assertEqual(payload['frame']['sequence'],1)
                self.assertEqual(len(read_run(session.path)['events']),1)
                self.assertFalse(session.closed)
        finally:
            release_first.set();release_second.set();session._thread.join(3)
            server.shutdown();server.server_close();thread.join(2)


if __name__=='__main__':unittest.main()
