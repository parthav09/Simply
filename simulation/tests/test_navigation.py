"""Navigation assistance stays Python-owned, recorded and replayable."""
import copy
import json
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents.base import Decision, ProposalResult
from core.export_replay import build_bundle
from core.navigation import GARY2, GARY2_CURRENT, MODEL_ONLY, adjusted_action
from core.run_log import RunLogError, read_run
from core.session import SimulationSession
from core.grid import build_store
from core.customers import instantiate_agents
from agents.state import CartItem
from live.protocol import LiveProjection


class SingleActionProvider:
    provider_id = model = 'scripted_test'
    supports_action_plans = True

    def __init__(self):
        self.calls = 0

    def request(self, prompt, allowed_steps, shopper_id):
        self.calls += 1
        decision = Decision(next(step for step in allowed_steps if step.startswith('move_')), reason='test proposal')
        return ProposalResult(json.dumps(decision.to_dict()), decision)

    def request_plan(self, *args, **kwargs):
        raise AssertionError('Assisted live runs must request one action at a time')


class NavigationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.before = {'x': 3, 'y': 3, 'allowed_steps': ['move_left', 'move_right', 'move_down'],
                       'cart': [], 'requirements': [{'product_id': 'target', 'quantity': 2}],
                       'turn_budget': 120, 'turns_used': 0}
        self.layout = {'shelves': [], 'checkout': [[8, 8]]}

    def test_loop_avoidance_chooses_a_legal_less_visited_cell(self):
        decision, why = adjusted_action(Decision('move_left'), self.before, self.layout, Counter({(2, 3): 5}))
        self.assertEqual(decision.step, 'move_down')
        self.assertIn('avoid revisiting', why)
        self.assertIn('Model proposed move_left', decision.reason)

    def test_fulfilled_basket_steers_to_checkout_and_selects_checkout_at_register(self):
        self.before['cart'] = [{'product_id': 'target', 'quantity': 2}]
        decision, why = adjusted_action(Decision('move_left'), self.before, self.layout, {})
        self.assertEqual(decision.step, 'move_right')
        self.before['allowed_steps'].append('checkout')
        decision, why = adjusted_action(Decision('move_left'), self.before, self.layout, {})
        self.assertEqual(decision.step, 'checkout')

    def test_assistance_completes_both_checkout_phases_through_core(self):
        grid = build_store()
        shoppers = grid.spawn(instantiate_agents(count=1))
        shopper = shoppers[0]
        shopper.state.x, shopper.state.y = grid.checkout[0]
        shopper.state.cart = [CartItem(item.product_id, item.name, item.quantity)
                              for item in shopper.state.requirements]
        provider = SingleActionProvider()
        session = SimulationSession(shopper_count=1, max_rounds=2, decide=provider,
            navigation_policy=GARY2, grid=grid, shoppers=shoppers, output_path=self.root / 'checkout.jsonl')
        session.run()
        run = read_run(session.path)
        self.assertEqual([e['action']['step'] for e in run['events']], ['checkout', 'checkout'])
        self.assertEqual(run['summary']['finished_count'], 1)
        self.assertEqual(provider.calls, 2)
        self.assertEqual([e['after']['phase'] for e in run['events']], ['CheckoutState', 'FinishedState'])

    def test_assisted_session_rejects_unexpected_multi_action_responses(self):
        def provider(prompt, allowed):
            move = Decision(next(step for step in allowed if step.startswith('move_')))
            return ProposalResult(None, move, continuation=(move,))
        session = SimulationSession(shopper_count=1, max_rounds=1, decide=provider,
            navigation_policy=GARY2, output_path=self.root / 'unexpected-plan.jsonl')
        session.run()
        event = read_run(session.path)['events'][0]
        self.assertEqual(event['outcome'], 'invalid_decision')
        self.assertIsNone(event['action'])

    def test_low_turns_steer_toward_checkout_but_empty_baskets_do_not(self):
        self.before['turns_used'] = 90
        self.before['cart'] = [{'product_id': 'other', 'quantity': 1}]
        decision, _ = adjusted_action(Decision('move_left'), self.before, self.layout, {})
        self.assertEqual(decision.step, 'move_right')
        self.before['cart'] = []
        proposal = Decision('move_left')
        self.assertEqual(adjusted_action(proposal, self.before, self.layout, {}), (proposal, None))

    def test_reachable_pickups_respect_required_quantities_and_physical_reach(self):
        self.layout['shelves'] = [{'x': 4, 'y': 3, 'offsets': [[0, 0]], 'products': [{'id': 'target'}]}]
        self.before['allowed_steps'].append('grab')
        self.before['cart'] = [{'product_id': 'target', 'quantity': 1}]
        decision, _ = adjusted_action(Decision('move_left'), self.before, self.layout, {})
        self.assertEqual((decision.step, decision.product_id), ('grab', 'target'))
        self.before['cart'][0]['quantity'] = 2
        decision, _ = adjusted_action(Decision('grab', 'target'), self.before, self.layout, {})
        self.assertNotEqual(decision.step, 'grab')
        self.before['cart'] = []
        self.layout['shelves'][0]['x'] = 6
        proposal = Decision('move_left')
        self.assertEqual(adjusted_action(proposal, self.before, self.layout, {}), (proposal, None))

    def test_impulse_grab_of_an_unowned_off_list_item_is_kept(self):
        self.layout['shelves'] = [{'x': 4, 'y': 3, 'offsets': [[0, 0]], 'products': [{'id': 'treat'}]}]
        self.before['allowed_steps'].append('grab')
        proposal = Decision('grab', 'treat', 'A fitting treat')
        self.assertEqual(adjusted_action(proposal, self.before, self.layout, {}), (proposal, None))
        self.layout['shelves'][0]['products'].append({'id': 'target'})
        decision, why = adjusted_action(proposal, self.before, self.layout, {})
        self.assertEqual((decision.step, decision.product_id), ('grab', 'target'))
        self.assertIn('list item', why)
        self.before['cart'] = [{'product_id': 'target', 'quantity': 2}]
        self.layout['shelves'][0]['products'] = [{'id': 'treat'}]
        decision, _ = adjusted_action(proposal, self.before, self.layout, {})
        self.assertNotEqual(decision.step, 'grab')

    def session(self, provider=None, **kwargs):
        return SimulationSession(shopper_count=1, max_rounds=3, decide=provider or SingleActionProvider(),
                                 navigation_policy=GARY2, output_path=self.root / 'run.jsonl', **kwargs)

    def test_one_request_per_action_and_adjusted_events_survive_live_export_and_tamper_checks(self):
        provider = SingleActionProvider()
        session = self.session(provider)
        shopper = session.shoppers[0]
        product = session.grid.products[shopper.state.requirements[0].product_id]
        shopper.state.x, shopper.state.y = session.grid.stand_cells_for((product['x'], product['y']))[0]
        # Recreate the session so the frozen initial position includes this setup.
        session.finish('cancelled', 'test setup')
        session = SimulationSession(shopper_count=1, max_rounds=3, decide=provider,
            navigation_policy=GARY2, grid=session.grid, shoppers=[shopper], output_path=self.root / 'assisted.jsonl')
        with patch('urllib.request.urlopen', side_effect=AssertionError('test must not call a model')):
            session.run()
        run = read_run(session.path)
        self.assertEqual(provider.calls, 3)
        self.assertNotIn('action_planning', run['start']['config'])
        self.assertEqual(run['events'][0]['action']['step'], 'grab')
        for event in run['events']:
            self.assertEqual(event['telemetry']['navigation']['proposed_action'], json.loads(event['raw_response']))
            self.assertEqual(event['after']['turns_used'], event['before']['turns_used'] + 1)
        projection = LiveProjection()
        for line in session.path.read_bytes().splitlines(keepends=True):
            projection.append(line)
        self.assertEqual(projection.snapshot(), json.loads(build_bundle(session.path, allow_test=True)['payload_json']))
        rows = [json.loads(line) for line in session.path.read_text().splitlines()]
        for mutate in (
            lambda event: event['telemetry'].pop('navigation'),
            lambda event: event['telemetry']['navigation'].update(adjustment='invented'),
            lambda event: event['telemetry']['navigation']['proposed_action'].update(reason='invented'),
        ):
            changed = copy.deepcopy(rows)
            mutate(changed[1])
            path = self.root / 'tampered.jsonl'
            path.write_text(''.join(json.dumps(row) + '\n' for row in changed))
            with self.assertRaisesRegex(RunLogError, 'navigation'):
                read_run(path)

    def test_provider_errors_and_invalid_responses_never_trigger_fallback_actions(self):
        for name, provider in [('invalid', lambda *args: None),
                               ('error', lambda *args: (_ for _ in ()).throw(RuntimeError('test failure')))]:
            session = SimulationSession(shopper_count=1, max_rounds=1, decide=provider,
                navigation_policy=GARY2, output_path=self.root / f'{name}.jsonl')
            session.run()
            event = read_run(session.path)['events'][0]
            self.assertIsNone(event['action'])
            self.assertEqual((event['before']['x'], event['before']['y']), (event['after']['x'], event['after']['y']))

    def test_real_session_default_uses_assistance_while_injected_tests_remain_explicit(self):
        with patch('agents.providers.build_provider', return_value=SingleActionProvider()):
            session = SimulationSession(shopper_count=1, output_path=self.root / 'default.jsonl',
                                        ledger_path=self.root / 'ledger.sqlite3')
        self.assertEqual(session.header['config']['navigation_policy'], GARY2_CURRENT)
        self.assertFalse(session.coordinator.uses_plans(session.shoppers[0]))
        session.finish('cancelled', 'test complete')
        session = SimulationSession(shopper_count=1, decide=SingleActionProvider(), output_path=self.root / 'injected.jsonl')
        self.assertEqual(session.header['config']['navigation_policy'], MODEL_ONLY)
        session.finish('cancelled', 'test complete')


if __name__ == '__main__':
    unittest.main()
