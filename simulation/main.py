"""Entry point for the Simply multi-agent simulation."""

import sys
from pathlib import Path

SIMULATION_DIR = Path(__file__).resolve().parent
if str(SIMULATION_DIR) not in sys.path:
    sys.path.insert(0, str(SIMULATION_DIR))

from core.customers import instantiate_agents
from core.grid import build_store


def main() -> None:
    grid = build_store()
    agents = grid.spawn(instantiate_agents(count=15))
    print(f"{len(agents)} customer agents")
    for agent in agents:
        observation = grid.observe(agent)
        decision = agent.decide(observation, use_llm=True)
        print(
            f"{agent.customer_id} {agent.name} at ({observation.x}, {observation.y}) "
            f"-> {decision.step} ({decision.reason})"
        )


if __name__ == "__main__":
    main()
