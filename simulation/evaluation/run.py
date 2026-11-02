"""Freeze, run, report, and publish a bounded model evaluation campaign."""
import argparse
import itertools
import json
import random
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

SIMULATION_DIR=Path(__file__).resolve().parents[1]
if str(SIMULATION_DIR) not in sys.path:sys.path.insert(0,str(SIMULATION_DIR))

from core.config import ACTIVE_LAYOUT_IDS, DEFAULT_SHOPPER_COUNT, MAX_SHOPPER_COUNT
from core.budget import CampaignLedger, read_ledger_snapshot
from core.integrity import fingerprint
from core.export_replay import export_run
from core.metrics import percentile
from core.run_log import read_run
from evaluation.behavior_records import read_behavior

LAYOUTS=ACTIVE_LAYOUT_IDS
LEGACY_LAYOUTS=('costco_back_anchor','neighborhood_express','back_destination')

METRICS=('mean_list_completion','unit_fulfillment','purchased_unit_fulfillment','checkout_completion',
         'sales_cents','mean_successful_moves','overspending_fraction','loop_detections')


def save_json(path,data):
    path=Path(path);temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n');temp.replace(path)


def save_campaign(path,manifest,ledger):
    snapshot={'recorded_at':datetime.now(timezone.utc).isoformat(),'values':ledger.snapshot()}
    snapshot['sha256']=fingerprint(snapshot)
    manifest['budget_snapshot']=snapshot
    save_json(path,manifest)


def saved_budget(manifest):
    saved=manifest.get('budget_snapshot')
    if saved is not None:
        body={k:v for k,v in saved.items() if k!='sha256'}
        if fingerprint(body)!=saved.get('sha256'):raise ValueError('Saved budget snapshot integrity mismatch')
    return saved


def report_budget(manifest):
    """Unknown or moved accounting evidence must not become a fresh $0 ledger."""
    saved=saved_budget(manifest)
    try:live=read_ledger_snapshot(manifest['ledger'])
    except ValueError:live=None
    if live is not None and saved and (live['requests']<saved['values']['requests'] or live['known_estimated_usd']<saved['values']['known_estimated_usd']):
        live=None
    if live is not None:return live,{'source':'ledger','recorded_at':None}
    if saved is not None:
        return saved['values'],{'source':'saved_snapshot','recorded_at':saved['recorded_at']}
    return {k:None for k in ('limit_usd','known_estimated_usd','unresolved_reserved_usd','requests','remaining_usd')},{'source':'unavailable','recorded_at':None}


def compatible(left,right,allow_prompt_difference=False,paired=True):
    a,b=left['start'],right['start']
    for run in (left,right):
        if run['summary']['status']!='completed' or run['warnings'] or run['start']['config']['mode']!='actions':
            raise ValueError('Comparison needs completed, intact action runs')
    for field in ('provider','model','catalogue','engine_fingerprint','provider_fingerprint'):
        if a.get(field)!=b.get(field):raise ValueError(f'Comparison mismatch: {field}')
    if not allow_prompt_difference and a['prompt_version']!=b['prompt_version']:raise ValueError('Comparison mismatch: prompt version')
    ca,cb=dict(a['config']),dict(b['config'])
    if not paired:ca.pop('seed',None);cb.pop('seed',None)
    if ca!=cb:raise ValueError('Comparison mismatch: settings')
    if [s['customer'] for s in a['shoppers']]!=[s['customer'] for s in b['shoppers']]:raise ValueError('Comparison mismatch: shoppers/lists')
    positions=lambda h:[(s['state']['x'],s['state']['y']) for s in h['shoppers']]
    if positions(a)!=positions(b):raise ValueError('Comparison mismatch: starting cells')
    for run in (left,right):
        if run['start']['provider'] in ('openai','gemini'):
            responses=[e for e in run['events'] if e['outcome']!='provider_exception' and e.get('telemetry',{}).get('request_submitted',True)]
            if not responses or any(not isinstance(e.get('telemetry',{}).get('model_version'),str) or not e['telemetry']['model_version'].strip() for e in responses):
                raise ValueError('Comparison needs verified actual model versions for returned responses')
    versions=lambda r:{e.get('telemetry',{}).get('model_version') for e in r['events'] if e.get('telemetry',{}).get('model_version')}
    if len(versions(left)|versions(right))>1:raise ValueError('Comparison mismatch: actual model versions')


