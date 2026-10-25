MOVES = {
    "move_left": (-1, 0),
    "move_right": (1, 0),
    "move_up": (0, -1),
    "move_down": (0, 1),
}

STEP_DESCRIPTIONS = {
    **{step: f"Move one cell {step.removeprefix('move_')}." for step in MOVES},
    "grab": "Take a product from a nearby shelf.",
    "remove": "Put one cart item back.",
    "checkout": "Pay for the cart and leave.",
}
