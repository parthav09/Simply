"""Audit a complete fake campaign without mistaking it for model success."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

SIMULATION_DIR=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SIMULATION_DIR))
from core.run_log import read_run
from evaluation.run import make_report


def verify(directory):
    directory=Path(directory)
    manifest=json.loads((directory/'campaign.json').read_text())
    assert manifest['provider']=='fake' and manifest['requested_shopper_count']==10
    assert manifest['layouts']==['costco_back_anchor','neighborhood_express']
    assert manifest['main_repetitions']==5
    assert len(manifest['attempts'])==14
    main=[a for a in manifest['attempts'] if a['stage']=='main']
    assert {(a['layout'],a['repetition']) for a in main}=={(layout,n) for layout in manifest['layouts'] for n in range(1,6)}
    actions=0;hashes={}
    for attempt in manifest['attempts']:
        path=directory/attempt['file'];run=read_run(path)
        assert run['start']['provider']=='fake' and run['summary']['shopper_count']==10
        assert run['summary']['finished_count']==0 and run['summary']['mean_list_completion']==0
        assert run['summary']['turns_used']==1200
        assert all(s['stop_reason']=='turn_budget_exhausted' for s in run['summary']['shoppers'])
        assert run['summary']['loop_detections']>0
        hashes[attempt['file']]=hashlib.sha256(path.read_bytes()).hexdigest()
        actions+=len(run['events'])
    report=make_report(directory)
    assert report['status']=='completed' and report['provider']=='fake'
    assert len(report['arms'])==2 and all(a['completed_runs']==5 for a in report['arms'])
    assert len(report['paired'])==16 and all(p['blocks']==5 and p['missing_blocks']==0 and p['ci95'] is not None for p in report['paired'])
    assert {'invalid_decision_rate','provider_failure_rate','request_latency_p95_ms','known_estimated_cost_usd'}<={p['metric'] for p in report['paired']}
    assert report['campaign_budget']['requests']==0
    result={'kind':'OFFLINE ORCHESTRATION CHECK ONLY','provider':'fake','attempts':14,
            'main_runs':10,'paired_repetition_blocks':5,'shoppers':10,'events':actions,
            'checkout_completions':0,'real_api_requests':0,'source_sha256':hashes}
    (directory/'orchestration-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print('OFFLINE campaign verified: 14 runs, 16,800 actions, five paired blocks, 16 comparison metrics, zero API requests. Shopper checkout failures were preserved.')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('directory',type=Path)
    verify(parser.parse_args().directory)
