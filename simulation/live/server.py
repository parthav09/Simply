"""Loopback HTTP/SSE adapter. Sessions and JSONL records remain authoritative."""
import argparse
import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from core.config import ACTIVE_LAYOUT_IDS, DECISION_RUNS_DIR, DEFAULT_CONCURRENCY
from core.session import SimulationSession,build_run_start
from core.export_replay import export_run
from core.budget import read_ledger_snapshot
from evaluation.benchmark import load_benchmark,instantiate_benchmark
from core.grid import build_store
from live.protocol import LiveProjection
from agents.openai_provider import MODEL,MODEL_PRICING,OpenAIProvider
from agents.openrouter_provider import OpenRouterProvider,MODEL_PRICING as ROUTER_PRICING
from core.integrity import fingerprint
from core.navigation import GARY2_CURRENT, MODEL_ONLY
from core.shopping import SIMPLE_SHOPPING
from core.evidence import EvidenceStore,history_payload

ID=re.compile(r'^[a-f0-9]{32}$')


class RunManager:
    def __init__(self,root=DECISION_RUNS_DIR,allow_test=False,destination=None):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.allow_test=allow_test;self.sessions={};self.paused=set();self.lock=threading.Lock()
        self.evidence=EvidenceStore(self.root)
        self.destination=Path(destination) if destination else Path(__file__).resolve().parents[2]/'landing/public/replays'
        self.published_evidence=EvidenceStore(self.destination)

    def records(self):
        result=[]
        for path in self.root.rglob('*.jsonl'):
            try:
                with path.open('rb') as handle:
                    header=json.loads(handle.readline())
                    if header.get('type')!='run_start' or header.get('config',{}).get('mode')!='actions':continue
                    if not self.allow_test and header.get('provider') not in ('openai','gemini','openrouter'):continue
                    if not ID.fullmatch(header.get('run_id','')):continue
                    handle.seek(max(0,path.stat().st_size-524288));tail=handle.read().split(b'\n')
                    last=json.loads(tail[-2]) if len(tail)>1 and tail[-1]==b'' else {}
                status=last.get('status') if last.get('type')=='run_end' else 'recording'
                result.append({'run_id':header['run_id'],'model':header['model'],'provider':header['provider'],
                    'layout_id':header['layout']['id'],'shopper_count':len(header['shoppers']),
                    'recorded_at':header['recorded_at'],'status':status,'controllable':header['run_id'] in self.sessions,
                    '_path':path})
            except (OSError,ValueError,KeyError):continue
        return sorted(result,key=lambda r:r['recorded_at'],reverse=True)

    def find(self,identifier):
        if not ID.fullmatch(identifier):raise ValueError('Invalid run ID')
        row=next((r for r in self.records() if r['run_id']==identifier),None)
        if row is None:raise FileNotFoundError('Recording not found')
        return row

    def state(self,identifier):
        session=self.sessions.get(identifier)
        if session is None:return {'controllable':False,'status':'observing'}
        return {'controllable':True,'status':session.control_status}

    def history(self):
        local=self.evidence.snapshot();saved=self.published_evidence.snapshot()
        snapshot=history_payload([*local['runs'],*saved['runs']],'local_saved_and_published',
                                 [*local['issues'],*saved['issues']])
        try:
            catalog=json.loads((self.destination/'index.json').read_text())
            published={row['run_id']:row for row in catalog['runs']}
        except (OSError,ValueError,KeyError,TypeError):
            published={}
        snapshot['runs']=[{**row,'published':
            {'url':published[row['run_id']]['url'],'evidence_url':published[row['run_id']]['evidence_url']}
            if row['run_id'] in published and published[row['run_id']]['sha256']==row['source_sha256'] else None}
            for row in snapshot['runs']]
        return snapshot

    def create(self,body):
        if set(body)-{'layout','shoppers','provider','max_rounds','model'}:raise ValueError('Unsupported run configuration')
        layout=body.get('layout',ACTIVE_LAYOUT_IDS[0]);count=body.get('shoppers',10);provider=body.get('provider','openrouter')
        model=body.get('model',MODEL)
        if model not in MODEL_PRICING:raise ValueError('Choose GPT-6 Luna or GPT-6.1 Terra')
        rounds=body.get('max_rounds',120)
        if layout not in ACTIVE_LAYOUT_IDS:raise ValueError('Choose layout A or B')
        if type(count) is not int or not (1 if self.allow_test and provider=='fake' else 10)<=count<=15:raise ValueError('Choose 10–15 shoppers')
        if provider not in ('openai','openrouter') and not (self.allow_test and provider=='fake'):raise ValueError('Live runs require OpenRouter or direct OpenAI')
        if type(rounds) is not int or not 1<=rounds<=120:raise ValueError('Invalid round limit')
        with self.lock:
            if any(not s.closed for s in self.sessions.values()):raise RuntimeError('A live session is already running; attach to it')
            grid=build_store(layout)
            benchmark=load_benchmark(Path(__file__).resolve().parents[1]/'benchmarks/two_layouts_15_v2.json')
            shoppers=instantiate_benchmark(benchmark,count,grid,shopping_rules=SIMPLE_SHOPPING)
            from agents.providers import FakeDecisionProvider
            session=SimulationSession(layout,count,rounds,120,DEFAULT_CONCURRENCY,grid=grid,shoppers=shoppers,
                provider_name=provider,model_name=model,decide=FakeDecisionProvider() if provider=='fake' else None,
                navigation_policy=GARY2_CURRENT if provider!='fake' else MODEL_ONLY,
                shopping_rules=SIMPLE_SHOPPING,
                requests_per_minute=18 if provider=='openrouter' else 0,
                output_path=self.root/f'live_{time.time_ns()}.jsonl',ledger_path=self.root/'gemini_campaign.sqlite3',
                experiment={'stage':'live_web','benchmark_sha256':benchmark['sha256']})
            self.sessions[session.run_id]=session;session.start()
            return {'run_id':session.run_id,**self.state(session.run_id)}

    def preview(self,layout,count,model):
        if layout not in ACTIVE_LAYOUT_IDS or type(count) is not int or not 10<=count<=15 or model not in MODEL_PRICING:raise ValueError('Invalid preview configuration')
        grid=build_store(layout);benchmark=load_benchmark(Path(__file__).resolve().parents[1]/'benchmarks/two_layouts_15_v2.json')
        shoppers=instantiate_benchmark(benchmark,count,grid,shopping_rules=SIMPLE_SHOPPING)
        header=build_run_start(grid,shoppers,run_id='preview',provider='not-started',model=model,
            max_rounds=120,concurrency=DEFAULT_CONCURRENCY,propose_only=False,prompt_variant='informed',
            generation_settings=OpenRouterProvider.generation_settings,pricing=ROUTER_PRICING[model],navigation_policy=GARY2_CURRENT,
            shopping_rules=SIMPLE_SHOPPING)
        projection=LiveProjection();projection.append((json.dumps(header)+'\n').encode())
        return projection.snapshot()

    def control(self,identifier,command):
        session=self.sessions.get(identifier)
        if session is None:raise ValueError('This run is observed from another Python process; controls are unavailable')
        if session.closed:raise ValueError('Run has already ended')
        if command=='pause':self.paused.add(identifier);session.pause()
        elif command=='resume':self.paused.discard(identifier);session.resume()
        elif command=='advance':
            if session.control_status!='paused':raise ValueError('Pause and let the current round finish before advancing')
            self.paused.add(identifier);session.advance()
        elif command=='stop':session.stop()
        else:raise ValueError('Unknown control')
        return self.state(identifier)

    def close(self):
        for session in self.sessions.values():
            if not session.closed:session.stop()
        for session in self.sessions.values():
            session.join(40)


