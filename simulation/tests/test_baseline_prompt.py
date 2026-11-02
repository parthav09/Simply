"""The baseline must match original recorded requests, not another builder call."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

SIMULATION_DIR=Path(__file__).resolve().parents[1]
if str(SIMULATION_DIR) not in sys.path:sys.path.insert(0,str(SIMULATION_DIR))
from agents.base import Observation
from agents.customer import Customer, ShoppingItem
from agents.prompts import baseline_prompt
from agents.shopper import Shopper
from agents.state import CartItem, NearbyShelf, Requirement

FIXTURE=SIMULATION_DIR/'tests/fixtures/baseline_prompt_v1.json'


def reconstruct(profile,state):
    customer=Customer(**{**profile,'shopping_list':tuple(ShoppingItem(**i) for i in profile['shopping_list'])})
    observation=Observation(customer=customer,x=state['x'],y=state['y'],phase=state['phase'],
        cart=tuple(CartItem(**i) for i in state['cart']),
        nearby_shelves=tuple(NearbyShelf(**i) for i in state['nearby_shelves']),
        requirements=tuple(Requirement(**i) for i in state['requirements']),
        allowed_steps=tuple(state['allowed_steps']))
    return Shopper(customer),observation


class FrozenBaselineTests(unittest.TestCase):
    def test_baseline_matches_all_original_recorded_requests_exactly(self):
        fixture=json.loads(FIXTURE.read_text())
        self.assertEqual(fixture['fixture_version'],1)
        self.assertEqual(fixture['source']['provider'],'gemini')
        self.assertEqual(fixture['source']['status'],'aborted')
        self.assertEqual(len(fixture['profiles']),3)
        self.assertEqual(len(fixture['cases']),9)
        for case in fixture['cases']:
            shopper,obs=reconstruct(fixture['profiles'][case['agent_id']],case['before'])
            with self.subTest(sequence=case['sequence']):
                self.assertEqual(baseline_prompt(shopper,obs),case['prompt'])

    def test_historical_prompt_reconstruction_is_independent_of_current_data(self):
        script="""
import builtins,json,sys,urllib.request
sys.path.insert(0,'simulation');sys.path.insert(0,'simulation/tests')
original=builtins.__import__
def load(name,*args,**kwargs):
    if name in ('core.grid','agents.llm','agents.openai_provider'):
        raise AssertionError('live simulation/provider dependency')
    return original(name,*args,**kwargs)
builtins.__import__=load
urllib.request.urlopen=lambda *a,**k:(_ for _ in ()).throw(AssertionError('network'))
from test_baseline_prompt import FIXTURE,reconstruct
from agents.prompts import baseline_prompt
fixture=json.loads(FIXTURE.read_text())
for case in fixture['cases']:
    shopper,obs=reconstruct(fixture['profiles'][case['agent_id']],case['before'])
    assert baseline_prompt(shopper,obs)==case['prompt']
"""
        result=subprocess.run([sys.executable,'-c',script],cwd=SIMULATION_DIR.parent,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()
