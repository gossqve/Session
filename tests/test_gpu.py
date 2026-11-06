"""Hand-derived S1-A contracts; uses the same event engine as S0."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from replacement.simulation.events import EventQueue
from replacement.resources.gpu import EqualShareGPU


class GPUTests(unittest.TestCase):
    def setUp(self):
        self.queue = EventQueue()
        self.gpu = EqualShareGPU(self.queue, "E1", 10)

    def drain(self):
        done = []
        count = 0
        while self.queue:
            count += 1
            self.assertLess(count, 1000, "event progress")
            done.extend(self.gpu.handle_event(self.queue.pop()))
        return [(c.task_id, c.time_s) for c in done]

    def assert_conserved(self):
        for task in self.gpu.tasks.values():
            self.assertAlmostEqual(task.initial_work, task.consumed_work + task.remaining_work)
            self.assertGreaterEqual(task.remaining_work, 0)
        self.assertLessEqual(sum(self.gpu.rates.values()), 10 + 1e-12)

    def test_a_single_task(self):
        self.gpu.submit("S1:T1", 10, 0)
        self.assertEqual(self.drain(), [("S1:T1", 1)])
        self.assert_conserved()

    def test_b_simultaneous_equal_tasks(self):
        self.gpu.submit("a", 10, 0)
        self.gpu.submit("b", 10, 0)
        self.assertEqual(self.gpu.rates, {"a": 5, "b": 5})
        self.assertEqual(self.drain(), [("a", 2), ("b", 2)])

    def test_c_midway_arrival_and_remaining_work(self):
        self.gpu.submit("a", 10, 0)
        self.gpu.submit("b", 10, 0.5)
        self.assertEqual(self.gpu.tasks["a"].consumed_work, 5)
        self.assertEqual(self.gpu.tasks["a"].remaining_work, 5)
        self.assertEqual(self.gpu.rates, {"a": 5, "b": 5})
        # Old t=1 prediction must do nothing, including no duplicate settlement.
        stale = self.queue.pop()
        self.assertEqual(stale.time, 1)
        before = self.gpu.tasks
        self.assertEqual(self.gpu.handle_event(stale), ())
        self.assertEqual(self.gpu.tasks, before)
        self.assertEqual(self.drain(), [("a", 1.5), ("b", 2)])

    def test_d_three_tasks_and_old_predictions(self):
        for name, work in [("a", 10), ("b", 20), ("c", 30)]:
            self.gpu.submit(name, work, 0)
        self.assertEqual(self.gpu.rates, dict.fromkeys("abc", 10 / 3))
        completed = []
        while self.queue:
            result = self.gpu.handle_event(self.queue.pop())
            completed.extend((c.task_id, c.time_s) for c in result)
            if result and result[0].task_id == "a":
                self.assertEqual(self.gpu.rates, {"b": 5, "c": 5})
                self.assertEqual(self.gpu.tasks["b"].remaining_work, 10)
                self.assertEqual(self.gpu.tasks["c"].remaining_work, 20)
        self.assertEqual(completed, [("a", 3), ("b", 5), ("c", 6)])

    def test_e_conservation_at_intermediate_times(self):
        self.gpu.submit("a", 10, 0)
        self.gpu.submit("b", 10, 0.5)
        for time in [0.6, 0.8, 1, 1.25]:
            self.gpu.advance(time)
            self.assert_conserved()
            self.assertAlmostEqual(sum(t.consumed_work for t in self.gpu.tasks.values()), 10 * time)
        self.assertEqual(self.drain(), [("a", 1.5), ("b", 2)])
        self.assert_conserved()

    def test_f_zero_work_idle_and_restart(self):
        done = self.gpu.submit("zero", 0, 0)
        self.assertEqual([(c.task_id, c.time_s) for c in done], [("zero", 0)])
        self.assertFalse(self.queue)
        self.assertEqual(self.gpu.rates, {})
        self.gpu.advance(100)
        self.gpu.submit("next", 10, 100)
        self.assertEqual(self.drain(), [("next", 101)])
        self.assertEqual(self.gpu.rates, {})

    def test_f_completion_at_arrival_in_either_dispatch_order(self):
        for arrival_first in [True, False]:
            with self.subTest(arrival_first=arrival_first):
                self.setUp()
                self.gpu.submit("a", 10, 0)
                done = []
                if not arrival_first:
                    done.extend(self.gpu.handle_event(self.queue.pop()))
                done.extend(self.gpu.submit("b", 10, 1))
                tail = self.drain()
                self.assertEqual([(c.task_id, c.time_s) for c in done] + tail,
                                 [("a", 1), ("b", 2)])

    def test_f_invalid_values_and_duplicate_ids(self):
        for capacity in [0, -1, float("nan"), float("inf")]:
            with self.assertRaises(ValueError):
                EqualShareGPU(self.queue, "bad", capacity)
        for work in [-1, float("nan"), float("inf")]:
            with self.assertRaises(ValueError):
                self.gpu.submit("bad", work, 0)
        self.gpu.submit("a", 10, 1)
        for time in [-1, 0, float("nan"), float("inf")]:
            with self.assertRaises(ValueError):
                self.gpu.advance(time)
        with self.assertRaises(ValueError):
            self.gpu.submit("a", 10, 1)

    def test_f_deterministic_trace_and_stable_submission_order(self):
        def run():
            self.setUp()
            for name in ["z", "a", "m"]:
                self.gpu.submit(name, 10, 0)
            done = self.drain()
            return done, self.gpu.trace
        first = run()
        self.assertEqual(first, run())
        self.assertEqual(first[0], [("z", 3), ("a", 3), ("m", 3)])

    def test_exit_settles_and_redistributes_without_completing_withdrawn_task(self):
        self.gpu.submit("a", 10, 0)
        self.gpu.submit("b", 10, 0)
        self.gpu.withdraw("a", 0.5)
        self.assertEqual(self.gpu.tasks["a"].remaining_work, 7.5)
        self.assertEqual(self.gpu.tasks["a"].status, "withdrawn")
        self.assertEqual(self.gpu.rates, {"b": 10})
        self.assertEqual(self.drain(), [("b", 1.25)])
        self.assert_conserved()

    def test_fractional_deadline_and_sub_tick_work_progress(self):
        self.gpu.submit("a", 1, 0)
        self.gpu.submit("b", 2, 0)
        self.assertEqual(self.drain(), [("a", 0.2), ("b", 0.3)])
        self.gpu.submit("tiny", 1e-15, 1)
        self.assertEqual(self.drain(), [("tiny", 1.000000000001)])
        self.assert_conserved()

    def test_advance_cannot_skip_pending_completion(self):
        self.gpu.submit("a", 10, 0)
        with self.assertRaises(ValueError):
            self.gpu.advance(2)
        self.assertEqual(self.drain(), [("a", 1)])

    def test_resource_isolation_on_shared_queue(self):
        other = EqualShareGPU(self.queue, "E2", 20)
        self.gpu.submit("a", 10, 0)
        other.submit("a", 10, 0)
        first = self.queue.pop()
        self.assertEqual(self.gpu.handle_event(first), ())
        self.assertEqual(other.handle_event(first)[0].time_s, 0.5)
        second = self.queue.pop()
        self.assertEqual(self.gpu.handle_event(second)[0].time_s, 1)

    def test_nonterminating_decimal_deadline_and_interval_capacity(self):
        gpu = EqualShareGPU(self.queue, "thirds", 3)
        gpu.submit("a", 1, 0)
        done = gpu.handle_event(self.queue.pop())
        self.assertEqual(done[0].time_s, 0.333333333334)
        self.assertEqual(gpu.tasks["a"].consumed_work, 1)
        for interval in gpu.trace:
            if interval["event"] == "service":
                self.assertLessEqual(interval["consumed_work"], 3 * interval["elapsed_s"])

    def test_general_task_count_with_unequal_work(self):
        for i in range(1, 8):
            self.gpu.submit(str(i), i, 0)
        self.assertEqual(self.drain(), [("1", 0.7), ("2", 1.3), ("3", 1.8),
                                       ("4", 2.2), ("5", 2.5), ("6", 2.7), ("7", 2.8)])
        self.assert_conserved()
        for interval in self.gpu.trace:
            if interval["event"] == "service":
                self.assertLessEqual(interval["consumed_work"], 10 * interval["elapsed_s"] + 1e-12)

    def test_replayed_completion_does_not_notify_twice(self):
        self.gpu.submit("a", 10, 0)
        event = self.queue.pop()
        self.assertEqual(len(self.gpu.handle_event(event)), 1)
        before = self.gpu.tasks
        self.assertEqual(self.gpu.handle_event(event), ())
        self.assertEqual(self.gpu.tasks, before)

    def test_demo_multiple_sessions_use_shared_resource(self):
        from replacement.demos.gpu_demo import run_demo
        config = {"edge_id": "E1", "capacity": 10, "tasks": [
            {"task_id": "S1:T1", "arrival_s": 0, "work": 10},
            {"task_id": "S2:T1", "arrival_s": 0.5, "work": 10}]}
        result, trace = run_demo(config)
        self.assertEqual(result["completions"], [
            {"task_id": "S1:T1", "time_s": 1.5},
            {"task_id": "S2:T1", "time_s": 2.0}])
        self.assertEqual(result["total_consumed_work"], 20)
        self.assertEqual((result, trace), run_demo(config))
