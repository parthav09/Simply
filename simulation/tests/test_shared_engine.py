"""Authoritative execution, costs, controls, evidence and architecture acceptance."""
import ast
import copy
import io
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

SIMULATION_DIR=Path(__file__).resolve().parents[1]
if str(SIMULATION_DIR) not in sys.path:sys.path.insert(0,str(SIMULATION_DIR))
from agents.base import Decision,ProposalResult
from agents.llm import GeminiProvider
from agents.providers import FakeDecisionProvider
from core.accounting import basket,cents
from core.budget import CampaignLedger,BudgetExhaustedError,usage_cost_micros
from core.export_replay import build_bundle,export_run
from core.grid import LAYOUTS, build_store
from core.metrics import loop_metrics
from core.recording import RecordingView
from core.run_log import read_run,RunLogError
from core.session import SimulationSession
from evaluation.benchmark import prepare,instantiate_benchmark,reference_turns
from evaluation.run import compatible,bootstrap
from build_golden import build


class SharedEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.folder=Path(self.temp.name)

    def session(self,**kwargs):
        defaults=dict(shopper_count=2,max_rounds=3,decide=FakeDecisionProvider(),output_path=self.folder/'trip.jsonl')
        defaults.update(kwargs);return SimulationSession(**defaults)

    def test_prompt_rejection_consumes_a_turn_then_requests_a_new_observation(self):
        from agents.openai_provider import OpenAIRequestError
        calls=[]
        def decide(prompt,allowed):
            calls.append(prompt)
            if len(calls)==1:
                raise OpenAIRequestError('OpenAI HTTP 400; reservation retained, no automatic retry','OFFLINE-error',10,
                                         {'provider_error_code':'invalid_prompt'})
            return Decision(allowed[0])
        session=self.session(shopper_count=1,max_rounds=2,decide=decide)
        session.run();run=read_run(session.path)
        self.assertEqual(session.status,'completed');self.assertEqual(len(calls),2)
        self.assertNotEqual(calls[0],calls[1])
        self.assertEqual([e['outcome'] for e in run['events']],['provider_exception','applied'])
        self.assertEqual([e['after']['turns_used'] for e in run['events']],[1,2])
        self.assertEqual(run['summary']['failures']['provider_exception'],1)

    def test_configuration_and_quota_rejections_still_stop_future_rounds(self):
        from agents.openai_provider import OpenAIRequestError
        for status,code in ((400,'invalid_json_schema'),(400,None),(401,'invalid_prompt'),(403,'access_denied'),(404,'model_not_found'),(429,'rate_limit_exceeded')):
            with self.subTest(status=status,code=code):
                calls=[]
                def decide(prompt,allowed):
                    calls.append(prompt)
                    raise OpenAIRequestError(f'OpenAI HTTP {status}; reservation retained, no automatic retry','OFFLINE-error',10,{'provider_error_code':code})
                session=self.session(shopper_count=1,max_rounds=3,decide=decide,output_path=self.folder/f'{status}-{code}.jsonl')
                session.run()
                self.assertEqual(session.status,'aborted');self.assertEqual(len(calls),1)
                self.assertEqual(read_run(session.path)['summary']['turns_used'],1)

    def test_informed_move_destinations_match_actions_applied_by_core(self):
        initial=self.session(shopper_count=1,max_rounds=1,output_path=self.folder/'observation.jsonl')
        shopper=initial.shoppers[0]
        prompt=shopper.prompt(initial.grid.observe(shopper))
        facts=json.loads(prompt.split('Current state: ',1)[1].split('\nChoose one step:',1)[0])
        initial.finish('cancelled','Offline observation fixture')
        self.assertTrue(facts['legal_move_destinations'])
        for step,destination in facts['legal_move_destinations'].items():
            with self.subTest(step=step):
                session=self.session(shopper_count=1,max_rounds=1,decide=lambda prompt,allowed:Decision(step),output_path=self.folder/f'{step}.jsonl')
                session.run();after=read_run(session.path)['events'][0]['after']
                self.assertEqual([after['x'],after['y']],destination)

    def test_worker_and_command_session_use_identical_business_transitions(self):
        a=self.session();a.run()
        b=self.session(output_path=self.folder/'thread.jsonl');b.start();b._thread.join(5)
        self.assertTrue(b.closed)
        x,y=read_run(a.path),read_run(b.path)
        self.assertEqual(x['end']['shoppers'],y['end']['shoppers'])
        fields=('sequence','agent_id','before','after','action','outcome','failure')
        self.assertEqual([{k:e[k] for k in fields} for e in x['events']],[{k:e[k] for k in fields} for e in y['events']])

    def test_pause_single_step_and_stop_do_not_schedule_hidden_requests(self):
        started=threading.Event();release=threading.Event();calls=[]
        def decide(prompt,allowed):
            calls.append(1);started.set();release.wait(3);return Decision(allowed[0])
        session=self.session(decide=decide,shopper_count=1,max_rounds=10)
        session.start(paused=True)
        time.sleep(.03);self.assertEqual(calls,[])
        session.advance();self.assertTrue(started.wait(1))
        session.pause();release.set()
        deadline=time.monotonic()+2
        while session.rounds_completed<1 and time.monotonic()<deadline:time.sleep(.005)
        time.sleep(.03);self.assertEqual(len(calls),1)
        session.stop();session._thread.join(2)
        self.assertTrue(session.closed)
        loaded=read_run(session.path)
        self.assertEqual(loaded['summary']['status'],'cancelled');self.assertEqual(len(loaded['events']),1)

    def test_valid_unwise_decisions_are_not_replaced_and_accounting_is_exact(self):
        path=build(self.folder);run=read_run(path);row=run['summary']['shoppers'][0]
        price=cents(run['start']['catalogue'][next(i for i,p in enumerate(run['start']['catalogue']) if p['id']==run['start']['shoppers'][0]['customer']['shopping_list'][0]['product_id'])]['price'])
        self.assertEqual(row['fulfilled_units'],2)
        self.assertEqual(row['basket_cents'],2*price)
        self.assertEqual(row['checkout_spend_cents'],2*price)
        self.assertEqual(row['overshoot_cents'],2*price-1)
        self.assertEqual(row['max_basket_overshoot_cents'],3*price-1)
        self.assertEqual(row['above_acceptable_price_purchases'],3)
        self.assertEqual(run['summary']['sales_cents'],2*price)
        self.assertFalse(run['summary']['shoppers'][1]['finished'])
        self.assertEqual(run['summary']['shoppers'][1]['checkout_spend_cents'],0)
        self.assertEqual(run['summary']['failures'],{'invalid_decision':1,'provider_exception':1,'grid_rejected':1})
        for e in run['events']:
            if e['outcome']=='applied':self.assertEqual(e['action']['step'],json.loads(e['raw_response'])['step'])

    def test_export_rejects_fake_and_partial_without_explicit_flags(self):
        session=self.session();session.run()
        with self.assertRaisesRegex(ValueError,'Non-Gemini'):build_bundle(session.path)
        target=export_run(session.path,self.folder/'public',allow_test=True)
        payload=json.loads(json.loads(target.read_text())['payload_json'])
        self.assertEqual(payload['source']['provider'],'fake')
        self.assertEqual(payload['final']['summary'],read_run(session.path)['summary'])
        cancelled=self.session(output_path=self.folder/'cancelled.jsonl');cancelled.stop();cancelled.run()
        with self.assertRaisesRegex(ValueError,'Partial'):build_bundle(cancelled.path,allow_test=True)
        self.assertEqual(json.loads(build_bundle(cancelled.path,True,True)['payload_json'])['source']['status'],'cancelled')

    def test_pure_replay_and_bundle_do_not_load_current_data(self):
        path=build(self.folder)
        script="""
import builtins,sys,urllib.request
from pathlib import Path
original_open=builtins.open
def read(file,*args,**kwargs):
    if str(file).endswith(('.csv','.env')):raise AssertionError('current data read')
    return original_open(file,*args,**kwargs)
builtins.open=read
urllib.request.urlopen=lambda *a,**k:(_ for _ in ()).throw(AssertionError('network'))
sys.path.insert(0,'simulation')
from core.export_replay import build_bundle
bundle=build_bundle(sys.argv[1],allow_test=True)
assert 'core.grid' not in sys.modules and 'agents.llm' not in sys.modules
print(len(bundle['payload_json']))
"""
        result=subprocess.run([sys.executable,'-c',script,str(path)],cwd=SIMULATION_DIR.parent,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_primary_launcher_runs_and_replays_without_desktop_or_network(self):
        path=self.folder/'cli.jsonl'
        # Prohibit both model access and UI imports, rather than relying on
        # a display being absent on the machine running this check.
        script="""
import builtins,runpy,sys,urllib.request
original_import=builtins.__import__
def import_module(name,*args,**kwargs):
    if name.split('.')[0] in ('pygame','pyray','tkinter','ui'):
        raise AssertionError('desktop import')
    return original_import(name,*args,**kwargs)
builtins.__import__=import_module
urllib.request.urlopen=lambda *a,**k:(_ for _ in ()).throw(AssertionError('network'))
path=sys.argv[1]
sys.argv=['simulation/main.py','--provider','fake','--shoppers','2','--max-rounds','2','--output',path]
runpy.run_path('simulation/main.py',run_name='__main__')
sys.argv=['simulation/main.py','--replay',path]
runpy.run_path('simulation/main.py',run_name='__main__')
"""
        result=subprocess.run([sys.executable,'-c',script,str(path)],cwd=SIMULATION_DIR.parent,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        run=read_run(path)
        self.assertEqual(run['start']['provider'],'fake')
        self.assertEqual(len(run['events']),4)
        self.assertIn('Saved run:',result.stdout)

    def test_early_version_two_keeps_original_token_metric_shape(self):
        # Before cache-write telemetry was added, version-two records used
        # four usage fields. Their saved summaries remain verifiable.
        path=SIMULATION_DIR/'tests/fixtures/golden.jsonl'
        run=read_run(path)
        self.assertEqual(run['start']['schema_version'],2)
        self.assertNotIn('metrics_version',run['start'])
        self.assertEqual(set(run['summary']['resources']['usage']),{
            'promptTokenCount','candidatesTokenCount','cachedContentTokenCount','thoughtsTokenCount'})

    def test_integrity_rejects_catalogue_and_applied_state_tampering(self):
        path=build(self.folder);rows=[json.loads(line) for line in path.read_text().splitlines()]
        rows[0]['catalogue'][0]['price']+=1
        changed=self.folder/'bad.jsonl';changed.write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
        with self.assertRaisesRegex(RunLogError,'fingerprint'):read_run(changed)
        rows=[json.loads(line) for line in path.read_text().splitlines()]
        rows[1]['after']['x']+=1
        changed.write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
        with self.assertRaises(RunLogError):read_run(changed)

    def test_canonical_off_list_purchase_and_unknown_remove(self):
        session=self.session(shopper_count=1);s=session.shoppers[0];grid=session.grid
        product=next(p for p in grid.products.values() if p['id'] not in {i.product_id for i in s.customer.shopping_list})
        s.state.x,s.state.y=grid.stand_cells_for((product['x'],product['y']))[0];grid.refresh(s)
        self.assertTrue(grid.apply(s,Decision('grab',product['id'])))
        self.assertEqual(s.state.cart[0].product_id,product['id'])
        before=copy.deepcopy(s.state.cart)
        self.assertFalse(grid.apply(s,Decision('remove','not-owned')))
        self.assertEqual(s.state.cart,before)
        session.finish('aborted','direct fixture mutation')

    def test_baseline_frozen_and_informed_contains_decision_information(self):
        from agents.prompts import baseline_prompt
        session=self.session();s=session.shoppers[0]
        s.prompt_variant='baseline';self.assertEqual(s.prompt(),baseline_prompt(s))
        s.prompt_variant='informed';prompt=s.prompt()
        for field in ('unit_price_cents','quantity','remaining_budget_cents','recent_actions','checkout_cells','blocked_cells'):
            # Initial position may have no grabbable products, so price fields
            # become available after standing beside an actual shelf.
            if field=='unit_price_cents':continue
            self.assertIn(field,prompt)
        p=next(iter(session.grid.products.values()));s.state.x,s.state.y=session.grid.stand_cells_for((p['x'],p['y']))[0]
        self.assertIn('unit_price_cents',s.prompt(session.grid.observe(s)))
        session.finish('aborted','direct fixture mutation')

    def test_loops_detect_oscillation_without_misclassifying_productive_revisits(self):
        session=self.session(shopper_count=1,max_rounds=8);session.run();run=read_run(session.path)
        self.assertGreater(loop_metrics(run['events'])['loop_detections'],0)
        events=copy.deepcopy(run['events'])
        for i,e in enumerate(events):e['after']['cart']=[{'product_id':'new','quantity':i+1}]
        self.assertEqual(loop_metrics(events)['loop_detections'],0)

    def test_frozen_feasible_cohort_and_shared_starts(self):
        b=prepare(self.folder/'benchmark.json')
        self.assertEqual(len(b['customers']),15)
        self.assertEqual(tuple(b['layouts']),tuple(LAYOUTS))
        self.assertEqual(len({c['shopping_style'] for c in b['customers'][:3]}),3)
        for layout in LAYOUTS:
            grid=build_store(layout);shoppers=instantiate_benchmark(b,15,grid)
            for s,cell in zip(shoppers,b['starting_cells']):
                self.assertEqual([s.state.x,s.state.y],cell)
                self.assertLessEqual(reference_turns(grid,s.customer.shopping_list,tuple(cell)),96)
                total=sum(cents(grid.products[i.product_id]['price'])*i.quantity for i in s.customer.shopping_list)
                self.assertLessEqual(total,cents(s.customer.budget_per_trip_usd)*80//100)

    def test_budget_reservations_are_atomic_and_unknown_usage_is_not_refunded(self):
        ledger=CampaignLedger(self.folder/'budget.sqlite3',limit_usd=.01)
        def reserve(_):
            try:return ledger.reserve('test','x'*1000)
            except BudgetExhaustedError:return None
        with ThreadPoolExecutor(max_workers=8) as pool:results=list(pool.map(reserve,range(20)))
        self.assertTrue(any(r is not None for r in results))
        self.assertLessEqual(ledger.snapshot()['unresolved_reserved_usd'],.01)
        reserved=ledger.snapshot()['unresolved_reserved_usd']
        request_id=next(r[0] for r in results if r)
        ledger.settle(request_id,None)
        self.assertEqual(ledger.snapshot()['unresolved_reserved_usd'],reserved)
        self.assertIsNone(usage_cost_micros(None))
        self.assertEqual(usage_cost_micros({'promptTokenCount':1000,'candidatesTokenCount':100,'thoughtsTokenCount':20,'cachedContentTokenCount':100}),573)

    def test_metered_provider_records_real_usage_and_seed_and_does_not_retry(self):
        ledger=CampaignLedger(self.folder/'provider.sqlite3')
        provider=GeminiProvider(ledger,'test',42)
        raw=json.dumps({'step':'move_left','reason':'recorded'})
        response=json.dumps({'candidates':[{'content':{'parts':[{'text':raw}]}}],
             'usageMetadata':{'promptTokenCount':100,'candidatesTokenCount':20},'modelVersion':'tested-version'}).encode()
        with patch('agents.llm.load_env_file',return_value={'GEMINI_API_KEY':'test-key'}),patch('urllib.request.urlopen',return_value=io.BytesIO(response)) as transport:
            result=provider.request('prompt',('move_left',),'C0001')
        self.assertEqual(transport.call_count,1)
        self.assertEqual(result.telemetry['usage']['promptTokenCount'],100)
        self.assertEqual(result.telemetry['estimated_cost_micros'],80)
        self.assertEqual(result.telemetry['model_version'],'tested-version')
        self.assertEqual(ledger.snapshot()['unresolved_reserved_usd'],0)

    def test_legacy_reader_preserves_original_metric_shape(self):
        path=build(self.folder);rows=[json.loads(line) for line in path.read_text().splitlines()]
        rows[0]['schema_version']=1
        from core.run_log import summarize
        rows[-1]['summary']=summarize(rows[0],rows[1:-1],rows[-1]['shoppers'])
        legacy=self.folder/'legacy.jsonl';legacy.write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
        loaded=read_run(legacy)
        self.assertNotIn('sales_cents',loaded['summary'])
        self.assertEqual(loaded['summary']['mean_list_completion'],.5)

    def test_compare_guards_and_bootstrap(self):
        a=self.session();a.run();left=read_run(a.path)
        b=self.session(output_path=self.folder/'b.jsonl',layout_name='neighborhood_express');b.run();right=read_run(b.path)
        compatible(left,right)
        right['start']['config']['seed']+=1
        with self.assertRaisesRegex(ValueError,'settings'):compatible(left,right)
        self.assertIsNone(bootstrap([1,2]))
        self.assertEqual(bootstrap([1,1,1,1,1]),[1,1])

    def test_core_and_active_website_obey_dependency_rules(self):
        for path in (SIMULATION_DIR/'core').glob('*.py'):
            tree=ast.parse(path.read_text())
            for node in ast.walk(tree):
                imports=[a.name for a in node.names] if isinstance(node,ast.Import) else [node.module or ''] if isinstance(node,ast.ImportFrom) else []
                self.assertFalse(any(n.split('.')[0] in ('pygame','tkinter','ui','landing') for n in imports),str(path))
        for root in ('app','ui','site','lib'):
            for path in (SIMULATION_DIR.parent/'landing'/root).rglob('*'):
                if path.suffix in ('.ts','.tsx'):
                    for forbidden in ('stepAgent','spawnAgents','runLayoutBenchmark','tryImpulseGrab'):
                        self.assertNotIn(forbidden,path.read_text(),str(path))

class ProductScopeTests(unittest.TestCase):
    def test_two_layouts_support_ten_and_fifteen_independent_shoppers(self):
        self.assertEqual(tuple(LAYOUTS),('costco_back_anchor','neighborhood_express'))
        with tempfile.TemporaryDirectory() as folder:
            for layout in LAYOUTS:
                for count in (10,15):
                    session=SimulationSession(layout,shopper_count=count,max_rounds=1,decide=FakeDecisionProvider(),output_path=Path(folder)/f'{layout}-{count}.jsonl')
                    session.run();run=read_run(session.path)
                    self.assertEqual(len(run['events']),count)
                    self.assertEqual(len({s['agent_id'] for s in run['end']['shoppers']}),count)
                    self.assertEqual(run['summary']['shopper_count'],count)
            with self.assertRaises(ValueError):build_store('back_destination')
            with self.assertRaises(ValueError):SimulationSession(shopper_count=16)

    def test_reports_use_frozen_layout_scope_and_keep_legacy_scope(self):
        from evaluation.run import make_report
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            manifest={'study_id':'scope-fixture','benchmark_sha256':'fixture','provider':'fake',
                      'ledger':str(root/'ledger.sqlite3'),'attempts':[],
                      'layouts':list(LAYOUTS),'requested_shopper_count':15}
            (root/'campaign.json').write_text(json.dumps(manifest))
            report=make_report(root)
            self.assertEqual([a['layout_id'] for a in report['arms']],list(LAYOUTS))
            self.assertEqual(report['cohort_size'],15)
            self.assertEqual(report['status'],'pilot_or_incomplete')
            del manifest['layouts'];del manifest['requested_shopper_count']
            (root/'campaign.json').write_text(json.dumps(manifest))
            self.assertEqual(len(make_report(root)['arms']),3)


class LunaProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.folder=Path(self.temp.name)

    def test_terra_selection_uses_terra_request_identity_and_prices(self):
        from agents.openai_provider import OpenAIProvider
        ledger=CampaignLedger(self.folder/'terra.sqlite3');provider=OpenAIProvider(ledger,'terra-fixture',model='gpt-6.1-terra')
        payload={'model':'gpt-6.1-terra','status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'{"step":"move_left","product_id":"","reason":"fixture"}'}]}],
                 'usage':{'input_tokens':100,'output_tokens':20,'total_tokens':120,'input_tokens_details':{'cached_tokens':0,'cache_write_tokens':0},'output_tokens_details':{'reasoning_tokens':0}}}
        with patch.dict(os.environ,{},clear=True),patch('agents.openai_provider.load_env_file',return_value={'OPENAI_API_KEY':'fixture-key'}),patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(payload).encode())) as transport:
            result=provider.request('fixture',('move_left',),'C0001')
        self.assertEqual(json.loads(transport.call_args.args[0].data)['model'],'gpt-6.1-terra')
        self.assertEqual(result.telemetry['model_version'],'gpt-6.1-terra')
        self.assertEqual(result.telemetry['estimated_cost_micros'],200)
        self.assertEqual(OpenAIProvider(ledger,'luna-fixture').pricing['input_usd_per_million'],.1)
        self.assertEqual(provider.pricing['input_usd_per_million'],1)
        with self.assertRaises(ValueError):OpenAIProvider(ledger,'bad',model='unsupported')

    def test_session_records_selected_model_and_pricing_before_any_requests(self):
        session=SimulationSession(shopper_count=2,max_rounds=1,model_name='gpt-6.1-terra',output_path=self.folder/'terra.jsonl',ledger_path=self.folder/'ledger.sqlite3')
        session.finish('cancelled','Explicit offline contract test')
        run=read_run(session.path)
        self.assertEqual(run['start']['model'],'gpt-6.1-terra')
        self.assertEqual(run['start']['pricing']['output_usd_per_million'],5)
        self.assertEqual(run['events'],[])

    def test_luna_uses_explicit_model_strict_schema_and_actual_usage(self):
        from agents.openai_provider import OpenAIProvider
        ledger=CampaignLedger(self.folder/'ledger.sqlite3')
        provider=OpenAIProvider(ledger,'luna-fixture')
        action={'step':'move_left','product_id':'','reason':'Fixture only'}
        payload={'id':'response-fixture','model':'gpt-6-luna','status':'completed',
                 'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(action)}]}],
                 'usage':{'input_tokens':1000,'output_tokens':40,'total_tokens':1040,
                          'input_tokens_details':{'cached_tokens':100,'cache_write_tokens':200,
                             'cache_write_tokens_details':{'ttl_30m_tokens':100,'ttl_12h_tokens':100}},
                          'output_tokens_details':{'reasoning_tokens':0}}}
        with patch('agents.openai_provider.load_env_file',return_value={'OPENAI_API_KEY':'fixture-key'}),patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(payload).encode())) as transport:
            result=provider.request('fixture',('move_left',),'C0001')
        self.assertEqual(transport.call_count,1)
        request=transport.call_args.args[0];body=json.loads(request.data)
        self.assertEqual(body['model'],'gpt-6-luna');self.assertEqual(body['reasoning'],{'effort':'none'})
        self.assertFalse(body['store']);self.assertNotIn('seed',body)
        self.assertEqual(body['prompt_cache_options'],{'ttl':'30m'})
        self.assertTrue(body['text']['format']['strict'])
        self.assertFalse(body['text']['format']['schema']['additionalProperties'])
        self.assertEqual(result.decision,Decision('move_left',reason='Fixture only'))
        self.assertEqual(result.telemetry['estimated_cost_micros'],128)
        self.assertEqual(result.telemetry['usage']['cacheWrite12hTokenCount'],100)
        self.assertEqual(ledger.snapshot()['unresolved_reserved_usd'],0)

    def test_cache_write_split_uses_explicit_request_lifetime_only(self):
        from agents.openai_provider import normalize_usage
        usage={'input_tokens':1511,'input_tokens_details':{'cache_write_tokens':1508,'cached_tokens':0},
               'output_tokens':34,'output_tokens_details':{'reasoning_tokens':0},'total_tokens':1545}
        self.assertIsNone(normalize_usage(usage))
        normalized=normalize_usage(usage,requested_cache_ttl='30m')
        self.assertEqual(normalized['cacheWrite30mTokenCount'],1508)
        self.assertEqual(normalized['cacheWrite12hTokenCount'],0)
        self.assertIsNone(normalize_usage(usage,requested_cache_ttl='12h'))
        usage['input_tokens_details']['cache_write_tokens_details']={'ttl_30m_tokens':1}
        self.assertIsNone(normalize_usage(usage,requested_cache_ttl='30m'))

    def test_provider_rejection_keeps_diagnostic_without_credentials_or_retry(self):
        import urllib.error
        from agents.openai_provider import OpenAIProvider,OpenAIRequestError
        ledger=CampaignLedger(self.folder/'rejection.sqlite3');provider=OpenAIProvider(ledger,'rejected')
        body=json.dumps({'error':{'code':'invalid_prompt','type':'invalid_request_error',
                                 'message':'Rejected fixture-key input','param':'input'}}).encode()
        error=urllib.error.HTTPError('https://api.openai.com/v1/responses',400,'Bad request',{},io.BytesIO(body))
        with patch('agents.openai_provider.load_env_file',return_value={'OPENAI_API_KEY':'fixture-key'}),patch.dict(os.environ,{},clear=True),patch('urllib.request.urlopen',side_effect=error) as transport:
            with self.assertRaises(OpenAIRequestError) as caught:provider.request('fixture',('move_left',),'C0001')
        self.assertEqual(transport.call_count,1)
        self.assertEqual(caught.exception.telemetry['provider_error_message'],'Rejected [redacted] input')
        self.assertEqual(caught.exception.telemetry['provider_error_param'],'input')
        self.assertIsNone(caught.exception.telemetry['estimated_cost_micros'])
        self.assertGreater(ledger.snapshot()['unresolved_reserved_usd'],0)

    def test_unknown_or_incomplete_response_never_fabricates_usage_or_action(self):
        from agents.openai_provider import normalize_usage,OpenAIProvider
        self.assertIsNone(normalize_usage({'input_tokens':10,'output_tokens':2,'total_tokens':12}))
        ledger=CampaignLedger(self.folder/'unknown.sqlite3');provider=OpenAIProvider(ledger,'incomplete')
        payload={'model':'gpt-6-luna','status':'incomplete','output':[{'type':'message','content':[{'type':'output_text','text':'{"step":"move_left","reason":"partial"}'}]}]}
        with patch('agents.openai_provider.load_env_file',return_value={'OPENAI_API_KEY':'fixture-key'}),patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(payload).encode())):
            result=provider.request('fixture',('move_left',),'C0001')
        self.assertIsNone(result.decision);self.assertIsNone(result.telemetry['usage'])
        self.assertIsNone(result.telemetry['estimated_cost_micros'])
        self.assertGreater(ledger.snapshot()['unresolved_reserved_usd'],0)

    def test_missing_openai_key_is_fatal_before_mutation(self):
        from agents.openai_provider import MissingOpenAIApiKeyError
        with patch.dict(os.environ,{},clear=True),patch('agents.openai_provider.load_env_file',return_value={}):
            s=SimulationSession(shopper_count=2,max_rounds=2,output_path=self.folder/'missing.jsonl',ledger_path=self.folder/'ledger.sqlite3')
            with self.assertRaises(MissingOpenAIApiKeyError):s.run()
        loaded=read_run(s.path)
        self.assertEqual(loaded['start']['provider'],'openai');self.assertEqual(loaded['start']['model'],'gpt-6-luna')
        self.assertEqual(loaded['events'],[]);self.assertEqual(loaded['summary']['turns_used'],0)
        self.assertEqual(loaded['summary']['status'],'aborted')

    def test_pacing_wait_is_cancellable_without_dispatch(self):
        ledger=CampaignLedger(self.folder/'rate.sqlite3');cancel=threading.Event()
        ledger.acquire_slot(1,cancel)
        caught=[]
        def wait():
            try:ledger.acquire_slot(1,cancel)
            except RuntimeError as e:caught.append(str(e))
        thread=threading.Thread(target=wait);thread.start();time.sleep(.03);cancel.set();thread.join(1)
        self.assertFalse(thread.is_alive());self.assertTrue(caught)
        self.assertEqual(ledger.snapshot()['requests'],0)




