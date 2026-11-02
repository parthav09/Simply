"""Offline checks for state isolation and the provider/validation boundary."""

import copy
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

SIMULATION_DIR = Path(__file__).resolve().parents[1]
if str(SIMULATION_DIR) not in sys.path:
    sys.path.insert(0, str(SIMULATION_DIR))

from agents.base import Decision
from agents.llm import MissingGeminiApiKeyError, parse_decision
from agents.providers import FakeDecisionProvider
from agents.state import CartItem, CheckoutState, FinishedState
from core.customers import instantiate_all_agents
from core.grid import build_store
from core.rounds import RoundCoordinator
from run import collect_decision_records, run


class IndependentStateTests(unittest.TestCase):
    def setUp(self):
        self.grid = build_store()
        self.shoppers = instantiate_all_agents()

    def test_all_50_agents_own_their_mutable_containers(self):
        self.assertEqual(len(self.shoppers), 50)
        self.assertEqual(len({s.customer_id for s in self.shoppers}), 50)
        for attribute in ("state", "trajectory"):
            self.assertEqual(len({id(getattr(s, attribute)) for s in self.shoppers}), 50)
        for attribute in ("cart", "requirements", "nearby_shelves"):
            self.assertEqual(
                len({id(getattr(s.state, attribute)) for s in self.shoppers}), 50,
            )

        self.grid.spawn(self.shoppers)
        # Observe the same shelf so nested product lists are exercised too.
        product = next(iter(self.grid.products.values()))
        cell = self.grid.stand_cells_for((product["x"], product["y"]))[0]
        for shopper in self.shoppers:
            shopper.state.x, shopper.state.y = cell
            self.grid.refresh(shopper)
        expected = [copy.deepcopy(s.state) for s in self.shoppers]
        for index, shopper in enumerate(self.shoppers):
            with self.subTest(agent=shopper.customer_id):
                shopper.state.cart.append(CartItem(f"test-{index}", "fixture"))
                shopper.state.cart[0].quantity = index + 2
                shopper.state.requirements[0].quantity += 10
                shopper.state.nearby_shelves[0].products.append(f"fixture-{index}")
                expected[index] = copy.deepcopy(shopper.state)
                self.assertEqual([s.state for s in self.shoppers], expected)

    def test_one_agents_action_and_phase_changes_leave_49_peers_unchanged(self):
        self.grid.spawn(self.shoppers)
        shopper = self.shoppers[0]
        peers_before = copy.deepcopy([s.__dict__ for s in self.shoppers[1:]])
        outcome = RoundCoordinator(FakeDecisionProvider()).run(self.grid, [shopper])[0]
        self.assertTrue(outcome.applied)
        self.assertEqual(shopper.turns_used, 1)
        self.assertEqual(len(shopper.trajectory), 1)
        self.assertEqual(len(shopper.decision_history), 1)

        requirement = shopper.state.requirements[0]
        product = self.grid.products[requirement.product_id]
        shopper.state.x, shopper.state.y = self.grid.stand_cells_for(
            (product["x"], product["y"]),
        )[0]
        self.grid.refresh(shopper)
        self.assertTrue(self.grid.apply(shopper, Decision("grab", requirement.product_id)))
        shopper.state.x, shopper.state.y = self.grid.checkout[0]
        self.assertTrue(self.grid.apply(shopper, "checkout"))
        self.assertIsInstance(shopper.state, CheckoutState)
        self.assertTrue(self.grid.apply(shopper, "checkout"))
        self.assertIsInstance(shopper.state, FinishedState)
        self.assertEqual([s.__dict__ for s in self.shoppers[1:]], peers_before)


class MalformedResponseTests(unittest.TestCase):
    def test_malformed_responses_are_rejected_without_raising(self):
        cases = [
            None, 42, True, b'{}', {}, [], "", "   ", "not json",
            '{"step":', '{}', '[]', 'null', 'true', '42', '"move_left"',
            '{"reason":"test"}', '{"step":"move_left"}',
            '{"step":"teleport","reason":"test"}',
            '{"step":"checkout","reason":"test"}',
            '{"step":null,"reason":"test"}',
            '{"step":[],"reason":"test"}',
            '{"step":{},"reason":"test"}',
            '{"step":42,"reason":"test"}',
            '{"step":"move_left","reason":null}',
            '{"step":"move_left","reason":[]}',
            '{"step":"move_left","reason":false}',
            '{"step":"move_left","reason":"test","product_id":null}',
            '{"step":"move_left","reason":"test","product_id":3}',
            '{"step":"move_left","reason":"test","product_id":[]}',
            '{"step":"move_left","reason":"test","extra":"ignored?"}',
            '```json\n{"step":"move_left","reason":"test"}',
            '{"step":"move_left","reason":"test"} trailing prose',
        ]
        for raw in cases:
            with self.subTest(raw=raw):
                self.assertIsNone(parse_decision(raw, ("move_left", "grab")))

    def test_valid_responses_accept_optional_product_id_and_code_fences(self):
        for raw in (
            '{"step":"grab","reason":"nearby","product_id":"P001"}',
            '```json\n{"step":"grab","reason":"nearby","product_id":"P001"}\n```',
        ):
            with self.subTest(raw=raw):
                self.assertEqual(parse_decision(raw, ("grab",)), Decision("grab", "P001", "nearby"))
        self.assertEqual(
            parse_decision(' {"step":"move_left","reason":""} ', ("move_left",)),
            Decision("move_left"),
        )
        self.assertIsNone(parse_decision('{"step":"grab","reason":"test"}', ()))

    def test_direct_decisions_cannot_bypass_type_validation(self):
        grid = build_store()
        shopper = grid.spawn(instantiate_all_agents())[0]
        step = grid.observe(shopper).allowed_steps[0]
        for decision in (Decision(step, product_id=3), Decision(step, reason=[]), Decision([])):
            with self.subTest(decision=decision):
                outcome = RoundCoordinator(lambda *_: decision).run(grid, [shopper])[0]
                self.assertEqual(outcome.failure, "invalid decision")
                self.assertIsNone(outcome.applied)
                with self.assertRaisesRegex(RuntimeError, "valid allowed decision"):
                    shopper.decide(grid.observe(shopper), decision_adapter=lambda *_: decision)
        self.assertEqual(shopper.trajectory, [])


