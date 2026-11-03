"""Headline membership, pooled denominators, N/A and source-backed distributions."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from evaluation import dashboard,matrix,study
import test_matrix_study as fixtures


class EvidenceDashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        original=study.prepare
        def short(directory,**kwargs):return original(directory,**kwargs,turn_budget=2)
        with patch('evaluation.matrix.study.prepare',short):
            self.plan=matrix.prepare(self.root/'matrix',repetitions=1)
        with patch('agents.openai_provider.OpenAIProvider._request',fixtures.MatrixStudyTests.fixture),patch('evaluation.study.DECISION_RUNS_DIR',self.root/'accounting'):
            matrix.execute(self.root/'matrix')
        self.protocols=[study.load_protocol(self.root/'matrix'/c['directory']) for c in self.plan['children']]
        self.records=[dashboard.record(p,self.protocols) for p in sorted((self.root/'matrix').rglob('*.jsonl'))]

    def test_first_view_is_one_run_in_each_cell_and_qwen_has_only_na(self):
        result=dashboard.assemble(self.records,self.plan['study_id']);view=result['views'][0]
        self.assertEqual((view['runs'],view['trips']),(4,40))
        for model in view['models'][:2]:
            for c in model['cells'].values():
                self.assertEqual((c['runs'],c['trips']),(1,10))
                self.assertEqual(c['metrics']['checkout_completion'],0)
                self.assertIsNone(c['metrics']['estimated_cost_per_checkout_usd'])
        for model in view['models'][2:]:
            for c in model['cells'].values():
                self.assertEqual(c['status'],'not_evaluated')
                self.assertTrue(all(v is None for v in c['metrics'].values()))
                self.assertEqual(c['run_ids'],[])

    def test_stopped_runs_and_other_cohorts_remain_in_distributions_not_first_table(self):
        second=copy.deepcopy(self.records[0]);second.update(run_id='a'*32,repetition=2,status='aborted')
        other=copy.deepcopy(self.records[1]);other.update(run_id='b'*32,group='historical')
        pilot=copy.deepcopy(self.records[1]);pilot.update(run_id='c'*32,group='pilot')
        router=copy.deepcopy(self.records[1]);router.update(run_id='d'*32,group='openrouter',provider='openrouter',status='aborted')
        result=dashboard.assemble([*self.records,second,other,pilot,router],self.plan['study_id'])
        self.assertEqual(result['coverage']['retained_runs'],8)
        self.assertEqual(result['coverage']['retained_trips'],80)
        self.assertEqual(result['views'][0]['runs'],4)
        self.assertEqual(result['views'][1]['runs'],4)
        self.assertEqual(result['views'][2]['runs'],5)
        self.assertEqual(len(result['runs']),8)
        duplicate=[*self.records,copy.deepcopy(self.records[0])]
        with self.assertRaisesRegex(ValueError,'Duplicate'):dashboard.assemble(duplicate,self.plan['study_id'])

    def test_costs_and_fulfillment_pool_numerators_and_do_not_drop_unfinished_trips(self):
        a,b=copy.deepcopy(self.records[:2])
        def measured(row,paid,requested,cost,finished):
            row['points']=[{'profile_id':'OFFLINE','finished':finished,'requested':requested,'purchased':paid,
                'values':{'moves':7,'fulfillment':paid/requested,'requests':3,'estimated_cost_usd':cost}}]
            row['run_metrics'].update(known_estimated_cost_usd=cost,sales_cents=0,turns_used=3,navigation_adjustments=0)
            row['cost_complete']=True
        measured(a,1,1,2,True);measured(b,0,9,3,False)
        result=dashboard.cell([a,b])
        self.assertEqual(result['metrics']['purchased_unit_fulfillment'],.1)
        self.assertEqual(result['metrics']['checkout_completion'],.5)
        self.assertEqual(result['metrics']['estimated_cost_per_checkout_usd'],5)
        self.assertEqual(result['metrics']['estimated_cost_per_run_usd'],2.5)
        b['cost_complete']=False
        self.assertIsNone(dashboard.cell([a,b])['metrics']['estimated_cost_per_checkout_usd'])
        self.assertIsNone(dashboard.cell([a,b])['metrics']['estimated_cost_per_run_usd'])

    def test_distribution_retains_zero_and_unknown_and_is_not_a_confidence_interval(self):
        self.assertEqual(dashboard.distribution([0,None,10]),{'known':2,'unknown':1,'min':0,'q1':2.5,'median':5,'q3':7.5,'max':10})
        self.assertIsNone(dashboard.distribution([None])['median'])
        for row in self.records:
            self.assertEqual(row['distributions']['moves']['known'],10)
            self.assertEqual(row['distributions']['moves']['unknown'],0)

    def test_qwen_view_uses_its_frozen_study_only_and_keeps_charges_separate(self):
        from test_openrouter_provider import OpenRouterTests
        directory=self.root/'qwen'
        protocol=study.prepare(directory,provider='openrouter',kind='layout',models=['qwen2.5-7b-instruct'],
            repetitions=1,turn_budget=1)
        with patch('agents.openrouter_provider.api_key',return_value='OFFLINE'),patch('urllib.request.urlopen',side_effect=OpenRouterTests.response),patch('evaluation.study.DECISION_RUNS_DIR',self.root/'accounting'):
            study.execute(directory)
        rows=[dashboard.record(p,[*self.protocols,protocol]) for p in sorted(directory.glob('*.jsonl'))]
        self.assertTrue(all(r['group']=='qwen_baseline' for r in rows))
        result=dashboard.assemble([*self.records,*rows],self.plan['study_id'])
        self.assertEqual(result['default_view'],'qwen_baseline')
        self.assertEqual(result['views'][0]['runs'],4)
        qwen=result['views'][-1]
        self.assertEqual((qwen['runs'],qwen['trips']),(2,20))
        for c in qwen['models'][0]['cells'].values():
            self.assertEqual(c['trips'],10)
            self.assertAlmostEqual(c['metrics']['provider_reported_cost_per_run_usd'],.00013)
            self.assertIsNone(c['metrics']['provider_reported_cost_per_checkout_usd'])
            self.assertNotEqual(c['metrics']['estimated_cost_per_run_usd'],.00013)
        self.assertEqual(qwen['models'][1]['status'],'not_evaluated')
        # A Qwen attempt without the selected protocol is only a separate transport recording.
        unselected=dashboard.record(next(directory.glob('*.jsonl')),self.protocols)
        self.assertEqual(unselected['group'],'openrouter')

    def test_published_dashboard_reconstructs_and_detects_changed_table_values(self):
        public=self.root/'public';public.mkdir()
        def save(name,value):
            path=public/name;path.write_text(json.dumps(value));return path
        save(f"matrix-{self.plan['study_id']}.protocol.json",self.plan)
        for p in self.protocols:save(f"study-{p['study_id']}.protocol.json",p)
        import shutil
        for source,row in zip(sorted((self.root/'matrix').rglob('*.jsonl')),self.records):
            shutil.copyfile(source,public/f"{row['run_id']}.source.jsonl")
        result=dashboard.assemble(self.records,self.plan['study_id'])
        path=save('evidence-dashboard.json',result)
        import hashlib
        def index():save('index.json',{'matrix':{'protocol_url':f"/replays/matrix-{self.plan['study_id']}.protocol.json"},
            'dashboard':{'url':'/replays/evidence-dashboard.json','sha256':hashlib.sha256(path.read_bytes()).hexdigest()}})
        index()
        with patch('urllib.request.urlopen',side_effect=AssertionError('Verification must not call APIs')):
            self.assertEqual(dashboard.verify(public)['verified_runs'],4)
            result['views'][0]['models'][0]['cells']['costco_back_anchor']['metrics']['checkout_completion']=1
            save('evidence-dashboard.json',result);index()
            with self.assertRaisesRegex(ValueError,'source reconstruction'):dashboard.verify(public)
