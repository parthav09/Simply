"""Pure integer-cent accounting, shared by execution, replay, and export."""
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP


def cents(value):
    return int((Decimal(str(value)) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def resolve_product(item, catalogue):
    by_id = {p['id']: p for p in catalogue}
    if item['product_id'] in by_id:
        return by_id[item['product_id']]
    names = [p for p in catalogue if p['name'] == item.get('name', item['product_id'])]
    return names[0] if len(names) == 1 else None


def basket(cart, catalogue):
    total, unresolved, quantities = 0, 0, Counter()
    for item in cart:
        product = resolve_product(item, catalogue)
        if product is None:
            unresolved += item['quantity']
            continue
        total += cents(product['price']) * item['quantity']
        quantities[product['id']] += item['quantity']
    return {'basket_cents': total if not unresolved else None,
            'known_basket_cents': total, 'unresolved_units': unresolved,
            'quantities': dict(quantities)}
