import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.mlx_provider import MLXProvider, MODEL, SETTINGS, health
from agents.mps_provider import MPSRequestError
from agents.providers import build_provider


IDENTITY = {'model': MODEL, 'device': 'mlx-metal', 'base_model': 'Qwen/Qwen2.5-7B-Instruct',
    'training_mode': 'pilot', 'generation': SETTINGS, 'loaded_lora_tensors': 392,
    'adapter_sha256': 'a' * 64, 'base_revision': 'b' * 40}


class MLXProviderTests(unittest.TestCase):
    def test_identity_and_provider_routing(self):
        with patch('agents.mlx_provider.local_json', return_value={'status': 'ready', 'identity': IDENTITY}):
            self.assertEqual(health(), IDENTITY)
        with patch.object(MLXProvider, 'serving_health', return_value=IDENTITY):
            provider = build_provider('local_mps', None, 'run', model=MODEL)
        self.assertIsInstance(provider, MLXProvider)
        response = {'identity': IDENTITY, 'raw_response': json.dumps({'step': 'move_right', 'product_id': '', 'reason': 'Proceed'}),
            'finish_reason': 'stop', 'usage': {'prompt_tokens': 4, 'completion_tokens': 2}}
        with patch('agents.mps_provider.local_json', return_value=response) as request:
            result = provider.request('observation', ['move_right'], 'shopper')
        self.assertIsNotNone(result.decision)
        self.assertEqual(request.call_args.args[2]['model'], MODEL)
        self.assertEqual(result.telemetry['serving_provider'], 'Local MLX Metal')

    def test_rejects_wrong_identity(self):
        bad = copy.deepcopy(IDENTITY)
        bad['device'] = 'mps'
        with patch('agents.mlx_provider.local_json', return_value={'status': 'ready', 'identity': bad}):
            with self.assertRaises(ValueError): health()

    def test_changed_serving_identity_aborts(self):
        with patch.object(MLXProvider, 'serving_health', return_value=IDENTITY):
            provider = MLXProvider(None, 'run', model=MODEL)
        changed = copy.deepcopy(IDENTITY)
        changed['adapter_sha256'] = 'c' * 64
        with patch('agents.mps_provider.local_json', return_value={'identity': changed}):
            with self.assertRaisesRegex(MPSRequestError, 'MLX HTTP 503'):
                provider.request('observation', ['move_right'], 'shopper')

    def test_preview_does_not_load_or_contact_model(self):
        from live.server import RunManager
        with tempfile.TemporaryDirectory() as root, patch('agents.mlx_provider.health', side_effect=AssertionError('preview contacted model')):
            preview = RunManager(Path(root)).preview('costco_back_anchor', 10, MODEL)
        self.assertEqual(preview['source']['model'], MODEL)
        self.assertEqual(preview['source']['provider'], 'not-started')

    def test_frozen_mlx_study_records_and_displays_distinct_arms(self):
        from evaluation import dashboard, study
        response = {'identity': IDENTITY, 'raw_response': json.dumps({'step': 'move_right', 'product_id': '', 'reason': 'Proceed'}),
            'finish_reason': 'stop', 'usage': {'prompt_tokens': 4, 'completion_tokens': 2}}
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / 'study'
            with patch.object(MLXProvider, 'serving_health', return_value=IDENTITY), \
                    patch('agents.mps_provider.local_json', return_value=response), \
                    patch('evaluation.study.DECISION_RUNS_DIR', Path(root) / 'accounting'):
                protocol = study.prepare(directory, provider='local_mps', models=[MODEL], concurrency=1,
                    repetitions=1, turn_budget=1)
                study.execute(directory)
            rows = [dashboard.record(path, [protocol]) for path in directory.glob('*.jsonl')]
            self.assertEqual({r['group'] for r in rows}, {'qwen_mlx'})
            view = dashboard.assemble(rows, 'f' * 32, mlx_selected=True)['views'][-1]
            self.assertEqual(view['models'][-1]['id'], MODEL)
            self.assertTrue(all(cell['runs'] == 1 and cell['trips'] == 10 for cell in view['models'][-1]['cells'].values()))

    def test_remaining_slot_can_run_without_retrying_interrupted_slot(self):
        from evaluation import study
        response = {'identity': IDENTITY, 'raw_response': json.dumps({'step': 'move_right', 'product_id': '', 'reason': 'Proceed'}),
            'finish_reason': 'stop', 'usage': {'prompt_tokens': 4, 'completion_tokens': 2}}
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / 'study'
            with patch.object(MLXProvider, 'serving_health', return_value=IDENTITY), \
                    patch('agents.mps_provider.local_json', return_value=response), \
                    patch('evaluation.study.DECISION_RUNS_DIR', Path(root) / 'accounting'):
                study.prepare(directory, provider='local_mps', models=[MODEL], concurrency=1,
                    repetitions=1, turn_budget=1)
                study.execute(directory, max_new_runs=1)
                existing = next(directory.glob('*.jsonl'))
                lines = existing.read_bytes().splitlines(keepends=True)
                existing.write_bytes(b''.join(lines[:-1]))
                retained = existing.read_bytes()
                with self.assertRaisesRegex(ValueError, 'no automatic retry'):
                    study.execute(directory, max_new_runs=1)
                study.execute(directory, max_new_runs=1, skip_stopped=True)
                self.assertEqual(existing.read_bytes(), retained)
                self.assertEqual(len(list(directory.glob('*.jsonl'))), 2)

    def test_continuation_replays_history_and_preserves_source(self):
        from core.run_log import read_run
        from evaluation import continue_mlx, dashboard, study
        response = {'identity': IDENTITY, 'raw_response': json.dumps({'step': 'move_right', 'product_id': '', 'reason': 'Proceed'}),
            'finish_reason': 'stop', 'usage': {'prompt_tokens': 4, 'completion_tokens': 2}}
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / 'study'
            with patch.object(MLXProvider, 'serving_health', return_value=IDENTITY), \
                    patch('agents.mps_provider.local_json', return_value=response), \
                    patch('evaluation.study.DECISION_RUNS_DIR', Path(root) / 'accounting'), \
                    patch('evaluation.continue_mlx.DECISION_RUNS_DIR', Path(root) / 'accounting'):
                protocol = study.prepare(directory, provider='local_mps', models=[MODEL], concurrency=1,
                    repetitions=1, turn_budget=2)
                study.execute(directory, max_new_runs=1)
                source = next(directory.glob('*.jsonl'))
                lines = source.read_bytes().splitlines(keepends=True)
                source.write_bytes(b''.join(lines[:12]))
                original = source.read_bytes()
                before = read_run(source)
                resumed = continue_mlx.prepare(source, directory, Path(root) / 'continued.jsonl')
                resumed.run()
                result = read_run(resumed.path)
                self.assertEqual(source.read_bytes(), original)
                self.assertEqual(result['events'][:len(before['events'])], before['events'])
                self.assertEqual(len(result['events']), 20)
                self.assertEqual(result['events'][len(before['events'])]['agent_id'], before['events'][1]['agent_id'])
                self.assertEqual(result['summary']['status'], 'completed')
                self.assertEqual(result['start']['experiment']['source_run_id'], before['start']['run_id'])
                rows = [dashboard.record(source, [protocol]), dashboard.record(resumed.path, [protocol])]
                paths = {before['start']['run_id']: source, result['start']['run_id']: resumed.path}
                dashboard.validate_continuations(rows, paths)
                rows[1]['continuation']['source_event_count'] += 1
                with self.assertRaisesRegex(ValueError, 'source prefix'):
                    dashboard.validate_continuations(rows, paths)


if __name__ == '__main__':
    unittest.main()
