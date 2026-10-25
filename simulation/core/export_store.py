import json
import sys
from pathlib import Path

SIMULATION_DIR = Path(__file__).resolve().parent.parent
if str(SIMULATION_DIR) not in sys.path:
    sys.path.insert(0, str(SIMULATION_DIR))

from core.customers import load_customers
from core.grid import LAYOUTS, build_store

OUT = SIMULATION_DIR.parent / "landing" / "data" / "store.json"
OUT_V2 = SIMULATION_DIR.parent / "landing" / "data" / "store_v2.json"

PEOPLE = [
    "🧑", "👩", "👨", "👧", "🧔", "👵", "👴", "🧕",
    "👱‍♀️", "👱", "🧑‍🦰", "🧑‍🦱", "🧑‍🦳", "🧑‍🦲", "👩‍🦰",
]

PRODUCT_EMOJI = [
    ("ramen", "🍜"), ("udon", "🍜"), ("noodle", "🍜"), ("gyoza", "🥟"),
    ("rotisserie", "🍗"), ("orange chicken", "🍗"), ("teriyaki", "🍢"),
    ("banana", "🍌"), ("apple", "🍎"), ("orange", "🍊"), ("strawberr", "🍓"),
    ("blueberr", "🫐"), ("grape", "🍇"), ("lemon", "🍋"), ("peach", "🍑"),
    ("pear", "🍐"), ("melon", "🍈"), ("carrot", "🥕"), ("broccoli", "🥦"),
    ("lettuce", "🥬"), ("tomato", "🍅"), ("potato", "🥔"), ("onion", "🧅"),
    ("garlic", "🧄"), ("egg", "🥚"), ("milk", "🥛"), ("cheese", "🧀"),
    ("butter", "🧈"), ("yogurt", "🍦"), ("chicken", "🍗"), ("beef", "🥩"),
    ("ribeye", "🥩"), ("pork", "🥓"), ("salmon", "🐟"), ("shrimp", "🦐"),
    ("fish", "🐠"), ("bread", "🍞"), ("croissant", "🥐"), ("brownie", "🍫"),
    ("cake", "🍰"), ("cookie", "🍪"), ("candy", "🍬"), ("gummy", "🍬"),
    ("chocolate", "🍫"), ("coffee", "☕"), ("tea", "🍵"), ("beer", "🍺"),
    ("wine", "🍷"), ("soda", "🥤"), ("juice", "🧃"), ("water", "💧"),
    ("energy drink", "⚡"), ("rice", "🍚"), ("pasta", "🍝"), ("bean", "🫘"),
    ("soup", "🍲"), ("honey", "🍯"), ("shampoo", "🧴"), ("soap", "🧼"),
    ("tooth", "🪥"), ("vitamin", "💊"), ("detergent", "🧺"), ("towel", "🧻"),
    ("paper", "🧻"), ("baby", "🍼"), ("diaper", "👶"), ("dog", "🐶"),
    ("cat", "🐱"), ("ice cream", "🍨"), ("pizza", "🍕"), ("frozen", "🧊"),
]

DEPARTMENT_EMOJI_FALLBACK = {
    "Produce": "🥬",
    "Dairy & Eggs": "🥛",
    "Meat & Seafood": "🥩",
    "Bakery": "🥐",
    "Frozen": "🧊",
    "Pantry": "🥫",
    "Snacks": "🍪",
    "Beverages": "🥤",
    "Health & Beauty": "🧴",
    "Household": "🧹",
    "Baby": "🍼",
    "Pet": "🐾",
    "Ramen & Noodles": "🍜",
    "Prepared Meals": "🍗",
}


def product_emoji(product):
    name = product["name"].lower()
    for word, emoji in PRODUCT_EMOJI:
        if word in name:
            return emoji
    return DEPARTMENT_EMOJI_FALLBACK.get(product["department"], "🛒")


def export_layout(layout_name, customers):
    grid = build_store(layout_name=layout_name)
    meta = LAYOUTS[layout_name]
    return {
        "id": meta["id"],
        "name": meta["name"],
        "subtitle": meta["subtitle"],
        "width": grid.width,
        "height": grid.height,
        "entrance": [{"x": x, "y": y} for x, y in grid.entrance],
        "checkout": [{"x": x, "y": y} for x, y in grid.checkout],
        "exit": {"x": grid.exit[0], "y": grid.exit[1]},
        "shelves": [
            {
                "x": shelf.x,
                "y": shelf.y,
                "width": shelf.width,
                "height": shelf.height,
                "shape": shelf.shape,
                "zone": shelf.zone,
                "department": shelf.department,
                "emoji": shelf.emoji,
                "cells": [{"x": cx, "y": cy} for cx, cy in shelf.cells()],
                "products": [
                    {**p, "emoji": product_emoji(p)} for p in shelf.products
                ],
            }
            for shelf in grid.shelves
        ],
        "customers": [
            {
                "id": c.customer_id,
                "name": c.name,
                "emoji": PEOPLE[i % len(PEOPLE)],
                "age": c.age,
                "occupation": c.occupation,
                "budget": c.budget_per_trip_usd,
                "tripType": c.trip_type,
                "style": c.shopping_style,
                "pace": c.walking_pace,
                "impulseProb": c.impulse_buy_probability,
                "promoResp": c.promo_responsiveness_0_1,
                "persona": c.build_persona_summary(),
                "directives": c.build_behavioral_directives(),
                "targets": c.get_target_products(),
                "list": [
                    {
                        "productId": item.product_id,
                        "name": item.product_name,
                        "quantity": item.quantity,
                        "priority": item.priority,
                        "department": item.department,
                        "price": grid.products[item.product_id]["price"],
                        "x": grid.products[item.product_id]["x"],
                        "y": grid.products[item.product_id]["y"],
                        "emoji": product_emoji(grid.products[item.product_id]),
                    }
                    for item in c.shopping_list
                    if item.product_id in grid.products
                ],
            }
            for i, c in enumerate(customers)
        ],
    }


def main():
    customers = load_customers()[:15]
    layouts = {
        name: export_layout(name, customers)
        for name in LAYOUTS
    }
    default_layout = layouts["costco_back_anchor"]
    payload = {
        **default_layout,
        "layouts": layouts,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=1)
    OUT.write_text(text, encoding="utf-8")
    OUT_V2.write_text(text, encoding="utf-8")
    print(f"wrote {OUT} and {OUT_V2} layouts={list(layouts.keys())} customers={len(customers)}")


if __name__ == "__main__":
    main()