class EvaluationEvidenceTests(unittest.TestCase):
    def test_behavior_stops_after_fatal_failure_and_keeps_incomplete_status(self):
        from agents.openai_provider import MissingOpenAIApiKeyError
        from evaluation.behavior import run_behavior
        class BrokenProvider:
            model='OFFLINE-fixture'
            calls=0
            def request(self,*args):
                self.calls+=1
                raise MissingOpenAIApiKeyError('Fixture missing key')
        provider=BrokenProvider()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'behavior.jsonl';ledger=CampaignLedger(Path(folder)/'ledger.sqlite3')
            with patch('evaluation.behavior.build_provider',return_value=provider):
                summary=run_behavior(path,ledger)
            self.assertEqual(provider.calls,1)
            self.assertEqual(summary['attempts'],1);self.assertEqual(summary['status'],'incomplete')
            self.assertEqual(run_behavior(path,ledger),summary)
            with self.assertRaisesRegex(ValueError,'provider/settings'):run_behavior(path,ledger,provider_name='gemini')

    def test_report_preserves_missing_evidence_and_rejects_false_provider_identity(self):
        from evaluation.run import make_report
        with tempfile.TemporaryDirectory() as folder:
            directory=Path(folder)
            session=SimulationSession(shopper_count=10,max_rounds=1,decide=FakeDecisionProvider(),output_path=directory/'trip.jsonl')
            session.run()
            CampaignLedger(directory/'ledger.sqlite3')
            manifest={'study_id':'OFFLINE-evidence-test','benchmark_sha256':'fixture','provider':'fake',
                      'ledger':str(directory/'ledger.sqlite3'),'attempts':[
                          {'file':'trip.jsonl','stage':'main','layout':'costco_back_anchor','repetition':1},
                          {'file':'missing.jsonl','stage':'main','layout':'neighborhood_express','repetition':1}],
                      'layouts':['costco_back_anchor','neighborhood_express'],'cohort_size':10}
            path=directory/'campaign.json';path.write_text(json.dumps(manifest))
            report=make_report(directory)
            self.assertEqual(report['missing_evidence'],['missing.jsonl'])
            self.assertEqual(report['status'],'pilot_or_incomplete')
            manifest['provider']='openai';path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'provider/layout identity'):make_report(directory)
            manifest['provider']='fake';manifest['attempts'].append(manifest['attempts'][0]);path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'Duplicate'):make_report(directory)


if __name__=='__main__':unittest.main()
