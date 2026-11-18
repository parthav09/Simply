"""Legacy compatibility helpers. The authoritative lab interface is React."""

from agents.state import FinishedState


def cart_count(shopper, product_id):
    """Return an item count for display; this does not make decisions."""
    return sum(item.product_id == product_id for item in shopper.state.cart)


def next_target(shopper):
    """Return the next unfulfilled list item for display highlighting only."""
    for item in shopper.customer.shopping_list:
        if cart_count(shopper, item.product_id) < item.quantity:
            return item
    return None


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
