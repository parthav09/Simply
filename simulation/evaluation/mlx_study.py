"""Run and publish exactly the two frozen MLX pilot layout slots."""
import argparse
import fcntl
import json
from pathlib import Path
import sys

SIMULATION_DIR = Path(__file__).resolve().parents[1]
if str(SIMULATION_DIR) not in sys.path: sys.path.insert(0, str(SIMULATION_DIR))

from core.config import ACTIVE_LAYOUT_IDS, DECISION_RUNS_DIR
from core.run_log import read_run
from evaluation import dashboard, mps_study, study
from evaluation.run import save_json


def validate(protocol):
    if (protocol['provider'] != 'local_mps' or protocol['kind'] != 'layout'
            or protocol['cohort_size'] != 10 or protocol['repetitions'] != 1
            or protocol['concurrency'] != 1 or protocol['turn_budget'] != 120
            or len(protocol['schedule']) != 2 or len(protocol['arms']) != 2
            or {a['layout_id'] for a in protocol['arms']} != set(ACTIVE_LAYOUT_IDS)
            or any(a['model'] != 'qwen2.5-7b-pilot-mlx' or a['policy'] != 'guided_nav_v2' for a in protocol['arms'])
            or protocol['shopping_rules'] != 'unique_single_checkout_v1'):
        raise ValueError('Expected exactly two frozen MLX pilot layout runs')


def publish(directory, public):
    result = study.publish(directory, public)
    protocol = study.load_protocol(directory)
    index_path = public / 'index.json'
    index = json.loads(index_path.read_text())
    index['qwen_mlx'] = {'protocol_url': f"/replays/study-{protocol['study_id']}.protocol.json", 'sha256': protocol['sha256']}
    save_json(index_path, index)
    stopped = json.loads((directory / 'interrupted-slots.json').read_text()) if (directory / 'interrupted-slots.json').exists() else []
    allowed = {study.slot_path(directory, slot).name for slot in protocol['schedule']}
    if not isinstance(stopped, list) or any(name not in allowed for name in stopped):
        raise ValueError('Invalid interrupted slot list')
    dashboard.publish(DECISION_RUNS_DIR, public, closed_only=True, closed_paths=[directory / name for name in stopped])
    dashboard.verify(public)
    return result


def execute(directory, public):
    directory, public = Path(directory), Path(public)
    protocol = study.load_protocol(directory)
    validate(protocol)
    with (directory / '.worker.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        interrupted = [study.slot_path(directory, slot).name for slot in protocol['schedule']
            if study.slot_path(directory, slot).exists() and read_run(study.slot_path(directory, slot))['end'] is None]
        (directory / 'interrupted-slots.json').write_text(json.dumps(interrupted, indent=2) + '\n')
        if interrupted: publish(directory, public)
        mps_study.update_status(directory, protocol, 'running')
        try:
            for _ in range(2):
                if study.report(directory)['status'] == 'completed': break
                missing = study.report(directory)['missing_evidence']
                if not missing: break
                study.execute(directory, max_new_runs=1, skip_stopped=True)
                publish(directory, public)
                mps_study.update_status(directory, protocol, 'running')
            final = publish(directory, public)
            return mps_study.update_status(directory, protocol,
                'completed' if final['status'] == 'completed' else 'incomplete')
        except BaseException as error:
            try: publish(directory, public)
            except Exception: pass
            mps_study.update_status(directory, protocol, 'failed', f'{type(error).__name__}: {error}')
            raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--public', type=Path, default=SIMULATION_DIR.parent / 'landing/public/replays')
    args = parser.parse_args()
    try: print(json.dumps(execute(args.directory, args.public)), flush=True)
    except (OSError, ValueError, RuntimeError) as error: parser.exit(2, f'MLX study stopped: {error}\n')
