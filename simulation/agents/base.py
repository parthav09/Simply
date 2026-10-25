from dataclasses import dataclass, field


@dataclass(frozen=True)
class Observation:
    customer: object = None
    state: object = None
    x: int = 0
    y: int = 0
    phase: str = "BrowsingState"
    cart: tuple = ()
    nearby_shelves: tuple = ()
    requirements: tuple = ()
    allowed_steps: tuple = ()


@dataclass(frozen=True)
class Decision:
    step: str
    product_id: str | None = None
    reason: str = ""

    def to_dict(self):
        return {
            "step": self.step,
            "product_id": self.product_id or "",
            "reason": self.reason,
        }


@dataclass(frozen=True)
class DecisionSnapshot:
    prompt: str
    allowed_steps: tuple[str, ...]


@dataclass(frozen=True)
class RoundOutcome:
    shopper_id: str
    decision: Decision | None = None
    failure: str | None = None
    applied: bool | None = None


@dataclass
class Agent:
    agent_id: str
    name: str = ""
    notes: list[str] = field(default_factory=list)

    def update(self, state):
        return None

    def decide(self, observation):
        raise NotImplementedError("Subclasses must implement decide(observation)")

