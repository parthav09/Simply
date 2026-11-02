"""Versioned shopping rules. Old recordings retain their original contract."""
from dataclasses import replace

LEGACY_SHOPPING = 'quantity_two_phase_v1'
SIMPLE_SHOPPING = 'unique_single_checkout_v1'
SHOPPING_RULES = (LEGACY_SHOPPING, SIMPLE_SHOPPING)


def unique_profile(customer):
    """One unit of each requested SKU; never rewrite the source customer data."""
    seen = set(); items = []
    for item in customer.shopping_list:
        if item.product_id in seen:
            continue
        seen.add(item.product_id)
        items.append(replace(item, quantity=1, expected_line_total=item.expected_line_total/item.quantity))
    return replace(customer, shopping_list=tuple(items))


def configure_shopper(shopper, rules, grid):
    if rules not in SHOPPING_RULES:
        raise ValueError('Unknown shopping rules')
    shopper.shopping_rules = rules
    if rules == SIMPLE_SHOPPING:
        if type(shopper.state).__name__ == 'CheckoutState':
            raise ValueError('Single-checkout shoppers cannot start in a checkout phase')
        ids = [item.product_id for item in shopper.state.cart]
        if len(ids) != len(set(ids)) or any(item.quantity != 1 for item in shopper.state.cart):
            raise ValueError('Unique-product shopping cannot start with duplicate cart items')
        shopper.customer = unique_profile(shopper.customer)
        grid.place_requirements(shopper)
