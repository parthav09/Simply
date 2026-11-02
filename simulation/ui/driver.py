"""Legacy compatibility helpers. The authoritative lab interface is React."""

from agents.state import BrowsingState, FinishedState


def cart_count(shopper, product_id):
    """Return an item count for display; this does not make decisions."""
    return sum(item.product_id == product_id for item in shopper.state.cart)


def cart_spend(grid, shopper):
    """Calculate basket spend for display; this does not make decisions."""
    total = 0.0
    by_name = {product["name"]: product for product in grid.products.values()}
    for item in shopper.state.cart:
        product = grid.products.get(item.product_id) or by_name.get(item.name)
        if product:
            total += product["price"] * item.quantity
    return round(total, 2)


def next_target(shopper):
    """Return the next unfulfilled list item for display highlighting only."""
    for item in shopper.customer.shopping_list:
        if cart_count(shopper, item.product_id) < item.quantity:
            return item
    return None


def planned_path(grid, shopper):
    """Draw a shortest-path overlay; Gemini is still responsible for the action."""
    if not isinstance(shopper.state, BrowsingState):
        return []
    target = next_target(shopper)
    start = (shopper.state.x, shopper.state.y)
    if target is None:
        return grid.find_path(start, grid.checkout) or []
    product = grid.products.get(target.product_id)
    if product is None:
        return []
    return grid.find_path(start, grid.stand_cells_for((product["x"], product["y"]))) or []


def decide_step(grid, shopper):
    """Observe the live store, then let Gemini choose one next action."""
    observation = grid.observe(shopper)
    if isinstance(shopper.state, FinishedState) or not observation.allowed_steps:
        return None
    return shopper.decide(observation, use_llm=True)


def auto_step(grid, shopper):
    """Apply one Gemini-selected action and refresh the live store state."""
    decision = decide_step(grid, shopper)
    if decision is None:
        return False
    applied = grid.apply(shopper, decision)
    return applied
