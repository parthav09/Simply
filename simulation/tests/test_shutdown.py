"""Stopping a run must not dispatch the queued remainder of a model round."""
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

SIMULATION_DIR=Path(__file__).resolve().parents[1]
if str(SIMULATION_DIR) not in sys.path:sys.path.insert(0,str(SIMULATION_DIR))
from agents.base import Decision
from agents.openai_provider import OpenAIProvider
from core.budget import CampaignLedger, RequestCancelledError
from core.run_log import read_run
from core.session import SimulationSession


class OfflineProvider(OpenAIProvider):
    provider_id='scripted_test'
    supports_action_plans=False


class ShutdownTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.folder=Path(self.temp.name);self.ledger=CampaignLedger(self.folder/'ledger.sqlite3')

    def test_cancelled_unpaced_requests_never_reserve_or_dispatch(self):
        provider=OfflineProvider(self.ledger,'OFFLINE-cancelled');provider.cancelled.set()
        with patch.dict(os.environ,{'OPENAI_API_KEY':'OFFLINE-not-a-real-key'}),patch('urllib.request.urlopen') as transport:
            with self.assertRaises(RequestCancelledError):provider.request('fixture',('move_right',),'C0001')
            with self.assertRaises(RequestCancelledError):self.ledger.acquire_slot(0,provider.cancelled)
        transport.assert_not_called();self.assertEqual(self.ledger.snapshot()['requests'],0)

    def test_stop_settles_inflight_work_and_prevents_the_queued_api_calls(self):
        entered=threading.Event();release=threading.Event();lock=threading.Lock();calls=[]
        def transport(request,timeout):
            with lock:
                calls.append(request)
                if len(calls)==2:entered.set()
            release.wait(2)
            allowed=json.loads(request.data)['text']['format']['schema']['properties']['step']['enum']
            action={'step':allowed[0],'product_id':'','reason':'OFFLINE shutdown fixture'}
            response={'model':'OFFLINE-shutdown','status':'completed',
                      'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(action)}]}],
                      'usage':{'input_tokens':100,'output_tokens':20,'total_tokens':120,
                               'input_tokens_details':{'cached_tokens':0,'cache_write_tokens':0},
                               'output_tokens_details':{'reasoning_tokens':0}}}
            return io.BytesIO(json.dumps(response).encode())
        provider=OfflineProvider(self.ledger,'OFFLINE-stop')
        session=SimulationSession(shopper_count=10,max_rounds=5,concurrency=2,decide=provider,output_path=self.folder/'trip.jsonl')
        with patch.dict(os.environ,{'OPENAI_API_KEY':'OFFLINE-not-a-real-key'}),patch('urllib.request.urlopen',side_effect=transport):
            session.start()
            try:
                self.assertTrue(entered.wait(2));session.stop()
            finally:
                release.set();session._thread.join(3)
        self.assertTrue(session.closed);self.assertEqual(len(calls),2)
        self.assertEqual(self.ledger.snapshot()['requests'],2)
        run=read_run(session.path)
        self.assertEqual(run['summary']['status'],'cancelled')
        self.assertEqual(len(run['events']),10)
        self.assertEqual(sum(e['telemetry'].get('cancelled',False) for e in run['events']),8)
        self.assertEqual(sum(e['outcome']=='applied' for e in run['events']),2)

    def test_keyboard_interrupt_cancels_queued_work_before_executor_shutdown(self):
        class InterruptProvider:
            model='scripted_test'
            cancelled=threading.Event()
            first=None
            calls=0
            def request(self,prompt,allowed_steps,shopper_id):
                self.calls+=1
                if shopper_id==self.first:raise KeyboardInterrupt()
                self.cancelled.wait(2)
                return Decision(allowed_steps[0],reason='OFFLINE settled request')
        provider=InterruptProvider()
        session=SimulationSession(shopper_count=15,max_rounds=5,concurrency=2,decide=provider,output_path=self.folder/'interrupt.jsonl')
        provider.first=session.shoppers[0].customer_id
        started=time.monotonic()
        with self.assertRaises(KeyboardInterrupt):session.run()
        self.assertLess(time.monotonic()-started,1)
        self.assertLessEqual(provider.calls,3);self.assertTrue(provider.cancelled.is_set())
        run=read_run(session.path)
        self.assertEqual(run['summary']['status'],'cancelled')
        self.assertEqual(run['events'],[])


if __name__=='__main__':unittest.main()
