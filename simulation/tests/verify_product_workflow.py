"""Explicit OFFLINE fixtures for full run -> record -> export -> React verification.

Routes in this file are test instructions, never a production shopper policy.
The real OpenAI request/parser/metering path runs against a local mocked transport.
Every recording keeps provider_id=scripted_test; no model behavior is claimed.
"""
import argparse
import io
import json
import os
import sys
import threading
from collections import deque
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

SIMULATION_DIR=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SIMULATION_DIR))

from agents.openai_provider import OpenAIProvider
from agents.base import ProposalResult
from agents.schema import parse_decision
from core.budget import CampaignLedger
from core.config import ACTIVE_LAYOUT_IDS
from core.export_replay import export_run
from core.recording import RecordingView
from core.run_log import read_run
from core.session import SimulationSession, snapshot_shoppers
from evaluation.benchmark import load_benchmark, instantiate_benchmark
from evaluation.run import make_report, publish, save_json, save_campaign
from core.grid import build_store


def scripted_actions(grid, shopper):
    position=(shopper.state.x,shopper.state.y)
    actions=[];remaining=list(shopper.customer.shopping_list)
    directions={(-1,0):'move_left',(1,0):'move_right',(0,-1):'move_up',(0,1):'move_down'}
    def walk(path):
        nonlocal position
        for cell in path:
            actions.append({'step':directions[cell[0]-position[0],cell[1]-position[1]],'product_id':'','reason':'OFFLINE fixture route'})
            position=cell
    while remaining:
        options=[]
        for item in remaining:
            p=grid.products[item.product_id]
            path=grid.find_path(position,grid.stand_cells_for((p['x'],p['y'])))
            assert path is not None
            options.append((len(path),item.product_id,item,path))
        _,_,item,path=min(options,key=lambda entry:entry[:2])
        walk(path)
        actions.extend({'step':'grab','product_id':item.product_id,'reason':'OFFLINE fixture purchase'} for _ in range(item.quantity))
        remaining.remove(item)
    walk(grid.find_path(position,grid.checkout))
    actions.extend({'step':'checkout','product_id':'','reason':'OFFLINE fixture checkout'} for _ in range(2))
    assert len(actions)<=96
    return deque(actions)


class OfflineTransportProvider(OpenAIProvider):
    provider_id='scripted_test'
    supports_action_plans=False

    def __init__(self, ledger, queues):
        super().__init__(ledger,'OFFLINE-workflow-verification')
        self.queues=queues
        self.local=threading.local()
        self.calls=0
        self.lock=threading.Lock()

    def request(self,prompt,allowed_steps,shopper_id):
        self.local.shopper_id=shopper_id
        return super().request(prompt,allowed_steps,shopper_id)

    def transport(self,request,timeout):
        assert request.full_url=='https://api.openai.com/v1/responses'
        body=json.loads(request.data)
        assert body['model']=='gpt-6-luna' and body['text']['format']['strict']
        action=self.queues[self.local.shopper_id].popleft()
        assert action['step'] in body['text']['format']['schema']['properties']['step']['enum']
        with self.lock:self.calls+=1
        response={'id':'OFFLINE-fixture-response','model':'OFFLINE-mocked-gpt-6-luna','status':'completed',
                  'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(action)}]}],
                  'usage':{'input_tokens':100,'output_tokens':30,'total_tokens':130,
                           'input_tokens_details':{'cached_tokens':0,'cache_write_tokens':0},
                           'output_tokens_details':{'reasoning_tokens':0}}}
        return io.BytesIO(json.dumps(response).encode())


class OfflineProbeProvider:
    model='OFFLINE-scripted-probe'
    generation_settings={'decision_source':'explicit_offline_fixture'}

    def request(self,prompt,allowed_steps,shopper_id):
        raw=json.dumps({'step':allowed_steps[1],'product_id':'','reason':'OFFLINE skip fixture'})
        return ProposalResult(raw,parse_decision(raw,allowed_steps),{'request_submitted':False,'estimated_cost_micros':0})


