"""Explicit export of validated Python evidence to a read-only website catalogue."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

SIMULATION_DIR = Path(__file__).resolve().parents[1]
if str(SIMULATION_DIR) not in sys.path:
    sys.path.insert(0,str(SIMULATION_DIR))

from core.recording import RecordingView, display_profile, display_state, totals
from core.run_log import read_run


def encode_payload(payload):
    text = json.dumps(payload,ensure_ascii=False,separators=(',',':'),allow_nan=False)
    return {'bundle_version':1,'payload_sha256':hashlib.sha256(text.encode()).hexdigest(),'payload_json':text}


def build_bundle(path, allow_partial=False, allow_test=False):
    path = Path(path)
    run = read_run(path)
    start = run['start']
    if start['config']['mode'] != 'actions':
        raise ValueError('Proposal-only runs cannot be published as shopper trips')
    if (run['summary']['status'] != 'completed' or run['warnings']) and not allow_partial:
        raise ValueError('Partial/aborted runs require --allow-partial')
    if start['provider'] not in ('gemini','openai','openrouter') and not allow_test:
        raise ValueError('Non-Gemini/non-OpenAI/non-OpenRouter recordings require --allow-test and retain their fixture label')
    view = RecordingView(start)
    initial = view.snapshot()
    frames = []
    for event in run['events']:
        view.append(event)
        aid = event['agent_id']
        frames.append({'sequence':event['sequence'],'round':event['round'],'agent_id':aid,
                       'before':display_state(event['before'],start['catalogue']),
                       'after':display_state(event['after'],start['catalogue']),
                       'action':event['action'],'outcome':event['outcome'],'failure':event['failure'],
                       'totals':totals(view.summary),
                       'shopper_metrics':next(r for r in view.summary['shoppers'] if r['agent_id']==aid)})
    if run['end']:
        view.append(run['end'])
    payload = {'schema_version':1,
               'source':{'run_id':start['run_id'],'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                         'provider':start['provider'],'model':start['model'],'status':run['summary']['status'],
                         'recorded_at':start['recorded_at'],'prompt_variant':start.get('prompt_variant','legacy'),
                         'prompt_version':start['prompt_version'],'warnings':run['warnings']},
               'layout':start['layout'],'catalogue':start['catalogue'],
               'shoppers':[display_profile(s) for s in start['shoppers']],
               'initial':initial,'events':frames,'summary':run['summary'],
               'final':view.snapshot(), 'config':start['config']}
    return encode_payload(payload)


def export_run(path, destination, allow_partial=False, allow_test=False):
    destination = Path(destination); destination.mkdir(parents=True,exist_ok=True)
    envelope = build_bundle(path,allow_partial,allow_test)
    payload = json.loads(envelope['payload_json'])
    source = payload['source']; run_id = source['run_id']
    if not run_id.replace('-','').replace('_','').isalnum():
        raise ValueError('Unsafe run ID')
    filename = f'{run_id}.json'
    target = destination/filename
    if target.exists():
        if json.loads(target.read_text()) != envelope:
            raise FileExistsError('Different evidence already exists for this run ID')
    else:
        with target.open('x') as handle:
            json.dump(envelope,handle,ensure_ascii=False,separators=(',',':'))
    evidence = f'{run_id}.source' + ('.jsonl.gz' if Path(path).suffix=='.gz' else '.jsonl')
    if not (destination/evidence).exists():
        shutil.copyfile(path,destination/evidence)
    index = destination/'index.json'
    existing = json.loads(index.read_text()) if index.exists() else {'schema_version':1,'runs':[],'reports':[]}
    entry = {**source,'layout_id':payload['layout']['id'],'shopper_count':len(payload['shoppers']),
             'url':f'/replays/{filename}','evidence_url':f'/replays/{evidence}',
             'bundle_sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
    existing['runs'] = [r for r in existing['runs'] if r['run_id'] != run_id] + [entry]
    temporary = index.with_suffix('.tmp')
    temporary.write_text(json.dumps(existing,indent=2)+'\n'); temporary.replace(index)
    from core.evidence import update_published_history
    update_published_history(destination)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run',type=Path)
    parser.add_argument('--destination',type=Path,default=SIMULATION_DIR.parent/'landing/public/replays')
    parser.add_argument('--allow-partial',action='store_true')
    parser.add_argument('--allow-test',action='store_true')
    args=parser.parse_args()
    try:
        print(export_run(args.run,args.destination,args.allow_partial,args.allow_test))
    except (ValueError,OSError) as e:
        parser.exit(2,f'Export failed: {e}\n')

if __name__=='__main__':
    main()
