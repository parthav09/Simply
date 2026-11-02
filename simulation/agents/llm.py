"""Gemini transport and strict parsing for individual shopper decisions."""

import json
import urllib.request

from agents.base import Decision, ProposalResult, MissingProviderApiKeyError
from agents.schema import gemini_response_schema, is_valid_decision, parse_decision
from core.env import load_env_file

MODEL = "gemini-2.5-flash"


class MissingGeminiApiKeyError(MissingProviderApiKeyError):
    """Gemini cannot run until its API key is configured."""


def decide_prompt_with_gemini(prompt: str, allowed_steps: tuple[str, ...]) -> ProposalResult:
    """Return Gemini's raw text and a validated decision for one immutable round snapshot."""
    raw = ask_gemini(prompt, allowed_steps)
    return ProposalResult(raw_response=raw, decision=parse_decision(raw, allowed_steps))


def decide_with_llm(shopper, observation=None):
    obs = shopper._unpack_observation(observation)
    allowed = tuple(obs.allowed_steps)
    if not allowed:
        return None
    return decide_prompt_with_gemini(shopper.prompt(obs), allowed).decision


def act(shopper, observation=None, use_llm=True):
    decision = shopper.decide(observation, use_llm=use_llm)
    if not decision:
        return False
    return shopper.perform(decision)


def ask_gemini(prompt, allowed_steps=()):
    key = load_env_file().get("GEMINI_API_KEY", "")
    if not key:
        raise MissingGeminiApiKeyError("GEMINI_API_KEY is missing from .env")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{MODEL}:generateContent"
    )
    body = {"contents": [{"parts": [{"text": prompt}]}]}
    if allowed_steps:
        body["generationConfig"] = {
            "responseMimeType": "application/json",
            "responseSchema": gemini_response_schema(allowed_steps),
        }
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": key,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload["candidates"][0]["content"]["parts"][0]["text"]


class GeminiProvider:
    """Bounded, metered real provider. No retries and no policy fallback."""
    model = MODEL
    provider_id = 'gemini'
    from core.budget import PRICING as pricing
    generation_settings = {'temperature': 0.3, 'maxOutputTokens': 256,
                           'thinkingConfig': {'thinkingBudget': 0}}

    def __init__(self, ledger, run_id, seed=42, bucket="manual", stage_limit_usd=None, requests_per_minute=0):
        self.ledger, self.run_id, self.seed = ledger, run_id, seed
        self.round_number = 1
        self.bucket, self.stage_limit_usd = bucket, stage_limit_usd
        import threading
        self.cancelled = threading.Event()
        self.requests_per_minute = requests_per_minute

    def __call__(self, prompt, allowed_steps):
        return self.request(prompt, allowed_steps, shopper_id='single')

    def request(self, prompt, allowed_steps, shopper_id):
        from core.budget import RequestCancelledError
        if self.cancelled.is_set():raise RequestCancelledError()
        import hashlib
        import os
        import urllib.error
        key = os.environ.get('GEMINI_API_KEY') or load_env_file().get('GEMINI_API_KEY', '')
        if not key:
            raise MissingGeminiApiKeyError('GEMINI_API_KEY is missing from .env or environment')
        seed = int(hashlib.sha256(f'{self.seed}:{self.round_number}:{shopper_id}'.encode()).hexdigest()[:7], 16)
        generation = {**self.generation_settings, 'seed': seed,
                      'responseMimeType': 'application/json',
                      'responseSchema': gemini_response_schema(allowed_steps)}
        body = {'contents': [{'parts': [{'text': prompt}]}], 'generationConfig': generation}
        encoded = json.dumps(body).encode()
        from time import perf_counter
        admission_started = perf_counter()
        self.ledger.acquire_slot(self.requests_per_minute, self.cancelled)
        admission_ms = (perf_counter()-admission_started)*1000
        request_id, reserved = self.ledger.reserve(self.run_id, prompt, 256, len(json.dumps(generation).encode()),self.bucket,self.stage_limit_usd)
        request = urllib.request.Request(
            f'https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent',
            data=encoded, headers={'Content-Type': 'application/json', 'x-goog-api-key': key}, method='POST')
        api_started = perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as error:
            # Save only structured quota identifiers and retry timing, never
            # headers, request objects, keys, or arbitrary error text.
            details = {}
            try:
                body = json.loads(error.read().decode('utf-8')).get('error', {})
                details['provider_status'] = body.get('status')
                for detail in body.get('details', []):
                    if detail.get('@type', '').endswith('QuotaFailure'):
                        details['quota_violations'] = [{k:v[k] for k in ('quotaMetric','quotaId','quotaValue') if k in v} for v in detail.get('violations', [])]
                    elif detail.get('@type', '').endswith('RetryInfo'):
                        details['retry_delay'] = detail.get('retryDelay')
            except (ValueError,UnicodeError,OSError):
                pass
            raise GeminiRequestError(f'Gemini HTTP {error.code}; reservation retained, no automatic retry',request_id,reserved,details) from None
        except Exception as error:
            raise GeminiRequestError(f'Gemini transport {type(error).__name__}; reservation retained',request_id,reserved) from None
        usage = payload.get('usageMetadata')
        actual = self.ledger.settle(request_id, usage)
        candidates = payload.get('candidates', [])
        parts = candidates[0].get('content', {}).get('parts', []) if candidates else []
        raw = ''.join(p.get('text', '') for p in parts if not p.get('thought'))
        return ProposalResult(raw, parse_decision(raw, allowed_steps), {
            'usage': usage, 'model_version': payload.get('modelVersion'),
            'api_latency_ms': (perf_counter()-api_started)*1000, 'admission_wait_ms': admission_ms,
            'response_id': payload.get('responseId'), 'request_seed': seed,
            'request_id': request_id, 'reserved_micros': reserved,
            'estimated_cost_micros': actual,
            'finish_reason': candidates[0].get('finishReason') if candidates else None,
            'request_submitted': True,
        })


class GeminiRequestError(RuntimeError):
    def __init__(self,message,request_id,reserved,details=None):
        super().__init__(message)
        self.telemetry={'request_submitted':True,'request_id':request_id, **(details or {}),
                        'reserved_micros':reserved,'estimated_cost_micros':None,'usage':None}
