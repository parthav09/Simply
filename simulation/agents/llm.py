import json
import urllib.request

from agents.base import Decision, ProposalResult
from agents.schema import gemini_response_schema
from core.env import load_env_file

MODEL = "gemini-2.5-flash"


class MissingGeminiApiKeyError(RuntimeError):
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


def parse_decision(raw, allowed_steps):
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.removeprefix("json").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    step = data.get("step")
    if step not in allowed_steps:
        return None
    product_id = data.get("product_id")
    if product_id is not None and not isinstance(product_id, str):
        return None
    reason = data.get("reason")
    if reason is not None and not isinstance(reason, str):
        return None
    return Decision(
        step=step,
        product_id=product_id or None,
        reason=reason or "",
    )


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
