"""Frozen loopback MPS model proposals. Python core applies all shopper actions."""
import json
import os
import re
import threading
from time import perf_counter
import urllib.error
import urllib.request
from urllib.parse import urlparse
import uuid

from agents.base import ProposalResult
from agents.mps_runtime import MODEL,PRICING,SETTINGS
from agents.schema import parse_decision
from core.budget import RequestCancelledError
from core.env import load_env_file


def server_url():
    value=os.environ.get('SIMPLY_MPS_URL') or load_env_file().get('SIMPLY_MPS_URL','http://127.0.0.1:8766')
    parsed=urlparse(value)
    if (parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost')
        or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/')):
        raise ValueError('SIMPLY_MPS_URL must be a loopback HTTP origin')
    return value.rstrip('/')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


def local_json(base,path,body=None,timeout=5):
    request=urllib.request.Request(base+path,data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type':'application/json'} if body is not None else {})
    # Ignore proxies and redirects: local prompts must stay on the configured loopback service.
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
    with opener.open(request,timeout=timeout) as response:return json.load(response)


def health():
    value=local_json(server_url(),'/health',timeout=.5)
    identity=value.get('identity',{})
    if (value.get('status')!='ready' or identity.get('model')!=MODEL or identity.get('device')!='mps'
        or identity.get('base_model')!='Qwen/Qwen2.5-7B-Instruct'
        or identity.get('training_mode')!='pilot' or identity.get('generation')!=SETTINGS
        or not re.fullmatch('[a-f0-9]{64}',identity.get('adapter_sha256',''))
        or not re.fullmatch('[a-f0-9]{40}',identity.get('base_revision',''))):
        raise ValueError('MPS server identity is invalid')
    return identity


class MPSRequestError(RuntimeError):
    def __init__(self,message,telemetry):super().__init__(message);self.telemetry=telemetry


class MPSProvider:
    provider_id='local_mps'
    supports_action_plans=False
    model=MODEL
    pricing=PRICING
    generation_settings=SETTINGS
    server_label='Local PyTorch MPS'
    provider_label='MPS'

    @staticmethod
    def serving_health():return health()

    @staticmethod
    def serving_url():return server_url()

    @classmethod
    def settings_for_model(cls,model):
        if model!=cls.model:raise ValueError('Unsupported local shopper model')
        return {**cls.generation_settings,'serving_identity':cls.serving_health()}

    def __init__(self,ledger,run_id,seed=42,bucket='manual',stage_limit_usd=None,requests_per_minute=0,*,model=MODEL):
        if model!=self.model:raise ValueError('Unsupported local shopper model')
        try:self.generation_settings=self.settings_for_model(model)
        except (OSError,ValueError) as error:raise ValueError(f'Start the Qwen {self.provider_label} inference server before starting a shopper run') from error
        self.identity=self.generation_settings['serving_identity']
        self.base=self.serving_url();self.seed=seed;self.run_id=run_id
        self.cancelled=threading.Event();self.round_number=1

    def __call__(self,prompt,allowed_steps):return self.request(prompt,allowed_steps,'single')

    def request(self,prompt,allowed_steps,shopper_id):
        if self.cancelled.is_set():raise RequestCancelledError()
        started=perf_counter()
        telemetry={'request_submitted':True,'request_id':uuid.uuid4().hex,'reserved_micros':0,
            'estimated_cost_micros':0,'cost_basis':self.pricing['cost_basis'],'usage':None,
            'experiment_seed':self.seed,'request_seed':None,'shopper_id':shopper_id,'round':self.round_number,
            'serving_identity':self.identity,'serving_provider':self.server_label}
        try:
            value=local_json(self.base,'/decision',{'model':self.model,'prompt':prompt,'identity':self.identity},timeout=600)
            if value.get('identity')!=self.identity:raise ValueError('Serving identity drift')
            usage=value['usage'];prompt_tokens=usage['prompt_tokens'];output=usage['completion_tokens']
            if any(type(n) is not int or n<0 for n in (prompt_tokens,output)):raise ValueError('Invalid usage')
            raw=value['raw_response']
            if not isinstance(raw,str) or value.get('finish_reason') not in ('stop','length'):raise ValueError('Invalid response')
        except (OSError,ValueError,KeyError,TypeError):
            telemetry['api_latency_ms']=(perf_counter()-started)*1000
            raise MPSRequestError(f'{self.provider_label} HTTP 503; inference unavailable or identity changed; no fallback',telemetry) from None
        telemetry.update(model_version=f"{self.model}:{self.identity['base_revision']}:{self.identity['adapter_sha256']}",
            usage={'promptTokenCount':prompt_tokens,'candidatesTokenCount':output,'thoughtsTokenCount':0,
                'cachedContentTokenCount':0,'cacheWriteTokenCount':0,'totalTokenCount':prompt_tokens+output},
            api_latency_ms=(perf_counter()-started)*1000,inference_ms=value.get('inference_ms'),
            response_status=value['finish_reason'])
        return ProposalResult(raw,parse_decision(raw,allowed_steps) if value['finish_reason']=='stop' else None,telemetry)
