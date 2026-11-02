"""Batch one decision per customer agent and export JSONL for inspection."""

import argparse
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

SIMULATION_DIR = Path(__file__).resolve().parent
if str(SIMULATION_DIR) not in sys.path:
    sys.path.insert(0, str(SIMULATION_DIR))

from agents.base import ProposalResult
from agents.llm import MODEL, MissingGeminiApiKeyError, decide_prompt_with_gemini
from agents.providers import FakeDecisionProvider
from core.config import DECISION_RUNS_DIR
from core.cli import positive_int
from core.customers import instantiate_all_agents
from core.decision_log import build_decision_record, write_jsonl
from core.grid import build_store
from core.rounds import unpack_decision_result

def collect_decision_records(grid, shoppers, run_id, concurrency=4, decide=None):
    if isinstance(concurrency, bool) or not isinstance(concurrency, int) or concurrency < 1:
        raise ValueError("concurrency must be a positive integer")
    provider = decide if decide is not None else decide_prompt_with_gemini
    model = getattr(provider, "model", MODEL if decide is None else "custom")
    records = []

    def decide_for_shopper(shopper):
        observation = grid.observe(shopper)
        prompt = shopper.prompt(observation)
        proposal = ProposalResult(raw_response="", decision=None)
        failure = None
        if observation.allowed_steps:
            try:
                result = provider(prompt, tuple(observation.allowed_steps))
                decision, raw = unpack_decision_result(result)
                proposal = ProposalResult(raw_response=raw, decision=decision)
            except MissingGeminiApiKeyError:
                raise
            except Exception as error:
                failure = str(error) or type(error).__name__
        else:
            failure = "no allowed actions"
        return build_decision_record(
            shopper,
            observation,
            proposal,
            layout_id=grid.layout_name,
            prompt=prompt,
            run_id=run_id,
            failure=failure,
            model=model,
        )

    if concurrency == 1:
        for shopper in shoppers:
            records.append(decide_for_shopper(shopper))
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {
                executor.submit(decide_for_shopper, shopper): shopper
                for shopper in shoppers
            }
            for future in as_completed(futures):
                records.append(future.result())

    records.sort(key=lambda row: row["agent_id"])
    return records


def default_output_path():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return DECISION_RUNS_DIR / f"decisions_{stamp}.jsonl"


def run(layout_name="costco_back_anchor", output_path=None, concurrency=4, decide=None):
    run_id = uuid.uuid4().hex
    grid = build_store(layout_name)
    shoppers = grid.spawn(instantiate_all_agents())
    records = collect_decision_records(
        grid, shoppers, run_id, concurrency=concurrency, decide=decide,
    )
    path = write_jsonl(output_path or default_output_path(), records)
    valid = sum(1 for row in records if row["action"] is not None)
    print(
        f"Recorded {len(records)} decisions ({valid} valid, "
        f"{len(records) - valid} failed) for run {run_id} -> {path}"
    )
    for row in records:
        if row["failure"] is not None:
            print(f"  {row['agent_id']}: failed ({row['failure']})", file=sys.stderr)
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run one decision per customer agent and save JSONL.",
    )
    parser.add_argument("--layout", default="costco_back_anchor")
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--concurrency", type=positive_int, default=4)
    parser.add_argument("--provider", choices=("gemini", "fake"), default="gemini")
    args = parser.parse_args()
    try:
        run(
            args.layout,
            output_path=args.output,
            concurrency=args.concurrency,
            decide=FakeDecisionProvider() if args.provider == "fake" else None,
        )
    except MissingGeminiApiKeyError as error:
        print(f"Gemini configuration error: {error}", file=sys.stderr)
        raise SystemExit(2)
