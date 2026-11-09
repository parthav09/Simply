"""Explicit OFFLINE training fixture; never a live policy or model fallback.

Run from the repository root with .venv/bin/python data/finetuning_demo/generate_demo.py.
Only proposes actions. SimulationSession owns all transitions and canonical logs.
"""

import argparse
import hashlib
import json
import sys
from collections import Counter, deque
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "simulation"))

from agents.base import Decision, ProposalResult
from agents.customer import ShoppingItem
from agents.schema import parse_decision
from agents.shopper import Shopper
from agents.steps import MOVES
from core.accounting import cents
from core.config import ACTIVE_LAYOUT_IDS
from core.customers import load_customers
from core.grid import build_store
from core.run_log import read_run
from core.session import SimulationSession
from core.shopping import SIMPLE_SHOPPING


def facts_from_prompt(prompt):
    return json.loads(prompt.split("Current state: ", 1)[1].split("\nChoose one step:", 1)[0])


def path_to(facts, goals):
    """Route proposal from the public floor map; no hidden store facts."""
    start = tuple(facts["position"])
    goals = {tuple(cell) for cell in goals}
    rows = facts["floor_map"]["rows"]
    frontier = deque([(start, ())])
    visited = {start}
    while frontier:
        cell, steps = frontier.popleft()
        if cell in goals:
            return steps
        for step, (dx, dy) in MOVES.items():
            nxt = cell[0] + dx, cell[1] + dy
            x, y = nxt
            if (nxt not in visited and 0 <= y < len(rows)
                    and 0 <= x < len(rows[y]) and rows[y][x] != "#"):
                visited.add(nxt)
                frontier.append((nxt, (*steps, step)))
    return None


class OfflineDemoTeacher:
    """Narrow list-completion fixture, not human behavior or a learned expert."""

    model = provider_id = "scripted_test"
    supports_action_plans = False
    generation_settings = {"decision_source": "offline_synthetic_demo_v1"}

    def __call__(self, prompt, allowed_steps):
        facts = facts_from_prompt(prompt)
        remaining = {item["product_id"]: item for item in facts["remaining_items"]}
        reachable = [p for p in facts["grabbable_products"] if p["product_id"] in remaining]
        if reachable and "grab" in allowed_steps:
            product = min(reachable, key=lambda p: p["product_id"])
            reason = f"Collect the requested {product['name']}."
            if product["unit_price_cents"] > facts["remaining_budget_cents"]:
                reason = f"Prioritize the requested {product['name']} despite exceeding my spending target."
            decision = Decision("grab", product["product_id"], reason)
        elif remaining:
            options = []
            for item in remaining.values():
                for department in facts["department_locations"]:
                    if department["department"] != item["department"]:
                        continue
                    path = path_to(facts, department["walkable_access_cells"])
                    if path:
                        options.append((len(path), item["product_id"], path, item))
            if not options:
                raise ValueError("Demo fixture has no route to a remaining target")
            _, _, path, item = min(options, key=lambda option: option[:2])
            decision = Decision(path[0], reason=f"Follow an open corridor toward {item['name']} in {item['department']}.")
        elif "checkout" in allowed_steps:
            decision = Decision("checkout", reason="My requested items are collected; pay once and finish the trip.")
        else:
            path = path_to(facts, facts["checkout_cells"])
            if not path:
                raise ValueError("Demo fixture cannot reach checkout")
            decision = Decision(path[0], reason="My list is complete; follow the open corridor to checkout.")
        raw = json.dumps(decision.to_dict(), ensure_ascii=False)
        if parse_decision(raw, allowed_steps) != decision:
            raise ValueError("Demo teacher produced an invalid action")
        return ProposalResult(raw, decision, {
            "request_submitted": False, "estimated_cost_micros": 0,
            "decision_source": "offline_synthetic_demo_v1",
        })


