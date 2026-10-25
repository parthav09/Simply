import sys
from pathlib import Path

from core.config import ROOT_ENV_PATH


def python_is_venv() -> bool:
    return sys.prefix != sys.base_prefix


def load_env_file(path: Path = ROOT_ENV_PATH) -> dict[str, str]:
    """Read a simple KEY=VALUE .env file. Does not touch the process environment."""
    if not path.is_file():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values
