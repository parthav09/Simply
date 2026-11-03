"""OpenRouter contracts, metering, frozen studies and replay; all HTTP is mocked."""
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agents.openrouter_provider import OpenRouterProvider,OpenRouterRequestError,MODEL_SLUGS,api_key,normalize_usage
from core.budget import CampaignLedger,usage_cost_micros
from core.run_log import read_run
from core.export_replay import build_bundle
from core.evidence import run_row
from core.session import SimulationSession
from live.protocol import LiveProjection
from evaluation import matrix,study


class OpenRouterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.key=patch('agents.openrouter_provider.api_key',return_value='OFFLINE-TEST-KEY');self.key.start();self.addCleanup(self.key.stop)
        self.ledger=CampaignLedger(self.root/'ledger.sqlite3',enforce_limit=False)

    @staticmethod
    def response(request,timeout=60):
        body=json.loads(request.data)
        step=body['response_format']['json_schema']['schema']['properties']['step']['enum'][0]
        return io.BytesIO(json.dumps({'id':'OFFLINE-RESPONSE','model':body['model'],'provider':'Phala' if body['model'].startswith('qwen/') else 'OpenAI',
            'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'step':step,'product_id':'','reason':'Explicit offline OpenRouter test'})}}],
            'usage':{'prompt_tokens':100,'completion_tokens':10,'total_tokens':110,
                'prompt_tokens_details':{'cached_tokens':20,'cache_write_tokens':0},
                'completion_tokens_details':{'reasoning_tokens':0},'cost':.000013}}).encode())

    def test_both_models_pin_endpoint_schema_and_disable_fallbacks_without_key_export(self):
        for model in MODEL_SLUGS:
            provider=OpenRouterProvider(self.ledger,'OFFLINE',model=model)
            with patch('urllib.request.urlopen',side_effect=self.response) as transport:
                result=provider.request('OFFLINE prompt',['move_left'],'profile')
            request=transport.call_args.args[0];body=json.loads(request.data)
            self.assertEqual(request.full_url,'https://openrouter.ai/api/v1/chat/completions')
            self.assertEqual(body['model'],MODEL_SLUGS[model]);self.assertFalse(body['provider']['allow_fallbacks'])
            self.assertEqual(body['provider']['only'],['phala'] if model=='qwen2.5-7b-instruct' else ['openai']);self.assertTrue(body['provider']['require_parameters'])
            if model=='qwen2.5-7b-instruct':
                self.assertNotIn('reasoning',body);self.assertNotIn('service_tier',body)
            self.assertTrue(body['response_format']['json_schema']['strict']);self.assertEqual(body['plugins'],[])
            self.assertNotIn('temperature',body);self.assertEqual(result.decision.step,'move_left')
            self.assertEqual(result.telemetry['provider_reported_cost_usd'],.000013)
            self.assertNotIn('OFFLINE-TEST-KEY',json.dumps(result.telemetry))
        self.assertEqual(self.ledger.snapshot()['requests'],len(MODEL_SLUGS))
        with self.assertRaisesRegex(ValueError,'no model substitution'):
            OpenRouterProvider(self.ledger,'OFFLINE',model='qwen/qwen3-4b-instruct-2507')

    def test_quota_error_is_not_retried_and_reservation_and_redaction_survive(self):
        error=urllib.error.HTTPError('https://openrouter.ai/api/v1/chat/completions',402,'No credits',{},
            io.BytesIO(json.dumps({'error':{'code':402,'message':'OFFLINE-TEST-KEY credits exhausted'}}).encode()))
        with patch('urllib.request.urlopen',side_effect=error) as transport:
            with self.assertRaises(OpenRouterRequestError) as caught:
                OpenRouterProvider(self.ledger,'OFFLINE').request('test',['move_left'],'one')
        self.assertEqual(transport.call_count,1);self.assertEqual(caught.exception.telemetry['provider_error_code'],'402')
        self.assertNotIn('OFFLINE-TEST-KEY',json.dumps(caught.exception.telemetry))
        self.assertGreater(self.ledger.snapshot()['unresolved_reserved_usd'],0)

    def test_serving_drift_is_accounted_but_not_applied(self):
        def wrong(request,timeout):
            payload=json.load(self.response(request));payload['provider']='Other'
            return io.BytesIO(json.dumps(payload).encode())
        with patch('urllib.request.urlopen',side_effect=wrong):
            with self.assertRaisesRegex(OpenRouterRequestError,'drift') as caught:
                OpenRouterProvider(self.ledger,'OFFLINE').request('test',['move_left'],'one')
        self.assertEqual(caught.exception.telemetry['provider_error_code'],'serving_identity_mismatch')
        self.assertIsNotNone(caught.exception.telemetry['estimated_cost_micros'])

    def test_generic_cache_writes_use_frozen_endpoint_price_without_inventing_ttl(self):
        self.assertIsNone(normalize_usage(None))
        usage={'prompt_tokens':100,'completion_tokens':10,'total_tokens':110,'prompt_tokens_details':{'cache_write_tokens':50}}
        normalized=normalize_usage(usage)
        self.assertEqual(normalized['cacheWriteTokenCount'],50)
        self.assertNotIn('cacheWrite30mTokenCount',normalized)
        self.assertEqual(usage_cost_micros(normalized,OpenRouterProvider(self.ledger,'OFFLINE').pricing),16)
        usage['prompt_tokens_details']={'cached_tokens':101}
        self.assertIsNone(normalize_usage(usage))

    def test_openrouter_session_live_export_and_report_keep_charges_separate(self):
        with patch('urllib.request.urlopen',side_effect=self.response):
            session=SimulationSession(provider_name='openrouter',shopper_count=10,max_rounds=1,
                allow_action_plans=False,output_path=self.root/'run.jsonl',ledger_path=self.ledger.path)
            session.run()
        run=read_run(session.path);row=run_row(session.path)
        self.assertEqual(row['kind'],'model');self.assertEqual(row['provider'],'openrouter')
        self.assertAlmostEqual(row['metrics']['provider_reported_cost_usd'],.00013)
        self.assertIsNone(row['metrics']['provider_reported_cost_per_checkout_usd'])
        projection=LiveProjection()
        for line in session.path.read_bytes().splitlines(keepends=True):projection.append(line)
        self.assertEqual(projection.snapshot(),json.loads(build_bundle(session.path)['payload_json']))
        self.assertNotIn('OFFLINE-TEST-KEY',session.path.read_text())
        self.assertEqual(run['summary']['resources']['unknown_provider_charge_requests'],0)

    def test_full_openrouter_matrix_uses_frozen_controls_and_explicit_pending_qwen(self):
        directory=self.root/'matrix';original=study.prepare
        def short(directory,**kwargs):return original(directory,**kwargs,turn_budget=1)
        with patch('evaluation.matrix.study.prepare',short):
            plan=matrix.prepare(directory,provider='openrouter',repetitions=1,requests_per_minute=0)
        with patch('urllib.request.urlopen',side_effect=self.response),patch('evaluation.study.DECISION_RUNS_DIR',self.root/'accounting'):
            result=matrix.execute(directory)
        self.assertEqual(result['status'],'completed');self.assertEqual(len(result['runs']),4)
        self.assertEqual(result['provider'],'openrouter');self.assertEqual(len(plan['pending_models']),2)
        self.assertTrue(all(r['provider']=='openrouter' for r in result['runs']))
        self.assertTrue(all('provider_reported_cost_usd' in r['metrics'] for r in result['runs']))
        self.assertTrue(all(len(c['profile_pairs'])==10 for c in result['comparisons']))

    def test_key_alias_is_supported_without_printing_or_copying_it(self):
        self.key.stop()
        with patch.dict(os.environ,{},clear=True),patch('agents.openrouter_provider.load_env_file',return_value={'OPEN_ROUTER_KEY':'OFFLINE-ALIAS'}):
            self.assertEqual(api_key(),'OFFLINE-ALIAS')

    def test_qwen_study_freezes_endpoint_and_preserves_paid_identity_drift(self):
        directory=self.root/'qwen'
        plan=study.prepare(directory,provider='openrouter',kind='layout',models=['qwen2.5-7b-instruct'],
            repetitions=1,turn_budget=1)
        self.assertEqual(len(plan['schedule']),2)
        for contract in plan['contracts'].values():
            self.assertEqual(contract['config']['generation']['provider']['only'],['phala'])
            self.assertEqual(contract['pricing']['serving_provider'],'Phala')
        with patch('urllib.request.urlopen',side_effect=self.response),patch('evaluation.study.DECISION_RUNS_DIR',self.root/'accounting'):
            result=study.execute(directory)
        self.assertEqual(result['status'],'completed')
        self.assertEqual(len(result['runs']),2)
        self.assertTrue(all(r['model_versions']==['qwen/qwen-2.5-7b-instruct'] for r in result['runs']))
        def wrong(request,timeout):
            payload=json.load(self.response(request));payload['provider']='Other'
            return io.BytesIO(json.dumps(payload).encode())
        with patch('urllib.request.urlopen',side_effect=wrong):
            with self.assertRaisesRegex(OpenRouterRequestError,'drift') as caught:
                OpenRouterProvider(self.ledger,'OFFLINE',model='qwen2.5-7b-instruct').request('test',['move_left'],'one')
        self.assertIsNotNone(caught.exception.telemetry['estimated_cost_micros'])


if __name__=='__main__':unittest.main()
