"""Paired, explicit one-decision probes using the real informed prompt builder."""
import json
from dataclasses import asdict, replace
from pathlib import Path
from agents.base import MissingProviderApiKeyError
from agents.customer import ShoppingItem
from agents.providers import build_provider
from agents.shopper import Shopper
from core.accounting import cents
from core.customers import load_customers
from core.grid import build_store
from core.integrity import fingerprint
from evaluation.behavior_records import score, evaluate_choice, read_behavior

CATEGORIES=('budget','acceptable_price','priority','shopping_style')


def scenarios():
    template=load_customers()[0]
    original=build_store();ordered=sorted(original.products.values(),key=lambda p:(p['price'],p['id']))
    for category in CATEGORIES:
        for number in range(5):
            cheap=ordered[15+number*9].copy();dear=ordered[180+number*8].copy()
            products=[cheap,dear]
            for side in ('low','high'):
                grid=build_store();shelf=grid.shelves[0]
                for p in products:p['x'],p['y']=shelf.x,shelf.y
                shelf.products=[p.copy() for p in (list(reversed(products)) if number%2 else products)]
                grid.shelves=[shelf];grid.products={p['id']:p.copy() for p in products};grid.blocked=set(shelf.cells())
                def item(p,priority='want',maximum=1000):
                    return ShoppingItem('controlled-choice',p['id'],p['name'],p['type'],p['department'],p['aisle'],1,priority,True,p['price'],p['price'],maximum,False,p.get('company',''))
                budget=dear['price']*3
                need=[item(cheap),item(dear)]
                style='mixed';prob=.3
                if category=='budget': budget=cheap['price'] if side=='low' else dear['price']*3
                if category=='acceptable_price': need=[item(dear,maximum=cheap['price'] if side=='low' else dear['price']*2)]
                if category=='priority': need=[item(cheap,'must_have' if side=='low' else 'nice_to_have'),item(dear,'nice_to_have' if side=='low' else 'must_have')]
                if category=='shopping_style':
                    need=[];style='planner' if side=='low' else 'impulsive'
                profile=replace(template,shopping_list=tuple(need),budget_per_trip_usd=budget,shopping_style=style,impulse_buy_probability=prob)
                shopper=grid.spawn([Shopper(profile)])[0]
                shopper.state.x,shopper.state.y=grid.stand_cells_for((shelf.x,shelf.y))[0]
                grid.refresh(shopper);shopper.prompt_variant='informed'
                obs=grid.observe(shopper)
                skip=next((a for a in obs.allowed_steps if a.startswith('move_')),None)
                allowed=('grab',skip)
                obs=replace(obs,allowed_steps=allowed)
                prompt=shopper.prompt(obs)+'\nControlled one-decision probe: choose a visible product with grab, or choose '+skip+' to skip purchasing. The same two products are offered in both paired cases. Do not invent another product.'
                if number%2:
                    # The two available options are displayed in alternate order;
                    # IDs and prices stay fixed, and the order is recorded.
                    prompt+='\nOption order: '+dear['id']+', '+cheap['id']
                else:prompt+='\nOption order: '+cheap['id']+', '+dear['id']
                yield {'category':category,'pair':number,'side':side,'prompt':prompt,'allowed':allowed,
                       'products':products,'profile':asdict(profile),'skip':skip}


def run_behavior(path,ledger,seed=42,provider_name="openai",requests_per_minute=0):
    path=Path(path)
    if path.exists():
        evidence=read_behavior(path)
        if evidence['start'].get('provider')!=provider_name or evidence['start'].get('seed')!=seed:
            raise ValueError('Behavior evidence has different or unverified provider/settings; use a new attempt')
        if evidence['end'] is None or evidence['warnings']:
            raise ValueError('Behavior evidence is incomplete; retain it and use a new explicitly named attempt')
        return evidence['summary']
    path.parent.mkdir(parents=True,exist_ok=True)
    records=[];provider=build_provider(provider_name,ledger,'behavior',seed,bucket='informed',stage_limit_usd=1,requests_per_minute=requests_per_minute)
    cases=list(scenarios())
    with path.open('x') as handle:
        handle.write(json.dumps({'type':'behavior_start','version':3,'seed':seed,'planned_attempts':40,
                                 'provider':provider_name,'model':provider.model,'cases':cases,
                                 'cases_sha256':fingerprint(cases),
                                 'generation':getattr(provider,'generation_settings',{}),
                                 'pricing':getattr(provider,'pricing',{})})+'\n');handle.flush()
        for index,case in enumerate(cases):
            provider.round_number=index//2+1
            decision=None;failure=None;telemetry={};raw=None;fatal=False
            try:
                result=provider.request(case['prompt'],case['allowed'],f"{case['category']}:{case['pair']}")
                decision=result.decision;telemetry=result.telemetry or {};raw=result.raw_response
            except Exception as e:
                failure=str(e);telemetry=getattr(e,'telemetry',{});fatal=isinstance(e,MissingProviderApiKeyError)
            record={'type':'behavior_choice','sequence':index+1,**case,'raw_response':raw,
                    'action':decision.to_dict() if decision else None,
                    'failure':failure,'telemetry':telemetry,**evaluate_choice(case,decision)}
            records.append(record);handle.write(json.dumps(record,ensure_ascii=False)+'\n');handle.flush()
            if fatal or (failure and failure.startswith(('Campaign budget exhausted','Gemini HTTP 400','Gemini HTTP 403','Gemini HTTP 404','Gemini HTTP 429','OpenAI HTTP 400','OpenAI HTTP 401','OpenAI HTTP 403','OpenAI HTTP 404','OpenAI HTTP 429'))):break
        summary=score(records)
        handle.write(json.dumps({'type':'behavior_end','summary':summary})+'\n')
    return summary
