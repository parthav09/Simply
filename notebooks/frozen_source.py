"""One frozen copy of the Simply Python core for dataset generation and every Colab notebook.

All simulation files come from FROZEN_COMMIT: the impulse-aware `informed` prompt (it shows
impulse_buy_probability / shopping_style) and guided_nav_v3, with CUDA provider routing already in the
commit. Only the files in OVERLAY (this work's serving + eval modules) are read from the working tree.
Every consumer checks the same SHA-256 of the result, so uncommitted experiments elsewhere cannot leak in.
"""
import hashlib
import io
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN_COMMIT = '0967ac30348e4116fcd4c279c7e971e87c269967'
SKIP_DIRS = {'runs', 'models', 'tests', 'docs', 'artifacts', 'ui', '__pycache__', 'replay', 'live'}
DATA_CSVS = ('customer_profiles_50.csv', 'shopping_lists_50.csv', 'products.csv')
OVERLAY = ('simulation/agents/cuda_runtime.py', 'simulation/agents/cuda_provider.py',
           'simulation/evaluation/impulse_eval.py')
PATCHES = {}


def _git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, check=True, capture_output=True).stdout


def files():
    """{relative path: bytes} for the frozen simulation core and catalogue."""
    out = {}
    for name in sorted(_git('ls-tree', '-r', '--name-only', FROZEN_COMMIT, 'simulation').decode().split()):
        if name.endswith('.pyc') or SKIP_DIRS & set(Path(name).parts[1:-1]):
            continue
        data = _git('show', f'{FROZEN_COMMIT}:{name}')
        for old, new in PATCHES.get(name, []):
            text = data.decode()
            assert text.count(old) == 1, f'patch target changed: {name}'
            data = text.replace(old, new).encode()
        out[name] = data
    for name in OVERLAY:
        out[name] = (ROOT / name).read_bytes()
    for name in DATA_CSVS:
        out[f'data/{name}'] = _git('show', f'{FROZEN_COMMIT}:data/{name}')
    prompt = out['simulation/agents/prompts.py'].decode()
    navigation = out['simulation/core/navigation.py'].decode()
    assert "'impulse_buy_probability': profile.impulse_buy_probability" in prompt, 'frozen prompt must be the impulse-aware v3 prompt'
    assert 'GUIDED_CURRENT = GUIDED_V3' in navigation, 'frozen policy must be guided_nav_v3'
    assert 'CUDA_PROVIDERS' in out['simulation/agents/providers.py'].decode(), 'frozen commit lacks CUDA routing'
    return out


def fingerprint(entries):
    digest = hashlib.sha256()
    for name in sorted(entries):
        digest.update(name.encode() + b'\0' + hashlib.sha256(entries[name]).digest())
    return digest.hexdigest()


def materialize(destination):
    """Write the frozen tree to destination (must be empty or absent). Returns its fingerprint."""
    destination = Path(destination)
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f'{destination} is not empty')
    entries = files()
    for name, data in entries.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (destination / 'simulation' / 'runs').mkdir(exist_ok=True)
    return fingerprint(entries)


def bundle(extra=None):
    """ZIP bytes of the frozen tree plus extra {path: bytes}; returns (bytes, source fingerprint)."""
    entries = files()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted({**entries, **(extra or {})}.items()):
            archive.writestr(zipfile.ZipInfo(name, date_time=(2026, 11, 17, 0, 0, 0)), data,
                             compress_type=zipfile.ZIP_DEFLATED)
    return buffer.getvalue(), fingerprint(entries)
