"""Metered GPT-6 Luna proposals via Responses API. No retries or action repairs."""
import json
import os
import threading
import urllib.error
import urllib.request
from time import perf_counter

from agents.base import ProposalResult, MissingProviderApiKeyError
from agents.schema import MAX_PLAN_ACTIONS, parse_action_plan, parse_decision
from agents.steps import STEP_DESCRIPTIONS
from core.env import load_env_file
from core.budget import RequestCancelledError

MODEL='gpt-6-luna'
PRICING={'model':MODEL,'as_of':'2026-10-27',
         'source':'https://developers.openai.com/api/docs/models/gpt-6-luna',
         'input_usd_per_million':.10,'cached_usd_per_million':.01,
         'cache_write_usd_per_million':.125,'cache_write_12h_usd_per_million':.25,'output_usd_per_million':.50}
MODEL_PRICING={MODEL:PRICING,'gpt-6.1-terra':{
    'model':'gpt-6.1-terra','as_of':'2026-10-27',
    'source':'https://developers.openai.com/api/docs/models/gpt-6.1-terra',
    'input_usd_per_million':1.0,'cached_usd_per_million':.05,
    'cache_write_usd_per_million':1.25,'cache_write_12h_usd_per_million':2.5,'output_usd_per_million':5.0}}


class MissingOpenAIApiKeyError(MissingProviderApiKeyError):
    pass


class OpenAIRequestError(RuntimeError):
    def __init__(self,message,request_id,reserved,details=None):
        super().__init__(message)
        self.telemetry={'request_submitted':True,'request_id':request_id,'reserved_micros':reserved,
                        'estimated_cost_micros':None,'usage':None,**(details or {})}


def response_schema(allowed):
    return {'type':'object','properties':{
        'step':{'type':'string','enum':list(allowed)},
        'product_id':{'type':'string'},'reason':{'type':'string'}},
        'required':['step','product_id','reason'],'additionalProperties':False}


def action_plan_schema():
    return {'type': 'object', 'properties': {
        'reason': {'type': 'string'},
        'actions': {'type': 'array', 'minItems': 1, 'maxItems': MAX_PLAN_ACTIONS,
                    'items': {'type': 'object', 'properties': {
                        'step': {'type': 'string', 'enum': list(STEP_DESCRIPTIONS)},
                        'product_id': {'type': 'string'}},
                        'required': ['step', 'product_id'], 'additionalProperties': False}}},
        'required': ['reason', 'actions'], 'additionalProperties': False}


def normalize_usage(usage, *, requested_cache_ttl=None):
    if not usage or any(type(usage.get(k)) is not int for k in ('input_tokens','output_tokens','total_tokens')):
        return None
    details=usage.get('input_tokens_details') or {}
    output_details=usage.get('output_tokens_details') or {}
    if any(type(details.get(k)) is not int for k in ('cached_tokens','cache_write_tokens')) or type(output_details.get('reasoning_tokens')) is not int:
        return None
    if usage['total_tokens'] != usage['input_tokens']+usage['output_tokens']:
        return None
    thoughts=output_details['reasoning_tokens'];written=details['cache_write_tokens']
    lifetimes=details.get('cache_write_tokens_details') or {}
    if written and not lifetimes and requested_cache_ttl=='30m':
        # Responses may omit the split. This request explicitly chose one TTL
        # and contains no per-breakpoint overrides, so all writes use that TTL.
        lifetimes={'ttl_30m_tokens':written,'ttl_12h_tokens':0}
    if written and (type(lifetimes.get('ttl_30m_tokens')) is not int or type(lifetimes.get('ttl_12h_tokens')) is not int):return None
    short,long=lifetimes.get('ttl_30m_tokens',0),lifetimes.get('ttl_12h_tokens',0)
    if short+long!=written:return None
    return {'promptTokenCount':usage['input_tokens'],'cachedContentTokenCount':details['cached_tokens'],
            'candidatesTokenCount':usage['output_tokens']-thoughts,'thoughtsTokenCount':thoughts,
            'totalTokenCount':usage['total_tokens'],'cacheWriteTokenCount':written,
            'cacheWrite30mTokenCount':short,'cacheWrite12hTokenCount':long}