def verify(destination):
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    benchmark=load_benchmark(SIMULATION_DIR/'benchmarks/two_layouts_15_v2.json')
    results=[]
    for count in (10,15):
        directory=destination/f'cohort-{count}';directory.mkdir()
        ledger=CampaignLedger(directory/'OFFLINE-ledger.sqlite3')
        manifest={'study_id':f'OFFLINE-workflow-{count}','provider':'scripted_test',
                  'benchmark_sha256':benchmark['sha256'],'ledger':str(ledger.path.resolve()),
                  'layouts':list(ACTIVE_LAYOUT_IDS),'cohort_size':count,'requested_shopper_count':count,
                  'main_repetitions':5,'attempts':[]}
        for layout in ACTIVE_LAYOUT_IDS:
            started=perf_counter();grid=build_store(layout)
            shoppers=instantiate_benchmark(benchmark,count,grid)
            provider=OfflineTransportProvider(ledger,{s.customer_id:scripted_actions(grid,s) for s in shoppers})
            path=directory/f'{layout}.jsonl'
            session=SimulationSession(layout,count,120,120,2,decide=provider,output_path=path,grid=grid,shoppers=shoppers)
            print(f'OFFLINE: {layout}, {count} shoppers',flush=True)
            with patch.dict(os.environ,{'OPENAI_API_KEY':'OFFLINE-not-a-real-key'}),patch('urllib.request.urlopen',side_effect=provider.transport):
                session.run()
            run=read_run(path)
            assert run['start']['provider']=='scripted_test'
            assert run['summary']['finished_count']==count
            assert run['summary']['purchased_unit_fulfillment']==1
            assert run['summary']['sales_cents']==run['summary']['basket_value_cents']
            assert not any(run['summary']['failures'].values())
            assert run['end']['shoppers']==snapshot_shoppers(grid,shoppers)
            assert provider.calls==len(run['events']) and all(not q for q in provider.queues.values())
            runtime=perf_counter()-started;export_started=perf_counter()
            target=export_run(path,destination/'artifacts',allow_test=True)
            payload=json.loads(json.loads(target.read_text())['payload_json'])
            view=RecordingView(run['start'])
            # All raw state changes must survive export; endpoint metrics are
            # checked independently against the live session and validated log.
            states={s['agent_id']:s['state'] for s in run['start']['shoppers']}
            for event,frame in zip(run['events'],payload['events'],strict=True):
                states[event['agent_id']]=event['after']
                assert frame['after']['cart']==event['after']['cart']
                assert (frame['after']['x'],frame['after']['y'])==(event['after']['x'],event['after']['y'])
            assert payload['final']['summary']==run['summary']==session.summary
            assert payload['source']['provider']=='scripted_test'
            samples={}
            points={0,1,len(run['events'])//2,len(run['events'])-1,len(run['events'])}
            for index,event in enumerate(run['events'],1):
                if index==1:samples['0']=view.snapshot()
                view.append(event)
                if index in points:samples[str(index)]=view.snapshot()
            view.append(run['end']);samples[str(len(run['events']))]=view.snapshot()
            expected=target.with_suffix('.expected.json');save_json(expected,samples)
            manifest['attempts'].append({'file':path.name,'stage':'main','layout':layout,'repetition':1,'status':'completed'})
            result={'layout':layout,'shoppers':count,'run_id':session.run_id,'events':len(run['events']),
                    'checkout':run['summary']['finished_count'],'fulfillment':run['summary']['purchased_unit_fulfillment'],
                    'sales_cents':run['summary']['sales_cents'],'run_seconds':runtime,'export_seconds':perf_counter()-export_started,
                    'bundle':str(target.resolve()),'expected':str(expected.resolve())}
            results.append(result);print(json.dumps(result),flush=True)
        from evaluation.behavior import run_behavior
        with patch('evaluation.behavior.build_provider',return_value=OfflineProbeProvider()):
            manifest['behavior']=run_behavior(directory/'behavior.jsonl',ledger,provider_name='scripted_test')
        assert manifest['behavior']['attempts']==40 and manifest['behavior']['ties']==20
        manifest['seed']=42
        save_campaign(directory/'campaign.json',manifest,ledger)
        report=make_report(directory)
        assert len(report['arms'])==2 and len(report['paired'])==16
        assert report['status']=='pilot_or_incomplete'
        assert all(p['ci95'] is None for p in report['paired'])
        publish(directory,destination/'public/replays')
    save_json(destination/'verification.json',{'kind':'OFFLINE TEST ONLY','real_api_requests':0,'results':results})
    return results


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('destination',type=Path)
    args=parser.parse_args();verify(args.destination)
