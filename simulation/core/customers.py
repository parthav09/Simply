"""Load CSV fixtures and instantiate independent customer shopper agents."""

import csv
from collections import defaultdict

from agents.customer import Customer, ShoppingItem
from agents.shopper import Shopper
from core.config import CUSTOMER_PROFILES_PATH, SHOPPING_LISTS_PATH


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_customers(profiles_path=CUSTOMER_PROFILES_PATH, lists_path=SHOPPING_LISTS_PATH):
    profile_rows = read_csv(profiles_path)
    list_rows = read_csv(lists_path)

    profile_ids = set()
    for row in profile_rows:
        customer_id = row["customer_id"].strip()
        has_name = row["first_name"].strip() and row["last_name"].strip()
        if customer_id and has_name:
            profile_ids.add(customer_id)

    list_ids = {row["customer_id"].strip() for row in list_rows if row["customer_id"].strip()}
    shared_ids = profile_ids & list_ids

    list_rows.sort(key=lambda row: (row["customer_id"], int(row["list_item_no"])))
    items_by_customer = defaultdict(list)
    for row in list_rows:
        customer_id = row["customer_id"].strip()
        if customer_id not in shared_ids:
            continue
        try:
            items_by_customer[customer_id].append(ShoppingItem.from_row(row))
        except (KeyError, TypeError, ValueError):
            items_by_customer.pop(customer_id, None)
            shared_ids.discard(customer_id)

    profile_rows.sort(key=lambda row: row["customer_id"])
    customers = []
    seen = set()
    for row in profile_rows:
        customer_id = row["customer_id"].strip()
        if customer_id not in shared_ids or customer_id in seen:
            continue
        if not items_by_customer[customer_id]:
            continue
        try:
            customer = Customer.from_row(row, items_by_customer[customer_id])
        except (KeyError, TypeError, ValueError):
            continue
        seen.add(customer_id)
        customers.append(customer)
    return customers


def spawn_agents(customers, count=15, start=0, turn_budget=120):
    return [
        Shopper(customer, x=0, y=index, turn_budget=turn_budget)
        for index, customer in enumerate(customers[start:start + count])
    ]


def instantiate_agents(count=15, start=0, turn_budget=120):
    customers = load_customers()
    return spawn_agents(
        customers,
        count=count,
        start=start,
        turn_budget=turn_budget,
    )


def instantiate_all_agents(turn_budget=120):
    customers = load_customers()
    return spawn_agents(customers, count=len(customers), turn_budget=turn_budget)
