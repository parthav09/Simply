"""Read-only model/layout dashboard from retained canonical recordings. No model calls."""
import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from statistics import mean

SIMULATION_DIR=Path(__file__).resolve().parents[1]
if str(SIMULATION_DIR) not in sys.path:sys.path.insert(0,str(SIMULATION_DIR))

from core.evidence import run_row
from core.export_replay import export_run
from core.integrity import fingerprint
from core.metrics import percentile
from core.run_log import read_run
from evaluation import matrix,study
from evaluation.run import save_json

LAYOUTS=[{'id':'costco_back_anchor','label':'Layout A','description':'Back-anchor placement'},
         {'id':'neighborhood_express','label':'Layout B','description':'Express placement'}]
MODELS=[{'id':'gpt-6-luna','label':'GPT-6 Luna','status':'recorded'},
        {'id':'gpt-6.1-terra','label':'GPT-6.1 Terra','status':'recorded'},
        {'id':'qwen3-4b-instruct-2507','label':'Qwen3-4B-Instruct-2507','status':'not_evaluated'},
        {'id':'qwen3-4b-instruct-2507-finetuned','label':'Qwen 4B · fine-tuned','status':'not_evaluated'}]
MEASURES=[
    {'id':'checkout_completion','label':'Checkout completion','unit':'rate','primary':True},
    {'id':'purchased_unit_fulfillment','label':'Shopping list purchased','unit':'rate','primary':True},
    {'id':'moves_per_trip','label':'Movement steps / trip','unit':'number','primary':True},
    {'id':'requests_per_trip','label':'API requests / trip','unit':'number','primary':True},
    {'id':'estimated_cost_per_checkout_usd','label':'Estimated API cost / checkout','unit':'usd','primary':True},
    {'id':'estimated_cost_per_run_usd','label':'Estimated API cost / run','unit':'usd','primary':True},
    {'id':'simulated_sales_per_run_usd','label':'Simulated checkout sales / run','unit':'usd','primary':False},
    {'id':'actions_per_trip','label':'Action attempts / trip','unit':'number','primary':False},
    {'id':'adjusted_request_fraction','label':'Requests adjusted by assistance','unit':'rate','primary':False},
    {'id':'invalid_replies','label':'Invalid replies · total','unit':'integer','primary':False},
    {'id':'rejected_actions','label':'Rejected actions · total','unit':'integer','primary':False},
    {'id':'provider_failures','label':'Provider failures · total','unit':'integer','primary':False},
    {'id':'input_tokens_per_run','label':'Input tokens / run','unit':'number','primary':False},
    {'id':'output_tokens_per_run','label':'Output tokens / run','unit':'number','primary':False},
    {'id':'latency_p50_ms','label':'Request latency · median','unit':'milliseconds','primary':False},
    {'id':'latency_p95_ms','label':'Request latency · 95th percentile','unit':'milliseconds','primary':False},
]
DISTRIBUTIONS=[{'id':'moves','label':'Movement steps / trip','unit':'number'},
    {'id':'fulfillment','label':'Paid-list fulfillment','unit':'rate'},
    {'id':'requests','label':'Submitted API requests / trip','unit':'number'},
    {'id':'estimated_cost_usd','label':'Estimated API cost / attempted trip','unit':'usd'}]
GROUPS={'main':'Main controlled OpenAI study','pilot':'Separate OpenAI pilots',
        'historical':'Historical OpenAI demonstrations','openrouter':'OpenRouter · separate transport'}


def distribution(values):
    known=[v for v in values if v is not None]
    return {'known':len(known),'unknown':len(values)-len(known),
        'min':min(known) if known else None,'q1':percentile(known,.25),'median':percentile(known,.5),
        'q3':percentile(known,.75),'max':max(known) if known else None}


