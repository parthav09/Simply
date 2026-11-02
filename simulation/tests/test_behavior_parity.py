"""Gary-2 shared semantics, soft shopper budgets, and versioned corrections."""
import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents.base import Decision, ProposalResult
from core.accounting import basket, cents
from core.grid import build_store
from core.customers import instantiate_agents
from core.navigation import GARY2, GARY2_CURRENT, MODEL_ONLY, adjusted_action
from core.session import SimulationSession
from core.run_log import read_run


class BehaviorParityTests(unittest.TestCase):
    def test_multiple_reachable_targets_use_gary2_left_right_up_down_priority(self):
        before = {'x': 3, 'y': 3, 'cart': [], 'requirements': [
            {'product_id': 'right', 'quantity': 1}, {'product_id': 'left', 'quantity': 1}],
            'allowed_steps': ['grab', 'move_down'], 'turn_budget': 120, 'turns_used': 0}
        layout = {'checkout': [[8, 8]], 'shelves': [
            {'x': 4, 'y': 3, 'offsets': [[0, 0]], 'products': [{'id': 'right'}]},
            {'x': 2, 'y': 3, 'offsets': [[0, 0]], 'products': [{'id': 'left'}]}]}
        self.assertEqual(adjusted_action(Decision('move_down'), before, layout, {}, GARY2_CURRENT)[0].product_id, 'left')
        self.assertEqual(adjusted_action(Decision('move_down'), before, layout, {}, GARY2)[0].product_id, 'right')

    def test_checkout_urgency_overrides_impulse_and_historical_policy_is_preserved(self):
        before = {'x': 3, 'y': 3, 'cart': [{'product_id': 'owned', 'quantity': 1}],
            'requirements': [{'product_id': 'target', 'quantity': 1}],
            'allowed_steps': ['grab', 'move_left', 'move_right'], 'turn_budget': 120, 'turns_used': 90}
        layout = {'checkout': [[8, 3]], 'shelves': [{'x': 3, 'y': 4, 'offsets': [[0, 0]], 'products': [{'id': 'treat'}]}]}
        proposal = Decision('grab', 'treat', 'A fitting treat')
        self.assertEqual(adjusted_action(proposal, before, layout, {}, GARY2)[0], proposal)
        self.assertEqual(adjusted_action(proposal, before, layout, {}, GARY2_CURRENT)[0].step, 'move_right')
        before['turns_used'] = 0
        self.assertEqual(adjusted_action(proposal, before, layout, {}, GARY2_CURRENT)[0], proposal)
        self.assertEqual(adjusted_action(proposal, before, layout, {}, GARY2_CURRENT, action_limit=1)[0].step, 'grab')
        before['allowed_steps'].append('checkout')
        self.assertEqual(adjusted_action(proposal, before, layout, {}, GARY2_CURRENT, action_limit=10)[0].step, 'checkout')

    def test_over_budget_grab_and_checkout_are_applied_and_measured_without_trimming(self):
        with tempfile.TemporaryDirectory() as directory:
            grid = build_store(); shoppers = grid.spawn(instantiate_agents(count=1)); shopper = shoppers[0]
            product = grid.products[shopper.customer.shopping_list[0].product_id]
            shopper.customer = replace(shopper.customer, budget_per_trip_usd=.01)
            shopper.prompt_variant = 'informed'
            shopper.state.x, shopper.state.y = grid.stand_cells_for((product['x'], product['y']))[0]
            self.assertTrue(grid.apply(shopper, Decision('grab', product['id'])))
            self.assertGreater(basket([vars(i) for i in shopper.state.cart], list(grid.products.values()))['basket_cents'], 1)
            self.assertIn('negative remaining_budget_cents does not block', shopper.prompt())
            shopper.state.x, shopper.state.y = grid.checkout[0]
            session = SimulationSession(shopper_count=1, max_rounds=2, grid=grid, shoppers=shoppers,
                navigation_policy=GARY2_CURRENT, decide=lambda *_: Decision('checkout'), output_path=Path(directory)/'overspend.jsonl')
            session.run(); run = read_run(session.path); summary = run['summary']
            self.assertEqual(summary['finished_count'], 1)
            self.assertEqual(summary['sales_cents'], cents(product['price']))
            self.assertEqual(summary['shoppers'][0]['checkout_overshoot_cents'], cents(product['price'])-1)
            self.assertEqual(summary['overspending_fraction'], 1)
            self.assertEqual(len(run['end']['shoppers'][0]['state']['cart']), 1)
            self.assertTrue(all(event['outcome'] == 'applied' for event in run['events']))

    def test_common_states_match_pinned_upstream_decisions(self):
        fixture = json.loads((Path(__file__).parent/'fixtures/gary2-policy-parity.json').read_text())
        self.assertEqual(fixture['commit'], '93a4d0dac630461cbbb1d3e6e07b156f0b1bb7a3')
        self.assertGreaterEqual(len(fixture['cases']), 100)
        for case in fixture['cases']:
            with self.subTest(case=case['name']):
                visits = {tuple(cell): count for cell, count in case['visits']}
                decision, _ = adjusted_action(Decision(**case['proposal']), case['before'], case['layout'], visits, GARY2_CURRENT)
                self.assertEqual([decision.step, decision.product_id], case['expected'])

    def test_model_only_study_uses_one_request_per_action_without_plans(self):
        class Provider:
            model = provider_id = 'scripted_test'
            supports_action_plans = True
            calls = 0
            def request(self, prompt, allowed_steps, shopper_id):
                self.calls += 1
                decision = Decision(allowed_steps[0])
                return ProposalResult(json.dumps(decision.to_dict()), decision)
            def request_plan(self, *args, **kwargs):
                raise AssertionError('Model comparison must not use a different planning interface')
        with tempfile.TemporaryDirectory() as directory:
            provider = Provider()
            session = SimulationSession(shopper_count=1, max_rounds=3, decide=provider,
                navigation_policy=MODEL_ONLY, allow_action_plans=False, output_path=Path(directory)/'single.jsonl')
            session.run(); run = read_run(session.path)
            self.assertEqual(provider.calls, 3)
            self.assertNotIn('action_planning', run['start']['config'])
            self.assertEqual(run['start']['config']['decision_mode'], 'single_action')

    def test_single_action_study_rejects_a_provider_that_returns_a_continuation(self):
        def provider(prompt, allowed):
            decision = Decision(allowed[0])
            return ProposalResult(json.dumps(decision.to_dict()), decision, continuation=(decision,))
        with tempfile.TemporaryDirectory() as directory:
            session = SimulationSession(shopper_count=1, max_rounds=2, decide=provider,
                navigation_policy=MODEL_ONLY, allow_action_plans=False, output_path=Path(directory)/'invalid-plan.jsonl')
            session.run(); run = read_run(session.path)
            self.assertEqual(len(run['events']), 2)
            self.assertTrue(all(event['outcome'] == 'invalid_decision' for event in run['events']))
            self.assertFalse(session.coordinator.pending_plans)
