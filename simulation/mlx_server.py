"""Serve the converted Qwen pilot with MLX Metal on loopback only."""
import argparse
import json
from http.server import ThreadingHTTPServer
from pathlib import Path

from agents.mlx_runtime import MLXRuntime, MODEL
from agents.mps_runtime import prepare_adapter
from mps_server import handler_for


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adapter', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8767)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('Invalid port')
    root = Path(__file__).resolve().parent / 'models'
    try:
        original, _ = prepare_adapter(args.adapter, root / 'adapters')
        runtime = MLXRuntime(root / 'qwen25-7b-mlx-int4', root / 'mlx-pilot-adapter', original,
            json.loads((root / 'qwen-base-source.json').read_text()))
        print('Loading Qwen pilot on MLX Metal…', flush=True)
        identity = runtime.load()
        server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(runtime, MODEL, 'MLX'))
        server.daemon_threads = True
        print(f"Ready: http://127.0.0.1:{args.port} · {MODEL} · adapter {identity['adapter_sha256'][:12]}", flush=True)
        try: server.serve_forever()
        finally: server.server_close()
    except KeyboardInterrupt:
        return
    except (OSError, ValueError, RuntimeError) as error:
        parser.exit(2, f'MLX server stopped: {error}\n')


if __name__ == '__main__':
    main()
