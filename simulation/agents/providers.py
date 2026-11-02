"""Offline decision provider with the same callable interface as Gemini."""

import json

from agents.base import ProposalResult
from agents.llm import parse_decision


class FakeDecisionProvider:
    """Choose the first allowed step, or replay fixed response text for testing.

    This stateless provider is safe to share across concurrent requests. Its
    choices are fixtures for engineering checks, not simulated human behavior.
    """

    model = "fake"

    def __init__(self, raw_response=None):
        self.raw_response = raw_response

    def __call__(self, prompt, allowed_steps):
        raw = self.raw_response
        if raw is None:
            raw = json.dumps({
                "step": allowed_steps[0] if allowed_steps else "",
                "product_id": "",
                "reason": "Offline test decision",
            })
        return ProposalResult(raw, parse_decision(raw, allowed_steps))


def build_provider(name,ledger,run_id,seed=42,bucket='manual',stage_limit_usd=None,requests_per_minute=0,model=None):
    if model is not None and name not in ('openai','openrouter'):raise ValueError('Model selection requires OpenAI or OpenRouter')
    if name=='openrouter':
        from agents.openrouter_provider import OpenRouterProvider,MODEL
        return OpenRouterProvider(ledger,run_id,seed,bucket,stage_limit_usd,requests_per_minute,model=model or MODEL)
    if name=='gemini':
        from agents.llm import GeminiProvider
        return GeminiProvider(ledger,run_id,seed,bucket,stage_limit_usd,requests_per_minute)
    if name=='openai':
        from agents.openai_provider import OpenAIProvider,MODEL
        return OpenAIProvider(ledger,run_id,seed,bucket,stage_limit_usd,requests_per_minute,model=model or MODEL)
    if name=='fake':return FakeDecisionProvider()
    raise ValueError(f'Unsupported provider: {name}')