def metric_values(run):
    s=run['summary'];attempts=max(1,s['turns_used'])
    return {**{k:s.get(k) for k in METRICS},
            'invalid_decision_rate':s['failures']['invalid_decision']/attempts,
            'grid_rejection_rate':s['failures']['grid_rejected']/attempts,
            'provider_failure_rate':s['failures']['provider_exception']/attempts,
            'request_latency_p50_ms':s.get('performance',{}).get('request_latency_p50_ms'),
            'request_latency_p95_ms':s.get('performance',{}).get('request_latency_p95_ms'),
            'run_duration_ms':s.get('performance',{}).get('run_duration_ms'),
            'known_estimated_cost_usd':s.get('resources',{}).get('known_estimated_cost_usd'),
            'unknown_usage_requests':s.get('resources',{}).get('unknown_usage_requests')}


def bootstrap(values,seed=42):
    if len(values)<5:return None
    rng=random.Random(seed)
    means=sorted(mean(rng.choices(values,k=len(values))) for _ in range(10000))
    return [percentile(means,.025),percentile(means,.975)]


def make_report(directory):
    directory=Path(directory);manifest=json.loads((directory/'campaign.json').read_text())
    layouts=tuple(manifest.get('layouts',LEGACY_LAYOUTS))
    runs=[];loaded=[];missing=[]
    for attempt in manifest['attempts']:
        path=directory/attempt['file']
        if not path.exists():
            missing.append(attempt['file']);continue
        run=read_run(path)
        if run['start']['provider']!=manifest['provider'] or run['start']['layout']['id']!=attempt['layout']:
            raise ValueError('Experiment manifest does not match recorded provider/layout identity')
        loaded.append((attempt,run))
        runs.append({'run_id':run['start']['run_id'],'file':attempt['file'],
                     'layout_id':run['start']['layout']['id'],'stage':attempt['stage'],
                     'prompt':run['start'].get('prompt_variant'),'repetition':attempt['repetition'],
                     'status':run['summary']['status'],'summary':run['summary'],
                     'source_fingerprints':run['start'].get('input_fingerprints'),
                     'source_sha256':__import__('hashlib').sha256(path.read_bytes()).hexdigest()})
    chosen=[(a,r) for a,r in loaded if a['stage']=='main' and r['summary']['status']=='completed' and not r['warnings']]
    completed_slots=set()
    for attempt,run in chosen:
        layout=run['start']['layout']['id'];slot=(layout,attempt['repetition'])
        if layout not in layouts or attempt['layout']!=layout or slot in completed_slots:
            raise ValueError('Duplicate or incompatible completed experiment slot')
        if len(run['start']['shoppers'])!=manifest.get('cohort_size'):
            raise ValueError('Completed run does not match the frozen cohort size')
        completed_slots.add(slot)
    # Validate controls across repetitions too, while allowing their seed schedule.
    if chosen:
        for _,run in chosen[1:]:compatible(chosen[0][1],run,paired=False)
    arms=[]
    for layout in layouts:
        own=[r for _,r in chosen if r['start']['layout']['id']==layout]
        rows=[metric_values(r) for r in own]
        values={k:(mean(row[k] for row in rows) if rows and all(row[k] is not None for row in rows) else None) for k in metric_values(chosen[0][1])} if chosen else {}
        arms.append({'layout_id':layout,'completed_runs':len(own),'metrics':values})
    paired=[]
    for left,right in itertools.combinations(layouts,2):
        blocks=[]
        for repetition in range(1,manifest.get('main_repetitions',5)+1):
            la=[r for a,r in chosen if a['repetition']==repetition and r['start']['layout']['id']==left]
            rb=[r for a,r in chosen if a['repetition']==repetition and r['start']['layout']['id']==right]
            if len(la)==1 and len(rb)==1:
                compatible(la[0],rb[0]);blocks.append((la[0],rb[0]))
        metrics=metric_values(blocks[0][0]) if blocks else {}
        for metric in metrics:
            values=[]
            for a,b in blocks:
                first,second=metric_values(a)[metric],metric_values(b)[metric]
                if first is not None and second is not None:values.append(second-first)
            paired.append({'comparison':f'{right} minus {left}','metric':metric,
                           'mean_difference':mean(values) if values else None,'ci95':bootstrap(values),
                           'blocks':len(values),'missing_blocks':len(blocks)-len(values),
                           'status':'assessed' if values else 'unassessed'})
    repetitions=manifest.get('main_repetitions',5)
    expected_slots={(layout,n) for layout in layouts for n in range(1,repetitions+1)}
    behavior={};behavior_evidence=None
    behavior_path=directory/'behavior.jsonl'
    if behavior_path.exists():
        evidence=read_behavior(behavior_path)
        if evidence['start']['provider']!=manifest['provider'] or ('seed' in manifest and evidence['start']['seed']!=manifest['seed']):
            raise ValueError('Behavior evidence differs from experiment provider/settings')
        behavior=evidence['summary']
        if manifest.get('behavior') is not None and manifest['behavior']!=behavior:
            raise ValueError('Experiment behavior summary differs from saved decision evidence')
        behavior_evidence={'file':'behavior.jsonl','sha256':evidence['sha256'],'warnings':evidence['warnings'],
                           'provider':evidence['start']['provider'],'status':behavior['status']}
    elif manifest.get('behavior') is not None:
        missing.append('behavior.jsonl')
    behavior_complete=manifest['provider'] in ('fake','scripted_test') or (behavior.get('attempts')==40 and behavior.get('status','completed')=='completed')
    budget,budget_evidence=report_budget(manifest)
    if budget_evidence['source']=='unavailable':missing.append('campaign budget ledger or saved snapshot')
    complete=manifest.get('cohort_size') is not None and completed_slots==expected_slots and behavior_complete and not missing
    baseline=[]
    for layout in layouts:
        old=[r for a,r in loaded if a['stage']=='baseline' and r['start']['layout']['id']==layout and r['summary']['status']=='completed']
        new=[r for a,r in loaded if a['stage']=='informed' and r['start']['layout']['id']==layout and r['summary']['status']=='completed']
        if len(old)==1 and len(new)==1:
            compatible(old[0],new[0],allow_prompt_difference=True)
            baseline.append({'layout_id':layout,'baseline':metric_values(old[0]),'informed':metric_values(new[0]),
                             'interpretation':'Single pilot pair; not a repeated prompt-quality estimate'})
    report={'report_version':1,'study_id':manifest['study_id'],'status':'completed' if complete else 'pilot_or_incomplete',
            'cohort_size':manifest.get('cohort_size',manifest.get('requested_shopper_count',3)),'repetitions':manifest.get('main_repetitions',5),
            'provider':manifest['provider'],'benchmark_sha256':manifest['benchmark_sha256'],
            'arms':arms,'paired':paired,'baseline_vs_informed':baseline,'runs':runs,
            'behavior':behavior or None,'behavior_evidence':behavior_evidence,
            'campaign_budget':budget,'campaign_budget_evidence':budget_evidence,
            'prior_campaigns':manifest.get('prior_campaigns',[]),
            'protocol':manifest.get('main_protocol'),'missing_evidence':missing,
            'limitations':['Simulated outcomes; no validated real-customer or business-impact prediction.',
                'Confidence intervals resample repetition blocks, conditional on this fixed derived cohort; model actions are not independent samples.',
                *(['Layout C is demand-informed. These results are not out-of-population validation.'] if 'back_destination' in layouts else []),
                'Replenished inventory, independent movement, no crowd blocking and no checkout queues.',
                'Unknown token usage is not zero. Conservative cost reservations remain in the campaign ledger.',
                'Aborted/incomplete attempts are retained and excluded from completed paired blocks.',
                'Brand/diet metadata are synthetic or incomplete; unsupported preferences remain unassessed.']}
    save_json(directory/'report.json',report)
    lines=['# Simply evaluation report',f"\nStudy: {report['study_id']} • {report['status']} • provider: {report['provider']}",
           f"\nBenchmark: `{report['benchmark_sha256']}`",f"\nCampaign cost: {json.dumps(report['campaign_budget'])}",
           '\n## Main layout results','\n| Layout | Completed repetitions | Mean fulfillment | Checkout |','|---|---:|---:|---:|']
    for arm in arms:
        fmt=lambda v:'N/A' if v is None else f'{v:.1%}'
        lines.append(f"| {arm['layout_id']} | {arm['completed_runs']} | {fmt(arm['metrics'].get('mean_list_completion'))} | {fmt(arm['metrics'].get('checkout_completion'))} |")
    lines+=['\n## Pilot comparison', f"Baseline and informed prompts use the same {manifest.get('pilot_shopper_count',3)} frozen benchmark shoppers and controlled settings."]
    for row in baseline:
        lines.append(f"- {row['layout_id']}: baseline fulfillment {row['baseline']['mean_list_completion']:.1%}, informed {row['informed']['mean_list_completion']:.1%}; baseline checkout {row['baseline']['checkout_completion']:.1%}, informed {row['informed']['checkout_completion']:.1%}.")
    lines+=['\n## Behavioral probes',json.dumps(report['behavior'],indent=2),'\n## Every attempt']
    for row in runs:lines.append(f"- `{row['run_id']}`: {row['stage']} / {row['layout_id']} / repeat {row['repetition']} / {row['status']} — `{row['file']}`")
    lines+=['\n## Interpretation and limitations',*[f'- {v}' for v in report['limitations']]]
    (directory/'report.md').write_text('\n'.join(lines)+'\n')
    return report


