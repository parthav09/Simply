import sys
import threading
import tempfile
import unittest
from concurrent.futures import Future
from pathlib import Path
from unittest.mock import patch


SIMULATION_DIR = Path(__file__).resolve().parents[1]
if str(SIMULATION_DIR) not in sys.path:
    sys.path.insert(0, str(SIMULATION_DIR))

from agents import Agent, CustomerProfile, Decision
from agents.base import ProposalResult
from agents.llm import (
    MissingGeminiApiKeyError,
    act,
    ask_gemini,
    decide_prompt_with_gemini,
    parse_decision,
)
from agents.shopper import Shopper
from agents.state import CheckoutState, FinishedState
from core.config import DECISION_RUNS_DIR, RESULTS_PATH, TRAJECTORY_DIR, VENV_PYTHON
from core.customers import (
    instantiate_agents,
    instantiate_all_agents,
    load_customers,
    spawn_agents,
)
from core.decision_log import build_decision_record, observation_to_dict, write_jsonl
from core.env import python_is_venv
from core.grid import build_store
from core.rounds import RoundCoordinator
from ui.driver import auto_step


class SimulationContractTests(unittest.TestCase):
    def setUp(self):
        self.grid = build_store()
        self.shopper = self.grid.spawn(instantiate_agents(count=1))[0]

    def test_instantiate_all_agents_loads_every_customer(self):
        shoppers = instantiate_all_agents()
        self.assertEqual(len(shoppers), len(load_customers()))

    def test_customer_data_builds_agents_with_shopping_lists(self):
        customers = load_customers()

        self.assertEqual(len(customers), 50)
        self.assertTrue(all(customer.shopping_list for customer in customers))
        self.assertEqual(self.shopper.customer_id, customers[0].customer_id)

    def test_public_compatibility_symbols_remain_available(self):
        customer = load_customers()[0]

        self.assertIsInstance(Agent("test"), Agent)
        self.assertIs(CustomerProfile, type(customer))
        self.assertTrue(callable(act))
        self.assertTrue(callable(spawn_agents))
        self.assertTrue(callable(python_is_venv))
        self.assertTrue(VENV_PYTHON.name == "python")
        self.assertEqual(RESULTS_PATH.name, "results.json")
        self.assertEqual(TRAJECTORY_DIR.name, "trajectory")

    def test_grid_rejects_walls_and_records_the_attempt(self):
        self.shopper.state.x = 0
        self.shopper.state.y = 0
        start = (self.shopper.state.x, self.shopper.state.y)

        self.assertFalse(self.grid.apply(self.shopper, "move_left"))
        self.assertEqual((self.shopper.state.x, self.shopper.state.y), start)
        self.assertFalse(self.shopper.trajectory[-1].success)

    def test_shopper_can_move_grab_and_checkout(self):
        requirement = self.shopper.state.requirements[0]
        product = self.grid.products[requirement.product_id]
        stand_cell = self.grid.stand_cells_for((product["x"], product["y"]))[0]

        self.shopper.state.x, self.shopper.state.y = stand_cell
        self.grid.refresh(self.shopper)
        self.assertTrue(self.grid.apply(self.shopper, "grab", requirement.product_id))
        self.assertEqual(self.shopper.state.cart[0].product_id, requirement.product_id)

        self.shopper.state.x, self.shopper.state.y = self.grid.checkout[0]
        self.assertTrue(self.grid.apply(self.shopper, "checkout"))
        self.assertIsInstance(self.shopper.state, CheckoutState)
        self.assertTrue(self.grid.apply(self.shopper, "checkout"))
        self.assertIsInstance(self.shopper.state, FinishedState)

    def test_observation_only_exposes_walkable_moves(self):
        observation = self.grid.observe(self.shopper)

        for step in observation.allowed_steps:
            if step.startswith("move_"):
                dx, dy = {
                    "move_left": (-1, 0),
                    "move_right": (1, 0),
                    "move_up": (0, -1),
                    "move_down": (0, 1),
                }[step]
                self.assertTrue(
                    self.grid.walkable(observation.x + dx, observation.y + dy)
                )

    def test_llm_decision_must_be_an_allowed_json_step(self):
        allowed = ("move_left", "grab")

        self.assertEqual(
            parse_decision('```json\n{"step": "grab", "product_id": "", "reason": ""}\n```', allowed),
            Decision("grab"),
        )
        self.assertIsNone(parse_decision('{"step": "checkout"}', allowed))
        self.assertIsNone(parse_decision("not json", allowed))

    def test_prompt_adapter_parses_gemini_response_with_injected_transport(self):
        allowed = ("move_left", "grab")

        with patch(
            "agents.llm.ask_gemini",
            return_value='{"step": "grab", "reason": "nearby"}',
        ) as ask:
            proposal = decide_prompt_with_gemini("choose a step", allowed)

        ask.assert_called_once_with("choose a step", allowed)
        self.assertEqual(
            proposal,
            ProposalResult(
                raw_response='{"step": "grab", "reason": "nearby"}',
                decision=Decision("grab", reason="nearby"),
            ),
        )

    def test_ask_gemini_raises_a_distinct_missing_key_error(self):
        with patch("agents.llm.load_env_file", return_value={}):
            with self.assertRaises(MissingGeminiApiKeyError):
                ask_gemini("choose a step")

    def test_finished_shopper_does_not_take_another_step(self):
        self.shopper.state = FinishedState(self.shopper.customer_id, 5, 6)

        self.assertFalse(auto_step(self.grid, self.shopper))
        self.assertEqual((self.shopper.state.x, self.shopper.state.y), (5, 6))

    def test_fast_shopper_commits_while_a_slower_peer_is_still_pending(self):
        shoppers = self.grid.spawn(instantiate_agents(count=2))
        first_observation = self.grid.observe(shoppers[0])
        first_prompt = shoppers[0].prompt(first_observation)
        first_step = first_observation.allowed_steps[0]
        second_step = self.grid.observe(shoppers[1]).allowed_steps[0]
        first_started = threading.Event()
        second_finished = threading.Event()
        release_first = threading.Event()
        round_finished = threading.Event()
        worker_inputs = []
        commits = []
        original_apply = self.grid.apply

        def record_apply(shopper, decision):
            commits.append(shopper)
            return original_apply(shopper, decision)

        def decide(prompt, allowed_steps):
            worker_inputs.append((prompt, allowed_steps))
            self.assertIsInstance(prompt, str)
            self.assertIsInstance(allowed_steps, tuple)
            if prompt == first_prompt:
                first_started.set()
                self.assertTrue(release_first.wait(timeout=2))
                return Decision(first_step)
            second_finished.set()
            return Decision(second_step)

        self.grid.apply = record_apply
        coordinator = RoundCoordinator(decide)

        first_applied = threading.Event()

        def run_round():
            coordinator.tick(self.grid, shoppers, wait_all=False)
            first_applied.set()
            self.assertTrue(release_first.wait(timeout=2))
            coordinator.settle(self.grid)
            round_finished.set()

        thread = threading.Thread(target=run_round)
        initial_states = [
            (shopper.state.x, shopper.state.y, shopper.step_count, tuple(shopper.trajectory))
            for shopper in shoppers
        ]
        thread.start()
        self.assertTrue(first_started.wait(timeout=2))
        self.assertTrue(second_finished.wait(timeout=2))
        self.assertTrue(first_applied.wait(timeout=2))
        self.assertFalse(round_finished.is_set())
        self.assertEqual(
            (shoppers[0].state.x, shoppers[0].state.y, shoppers[0].step_count),
            initial_states[0][:3],
        )
        self.assertEqual(shoppers[1].step_count, 1)

        release_first.set()
        thread.join(timeout=2)
        self.assertFalse(thread.is_alive())
        self.assertTrue(round_finished.is_set())
        self.assertEqual(commits, [shoppers[1], shoppers[0]])
        self.assertEqual([shopper.step_count for shopper in shoppers], [1, 1])
        self.assertEqual([len(shopper.trajectory) for shopper in shoppers], [1, 1])
        self.assertEqual(len(worker_inputs), 2)

    def test_round_reports_invalid_decision_without_applying_or_retrying(self):
        calls = []

        def decide(prompt, allowed_steps):
            calls.append((prompt, allowed_steps))
            return Decision("not_allowed")

        outcome = RoundCoordinator(decide).run(self.grid, [self.shopper])[0]

        self.assertEqual(outcome.shopper_id, self.shopper.customer_id)
        self.assertEqual(outcome.failure, "invalid decision")
        self.assertIsNone(outcome.applied)
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.shopper.step_count, 0)
        self.assertEqual(self.shopper.trajectory, [])

    def test_round_skips_shopper_after_its_turn_budget_is_exhausted(self):
        self.shopper = self.grid.spawn([
            Shopper(self.shopper.customer, turn_budget=1)
        ])[0]
        self.assertEqual(self.shopper.turn_budget, 1)
        calls = []

        def decide(prompt, allowed_steps):
            calls.append((prompt, allowed_steps))
            return Decision(allowed_steps[0])

        coordinator = RoundCoordinator(decide)
        first_outcomes = coordinator.run(self.grid, [self.shopper])
        second_outcomes = coordinator.run(self.grid, [self.shopper])

        self.assertEqual(len(first_outcomes), 1)
        self.assertEqual(second_outcomes, ())
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.shopper.turns_used, 1)
        self.assertTrue(self.shopper.out_of_turns)

    def test_invalid_and_failing_decisions_consume_turns(self):
        shoppers = self.grid.spawn(instantiate_agents(count=2))
        first_prompt = shoppers[0].prompt(self.grid.observe(shoppers[0]))

        def decide(prompt, allowed_steps):
            if prompt == first_prompt:
                return Decision("not_allowed")
            raise RuntimeError("temporary Gemini error")

        outcomes = RoundCoordinator(decide).run(self.grid, shoppers)

        self.assertEqual([outcome.failure for outcome in outcomes], [
            "invalid decision",
            "temporary Gemini error",
        ])
        self.assertEqual([shopper.turns_used for shopper in shoppers], [1, 1])
        self.assertEqual([shopper.out_of_turns for shopper in shoppers], [False, False])

    def test_fatal_configuration_failure_aborts_round_without_mutation(self):
        shoppers = self.grid.spawn(instantiate_agents(count=2))
        first_prompt = shoppers[0].prompt(self.grid.observe(shoppers[0]))
        second_started = threading.Event()
        release_second = threading.Event()
        finished = threading.Event()
        caught = []
        apply_calls = []
        original_apply = self.grid.apply

        def record_apply(shopper, decision):
            apply_calls.append((shopper, decision))
            return original_apply(shopper, decision)

        def decide(prompt, allowed_steps):
            if prompt == first_prompt:
                raise MissingGeminiApiKeyError("GEMINI_API_KEY is missing from .env")
            second_started.set()
            self.assertTrue(release_second.wait(timeout=2))
            return Decision(allowed_steps[0])

        def run_round():
            try:
                RoundCoordinator(decide, max_workers=2).run(self.grid, shoppers)
            except MissingGeminiApiKeyError as error:
                caught.append(error)
            finally:
                finished.set()

        self.grid.apply = record_apply
        thread = threading.Thread(target=run_round)
        thread.start()
        self.assertTrue(second_started.wait(timeout=2))
        self.assertFalse(finished.is_set())
        release_second.set()
        thread.join(timeout=2)

        self.assertFalse(thread.is_alive())
        self.assertTrue(finished.is_set())
        self.assertEqual(len(caught), 1)
        self.assertEqual(apply_calls, [])
        self.assertEqual([shopper.turns_used for shopper in shoppers], [0, 0])
        self.assertEqual([shopper.decision_history for shopper in shoppers], [(), ()])

    def test_shopper_decision_history_records_ordered_immutable_outcomes(self):
        def decide(prompt, allowed_steps):
            return Decision(allowed_steps[0])

        coordinator = RoundCoordinator(decide)
        first = coordinator.run(self.grid, [self.shopper])[0]
        second = coordinator.run(self.grid, [self.shopper])[0]

        self.assertEqual(self.shopper.decision_history, (first, second))
        self.assertEqual(
            [outcome.decision.step for outcome in self.shopper.decision_history],
            [first.decision.step, second.decision.step],
        )
        with self.assertRaises(AttributeError):
            self.shopper.decision_history.append(first)

    def test_round_coordinator_rejects_invalid_worker_limits(self):
        for max_workers in (0, -1, 1.5, "4", True):
            with self.subTest(max_workers=max_workers):
                with self.assertRaises(ValueError):
                    RoundCoordinator(lambda *_: None, max_workers=max_workers)

    def test_round_records_raw_response_for_invalid_json(self):
        def decide(prompt, allowed_steps):
            return ProposalResult(raw_response="not json", decision=None)

        outcome = RoundCoordinator(decide).run(self.grid, [self.shopper])[0]

        self.assertEqual(outcome.failure, "invalid decision")
        self.assertEqual(outcome.raw_response, "not json")
        self.assertEqual(self.shopper.decision_history[-1].raw_response, "not json")

    def test_propose_only_records_without_grid_mutation_or_turn_use(self):
        start = (self.shopper.state.x, self.shopper.state.y)
        apply_calls = []
        original_apply = self.grid.apply

        def record_apply(shopper, decision):
            apply_calls.append((shopper, decision))
            return original_apply(shopper, decision)

        def decide(prompt, allowed_steps):
            return ProposalResult(
                raw_response='{"step": "' + allowed_steps[0] + '", "reason": "test"}',
                decision=Decision(allowed_steps[0], reason="test"),
            )

        self.grid.apply = record_apply
        outcome = RoundCoordinator(decide).run(
            self.grid,
            [self.shopper],
            apply_decisions=False,
        )[0]

        self.assertEqual(outcome.decision.step, self.grid.observe(self.shopper).allowed_steps[0])
        self.assertIsNone(outcome.applied)
        self.assertEqual(apply_calls, [])
        self.assertEqual((self.shopper.state.x, self.shopper.state.y), start)
        self.assertEqual(self.shopper.trajectory, [])
        self.assertEqual(self.shopper.turns_used, 0)
        self.assertEqual(len(self.shopper.decision_history), 1)

    def test_decision_log_jsonl_round_trip(self):
        observation = self.grid.observe(self.shopper)
        proposal = ProposalResult(
            raw_response='{"step": "' + observation.allowed_steps[0] + '", "reason": "test"}',
            decision=Decision(observation.allowed_steps[0], reason="test"),
        )
        record = build_decision_record(
            self.shopper,
            observation,
            proposal,
            layout_id=self.grid.layout_name,
            prompt="prompt text",
            run_id="run-test",
        )
        with tempfile.TemporaryDirectory() as folder:
            path = write_jsonl(Path(folder) / "test_decisions.jsonl", [record])
            lines = path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(record["agent_id"], self.shopper.customer_id)
        self.assertEqual(record["observation"], observation_to_dict(observation))
        self.assertEqual(record["action"]["step"], observation.allowed_steps[0])
        self.assertEqual(record["llm"]["raw_response"], proposal.raw_response)

    def test_run_py_collects_one_record_per_agent_with_mocked_gemini(self):
        import run as decision_run

        grid = build_store()
        shoppers = grid.spawn(instantiate_all_agents())
        allowed = grid.observe(shoppers[0]).allowed_steps[0]

        def fake_decide(prompt, allowed_steps):
            step = allowed_steps[0]
            return ProposalResult(
                raw_response='{"step": "' + step + '", "reason": "mock"}',
                decision=Decision(step, reason="mock"),
            )

        with patch("run.decide_prompt_with_gemini", side_effect=fake_decide):
            records = decision_run.collect_decision_records(
                grid,
                shoppers,
                "run-mock",
                concurrency=1,
            )

        self.assertEqual(len(records), len(shoppers))
        self.assertTrue(all(row["run_id"] == "run-mock" for row in records))
        self.assertTrue(all(row["action"] is not None for row in records))

    def test_round_coordinator_uses_configured_worker_limit(self):
        shoppers = self.grid.spawn(instantiate_agents(count=5))

        def submit(decide, prompt, allowed_steps):
            future = Future()
            future.set_result(decide(prompt, allowed_steps))
            return future

        with patch("core.rounds.ThreadPoolExecutor") as executor_class:
            executor_class.return_value.submit.side_effect = submit
            RoundCoordinator(
                lambda prompt, allowed_steps: Decision(allowed_steps[0]),
                max_workers=2,
            ).run(self.grid, shoppers)

        executor_class.assert_called_once_with(max_workers=2)


if __name__ == "__main__":
    unittest.main()
