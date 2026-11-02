"""Read-only display projections for browser export and offline verification."""
import copy
from core.accounting import basket, cents
from core.run_log import summarize


def display_state(state, catalogue):
    result = {k:copy.deepcopy(state[k]) for k in ('x','y','phase','cart','turns_used','turn_budget')}
    result.update({k:v for k,v in basket(state['cart'],catalogue).items() if k != 'quantities'})
    return result


def display_profile(shopper):
    c = shopper['customer']
    return {'id':shopper['agent_id'], 'name':f"{c.get('first_name','')} {c.get('last_name','')}".strip(),
            'style':c.get('shopping_style',''), 'budget_cents':cents(c['budget_per_trip_usd']),
            'persona':{k:c[k] for k in ('diet_type','price_sensitivity_1_5','brand_loyalty_1_5','impulse_buy_probability','trip_type') if k in c},
            'list':copy.deepcopy(c['shopping_list']),
            'sprite_index':shopper.get('presentation',{}).get('sprite_index',0)}


def totals(summary):
    return {k:copy.deepcopy(v) for k,v in summary.items() if k != 'shoppers'}


class RecordingView:
    """Consumes records only. It never calls a store or decision provider."""
    def __init__(self, start):
        self.start = copy.deepcopy(start)
        self.events = []
        self.states = {s['agent_id']:copy.deepcopy(s['state']) for s in start['shoppers']}
        self.summary = self._summary('incomplete')
        self.end = None

    def _summary(self, status):
        final = [{'agent_id':s['agent_id'],'state':self.states[s['agent_id']]} for s in self.start['shoppers']]
        return summarize(self.start,self.events,final,status)

    def append(self, record):
        if record['type'] == 'decision':
            if record['sequence'] != len(self.events)+1 or record['before'] != self.states[record['agent_id']]:
                raise ValueError('Replay event chain mismatch')
            self.events.append(copy.deepcopy(record))
            self.states[record['agent_id']] = copy.deepcopy(record['after'])
            self.summary = self._summary('incomplete')
        elif record['type'] == 'run_end':
            self.end = copy.deepcopy(record)
            self.summary = self._summary(record['status'])
            if self.summary != record['summary']:
                raise ValueError('Replay summary mismatch')

    def snapshot(self):
        return {'sequence':len(self.events), 'states':{aid:display_state(s,self.start['catalogue']) for aid,s in self.states.items()},
                'summary':copy.deepcopy(self.summary)}
