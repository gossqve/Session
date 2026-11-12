"""Current schema and explicit delivery acceptance through real executors."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from replacement.simulation.serving import ServingSimulator
from replacement.simulation.s0 import S0Simulator
from test_serving import config

class CleanupTests(unittest.TestCase):
    def test_turn_access_rejected_even_when_equal_to_initial(self):
        for access in ("E", "future-edge", None):
            c = config()
            c["sessions"][0]["turns"][0]["access_edge_id"] = access
            with self.subTest(access=access), self.assertRaises(ValueError):
                ServingSimulator(c)

    def test_s0_future_turn_access_rejected_at_loading(self):
        c = json.loads((ROOT / "configs/s0_smoke.json").read_text(encoding="utf8"))
        c["session"]["turns"][-1]["access_edge_id"] = c["session"]["access_edge_id"]
        with self.assertRaises(ValueError):
            S0Simulator(c)

    def test_delivery_requires_explicit_nonnull_identity_without_mutation(self):
        sim = ServingSimulator(config())
        sim.advance_to(0.3)
        turn = sim.runtime.sessions["S1"].current_turn
        with self.assertRaises(TypeError):
            sim.runtime.deliver_token("S1")
        with self.assertRaises(RuntimeError):
            sim.runtime.deliver_token("S1", token_id=None)
        self.assertEqual(turn.delivered, 0)
        sim.run()
        self.assertEqual(turn.delivered, 1)

    def test_turn_result_has_only_unambiguous_submission_access(self):
        out = ServingSimulator(config()).run()
        self.assertNotIn("access_edge_id", out["turns"][0])
        self.assertEqual(out["turns"][0]["submitted_access_edge_id"], "E")
        self.assertEqual(out["sessions"][0]["access_edge_id"], "E")
        self.assertEqual(out["output_tokens"][0]["access_edge_id"], "E")

    def test_rejected_turnplan_access_argument(self):
        from replacement.core.workload import TurnPlan
        with self.assertRaises(TypeError):
            TurnPlan(1, 1, "E")

    def test_repeated_commit_does_not_duplicate_output_identity(self):
        sim = ServingSimulator(config())
        sim.advance_to(0.3)
        turn = sim.runtime.sessions["S1"].current_turn
        before = turn.output_tokens
        with self.assertRaises(RuntimeError):
            sim.runtime.commit_token("S1")
        self.assertEqual(turn.output_tokens, before)
        self.assertEqual(len(before), 1)

    def test_future_arrival_access_does_not_change_prefix(self):
        c = config()
        second = copy.deepcopy(c["edges"][0])
        second["id"] = "E2"
        c["edges"].append(second)
        future = copy.deepcopy(c["sessions"][0])
        future.update(id="future", arrival_time=5)
        c["sessions"].append(future)
        changed = copy.deepcopy(c)
        changed["sessions"][-1].update(access_edge_id="E2", execution_edge_id="E2")
        a, b = ServingSimulator(c), ServingSimulator(changed)
        a.advance_to(0.25)
        b.advance_to(0.25)
        self.assertEqual(a.observation(), b.observation())
        self.assertEqual(a.events, b.events)
        for key in ("E", "E2"):
            self.assertEqual(a.runtime.edges[key].kv.trace, b.runtime.edges[key].kv.trace)
            self.assertEqual(a.runtime.edges[key].compute.scheduler.gpu_trace,
                             b.runtime.edges[key].compute.scheduler.gpu_trace)