def publish(directory,destination):
    directory=Path(directory);destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    report=make_report(directory)
    # Replays are selected explicitly by this command; all retained attempts stay
    # in the downloadable experiment report, including failed runs.
    for row in report['runs']:
        if row['stage'] in ('informed','main') and row['status']=='completed':
            export_run(directory/row['file'],destination,allow_test=report['provider'] not in ('gemini','openai'))
    if report['behavior_evidence']:
        evidence=report['behavior_evidence'];raw=(directory/evidence['file']).read_bytes()
        if __import__('hashlib').sha256(raw).hexdigest()!=evidence['sha256']:
            raise ValueError('Behavior evidence changed during publication')
        evidence_name=f"study-{report['study_id']}.behavior.jsonl"
        target=destination/evidence_name
        if target.exists():
            if target.read_bytes()!=raw:raise FileExistsError('Different behavior evidence already published for this study')
        else:
            with target.open('xb') as handle:handle.write(raw)
        evidence['url']=f'/replays/{evidence_name}'
    filename=f"study-{report['study_id']}.json";save_json(destination/filename,report)
    index=destination/'index.json'
    catalog=json.loads(index.read_text()) if index.exists() else {'schema_version':1,'runs':[],'reports':[]}
    entry={'url':f'/replays/{filename}','title':f"{report['provider']} · {report['cohort_size']} shoppers · {report['status']} · {report['study_id'][:8]}",
           'sha256':__import__('hashlib').sha256((destination/filename).read_bytes()).hexdigest()}
    catalog['reports']=[r for r in catalog.get('reports',[]) if r['url']!=entry['url']]+[entry]
    save_json(index,catalog)
    return report


