"""Unique products and single-action checkout for new sessions; legacy replay stays intact."""
import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from agents.base import Decision,ProposalResult
from core.grid import build_store
from core.customers import instantiate_agents
from core.session import SimulationSession
from core.shopping import SIMPLE_SHOPPING,unique_profile
from core.run_log import read_run,RunLogError
from core.export_replay import build_bundle
from core.accounting import cents
from live.protocol import LiveProjection


class CheckoutFixture:
    model=provider_id='scripted_test'
    def __init__(self,shopper,grid):self.shopper=shopper;self.grid=grid;self.calls=0
    def request(self,prompt,allowed_steps,shopper_id):
        self.calls+=1
        if 'grab' in allowed_steps and not self.shopper.state.cart:
            decision=Decision('grab',self.shopper.state.requirements[0].product_id, 'OFFLINE target pickup')
        elif 'checkout' in allowed_steps:
            decision=Decision('checkout',reason='OFFLINE pay once')
        else:
            position=(self.shopper.state.x,self.shopper.state.y)
            destination=self.grid.find_path(position,self.grid.checkout)[0]
            dx,dy=destination[0]-position[0],destination[1]-position[1]
            step={(-1,0):'move_left',(1,0):'move_right',(0,-1):'move_up',(0,1):'move_down'}[(dx,dy)]
            decision=Decision(step,reason='OFFLINE explicit fixture route')
        return ProposalResult(json.dumps(decision.to_dict()),decision,{'request_submitted':False,'estimated_cost_micros':0})


class SimpleShoppingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def setup_trip(self,layout='costco_back_anchor'):
        grid=build_store(layout);shoppers=grid.spawn(instantiate_agents(count=1));shopper=shoppers[0]
        first=replace(shopper.customer.shopping_list[0],quantity=3)
        shopper.customer=replace(shopper.customer,shopping_list=(first,first),budget_per_trip_usd=.01)
        grid.place_requirements(shopper)
        product=grid.products[first.product_id]
        shopper.state.x,shopper.state.y=grid.stand_cells_for((product['x'],product['y']))[0]
        provider=CheckoutFixture(shopper,grid)
        session=SimulationSession(layout_name=layout,shopper_count=1,grid=grid,shoppers=shoppers,
            decide=provider,navigation_policy='model_only',allow_action_plans=False,
            shopping_rules=SIMPLE_SHOPPING,output_path=self.root/f'{layout}.jsonl')
        return session,provider,product

    def test_unique_targets_do_not_modify_source_profile_or_budget(self):
        customer=instantiate_agents(count=1)[0].customer
        first=replace(customer.shopping_list[0],quantity=3)
        original=replace(customer,shopping_list=(first,first),budget_per_trip_usd=.01)
        unique=unique_profile(original)
        self.assertEqual(len(original.shopping_list),2);self.assertEqual(first.quantity,3)
        self.assertEqual(len(unique.shopping_list),1);self.assertEqual(unique.shopping_list[0].quantity,1)
        self.assertEqual(unique.budget_per_trip_usd,.01)

    def test_one_checkout_pays_for_an_over_budget_basket_and_finishes_in_both_layouts(self):
        for layout in ('costco_back_anchor','neighborhood_express'):
            session,provider,product=self.setup_trip(layout);session.run();run=read_run(session.path)
            self.assertEqual(run['start']['config']['shopping_rules'],SIMPLE_SHOPPING)
            self.assertEqual(len(run['start']['shoppers'][0]['customer']['shopping_list']),1)
            self.assertEqual(run['start']['shoppers'][0]['state']['requirements'][0]['quantity'],1)
            self.assertEqual(run['summary']['finished_count'],1)
            self.assertEqual(run['summary']['purchased_unit_fulfillment'],1)
            self.assertEqual(run['summary']['sales_cents'],cents(product['price']))
            self.assertEqual(run['summary']['shoppers'][0]['checkout_overshoot_cents'],cents(product['price'])-1)
            checkouts=[event for event in run['events'] if event.get('action',{}).get('step')=='checkout']
            self.assertEqual(len(checkouts),1);self.assertEqual(checkouts[0]['after']['phase'],'FinishedState')
            self.assertEqual(provider.calls,len(run['events']))
            self.assertFalse(any(event['after']['phase']=='CheckoutState' for event in run['events']))
            self.assertIn('One checkout action',run['events'][-1]['prompt'])
            projection=LiveProjection()
            for line in session.path.read_bytes().splitlines(keepends=True):projection.append(line)
            self.assertEqual(projection.snapshot(),json.loads(build_bundle(session.path,allow_test=True)['payload_json']))

    def test_duplicate_grab_is_rejected_without_clipping_budget_or_replacing_items(self):
        session,_,product=self.setup_trip();shopper=session.shoppers[0]
        self.assertTrue(session.grid.apply(shopper,Decision('grab',product['id'])))
        self.assertFalse(session.grid.apply(shopper,Decision('grab',product['id'])))
        self.assertEqual(len(shopper.state.cart),1)
        prompt=shopper.prompt();facts=json.loads(prompt.split('Current state: ',1)[1].split('\nChoose one step:',1)[0])
        self.assertNotIn(product['id'],[item['product_id'] for item in facts['grabbable_products']])
        self.assertLess(facts['remaining_budget_cents'],0)
        session.finish('cancelled','OFFLINE duplicate inspection')

    def test_new_real_model_defaults_use_simple_rules_without_dispatch(self):
        class Provider:model=provider_id='scripted_test'
        with patch('agents.providers.build_provider',return_value=Provider()):
            session=SimulationSession(shopper_count=1,output_path=self.root/'default.jsonl',ledger_path=self.root/'ledger.sqlite3')
        self.assertEqual(session.header['config']['shopping_rules'],SIMPLE_SHOPPING)
        self.assertTrue(all(item.quantity==1 for item in session.shoppers[0].customer.shopping_list))
        session.finish('cancelled','OFFLINE no model dispatch')

    def test_single_checkout_record_cannot_be_changed_into_an_intermediate_phase(self):
        session,_,_=self.setup_trip();session.run()
        records=[json.loads(line) for line in session.path.read_text().splitlines()]
        checkout=next(row for row in records if row['type']=='decision' and row.get('action',{}).get('step')=='checkout')
        checkout['after']['phase']='CheckoutState'
        path=self.root/'tampered.jsonl';path.write_text(''.join(json.dumps(row)+'\n' for row in records))
        with self.assertRaisesRegex(RunLogError,'checkout transition'):read_run(path)

    def test_empty_cart_cannot_checkout_and_legacy_golden_remains_readable(self):
        session,_,_=self.setup_trip();shopper=session.shoppers[0]
        shopper.state.x,shopper.state.y=session.grid.checkout[0]
        self.assertFalse(session.grid.apply(shopper,Decision('checkout')))
        self.assertEqual(type(shopper.state).__name__,'BrowsingState')
        session.finish('cancelled','OFFLINE empty cart inspection')
        legacy=read_run(Path(__file__).parent/'fixtures/golden.jsonl')
        phases=[event['after']['phase'] for event in legacy['events']]
        self.assertIn('CheckoutState',phases);self.assertIn('FinishedState',phases)
