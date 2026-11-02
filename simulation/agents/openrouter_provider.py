"""Pinned OpenRouter Chat Completions transport; one request, no fallback or repair."""
import json
import math
import os
import threading
import urllib.error
import urllib.request
from time import perf_counter

from agents.base import ProposalResult, MissingProviderApiKeyError
from agents.openai_provider import response_schema
from agents.schema import parse_decision
from core.budget import RequestCancelledError
from core.env import load_env_file

MODEL='gpt-6-luna'
MODEL_SLUGS={'gpt-6-luna':'openai/gpt-6-luna-20260922',
             'gpt-6.1-terra':'openai/gpt-6.1-terra-20261026'}
MODEL_PRICING={model:{'model':model,'as_of':'2026-10-29',
    'source':f'https://openrouter.ai/api/v1/models/{model_slug}/endpoints',
    'input_usd_per_million':input_price,'cached_usd_per_million':cached,
    'cache_write_usd_per_million':input_price*1.25,
    'cache_write_12h_usd_per_million':input_price*2.5,'output_usd_per_million':output_price,
    'serving_provider':'OpenAI','endpoint':'openai','service_tier':'default',
    'cost_basis':'frozen token-price estimate; OpenRouter-reported charge recorded separately'}
    for model,model_slug,input_price,cached,output_price in
    [('gpt-6-luna',MODEL_SLUGS['gpt-6-luna'],.1,.01,.5),
     ('gpt-6.1-terra',MODEL_SLUGS['gpt-6.1-terra'],1.,.05,5.)]}


def api_key():
    settings=load_env_file()
    return (os.environ.get('OPENROUTER_API_KEY') or os.environ.get('OPEN_ROUTER_KEY')
            or settings.get('OPENROUTER_API_KEY') or settings.get('OPEN_ROUTER_KEY',''))


def normalize_usage(usage):
    if not isinstance(usage,dict) or any(type(usage.get(k)) is not int or usage[k]<0 for k in ('prompt_tokens','completion_tokens','total_tokens')):
        return None
    if usage['total_tokens']!=usage['prompt_tokens']+usage['completion_tokens']:return None
    details=usage.get('prompt_tokens_details') or {}; completion=usage.get('completion_tokens_details') or {}
    cached=details.get('cached_tokens',0); written=details.get('cache_write_tokens',0)
    thoughts=completion.get('reasoning_tokens',0)
    if any(type(n) is not int or n<0 for n in (cached,written,thoughts)) or cached+written>usage['prompt_tokens'] or thoughts>usage['completion_tokens']:return None
    # OpenRouter publishes a standard per-token cache-write price for this
    # endpoint. Use that frozen price without inventing a cache TTL. Absent
    # lifetime-specific fields intentionally use the ledger's generic-write path.
    return {'promptTokenCount':usage['prompt_tokens'],'candidatesTokenCount':usage['completion_tokens']-thoughts,
        'thoughtsTokenCount':thoughts,'totalTokenCount':usage['total_tokens'],
        'cachedContentTokenCount':cached,'cacheWriteTokenCount':written}


class OpenRouterRequestError(RuntimeError):
    def __init__(self,message,request_id,reserved,details=None):
        super().__init__(message)
        self.telemetry={'request_submitted':True,'request_id':request_id,'reserved_micros':reserved,
            'estimated_cost_micros':None,'usage':None,**(details or {})}


