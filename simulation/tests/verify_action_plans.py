"""OFFLINE comparison of single actions and explicit plans on frozen full trips.

Fixture routes choose every action. They are never a production shopper policy
or evidence of real model behavior. No remote API requests are made.
"""
import argparse
import copy
import json
import os
from pathlib import Path
from unittest.mock import patch

from verify_product_workflow import (
    OfflineTransportProvider, SIMULATION_DIR, scripted_actions,
)
from agents.openai_provider import OpenAIProvider
from core.budget import CampaignLedger
from core.config import ACTIVE_LAYOUT_IDS
from core.export_replay import build_bundle
from core.recording import RecordingView
from core.run_log import read_run
from core.session import SimulationSession
from core.grid import build_store
from evaluation.benchmark import load_benchmark, instantiate_benchmark
from live.protocol import LiveProjection


class OfflinePlanTransport(OfflineTransportProvider):
    supports_action_plans = True

    def __init__(self, ledger, queues):
        super().__init__(ledger, queues)
        self.actions = {key: list(value) for key, value in queues.items()}

    def request_plan(self, prompt, allowed_steps, shopper_id):
        self.local.shopper_id = shopper_id
        return OpenAIProvider.request_plan(self, prompt, allowed_steps, shopper_id)

    def transport(self, request, timeout):
        import io
        body = json.loads(request.data)
        facts = json.loads(body['input'].split('Current state: ', 1)[1].splitlines()[0])
        remaining = self.actions[self.local.shopper_id][facts['turns_used']:]
        visible = {p['product_id'] for p in facts['grabbable_products']}
        actions = []
        for action in remaining[:8]:
            if action['step'] == 'grab' and action['product_id'] not in visible:
                break
            actions.append({key: action[key] for key in ('step', 'product_id')})
        assert actions, 'Fixture must supply a currently valid first action'
        assert body['text']['format']['schema']['properties']['actions']['maxItems'] == 8
        with self.lock:
            self.calls += 1
        raw = json.dumps({'reason': 'OFFLINE fixture plan', 'actions': actions})
        response = {'id': 'OFFLINE-plan-response', 'model': 'OFFLINE-mocked-gpt-6-luna', 'status': 'completed',
                    'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': raw}]}],
                    'usage': {'input_tokens': 100, 'output_tokens': 80, 'total_tokens': 180,
                              'input_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0},
                              'output_tokens_details': {'reasoning_tokens': 0}}}
        return io.BytesIO(json.dumps(response).encode())


def verify(destination):
    destination = Path(destination);destination.mkdir(parents=True, exist_ok=True)
    benchmark = load_benchmark(SIMULATION_DIR / 'benchmarks/two_layouts_15_v2.json')
    results = []
    for layout in ACTIVE_LAYOUT_IDS:
        reference = None
        for plans in (False, True):
            name = f'{layout}-' + ('plans' if plans else 'single')
            grid = build_store(layout);shoppers = instantiate_benchmark(benchmark, 10, grid)
            ledger = CampaignLedger(destination / f'{name}.sqlite3')
            provider_type = OfflinePlanTransport if plans else OfflineTransportProvider
            provider = provider_type(ledger, {s.customer_id: scripted_actions(grid, s) for s in shoppers})
            session = SimulationSession(layout, 10, 120, 120, 10, decide=provider,
                output_path=destination / f'{name}.jsonl', grid=grid, shoppers=shoppers)
            with patch.dict(os.environ, {'OPENAI_API_KEY': 'OFFLINE-not-a-real-key'}), \
                 patch('urllib.request.urlopen', side_effect=provider.transport):
                session.run()
            run = read_run(session.path)
            assert run['summary']['finished_count'] == 10, (name, run['summary']['finished_count'])
            assert run['summary']['purchased_unit_fulfillment'] == 1
            assert not any(run['summary']['failures'].values())
            by_shopper = {s.customer_id: [
                {key: event[key] for key in ('before', 'after', 'outcome')}
                | {'action': {key: event['action'][key] for key in ('step', 'product_id')}}
                for event in run['events'] if event['agent_id'] == s.customer_id] for s in shoppers}
            if reference is None:
                reference = copy.deepcopy(by_shopper)
            else:
                assert by_shopper == reference, 'Planning changed the fixture business transitions'
            view = RecordingView(run['start']);frames = [view.snapshot()]
            for event in run['events']:
                view.append(event);frames.append(view.snapshot())
            view.append(run['end']);frames[-1] = view.snapshot()
            bundle = build_bundle(session.path, allow_test=True)
            bundle_path = destination / f'{name}.bundle.json'
            bundle_path.write_text(json.dumps(bundle))
            expected_path = destination / f'{name}.expected.json'
            expected_path.write_text(json.dumps(frames))
            projection = LiveProjection()
            messages = []
            for line in session.path.read_bytes().splitlines(keepends=True):
                kind = projection.append(line)
                message = {'stream_version': 1, 'run': projection.snapshot()} if kind == 'run_start' else projection.transition(kind == 'run_end')
                messages.append({'kind': kind, 'message': message})
            assert projection.snapshot() == json.loads(bundle['payload_json'])
            messages_path = destination / f'{name}.messages.json'
            messages_path.write_text(json.dumps(messages))
            result = {'layout': layout, 'plans': plans, 'events': len(run['events']),
                      'requests': provider.calls, 'rounds': session.rounds_completed,
                      'finished': 10, 'bundle': str(bundle_path.resolve()),
                      'expected': str(expected_path.resolve()), 'messages': str(messages_path.resolve())}
            results.append(result)
            print(json.dumps(result), flush=True)
    for baseline, planned in zip(results[::2], results[1::2]):
        assert planned['requests'] < baseline['requests']
    (destination / 'verification.json').write_text(json.dumps({'real_api_requests': 0, 'results': results}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    verify(parser.parse_args().destination)
