from agents.base import Decision, Observation
from agents.state import (
    BrowsingState,
    CartItem,
    CheckoutState,
    FinishedState,
    TrajectoryStep,
)
from agents.steps import MOVES, STEP_DESCRIPTIONS


class Shopper:
    def __init__(self, customer, x=0, y=0, turn_budget=120):
        if isinstance(turn_budget, bool) or not isinstance(turn_budget, int) or turn_budget < 1:
            raise ValueError("turn_budget must be a positive integer")
        self.customer = customer
        self.state = BrowsingState.for_customer(customer)
        self.state.x = x
        self.state.y = y
        self.trajectory = []
        self.step_count = 0
        self._turn_budget = turn_budget
        self.turns_used = 0
        self.decision_history = ()

    @property
    def customer_id(self):
        return self.customer.customer_id

    @property
    def name(self):
        return self.customer.name

    @property
    def turn_budget(self):
        return self._turn_budget

    @property
    def out_of_turns(self):
        return self.turns_used >= self.turn_budget

    def consume_turn(self):
        if self.out_of_turns:
            return False
        self.turns_used += 1
        return True

    def record_decision_outcome(self, outcome):
        self.decision_history += (outcome,)

    def allowed_steps(self, state=None):
        state = state or self.state
        if isinstance(state, FinishedState):
            return []

        possible = set(MOVES)
        shelves = getattr(state, "nearby_shelves", [])
        if any(shelf.products for shelf in shelves):
            possible.add("grab")
        if state.cart:
            possible.add("remove")
            possible.add("checkout")
        return [step for step in STEP_DESCRIPTIONS if step in possible]

    def observe(self, state=None, customer=None):
        current_state = state or self.state
        profile = customer or self.customer
        return Observation(
            customer=profile,
            state=current_state,
            x=current_state.x,
            y=current_state.y,
            phase=type(current_state).__name__,
            cart=tuple(current_state.cart),
            nearby_shelves=tuple(getattr(current_state, "nearby_shelves", [])),
            requirements=tuple(getattr(current_state, "requirements", [])),
            allowed_steps=tuple(self.allowed_steps(current_state)),
        )

    def _unpack_observation(self, observation=None, customer=None, state=None):
        profile = customer or self.customer
        current_state = state or self.state
        if observation is None:
            return self.observe(state=current_state, customer=profile)
        if isinstance(observation, Observation):
            return Observation(
                customer=observation.customer or profile,
                state=observation.state or current_state,
                x=observation.x,
                y=observation.y,
                phase=observation.phase,
                cart=observation.cart,
                nearby_shelves=observation.nearby_shelves,
                requirements=observation.requirements,
                allowed_steps=observation.allowed_steps or tuple(self.allowed_steps(current_state)),
            )
        if isinstance(observation, dict):
            obs_state = observation.get("state", current_state)
            obs_customer = observation.get("customer", profile)
            return Observation(
                customer=obs_customer,
                state=obs_state,
                x=observation.get("x", obs_state.x),
                y=observation.get("y", obs_state.y),
                phase=observation.get("phase", type(obs_state).__name__),
                cart=tuple(observation.get("cart", obs_state.cart)),
                nearby_shelves=tuple(
                    observation.get("nearby_shelves", getattr(obs_state, "nearby_shelves", []))
                ),
                requirements=tuple(
                    observation.get("requirements", getattr(obs_state, "requirements", []))
                ),
                allowed_steps=tuple(
                    observation.get("allowed_steps", self.allowed_steps(obs_state))
                ),
            )
        return self.observe(state=observation, customer=profile)

    def decide(
        self,
        observation=None,
        customer=None,
        state=None,
        use_llm=True,
        decision_adapter=None,
    ):
        """Ask the configured LLM to choose one valid next action."""
        obs = self._unpack_observation(observation, customer=customer, state=state)
        allowed = list(obs.allowed_steps)
        if not allowed or obs.phase == "FinishedState":
            return None

        if not use_llm:
            raise RuntimeError(
                "Rule-based decisions were removed. Call decide(..., use_llm=True)."
            )

        from agents.llm import decide_with_llm

        adapter = decision_adapter or decide_with_llm
        decision = adapter(self, obs)
        if decision is None or decision.step not in allowed:
            raise RuntimeError(
                "The LLM did not return a valid allowed decision for this observation."
            )
        return decision

    def perform(self, step, product_id=None):
        if isinstance(step, Decision):
            product_id = step.product_id
            step = step.step
        if step not in self.allowed_steps():
            return False
        if step in MOVES:
            dx, dy = MOVES[step]
            return self.move(dx, dy, step)
        return getattr(self, step)(product_id)

    def move_left(self, product_id=None):
        return self.move(-1, 0, "move_left")

    def move_right(self, product_id=None):
        return self.move(1, 0, "move_right")

    def move_up(self, product_id=None):
        return self.move(0, -1, "move_up")

    def move_down(self, product_id=None):
        return self.move(0, 1, "move_down")

    def move(self, dx, dy, step):
        before_x = self.state.x
        before_y = self.state.y
        self.state.x += dx
        self.state.y += dy
        self.record(step, before_x, before_y, True)
        return True

    def grab(self, product_id=None):
        before_x = self.state.x
        before_y = self.state.y
        for shelf in self.state.nearby_shelves:
            for name in shelf.products:
                item = self.find_list_item(product_id, name)
                if product_id and item is None and product_id != name:
                    continue
                picked_id = item.product_id if item else name
                picked_name = item.product_name if item else name
                self.state.cart.append(CartItem(picked_id, picked_name, 1, shelf.x, shelf.y))
                self.record("grab", before_x, before_y, True)
                return True
        self.record("grab", before_x, before_y, False)
        return False

    def remove(self, product_id=None):
        before_x = self.state.x
        before_y = self.state.y
        if not self.state.cart:
            self.record("remove", before_x, before_y, False)
            return False
        if product_id:
            for index, item in enumerate(self.state.cart):
                if item.product_id == product_id or item.name == product_id:
                    self.state.cart.pop(index)
                    self.record("remove", before_x, before_y, True)
                    return True
        self.state.cart.pop()
        self.record("remove", before_x, before_y, True)
        return True

    def checkout(self, product_id=None):
        before_x = self.state.x
        before_y = self.state.y
        if isinstance(self.state, BrowsingState):
            self.state = self.state.enter_checkout()
            self.record("checkout", before_x, before_y, True)
            return True
        if isinstance(self.state, CheckoutState):
            self.state = self.state.finish()
            self.record("checkout", before_x, before_y, True)
            return True
        self.record("checkout", before_x, before_y, False)
        return False

    def find_list_item(self, product_id, shelf_name, customer=None):
        profile = customer or self.customer
        for item in profile.shopping_list:
            same_shelf = item.product_name == shelf_name or item.product_id == shelf_name
            if not same_shelf:
                continue
            if not product_id or product_id in (item.product_id, item.product_name):
                return item
        return None

    def record(self, step, before_x, before_y, success):
        self.step_count += 1
        self.trajectory.append(TrajectoryStep(
            self.step_count,
            step,
            before_x,
            before_y,
            self.state.x,
            self.state.y,
            [item.product_id for item in self.state.cart],
            success,
        ))

    def prompt(self, observation=None):
        obs = self._unpack_observation(observation)
        profile = obs.customer
        shelves = []
        for shelf in obs.nearby_shelves:
            products = ", ".join(shelf.products) or "empty"
            shelves.append(f"- ({shelf.x}, {shelf.y}) {shelf.aisle}: {products}")
        if not shelves:
            shelves.append("- no shelves in view")
        cart = ", ".join(getattr(item, "name", str(item)) for item in obs.cart) or "empty"
        steps = "\n".join(
            f"- {step}: {STEP_DESCRIPTIONS[step]}" for step in obs.allowed_steps
        )
        return "\n".join([
            profile.build_persona_summary(),
            "",
            profile.build_behavioral_directives(),
            "",
            "Requested products: " + (", ".join(profile.get_target_products()) or "none"),
            f"Current state: {obs.phase} at ({obs.x}, {obs.y}).",
            f"Cart: {cart}.",
            "Nearby shelves:",
            *shelves,
            "Choose one step:",
            steps,
            'Reply with JSON only: {"step": "move_right", "product_id": "", "reason": ""}',
        ])
