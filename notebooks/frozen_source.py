"""One frozen copy of the Simply Python core for dataset generation and every Colab notebook.

All simulation files come from FROZEN_COMMIT (benchmarked `informed` prompt, guided_nav_v2),
never from the working tree, so uncommitted prompt/policy experiments cannot leak in.
Only the CUDA serving files and the impulse eval module are added, plus two exact routing
patches. Every consumer checks the same SHA-256 of the result.
"""
import hashlib
import io
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN_COMMIT = '584298d4b28005801af8842622e76bfd7a541c3b'
SKIP_DIRS = {'runs', 'models', 'tests', 'docs', 'artifacts', 'ui', '__pycache__', 'replay', 'live'}
DATA_CSVS = ('customer_profiles_50.csv', 'shopping_lists_50.csv', 'products.csv')
NEW_FILES = ('simulation/agents/cuda_runtime.py', 'simulation/agents/cuda_provider.py',
             'simulation/evaluation/impulse_eval.py')
PATCHES = {
    'simulation/agents/providers.py': [(
        "            return MLXProvider(ledger,run_id,seed,bucket,stage_limit_usd,requests_per_minute,model=model)\n",
        "            return MLXProvider(ledger,run_id,seed,bucket,stage_limit_usd,requests_per_minute,model=model)\n"
        "        from agents.cuda_runtime import MODELS as CUDA_MODELS\n"
        "        if model in CUDA_MODELS:\n"
        "            from agents.cuda_provider import PROVIDERS as CUDA_PROVIDERS\n"
        "            return CUDA_PROVIDERS[model](ledger,run_id,seed,bucket,stage_limit_usd,requests_per_minute,model=model)\n")],
    'simulation/evaluation/study.py': [(
        "        return (MLXProvider if model==mlx_model else MPSProvider),{local_model:local_price,mlx_model:mlx_price}\n",
        "        from agents.cuda_provider import PROVIDERS as cuda_providers,PRICES as cuda_prices\n"
        "        cls={mlx_model:MLXProvider,**cuda_providers}.get(model,MPSProvider)\n"
        "        return cls,{local_model:local_price,mlx_model:mlx_price,**cuda_prices}\n")],
}


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
    for name in NEW_FILES:
        out[name] = (ROOT / name).read_bytes()
    for name in DATA_CSVS:
        out[f'data/{name}'] = _git('show', f'{FROZEN_COMMIT}:data/{name}')
    prompt = out['simulation/agents/prompts.py'].decode()
    navigation = out['simulation/core/navigation.py'].decode()
    assert 'impulse_buy_probability' not in prompt, 'frozen prompt must not expose impulse_buy_probability'
    assert "GUIDED_CURRENT = 'guided_nav_v2'" in navigation, 'frozen policy must be guided_nav_v2'
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
