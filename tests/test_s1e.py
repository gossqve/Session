"""S1-E provenance and ownership contracts through actual serving/runtime paths."""
import copy
from dataclasses import FrozenInstanceError, asdict, fields
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from replacement.simulation.serving import ServingSimulator
from replacement.core.workload import TurnPlan
from replacement.core.entities import Phase
from test_serving import config


def single(*, inputs=1, outputs=3, text_bytes=1, capacity=256):
    c = config(capacity=capacity)
    c["sessions"] = c["sessions"][:1]
    c["sessions"][0]["turns"] = [{"input_tokens": inputs, "output_tokens": outputs}]
    c["network"]["text_bytes_per_token"] = text_bytes
    return c


class S1EEntityTests(unittest.TestCase):
    def test_area_config_is_static_and_legacy_unspecified_is_explicit(self):
        c = config()
        c["edges"][0]["area_id"] = "Area-A"
        sim = ServingSimulator(c)
        sim.run()
        edge = sim.runtime.edges["E"]
        self.assertEqual(getattr(edge, "area_id", None), "Area-A")
        self.assertEqual(sim.observation().edges[0].area_id, "Area-A")
        with self.assertRaises(AttributeError):
            edge.area_id = "Area-B"
        old = ServingSimulator(config())
        self.assertIsNone(old.runtime.edges["E"].area_id)
        self.assertEqual(old.run()["summary"]["mean_full_turn_e2e_s"], 0.5)

    def test_invalid_explicit_area_rejected_before_serving(self):
        for value in ("", " ", 1, False):
            c = config()
            c["edges"][0]["area_id"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                ServingSimulator(c)

    def test_initial_current_and_turn_submission_access_are_distinct(self):
        c = single(outputs=1)
        second = copy.deepcopy(c["edges"][0])
        second["id"] = "E2"
        c["edges"].append(second)
        sim = ServingSimulator(c)
        sim.advance_to(0.2)
        session = sim.runtime.sessions["S1"]
        self.assertEqual(getattr(session, "initial_access_edge_id", None), "E")
        self.assertEqual(session.current_turn.submitted_access_edge_id, "E")
        # Execution-owned field update only: this is NOT a simulated Handover.
        session.access_edge_id = "E2"
        self.assertEqual(session.initial_access_edge_id, "E")
        self.assertEqual(session.current_turn.submitted_access_edge_id, "E")
        self.assertEqual(sim.observation().sessions[0].access_edge_id, "E2")
        self.assertEqual(session.execution_edge_id, "E")
        with self.assertRaises(AttributeError):
            session.initial_access_edge_id = "E2"

    def test_turn_workload_contains_no_formal_access_or_mobility(self):
        self.assertEqual({f.name for f in fields(TurnPlan)}, {"input_tokens", "hidden_output_tokens"})
        self.assertEqual(TurnPlan(1, 2).input_tokens, 1)

    def test_per_turn_access_is_rejected_for_all_turns(self):
        for index in (0, 1):
            c = single(outputs=1)
            c["sessions"][0]["turns"] *= 2
            c["sessions"][0]["turns"][index] = dict(c["sessions"][0]["turns"][index], access_edge_id="E")
            with self.subTest(index=index), self.assertRaises(ValueError):
                ServingSimulator(c)


class S1ETokenTests(unittest.TestCase):
    def test_decode_records_unique_ids_and_real_generation_times(self):
        sim = ServingSimulator(single())
        sim.run()
        turn = sim.runtime.sessions["S1"].current_turn
        self.assertEqual(len(getattr(turn, "output_tokens", ())), 3)
        self.assertEqual([t.token_id for t in turn.output_tokens], [("S1", 1, 1), ("S1", 1, 2), ("S1", 1, 3)])
        self.assertEqual([t.generated_at for t in turn.output_tokens], [0.3, 0.4, 0.5])
        self.assertEqual([(t.execution_edge_id, t.access_edge_id) for t in turn.output_tokens], [("E", "E")] * 3)

    def test_generation_provenance_is_frozen_after_current_access_changes(self):
        sim = ServingSimulator(single())
        sim.advance_to(0.3)
        session = sim.runtime.sessions["S1"]
        self.assertEqual(len(getattr(session.current_turn, "output_tokens", ())), 1)
        token = session.current_turn.output_tokens[0]
        session.access_edge_id = "future-current"
        self.assertEqual((token.execution_edge_id, token.access_edge_id), ("E", "E"))
        with self.assertRaises(FrozenInstanceError):
            token.access_edge_id = "future-current"
        self.assertIsInstance(session.current_turn.output_tokens, tuple)

    def test_runtime_commit_snapshots_actual_access_independent_of_execution(self):
        c = single(inputs=0, outputs=1)
        second = copy.deepcopy(c["edges"][0])
        second["id"] = "E2"
        c["edges"].append(second)
        sim = ServingSimulator(c)
        sim.advance_to(0)
        session = sim.runtime.sessions["S1"]
        task = session.current_turn.compute_task
        # Component integration below exercises commit, not a Mobility executor.
        session.access_edge_id = "E2"
        sim.runtime.time_s = 0.1
        sim.runtime.edges["E"].compute.advance(0.1)
        sim.runtime.commit_token("S1")
        self.assertEqual(len(getattr(session.current_turn, "output_tokens", ())), 1)
        token = session.current_turn.output_tokens[0]
        self.assertEqual((token.generated_at, token.execution_edge_id, token.access_edge_id), (0.1, "E", "E2"))
        self.assertEqual(session.authoritative_kv_bytes, 4)
        self.assertEqual(task.consumed_work, 1)

    def test_incomplete_compute_and_blocked_commit_never_publish_output(self):
        sim = ServingSimulator(single(inputs=0, outputs=3, capacity=4))
        sim.advance_to(0.05)
        turn = sim.runtime.sessions["S1"].current_turn
        self.assertEqual(getattr(turn, "output_tokens", None), ())
        sim.advance_to(0.2)
        self.assertEqual(turn.status, "blocked")
        self.assertEqual((turn.decode_done, len(turn.output_tokens)), (1, 1))
        self.assertEqual(turn.output_tokens[0].token_id, ("S1", 1, 1))
        out = sim.run()
        self.assertIsNone(out["summary"]["mean_full_turn_e2e_s"])
        self.assertEqual(len(out["output_tokens"]), 1)

    def test_recovered_token_published_once_at_legal_commit_time(self):
        c = json.loads((ROOT / "configs/s1d_recover.json").read_text(encoding="utf8"))
        sim = ServingSimulator(c)
        sim.advance_to(0.7)
        turn = sim.runtime.sessions["S1"].current_turn
        self.assertEqual(turn.pending_commit.phase, Phase.DECODE)
        self.assertEqual(getattr(turn, "output_tokens", None), ())
        out = sim.run()
        token = turn.output_tokens[0]
        self.assertEqual((token.token_id, token.generated_at), (("S1", 1, 1), 3.1))
        self.assertEqual(len(turn.output_tokens), 1)
        self.assertEqual(out["summary"]["gpu_work"], 8)

    def test_fifo_exactly_once_delivery_uses_same_token_identity(self):
        c = single()
        c["network"]["wireless_down_bits_per_second"] = 8
        sim = ServingSimulator(c)
        out = sim.run()
        self.assertIn("output_tokens", out)
        self.assertEqual([r["received_at"] for r in out["output_tokens"]], [1.3, 2.3, 3.3])
        delivered = [e for e in out["events"] if e["event"] == "downlink_done"]
        self.assertEqual([tuple(e["token_id"]) for e in delivered], [("S1", 1, 1), ("S1", 1, 2), ("S1", 1, 3)])
        with self.assertRaises(RuntimeError):
            sim.runtime.deliver_token("S1", token_id=("S1", 1, 3))
        self.assertEqual(sim.runtime.sessions["S1"].current_turn.delivered, 3)
        self.assertEqual(out["turns"][0]["e2e_s"], 3.3)

    def test_delivery_rejects_wrong_identity_before_counter_mutation(self):
        sim = ServingSimulator(single())
        sim.advance_to(0.3)
        turn = sim.runtime.sessions["S1"].current_turn
        self.assertEqual(len(getattr(turn, "output_tokens", ())), 1)
        for token_id in (("S1", 1, 2), ("S2", 1, 1), ("S1", 2, 1)):
            with self.subTest(token_id=token_id), self.assertRaises(RuntimeError):
                sim.runtime.deliver_token("S1", token_id=token_id)
        self.assertEqual(turn.delivered, 0)

    def test_text_bytes_are_independent_of_structural_kv(self):
        sim = ServingSimulator(single(inputs=1, outputs=2, text_bytes=3))
        out = sim.run()
        self.assertIn("output_tokens", out)
        self.assertEqual([t["text_bytes"] for t in out["output_tokens"]], [3, 3])
        self.assertEqual(out["turns"][0]["authoritative_kv_bytes"], 12)
        self.assertEqual(out["summary"]["peak_kv_bytes"], 12)
        self.assertEqual(out["turns"][0]["e2e_s"], 1.1)

    def test_context_limit_only_preserves_already_legal_output(self):
        c = single()
        c["models"][0]["context_window_tokens"] = 2
        out = ServingSimulator(c).run()
        self.assertIn("output_tokens", out)
        self.assertEqual(len(out["output_tokens"]), 1)
        self.assertEqual(out["output_tokens"][0]["output_index"], 1)
        self.assertEqual(out["summary"]["completed_turns"], 0)

    def test_multiturn_ids_zero_idle_and_snapshot_rows(self):
        c = single(outputs=1)
        c["sessions"][0]["turns"] *= 2
        out = ServingSimulator(c).run()
        self.assertIn("output_tokens", out)
        self.assertEqual([tuple(t["token_id"]) for t in out["output_tokens"]], [("S1", 1, 1), ("S1", 2, 1)])
        self.assertEqual(out["turns"][1]["submitted_at"], out["turns"][0]["received_at"])
        self.assertEqual([r["submitted_access_edge_id"] for r in out["turns"]], ["E", "E"])

    def test_future_mobility_output_and_turns_do_not_change_history(self):
        c = single(outputs=3)
        changed = copy.deepcopy(c)
        changed["sessions"][0]["turns"][0]["output_tokens"] = 8
        changed["sessions"][0]["turns"].append({"input_tokens": 999, "output_tokens": 999})
        # Reserved unsupported config is private input, never scheduled/read as Mobility.
        changed["mobility"] = {"seed": 999, "future_access": ["unrevealed"]}
        a, b = ServingSimulator(c), ServingSimulator(changed)
        a.advance_to(0.3)
        b.advance_to(0.3)
        self.assertEqual(a.observation(), b.observation())
        self.assertEqual(a.events, b.events)
        self.assertEqual(a.runtime.edges["E"].compute.scheduler.rates, b.runtime.edges["E"].compute.scheduler.rates)
        self.assertEqual(a.runtime.edges["E"].kv.trace, b.runtime.edges["E"].kv.trace)
        self.assertEqual(len(getattr(a.runtime.sessions["S1"].current_turn, "output_tokens", ())), 1)
        encoded = str(asdict(b.observation()))
        for banned in ("future_access", "mobility", "driver", "hidden_output_tokens", "unrevealed"):
            self.assertNotIn(banned, encoded)

