import json
import urllib.request

from agents.base import Decision
from core.env import load_env_file

MODEL = "gemini-2.5-flash"


class MissingGeminiApiKeyError(RuntimeError):
    """Gemini cannot run until its API key is configured."""


def decide_prompt_with_gemini(prompt: str, allowed_steps: tuple[str, ...]):
    """Return Gemini's allowed decision for one immutable round snapshot."""
    return parse_decision(ask_gemini(prompt), allowed_steps)


def decide_with_llm(shopper, observation=None):
    obs = shopper._unpack_observation(observation)
    allowed = tuple(obs.allowed_steps)
    if not allowed:
        return None
    return decide_prompt_with_gemini(shopper.prompt(obs), allowed)


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
    step = data.get("step")
    if step not in allowed_steps:
        return None
    return Decision(
        step=step,
        product_id=data.get("product_id") or None,
        reason=data.get("reason") or "",
    )


def ask_gemini(prompt):
    key = load_env_file().get("GEMINI_API_KEY", "")
    if not key:
        raise MissingGeminiApiKeyError("GEMINI_API_KEY is missing from .env")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{MODEL}:generateContent"
    )
    body = {"contents": [{"parts": [{"text": prompt}]}]}
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
