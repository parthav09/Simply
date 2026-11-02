"""Read-only verification of the explicitly synthetic training demo."""

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

DIRECTORY = Path(__file__).resolve().parent
sys.path.insert(0, str(DIRECTORY.parents[1] / "simulation"))

from agents.schema import parse_decision
from core.run_log import read_run


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def verify(directory=DIRECTORY):
    manifest = json.loads((directory / "manifest.json").read_text())
    assert manifest["synthetic"] and manifest["model_requests"] == 0
    for name, expected_hash in manifest["files"].items():
        assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == expected_hash, name
    assert hashlib.sha256((directory / "generate_demo.py").read_bytes()).hexdigest() == manifest["generator_sha256"]
    fixtures = {}
    for fixture in manifest["fixtures"]:
        run = read_run(directory / fixture["fixture"])
        assert run["start"]["provider"] == "scripted_test"
        assert run["start"]["config"]["shopping_rules"] == "unique_single_checkout_v1"
        assert run["start"]["config"]["navigation_policy"] == "model_only"
        assert run["start"]["experiment"]["synthetic"]
        assert run["summary"]["finished_count"] == 1
        assert run["summary"]["purchased_unit_fulfillment"] == 1
        assert sum(event["action"]["step"] == "checkout" for event in run["events"]) == 1
        assert all(event["outcome"] == "applied" and not event["failure"] for event in run["events"])
        fixtures[fixture["fixture"]] = run
    provenance = read_jsonl(directory / "provenance.jsonl")
    index = {(row["split"], row["line"]): row for row in provenance}
    assert len(index) == len(provenance)
    groups, prompt_hashes = {}, {}
    total = 0
    for split in ("train", "validation", "test"):
        rows = read_jsonl(directory / f"{split}.jsonl")
        assert len(rows) == manifest["examples"][split]
        groups[split], prompt_hashes[split], actions = set(), set(), Counter()
        for line, row in enumerate(rows, 1):
            assert set(row) == {"messages"}
            messages = row["messages"]
            assert [message["role"] for message in messages] == ["user", "assistant"]
            meta = index[split, line]
            assert meta["synthetic"] and meta["core_validated"]
            run = fixtures[meta["fixture"]]
            assert run["start"]["experiment"]["split"] == split
            assert run["start"]["experiment"]["mission_group"] == meta["mission_group"]
            event = run["events"][meta["sequence"] - 1]
            assert messages[0]["content"] == event["prompt"]
            assert messages[1]["content"] == event["raw_response"]
            decision = parse_decision(messages[1]["content"], event["before"]["allowed_steps"])
            assert decision is not None and decision.to_dict() == event["action"]
            assert hashlib.sha256(event["prompt"].encode()).hexdigest() == meta["prompt_sha256"]
            assert hashlib.sha256(event["raw_response"].encode()).hexdigest() == meta["target_sha256"]
            actions[decision.step] += 1
            groups[split].add(meta["mission_group"])
            prompt_hashes[split].add(meta["prompt_sha256"])
        assert dict(actions) == manifest["actions"][split]
        total += len(rows)
    assert total == len(provenance)
    for left, right in (("train", "validation"), ("train", "test"), ("validation", "test")):
        assert not groups[left] & groups[right]
        assert not prompt_hashes[left] & prompt_hashes[right]
    assert {"move_left", "move_right", "move_up", "move_down", "grab", "checkout"} <= set(manifest["actions"]["train"])
    print(json.dumps({"validated_examples": total, "validated_fixtures": len(fixtures),
                      "examples": manifest["examples"], "split_leakage_checks": "passed",
                      "model_requests": 0}, indent=2))


if __name__ == "__main__":
    verify()
