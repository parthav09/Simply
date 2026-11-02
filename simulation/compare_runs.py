"""Compare compatible completed action runs entirely from saved evidence."""

import argparse
from pathlib import Path
import sys

SIMULATION_DIR = Path(__file__).resolve().parent
if str(SIMULATION_DIR) not in sys.path:
    sys.path.insert(0, str(SIMULATION_DIR))

from core.run_log import RunLogError, read_run


def compare_runs(left, right):
    for run in (left, right):
        if run["summary"]["status"] != "completed" or run["warnings"]:
            raise RunLogError("comparison requires completed, intact runs")
        if run["start"]["config"]["mode"] != "actions":
            raise RunLogError("proposal-only runs cannot be compared as shopper trips")
    if min(left['start'].get('schema_version',1),right['start'].get('schema_version',1))>=2:
        from evaluation.run import compatible
        try:compatible(left,right)
        except ValueError as error:raise RunLogError(str(error)) from error
    a, b = left["start"], right["start"]
    for field in ("provider", "model", "prompt_version", "config", "catalogue"):
        if a[field] != b[field]:
            raise RunLogError(f"comparison mismatch: {field}")
    for field in ("policy", "policy_model_sha256"):
        if a.get(field) != b.get(field):
            raise RunLogError(f"comparison mismatch: {field}")
    if [s["customer"] for s in a["shoppers"]] != [s["customer"] for s in b["shoppers"]]:
        raise RunLogError("comparison mismatch: shopper profiles or shopping lists")
    rows = []
    def add(label, getter, formatter=str):
        rows.append((label, formatter(getter(left["summary"])), formatter(getter(right["summary"]))))
    add("Checkout completion", lambda s: f"{s['finished_count']}/{s['shopper_count']}")
    add("Mean list completion", lambda s: s["mean_list_completion"], lambda v: f"{v:.1%}")
    add("Mean successful moves", lambda s: s["mean_successful_moves"], lambda v: f"{v:.2f}")
    add("Turns used", lambda s: s["turns_used"])
    add("Mean turns to checkout", lambda s: s["mean_turns_to_checkout"],
        lambda v: "N/A (0 finished)" if v is None else f"{v:.2f}")
    for kind in ("invalid_decision", "provider_exception", "grid_rejected"):
        add(kind, lambda s, kind=kind: s["failures"][kind])
    headings = ("Measure", a["layout"]["id"], b["layout"]["id"])
    widths = [max(len(row[i]) for row in [headings, *rows]) for i in range(3)]
    lines = [f"Provider/model: {a['provider']}/{a['model']}"]
    lines.extend(" | ".join(value.ljust(widths[i]) for i, value in enumerate(row)) for row in [headings, *rows])
    for run in (left, right):
        lines.append(f"{run['start']['layout']['id']} stopping reasons: " + ", ".join(
            f"{s['agent_id']}={s['stop_reason']}" for s in run["summary"]["shoppers"]))
    if a["provider"] in {"fake", "scripted_test"} or a.get("policy"):
        lines.append("Offline engineering check: test-provider outcomes do not establish realistic shopper behavior or a superior layout.")
    else:
        lines.append("Pilot observation only: model reruns can differ; one run per layout does not establish a superior layout.")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    args = parser.parse_args(argv)
    try:
        print(compare_runs(read_run(args.left), read_run(args.right)))
    except (OSError, ValueError) as error:
        parser.exit(2, f"Comparison failed: {error}\n")


if __name__ == "__main__":
    main()