class OpenAIProvider:
    provider_id='openai'
    model=MODEL
    pricing=PRICING
    supports_action_plans=True
    generation_settings={'temperature':.3,'max_output_tokens':256,'reasoning':{'effort':'none'},
                         'service_tier':'default','store':False,'request_seed_supported':False,
                         'prompt_cache_options':{'ttl':'30m'}}

    def __init__(self,ledger,run_id,seed=42,bucket='manual',stage_limit_usd=None,requests_per_minute=0,*,model=MODEL):
        if model not in MODEL_PRICING:raise ValueError('Unsupported OpenAI shopper model')
        self.model=model;self.pricing=dict(MODEL_PRICING[model])
        self.ledger,self.run_id,self.seed=ledger,run_id,seed
        self.bucket,self.stage_limit_usd=bucket,stage_limit_usd
        self.requests_per_minute=requests_per_minute
        self.cancelled=threading.Event();self.round_number=1

    def __call__(self,prompt,allowed_steps):
        return self.request(prompt,allowed_steps,shopper_id='single')

    def request(self,prompt,allowed_steps,shopper_id):
        return self._request(prompt,allowed_steps,shopper_id,action_plan=False)

    def request_plan(self,prompt,allowed_steps,shopper_id):
        return self._request(prompt,allowed_steps,shopper_id,action_plan=True)

    def _request(self,prompt,allowed_steps,shopper_id,*,action_plan):
        if self.cancelled.is_set():raise RequestCancelledError()
        key=os.environ.get('OPENAI_API_KEY') or load_env_file().get('OPENAI_API_KEY','')
        if not key:raise MissingOpenAIApiKeyError('OPENAI_API_KEY is missing from .env or environment')
        schema=action_plan_schema() if action_plan else response_schema(allowed_steps)
        output_limit=512 if action_plan else 256
        body={'model':self.model,'input':prompt,'temperature':.3,'max_output_tokens':output_limit,
              'reasoning':{'effort':'none'},'store':False,'service_tier':'default',
              'prompt_cache_options':{'ttl':'30m'},
              'text':{'format':{'type':'json_schema','name':'shopper_action','strict':True,'schema':schema}}}
        admission=perf_counter();self.ledger.acquire_slot(self.requests_per_minute,self.cancelled)
        admission_ms=(perf_counter()-admission)*1000
        request_id,reserved=self.ledger.reserve(self.run_id,prompt,output_limit,len(json.dumps(schema).encode()),
                        self.bucket,self.stage_limit_usd,pricing=self.pricing)
        request=urllib.request.Request('https://api.openai.com/v1/responses',data=json.dumps(body).encode(),
                   headers={'Content-Type':'application/json','Authorization':f'Bearer {key}'},method='POST')
        started=perf_counter()
        try:
            with urllib.request.urlopen(request,timeout=30) as response:
                payload=json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as error:
            details={}
            try:
                value=json.loads(error.read().decode('utf-8')).get('error',{})
                def safe_field(field):
                    text=value.get(field)
                    return text.replace(key,'[redacted]')[:1000] if isinstance(text,str) else None
                details={'provider_error_code':safe_field('code'),'provider_error_type':safe_field('type'),
                         'provider_error_message':safe_field('message'),'provider_error_param':safe_field('param')}
            except (ValueError,UnicodeError,OSError):pass
            raise OpenAIRequestError(f'OpenAI HTTP {error.code}; reservation retained, no automatic retry',request_id,reserved,details) from None
        except Exception as error:
            raise OpenAIRequestError(f'OpenAI transport {type(error).__name__}; reservation retained',request_id,reserved) from None
        usage=normalize_usage(payload.get('usage'),requested_cache_ttl='30m')
        cost=self.ledger.settle(request_id,usage,pricing=self.pricing)
        raw=''.join(c.get('text','') for item in payload.get('output',[]) if item.get('type')=='message'
                    for c in item.get('content',[]) if c.get('type')=='output_text')
        completed=payload.get('status')=='completed'
        plan=parse_action_plan(raw,allowed_steps) if action_plan and completed else ()
        decision=plan[0] if plan else (parse_decision(raw,allowed_steps) if completed and not action_plan else None)
        return ProposalResult(raw,decision,{
            'request_submitted':True,'request_id':request_id,'reserved_micros':reserved,
            'estimated_cost_micros':cost,'usage':usage,'provider_usage':payload.get('usage'),
            'model_version':payload.get('model'),'response_id':payload.get('id'),
            'response_status':payload.get('status'),'request_seed':None,
            'experiment_seed':self.seed,'shopper_id':shopper_id,'round':self.round_number,
            'api_latency_ms':(perf_counter()-started)*1000,'admission_wait_ms':admission_ms},
            continuation=plan[1:])