def record(path, main_protocols):
    """Use canonical Python outcomes, independently reconciling trip counts to totals."""
    run=read_run(path);header=run['start'];summary=run['summary'];row=run_row(path)
    experiment=header.get('experiment') or {};main_by_id={p['study_id']:p for p in main_protocols}
    if experiment.get('study_id') in main_by_id:
        protocol=main_by_id[experiment['study_id']]
        arm=next(a for a in protocol['arms'] if a['arm_id']==experiment['arm_id'])
        if study.controls(header)!=study.expected(protocol,arm,experiment['repetition']):
            raise ValueError('Dashboard source differs from frozen main-study controls')
        if experiment.get('protocol_sha256')!=protocol['sha256'] or header['provider']!='openai':
            raise ValueError('Invalid main-study source identity')
        group='main'
    elif header['provider']=='openrouter':group='openrouter'
    elif experiment.get('stage')=='main':group='pilot'
    else:group='historical'
    points=[]
    for shopper in summary['shoppers']:
        own=[e for e in run['events'] if e['agent_id']==shopper['agent_id']]
        submitted=[e.get('telemetry',{}).get('request_submitted') for e in own]
        costs=[e.get('telemetry',{}).get('estimated_cost_micros') for e in own]
        requested=shopper['requested_units'];paid=shopper['purchased_fulfilled_units']
        points.append({'profile_id':shopper['agent_id'],'finished':shopper['finished'],
            'requested':requested,'purchased':paid,
            'values':{'moves':shopper['successful_moves'],'fulfillment':paid/requested if requested else 1,
                'requests':sum(submitted) if all(type(n) is bool for n in submitted) else None,
                'estimated_cost_usd':sum(costs)/1e6 if all(type(n) is int for n in costs) else None}})
    requested=sum(p['requested'] for p in points);paid=sum(p['purchased'] for p in points)
    if abs((paid/requested if requested else 1)-row['metrics']['purchased_unit_fulfillment'])>1e-12:
        raise ValueError('Trip paid fulfillment does not reconcile to run metric')
    latencies=[e['telemetry'].get('api_latency_ms',e['telemetry']['provider_latency_ms']) for e in run['events']
        if e.get('telemetry',{}).get('request_submitted') is True]
    unknown_usage=summary['resources']['unknown_usage_requests']
    return {'run_id':row['run_id'],'source_sha256':row['source_sha256'],'provider':row['provider'],
        'model':row['model'],'layout_id':row['layout_id'],'recorded_at':row['recorded_at'],
        'status':row['status'],'warnings':row['warnings'],'group':group,
        'repetition':experiment.get('repetition'),'cohort_sha256':header['input_fingerprints']['shoppers'],
        'shopping_rules':row['shopping_rules'],'policy':row['navigation_policy'],
        'run_metrics':row['metrics'],'cost_complete':row['cost_complete'],
        'known_input_tokens':summary['resources']['usage']['promptTokenCount'],
        'known_output_tokens':summary['resources']['usage']['candidatesTokenCount']+summary['resources']['usage']['thoughtsTokenCount'],
        'usage_complete':unknown_usage==0,'latencies_ms':latencies,
        'points':points,'source_url':f"/replays/{row['run_id']}.source.jsonl",
        'replay_url':f"/replays/{row['run_id']}.json",
        'distributions':{m['id']:distribution([p['values'][m['id']] for p in points]) for m in DISTRIBUTIONS}}


def cell(rows, status='recorded'):
    points=[p for r in rows for p in r['points']];trips=len(points);finished=sum(p['finished'] for p in points)
    requested=sum(p['requested'] for p in points);purchased=sum(p['purchased'] for p in points)
    costs=[r['run_metrics']['known_estimated_cost_usd'] for r in rows]
    complete_cost=bool(rows) and all(r['cost_complete'] and c is not None for r,c in zip(rows,costs))
    total_cost=sum(costs) if complete_cost else None
    requests=[p['values']['requests'] for p in points]
    request_count=sum(requests) if points and all(n is not None for n in requests) else None
    latency=[n for r in rows for n in r['latencies_ms']]
    def total(key):
        values=[r['run_metrics'][key] for r in rows]
        return sum(values) if values and all(n is not None for n in values) else None
    metrics={m['id']:None for m in MEASURES}
    if rows:
        metrics.update(checkout_completion=finished/trips,purchased_unit_fulfillment=purchased/requested if requested else 1,
            moves_per_trip=sum(p['values']['moves'] for p in points)/trips,
            requests_per_trip=request_count/trips if request_count is not None else None,
            estimated_cost_per_checkout_usd=total_cost/finished if finished and total_cost is not None else None,
            estimated_cost_per_run_usd=total_cost/len(rows) if total_cost is not None else None,
            simulated_sales_per_run_usd=total('sales_cents')/100/len(rows) if total('sales_cents') is not None else None,
            actions_per_trip=total('turns_used')/trips if total('turns_used') is not None else None,
            adjusted_request_fraction=total('navigation_adjustments')/request_count if request_count else None,
            invalid_replies=total('invalid_decision_count'),rejected_actions=total('grid_rejection_count'),
            provider_failures=total('provider_failure_count'),
            input_tokens_per_run=mean(r['known_input_tokens'] for r in rows) if all(r['usage_complete'] for r in rows) else None,
            output_tokens_per_run=mean(r['known_output_tokens'] for r in rows) if all(r['usage_complete'] for r in rows) else None,
            latency_p50_ms=percentile(latency,.5),latency_p95_ms=percentile(latency,.95))
    return {'status':status if not rows else 'recorded','run_ids':[r['run_id'] for r in rows],
        'runs':len(rows),'trips':trips,'finished':finished,'requested':requested,'purchased':purchased,
        'stopped_runs':sum(r['status']!='completed' or bool(r['warnings']) for r in rows),'metrics':metrics}


