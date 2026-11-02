"""Convert decision observations and outcomes into inspectable JSONL records."""

import json
from datetime import datetime, timezone
from pathlib import Path

from agents.base import Observation, ProposalResult
from agents.llm import MODEL
from agents.schema import is_valid_decision


def _cart_item(item):
    return {
        "product_id": item.product_id,
        "name": getattr(item, "name", getattr(item, "product_name", str(item))),
        "quantity": getattr(item, "quantity", 1),
    }


def _nearby_shelf(shelf):
    return {
        "x": shelf.x,
        "y": shelf.y,
        "aisle": shelf.aisle,
        "department": shelf.department,
        "distance": shelf.distance,
        "products": list(shelf.products),
    }


def _requirement(req):
    return {
        "product_id": req.product_id,
        "name": req.name,
        "quantity": req.quantity,
        "x": req.x,
        "y": req.y,
    }


def observation_to_dict(observation: Observation) -> dict:
    return {
        "x": observation.x,
        "y": observation.y,
        "phase": observation.phase,
        "cart": [_cart_item(item) for item in observation.cart],
        "nearby_shelves": [_nearby_shelf(shelf) for shelf in observation.nearby_shelves],
        "requirements": [_requirement(req) for req in observation.requirements],
        "allowed_steps": list(observation.allowed_steps),
    }


def build_decision_record(
    shopper,
    observation: Observation,
    proposal: ProposalResult,
    *,
    layout_id: str,
    prompt: str,
    run_id: str,
    failure: str | None = None,
    model: str = MODEL,
):
    decision = proposal.decision
    if failure is not None or not is_valid_decision(decision, observation.allowed_steps):
        failure = failure if failure is not None else "invalid decision"
        decision = None
    return {
        "run_id": run_id,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "layout": layout_id,
        "agent_id": shopper.customer_id,
        "agent_name": shopper.name,
        "observation": observation_to_dict(observation),
        "action": decision.to_dict() if decision else None,
        "failure": failure,
        "llm": {
            "model": model,
            "raw_response": proposal.raw_response,
            "prompt": prompt,
        },
    }


def write_jsonl(path: Path, records: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path
