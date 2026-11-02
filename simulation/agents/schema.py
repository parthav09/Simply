"""Structured decision contract for LLM shoppers."""

import json

from agents.base import Decision
from agents.steps import STEP_DESCRIPTIONS

DECISION_JSON_EXAMPLE = '{"step": "move_right", "product_id": "", "reason": ""}'
MAX_PLAN_ACTIONS = 8


def parse_action_plan(raw, allowed_steps):
    """Parse a bounded model plan, without repairing or selecting any action."""
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return ()
    if (not isinstance(data, dict) or set(data) != {'reason', 'actions'}
            or not isinstance(data['reason'], str)
            or not isinstance(data['actions'], list)
            or not 1 <= len(data['actions']) <= MAX_PLAN_ACTIONS):
        return ()
    decisions = []
    for index, item in enumerate(data['actions']):
        if (not isinstance(item, dict) or set(item) != {'step', 'product_id'}
                or not isinstance(item['product_id'], str)):
            return ()
        decision = Decision(item['step'], item['product_id'] or None, data['reason'])
        # Later actions may become legal only after earlier actions execute.
        if not is_valid_decision(decision, allowed_steps if index == 0 else STEP_DESCRIPTIONS):
            return ()
        decisions.append(decision)
    return tuple(decisions)


def is_valid_decision(decision, allowed_steps):
    """Validate types even when a provider constructs Decision directly."""
    return (
        isinstance(decision, Decision)
        and isinstance(decision.step, str)
        and decision.step in allowed_steps
        and (decision.product_id is None or isinstance(decision.product_id, str))
        and isinstance(decision.reason, str)
    )


def gemini_response_schema(allowed_steps: tuple[str, ...]) -> dict:
    """OpenAPI-style schema passed to Gemini so replies match the action contract."""
    return {
        "type": "OBJECT",
        "properties": {
            "step": {
                "type": "STRING",
                "enum": list(allowed_steps),
                "description": "One allowed action for this turn.",
            },
            "product_id": {
                "type": "STRING",
                "description": "Product id when grabbing or removing; otherwise empty.",
            },
            "reason": {
                "type": "STRING",
                "description": "Brief justification for the chosen step.",
            },
        },
        "required": ["step", "reason"],
    }


def format_allowed_actions(allowed_steps: tuple[str, ...]) -> str:
    return "\n".join(
        f"- {step}: {STEP_DESCRIPTIONS[step]}" for step in allowed_steps
    )


def parse_decision(raw, allowed_steps):
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if text.startswith("```") and text.endswith("```"):
        text = text[3:-3].removeprefix("json").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    if not {"step", "reason"} <= data.keys():
        return None
    if data.keys() - {"step", "reason", "product_id"}:
        return None
    # Omission is allowed; an explicitly supplied product_id must be a string.
    if "product_id" in data and not isinstance(data["product_id"], str):
        return None
    decision = Decision(
        step=data["step"],
        product_id=data.get("product_id") or None,
        reason=data["reason"],
    )
    return decision if is_valid_decision(decision, allowed_steps) else None