def assemble(records, main_study_id):
    ids=[r['run_id'] for r in records]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate retained run ID')
    records=sorted(records,key=lambda r:(r['recorded_at'],r['run_id']))
    main=[r for r in records if r['group']=='main'];complete=[r for r in main if r['status']=='completed' and not r['warnings']]
    required={(m['id'],l['id']) for m in MODELS[:2] for l in LAYOUTS}
    intact=[n for n in sorted({r['repetition'] for r in complete})
            if {(r['model'],r['layout_id']) for r in complete if r['repetition']==n}==required]
    first=[r for r in complete if r['repetition']==intact[0]] if intact else []
    selections=[('matched_first','One run per model / layout',first,
        'The earliest intact main-study repetition, selected by repetition order, not by performance. One run and ten fixed profiles in each measured cell.'),
        ('completed_average','Average of completed main-study runs',complete,
        f'All {len(complete)} completed main-study runs. Cell sample sizes may differ; interrupted attempts are excluded here and remain visible in the all-attempt view.'),
        ('all_attempts','All main-study attempts · includes interruption',main,
        'All retained main-study attempts, including the provider-credit interruption. Low paid fulfillment in a stopped run is not evidence of poor model quality.')]
    views=[]
    for key,label,rows,note in selections:
        views.append({'id':key,'label':label,'note':note,'runs':len(rows),'trips':sum(len(r['points']) for r in rows),
            'models':[{**m,'cells':{l['id']:cell([r for r in rows if r['model']==m['id'] and r['layout_id']==l['id']],
                status='not_evaluated' if m['status']=='not_evaluated' else 'missing') for l in LAYOUTS}} for m in MODELS]})
    counts=Counter(r['group'] for r in records)
    return {'dashboard_version':1,'main_study_id':main_study_id,'default_view':'matched_first',
        'layouts':LAYOUTS,'measures':MEASURES,'distribution_measures':DISTRIBUTIONS,'views':views,'runs':records,
        'coverage':{'retained_runs':len(records),'retained_trips':sum(len(r['points']) for r in records),
            'completed_runs':sum(r['status']=='completed' and not r['warnings'] for r in records),
            'stopped_runs':sum(r['status']!='completed' or bool(r['warnings']) for r in records),
            'main_runs':len(main),'main_trips':sum(len(r['points']) for r in main),
            'groups':[{'id':g,'label':GROUPS[g],'runs':counts[g],'trips':sum(len(r['points']) for r in records if r['group']==g)} for g in GROUPS]},
        'limitations':[
            'These are simulated shopping trips, not independent people or predictions validated against human behavior.',
            'The default table uses four matched runs. One repetition provides descriptive results, not a confidence interval or statistical significance.',
            'The same ten profiles repeat in the main study. Distribution points are observed trips; they are not independent experimental repetitions.',
            'Only the main controlled OpenAI study enters the headline table. Pilots, historical demonstrations and OpenRouter attempts stay separate.',
            'Purchased-list fulfillment counts requested units in paid carts. Unfinished shoppers retain zero purchased units; unpaid baskets are not sales.',
            'Known cost estimates use each recording’s frozen token prices, including cache charges. A missing charge keeps the full cost estimate unknown.',
            'API cost per checkout pools all selected costs and divides by completed checkouts, retaining costs from unfinished trips. Other per-trip rates pool their numerators and denominators.',
            'Simulated checkout sales are not real revenue. Both models use recorded Python navigation assistance; this does not isolate unassisted model intelligence.',
            'Qwen3-4B-Instruct-2507 and fine-tuned Qwen have not been evaluated here. N/A means no results; it never means zero performance.']}


