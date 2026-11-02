"""Protect the LLM-first execution contract without contacting a real provider."""

from contextlib import redirect_stderr, redirect_stdout
import gzip
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SIMULATION_DIR = Path(__file__).resolve().parents[1]
if str(SIMULATION_DIR) not in sys.path:
    sys.path.insert(0, str(SIMULATION_DIR))

from agents.llm import MODEL
from agents.providers import FakeDecisionProvider
from core.run_log import read_run
from run_llm_simulation import main, run


class LLMWorkflowTests(unittest.TestCase):
    def test_default_full_trip_reaches_gemini_transport_for_each_shopper(self):
        raw = json.dumps({"step": "move_left", "reason": "Mocked Gemini output"})
        response = json.dumps({"candidates": [{"content": {"parts": [{"text": raw}]}}]}).encode()
        with tempfile.TemporaryDirectory() as folder:
            with patch("agents.llm.load_env_file", return_value={"GEMINI_API_KEY": "unit-test-key"}), \
                 patch("urllib.request.urlopen", side_effect=lambda *args, **kwargs: io.BytesIO(response)) as transport, \
                 redirect_stdout(io.StringIO()):
                path = run("costco_back_anchor", 3, 1, output_path=Path(folder) / "gemini.jsonl", ledger_path=Path(folder) / "ledger.sqlite3", requests_per_minute=0)
            saved = read_run(path)
            self.assertEqual(transport.call_count, 3)
            self.assertEqual(saved["start"]["provider"], "gemini")
            self.assertEqual(saved["start"]["model"], MODEL)
            self.assertTrue(all(event["raw_response"] == raw for event in saved["events"]))
            self.assertTrue(all(event["outcome"] == "applied" for event in saved["events"]))
            for call in transport.call_args_list:
                request = call.args[0]
                self.assertIn(f"/models/{MODEL}:generateContent", request.full_url)
                body = json.loads(request.data)
                self.assertEqual(body["generationConfig"]["responseMimeType"], "application/json")
                self.assertIn("Current state:", body["contents"][0]["parts"][0]["text"])

    def test_route_policy_is_not_an_active_cli_provider(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            main(["--provider", "learned"])
        self.assertEqual(caught.exception.code, 2)

    def test_offline_trace_retains_provider_identity_telemetry_and_gzip_replay(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")) as transport, \
                 redirect_stdout(io.StringIO()):
                path = run("costco_back_anchor", 3, 2, decide=FakeDecisionProvider(),
                           output_path=Path(folder) / "fixture.jsonl")
            transport.assert_not_called()
            saved = read_run(path)
            self.assertEqual(saved["start"]["provider"], "fake")
            for event in saved["events"]:
                self.assertGreaterEqual(event["telemetry"]["provider_latency_ms"], 0)
                self.assertEqual(event["telemetry"]["prompt_bytes"], len(event["prompt"].encode()))
            compressed = path.with_suffix(".jsonl.gz")
            with gzip.open(compressed, "wb") as handle:
                handle.write(path.read_bytes())
            self.assertEqual(read_run(compressed), saved)


if __name__ == "__main__":
    unittest.main()
