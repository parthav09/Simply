"""Deterministic feasible cohort construction; the reference route never acts."""
from collections import defaultdict, deque
from dataclasses import asdict, replace
import json
from pathlib import Path
from agents.customer import Customer, ShoppingItem
from agents.shopper import Shopper
from core.accounting import cents
from core.config import DATA_DIR, ACTIVE_LAYOUT_IDS, MAX_SHOPPER_COUNT
from core.customers import load_customers
from core.grid import build_store
from core.integrity import fingerprint
from core.shopping import LEGACY_SHOPPING, SIMPLE_SHOPPING, unique_profile

PRIORITIES={'must_have':0,'want':1,'nice_to_have':2,'impulse_candidate':3}


def common_start_cells(grids):
    common=set((x,y) for y in range(grids[0].height) for x in range(grids[0].width))
    for grid in grids:
        common &= {(x,y) for y in range(grid.height) for x in range(grid.width)
                   if grid.walkable(x,y) and (x,y) not in set(grid.checkout)|{grid.exit}}
    return sorted(common,key=lambda c:(min(abs(c[0]-x)+abs(c[1]-y) for x,y in grids[0].entrance),-c[1],c[0]))


def reference_turns(grid, items, start):
    remaining=list(items); position=start; turns=0
    while remaining:
        options=[]
        for item in remaining:
            p=grid.products[item.product_id]
            path=grid.find_path(position,grid.stand_cells_for((p['x'],p['y'])))
            if path is not None: options.append((len(path),item.product_id,item,path))
        if not options: return None
        _,_,item,path=min(options,key=lambda v:(v[0],v[1]))
        turns+=len(path)+item.quantity
        if path: position=path[-1]
        remaining.remove(item)
    path=grid.find_path(position,grid.checkout)
    return turns+len(path)+2 if path is not None else None


def prepare(path, count=MAX_SHOPPER_COUNT):
    path=Path(path)
    if path.exists():
        data=load_benchmark(path)
        if len(data['customers'])!=count or data.get('layouts')!=list(ACTIVE_LAYOUT_IDS):
            raise ValueError('Frozen benchmark has different scope; choose a new benchmark path')
        return data
    if not 10<=count<=MAX_SHOPPER_COUNT: raise ValueError('Benchmark cohort must contain 10–15 profiles')
    grids=[build_store(name) for name in ACTIVE_LAYOUT_IDS]; catalogue=grids[0].products
    starts=common_start_cells(grids)
    customers=sorted(load_customers(),key=lambda c:(c.budget_per_trip_usd,c.customer_id))
    buckets=defaultdict(deque)
    for index,c in enumerate(customers): buckets[(c.shopping_style,min(2,index*3//len(customers)))].append(c)
    candidates=[]
    while any(buckets.values()):
        for key in sorted(buckets,key=lambda k:(k[1],k[0])):
            if buckets[key]: candidates.append(buckets[key].popleft())
    cohort=[]; references={}
    for c in candidates:
        items=[]; remaining=cents(c.budget_per_trip_usd)*80//100
        for _,item in sorted(enumerate(c.shopping_list),key=lambda x:(PRIORITIES.get(x[1].priority,99),x[0])):
            p=catalogue.get(item.product_id)
            if not p or cents(p['price'])>cents(item.max_acceptable_unit_price): continue
            price=cents(p['price']); quantity=min(item.quantity,remaining//max(price,1))
            if quantity<1:continue
            candidate=replace(item,quantity=quantity,expected_line_total=price*quantity/100)
            proposed=items+[candidate]
            bounds=[reference_turns(g,proposed,starts[len(cohort)]) for g in grids]
            if all(t is not None and t<=96 for t in bounds):
                items=proposed;remaining-=quantity*price
        if not items:continue
        frozen=replace(c,shopping_list=tuple(items));cohort.append(asdict(frozen))
        references[c.customer_id]={name:reference_turns(grid,items,starts[len(cohort)-1]) for name,grid in zip(ACTIVE_LAYOUT_IDS,grids)}
        if len(cohort)==count:break
    if len(cohort)!=count:raise ValueError(f'Only {len(cohort)} eligible profiles found')
    source={p.name:fingerprint(p.read_text()) for p in sorted(DATA_DIR.glob('*.csv'))}
    body={'benchmark_version':2,'layouts':list(ACTIVE_LAYOUT_IDS),'construction':'style/budget bands; original priority/order; <=80% budget; acceptable prices; greedy feasible route <=96 turns',
          'customers':cohort,'starting_cells':[list(c) for c in starts[:count]], 'reference_turns':references,
          'source_fingerprints':source,'catalogue_fingerprint':fingerprint([{k:v for k,v in p.items() if k not in ('x','y')} for _,p in sorted(catalogue.items())]),
          'limitations':['Derived feasible lists, not the original population lists','Reference paths establish feasibility only and never select model actions']}
    body['sha256']=fingerprint(body)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as handle:json.dump(body,handle,indent=2)
    return body


def load_benchmark(path):
    data=json.loads(Path(path).read_text());expected=data.pop('sha256')
    if fingerprint(data)!=expected:raise ValueError('Frozen benchmark hash mismatch')
    data['sha256']=expected
    return data


def instantiate_benchmark(data,count,grid,turn_budget=120,shopping_rules=LEGACY_SHOPPING):
    if count>len(data['customers']):raise ValueError('Cohort exceeds frozen benchmark')
    shoppers=[]
    for c in data['customers'][:count]:
        profile=Customer(**{**c,'shopping_list':tuple(ShoppingItem(**i) for i in c['shopping_list'])})
        if shopping_rules == SIMPLE_SHOPPING:
            profile = unique_profile(profile)
        shoppers.append(Shopper(profile,turn_budget=turn_budget))
        shoppers[-1].shopping_rules = shopping_rules
    grid.spawn(shoppers)
    for shopper,cell in zip(shoppers,data['starting_cells']):
        if not grid.walkable(*cell):raise ValueError('Frozen starting cell is not walkable')
        shopper.state.x,shopper.state.y=cell;grid.refresh(shopper)
    return shoppers
