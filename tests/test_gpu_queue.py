"""S1-B independent hand calculations on the real S1-A GPU resource."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from replacement.simulation.events import EventQueue
from replacement.resources.gpu_queue import GPUQueue


class GPUQueueTests(unittest.TestCase):
    def make(self, capacity=10, slots=2):
        self.events = EventQueue()
        self.scheduler = GPUQueue(self.events, "E1", capacity, slots)
        return self.scheduler

    def invariants(self, scheduler=None):
        s = scheduler or self.scheduler
        self.assertLessEqual(len(s.rates), s.slots)
        self.assertLessEqual(sum(s.rates.values()), s.capacity + 1e-12)
        self.assertTrue(set(s.waiting_ids).isdisjoint(s.rates))
        for task in s.tasks.values():
            self.assertAlmostEqual(task.initial_work, task.consumed_work + task.remaining_work)
            self.assertGreaterEqual(task.remaining_work, 0)
            if task.status == "waiting":
                self.assertEqual(task.consumed_work, 0)
                self.assertIsNone(task.start_time)
                self.assertIsNone(task.completion_time)

    def drain(self):
        done = []
        count = 0
        while self.events:
            count += 1
            self.assertLess(count, 1000)
            done.extend(self.scheduler.handle_event(self.events.pop()))
            self.invariants()
        return [(c.task_id, c.time_s) for c in done]

    def test_a_sufficient_slots(self):
        s = self.make()
        s.ready("a", 10, 0)
        s.ready("b", 10, 0)
        self.assertEqual(s.rates, {"a": 5, "b": 5})
        self.assertEqual(self.drain(), [("a", 2), ("b", 2)])
        self.assertEqual([t.queue_wait_s for t in s.tasks.values()], [0, 0])

    def test_b_three_tasks_two_slots_no_work_while_waiting(self):
        s = self.make()
        for name in "abc":
            s.ready(name, 10, 0)
        self.assertEqual(s.waiting_ids, ("c",))
        s.advance(1)
        self.assertEqual(s.tasks["c"].remaining_work, 10)
        self.assertEqual(s.tasks["c"].consumed_work, 0)
        self.assertEqual(s.rates, {"a": 5, "b": 5})
        self.invariants()
        self.assertEqual(self.drain(), [("a", 2), ("b", 2), ("c", 3)])
        task = s.tasks["c"]
        self.assertEqual((task.ready_time, task.start_time, task.completion_time, task.queue_wait_s),
                         (0, 2, 3, 2))

    def test_c_single_slot(self):
        s = self.make(slots=1)
        s.ready("a", 10, 0)
        s.ready("b", 10, 0.5)
        self.assertEqual(self.drain(), [("a", 1), ("b", 2)])
        self.assertEqual((s.tasks["b"].start_time, s.tasks["b"].queue_wait_s), (1, 0.5))

    def test_d_fcfs_ready_time_and_stable_submission_ties(self):
        s = self.make(slots=1)
        s.ready("a", 10, 0)
        s.ready("z", 10, 0.5)
        s.ready("b", 10, 0.75)
        s.ready("c", 10, 0.75)
        self.assertEqual(s.waiting_ids, ("z", "b", "c"))
        self.assertEqual(self.drain(), [("a", 1), ("z", 2), ("b", 3), ("c", 4)])
        self.assertEqual(s.tasks["z"].queue_wait_s, 0.5)
        self.assertEqual(s.tasks["b"].queue_wait_s, 1.25)
        self.assertEqual(s.tasks["b"].start_time, 2)

    def test_e_dynamic_shares_stale_prediction_and_conservation(self):
        s = self.make(capacity=12)
        s.ready("a", 12, 0)
        s.ready("b", 18, 0.5)
        s.ready("c", 6, 0.75)
        self.assertEqual(s.rates, {"a": 6, "b": 6})
        stale = self.events.pop()
        self.assertEqual(stale.time, 1)
        before = s.tasks
        self.assertEqual(s.handle_event(stale), ())
        self.assertEqual(s.tasks, before)
        first = self.events.pop()
        self.assertEqual([(c.task_id, c.time_s) for c in s.handle_event(first)], [("a", 1.5)])
        self.assertEqual(s.tasks["b"].remaining_work, 12)
        self.assertEqual(s.rates, {"b": 6, "c": 6})
        self.assertEqual(s.tasks["c"].queue_wait_s, 0.75)
        # Removing a first predicts b alone; c's admission invalidates that
        # prediction even though its timestamp happens to remain 2.5.
        stale = self.events.pop()
        self.assertEqual(stale.time, 2.5)
        self.assertEqual(s.handle_event(stale), ())
        second = s.handle_event(self.events.pop())
        self.assertEqual([(c.task_id, c.time_s) for c in second], [("c", 2.5)])
        self.assertEqual(s.rates, {"b": 12})
        self.assertEqual(self.drain(), [("b", 3)])
        self.assertEqual(sum(t.consumed_work for t in s.tasks.values()), 36)
        self.invariants()

    def test_f_new_arrival_never_bypasses_existing_waiter_at_completion(self):
        for arrival_first in (True, False):
            with self.subTest(arrival_first=arrival_first):
                s = self.make(slots=1)
                s.ready("a", 10, 0)
                s.ready("b", 10, 0.5)
                done = []
                if not arrival_first:
                    done.extend(s.handle_event(self.events.pop()))
                done.extend(s.ready("c", 10, 1))
                self.assertEqual(s.tasks["b"].start_time, 1)
                self.assertEqual(s.waiting_ids, ("c",))
                self.assertEqual([(c.task_id, c.time_s) for c in done] + self.drain(),
                                 [("a", 1), ("b", 2), ("c", 3)])

    def test_f_multiple_releases_fill_all_slots_in_fcfs_order(self):
        s = self.make(slots=3)
        for name in ["a", "b", "c", "z", "x", "y", "last"]:
            s.ready(name, 10, 0)
        self.assertEqual(self.drain(), [("a", 3), ("b", 3), ("c", 3),
                                       ("z", 6), ("x", 6), ("y", 6), ("last", 7)])
        self.assertEqual([s.tasks[n].start_time for n in ["z", "x", "y"]], [3, 3, 3])

    def test_f_zero_work_obeys_fcfs_and_drains_without_time_advance(self):
        s = self.make(slots=1)
        immediate = s.ready("zero", 0, 0)
        self.assertEqual([(c.task_id, c.time_s) for c in immediate], [("zero", 0)])
        self.assertFalse(self.events)
        s.ready("a", 10, 0)
        for name in ["z1", "z2"]:
            self.assertEqual(s.ready(name, 0, 0.25), ())
        s.ready("b", 10, 0.5)
        self.assertEqual(s.waiting_ids, ("z1", "z2", "b"))
        self.assertEqual(self.drain(), [("a", 1), ("z1", 1), ("z2", 1), ("b", 2)])
        self.assertEqual(s.tasks["z1"].queue_wait_s, 0.75)
        self.assertEqual(s.tasks["b"].start_time, 1)
        self.assertEqual(s.rates, {})

    def test_f_cancel_running_and_waiting_tasks(self):
        s = self.make(slots=1)
        s.ready("a", 10, 0)
        s.ready("b", 10, 0.1)
        s.ready("c", 10, 0.2)
        s.cancel("b", 0.25)
        self.assertEqual(s.waiting_ids, ("c",))
        self.assertEqual(s.tasks["b"].queue_wait_s, 0.15)
        self.assertIsNone(s.tasks["b"].start_time)
        s.cancel("a", 0.5)
        self.assertEqual(s.tasks["a"].consumed_work, 5)
        self.assertEqual(s.tasks["a"].remaining_work, 5)
        self.assertEqual(s.tasks["a"].status, "cancelled")
        self.assertIsNone(s.tasks["a"].completion_time)
        self.assertEqual(s.tasks["c"].start_time, 0.5)
        self.assertEqual(self.drain(), [("c", 1.5)])
        self.invariants()

    def test_f_completion_wins_cancellation_tie_and_notifications_are_once(self):
        s = self.make(slots=1)
        s.ready("a", 10, 0)
        s.ready("b", 10, 0.5)
        done = s.cancel("a", 1)
        self.assertEqual([(c.task_id, c.time_s) for c in done], [("a", 1)])
        self.assertEqual(s.tasks["a"].status, "completed")
        self.assertEqual(s.cancel("a", 1), ())
        self.assertEqual(self.drain(), [("b", 2)])

    def test_f_validation_rejects_without_side_effects(self):
        for slots in [0, -1, 1.5, True, "2", None]:
            with self.subTest(slots=slots), self.assertRaises(ValueError):
                GPUQueue(EventQueue(), "E1", 10, slots)
        s = self.make()
        s.ready("a", 10, 0)
        before = s.tasks
        for task_id in ["", None, 4, [], "a"]:
            with self.subTest(task_id=task_id), self.assertRaises(ValueError):
                s.ready(task_id, 1, 0.5)
        for work in [-1, float("nan"), float("inf"), True, "1"]:
            with self.subTest(work=work), self.assertRaises(ValueError):
                s.ready("bad", work, 0.5)
        with self.assertRaises(ValueError):
            s.cancel("missing", 0.5)
        self.assertEqual(s.tasks, before)
        for time in [-1, float("nan"), float("inf")]:
            with self.assertRaises(ValueError):
                s.ready("bad", 1, time)
        s.advance(0.5)
        with self.assertRaises(ValueError):
            s.ready("past", 1, 0.25)
        with self.assertRaises(ValueError):
            s.advance(2)

    def test_f_idle_restart_and_waiting_time_checkpoint(self):
        s = self.make(slots=1)
        self.assertEqual(s.advance(10), ())
        self.assertEqual(s.rates, {})
        s.ready("a", 10, 10)
        s.ready("b", 10, 10.25)
        s.advance(10.5)
        self.assertEqual(s.tasks["b"].queue_wait_s, 0.25)
        self.assertEqual(self.drain(), [("a", 11), ("b", 12)])
        self.assertEqual(s.tasks["b"].queue_wait_s, 0.75)
        self.assertEqual(s.waiting_ids, ())

    def test_f_replay_stale_and_foreign_events_do_not_mutate_state(self):
        s = self.make(slots=1)
        s.ready("a", 10, 0)
        event = self.events.pop()
        self.assertEqual(len(s.handle_event(event)), 1)
        before = (s.tasks, list(s.trace))
        self.assertEqual(s.handle_event(event), ())
        self.assertEqual((s.tasks, s.trace), before)

    def test_f_edge_isolation_with_shared_event_queue(self):
        s = self.make(slots=1)
        other = GPUQueue(self.events, "E2", 20, 2)
        for scheduler in [s, other]:
            scheduler.ready("a", 10, 0)
            scheduler.ready("b", 10, 0)
        self.assertEqual(s.waiting_ids, ("b",))
        self.assertEqual(other.waiting_ids, ())
        done = {"E1": [], "E2": []}
        while self.events:
            event = self.events.pop()
            for key, scheduler in [("E1", s), ("E2", other)]:
                done[key].extend((c.task_id, c.time_s) for c in scheduler.handle_event(event))
                self.invariants(scheduler)
        self.assertEqual(done, {"E1": [("a", 1), ("b", 2)], "E2": [("a", 1), ("b", 1)]})

    def test_f_repeatable_trace(self):
        def run():
            s = self.make(slots=1)
            for task in ["z", "a", "b"]:
                s.ready(task, 10, 0)
            done = self.drain()
            return done, s.tasks, s.trace, s.gpu_trace
        self.assertEqual(run(), run())

    def test_integer_work_preserves_engine_precision(self):
        s = self.make(capacity=9007199254740992, slots=1)
        s.ready("a", 9007199254740993, 0)
        self.assertEqual(self.drain(), [("a", 1.000000000001)])

    def test_lossy_integer_clock_is_rejected_before_any_mutation(self):
        s = self.make(slots=1)
        for operation in (lambda: s.ready("a", 10, 9007199254740993),
                          lambda: s.advance(9007199254740993)):
            with self.assertRaises(ValueError):
                operation()
            self.assertEqual(s.tasks, {})
            self.assertEqual(s.waiting_ids, ())
            self.assertEqual(s.time_s, 0)
        s.ready("a", 10, 0)
        before = (s.tasks, s.time_s, list(s.trace))
        with self.assertRaises(ValueError):
            s.cancel("a", 9007199254740993)
        self.assertEqual((s.tasks, s.time_s, s.trace), before)
        self.assertEqual(self.drain(), [("a", 1)])

    def test_demo_outputs_gpu_phase_times_and_is_repeatable(self):
        from replacement.demos.gpu_queue_demo import run_demo
        config = {"edge_id": "E1", "capacity": 12, "slots": 2, "tasks": [
            {"task_id": "a", "work": 12, "ready_time": 0},
            {"task_id": "b", "work": 18, "ready_time": 0.5},
            {"task_id": "c", "work": 6, "ready_time": 0.75}]}
        output = run_demo(config)
        self.assertEqual(output["summary"]["total_consumed_work"], 36)
        self.assertEqual(output["summary"]["completed_tasks"], 3)
        self.assertEqual([(t["ready_time"], t["start_time"], t["completion_time"], t["queue_wait_s"])
                          for t in output["tasks"]], [(0, 0, 1.5, 0), (0.5, 0.5, 3, 0),
                                                    (0.75, 1.5, 2.5, 0.75)])
        self.assertEqual(output, run_demo(config))

    def test_demo_rejects_invalid_waiting_work_and_ids_before_run(self):
        from replacement.demos.gpu_queue_demo import run_demo
        for bad in [{"task_id": "b", "work": -1, "ready_time": 0},
                    {"task_id": "a", "work": 1, "ready_time": 0},
                    {"task_id": "b", "work": 1, "ready_time": float("nan")}]:
            config = {"edge_id": "E1", "capacity": 10, "slots": 1, "tasks": [
                {"task_id": "a", "work": 10, "ready_time": 0}, bad]}
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                run_demo(config)
