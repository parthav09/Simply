"""Loopback MLX provider with a frozen, distinct model and serving identity."""
import os
import re
from urllib.parse import urlparse

from agents.mlx_runtime import MODEL, PRICING, SETTINGS
from agents.mps_provider import MPSProvider, local_json
from core.env import load_env_file


def server_url():
    value = os.environ.get('SIMPLY_MLX_URL') or load_env_file().get('SIMPLY_MLX_URL', 'http://127.0.0.1:8767')
    parsed = urlparse(value)
    if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost')
            or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/')):
        raise ValueError('SIMPLY_MLX_URL must be a loopback HTTP origin')
    return value.rstrip('/')


def health():
    value = local_json(server_url(), '/health', timeout=.5)
    identity = value.get('identity', {})
    if (value.get('status') != 'ready' or identity.get('model') != MODEL or identity.get('device') != 'mlx-metal'
            or identity.get('base_model') != 'Qwen/Qwen2.5-7B-Instruct' or identity.get('training_mode') != 'pilot'
            or identity.get('generation') != SETTINGS or identity.get('loaded_lora_tensors') != 392
            or not re.fullmatch('[a-f0-9]{64}', identity.get('adapter_sha256', ''))
            or not re.fullmatch('[a-f0-9]{40}', identity.get('base_revision', ''))):
        raise ValueError('MLX server identity is invalid')
    return identity


class MLXProvider(MPSProvider):
    model = MODEL
    pricing = PRICING
    generation_settings = SETTINGS
    server_label = 'Local MLX Metal'
    provider_label = 'MLX'
    serving_health = staticmethod(health)
    serving_url = staticmethod(server_url)