def run_campaign(directory,benchmark_path,provider='openai',seed=42,ledger_path=None,requests_per_minute=None,replaces=None,shopper_count=DEFAULT_SHOPPER_COUNT):
    from agents.providers import FakeDecisionProvider
    from core.grid import build_store
    from core.session import SimulationSession
    from evaluation.benchmark import prepare,instantiate_benchmark
    from evaluation.behavior import run_behavior
    if not DEFAULT_SHOPPER_COUNT<=shopper_count<=MAX_SHOPPER_COUNT:
        raise ValueError('Evaluation requires 10–15 shoppers')
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    benchmark=prepare(benchmark_path)
    manifest_path=directory/'campaign.json'
    if manifest_path.exists():
        manifest=json.loads(manifest_path.read_text())
        if (manifest['benchmark_sha256']!=benchmark['sha256'] or manifest['provider']!=provider
            or manifest.get('layouts')!=list(LAYOUTS) or manifest.get('requested_shopper_count')!=shopper_count):
            raise ValueError('Campaign inputs differ from frozen manifest')
        if any(a['status']=='running' for a in manifest['attempts']):
            raise ValueError('An attempt is marked running. Inspect its process/log before explicitly replacing it; no automatic rerun.')
        recorded_ledger=Path(manifest['ledger']).resolve()
        if ledger_path is not None and Path(ledger_path).resolve()!=recorded_ledger:
            raise ValueError('Campaign ledger differs from the frozen manifest; resuming must preserve its spending history')
        if not recorded_ledger.is_file():
            raise ValueError('Campaign ledger is missing; a report can use saved evidence, but execution cannot reset its spending history')
        previous=saved_budget(manifest)
        current=read_ledger_snapshot(recorded_ledger)
        if previous and (current['requests']<previous['values']['requests'] or current['known_estimated_usd']<previous['values']['known_estimated_usd']):
            raise ValueError('Campaign spending history was reset or reduced; preserve the original ledger before resuming')
        ledger=CampaignLedger(recorded_ledger)
    else:
        ledger=CampaignLedger(ledger_path or SIMULATION_DIR/'runs/gemini_campaign.sqlite3')
        manifest={'study_id':uuid.uuid4().hex,'benchmark_sha256':benchmark['sha256'],'provider':provider,
                  'seed':seed,'ledger':str(ledger.path.resolve()),'attempts':[],'main_repetitions':5,
                  'layouts':list(LAYOUTS),'requested_shopper_count':shopper_count,'pilot_shopper_count':shopper_count}
        save_campaign(manifest_path,manifest,ledger)
    if replaces and 'prior_campaigns' not in manifest:
        previous=make_report(replaces)
        manifest['prior_campaigns']=[{'directory':str(Path(replaces).resolve()),'study_id':previous['study_id'],'reason':'Explicit provider/pacing revision; old evidence retained separately'}]
        save_campaign(manifest_path,manifest,ledger)
    seed=manifest['seed']
    rate=(8 if provider=='gemini' else 0) if requests_per_minute is None else requests_per_minute
    def trip(stage,layout,repetition,count,prompt):
        existing=[a for a in manifest['attempts'] if a['stage']==stage and a['layout']==layout and a['repetition']==repetition]
        if existing:
            latest=existing[-1]
            if latest['status']=='completed':return read_run(directory/latest['file'])
            raise ValueError('Previous failed attempt retained. Inspect evidence and use an explicitly named replacement campaign.')
        grid=build_store(layout);shoppers=instantiate_benchmark(benchmark,count,grid)
        filename=f'{stage}-{layout}-{repetition}-{uuid.uuid4().hex[:8]}.jsonl'
        attempt={'stage':stage,'layout':layout,'repetition':repetition,'file':filename,'status':'running'}
        manifest['attempts'].append(attempt);save_campaign(manifest_path,manifest,ledger)
        session=SimulationSession(layout,count,120,120,2,decide=FakeDecisionProvider() if provider=='fake' else None,
                    output_path=directory/filename,prompt_variant=prompt,seed=seed+repetition,
                    grid=grid,shoppers=shoppers,ledger_path=ledger.path,
                    experiment={'study_id':manifest['study_id'],'stage':stage,'stage_limit_usd':7 if stage=='main' else 1,
                                'repetition':repetition,'benchmark_sha256':benchmark['sha256']},
                    provider_name=provider,requests_per_minute=rate,enforce_api_budget=True,
                    shopping_rules='quantity_two_phase_v1')
        print(f'{stage}: {layout}, repeat {repetition}, {count} shoppers — {session.run_id}',flush=True)
        try:session.run()
        finally:
            attempt['status']=session.status;save_campaign(manifest_path,manifest,ledger)
        run=read_run(session.path)
        print(f"  {run['summary']['status']} | fulfillment {run['summary']['mean_list_completion']:.1%} | checkout {run['summary']['finished_count']}/{count}",flush=True)
        if run['summary']['status']!='completed':raise RuntimeError('Campaign stopped: incomplete run retained; inspect provider/budget evidence')
        return run
    try:
        for stage,prompt in [('baseline','baseline'),('informed','informed')]:
            for layout in LAYOUTS:trip(stage,layout,1,shopper_count,prompt)
        if provider!='fake' and 'behavior' not in manifest:
            manifest['behavior']=run_behavior(directory/'behavior.jsonl',ledger,seed,provider,rate)
            save_campaign(manifest_path,manifest,ledger)
        if provider!='fake' and (manifest['behavior'].get('attempts')!=40 or manifest['behavior'].get('status','completed')!='completed'):
            raise RuntimeError('Behavior checks stopped early. Preserve the incomplete evidence; the main evaluation has not been authorized by a complete pilot.')
        informed=[read_run(directory/a['file']) for a in manifest['attempts'] if a['stage']=='informed']
        if provider!='fake' and not any(r['summary']['finished_count']>0 for r in informed):
            raise RuntimeError('Informed pilot did not demonstrate model-selected checkout. Retain pilot evidence; version and validate a fix before the main experiment.')
        if 'cohort_size' not in manifest:
            costs=[e.get('telemetry',{}).get('estimated_cost_micros') for r in informed for e in r['events']]
            costs=[v/1e6 for v in costs if v is not None]
            if provider!='fake' and not costs:raise RuntimeError('No reported usage: cannot forecast the main experiment safely')
            bound=percentile(costs,.95) if costs else 0
            remaining=min(7,ledger.snapshot()['remaining_usd']-1)
            cohort=shopper_count
            if len(LAYOUTS)*5*cohort*120*bound>remaining:
                raise RuntimeError('Remaining budget cannot cover the requested 10–15 shopper evaluation; preserve the pilot instead of silently shrinking the cohort')
            manifest['cohort_size']=cohort
            manifest['main_protocol']={'cohort_size':cohort,'repetitions':5,'turn_budget':120,'max_rounds':120,'concurrency':2,
                                       'forecast_request_cost_usd':bound,'forecast_upper_turn_cost_usd':len(LAYOUTS)*5*cohort*120*bound,
                                       'layouts':list(LAYOUTS),'starting_cells':benchmark['starting_cells'][:cohort],'seed':seed,'requests_per_minute':rate,
                                       'bootstrap':'10000 deterministic repetition-block resamples; 95% percentile interval'}
            save_campaign(manifest_path,manifest,ledger)
        for repetition in range(1,6):
            order=list(LAYOUTS);random.Random(seed+repetition).shuffle(order)
            for layout in order:trip('main',layout,repetition,manifest['cohort_size'],'informed')
    finally:
        save_campaign(manifest_path,manifest,ledger)
        make_report(directory)
    return make_report(directory)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('prepare','campaign','report','publish'))
    parser.add_argument('--directory',type=Path,default=SIMULATION_DIR/'runs/evaluation-luna-two-layouts-v2')
    parser.add_argument('--benchmark',type=Path,default=SIMULATION_DIR/'benchmarks/two_layouts_15_v2.json')
    parser.add_argument('--provider',choices=('openai','gemini','fake'),default='openai')
    parser.add_argument('--shoppers',type=int,choices=range(DEFAULT_SHOPPER_COUNT,MAX_SHOPPER_COUNT+1),default=DEFAULT_SHOPPER_COUNT)
    parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--ledger',type=Path)
    parser.add_argument('--requests-per-minute',type=int)
    parser.add_argument('--replaces',type=Path,help='Explicitly link a retained earlier campaign after a provider/configuration fix')
    parser.add_argument('--destination',type=Path,default=SIMULATION_DIR.parent/'landing/public/replays')
    args=parser.parse_args(argv)
    try:
        if args.command=='prepare':
            from evaluation.benchmark import prepare
            print(prepare(args.benchmark)['sha256'])
        elif args.command=='campaign':print(json.dumps(run_campaign(args.directory,args.benchmark,args.provider,args.seed,args.ledger,args.requests_per_minute,args.replaces,args.shoppers)['campaign_budget']))
        elif args.command=='report':print(make_report(args.directory)['status'])
        else:print(publish(args.directory,args.destination)['status'])
    except (ValueError,RuntimeError,OSError) as e:parser.exit(2,f'Evaluation stopped: {e}\n')

if __name__=='__main__':main()