def dump_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def dump_jsonl(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def generate(destination):
    destination.mkdir(parents=True, exist_ok=True)
    outputs = [destination / name for name in (
        "train.jsonl", "validation.jsonl", "test.jsonl", "provenance.jsonl",
        "preview.json", "manifest.json", "fixtures",
    )]
    if any(path.exists() for path in outputs):
        raise FileExistsError("Generated files already exist; choose a new --output directory")
    (destination / "fixtures").mkdir()
    profiles = load_customers()
    split_rows = {split: [] for split in ("train", "validation", "test")}
    provenance, previews, summaries = [], {}, []
    action_counts = {split: Counter() for split in split_rows}
    # Independent synthetic missions; each mission's two layouts stay in one split.
    # These are small explicit offline fixtures, outside the live 10–15 shopper scope.
    for mission in range(6):
        split = "train" if mission < 4 else "validation" if mission == 4 else "test"
        reference_grid = build_store(ACTIVE_LAYOUT_IDS[0])
        products = [p for p in sorted(reference_grid.products.values(), key=lambda p: p["id"])
                    if p["department"] not in ("Snacks", "Beverages")]
        selected = [products[(mission * 13 + offset) % len(products)] for offset in (0, 7)]
        items = tuple(ShoppingItem(
            list_id=f"DEMO-M{mission + 1:02d}", product_id=p["id"], product_name=p["name"],
            product_type=p["type"], department=p["department"], aisle=p["aisle"],
            quantity=1, priority="high", on_written_list=True,
            expected_unit_price=p["price"], expected_line_total=p["price"],
            max_acceptable_unit_price=p["price"] * 1.1, substitute_allowed=False,
            preferred_brand=p["company"],
        ) for p in selected)
        # Budgets deliberately vary, including valid, explicitly labeled overspending.
        budget = .50 if mission in (1, 5) else round(sum(p["price"] for p in selected) * 1.5, 2)
        customer = replace(
            profiles[mission], customer_id=f"DEMO-M{mission + 1:02d}",
            first_name="Demo", last_name=f"Shopper{mission + 1}", shopping_list=items,
            shopping_style="planner", uses_shopping_list=True, impulse_buy_probability=0,
            diet_type="omnivore", food_allergy="none", health_consciousness_1_5=1,
            organic_preference_1_5=1, price_sensitivity_1_5=1, brand_loyalty_1_5=1,
            budget_per_trip_usd=budget, trip_type="top_up",
        )
        for layout in ACTIVE_LAYOUT_IDS:
            grid = build_store(layout)
            shoppers = grid.spawn([Shopper(customer, turn_budget=120)])
            # An explicit in-store fixture start adds leftward navigation coverage.
            # This is a frozen initial condition, never a teleport during a trip.
            if mission == 2:
                shoppers[0].state.x, shoppers[0].state.y = grid.width - 2, 0
            fixture_name = f"mission_{mission + 1:02d}_{layout}.jsonl"
            session = SimulationSession(
                layout_name=layout, shopper_count=1, max_rounds=120, turn_budget=120,
                concurrency=1, grid=grid, shoppers=shoppers, decide=OfflineDemoTeacher(),
                output_path=destination / "fixtures" / fixture_name,
                navigation_policy="model_only", shopping_rules=SIMPLE_SHOPPING,
                allow_action_plans=False,
                experiment={"kind": "offline_finetuning_demo", "synthetic": True,
                            "mission_group": customer.customer_id, "split": split},
            )
            session.run()
            run = read_run(session.path)
            if run["summary"]["finished_count"] != 1 or run["summary"]["purchased_unit_fulfillment"] != 1:
                raise ValueError(f"Incomplete demo fixture: {fixture_name}")
            for event in run["events"]:
                if event["outcome"] != "applied" or event["failure"]:
                    raise ValueError(f"Rejected demo action: {fixture_name}:{event['sequence']}")
                raw = event["raw_response"]
                decision = parse_decision(raw, event["before"]["allowed_steps"])
                if decision is None or decision.to_dict() != event["action"]:
                    raise ValueError("Training target differs from the validated proposal")
                row = {"messages": [
                    {"role": "user", "content": event["prompt"]},
                    {"role": "assistant", "content": raw},
                ]}
                row_number = len(split_rows[split]) + 1
                split_rows[split].append(row)
                action_counts[split][decision.step] += 1
                facts = facts_from_prompt(event["prompt"])
                provenance.append({
                    "example_id": f"{split}-{row_number:05d}", "split": split,
                    "line": row_number, "mission_group": customer.customer_id,
                    "layout": layout, "fixture": f"fixtures/{fixture_name}",
                    "sequence": event["sequence"], "synthetic": True,
                    "label_source": "offline_rule_teacher_v1", "core_validated": True,
                    "navigation_policy": "model_only", "shopping_rules": SIMPLE_SHOPPING,
                    "remaining_budget_cents_before": facts["remaining_budget_cents"],
                    "target_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                    "prompt_sha256": hashlib.sha256(event["prompt"].encode()).hexdigest(),
                })
                preview_kind = "soft_budget_pickup" if decision.step == "grab" and facts["remaining_budget_cents"] < cents(grid.products[decision.product_id]["price"]) else decision.step
                previews.setdefault(preview_kind, {
                    "example_id": provenance[-1]["example_id"],
                    "note": "Readable summary only; training files retain the full exact prompt.",
                    "observation_excerpt": {key: facts[key] for key in (
                        "position", "cart", "remaining_items", "grabbable_products",
                        "remaining_budget_cents", "allowed_steps",
                    )}, "target": decision.to_dict(),
                })
            summaries.append({"mission_group": customer.customer_id, "split": split,
                              "layout": layout, "decisions": len(run["events"]),
                              "finished": True, "fixture": f"fixtures/{fixture_name}"})
    hashes = {}
    for split, rows in split_rows.items():
        dump_jsonl(destination / f"{split}.jsonl", rows)
        hashes[split] = {hashlib.sha256(row["messages"][0]["content"].encode()).hexdigest() for row in rows}
    if any(hashes[a] & hashes[b] for a, b in (("train", "validation"), ("train", "test"), ("validation", "test"))):
        raise ValueError("Exact prompts leak between splits")
    dump_jsonl(destination / "provenance.jsonl", provenance)
    dump_json(destination / "preview.json", list(previews.values()))
    manifest = {
        "dataset": "simply_offline_synthetic_demo_v1", "synthetic": True,
        "purpose": "Fine-tuning format and engine integration demo; not human behavior or model evidence",
        "label_source": "offline_rule_teacher_v1", "model_requests": 0,
        "shopping_rules": SIMPLE_SHOPPING, "navigation_policy": "model_only",
        "split_unit": "synthetic shopper/mission group, both layouts together",
        "examples": {split: len(rows) for split, rows in split_rows.items()},
        "actions": {split: dict(counts) for split, counts in action_counts.items()},
        "source_catalogue_sha256": hashlib.sha256((ROOT / "data/products.csv").read_bytes()).hexdigest(),
        "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "limitations": [
            "Six synthetic shopper/mission groups; validation and test are demonstration splits only.",
            "Both layouts and shared catalog appear in every split; no unseen-layout or SKU generalization claim.",
            "Profile templates derive from repository CSVs; not independent external validation.",
            "One training mission starts inside the store to demonstrate leftward navigation.",
            "Labels imitate a narrow map-based list collector; no impulse, removal, rejection recovery, or realistic preference calibration.",
            "Soft-budget overspending examples are deliberate preferences, not a universal instruction to overspend.",
            "Do not publish these offline fixtures as model output or use their success as evidence of Qwen ability.",
        ],
        "fixtures": summaries,
        "files": {name: hashlib.sha256((destination / name).read_bytes()).hexdigest()
                  for name in ("train.jsonl", "validation.jsonl", "test.jsonl", "preview.json", "provenance.jsonl")},
    }
    dump_json(destination / "manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    result = generate(args.output)
    print(json.dumps({"output": str(args.output.resolve()), "examples": result["examples"],
                      "actions": result["actions"], "model_requests": 0}, indent=2))
