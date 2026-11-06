"""Formal entity, typed compute and causal observation acceptance tests."""
import copy
from dataclasses import FrozenInstanceError, asdict, fields, is_dataclass
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from replacement.core.entities import ModelSpec, SessionState, EdgeState, Phase, CommitResult
from replacement.core.runtime import RuntimeState
from replacement.simulation.events import EventQueue
from replacement.core.observation import observe
from replacement.simulation.s0 import S0Simulator


def model(name="m1", **changes):
    params = dict(model_id=name, layers=1, kv_heads=1, head_dim=1, element_bytes=2,
                  context_window_tokens=20, output_limit_per_turn=4,
                  prefill_work_per_token=1, decode_work_per_token=2)
    params.update(changes)
    return ModelSpec(**params)


class FoundationTests(unittest.TestCase):
    def setUp(self):
        self.queue = EventQueue()
        self.m1 = model()
        self.m2 = model("m2", layers=2, kv_heads=2, head_dim=3)
        self.edge = EdgeState("E1", 10, 1, 1000, frozenset({"m1", "m2"}), self.queue)
        self.runtime = RuntimeState({"m1": self.m1, "m2": self.m2}, {"E1": self.edge})

    def add(self, sid="s1", mid="m1"):
        session = SessionState(sid, mid, 0, "E1", "E1")
        self.runtime.add_session(session)
        return session

    def compute(self, session, phase=Phase.PREFILL):
        turn = session.current_turn
        if turn.phase == Phase.UPLOAD:
            self.runtime.input_arrived(session.session_id)
        unit = turn.prefill_done + 1 if phase == Phase.PREFILL else turn.decode_done + 1
        self.edge.compute.submit(session, turn, self.runtime.models[session.model_id], phase, unit,
                                 self.runtime.time_s)
        while self.queue:
            event = self.queue.pop()
            self.runtime.time_s = event.time
            self.edge.compute.handle_event(event)

    def test_a_sessions_bind_distinct_models_and_independent_state(self):
        a, b = self.add(), self.add("s2", "m2")
        self.runtime.submit_turn("s1", 1, 0)
        self.runtime.submit_turn("s2", 1, 0)
        self.compute(a)
        self.assertEqual(self.runtime.commit_token("s1"), CommitResult.COMMITTED)
        self.assertEqual((a.context_tokens, a.authoritative_kv_bytes), (1, 4))
        self.assertEqual((b.context_tokens, b.authoritative_kv_bytes), (0, 0))
        self.compute(b)
        self.runtime.commit_token("s2")
        self.assertEqual((b.context_tokens, b.authoritative_kv_bytes), (1, 48))
        self.assertEqual(self.edge.authoritative_kv_bytes, 52)
        with self.assertRaises(AttributeError):
            a.model_id = "m2"
        with self.assertRaises((AttributeError, TypeError)):
            a.priority = "H"

    def test_a_edge_resources_and_deployment_are_independent(self):
        other = EdgeState("E2", 30, 3, 7, frozenset({"m2"}), self.queue)
        self.runtime.edges["E2"] = other
        self.assertEqual((other.gpu_capacity, other.gpu_slots, other.kv_capacity_bytes), (30, 3, 7))
        with self.assertRaisesRegex(ValueError, "deployed"):
            self.runtime.add_session(SessionState("bad", "m1", 0, "E1", "E2"))
        session = SessionState("remote", "m2", 0, "E1", "E2")
        self.runtime.add_session(session)
        self.assertEqual((session.access_edge_id, session.execution_edge_id), ("E1", "E2"))

    def test_b_structural_kv_formula_and_validation(self):
        self.assertEqual(self.m1.kv_bytes_per_token, 4)
        self.assertEqual(self.m2.kv_bytes_per_token, 48)
        for field in ["layers", "kv_heads", "head_dim", "element_bytes", "context_window_tokens",
                      "output_limit_per_turn"]:
            for value in [0, -1, True, 1.5]:
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    model(**{field: value})
        for value in [0, -1, float("nan"), float("inf")]:
            with self.assertRaises(ValueError):
                model(prefill_work_per_token=value)
        with self.assertRaises(FrozenInstanceError):
            self.m1.layers = 20

    def test_c_compute_completion_is_not_token_commit_or_full_delivery(self):
        session = self.add()
        turn = self.runtime.submit_turn("s1", 1, 0)
        self.compute(session)
        task = turn.compute_task
        self.assertEqual((task.session_id, task.turn_index, task.phase, task.unit_index,
                          task.execution_edge_id, task.remaining_work),
                         ("s1", 1, Phase.PREFILL, 1, "E1", 0))
        self.assertEqual((session.context_tokens, turn.prefill_done), (0, 0))
        self.assertIsNone(turn.received_at)
        self.runtime.commit_token("s1")
        with self.assertRaises(RuntimeError):
            self.runtime.commit_token("s1")
        self.compute(session, Phase.DECODE)
        self.runtime.commit_token("s1")
        turn.generation_complete = True
        with self.assertRaises(RuntimeError):
            self.runtime.finish_turn("s1", self.runtime.time_s)
        self.runtime.deliver_token("s1", token_id=session.current_turn.output_tokens[0].token_id)
        self.runtime.finish_turn("s1", self.runtime.time_s)
        self.runtime.submit_turn("s1", 1, self.runtime.time_s)
        self.assertEqual(session.context_tokens, 2)
        self.assertEqual(session.current_turn.index, 2)
        self.assertEqual(session.authoritative_kv_bytes, 8)

    def test_c_typed_tasks_reuse_fcfs_and_have_unique_ownership(self):
        a, b = self.add(), self.add("s2", "m2")
        ta = self.runtime.submit_turn("s1", 1, 0)
        tb = self.runtime.submit_turn("s2", 1, 0)
        self.runtime.input_arrived("s1")
        self.runtime.input_arrived("s2")
        self.edge.compute.submit(a, ta, self.m1, Phase.PREFILL, 1, 0)
        self.edge.compute.submit(b, tb, self.m2, Phase.PREFILL, 1, 0)
        self.assertEqual([t.session_id for t in self.edge.running_tasks], ["s1"])
        self.assertEqual([t.session_id for t in self.edge.ready_queue], ["s2"])
        self.assertEqual(tb.remaining_gpu_work, 1)
        self.assertIsNone(tb.gpu_start_time)
        self.assertEqual(self.edge.authoritative_kv_bytes, 0)
        while self.queue:
            event = self.queue.pop()
            self.edge.compute.handle_event(event)
        self.assertEqual(tb.gpu_start_time, 0.1)
        self.assertEqual(tb.compute_task.completion_time, 0.2)
        with self.assertRaises(ValueError):
            self.edge.compute.submit(a, tb, self.m1, Phase.PREFILL, 1, 0.2)

    def test_d_observation_is_detached_readonly_whitelist(self):
        self.add()
        self.runtime.submit_turn("s1", 1, 0)
        snapshot = observe(self.runtime)
        encoded = asdict(snapshot)
        banned = {"config", "plan", "driver", "turns", "output_tokens", "planned_turns",
                  "remaining_turns", "predicted_completion_s", "priority", "queue", "simulator"}
        def audit(value):
            if isinstance(value, dict):
                self.assertFalse(banned.intersection(value))
                for child in value.values():
                    audit(child)
            elif isinstance(value, (tuple, list)):
                for child in value:
                    audit(child)
            else:
                self.assertIsInstance(value, (str, int, float, bool, type(None)))
        audit(encoded)
        json.dumps(encoded)
        with self.assertRaises(FrozenInstanceError):
            snapshot.time_s = 1
        with self.assertRaises(FrozenInstanceError):
            snapshot.sessions[0].context_tokens = 100
        self.runtime.sessions["s1"].context_tokens = 3
        self.assertEqual(snapshot.sessions[0].context_tokens, 0)

    def test_d_same_history_different_future_has_identical_observation_and_decisions(self):
        base = json.loads((ROOT / "configs/s0_smoke.json").read_text(encoding="utf-8"))
        changed = copy.deepcopy(base)
        changed["session"]["turns"][0]["output_tokens"] = 4
        changed["session"]["turns"][1] = {"input_tokens": 100, "output_tokens": 50}
        changed["session"]["turns"].append({"input_tokens": 999, "output_tokens": 99})
        a, b = S0Simulator(base), S0Simulator(changed)
        for _ in range(4):
            self.assertEqual(a.observation(), b.observation())
            self.assertEqual(a.step(), b.step())
        self.assertEqual(a.observation(), b.observation())
        self.assertEqual(a.edge.compute.scheduler.rates, b.edge.compute.scheduler.rates)
        self.assertFalse(hasattr(a, "config"))
        before = a.observation()
        base["session"]["turns"][0]["output_tokens"] = 999
        self.assertEqual(before, a.observation())

    def test_e_no_service_priority_in_entities_or_current_config(self):
        cfg = json.loads((ROOT / "configs/s0_smoke.json").read_text(encoding="utf-8"))
        self.assertNotIn("priority", cfg["session"])
        self.assertNotIn("priority", {f.name for f in fields(SessionState)})
        self.assertEqual(S0Simulator(cfg).run()[0]["completed_turns"], 2)

    def test_runtime_token_guard_is_atomic_and_retains_blocked_work(self):
        session = self.add()
        self.edge.kv_capacity_bytes = 0
        turn = self.runtime.submit_turn("s1", 1, 0)
        self.compute(session)
        self.assertEqual(self.runtime.commit_token("s1"), CommitResult.KV_BLOCKED)
        self.assertEqual((session.context_tokens, session.authoritative_kv_bytes, turn.prefill_done), (0, 0, 0))
        self.assertEqual(turn.partial_work, 1)
        self.assertEqual(turn.remaining_gpu_work, 0)
        self.assertEqual(self.edge.running_tasks, ())

    def test_session_arrival_and_single_current_turn_guards(self):
        with self.assertRaises(ValueError):
            self.runtime.add_session(SessionState("future", "m1", 5, "E1", "E1"))
        self.add()
        self.runtime.submit_turn("s1", 1, 0)
        with self.assertRaises(RuntimeError):
            self.runtime.submit_turn("s1", 1, 0)

    def test_context_failure_not_success_and_output_limit_is_per_turn(self):
        cfg = json.loads((ROOT / "configs/s0_smoke.json").read_text(encoding="utf-8"))
        cfg["model"]["context_window_tokens"] = 5
        summary, turns, _ = S0Simulator(cfg).run()
        self.assertEqual(summary["completed_turns"], 1)
        self.assertIsNone(summary["mean_full_turn_e2e_s"])
        self.assertEqual(summary["termination_reason"], "ContextLimit")
        cfg["model"]["context_window_tokens"] = 20
        cfg["model"]["output_limit_per_turn"] = 1
        cfg["session"]["turns"][0]["output_tokens"] = 99
        summary, turns, _ = S0Simulator(cfg).run()
        self.assertEqual(summary["completed_turns"], 2)
        self.assertEqual(turns[0]["output_tokens"], 1)

    def test_compute_requires_arrived_input_and_cannot_repeat_committed_unit(self):
        s = self.add()
        t = self.runtime.submit_turn("s1", 1, 0)
        with self.assertRaises(ValueError):
            self.edge.compute.submit(s, t, self.m1, Phase.PREFILL, 1, 0)
        self.runtime.input_arrived("s1")
        self.compute(s)
        self.runtime.commit_token("s1")
        with self.assertRaises(ValueError):
            self.edge.compute.submit(s, t, self.m1, Phase.PREFILL, 1, self.runtime.time_s)

    def test_arrival_visibility_and_release_share_one_authoritative_state(self):
        cfg = json.loads((ROOT / "configs/s0_smoke.json").read_text(encoding="utf-8"))
        cfg["session"]["arrival_time"] = 5
        sim = S0Simulator(cfg)
        self.assertEqual(sim.observation().sessions, ())
        self.assertEqual(sim.edge.resident_session_ids, ())
        sim.step()
        self.assertEqual(sim.observation().sessions[0].arrival_time, 5)
        summary, _, _ = sim.run()
        self.assertAlmostEqual(summary["mean_full_turn_e2e_s"], 0.7)
        self.assertEqual(sim.edge.resident_session_ids, ())
        self.assertEqual(sim.edge.authoritative_kv_bytes, 0)
        self.assertEqual(sim.session.context_tokens, 6)
        self.assertEqual(len(sim.session.turns), 2)

    def test_context_exhaustion_during_prefill_never_creates_legal_zero_reply(self):
        cfg = json.loads((ROOT / "configs/s0_smoke.json").read_text(encoding="utf-8"))
        cfg["model"]["context_window_tokens"] = 1
        sim = S0Simulator(cfg)
        summary, turns, _ = sim.run()
        self.assertEqual(summary["completed_turns"], 0)
        self.assertEqual(summary["termination_reason"], "ContextLimit")
        self.assertEqual(sim.active_turn.prefill_done, 1)
        self.assertIsNone(sim.active_turn.received_at)
        self.assertEqual(turns, [])
        self.assertEqual(sim.edge.authoritative_kv_bytes, 0)

    def test_context_exhaustion_drains_already_generated_response_before_cleanup(self):
        cfg = json.loads((ROOT / "configs/s0_smoke.json").read_text(encoding="utf-8"))
        cfg["model"]["context_window_tokens"] = 3
        cfg["session"]["turns"] = [{"input_tokens": 2, "output_tokens": 2}]
        cfg["network"]["wireless_down_bits_per_second"] = 8
        sim = S0Simulator(cfg)
        summary, turns, events = sim.run()
        self.assertEqual(summary["completed_turns"], 0)
        self.assertEqual(sim.active_turn.decode_done, 1)
        self.assertEqual(sim.active_turn.delivered, 1)
        self.assertEqual(turns[0]["status"], "failed")
        delivered = next(e["time_s"] for e in events if e["event"] == "downlink_done")
        released = next(e["time_s"] for e in events if e["event"] == "kv_release")
        self.assertEqual(delivered, released)

    def test_legacy_service_priority_is_rejected_as_removed_schema(self):
        cfg = json.loads((ROOT / "configs/s0_smoke.json").read_text(encoding="utf-8"))
        cfg["session"]["priority"] = "H"
        with self.assertRaisesRegex(ValueError, "removed"):
            S0Simulator(cfg)

    def test_observation_settles_current_unit_at_interleaved_delivery_event(self):
        cfg = json.loads((ROOT / "configs/s0_smoke.json").read_text(encoding="utf-8"))
        cfg["session"]["turns"] = [{"input_tokens": 1, "output_tokens": 3}]
        sim = S0Simulator(cfg)
        while sim.time < 0.5:
            sim.step()
        task = sim.observation().edges[0].running[0]
        self.assertEqual((task.remaining_work, task.consumed_work), (1, 1))
        self.assertEqual(sim.observation().sessions[0].current_turn.partial_work, 1)

    def test_compute_cannot_override_canonical_model_with_same_id(self):
        session = self.add()
        turn = self.runtime.submit_turn("s1", 1, 0)
        self.runtime.input_arrived("s1")
        forged = model(prefill_work_per_token=100)
        with self.assertRaises(ValueError):
            self.edge.compute.submit(session, turn, forged, Phase.PREFILL, 1, 0)
        self.assertEqual(self.edge.compute.tasks, {})
        self.assertIsNone(turn.compute_task)
        with self.assertRaises(TypeError):
            self.runtime.models["m1"] = forged

    def test_compute_ready_clock_must_match_runtime_after_turn_submission(self):
        session = self.add()
        self.runtime.time_s = 5
        turn = self.runtime.submit_turn("s1", 1, 5)
        self.runtime.input_arrived("s1")
        for time in [0, 4, 6]:
            with self.subTest(time=time), self.assertRaises(ValueError):
                self.edge.compute.submit(session, turn, self.m1, Phase.PREFILL, 1, time)
            self.assertEqual(self.edge.compute.tasks, {})
            self.assertIsNone(turn.compute_task)
        self.edge.compute.submit(session, turn, self.m1, Phase.PREFILL, 1, 5)
        self.assertEqual(turn.gpu_ready_time, 5)
