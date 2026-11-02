"""Inspect saved trip snapshots without loading current datasets or contacting Gemini."""

import argparse
from pathlib import Path
import sys

SIMULATION_DIR = Path(__file__).resolve().parents[1]
if str(SIMULATION_DIR) not in sys.path:
    sys.path.insert(0, str(SIMULATION_DIR))

from core.run_log import RunLogError, read_run, summary_text


def replay_text(run, agent_id=None):
    start = run["start"]
    ids = {s["agent_id"] for s in start["shoppers"]}
    if agent_id is not None and agent_id not in ids:
        raise RunLogError(f"unknown shopper: {agent_id}")
    lines = [f"Run {start['run_id']} | {start['layout']['id']} | {start['provider']}/{start['model']}",
             "Round | Shopper | Before -> After | Proposed action | Outcome | Cart quantity"]
    for event in run["events"]:
        if agent_id is not None and event["agent_id"] != agent_id:
            continue
        before, after, action = event["before"], event["after"], event["action"]
        def position(state):
            return f"{state['phase']} ({state['x']},{state['y']})"
        proposed = action["step"] if action else "<invalid/no decision>"
        if action and action["product_id"]:
            proposed += f" [{action['product_id']}]"
        lines.append(f"{event['round']:>5} | {event['agent_id']} | {position(before)} -> {position(after)} | "
                     f"{proposed} | {event['outcome']} | {sum(i['quantity'] for i in after['cart'])}")
        if action and action["reason"]:
            lines.append(f"      Model reason (recorded output): {action['reason']}")
        if event["failure"]:
            lines.append(f"      Failure: {event['failure']}")
    lines.extend(f"Notice: {warning}" for warning in run["warnings"])
    lines.append("Whole-run summary:")
    lines.append(summary_text(run["summary"]))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--agent")
    args = parser.parse_args(argv)
    try:
        print(replay_text(read_run(args.run), args.agent))
    except (OSError, ValueError) as error:
        parser.exit(2, f"Replay failed: {error}\n")


if __name__ == "__main__":
    main()
