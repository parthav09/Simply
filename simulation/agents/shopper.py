"""Shopper behavior that turns observations into validated actions and state updates."""

from agents.base import Decision, Observation
from agents.state import (
    BrowsingState,
    CartItem,
    CheckoutState,
    FinishedState,
    TrajectoryStep,
)
from agents.schema import DECISION_JSON_EXAMPLE, format_allowed_actions, is_valid_decision
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
    def _grid(self):
        ref = getattr(self, '_grid_ref', None)
        return ref() if ref else None

    @_grid.setter
    def _grid(self, value):
        import weakref
        self._grid_ref = weakref.ref(value)

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
        if not is_valid_decision(decision, allowed):
            raise RuntimeError(
                "The LLM did not return a valid allowed decision for this observation."
            )
        return decision

    def perform(self, step, product_id=None):
        from core.actions import apply_action
        return apply_action(self, step, product_id)

    def move(self, dx, dy, step):
        return self.perform(step)

    def move_left(self, product_id=None):
        return self.perform("move_left")

    def move_right(self, product_id=None):
        return self.perform("move_right")

    def move_up(self, product_id=None):
        return self.perform("move_up")

    def move_down(self, product_id=None):
        return self.perform("move_down")

    def grab(self, product_id=None):
        return self.perform("grab", product_id)

    def remove(self, product_id=None):
        return self.perform("remove", product_id)

    def checkout(self, product_id=None):
        return self.perform("checkout", product_id)

    def record(self, step, before_x, before_y, success):
        self.step_count += 1
        self.trajectory.append(TrajectoryStep(
            self.step_count, step, before_x, before_y,
            self.state.x, self.state.y,
            [item.product_id for item in self.state.cart], success,
        ))

    def prompt(self, observation=None, *, action_plan=False):
        from agents.prompts import baseline_prompt, informed_prompt
        if getattr(self, "prompt_variant", "baseline") == "informed":
            return informed_prompt(self, observation, action_plan=action_plan)
        return baseline_prompt(self, observation)
