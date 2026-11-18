import copy
import json
import os
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.cuda_provider import CUDAImpulseV2Provider, CUDAProvider, MODEL, SETTINGS, health, impulse_health
from agents.cuda_runtime import IMPULSE_MODEL
from agents.mps_provider import MPSRequestError
from agents.providers import build_provider
from mps_server import handler_for

IDENTITY = {'model': MODEL, 'device': 'cuda', 'base_model': 'Qwen/Qwen2.5-7B-Instruct',
    'training_mode': 'pilot', 'generation': SETTINGS, 'adapter_sha256': 'a' * 64, 'base_revision': 'b' * 40}


class StubRuntime:
    """Stands in for the GPU model: proposes the first allowed step from the observation."""
    identity = IDENTITY

    def generate(self, prompt):
        state = json.loads(prompt.split('Current state: ', 1)[1].split('\nChoose one step:', 1)[0])
        step = state['allowed_steps'][0]
        return {'raw_response': json.dumps({'step': step, 'product_id': '', 'reason': 'stub'}),
            'finish_reason': 'stop', 'identity': IDENTITY,
            'usage': {'prompt_tokens': 10, 'completion_tokens': 5}, 'inference_ms': 1.0}


class CUDAProviderTests(unittest.TestCase):
    def test_identity_and_routing(self):
        with patch('agents.cuda_provider.local_json', return_value={'status': 'ready', 'identity': IDENTITY}):
            self.assertEqual(health(), IDENTITY)
        with patch.object(CUDAProvider, 'serving_health', return_value=IDENTITY):
            provider = build_provider('local_mps', None, 'run', model=MODEL)
        self.assertIsInstance(provider, CUDAProvider)
        v2 = {**IDENTITY, 'model': IMPULSE_MODEL, 'training_mode': 'impulse_v2'}
        with patch('agents.cuda_provider.local_json', return_value={'status': 'ready', 'identity': v2}):
            self.assertEqual(impulse_health(), v2)
            with self.assertRaises(ValueError):
                health()  # a v2 server must never pass as the v1 pilot identity
        with patch.object(CUDAImpulseV2Provider, 'serving_health', return_value=v2):
            self.assertIsInstance(build_provider('local_mps', None, 'run', model=IMPULSE_MODEL), CUDAImpulseV2Provider)

    def test_rejects_wrong_identity(self):
        bad = copy.deepcopy(IDENTITY)
        bad['device'] = 'mps'
        with patch('agents.cuda_provider.local_json', return_value={'status': 'ready', 'identity': bad}):
            with self.assertRaises(ValueError):
                health()

    def test_changed_identity_aborts(self):
        with patch.object(CUDAProvider, 'serving_health', return_value=IDENTITY):
            provider = CUDAProvider(None, 'run', model=MODEL)
        changed = copy.deepcopy(IDENTITY)
        changed['adapter_sha256'] = 'c' * 64
        with patch('agents.mps_provider.local_json', return_value={'identity': changed}):
            with self.assertRaisesRegex(MPSRequestError, 'CUDA HTTP 503'):
                provider.request('observation', ['move_right'], 'shopper')

    def test_study_runs_through_loopback_server_and_core(self):
        from evaluation import study
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(StubRuntime(), MODEL, 'CUDA'))
        server.daemon_threads = True
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as root, \
                    patch.dict(os.environ, {'SIMPLY_CUDA_URL': f'http://127.0.0.1:{server.server_port}'}), \
                    patch('evaluation.study.DECISION_RUNS_DIR', Path(root) / 'accounting'):
                directory = Path(root) / 'study'
                protocol = study.prepare(directory, provider='local_mps', models=[MODEL], concurrency=1,
                    repetitions=1, turn_budget=3)
                result = study.execute(directory)
                self.assertEqual(result['status'], 'completed')
                self.assertEqual(len(result['runs']), 2)
                self.assertEqual({a['model'] for a in protocol['arms']}, {MODEL})
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    unittest.main()
