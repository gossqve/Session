"""Stdlib unittest tests: no pip install needed on an SSH server."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from replacement.simulation.events import EventQueue  # noqa: E402
from replacement.simulation.s0 import S0Simulator  # noqa: E402

BASE = json.loads((ROOT / "configs/s0_smoke.json").read_text(encoding="utf-8"))


class S0Tests(unittest.TestCase):
    def test_two_turn_hand_calculation_and_zero_idle(self):
        summary, turns, events = S0Simulator(copy.deepcopy(BASE)).run()
        self.assertEqual(summary["completed_turns"], 2)
        self.assertEqual(summary["completion_rate"], 1)
        self.assertAlmostEqual(turns[0]["e2e_s"], 0.7)
        self.assertAlmostEqual(turns[1]["e2e_s"], 0.7)
        self.assertAlmostEqual(turns[1]["submitted_at_s"], turns[0]["received_at_s"])
        self.assertAlmostEqual(summary["mean_full_turn_e2e_s"], 0.7)
        self.assertEqual(summary["final_context_tokens"], 6)
        self.assertEqual(summary["peak_authoritative_kv_bytes"], 24)
        self.assertEqual(summary["released_authoritative_kv_bytes"], 0)
        self.assertEqual(len([e for e in events if e["event"] == "kv_commit"]), 6)

    def test_deterministic_trace(self):
        a = S0Simulator(copy.deepcopy(BASE)).run()
        b = S0Simulator(copy.deepcopy(BASE)).run()
        self.assertEqual(a, b)

    def test_completion_waits_for_output_delivery(self):
        cfg = copy.deepcopy(BASE)
        cfg["session"]["turns"] = [{"input_tokens": 1, "output_tokens": 2}]
        cfg["network"]["wireless_down_bits_per_second"] = 8.0  # 1 second per token
        summary, turns, events = S0Simulator(cfg).run()
        self.assertEqual(summary["completed_turns"], 1)
        generated = [e for e in events if e["event"] == "decode_token_done"]
        received = [e for e in events if e["event"] == "downlink_done"]
        self.assertEqual(len(generated), 2)
        self.assertEqual(len(received), 2)
        self.assertGreater(received[0]["time_s"], generated[-1]["time_s"])
        self.assertEqual(turns[0]["received_at_s"], received[-1]["time_s"])
        self.assertGreater(turns[0]["received_at_s"], generated[-1]["time_s"])

    def test_zero_output_turn(self):
        cfg = copy.deepcopy(BASE)
        cfg["session"]["turns"] = [{"input_tokens": 2, "output_tokens": 0}]
        summary, turns, events = S0Simulator(cfg).run()
        self.assertAlmostEqual(turns[0]["e2e_s"], 0.4)
        self.assertEqual(summary["final_context_tokens"], 2)
        self.assertFalse(any(e["event"] == "downlink_start" for e in events))

    def test_unsafe_capacity_rejected_without_fake_success(self):
        cfg = copy.deepcopy(BASE)
        cfg["edge"]["kv_capacity_bytes"] = 20
        simulator = S0Simulator(cfg)  # future KV demand no longer rejects arrival
        summary, turns, events = simulator.run()
        self.assertEqual(summary["completed_turns"], 1)
        self.assertEqual(summary["termination_reason"], "KVBlocked")
        self.assertIsNone(summary["mean_full_turn_e2e_s"])
        self.assertEqual(summary["final_context_tokens"], 5)
        self.assertEqual(summary["released_authoritative_kv_bytes"], 20)
        self.assertEqual(simulator.active_turn.partial_work, 2)
        self.assertEqual(simulator.active_turn.decode_done, 0)
        self.assertEqual(simulator.edge.running_tasks, ())
        self.assertTrue(any(e["event"] == "kv_blocked" for e in events))

    def test_context_window_is_across_all_turns(self):
        cfg = copy.deepcopy(BASE)
        cfg["model"]["context_window_tokens"] = 5
        summary, turns, events = S0Simulator(cfg).run()
        self.assertEqual(summary["completed_turns"], 1)
        self.assertEqual(summary["termination_reason"], "ContextLimit")
        self.assertIsNone(summary["mean_full_turn_e2e_s"])
        self.assertEqual(summary["final_context_tokens"], 5)
        self.assertEqual(summary["peak_authoritative_kv_bytes"], 20)
        self.assertEqual(summary["released_authoritative_kv_bytes"], 0)
        self.assertTrue(any(e["event"] == "context_limit" for e in events))

    def test_stable_event_order_same_time(self):
        q = EventQueue()
        q.schedule(1, "later", priority=50)
        q.schedule(1, "first", priority=10)
        q.schedule(1, "also_later", priority=50)
        self.assertEqual([q.pop().kind for _ in range(3)], ["first", "later", "also_later"])


if __name__ == "__main__":
    unittest.main()
