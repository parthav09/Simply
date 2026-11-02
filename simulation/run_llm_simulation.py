"""Run complete shopper trips and save versioned, replayable JSONL evidence."""

import argparse
import hashlib
import sys
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

SIMULATION_DIR = Path(__file__).resolve().parent
if str(SIMULATION_DIR) not in sys.path:
    sys.path.insert(0, str(SIMULATION_DIR))

from agents.state import FinishedState
from agents.base import MissingProviderApiKeyError
from agents.llm import MODEL, MissingGeminiApiKeyError, decide_prompt_with_gemini
from agents.providers import FakeDecisionProvider
from core.config import DECISION_RUNS_DIR, DEFAULT_SHOPPER_COUNT, MAX_SHOPPER_COUNT
from core.customers import instantiate_agents
from core.cli import positive_int
from core.grid import LAYOUTS, build_store
from core.rounds import RoundCoordinator, state_snapshot
from core.run_log import SCHEMA_VERSION, RunWriter, summary_text


from core.session import SimulationSession, build_run_start, snapshot_shoppers


def run(layout_name, shopper_count, max_rounds, turn_budget=120, concurrency=4,
        propose_only=False, decide=None, output_path=None, prompt_variant="baseline",
        seed=42, ledger_path=None, requests_per_minute=0, provider_name="gemini"):
    # Keep this compatibility wrapper injectable for existing integration checks.
    grid = build_store(layout_name)
    shoppers = grid.spawn(instantiate_agents(count=shopper_count, turn_budget=turn_budget))
    session = SimulationSession(layout_name, shopper_count, max_rounds,
        turn_budget, concurrency, propose_only, decide, output_path,
        prompt_variant, seed, grid=grid, shoppers=shoppers, ledger_path=ledger_path, requests_per_minute=requests_per_minute,provider_name=provider_name)
    path = session.run()
    print(summary_text(session.summary))
    print(f"Saved run: {path}")
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout", choices=tuple(LAYOUTS), default="costco_back_anchor")
    parser.add_argument("--shoppers", type=positive_int, choices=range(1,MAX_SHOPPER_COUNT+1), default=DEFAULT_SHOPPER_COUNT)
    parser.add_argument("--turn-budget", type=positive_int, default=120)
    parser.add_argument("--max-rounds", type=positive_int, default=120)
    parser.add_argument("--concurrency", type=positive_int, default=4)
    parser.add_argument("--provider", choices=("openrouter", "openai", "gemini", "fake"), default="openrouter")
    parser.add_argument("--prompt", choices=("baseline", "informed"), default="informed")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--requests-per-minute", type=int, default=18)
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--output", type=Path, help="New JSONL path; existing files are never overwritten")
    parser.add_argument("--propose-only", action="store_true",
                        help="Record proposals without applying actions or consuming turns")
    args = parser.parse_args(argv)
    if args.provider != 'fake' and args.shoppers < DEFAULT_SHOPPER_COUNT:
        parser.error('Model runs require 10–15 shoppers; --provider fake permits smaller offline fixtures')
    try:
        run(args.layout, args.shoppers, args.max_rounds, turn_budget=args.turn_budget,
            concurrency=args.concurrency, propose_only=args.propose_only,
            decide=FakeDecisionProvider() if args.provider == "fake" else None,
            output_path=args.output, prompt_variant=args.prompt, seed=args.seed, ledger_path=args.ledger, requests_per_minute=args.requests_per_minute,provider_name=args.provider)
    except (MissingProviderApiKeyError, OSError, ValueError) as error:
        parser.exit(2, f"Run failed: {error}\n")
    except KeyboardInterrupt:
        parser.exit(130, "Run interrupted; saved events remain available for replay.\n")


if __name__ == "__main__":
    main()
