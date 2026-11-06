"""Turn segments retain the original GPUQueue slot across current units."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from replacement.resources.gpu_queue import GPUQueue
from replacement.simulation.events import EventQueue


class TurnGPUTests(unittest.TestCase):
    def test_typed_turn_cannot_mix_atomic_task_with_retained_slot(self):
        from replacement.core.entities import ModelSpec, SessionState, EdgeState, Phase
        from replacement.core.runtime import RuntimeState
        q = EventQueue()
        model = ModelSpec("m", 1, 1, 1, 2, 10, 3, 1, 1)
        edge = EdgeState("E", 10, 2, 100, frozenset({"m"}), q)
        runtime = RuntimeState({"m": model}, {"E": edge})
        session = SessionState("s", "m", 0, "E", "E")
        runtime.add_session(session)
        turn = runtime.submit_turn("s", 2, 0)
        runtime.input_arrived("s")
        edge.compute.submit(session, turn, model, Phase.PREFILL, 1, 0, continuous=True)
        event = q.pop()
        runtime.time_s = event.time
        edge.compute.handle_event(event)
        runtime.commit_token("s")
        with self.assertRaises(ValueError):
            edge.compute.submit(session, turn, model, Phase.PREFILL, 2, 0.1)
        self.assertEqual(len(edge.compute.scheduler.tasks), 1)
        edge.compute.submit(session, turn, model, Phase.PREFILL, 2, 0.1, continuous=True)
        self.assertEqual(len(edge.running_tasks), 1)

    def test_continuous_turn_never_requeues_at_unit_boundary(self):
        q = EventQueue()
        gpu = GPUQueue(q, "E", 10, 1)
        gpu.ready("turn1", 1, 0, retain_slot=True)
        gpu.ready("turn2", 1, 0, retain_slot=True)
        done = gpu.handle_event(q.pop())
        self.assertEqual([(d.task_id, d.time_s) for d in done], [("turn1", 0.1)])
        self.assertEqual(gpu.tasks["turn1"].status, "awaiting_unit")
        self.assertEqual(gpu.tasks["turn2"].status, "waiting")
        gpu.continue_task("turn1", 2, 0.1)
        done = gpu.handle_event(q.pop())
        self.assertEqual([(d.task_id, d.time_s) for d in done], [("turn1", 0.3)])
        self.assertIsNone(gpu.tasks["turn2"].start_time)
        gpu.release_turn("turn1", 0.3)
        self.assertEqual(gpu.tasks["turn2"].start_time, 0.3)
        self.assertEqual(gpu.tasks["turn1"].consumed_work, 3)
        self.assertEqual(gpu.tasks["turn2"].queue_wait_s, 0.3)

    def test_unit_boundaries_require_same_clock_decision_and_once_only_notification(self):
        q = EventQueue()
        gpu = GPUQueue(q, "E", 10, 1)
        gpu.ready("turn", 1, 0, retain_slot=True)
        event = q.pop()
        self.assertEqual(len(gpu.handle_event(event)), 1)
        self.assertEqual(gpu.handle_event(event), ())
        with self.assertRaises(ValueError):
            gpu.advance(1)
        gpu.release_turn("turn", 0.1)
        with self.assertRaises(ValueError):
            gpu.continue_task("turn", 1, 0.1)
