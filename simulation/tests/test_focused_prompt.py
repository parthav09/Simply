"""Focused prompt facts must describe physical evidence without choosing actions."""
import copy
import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agents.base import Decision
from agents.providers import FakeDecisionProvider
from core.config import ACTIVE_LAYOUT_IDS
from core.session import SimulationSession


def facts(shopper,grid):
    prompt=shopper.prompt(grid.observe(shopper))
    return json.loads(prompt.split('Current state: ',1)[1].split('\nChoose one step:',1)[0])


class FocusedPromptTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)

    def session(self,**kwargs):
        return SimulationSession(shopper_count=1,max_rounds=2,decide=kwargs.pop('decide',FakeDecisionProvider()),
            output_path=Path(self.temp.name)/f'{len(list(Path(self.temp.name).iterdir()))}.jsonl',**kwargs)

    def test_access_cells_and_floor_map_agree_with_each_physical_layout(self):
        for layout in ACTIVE_LAYOUT_IDS:
            session=self.session(layout_name=layout);shopper=session.shoppers[0];grid=session.grid
            before=copy.deepcopy(shopper.state)
            with patch.object(grid,'find_path',side_effect=AssertionError('Prompt must not select a route')):
                state=facts(shopper,grid)
            self.assertEqual(shopper.state,before)
            for shelf,entry in zip(grid.shelves,state['department_locations']):
                expected={(x,y) for y in range(grid.height) for x in range(grid.width)
                          if grid.walkable(x,y) and grid.distance_to_shelf(x,y,shelf)==1}
                self.assertEqual({tuple(c) for c in entry['walkable_access_cells']},expected)
            for y,row in enumerate(state['floor_map']['rows']):
                self.assertEqual(len(row),grid.width)
                for x,symbol in enumerate(row):
                    self.assertEqual(symbol=='#',(x,y) in grid.blocked)
            self.assertEqual(state['floor_map']['rows'][shopper.state.y][shopper.state.x],'@')
            session.finish('cancelled','offline prompt inspection')

    def test_visible_need_quantities_and_price_flags_follow_actual_cart(self):
        session=self.session();grid=session.grid;s=session.shoppers[0]
        product=grid.products[s.customer.shopping_list[0].product_id]
        item=replace(s.customer.shopping_list[0],quantity=2,max_acceptable_unit_price=product['price']-.01)
        s.customer=replace(s.customer,shopping_list=(item,),budget_per_trip_usd=product['price']+.01)
        s.state.x,s.state.y=grid.stand_cells_for((product['x'],product['y']))[0]
        self.assertTrue(grid.apply(s,Decision('grab',product['id'])))
        state=facts(s,grid)
        visible={p['product_id']:p for p in state['grabbable_products']}
        target=visible[product['id']]
        self.assertEqual(target['remaining_requested_quantity'],1)
        self.assertTrue(target['matches_remaining_list'])
        self.assertFalse(target['within_item_price_limit'])
        self.assertFalse(target['affordable_with_remaining_budget'])
        expected={p['id'] for shelf in grid.shelves if grid.distance_to_shelf(s.state.x,s.state.y,shelf)==1 for p in shelf.products}
        self.assertEqual(set(visible),expected)
        self.assertEqual(len(s.state.cart),1,'Building a prompt must not purchase another unit')
        session.finish('cancelled','offline prompt inspection')

    def test_last_public_plan_and_visit_counts_come_from_confirmed_history(self):
        choices=iter([Decision('move_left',reason='Visit the left corridor.'),Decision('move_right',reason='Return toward the pantry.')])
        session=self.session(decide=lambda prompt,allowed:next(choices));session.run()
        s=session.shoppers[0];state=facts(s,session.grid)
        self.assertEqual(state['your_last_plan'],'Return toward the pantry.')
        self.assertIn(state['checkout_urgency'], {'low', 'medium', 'high', 'critical'})
        self.assertIn('IMPULSE:', s.prompt())
        for step,destination in state['legal_move_destinations'].items():
            visits=sum([t.x_after,t.y_after]==destination for t in s.trajectory)
            visits+=int([s.trajectory[0].x_before,s.trajectory[0].y_before]==destination)
            self.assertEqual(state['adjacent_destination_visit_counts'][step],visits)
        self.assertEqual([o.decision.step for o in s.decision_history],['move_left','move_right'])

    def test_prompt_uses_the_same_effective_action_limit_as_execution(self):
        session = self.session(); state = facts(session.shoppers[0], session.grid)
        self.assertEqual(state['action_limit'], 2)
        self.assertEqual(state['turns_remaining'], 2)
        session.finish('cancelled', 'offline action-limit inspection')


if __name__=='__main__':unittest.main()
