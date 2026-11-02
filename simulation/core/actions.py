"""Only core applies validated shopper actions selected by the recorded policy."""
from agents.base import Decision
from agents.state import BrowsingState, CartItem, CheckoutState, FinishedState
from agents.steps import MOVES
from core.shopping import SIMPLE_SHOPPING


def apply_action(shopper, decision, product_id=None, grid=None):
    grid = grid or getattr(shopper, '_grid', None)
    if isinstance(decision, Decision):
        product_id, step = decision.product_id, decision.step
    else:
        step = decision
    state = shopper.state
    before = state.x, state.y
    allowed = grid.observe(shopper).allowed_steps if grid else shopper.allowed_steps()
    success = False
    if step in allowed:
        if step in MOVES:
            dx, dy = MOVES[step]
            if grid is None or grid.walkable(state.x + dx, state.y + dy):
                state.x += dx
                state.y += dy
                success = True
        elif step == 'grab' and product_id and grid is not None:
            # Legacy names are accepted only when unambiguous, never substituted.
            product = grid.products.get(product_id)
            if product is None:
                matches = [p for p in grid.products.values() if p['name'] == product_id]
                product = matches[0] if len(matches) == 1 else None
            unique = getattr(shopper, 'shopping_rules', None) == SIMPLE_SHOPPING
            duplicate = unique and product and any(item.product_id == product['id'] for item in state.cart)
            if product and not duplicate and any(product['id'] in {p['id'] for p in shelf.products}
                               and grid.distance_to_shelf(state.x, state.y, shelf) == 1
                               for shelf in grid.shelves):
                state.cart.append(CartItem(product['id'], product['name'], 1, product['x'], product['y']))
                success = True
        elif step == 'remove' and product_id:
            for index, item in enumerate(state.cart):
                if item.product_id == product_id:
                    if item.quantity > 1:
                        item.quantity -= 1
                    else:
                        state.cart.pop(index)
                    success = True
                    break
        elif step == 'checkout' and state.cart:
            if isinstance(state, BrowsingState) and (grid is None or before in grid.checkout):
                checkout = state.enter_checkout()
                shopper.state = checkout.finish() if getattr(shopper, 'shopping_rules', None) == SIMPLE_SHOPPING else checkout
                success = True
            elif isinstance(state, CheckoutState):
                shopper.state = state.finish()
                success = True
    if not isinstance(state, FinishedState):
        shopper.record(step, *before, success)
    return success
