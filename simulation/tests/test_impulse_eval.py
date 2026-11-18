import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation import impulse_eval as ie

DATASET = Path(__file__).resolve().parents[2] / 'data/finetuning/impulse_v3'


def facts(**overrides):
    base = {
        'allowed_steps': ['move_left', 'move_right', 'grab'], 'remaining_items': [
            {'product_id': 'P1', 'remaining': 1, 'max_unit_price_cents': 300, 'department': 'Produce'}],
        'shopping_list': [{'product_id': 'P1', 'quantity': 1}], 'cart': [], 'checkout_urgency': 'low',
        'remaining_budget_cents': 2000, 'budget_cents': 2000, 'turns_remaining': 100, 'action_limit': 120,
        'grabbable_products': [{'product_id': 'S1', 'name': 'Chips', 'unit_price_cents': 299,
            'dietary_tags': 'vegan;vegetarian', 'allergens': 'none', 'matches_remaining_list': False}],
        'nearby_shelves': [{'distance': 1, 'department': 'Snacks', 'products': [{'product_id': 'S1'}]}]}
    base.update(overrides)
    return base


PROFILE = {'style': 'impulsive', 'impulse_probability': 0.53, 'tier': 'impulsive', 'diet': 'omnivore', 'allergy': 'none', 'drinks_alcohol': True, 'health': 2,
           'price_sensitivity': 2, 'shopper_id': 'X'}


class ImpulseRuleTests(unittest.TestCase):
    def test_eligible_and_style_ordering(self):
        self.assertEqual(ie.impulse_context(facts(), PROFILE)[0], 'eligible')
        self.assertEqual(ie.impulse_context(facts(), {**PROFILE, 'tier': 'planner'})[0], 'no_fitting_candidate')
        self.assertEqual(ie.impulse_context(facts(), {**PROFILE, 'tier': None})[0], 'low_probability')

    def test_prompt_rules_block_impulse(self):
        self.assertEqual(ie.impulse_context(facts(checkout_urgency='high'), PROFILE)[0], 'urgent')
        self.assertEqual(ie.impulse_context(facts(turns_remaining=14), PROFILE)[0], 'urgent')
        self.assertEqual(ie.impulse_context(facts(turns_remaining=30), PROFILE)[0], 'urgent')   # <=30% of 120

    def test_v3_allows_impulse_after_list_complete_and_with_list_item_in_reach(self):
        self.assertEqual(ie.impulse_context(facts(remaining_items=[]), PROFILE)[0], 'eligible')
        both = facts()
        both['grabbable_products'].append({'product_id': 'P1', 'name': 'Apple', 'unit_price_cents': 100,
            'dietary_tags': 'vegan', 'allergens': 'none', 'matches_remaining_list': True})
        self.assertEqual(ie.impulse_context(both, PROFILE)[0], 'list_first')

    def test_tiers_follow_probability(self):
        self.assertEqual([ie.tier_for(p) for p in (0.76, 0.40, 0.39, 0.20, 0.10, 0.09)],
                         ['impulsive', 'impulsive', 'mixed', 'mixed', 'planner', None])

    def test_profile_fit(self):
        nuts = facts()
        nuts['grabbable_products'][0]['allergens'] = 'tree nuts/peanuts'
        self.assertEqual(ie.impulse_context(nuts, {**PROFILE, 'allergy': 'tree nuts/peanuts'})[0], 'no_fitting_candidate')
        beer = facts()
        beer['grabbable_products'][0]['dietary_tags'] = 'alcohol_21plus'
        self.assertEqual(ie.impulse_context(beer, {**PROFILE, 'drinks_alcohol': False})[0], 'no_fitting_candidate')

    def test_cap_counts_extras_in_cart(self):
        full = facts(cart=[{'product_id': 'A', 'quantity': 1}, {'product_id': 'B', 'quantity': 1}])
        self.assertEqual(ie.impulse_context(full, PROFILE)[0], 'cap_reached')


@unittest.skipUnless((DATASET / 'validation.jsonl').exists(), 'impulse_v3 dataset not generated')
class DatasetScoringTests(unittest.TestCase):
    def test_teacher_scores_perfectly_and_labels_follow_rules(self):
        rows = [json.loads(line) for line in (DATASET / 'validation.jsonl').read_text().splitlines()]
        metrics, _ = ie.score_offline(rows, [r['messages'][1]['content'] for r in rows])
        self.assertEqual(metrics['exact_action_agreement'], 1.0)
        self.assertEqual(metrics['impulse']['f1'], 1.0)
        self.assertEqual(metrics['rule_violation_rate'], 0.0)
        self.assertGreater(metrics['impulse']['moments'], 0)

    def test_violations_are_flagged(self):
        rows = [json.loads(line) for line in (DATASET / 'validation.jsonl').read_text().splitlines()]
        row = next(r for r in rows if ie.impulse_context(*(lambda p: (ie.observation(p), ie.parse_profile(p)))(r['messages'][0]['content']))[0] in ('urgent', 'cap_reached', 'low_probability')
                   and any(not p['matches_remaining_list'] for p in ie.observation(r['messages'][0]['content'])['grabbable_products']))
        state = ie.impulse_context(ie.observation(row['messages'][0]['content']), ie.parse_profile(row['messages'][0]['content']))[0]
        off = next(p for p in ie.observation(row['messages'][0]['content'])['grabbable_products'] if not p['matches_remaining_list'])
        metrics, _ = ie.score_offline([row], [json.dumps({'step': 'grab', 'product_id': off['product_id'], 'reason': 'x'})])
        self.assertEqual(metrics['rule_violations'], {state: 1})


if __name__ == '__main__':
    unittest.main()