def load_main(public):
    index=json.loads((public/'index.json').read_text());entry=index['matrix']
    protocol=json.loads((public/Path(entry['protocol_url']).name).read_text())
    # The comparison deliberately references the historical direct-OpenAI matrix,
    # even if a future active catalogue matrix points to a different transport.
    if protocol.get('provider','openai')!='openai':
        candidates=[]
        for path in public.glob('matrix-*.protocol.json'):
            p=json.loads(path.read_text())
            if p.get('provider','openai')=='openai':candidates.append(p)
        if len(candidates)!=1:raise ValueError('Select one authoritative direct-OpenAI matrix')
        protocol=candidates[0]
    if fingerprint({k:v for k,v in protocol.items() if k!='sha256'})!=protocol['sha256']:
        raise ValueError('Main matrix protocol integrity mismatch')
    children=[]
    for child in protocol['children']:
        matches=[json.loads(p.read_text()) for p in public.glob('study-*.protocol.json')]
        matches=[p for p in matches if p.get('sha256')==child['sha256']]
        if len(matches)!=1 or fingerprint({k:v for k,v in matches[0].items() if k!='sha256'})!=child['sha256']:
            raise ValueError('Missing or invalid frozen main protocol')
        children.append(matches[0])
    return protocol,children


def publish(runs_root, public):
    public=Path(public);plan,protocols=load_main(public);records=[];paths={}
    for path in sorted(Path(runs_root).rglob('*.jsonl')):
        with path.open('rb') as handle:header=json.loads(handle.readline())
        if header.get('type')!='run_start' or header.get('provider') not in ('openai','openrouter','gemini') or header.get('config',{}).get('mode')!='actions':continue
        row=record(path,protocols);records.append(row);paths[row['run_id']]=path
    result=assemble(records,plan['study_id'])
    index_path=public/'index.json';index=json.loads(index_path.read_text())
    catalogue={r['run_id']:r for r in index['runs']}
    for row in records:
        existing=catalogue.get(row['run_id']);bundle=public/f"{row['run_id']}.json";source=public/f"{row['run_id']}.source.jsonl"
        if not (existing and existing['sha256']==row['source_sha256'] and bundle.exists() and source.exists()
            and hashlib.sha256(bundle.read_bytes()).hexdigest()==existing['bundle_sha256']
            and hashlib.sha256(source.read_bytes()).hexdigest()==row['source_sha256']):
            export_run(paths[row['run_id']],public,allow_partial=row['status']!='completed' or bool(row['warnings']))
    # export_run updates the shared catalogue. Preserve all existing studies/runs.
    index=json.loads(index_path.read_text());name='evidence-dashboard.json'
    save_json(public/name,result)
    index['dashboard']={'url':'/replays/'+name,'sha256':hashlib.sha256((public/name).read_bytes()).hexdigest()}
    save_json(index_path,index)
    return result


def verify(public):
    public=Path(public);index=json.loads((public/'index.json').read_text());entry=index['dashboard']
    if entry['url']!='/replays/evidence-dashboard.json':raise ValueError('Invalid dashboard link')
    text=(public/'evidence-dashboard.json').read_bytes()
    if hashlib.sha256(text).hexdigest()!=entry['sha256']:raise ValueError('Dashboard integrity mismatch')
    saved=json.loads(text);plan,protocols=load_main(public);rows=[]
    for row in saved['runs']:
        path=public/f"{row['run_id']}.source.jsonl"
        if hashlib.sha256(path.read_bytes()).hexdigest()!=row['source_sha256']:raise ValueError('Dashboard source integrity mismatch')
        rows.append(record(path,protocols))
    if assemble(rows,plan['study_id'])!=saved:raise ValueError('Dashboard differs from canonical source reconstruction')
    return {'verified_runs':len(rows),'verified_trips':saved['coverage']['retained_trips'],'api_calls':0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('publish','verify'))
    parser.add_argument('--runs-root',type=Path,default=SIMULATION_DIR/'runs')
    parser.add_argument('--public',type=Path,default=SIMULATION_DIR.parent/'landing/public/replays')
    args=parser.parse_args()
    result=publish(args.runs_root,args.public)['coverage'] if args.command=='publish' else verify(args.public)
    print(json.dumps(result))


if __name__=='__main__':main()
