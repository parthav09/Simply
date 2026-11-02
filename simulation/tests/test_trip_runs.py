"""Full-trip evidence tests: execution, offline readers, failure recovery, and metrics."""

import contextlib
import copy
import io
import json
from dataclasses import replace
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

SIMULATION_DIR = Path(__file__).resolve().parents[1]
if str(SIMULATION_DIR) not in sys.path:
    sys.path.insert(0, str(SIMULATION_DIR))

from agents.base import Decision, ProposalResult
from agents.llm import MissingGeminiApiKeyError
from agents.providers import FakeDecisionProvider
from agents.state import CartItem
from core.customers import instantiate_agents
from core.grid import build_store
from core.rounds import RoundCoordinator, state_snapshot
from core.run_log import RunLogError, RunWriter, read_run, summarize
from core.session import SimulationSession
from compare_runs import compare_runs
from replay.__main__ import replay_text
from run_llm_simulation import build_run_start, run, snapshot_shoppers


class TripRunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.grid = build_store()
        self.shoppers = self.grid.spawn(instantiate_agents(count=3, turn_budget=4))

    def header(self, shoppers=None, max_rounds=4, proposals=False):
        return build_run_start(self.grid, shoppers or self.shoppers, run_id="test-run",
                               provider="fake", model="fake", max_rounds=max_rounds,
                               concurrency=2, propose_only=proposals)

    def fake_run(self, name="trip.jsonl", **kwargs):
        options = dict(layout_name="costco_back_anchor", shopper_count=3, max_rounds=2,
                       turn_budget=4, concurrency=2, decide=FakeDecisionProvider(),
                       output_path=self.root / name)
        options.update(kwargs)
        with contextlib.redirect_stdout(io.StringIO()):
            return run(**options)

    def save_records(self, records, name="edited.jsonl"):
        path = self.root / name
        path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
        return path

    def records(self, path):
        return [json.loads(line) for line in path.read_text().splitlines()]

    def test_snapshots_detach_cart_nested_shelves_and_requirements(self):
        shopper = self.shoppers[0]
        shopper.state.cart.append(CartItem("fixture", "fixture"))
        # Nearby shelf lists may be empty at the entrance; move next to a real product.
        req = shopper.state.requirements[0]
        shopper.state.x, shopper.state.y = self.grid.stand_cells_for((req.x, req.y))[0]
        before = state_snapshot(shopper, self.grid.observe(shopper))
        frozen = copy.deepcopy(before)
        shopper.state.cart[0].quantity = 20
        shopper.state.requirements[0].quantity = 20
        shopper.state.nearby_shelves[0].products.append("changed")
        shopper.turns_used = 1
        self.assertEqual(before, frozen)

    def test_events_capture_frozen_prompts_and_ordered_failures_on_main_thread(self):
        events, calls = [], []
        first_prompts = [s.prompt(self.grid.observe(s)) for s in self.shoppers]
        main_thread = threading.get_ident()
        callback_threads = []
        def provider(prompt, allowed):
            calls.append(prompt)
            if prompt == first_prompts[0]:
                raise TimeoutError("fixture timeout")
            if prompt == first_prompts[1]:
                return ProposalResult("not JSON", None)
            return FakeDecisionProvider()(prompt, allowed)
        def callback(event):
            events.append(event)
            callback_threads.append(threading.get_ident())
        outcomes = RoundCoordinator(provider, 2).run(self.grid, self.shoppers, event_callback=callback)
        self.assertEqual(len(calls), 3)
        self.assertEqual([e["agent_id"] for e in events], [s.customer_id for s in self.shoppers])
        self.assertEqual([e["outcome"] for e in events], ["provider_exception", "invalid_decision", "applied"])
        self.assertEqual([e["prompt"] for e in events], first_prompts)
        self.assertEqual(callback_threads, [main_thread] * 3)
        self.assertEqual([e["before"]["turns_used"] for e in events], [0, 0, 0])
        self.assertEqual([e["after"]["turns_used"] for e in events], [1, 1, 1])
        self.assertEqual(outcomes[1].raw_response, "not JSON")

    def test_grid_rejection_is_logged_separately_from_invalid_decision(self):
        events = []
        with patch.object(self.grid, "apply", return_value=False):
            RoundCoordinator(FakeDecisionProvider()).run(self.grid, self.shoppers[:1], event_callback=events.append)
        self.assertEqual(events[0]["outcome"], "grid_rejected")
        self.assertIsNotNone(events[0]["action"])
        self.assertEqual(events[0]["before"]["x"], events[0]["after"]["x"])
        self.assertEqual(events[0]["after"]["turns_used"], 1)

    def test_full_run_roundtrip_and_exclusive_output(self):
        path = self.fake_run()
        saved_bytes = path.read_bytes()
        loaded = read_run(path)
        self.assertEqual(len(loaded["events"]), 6)
        self.assertEqual(loaded["summary"]["turns_used"], 6)
        self.assertIsNone(loaded["summary"]["mean_turns_to_checkout"])
        self.assertEqual(loaded["end"]["summary"], loaded["summary"])
        with self.assertRaises(FileExistsError):
            self.fake_run()
        self.assertEqual(path.read_bytes(), saved_bytes)

    def test_default_outputs_are_unique_and_invalid_inputs_do_not_create_files(self):
        with patch("core.session.DECISION_RUNS_DIR", self.root):
            first = self.fake_run(output_path=None)
            second = self.fake_run(output_path=None)
        self.assertNotEqual(first, second)
        self.assertEqual(first.parent,self.root)
        self.assertEqual(second.parent,self.root)
        self.assertEqual(read_run(first)["summary"]["turns_used"], 6)
        for options in ({"shopper_count": 0}, {"shopper_count": 51}, {"max_rounds": 0},
                        {"turn_budget": True}, {"concurrency": -1}, {"layout_name": "missing"}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                self.fake_run(**options)
        self.assertFalse((self.root / "trip.jsonl").exists())

    def test_proposal_only_records_but_never_mutates_or_consumes_turns(self):
        loaded = read_run(self.fake_run(propose_only=True))
        self.assertEqual(loaded["summary"]["mode"], "proposals")
        self.assertEqual(loaded["summary"]["turns_used"], 0)
        for event in loaded["events"]:
            self.assertEqual(event["outcome"], "proposed")
            self.assertEqual(event["before"], event["after"])
        with self.assertRaisesRegex(RunLogError, "proposal-only"):
            compare_runs(loaded, loaded)

    def test_proposal_only_failures_remain_visible_without_counting_turns(self):
        for name, provider, category in (
            ("invalid", FakeDecisionProvider("broken JSON"), "invalid_decision"),
            ("timeout", lambda prompt, allowed: (_ for _ in ()).throw(TimeoutError("fixture")),
             "provider_exception"),
        ):
            with self.subTest(category=category):
                loaded = read_run(self.fake_run(name + ".jsonl", propose_only=True, decide=provider))
                self.assertEqual(loaded["summary"]["failures"][category], 6)
                self.assertEqual(loaded["summary"]["turns_used"], 0)
                self.assertTrue(all(e["before"] == e["after"] for e in loaded["events"]))

    def test_missing_key_records_abort_with_no_commits(self):
        path = self.root / "missing-key.jsonl"
        with patch("agents.llm.load_env_file", return_value={}):
            with self.assertRaises(MissingGeminiApiKeyError):
                self.fake_run(decide=None, output_path=path)
        loaded = read_run(path)
        self.assertEqual(loaded["events"], [])
        self.assertEqual(loaded["end"]["status"], "aborted")
        self.assertEqual(loaded["summary"]["turns_used"], 0)
        self.assertEqual(loaded["end"]["error"], "MissingGeminiApiKeyError")
        self.assertTrue(all(s["stop_reason"] == "aborted" for s in loaded["summary"]["shoppers"]))

    def test_turn_exhaustion_precedes_global_limit_and_skips_future_rounds(self):
        loaded = read_run(self.fake_run(turn_budget=1, max_rounds=5))
        self.assertEqual(len(loaded["events"]), 3)
        self.assertEqual(loaded["end"]["rounds_completed"], 1)
        self.assertTrue(all(s["stop_reason"] == "turn_budget_exhausted" for s in loaded["summary"]["shoppers"]))

    def test_no_allowed_actions_stops_without_requests(self):
        original = self.grid.observe
        def no_actions(shopper):
            return replace(original(shopper), allowed_steps=())
        with patch.object(self.grid, "observe", side_effect=no_actions), \
             patch("run_llm_simulation.build_store", return_value=self.grid):
            loaded = read_run(self.fake_run())
        self.assertEqual(loaded["events"], [])
        self.assertEqual(loaded["end"]["rounds_completed"], 0)
        self.assertTrue(all(s["stop_reason"] == "no_allowed_actions" for s in loaded["summary"]["shoppers"]))

    def test_write_failure_stops_before_requesting_another_round(self):
        real_append = RunWriter.append
        writes = []
        def broken_append(writer, event, round_number):
            writes.append(round_number)
            real_append(writer, event, round_number)
            writer.failed = True
            raise OSError("disk full fixture")
        with patch.object(RunWriter, "append", broken_append):
            with self.assertRaisesRegex(OSError, "disk full"):
                self.fake_run()
        self.assertEqual(writes, [1])
        loaded = read_run(self.root / "trip.jsonl")
        self.assertIsNone(loaded["end"])
        self.assertEqual(len(loaded["events"]), 1)

    def test_user_interrupt_after_complete_round_preserves_cancelled_record(self):
        original = SimulationSession.step
        def interrupted(session):
            result = original(session)
            if session.writer.events and len(session.writer.events) >= 3:
                raise KeyboardInterrupt()
            return result
        with patch.object(SimulationSession, "step", interrupted):
            with self.assertRaises(KeyboardInterrupt):
                self.fake_run()
        loaded = read_run(self.root / "trip.jsonl")
        self.assertGreaterEqual(len(loaded["events"]), 3)
        self.assertEqual(loaded["end"]["status"], "cancelled")
        self.assertGreaterEqual(loaded["end"]["rounds_completed"], 1)

    def test_interrupt_between_mutation_and_callback_leaves_readable_partial_run(self):
        original = self.grid.apply
        def interrupted(shopper, decision):
            original(shopper, decision)
            raise KeyboardInterrupt()
        with patch.object(self.grid, "apply", side_effect=interrupted), \
             patch("run_llm_simulation.build_store", return_value=self.grid):
            with self.assertRaises(KeyboardInterrupt):
                self.fake_run()
        loaded = read_run(self.root / "trip.jsonl")
        self.assertIsNone(loaded["end"])
        self.assertEqual(loaded["summary"]["status"], "incomplete")
        self.assertEqual(loaded["events"], [])

    def test_replay_and_comparison_do_not_load_datasets_or_contact_network(self):
        left = self.fake_run("a.jsonl")
        right = self.fake_run("b.jsonl", layout_name="neighborhood_express")
        # Run fresh interpreters with imports and dataset reads actively forbidden.
        script = '''
import builtins, runpy, sys, urllib.request
original_open = builtins.open
def safe_open(file, *args, **kwargs):
    if str(file).endswith((".csv", ".env")):
        raise AssertionError("reader loaded current dataset or credentials")
    return original_open(file, *args, **kwargs)
builtins.open = safe_open
urllib.request.urlopen = lambda *a, **k: (_ for _ in ()).throw(AssertionError("network called"))
sys.argv = sys.argv[2:]
runpy.run_module(sys.argv[0], run_name="__main__")
assert not any(m in sys.modules for m in ("core.grid", "agents.llm", "simulation.core.grid"))
'''
        for arguments in (("simulation.replay", str(left), "--agent", "C0001"),
                          ("simulation.compare_runs", str(left), str(right))):
            result = subprocess.run([sys.executable, "-c", script, "placeholder", *arguments],
                                    cwd=SIMULATION_DIR.parent, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(result.stdout)
        replay = replay_text(read_run(left), "C0001")
        self.assertIn("C0001 |", replay)
        self.assertNotIn("C0002 |", replay)
        with self.assertRaisesRegex(RunLogError, "unknown shopper"):
            replay_text(read_run(left), "missing")

    def test_truncated_final_record_recovers_but_bad_earlier_line_is_error(self):
        path = self.fake_run()
        records = self.records(path)
        partial = self.save_records(records[:-1], "partial.jsonl")
        with partial.open("a") as handle:
            handle.write('{"type": "run_end",')
        loaded = read_run(partial)
        self.assertEqual(len(loaded["events"]), 6)
        self.assertEqual(loaded["summary"]["status"], "incomplete")
        self.assertIn("truncated", " ".join(loaded["warnings"]))
        self.assertIn("Incomplete", replay_text(loaded))
        with partial.open("a") as handle:
            handle.write("\n{}\n")
        with self.assertRaisesRegex(RunLogError, "Line 8: invalid JSON"):
            read_run(partial)

    def test_unicode_text_separators_are_not_jsonl_record_boundaries(self):
        rows = self.records(self.fake_run())
        reason = "Two paragraphs\u2028and a second section\u2029with Unicode café"
        rows[1]["action"]["reason"] = reason
        rows[1]["raw_response"] = reason
        path = self.root / "unicode.jsonl"
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        loaded = read_run(path)
        self.assertEqual(len(loaded["events"]), 6)
        self.assertEqual(loaded["events"][0]["action"]["reason"], reason)
        self.assertEqual(loaded["summary"]["status"], "completed")

    def test_truncated_utf8_tail_recovers_and_bad_utf8_earlier_reports_line(self):
        rows = self.records(self.fake_run())
        path = self.save_records(rows[:-1], "multibyte.jsonl")
        with path.open("ab") as handle:
            handle.write(b'{"type":"run_end","error":"\xe2\x80')
        loaded = read_run(path)
        self.assertEqual(len(loaded["events"]), 6)
        self.assertEqual(loaded["summary"]["status"], "incomplete")
        self.assertIn("truncated", " ".join(loaded["warnings"]))
        with path.open("ab") as handle:
            handle.write(b'\n{}\n')
        with self.assertRaisesRegex(RunLogError, "Line 8: invalid UTF-8"):
            read_run(path)

    def test_reader_rejects_bad_version_state_order_and_summary_with_line_numbers(self):
        originals = self.records(self.fake_run())
        def bad_version(rows): rows[0]["schema_version"] = 999
        def bad_sequence(rows): rows[1]["sequence"] = 2
        def bad_quantity(rows): rows[1]["after"]["cart"] = [{"product_id": "bad", "quantity": -1}]
        def bad_state(rows): rows[2]["before"]["x"] = 999
        def bad_outcome(rows): rows[1]["outcome"] = "ignored"
        def missing_field(rows): del rows[1]["failure"]
        def bad_summary(rows): rows[-1]["summary"]["turns_used"] = 999
        def duplicate_commit(rows): rows[2] = copy.deepcopy(rows[1]); rows[2]["sequence"] = 2
        def extra_record(rows): rows.append(copy.deepcopy(rows[-1]))
        for mutate in (bad_version, bad_sequence, bad_quantity, bad_state, bad_outcome, missing_field,
                       bad_summary, duplicate_commit, extra_record):
            with self.subTest(mutation=mutate.__name__):
                rows = copy.deepcopy(originals)
                mutate(rows)
                with self.assertRaisesRegex(RunLogError, "Line "):
                    read_run(self.save_records(rows))

    def test_comparison_rejects_changed_inputs_incomplete_and_aborted_runs(self):
        left = read_run(self.fake_run("a.jsonl"))
        right = read_run(self.fake_run("b.jsonl", layout_name="neighborhood_express"))
        self.assertIn("neighborhood_express", compare_runs(left, right))
        for field in ("provider", "model", "prompt_version", "config", "catalogue", "shoppers"):
            changed = copy.deepcopy(right)
            if field == "shoppers":
                changed["start"][field][0]["customer"]["shopping_list"][0]["quantity"] += 1
            elif field == "config":
                changed["start"][field]["turn_budget"] += 1
            elif field == "catalogue":
                changed["start"][field][0]["price"] += 1
            else:
                changed["start"][field] += "changed"
            with self.subTest(field=field), self.assertRaisesRegex(RunLogError, "mismatch"):
                compare_runs(left, changed)
        for status in ("incomplete", "aborted"):
            changed = copy.deepcopy(right)
            changed["summary"]["status"] = status
            with self.assertRaisesRegex(RunLogError, "completed"):
                compare_runs(left, changed)

    def test_scripted_grabs_rejection_and_checkout_match_hand_calculation(self):
        shopper = self.shoppers[0]
        item = replace(shopper.customer.shopping_list[0], quantity=2)
        shopper.customer = replace(shopper.customer, shopping_list=(item,))
        self.grid.place_requirements(shopper)
        req = shopper.state.requirements[0]
        shopper.state.x, shopper.state.y = self.grid.stand_cells_for((req.x, req.y))[0]
        shopper._turn_budget = 100
        self.grid.refresh(shopper)
        header = self.header([shopper], max_rounds=100)
        header.update(provider="scripted_test", model="scripted_test")
        header["config"]["concurrency"] = 1
        path_cells = self.grid.find_path((shopper.state.x, shopper.state.y), self.grid.checkout)
        pos = (shopper.state.x, shopper.state.y)
        moves = []
        for cell in path_cells:
            delta = cell[0] - pos[0], cell[1] - pos[1]
            moves.append(Decision({(-1, 0): "move_left", (1, 0): "move_right",
                                   (0, -1): "move_up", (0, 1): "move_down"}[delta], reason="fixture path"))
            pos = cell
        actions = [Decision("grab", item.product_id, "fixture quantity") for _ in range(3)]
        actions += [Decision("grab", "unavailable-product", "fixture rejection")]
        actions += moves + [Decision("checkout", reason="fixture checkout")] * 2
        script = iter(actions)
        provider = lambda prompt, allowed: next(script)
        path = self.root / "scripted.jsonl"
        writer = RunWriter(path, header)
        try:
            for number in range(1, len(actions) + 1):
                RoundCoordinator(provider, 1).run(self.grid, [shopper],
                    event_callback=lambda event: writer.append(event, number))
            writer.finish(snapshot_shoppers(self.grid, [shopper]), len(actions))
        finally:
            writer.close()
        loaded = read_run(path)
        summary = loaded["summary"]
        self.assertEqual(summary["finished_count"], 1)
        self.assertEqual(summary["mean_list_completion"], 1)
        self.assertEqual(summary["shoppers"][0]["fulfilled_units"], 2)
        self.assertEqual(summary["shoppers"][0]["requested_units"], 2)
        self.assertEqual(summary["mean_successful_moves"], len(moves))
        self.assertEqual(summary["failures"]["grid_rejected"], 1)
        self.assertEqual(summary["turns_used"], len(moves) + 6)
        self.assertEqual(summary["mean_turns_to_checkout"], len(moves) + 6)
        self.assertEqual(summary["shoppers"][0]["stop_reason"], "finished_checkout")
        self.assertIn("grid_rejected", replay_text(loaded))
        # A 2-unit request with only one unit in the final cart is 50%, not 100%.
        final = copy.deepcopy(loaded["end"]["shoppers"])
        final[0]["state"]["cart"] = final[0]["state"]["cart"][:1]
        self.assertEqual(summarize(loaded["start"], loaded["events"], final)["mean_list_completion"], 0.5)


if __name__ == "__main__":
    unittest.main()