class OfflineProviderTests(unittest.TestCase):
    def setUp(self):
        self.grid = build_store()
        self.shoppers = self.grid.spawn(instantiate_all_agents())

    def test_50_agents_complete_a_fake_round_without_network(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")) as network:
            outcomes = RoundCoordinator(FakeDecisionProvider(), max_workers=4).run(
                self.grid, self.shoppers,
            )
        network.assert_not_called()
        self.assertEqual(len(outcomes), 50)
        self.assertTrue(all(o.applied and o.failure is None for o in outcomes))
        self.assertTrue(all(s.turns_used == 1 and len(s.decision_history) == 1 for s in self.shoppers))

    def test_batch_records_each_failure_and_continues_in_both_execution_modes(self):
        prompts = [s.prompt(self.grid.observe(s)) for s in self.shoppers[:3]]

        def mixed_provider(prompt, allowed_steps):
            if prompt == prompts[0]:
                raise TimeoutError("request timed out")
            if prompt == prompts[1]:
                return FakeDecisionProvider("broken json")(prompt, allowed_steps)
            if prompt == prompts[2]:
                return Decision(allowed_steps[0], reason=3)
            return FakeDecisionProvider()(prompt, allowed_steps)

        before = copy.deepcopy([s.__dict__ for s in self.shoppers])
        for concurrency in (1, 4):
            with self.subTest(concurrency=concurrency):
                records = collect_decision_records(
                    self.grid, self.shoppers, "mixed", concurrency, decide=mixed_provider,
                )
                self.assertEqual(len(records), 50)
                self.assertEqual([r["agent_id"] for r in records], sorted(s.customer_id for s in self.shoppers))
                self.assertEqual([r["failure"] for r in records[:3]], [
                    "request timed out", "invalid decision", "invalid decision",
                ])
                self.assertTrue(all(r["action"] is None for r in records[:3]))
                self.assertEqual(records[1]["llm"]["raw_response"], "broken json")
                self.assertTrue(all(r["action"] and r["failure"] is None for r in records[3:]))
                self.assertEqual([s.__dict__ for s in self.shoppers], before)

    def test_fake_batch_cli_path_writes_50_inspectable_jsonl_records(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "decisions.jsonl"
            with patch("urllib.request.urlopen") as network, redirect_stdout(io.StringIO()) as stdout:
                path = run(output_path=output, decide=FakeDecisionProvider())
            network.assert_not_called()
            records = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(len(records), 50)
            self.assertTrue(all(r["llm"]["model"] == "fake" for r in records))
            self.assertTrue(all(r["action"] and r["failure"] is None for r in records))
            self.assertIn("50 valid, 0 failed", stdout.getvalue())

    def test_failed_decisions_are_reported_and_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            with redirect_stdout(io.StringIO()) as stdout, redirect_stderr(io.StringIO()) as stderr:
                path = run(output_path=Path(directory) / "failed.jsonl",
                           decide=FakeDecisionProvider("not json"))
            records = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertIn("0 valid, 50 failed", stdout.getvalue())
        self.assertIn(f"{self.shoppers[0].customer_id}: failed (invalid decision)", stderr.getvalue())
        self.assertTrue(all(r["failure"] == "invalid decision" for r in records))

    def test_missing_key_remains_a_fatal_configuration_error(self):
        def missing_key(*_):
            raise MissingGeminiApiKeyError("missing key")

        for concurrency in (1, 4):
            with self.subTest(concurrency=concurrency):
                with self.assertRaises(MissingGeminiApiKeyError):
                    collect_decision_records(self.grid, self.shoppers, "missing", concurrency, decide=missing_key)

    def test_batch_rejects_invalid_concurrency(self):
        for concurrency in (0, -1, True, 1.5, "4"):
            with self.subTest(concurrency=concurrency):
                with self.assertRaises(ValueError):
                    collect_decision_records(self.grid, self.shoppers, "invalid", concurrency, decide=FakeDecisionProvider())

    def test_empty_exception_still_has_a_reported_failure(self):
        def fail(*_):
            raise TimeoutError()

        outcome = RoundCoordinator(fail).run(self.grid, self.shoppers[:1])[0]
        record = collect_decision_records(self.grid, self.shoppers[:1], "empty", decide=fail)[0]
        self.assertEqual(outcome.failure, "TimeoutError")
        self.assertEqual(record["failure"], "TimeoutError")

    def test_grid_rejection_is_recorded_as_a_failed_decision(self):
        with patch.object(self.grid, "apply", return_value=False):
            outcome = RoundCoordinator(FakeDecisionProvider()).run(self.grid, self.shoppers[:1])[0]
        self.assertFalse(outcome.applied)
        self.assertEqual(outcome.failure, "action rejected by grid")
        self.assertEqual(self.shoppers[0].decision_history[-1], outcome)


if __name__ == "__main__":
    unittest.main()
