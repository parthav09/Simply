"""Explicit offline model plans: fewer requests, identical physical authority."""
import copy
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents.base import Decision, ProposalResult
from agents.openai_provider import OpenAIProvider
from agents.schema import MAX_PLAN_ACTIONS, parse_action_plan
from agents.state import CartItem
from core.budget import CampaignLedger
from core.customers import instantiate_agents
from core.export_replay import build_bundle
from core.grid import build_store
from core.perception import SHELF_SIGHT_RADIUS, grabbable_product_ids
from core.rounds import RoundCoordinator
from core.run_log import RunLogError, read_run
from core.session import SimulationSession
from live.protocol import LiveProjection


def plan_result(actions, allowed, telemetry=None):
    raw = json.dumps({'reason': 'OFFLINE explicit plan', 'actions': [
        {'step': step, 'product_id': product_id} for step, product_id in actions]})
    plan = parse_action_plan(raw, allowed)
    return ProposalResult(raw, plan[0] if plan else None, telemetry, plan[1:])


class PlanFixture:
    provider_id = model = 'scripted_test'
    supports_action_plans = True

    def __init__(self, plans):
        self.plans = iter(plans)
        self.calls = 0

    def request_plan(self, prompt, allowed_steps, shopper_id):
        self.calls += 1
        return plan_result(next(self.plans), allowed_steps, {
            'request_submitted': True, 'request_id': f'OFFLINE-{self.calls}',
            'estimated_cost_micros': 10, 'usage': {'promptTokenCount': 100},
        })


class ActionPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def session(self, provider, *, position=(0, 13), **kwargs):
        grid = build_store()
        shoppers = grid.spawn(instantiate_agents(count=1, turn_budget=kwargs.get('turn_budget', 120)))
        shoppers[0].state.x, shoppers[0].state.y = position
        return SimulationSession(shopper_count=1, grid=grid, shoppers=shoppers,
            decide=provider, output_path=self.root / f'{len(list(self.root.iterdir()))}.jsonl', **kwargs)

    def test_eight_explicit_moves_use_one_request_and_eight_canonical_events(self):
        provider = PlanFixture([[('move_right', '')] * MAX_PLAN_ACTIONS])
        session = self.session(provider, max_rounds=8)
        with patch('urllib.request.urlopen', side_effect=AssertionError('offline only')):
            session.run()
        run = read_run(session.path)
        self.assertEqual(provider.calls, 1)
        self.assertEqual([e['after']['x'] for e in run['events']], list(range(1, 9)))
        self.assertEqual([e['after']['turns_used'] for e in run['events']], list(range(1, 9)))
        self.assertEqual([e['telemetry']['plan_action_index'] for e in run['events']], list(range(8)))
        self.assertEqual(sum(e['telemetry']['request_submitted'] for e in run['events']), 1)
        self.assertEqual(run['summary']['resources']['usage']['promptTokenCount'], 100)
        self.assertEqual(run['summary']['resources']['known_estimated_cost_usd'], .00001)
        self.assertEqual(run['summary']['resources']['unknown_usage_requests'], 0)
        self.assertEqual(run['summary']['resources']['unknown_cost_attempts'], 0)
        self.assertEqual(session.shoppers[0].state.cart, [])
        projection = LiveProjection()
        for line in session.path.read_bytes().splitlines(keepends=True):
            projection.append(line)
        self.assertEqual(projection.snapshot(), json.loads(build_bundle(session.path, allow_test=True)['payload_json']))

    def test_cached_plans_do_not_block_peer_requests(self):
        class UnevenFixture(PlanFixture):
            def request_plan(self, prompt, allowed_steps, shopper_id):
                self.calls += 1
                length = 8 if shopper_id == self.long_id else 1
                return plan_result([('move_right', '')] * length, allowed_steps)
        provider = UnevenFixture([])
        grid = build_store();shoppers = grid.spawn(instantiate_agents(count=2))
        for shopper in shoppers:
            shopper.state.x, shopper.state.y = 0, 13
            shopper.prompt_variant = 'informed'
        provider.long_id = shoppers[-1].customer_id
        coordinator = RoundCoordinator(provider)
        for _ in range(8):
            coordinator.run(grid, shoppers)
        self.assertEqual(provider.calls, 9)
        self.assertEqual([s.turns_used for s in shoppers], [8, 8])

    def test_waiting_for_a_peers_plan_does_not_shorten_an_action_allowance(self):
        class UnevenFixture(PlanFixture):
            def request_plan(self, prompt, allowed_steps, shopper_id):
                self.calls += 1
                length = 8 if shopper_id == self.long_id else 1
                return plan_result([('move_right', '')] * length, allowed_steps)
        grid = build_store();shoppers = grid.spawn(instantiate_agents(count=2))
        for shopper in shoppers:
            shopper.state.x, shopper.state.y = 0, 13
        provider = UnevenFixture([]);provider.long_id = shoppers[-1].customer_id
        session = SimulationSession(shopper_count=2, grid=grid, shoppers=shoppers,
            decide=provider, max_rounds=8, output_path=self.root / 'uneven.jsonl')
        session.run();run = read_run(session.path)
        self.assertEqual([s.turns_used for s in shoppers], [8, 8])
        self.assertLessEqual(session.rounds_completed, 16)
        self.assertEqual(provider.calls, 9)
        self.assertEqual(run['start']['config']['action_planning']['action_limit'], 8)
        self.assertEqual({s['stop_reason'] for s in run['summary']['shoppers']}, {'action_limit'})

    def test_record_reader_rejects_altered_plan_source_and_duplicate_metering(self):
        provider = PlanFixture([[('move_right', '')] * 3])
        session = self.session(provider, max_rounds=3);session.run()
        rows = [json.loads(line) for line in session.path.read_text().splitlines()]
        for key, value in [('plan_action_index', 0), ('estimated_cost_micros', 10),
                           ('request_submitted', True), ('source_request_id', 'other')]:
            with self.subTest(key=key):
                changed = copy.deepcopy(rows)
                changed[2]['telemetry'][key] = value
                target = self.root / f'tampered-{key}.jsonl'
                target.write_text(''.join(json.dumps(r)+'\n' for r in changed))
                with self.assertRaises(RunLogError):
                    read_run(target)
        changed = copy.deepcopy(rows)
        changed[2]['raw_response'] = changed[2]['raw_response'].replace('move_right', 'move_left')
        target = self.root / 'tampered-source.jsonl'
        target.write_text(''.join(json.dumps(r)+'\n' for r in changed))
        with self.assertRaises(RunLogError):
            read_run(target)

    def test_new_grabbable_assortment_interrupts_before_walking_past(self):
        provider = PlanFixture([[('move_up', '')] * 4, [('move_left', '')]])
        session = self.session(provider, position=(2, 13), max_rounds=3)
        session.run();run = read_run(session.path)
        self.assertEqual(provider.calls, 2)
        self.assertEqual([e['action']['step'] for e in run['events']], ['move_up', 'move_up', 'move_left'])
        self.assertEqual(run['events'][1]['telemetry']['plan_interrupted'], 'new_grabbable_products')
        self.assertEqual(session.shoppers[0].state.cart, [], 'Seeing an item cannot purchase it')

    def test_multiple_explicit_grabs_are_not_clamped_to_budget_or_list(self):
        grid = build_store();product = next(iter(grid.products.values()))
        cell = grid.stand_cells_for((product['x'], product['y']))[0]
        provider = PlanFixture([[('grab', product['id'])] * 3])
        session = self.session(provider, position=cell, max_rounds=3)
        session.run()
        self.assertEqual(provider.calls, 1)
        self.assertEqual([i.product_id for i in session.shoppers[0].state.cart], [product['id']] * 3)
        self.assertTrue(all(e['outcome'] == 'applied' for e in read_run(session.path)['events']))

    def test_rejected_grab_discards_tail_instead_of_repairing_or_purchasing(self):
        provider = PlanFixture([[('grab', 'does-not-exist'), ('move_left', '')], [('move_left', '')]])
        grid = build_store();product = next(iter(grid.products.values()))
        cell = grid.stand_cells_for((product['x'], product['y']))[0]
        session = self.session(provider, position=cell, max_rounds=2)
        session.run();run = read_run(session.path)
        self.assertEqual(provider.calls, 2)
        self.assertEqual(run['events'][0]['outcome'], 'grid_rejected')
        self.assertEqual(run['events'][0]['telemetry']['plan_interrupted'], 'action_failed')
        self.assertEqual(session.shoppers[0].state.cart, [])

    def test_illegal_later_move_is_recorded_then_tail_is_discarded(self):
        provider = PlanFixture([[('move_right', ''), ('move_down', ''), ('move_right', '')], [('move_right', '')]])
        session = self.session(provider, max_rounds=3)
        session.run();run = read_run(session.path)
        self.assertEqual(provider.calls, 2)
        self.assertEqual([e['outcome'] for e in run['events']], ['applied', 'invalid_decision', 'applied'])
        self.assertEqual(run['events'][1]['after']['turns_used'], 2)
        self.assertEqual(session.shoppers[0].state.x, 2)

    def test_unexpected_state_discards_plan_and_proposals_never_cache_actions(self):
        provider = PlanFixture([[('move_right', '')] * 3, [('move_up', '')]])
        session = self.session(provider, max_rounds=2)
        session.step()
        session.shoppers[0].state.x = 0
        # Exercise the coordinator boundary; external state editing is not a
        # supported session control and intentionally cannot form a valid log.
        session.coordinator.run(session.grid, session.shoppers)
        self.assertEqual(provider.calls, 2)
        self.assertEqual(session.shoppers[0].state.y, 12)
        session.finish('cancelled', 'offline state change test')
        provider = PlanFixture([[('move_right', '')] * 3] * 2)
        session = self.session(provider, max_rounds=2, propose_only=True)
        session.run()
        self.assertEqual(provider.calls, 2)
        self.assertEqual(session.shoppers[0].turns_used, 0)
        self.assertEqual(session.shoppers[0].state.x, 0)
        self.assertEqual(session.coordinator.pending_plans, {})

    def test_turn_limit_and_stop_do_not_execute_the_tail(self):
        provider = PlanFixture([[('move_right', '')] * 8])
        session = self.session(provider, max_rounds=10, turn_budget=2)
        session.run()
        self.assertEqual(session.shoppers[0].state.x, 2)
        self.assertEqual(len(read_run(session.path)['events']), 2)
        provider = PlanFixture([[('move_right', '')] * 8])
        session = self.session(provider, max_rounds=10)
        session.step();session.stop();session.run()
        self.assertEqual(session.shoppers[0].state.x, 1)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(read_run(session.path)['summary']['status'], 'cancelled')

    def test_two_explicit_checkout_actions_can_share_one_request(self):
        provider = PlanFixture([[('checkout', ''), ('checkout', ''), ('move_right', '')]])
        grid = build_store();shoppers = grid.spawn(instantiate_agents(count=1))
        product = next(iter(grid.products.values()))
        shoppers[0].state.x, shoppers[0].state.y = 16, 12
        shoppers[0].state.cart.append(CartItem(product['id'], product['name']))
        session = SimulationSession(shopper_count=1, grid=grid, shoppers=shoppers,
            decide=provider, max_rounds=5, output_path=self.root / 'checkout.jsonl')
        session.run();run = read_run(session.path)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(run['summary']['finished_count'], 1)
        self.assertEqual(len(run['events']), 2)

    def test_nearby_assortments_are_local_and_reach_is_unchanged(self):
        session = self.session(PlanFixture([]), max_rounds=1)
        shopper = session.shoppers[0];grid = session.grid
        before = copy.deepcopy(shopper.state)
        with patch.object(grid, 'find_path', side_effect=AssertionError('no route selection')):
            prompt = shopper.prompt(grid.observe(shopper), action_plan=True)
        facts = json.loads(prompt.split('Current state: ', 1)[1].splitlines()[0])
        expected = [s for s in grid.shelves if grid.distance_to_shelf(shopper.state.x, shopper.state.y, s) <= SHELF_SIGHT_RADIUS]
        self.assertEqual({tuple(s['position']) for s in facts['nearby_shelves']}, {(s.x, s.y) for s in expected})
        self.assertEqual({p['product_id'] for p in facts['grabbable_products']}, grabbable_product_ids(grid, shopper.state.x, shopper.state.y))
        self.assertEqual(shopper.state, before)
        session.finish('cancelled', 'offline visibility test')

    def test_plan_parser_rejects_invalid_contracts_without_truncating_them(self):
        valid = {'reason': 'fixture', 'actions': [{'step': 'move_right', 'product_id': ''}]}
        for value in (None, [], {}, {**valid, 'extra': True}, {**valid, 'reason': []},
                      {**valid, 'actions': []}, {**valid, 'actions': valid['actions'] * 9},
                      {**valid, 'actions': [{'step': 'teleport', 'product_id': ''}]},
                      {**valid, 'actions': [{'step': 'move_right', 'product_id': None}]},
                      {**valid, 'actions': [{'step': 'move_right', 'product_id': '', 'extra': 1}]}):
            with self.subTest(value=value):
                self.assertEqual(parse_action_plan(json.dumps(value), ('move_right',)), ())
        self.assertEqual(parse_action_plan(json.dumps(valid), ('move_left',)), ())

    def test_real_provider_plan_path_meters_once_and_records_exact_schema(self):
        ledger = CampaignLedger(self.root / 'ledger.sqlite3')
        provider = OpenAIProvider(ledger, 'OFFLINE-plan-transport')
        raw = json.dumps({'reason': 'OFFLINE fixture', 'actions': [{'step': 'move_right', 'product_id': ''}] * 8})
        payload = {'status': 'completed', 'model': provider.model,
            'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': raw}]}],
            'usage': {'input_tokens': 100, 'output_tokens': 80, 'total_tokens': 180,
                      'input_tokens_details': {'cached_tokens': 0, 'cache_write_tokens': 0},
                      'output_tokens_details': {'reasoning_tokens': 0}}}
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'OFFLINE-key'}), \
             patch('urllib.request.urlopen', return_value=io.BytesIO(json.dumps(payload).encode())) as transport:
            session = self.session(provider, max_rounds=8)
            session.run()
        run = read_run(session.path)
        self.assertEqual(transport.call_count, 1)
        body = json.loads(transport.call_args.args[0].data)
        self.assertEqual(body['max_output_tokens'], 512)
        self.assertEqual(body['text']['format']['schema']['properties']['actions']['maxItems'], 8)
        self.assertEqual(run['start']['config']['generation']['max_output_tokens'], 512)
        self.assertEqual(ledger.snapshot()['requests'], 1)
        self.assertEqual(run['summary']['resources']['known_estimated_cost_usd'], .00005)
        self.assertEqual(run['summary']['resources']['usage']['candidatesTokenCount'], 80)


if __name__ == '__main__':
    unittest.main()