class OpenRouterProvider:
    provider_id='openrouter'
    supports_action_plans=False
    generation_settings={'max_tokens':256,'reasoning':{'effort':'none'},'service_tier':'default',
        'stream':False,'request_seed_supported':False,'response_format':'strict_json_schema',
        'provider':{'only':['openai'],'order':['openai'],'ignore':['openai/flex','openai/fast'],
                    'allow_fallbacks':False,'require_parameters':True},'plugins':[]}

    def __init__(self,ledger,run_id,seed=42,bucket='manual',stage_limit_usd=None,requests_per_minute=0,*,model=MODEL):
        if model not in MODEL_SLUGS:raise ValueError('Unsupported OpenRouter shopper model; no model substitution')
        self.model=model; self.pricing=dict(MODEL_PRICING[model])
        self.ledger,self.run_id,self.seed=ledger,run_id,seed
        self.bucket,self.stage_limit_usd=bucket,stage_limit_usd
        self.requests_per_minute=requests_per_minute;self.cancelled=threading.Event();self.round_number=1

    def __call__(self,prompt,allowed_steps):return self.request(prompt,allowed_steps,'single')

    def request(self,prompt,allowed_steps,shopper_id):
        if self.cancelled.is_set():raise RequestCancelledError()
        key=api_key()
        if not key:raise MissingProviderApiKeyError('OPENROUTER_API_KEY (or OPEN_ROUTER_KEY) is missing')
        schema=response_schema(allowed_steps)
        body={'model':MODEL_SLUGS[self.model],'messages':[{'role':'user','content':prompt}],
            **{k:v for k,v in self.generation_settings.items() if k not in ('request_seed_supported','response_format')},
            'usage':{'include':True},'session_id':f'{self.run_id}:{shopper_id}',
            'response_format':{'type':'json_schema','json_schema':{'name':'shopper_action','strict':True,'schema':schema}}}
        admission=perf_counter();self.ledger.acquire_slot(self.requests_per_minute,self.cancelled)
        admission_ms=(perf_counter()-admission)*1000
        request_id,reserved=self.ledger.reserve(self.run_id,prompt,256,len(json.dumps(schema).encode()),
            self.bucket,self.stage_limit_usd,pricing=self.pricing)
        request=urllib.request.Request('https://openrouter.ai/api/v1/chat/completions',data=json.dumps(body).encode(),
            headers={'Content-Type':'application/json','Authorization':f'Bearer {key}','X-OpenRouter-Title':'Simply controlled evaluation'},method='POST')
        started=perf_counter()
        try:
            with urllib.request.urlopen(request,timeout=60) as response:payload=json.loads(response.read().decode())
        except urllib.error.HTTPError as error:
            details={}
            try:
                value=json.loads(error.read().decode()).get('error',{})
                details={'provider_error_code':str(value.get('code',error.code)),
                    'provider_error_message':str(value.get('message','')).replace(key,'[redacted]')[:1000]}
            except (ValueError,UnicodeError,OSError):pass
            raise OpenRouterRequestError(f'OpenRouter HTTP {error.code}; reservation retained, no automatic retry',request_id,reserved,details) from None
        except Exception as error:
            raise OpenRouterRequestError(f'OpenRouter transport {type(error).__name__}; reservation retained',request_id,reserved) from None
        if payload.get('error'):
            error=payload['error']
            raise OpenRouterRequestError('OpenRouter HTTP 400; upstream error, no automatic retry',request_id,reserved,
                {'provider_error_code':str(error.get('code')),'provider_error_message':str(error.get('message','')).replace(key,'[redacted]')[:1000]})
        usage=normalize_usage(payload.get('usage'));cost=self.ledger.settle(request_id,usage,pricing=self.pricing)
        provider_usage=payload.get('usage') or {};reported=provider_usage.get('cost')
        if type(reported) not in (int,float) or not math.isfinite(reported) or reported<0:reported=None
        choice=(payload.get('choices') or [{}])[0];raw=(choice.get('message') or {}).get('content') or ''
        actual_model=payload.get('model');upstream=payload.get('provider')
        identity_ok=actual_model in (MODEL_SLUGS[self.model],'openai/'+self.model) and upstream=='OpenAI'
        telemetry={'request_submitted':True,'request_id':request_id,'reserved_micros':reserved,
            'estimated_cost_micros':cost,'usage':usage,'provider_usage':provider_usage,
            'provider_reported_cost_usd':reported,'model_version':actual_model,'serving_provider':upstream,
            'requested_model_slug':MODEL_SLUGS[self.model],'response_id':payload.get('id'),
            'response_status':choice.get('finish_reason'),'system_fingerprint':payload.get('system_fingerprint'),
            'request_seed':None,'experiment_seed':self.seed,'shopper_id':shopper_id,'round':self.round_number,
            'api_latency_ms':(perf_counter()-started)*1000,'admission_wait_ms':admission_ms}
        if not identity_ok:
            # Still record and account for a paid unexpected response; never apply it.
            error=OpenRouterRequestError('OpenRouter HTTP 400; serving model/provider drift',request_id,reserved)
            error.telemetry=telemetry|{'provider_error_code':'serving_identity_mismatch'}
            raise error
        return ProposalResult(raw,parse_decision(raw,allowed_steps) if choice.get('finish_reason')=='stop' else None,telemetry)
