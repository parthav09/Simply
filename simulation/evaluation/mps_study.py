"""Run the two frozen local pilot slots and publish only their finished recordings."""
import argparse
from datetime import datetime,timezone
import fcntl
import json
from pathlib import Path
import sys

SIMULATION_DIR=Path(__file__).resolve().parents[1]
if str(SIMULATION_DIR) not in sys.path:sys.path.insert(0,str(SIMULATION_DIR))

from core.config import ACTIVE_LAYOUT_IDS,DECISION_RUNS_DIR
from evaluation import dashboard,study
from evaluation.run import save_json


def validate(protocol):
    if (protocol['provider']!='local_mps' or protocol['kind']!='layout'
        or protocol['cohort_size']!=10 or protocol['repetitions']!=1
        or protocol['concurrency']!=1 or protocol['turn_budget']!=120
        or len(protocol['schedule'])!=2 or len(protocol['arms'])!=2
        or {a['layout_id'] for a in protocol['arms']}!=set(ACTIVE_LAYOUT_IDS)
        or any(a['model']!='qwen2.5-7b-pilot-mps' or a['policy']!='guided_nav_v2' for a in protocol['arms'])
        or protocol['shopping_rules']!='unique_single_checkout_v1'):
        raise ValueError('Expected exactly two frozen MPS pilot layout runs with baseline-equivalent settings')


def publish(directory,public):
    result=study.publish(directory,public)
    protocol=study.load_protocol(directory)
    index_path=public/'index.json';index=json.loads(index_path.read_text())
    index['qwen_pilot']={'protocol_url':f"/replays/study-{protocol['study_id']}.protocol.json",
        'sha256':protocol['sha256']}
    save_json(index_path,index)
    # Static evidence must not capture an actively changing source under a fixed run ID.
    dashboard.publish(DECISION_RUNS_DIR,public,closed_only=True)
    dashboard.verify(public)
    return result


def update_status(directory,protocol,state,error=None):
    result=study.report(directory)
    value={'study_id':protocol['study_id'],'state':state,'updated_at':datetime.now(timezone.utc).isoformat(),
        'scheduled_runs':2,'recorded_runs':len(result['runs']),
        'completed_runs':sum(r['status']=='completed' and not r['warnings'] for r in result['runs']),
        'runs':[{key:r[key] for key in ('run_id','layout_id','status','shopper_count','finished_count')} for r in result['runs']],
        'evidence_url':'http://localhost:3000/evaluation','error':error}
    temporary=directory/'worker-status.tmp'
    temporary.write_text(json.dumps(value,indent=2)+'\n');temporary.replace(directory/'worker-status.json')
    return value


def execute(directory,public):
    directory=Path(directory);public=Path(public)
    protocol=study.load_protocol(directory);validate(protocol)
    with (directory/'.worker.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        update_status(directory,protocol,'running')
        try:
            for _ in range(2):
                if study.report(directory)['status']=='completed':break
                study.execute(directory,max_new_runs=1)
                publish(directory,public)
                update_status(directory,protocol,'running')
            final=publish(directory,public)
            if final['status']!='completed':raise RuntimeError('Study retained incomplete attempts; no retry or replacement')
            return update_status(directory,protocol,'completed')
        except BaseException as error:
            # Preserve and expose a stopped attempt; never restart or substitute a model.
            try:publish(directory,public)
            except Exception:pass
            update_status(directory,protocol,'failed',f'{type(error).__name__}: {error}')
            raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--public',type=Path,default=SIMULATION_DIR.parent/'landing/public/replays')
    args=parser.parse_args()
    try:print(json.dumps(execute(args.directory,args.public)),flush=True)
    except (OSError,ValueError,RuntimeError) as error:parser.exit(2,f'Local MPS study stopped: {error}\n')


if __name__=='__main__':main()
