"""S1-C real-entity KV/resource/event acceptance tests (A-I)."""
from dataclasses import asdict
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from replacement.core.entities import ModelSpec, SessionState, EdgeState, Phase, CommitResult
from replacement.core.runtime import RuntimeState
from replacement.core.observation import observe
from replacement.simulation.events import EventQueue
from replacement.resources.kv import KVResource, TokenCommitted


class KVTests(unittest.TestCase):
    def setUp(self):
        self.events = EventQueue()
        self.m4 = ModelSpec("m4", 1, 1, 1, 2, 100, 4, 1, 2)
        self.m8 = ModelSpec("m8", 1, 1, 1, 4, 100, 4, 1, 2)
        self.edge = EdgeState("E1", 10, 1, 12, frozenset({"m4", "m8"}), self.events)
        self.other = EdgeState("E2", 20, 2, 100, frozenset({"m4", "m8"}), self.events)
        self.runtime = RuntimeState({"m4": self.m4, "m8": self.m8}, {"E1": self.edge, "E2": self.other})

    def add(self, sid, inputs=1, model="m4", edge="E1"):
        s = SessionState(sid, model, self.runtime.time_s, edge, edge)
        self.runtime.add_session(s)
        self.runtime.submit_turn(sid, inputs, self.runtime.time_s)
        self.runtime.input_arrived(sid)
        return s

    def submit(self, s, phase=Phase.PREFILL):
        t = s.current_turn
        unit = t.prefill_done + 1 if phase == Phase.PREFILL else t.decode_done + 1
        self.runtime.edges[s.execution_edge_id].compute.submit(
            s, t, self.runtime.models[s.model_id], phase, unit, self.runtime.time_s)

    def compute(self, s, phase=Phase.PREFILL):
        self.submit(s, phase)
        while self.events:
            event = self.events.pop()
            self.runtime.time_s = event.time
            completions = self.runtime.edges[s.execution_edge_id].compute.handle_event(event)
            if any(t.session_id == s.session_id for t in completions):
                break
        return self.runtime.commit_token(s.session_id)

    def finish(self, s):
        t = s.current_turn
        t.generation_complete = True
        while t.delivered < t.decode_done:
            self.runtime.deliver_token(s.session_id, token_id=t.output_tokens[t.delivered].token_id)
        self.runtime.finish_turn(s.session_id, self.runtime.time_s)
        self.runtime.end_session(s.session_id, self.runtime.time_s)

    def retry(self):
        notices = []
        count = 0
        while self.events:
            count += 1
            self.assertLess(count, 100)
            event = self.events.pop()
            self.runtime.time_s = event.time
            notices.extend(self.runtime.handle_resource_event(event))
        return notices

    def assert_safe(self):
        for e in self.runtime.edges.values():
            self.assertEqual(e.kv.used_bytes, e.authoritative_kv_bytes)
            self.assertLessEqual(e.kv.used_bytes, e.kv_capacity_bytes)
            self.assertGreaterEqual(e.kv.free_bytes, 0)
            e.kv.assert_consistent()

    def test_a_b_structural_kv_shared_capacity_and_other_edge(self):
        a, b, c = self.add("a", model="m4"), self.add("b", model="m8"), self.add("c", edge="E2")
        self.assertEqual(self.compute(a), CommitResult.COMMITTED)
        self.assertEqual(self.compute(b), CommitResult.COMMITTED)
        self.compute(c)
        self.assertEqual((a.authoritative_kv_bytes, b.authoritative_kv_bytes, c.authoritative_kv_bytes), (4, 8, 4))
        self.assertEqual((self.edge.kv.used_bytes, self.other.kv.used_bytes), (12, 4))
        self.assert_safe()

    def test_c_boundary_atomic_block_and_duplicate_commit(self):
        a = self.add("a", inputs=4)
        for _ in range(3):
            self.assertEqual(self.compute(a), CommitResult.COMMITTED)
        self.assertEqual(self.edge.kv.used_bytes, 12)
        self.assertEqual(self.compute(a), CommitResult.KV_BLOCKED)
        t = a.current_turn
        self.assertEqual((a.context_tokens, a.authoritative_kv_bytes, t.prefill_done), (3, 12, 3))
        self.assertEqual((t.partial_work, t.remaining_gpu_work), (1, 0))
        self.assertEqual(t.block_count, 1)
        start = t.blocked_since
        self.assertEqual(self.runtime.commit_token("a"), CommitResult.KV_BLOCKED)
        self.assertEqual((t.block_count, t.blocked_since), (1, start))
        self.assertEqual(self.edge.kv.peak_bytes, 12)
        self.assert_safe()

    def full_edge(self):
        a, b = self.add("S1", inputs=3), self.add("S2", inputs=1)
        self.compute(a)
        self.compute(a)
        self.compute(b)
        self.assertEqual((a.authoritative_kv_bytes, b.authoritative_kv_bytes), (8, 4))
        self.assertEqual(self.compute(a), CommitResult.KV_BLOCKED)
        return a, b

    def test_d_release_recovers_pending_unit_without_gpu_recompute(self):
        a, b = self.full_edge()
        task = a.current_turn.compute_task
        count = len(self.edge.compute.tasks)
        self.runtime.time_s = 1
        self.finish(b)
        self.assertEqual(self.edge.kv.used_bytes, 8)
        self.assertEqual(a.authoritative_kv_bytes, 8)
        notices = self.retry()
        self.assertEqual(len(notices), 1)
        self.assertIsInstance(notices[0], TokenCommitted)
        self.assertEqual(notices[0].task_id, task.task_id)
        self.assertEqual((a.context_tokens, a.authoritative_kv_bytes, a.current_turn.prefill_done), (3, 12, 3))
        self.assertEqual((a.status, a.current_turn.status), ("active", "active"))
        self.assertIsNone(a.current_turn.pending_commit)
        self.assertAlmostEqual(a.current_turn.blocked_time_s, 0.6)
        self.assertEqual(len(self.edge.compute.tasks), count)
        with self.assertRaises(RuntimeError):
            self.runtime.commit_token("S1")
        self.assert_safe()

    def test_e_multiple_waiters_partial_deterministic_recovery(self):
        holder = self.add("holder", inputs=2)
        self.compute(holder)
        self.compute(holder)
        resident = self.add("resident")
        self.compute(resident)
        a, b, c = self.add("z", model="m8"), self.add("a"), self.add("b")
        for s in [a, b, c]:
            self.assertEqual(self.compute(s), CommitResult.KV_BLOCKED)
        self.finish(resident)  # 4 free: z needs 8 and stays blocked; a consumes 4
        notices = self.retry()
        self.assertEqual([n.session_id for n in notices], ["a"])
        self.assertEqual([p.session_id for p in self.edge.kv.pending], ["z", "b"])
        self.finish(holder)  # 8 free: older z recovers; b remains blocked
        self.assertEqual([n.session_id for n in self.retry()], ["z"])
        self.assertEqual([p.session_id for p in self.edge.kv.pending], ["b"])
        self.assert_safe()

    def test_f_gpu_slot_freed_and_resumed_next_unit_rejoins_fcfs(self):
        a, holder = self.full_edge()
        self.assertEqual(self.edge.running_tasks, ())
        follower = self.add("follower")
        self.submit(follower)
        self.assertEqual([t.session_id for t in self.edge.running_tasks], ["follower"])
        # Releasing holder retries a's already computed unit while follower runs.
        self.finish(holder)
        event = self.events.pop()
        self.assertEqual(event.kind, "kv_retry")
        self.runtime.time_s = event.time
        self.runtime.handle_resource_event(event)
        self.assertEqual(a.authoritative_kv_bytes, 12)
        self.submit(a, Phase.DECODE)
        self.assertEqual([t.session_id for t in self.edge.ready_queue], ["S1"])
        self.assertEqual(a.current_turn.compute_task.consumed_work, 0)
        self.assert_safe()

    def test_g_context_limit_never_joins_kv_retry(self):
        tiny = ModelSpec("tiny", 1, 1, 1, 2, 1, 4, 1, 2)
        q = EventQueue()
        e = EdgeState("E", 10, 1, 4, frozenset({"tiny"}), q)
        r = RuntimeState({"tiny": tiny}, {"E": e})
        s = SessionState("s", "tiny", 0, "E", "E")
        r.add_session(s)
        r.submit_turn("s", 2, 0)
        r.input_arrived("s")
        for unit in [1, 2]:
            e.compute.submit(s, s.current_turn, tiny, Phase.PREFILL, unit, r.time_s)
            event = q.pop()
            r.time_s = event.time
            e.compute.handle_event(event)
            result = r.commit_token("s")
        self.assertEqual(result, CommitResult.CONTEXT_LIMIT)
        self.assertEqual(e.kv.pending, ())
        self.assertEqual(s.current_turn.block_count, 0)
        self.assertEqual(s.context_tokens, 1)

    def test_h_release_idempotent_preserves_others_and_retry_is_once(self):
        a, b = self.full_edge()
        self.finish(b)
        event = self.events.pop()
        self.runtime.end_session("S2", self.runtime.time_s)
        self.assertFalse(self.events)
        self.assertEqual(self.edge.kv.used_bytes, 8)
        first = self.runtime.handle_resource_event(event)
        self.assertEqual(len(first), 1)
        self.assertEqual(self.runtime.handle_resource_event(event), ())
        self.assertEqual(a.authoritative_kv_bytes, 12)
        self.assertEqual(len([e for e in self.edge.kv.trace if e["event"] == "kv_release"]), 1)

    def test_i_unchanged_future_has_same_capacity_decision_and_observation(self):
        import copy
        import json
        from replacement.simulation.s0 import S0Simulator
        cfg = json.loads((Path(__file__).resolve().parents[1] / "configs/s0_smoke.json").read_text(encoding="utf-8"))
        cfg["edge"]["kv_capacity_bytes"] = 4
        changed = copy.deepcopy(cfg)
        changed["session"]["turns"][0]["output_tokens"] = 99
        changed["session"]["turns"][1] = {"input_tokens": 99, "output_tokens": 99}
        changed["session"]["turns"].append({"input_tokens": 99, "output_tokens": 99})
        a, b = S0Simulator(cfg), S0Simulator(changed)
        a.run()
        b.run()
        self.assertEqual(a.observation(), b.observation())
        self.assertEqual(a.edge.kv.trace, b.edge.kv.trace)
        self.assertEqual((a.edge.kv.can_fit(4), b.edge.kv.can_fit(4)), (False, False))
        snapshot = asdict(a.observation())
        self.assertNotIn("hidden_output_tokens", str(snapshot))
        self.assertNotIn("_runtime", str(snapshot))
        self.assertEqual(snapshot["sessions"][0]["current_turn"]["blocked_since"], 0.4)

    def test_no_release_means_finite_quiescence_without_fake_recovery(self):
        a, b = self.full_edge()
        self.assertEqual(self.retry(), [])
        self.assertEqual(a.status, "blocked")
        self.assertEqual(a.current_turn.status, "blocked")
        self.assertIsNone(a.current_turn.received_at)
        self.assertEqual(len(self.edge.kv.pending), 1)

    def test_wrong_event_or_clock_does_not_consume_pending_retry(self):
        a, b = self.full_edge()
        self.finish(b)
        event = self.events.pop()
        self.runtime.time_s += 1
        with self.assertRaises(ValueError):
            self.runtime.handle_resource_event(event)
        self.runtime.time_s = event.time
        self.assertEqual(len(self.runtime.handle_resource_event(event)), 1)
        self.assert_safe()

    def test_direct_release_cannot_discard_active_session_kv(self):
        a = self.add("a")
        self.compute(a)
        with self.assertRaises(RuntimeError):
            self.edge.kv.release_session("a")
        self.assertEqual(a.authoritative_kv_bytes, 4)
        self.assertEqual(self.edge.kv.used_bytes, 4)

    def test_demo_uses_real_pending_units_and_no_recompute(self):
        from replacement.demos.kv_demo import run_demo
        result = run_demo()
        self.assertEqual(result["summary"]["peak_kv_bytes"], 12)
        self.assertEqual(result["summary"]["total_gpu_work"], 6)
        self.assertEqual(result["summary"]["gpu_units"], 4)
        self.assertEqual(result["summary"]["recovered_units"], 1)
        self.assertEqual(result["summary"]["final_kv_bytes"], 0)
        self.assertEqual(result["summary"]["completed_turns"], 2)
        self.assertEqual(result["summary"]["duplicate_compute"], False)
        self.assertEqual(result, run_demo())
        commits = [e for e in result["events"] if e["event"] == "token_committed"]
        self.assertEqual([e["edge_used_bytes"] for e in commits], [4, 8, 12, 12])
        self.assertTrue(any(e["event"] == "kv_blocked" and e["time_s"] == 0.6
                            for e in result["events"]))
        self.assertTrue(any(e["event"] == "token_committed" and e["time_s"] == 0.8
                            and e["reason"] == "PendingCommitRecovered" for e in result["events"]))

    def test_recovered_prefill_can_finish_legal_zero_output_turn(self):
        import json
        from replacement.demos.kv_demo import run_demo
        config = json.loads((Path(__file__).resolve().parents[1] / "configs/s1c_kv_smoke.json").read_text(encoding="utf-8"))
        config["sessions"][0].update(input_tokens=3, output_tokens=0)
        result = run_demo(config)
        self.assertEqual(result["summary"]["completed_turns"], 2)
        self.assertEqual(result["summary"]["total_gpu_work"], 5)
        recovered = [e for e in result["events"] if e["reason"] == "PendingCommitRecovered"]
        self.assertEqual([(e["phase"], e["unit_index"]) for e in recovered], [("prefill", 3)])

    def test_demo_persistent_pressure_quiesces_without_completing_blocked_turn(self):
        import json
        from replacement.demos.kv_demo import run_demo
        config = json.loads((Path(__file__).resolve().parents[1] / "configs/s1c_kv_smoke.json").read_text(encoding="utf-8"))
        config["sessions"][0].update(input_tokens=4, output_tokens=0)
        result = run_demo(config)
        self.assertEqual(result["summary"]["completed_turns"], 1)
        self.assertEqual(result["summary"]["blocked_sessions"], ["S1"])
        self.assertEqual(result["summary"]["final_kv_bytes"], 12)
