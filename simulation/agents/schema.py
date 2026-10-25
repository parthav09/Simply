"""Structured decision contract for LLM shoppers."""

from agents.steps import STEP_DESCRIPTIONS

DECISION_JSON_EXAMPLE = '{"step": "move_right", "product_id": "", "reason": ""}'


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
