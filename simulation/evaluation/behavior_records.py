"""Pure preference-evidence reader and scores; no current data or provider access."""
import json
from pathlib import Path
from agents.schema import parse_decision, is_valid_decision
from core.accounting import cents
from core.integrity import fingerprint

CATEGORIES=('budget','acceptable_price','priority','shopping_style')
CASE_FIELDS=('category','pair','side','prompt','allowed','products','profile','skip')


def evaluate_choice(case,decision):
    valid_decision=is_valid_decision(decision,case['allowed'])
    chosen=decision.product_id if valid_decision and decision.step=='grab' else None
    product=next((p for p in case['products'] if p['id']==chosen),None)
    valid=bool(valid_decision and (decision.step==case['skip'] or product is not None))
    price=cents(product['price']) if product else 0
    adherent=None
    if valid:
        if case['category']=='budget':adherent=price<=cents(case['profile']['budget_per_trip_usd'])
        elif case['category']=='acceptable_price':
            limits={i['product_id']:cents(i['max_acceptable_unit_price']) for i in case['profile']['shopping_list']}
            adherent=chosen not in limits or price<=limits[chosen]
        elif case['category']=='priority':
            expected=next(i['product_id'] for i in case['profile']['shopping_list'] if i['priority']=='must_have')
            adherent=chosen==expected
        elif case['side']=='low':adherent=price==0
    return {'valid':valid,'chosen_id':chosen,'choice_cents':price,'adherent':adherent}


def _require(condition,message):
    if not condition:raise ValueError(message)


def read_behavior(path):
    """Recompute scores from frozen cases and original model replies."""
    path=Path(path)
    raw=path.read_bytes();rows=[];warnings=[];chunks=raw.split(b'\n')
    for index,line in enumerate(chunks):
        if not line.strip():continue
        try:rows.append(json.loads(line.decode('utf-8')))
        except (ValueError,UnicodeError) as error:
            if index==len(chunks)-1 and not raw.endswith(b'\n'):
                warnings.append('Incomplete final behavior record');break
            raise ValueError('Malformed behavior evidence') from error
    _require(bool(rows) and rows[0].get('type')=='behavior_start','Missing behavior header')
    start=rows[0]
    _require(start.get('version')==3,'Behavior evidence needs a version-three frozen protocol; preserve legacy evidence separately')
    cases=start.get('cases',[])
    _require(len(cases)==40 and fingerprint(cases)==start.get('cases_sha256'),'Frozen behavior cases mismatch')
    expected={(category,pair,side) for category in CATEGORIES for pair in range(5) for side in ('low','high')}
    _require({(c['category'],c['pair'],c['side']) for c in cases}==expected,'Missing or duplicate behavior cases')
    _require(start.get('planned_attempts')==40 and isinstance(start.get('provider'),str),'Invalid behavior protocol')
    records=[];end=None
    for row in rows[1:]:
        _require(end is None,'Records after behavior end')
        if row.get('type')=='behavior_end':
            end=row;continue
        index=len(records)
        _require(row.get('type')=='behavior_choice' and index<40 and row.get('sequence')==index+1,'Missing, duplicate or unordered behavior decision')
        case=cases[index]
        _require(fingerprint({k:row.get(k) for k in CASE_FIELDS})==fingerprint(case),'Behavior decision differs from frozen case')
        # Refusals/incomplete responses never become accepted actions simply
        # because a partial text happens to parse as JSON.
        accepted=not row.get('failure') and row.get('telemetry',{}).get('response_status','completed')=='completed'
        decision=parse_decision(row.get('raw_response'),case['allowed']) if accepted else None
        _require(row.get('action')==(decision.to_dict() if decision else None),'Behavior proposal/action mismatch')
        derived=evaluate_choice(case,decision)
        _require(all(row.get(k)==v for k,v in derived.items()),'Behavior action score mismatch')
        records.append(row)
    summary=score(records)
    if end is not None:_require(end.get('summary')==summary,'Behavior summary mismatch')
    if end is None or warnings:summary={**summary,'status':'incomplete'}
    return {'start':start,'records':records,'end':end,'summary':summary,
            'warnings':warnings,'sha256':__import__('hashlib').sha256(raw).hexdigest()}


def score(records):
    valid=[r for r in records if r['valid']]
    pairs={}
    for r in records:pairs.setdefault((r['category'],r['pair']),{})[r['side']]=r
    directional=0;assessable=0;ties=0
    categories={c:{'attempts':0,'valid':0,'adherent':0,'directional_pairs':0,'assessable_pairs':0,'ties':0} for c in CATEGORIES}
    for r in records:
        row=categories[r['category']];row['attempts']+=1;row['valid']+=r['valid'];row['adherent']+=r['adherent'] is True
    for (category,_),pair in pairs.items():
        if set(pair)!=set(('low','high')) or not all(r['valid'] for r in pair.values()):continue
        low,high=pair['low'],pair['high'];assessable+=1;categories[category]['assessable_pairs']+=1
        if category in ('budget','acceptable_price'):
            a,b=low['choice_cents'],high['choice_cents'];direction=a<b;tie=a==b
        elif category=='priority':
            direction=low['chosen_id']==low['products'][0]['id'] and high['chosen_id']==high['products'][1]['id'];tie=low['chosen_id']==high['chosen_id']
        else:
            direction=low['choice_cents']==0 and high['choice_cents']>0;tie=low['choice_cents']==high['choice_cents']
        directional+=direction;ties+=tie;categories[category]['directional_pairs']+=direction;categories[category]['ties']+=tie
    return {'status':'completed' if len(records)==40 else 'incomplete','planned_attempts':40,
            'pairs':len(pairs),'attempts':len(records),'valid_decisions':len(valid),'directional_pairs':directional,
            'assessable_pairs':assessable,'ties':ties,'categories':categories,
            'interpretation':'Constructed choice probes measure supplied-preference consistency, not human realism. Equal choices are ties, not positive directional effects.'}
