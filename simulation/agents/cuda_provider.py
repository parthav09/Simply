"""Loopback CUDA providers with frozen, distinct model and serving identities."""
import os
import re
from urllib.parse import urlparse

from agents.cuda_runtime import IMPULSE_MODEL, MODEL, MODELS, SETTINGS, pricing
from agents.mps_provider import MPSProvider, local_json


def server_url():
    value = os.environ.get('SIMPLY_CUDA_URL', 'http://127.0.0.1:8768')
    parsed = urlparse(value)
    if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost')
            or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/')):
        raise ValueError('SIMPLY_CUDA_URL must be a loopback HTTP origin')
    return value.rstrip('/')


def health_for(model):
    value = local_json(server_url(), '/health', timeout=5)
    identity = value.get('identity', {})
    if (value.get('status') != 'ready' or identity.get('model') != model or identity.get('device') != 'cuda'
            or identity.get('base_model') != 'Qwen/Qwen2.5-7B-Instruct'
            or identity.get('training_mode') != MODELS[model]['training_mode']
            or identity.get('generation') != SETTINGS
            or not re.fullmatch('[a-f0-9]{64}', identity.get('adapter_sha256', ''))
            or not re.fullmatch('[a-f0-9]{40}', identity.get('base_revision', ''))):
        raise ValueError('CUDA server identity is invalid')
    return identity


def health():
    return health_for(MODEL)


def impulse_health():
    return health_for(IMPULSE_MODEL)


class CUDAProvider(MPSProvider):
    model = MODEL
    pricing = pricing(MODEL)
    generation_settings = SETTINGS
    server_label = 'Local CUDA (Colab)'
    provider_label = 'CUDA'
    serving_health = staticmethod(health)
    serving_url = staticmethod(server_url)


class CUDAImpulseV2Provider(CUDAProvider):
    model = IMPULSE_MODEL
    pricing = pricing(IMPULSE_MODEL)
    serving_health = staticmethod(impulse_health)


PROVIDERS = {MODEL: CUDAProvider, IMPULSE_MODEL: CUDAImpulseV2Provider}
PRICES = {name: cls.pricing for name, cls in PROVIDERS.items()}
