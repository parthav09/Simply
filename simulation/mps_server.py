"""Serve the saved Qwen pilot on this Mac's MPS GPU, on loopback only."""
import argparse
import json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import sys

from agents.mps_runtime import MPSRuntime,MODEL,prepare_adapter


def handler_for(runtime, model=MODEL, backend='MPS'):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass

        def reply(self,status,value):
            data=json.dumps(value,allow_nan=False).encode()
            self.send_response(status);self.send_header('Content-Type','application/json')
            self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)))
            self.end_headers();self.wfile.write(data)

        def permitted(self):
            if self.headers.get('Host') not in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}') or self.headers.get('Origin'):
                self.reply(403,{'error':'Loopback Python client required'});return False
            return True

        def do_GET(self):
            if not self.permitted():return
            if self.path!='/health':return self.reply(404,{'error':'Unknown endpoint'})
            self.reply(200,{'status':'ready','identity':runtime.identity})

        def do_POST(self):
            if not self.permitted():return
            if self.path!='/decision':return self.reply(404,{'error':'Unknown endpoint'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=512*1024 or self.headers.get_content_type()!='application/json':
                    return self.reply(413,{'error':'JSON body required, maximum 512 KB'})
                body=json.loads(self.rfile.read(length))
                if not isinstance(body,dict) or set(body)!={'model','prompt','identity'}:
                    raise ValueError('Expected model, prompt and frozen identity')
                if body['model']!=model or body['identity']!=runtime.identity:
                    return self.reply(409,{'error':'Serving identity differs from the frozen run'})
                self.reply(200,runtime.generate(body['prompt']))
            except (ValueError,TypeError):self.reply(400,{'error':'Invalid request or observation exceeds full context'})
            except (BrokenPipeError,ConnectionResetError):pass
            except Exception as error:
                # Do not echo prompts, filesystem paths or arbitrary backend exception text.
                self.reply(503,{'error':f'{backend} inference failed ({type(error).__name__}); no fallback'})
    return Handler


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adapter',type=Path,required=True,help='Pilot adapter ZIP')
    parser.add_argument('--base-source',type=Path,default=Path(__file__).parent/'models/qwen-base-source.json')
    parser.add_argument('--port',type=int,default=8766)
    args=parser.parse_args()
    if not 1<=args.port<=65535:parser.error('Invalid port')
    try:
        adapter,manifest=prepare_adapter(args.adapter,Path(__file__).parent/'models/adapters')
        runtime=MPSRuntime(adapter,manifest,json.loads(args.base_source.read_text()))
        print('Loading pinned Qwen base and pilot adapter on MPS…',flush=True)
        identity=runtime.load()
        server=ThreadingHTTPServer(('127.0.0.1',args.port),handler_for(runtime));server.daemon_threads=True
        print(f"Ready: http://127.0.0.1:{args.port} · {MODEL} · adapter {identity['adapter_sha256'][:12]}",flush=True)
        try:server.serve_forever()
        finally:server.server_close()
    except KeyboardInterrupt:return
    except (OSError,ValueError,RuntimeError) as error:parser.exit(2,f'MPS server stopped: {error}\n')


if __name__=='__main__':main()