def handler_for(manager):
    class Handler(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.1'

        def log_message(self,*args):pass

        def reply(self,status,value):
            data=json.dumps(value,allow_nan=False).encode()
            self.send_response(status);self.send_header('Content-Type','application/json')
            self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)))
            self.end_headers();self.wfile.write(data)

        def do_GET(self):self.dispatch(False)
        def do_POST(self):self.dispatch(True)

        def dispatch(self,mutating):
            try:
                if self.headers.get('Host') not in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'):return self.reply(403,{'error':'Local host required'})
                if mutating and self.headers.get('Origin'):return self.reply(403,{'error':'Use the same-origin web proxy'})
                path=urlparse(self.path).path.strip('/').split('/')
                if not mutating and path==['health']:return self.reply(200,{'status':'ready','provider':'openrouter','models':list(ROUTER_PRICING),'budget':read_ledger_snapshot(manager.root/'gemini_campaign.sqlite3'),'api_budget_enforced':False})
                if not mutating and path==['preview']:
                    from urllib.parse import parse_qs
                    query=parse_qs(urlparse(self.path).query)
                    return self.reply(200,manager.preview(query.get('layout',[ACTIVE_LAYOUT_IDS[0]])[0],int(query.get('shoppers',['10'])[0]),query.get('model',[MODEL])[0]))
                if not mutating and path==['runs']:return self.reply(200,{'runs':[{k:v for k,v in r.items() if k!='_path'} for r in manager.records()]})
                if not mutating and path==['evidence']:return self.reply(200,manager.history())
                if mutating:
                    length=int(self.headers.get('Content-Length','0'))
                    if not 0<length<=8192 or self.headers.get_content_type()!='application/json':return self.reply(400,{'error':'JSON body required (maximum 8 KB)'})
                    body=json.loads(self.rfile.read(length))
                    if not isinstance(body,dict):raise ValueError('JSON object required')
                    if path==['runs']:return self.reply(201,manager.create(body))
                    if len(path)==3 and path[0]=='runs':
                        identifier=path[1];manager.find(identifier)
                        if path[2]=='control':return self.reply(200,manager.control(identifier,body.get('command')))
                        if path[2]=='export':
                            row=manager.find(identifier)
                            if row['status']=='recording':raise ValueError('Wait for the run to end before saving a replay')
                            target=export_run(row['_path'],manager.destination,allow_partial=body.get('allow_partial') is True,allow_test=manager.allow_test)
                            return self.reply(200,{'url':f'/replays/{target.name}'})
                if not mutating and len(path)==3 and path[0]=='runs' and path[2]=='events':return self.stream(path[1])
                self.reply(404,{'error':'Unknown endpoint'})
            except FileNotFoundError as e:self.reply(404,{'error':str(e)})
            except (ValueError,KeyError) as e:self.reply(400,{'error':str(e)})
            except RuntimeError as e:self.reply(409,{'error':str(e)})
            except (BrokenPipeError,ConnectionResetError):pass

        def stream(self,identifier):
            row=manager.find(identifier);projection=LiveProjection()
            self.send_response(200);self.send_header('Content-Type','text/event-stream')
            self.send_header('Cache-Control','no-cache, no-transform');self.send_header('Connection','close')
            self.send_header('X-Accel-Buffering','no');self.end_headers()
            def send(kind,data):
                self.wfile.write(('event: '+kind+'\ndata: '+json.dumps(data,separators=(',',':'),allow_nan=False)+'\n\n').encode());self.wfile.flush()
            try:
                with row['_path'].open('rb') as handle:
                    pending=b'';initial=True;heartbeat=time.monotonic()
                    while True:
                        chunk=handle.read(65536)
                        if chunk:pending+=chunk
                        while b'\n' in pending:
                            line,pending=pending.split(b'\n',1);kind=projection.append(line+b'\n')
                            if not initial:send('finished' if kind=='run_end' else 'transition',{**projection.transition(kind=='run_end'),'control':manager.state(identifier)})
                        if initial and projection.view is not None:
                            # Drain the prefix first; reconnects replace the entire
                            # browser frame instead of replaying duplicate events.
                            if chunk:continue
                            send('snapshot',{'stream_version':1,'run':projection.snapshot(),'control':manager.state(identifier)})
                            initial=False
                        if projection.view and projection.view.end is not None:return
                        if time.monotonic()-heartbeat>=2:
                            send('control',manager.state(identifier));heartbeat=time.monotonic()
                        if not chunk:time.sleep(.1)
            except (BrokenPipeError,ConnectionResetError):return
            except (ValueError,KeyError) as error:send('stream_error',{'error':str(error)})
    return Handler


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8765);parser.add_argument('--runs',type=Path,default=DECISION_RUNS_DIR)
    parser.add_argument('--allow-test-provider',action='store_true',help='Explicit offline testing only')
    args=parser.parse_args();manager=RunManager(args.runs,args.allow_test_provider)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),handler_for(manager));server.daemon_threads=True
    print(f'Simply Python live service: http://127.0.0.1:{server.server_port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close();manager.close()


if __name__=='__main__':main()
