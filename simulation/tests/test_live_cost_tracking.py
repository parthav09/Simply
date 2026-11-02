"""Live runs track costs; explicit study budgets and terminal records stay honest."""
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agents.base import Decision,ProposalResult
from agents.openai_provider import OpenAIRequestError
from agents.openrouter_provider import OpenRouterRequestError
from core.budget import CampaignLedger,BudgetExhaustedError,read_ledger_snapshot
from core.run_log import read_run
from core.session import SimulationSession


class LiveCostTrackingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def test_tracking_only_preserves_ledger_and_can_record_usage_above_its_old_study_limit(self):
        path=self.root/'ledger.sqlite3';limited=CampaignLedger(path,limit_usd=.001)
        with self.assertRaises(BudgetExhaustedError):limited.reserve('OFFLINE','x'*10000)
        tracking=CampaignLedger(path,limit_usd=.001,enforce_limit=False)
        identifier,reserved=tracking.reserve('OFFLINE','x'*10000)
        self.assertGreater(reserved,1000)
        tracking.settle(identifier,{'promptTokenCount':10000,'candidatesTokenCount':100})
        snapshot=read_ledger_snapshot(path)
        self.assertGreater(snapshot['known_estimated_usd'],snapshot['limit_usd'])
        self.assertEqual(snapshot['requests'],1);self.assertEqual(snapshot['limit_usd'],.001)
        with self.assertRaises(BudgetExhaustedError):limited.reserve('OFFLINE','x')
        self.assertEqual(read_ledger_snapshot(path)['requests'],1)

    def test_standard_model_session_defaults_to_tracking_only_and_freezes_the_policy(self):
        class Provider:
            model=provider_id='scripted_test'
        with patch('agents.providers.build_provider',return_value=Provider()):
            session=SimulationSession(shopper_count=1,ledger_path=self.root/'ledger.sqlite3',output_path=self.root/'default.jsonl')
        self.assertFalse(session.ledger.enforce_limit)
        self.assertFalse(session.header['config']['api_budget_enforced'])
        session.finish('cancelled','OFFLINE no requests')
        with patch('agents.providers.build_provider',return_value=Provider()):
            opted=SimulationSession(shopper_count=1,enforce_api_budget=True,ledger_path=self.root/'ledger.sqlite3',output_path=self.root/'limited.jsonl')
        self.assertTrue(opted.ledger.enforce_limit)
        self.assertTrue(opted.header['config']['api_budget_enforced'])
        opted.finish('cancelled','OFFLINE no requests')

    def test_terminal_error_records_already_dispatched_work_before_closing(self):
        for name,error,status in [
            ('budget',BudgetExhaustedError('Campaign budget exhausted before request dispatch'),'budget_exhausted'),
            ('rate',OpenAIRequestError('OpenAI HTTP 429; reservation retained','OFFLINE-request',100),'aborted'),
            ('openrouter-credit',OpenRouterRequestError('OpenRouter HTTP 402; reservation retained','OFFLINE-request',100),'aborted'),
        ]:
            with self.subTest(name=name):
                entered=threading.Event();release=threading.Event()
                class Provider:
                    model=provider_id='scripted_test'
                    cancelled=threading.Event()
                    first=None
                    def request(self,prompt,allowed_steps,shopper_id):
                        if shopper_id==self.first:
                            entered.wait(2)
                            raise error
                        entered.set();release.wait(3)
                        decision=Decision(allowed_steps[0],reason='OFFLINE already-dispatched reply')
                        return ProposalResult(json.dumps(decision.to_dict()),decision,{
                            'request_submitted':True,'estimated_cost_micros':20,'usage':{'promptTokenCount':1}})
                provider=Provider()
                session=SimulationSession(shopper_count=2,max_rounds=2,concurrency=2,decide=provider,output_path=self.root/f'{name}.jsonl')
                provider.first=session.shoppers[0].customer_id;session.start()
                try:
                    self.assertTrue(entered.wait(2));self.assertTrue(provider.cancelled.wait(2))
                    self.assertFalse(session.closed,'Run ended while a dispatched reply was still pending')
                    self.assertEqual(session.control_status,'stopping')
                finally:release.set();session.join(4)
                self.assertTrue(session.closed)
                run=read_run(session.path)
                self.assertEqual(run['summary']['status'],status)
                self.assertEqual(len(run['events']),2)
                self.assertEqual(sum(e['outcome']=='applied' for e in run['events']),1)
                self.assertEqual(run['summary']['resources']['known_estimated_cost_usd'],.00002)
                self.assertFalse(session.coordinator.in_flight)
                if name=='budget':
                    self.assertEqual(run['summary']['resources']['unknown_cost_attempts'],0)
