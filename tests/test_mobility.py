"""Section III.B.3: private exogenous plans, never actual Handover."""
import copy
from dataclasses import FrozenInstanceError, asdict
from fractions import Fraction
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from replacement.simulation.serving import ServingSimulator
from replacement.simulation.mobility import PendingMove, MobilityRuntime
from test_network_serving import remote


def moving(outputs=10, horizon=0.65, interval=0.15):
    c = remote(outputs)
    third = copy.deepcopy(c["edges"][0])
    third["id"] = "E3"
    c["edges"].append(third)
    t = c["topology"]
    t["edges"] = copy.deepcopy(c["edges"])
    t["links"].extend([
        dict(link_id="3a", source_node="E3", target_node="gA", capacity_bps=80),
        dict(link_id="a3", source_node="gA", target_node="E3", capacity_bps=80)])
    t["paths"].extend([
        dict(path_id="23", source_node="E2", target_node="E3", link_ids=["2b", "ba", "a3"]),
        dict(path_id="32", source_node="E3", target_node="E2", link_ids=["3a", "ab", "b2"])])
    t["allowed_serving_pairs"].extend([["E2", "E2"], ["E3", "E2"]])
    t["mobility_adjacency"] = {"E": ["E2"], "E2": ["E3"]}
    c["observation_end_s"] = horizon
    c["mobility"] = {"check_interval_s": interval, "transition_probabilities": {
        "E": {"E2": 1}, "E2": {"E3": 1}, "E3": {"E3": 1}}}
    return c


class MobilityTests(unittest.TestCase):
    def test_matrix_valid_exact_decimal_sum_and_self_transition(self):
        c = moving()
        c["mobility"]["transition_probabilities"]["E"] = {"E": 0.1, "E2": 0.9}
        ServingSimulator(c)
        c["mobility"]["transition_probabilities"]["E"] = {"E": 1}
        out = ServingSimulator(c).run()
        self.assertEqual(out["mobility"]["summary"]["planned_access_changes"], 0)

    def test_matrix_rejects_invalid_numbers(self):
        for value in [True, False, -0.1, float("nan"), float("inf"), "1", None]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                c = moving(); c["mobility"]["transition_probabilities"]["E"] = {"E2": value}
                ServingSimulator(c)

    def test_matrix_rejects_wrong_sum(self):
        for row in [{}, {"E": 0.9}, {"E": 0.1, "E2": 0.9000000000000001}]:
            with self.subTest(row=row), self.assertRaises(ValueError):
                c = moving(); c["mobility"]["transition_probabilities"]["E"] = row
                ServingSimulator(c)

    def test_matrix_requires_all_sources_and_registered_targets(self):
        for change in ["missing", "source", "target"]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                c = moving(); matrix = c["mobility"]["transition_probabilities"]
                if change == "missing": matrix.pop("E3")
                elif change == "source": matrix["ghost"] = {"ghost": 1}
                else: matrix["E"]["ghost"] = 0
                ServingSimulator(c)

    def test_positive_transition_needs_adjacency_and_directed_path(self):
        for change in ["adjacency", "path"]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                c = moving()
                if change == "adjacency": c["topology"]["mobility_adjacency"] = {}
                else:
                    # Serving E3/E2 is reachable, but E->E3 has no move path.
                    c["mobility"]["transition_probabilities"]["E"] = {"E3": 1}
                    c["topology"]["mobility_adjacency"]["E"] = ["E3"]
                ServingSimulator(c)

    def test_transitive_reachable_access_requires_allowed_pair(self):
        c = moving(); c["topology"]["allowed_serving_pairs"].remove(["E3", "E2"])
        with self.assertRaises(ValueError): ServingSimulator(c)

    def test_future_access_needs_both_serving_directions(self):
        c = moving(); c["topology"]["paths"] = [p for p in c["topology"]["paths"] if p["path_id"] != "32"]
        with self.assertRaises(ValueError): ServingSimulator(c)

    def test_zero_probability_non_neighbor_needs_no_movement_path(self):
        c = moving(); c["mobility"]["transition_probabilities"]["E"]["E3"] = 0
        ServingSimulator(c)

    def test_mobility_requires_topology_and_finite_horizon(self):
        for change in ["topology", "horizon", "none"]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                c = moving()
                if change == "topology": c.pop("topology")
                elif change == "horizon": c.pop("observation_end_s")
                else: c["mobility"] = None
                ServingSimulator(c)

    def test_clock_validation_and_one_tick_progress(self):
        for key in ["check_interval_s", "observation_end_s"]:
            for value in [True, -1, float("nan"), float("inf")]:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    c = moving()
                    (c["mobility"] if key == "check_interval_s" else c)[key] = value
                    ServingSimulator(c)
        for interval in [0, 1e-15]:
            with self.subTest(interval=interval), self.assertRaises(ValueError):
                ServingSimulator(moving(interval=interval))

    def test_sha256_fixed_vectors_and_literal_sampling(self):
        # Independently specified SHA-256 prefixes of compact UTF-8 JSON arrays.
        self.assertEqual(MobilityRuntime.draw(7, "S1", 1), Fraction(10322986851479038141, 2**64))
        self.assertEqual(MobilityRuntime.draw(7, "S1", 2), Fraction(14087191726135761714, 2**64))
        self.assertEqual(MobilityRuntime.draw(20261108, "用户", 3), Fraction(6973352579188996903, 2**64))
        c = moving(); c["seed"] = 7
        c["mobility"]["transition_probabilities"]["E"] = {"E2": 0.5, "E": 0.5}
        sim = ServingSimulator(c); sim.advance_to(0.15)
        self.assertEqual(sim.mobility.sessions["S1"].planned_access_edge_id, "E2")

    def test_markov_previous_row_and_fifo_not_latest_target(self):
        sim = ServingSimulator(moving()); sim.advance_to(0.45)
        s = sim.mobility.sessions["S1"]
        self.assertEqual(s.planned_access_edge_id, "E3")
        self.assertEqual([(p.source_edge_id, p.target_edge_id, p.planned_at) for p in s.pending_moves],
                         [("E", "E2", 0.15), ("E2", "E3", 0.3)])
        self.assertEqual((s.mobility_check_count, s.planned_change_count, s.max_pending_depth), (3, 2, 2))
        self.assertEqual([p.check_index for p in s.pending_moves], [1, 2])

    def test_pending_move_is_immutable(self):
        p = PendingMove(1, "E", "E2", 0.15)
        with self.assertRaises(FrozenInstanceError): p.target_edge_id = "E3"

    def test_arrival_relative_absolute_clock_and_lazy_registration(self):
        c = moving(horizon=1.1); c["sessions"][0]["arrival_time"] = 0.2
        sim = ServingSimulator(c)
        self.assertEqual(sim.mobility.sessions, {})
        sim.advance_to(0.2)
        self.assertEqual(sim.mobility.sessions["S1"].next_check_index, 1)
        self.assertEqual(sim.mobility.sessions["S1"].mobility_check_count, 0)
        sim.advance_to(0.65)
        checks = [e["time_s"] for e in sim.mobility.events if e["event"] == "mobility_check"]
        self.assertEqual(checks, [0.35, 0.5, 0.65])

    def test_does_not_prebuild_future_checks(self):
        sim = ServingSimulator(moving(horizon=100000))
        sim.step()  # arrival
        # Pop a copy of the queue to inspect public events without consuming the run.
        queue = copy.deepcopy(sim.queue); checks = []
        while queue:
            e = queue.pop()
            if e.kind == "mobility_check": checks.append(e)
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0].time, 0.15)

    def test_determinism_independent_session_and_call_order(self):
        c = moving(); c["mobility"]["transition_probabilities"]["E"] = {"E": 0.5, "E2": 0.5}
        original = ServingSimulator(c).run()["mobility"]["events"]
        self.assertEqual(original, ServingSimulator(copy.deepcopy(c)).run()["mobility"]["events"])
        other = copy.deepcopy(c["sessions"][0]); other["id"] = "other"; c["sessions"].insert(0, other)
        joined = ServingSimulator(c).run()["mobility"]["events"]
        self.assertEqual(original, [e for e in joined if e["session_id"] == "S1"])
        a = MobilityRuntime.draw(7, "S1", 2)
        MobilityRuntime.draw(7, "other", 1)
        self.assertEqual(MobilityRuntime.draw(7, "S1", 2), a)

    def test_natural_end_clears_pending_but_keeps_history_and_counts(self):
        sim = ServingSimulator(moving(outputs=1, horizon=0.9)); out = sim.run()
        s = sim.mobility.sessions["S1"]
        self.assertFalse(s.active); self.assertEqual(list(s.pending_moves), [])
        self.assertEqual(s.mobility_check_count, 3)  # end at .6 wins over check4
        self.assertEqual(out["mobility"]["summary"]["pending_moves_cancelled"], 2)
        self.assertEqual(sum(e["event"] == "mobility_pending_added" for e in sim.mobility.events), 2)

    def test_context_limit_prefill_and_decode_both_end_mobility(self):
        for inputs in [1, 2]:
            with self.subTest(inputs=inputs):
                c = moving(horizon=1); c["models"][0]["context_window_tokens"] = 1
                c["sessions"][0]["turns"][0]["input_tokens"] = inputs
                sim = ServingSimulator(c); out = sim.run()
                self.assertEqual(out["sessions"][0]["termination_reason"], "ContextLimit")
                self.assertFalse(sim.mobility.sessions["S1"].active)
                ended = out["sessions"][0]["end_time"]
                self.assertTrue(all(e["time_s"] <= ended for e in sim.mobility.events))
                self.assertEqual(list(sim.mobility.sessions["S1"].pending_moves), [])

    def test_expired_check_does_not_advance_clock(self):
        sim = ServingSimulator(moving(outputs=1)); sim.run(); end = sim.time_s
        sim.queue.schedule(99, "mobility_check", priority=80, session_id="S1", check_index=999)
        self.assertIsNone(sim.step()); self.assertEqual(sim.time_s, end)

    def test_kvblocked_session_remains_mobile(self):
        c = moving(); c["edges"][1]["kv_capacity_bytes"] = 4
        c["topology"]["edges"] = copy.deepcopy(c["edges"])
        sim = ServingSimulator(c); out = sim.run()
        self.assertEqual(out["summary"]["blocked_sessions"], 1)
        self.assertTrue(sim.mobility.sessions["S1"].active)
        self.assertEqual(sim.mobility.sessions["S1"].mobility_check_count, 4)

    def test_future_seed_does_not_leak_before_first_check(self):
        c = moving(); changed = copy.deepcopy(c); changed["seed"] = 999
        a, b = ServingSimulator(c), ServingSimulator(changed)
        a.advance_to(0.1); b.advance_to(0.1)
        self.assertEqual(asdict(a.observation()), asdict(b.observation()))
        for key in ["events", "turns", "sessions", "resources", "gpu_events", "kv_events", "network_events"]:
            self.assertEqual(a.results()[key], b.results()[key])
        self.assertNotIn("mobility", str(asdict(a.observation())))

    def test_actual_provenance_paths_and_complete_core_results_unchanged(self):
        c = moving(horizon=2)
        a = ServingSimulator(c); active = a.run()
        base = copy.deepcopy(c); base.pop("mobility")
        b = ServingSimulator(base); b.advance_to(2); plain = b.results()
        for key in plain:
            if key != "summary": self.assertEqual(active[key], plain[key], key)
        summary = dict(active["summary"]); summary["stage"] = "S2-C"
        self.assertEqual(summary, plain["summary"])
        self.assertEqual(active["summary"]["stage"], "S3-A")
        self.assertEqual({t["access_edge_id"] for t in active["output_tokens"]}, {"E"})
        self.assertEqual({t["execution_edge_id"] for t in active["output_tokens"]}, {"E2"})
        self.assertNotIn("mobility", plain)

    def test_same_clock_gpu_and_delivery_settle_before_mobility(self):
        c = moving(outputs=3, interval=0.1)
        sim = ServingSimulator(c); order = []
        for _ in range(100):
            event = sim.step()
            self.assertIsNotNone(event)
            order.append(event)
            if event == (0.6, "mobility_check"):
                break
        else:
            self.fail("Did not execute the .6 mobility check")
        for t in [0.3, 0.4, 0.5, 0.6]:
            same = [kind for time, kind in order if time == t]
            self.assertEqual(same[-1], "mobility_check")
            self.assertIn("gpu_completion", same[:-1])
        # GPU settlement can also deliver the due network/wireless notices,
        # invalidating their redundant queue forecasts at the same timestamp.
        due = [e["event"] for e in sim.events if e["time_s"] == 0.6]
        for name in ["gpu_compute_completed", "token_access_arrival", "downlink_done"]:
            self.assertIn(name, due)
        self.assertEqual(sim.mobility.sessions["S1"].mobility_check_count, 6)

    def test_cutoff_keeps_pending_unfinished_and_includes_boundary_check(self):
        out = ServingSimulator(moving(horizon=0.3)).run()
        self.assertEqual(out["summary"]["observation_end_s"], 0.3)
        self.assertEqual(out["summary"]["completed_turns"], 0)
        self.assertIsNone(out["summary"]["mean_full_turn_e2e_s"])
        self.assertEqual(out["mobility"]["summary"]["mobility_checks"], 2)
        self.assertEqual(out["mobility"]["summary"]["pending_moves_at_observation_end"], 2)
        self.assertTrue(all(e["time_s"] <= 0.3 for e in out["mobility"]["events"]))

    def test_same_clock_kv_retry_commits_before_mobility(self):
        c = moving(horizon=4, interval=0.1)
        c["edges"][1]["kv_capacity_bytes"] = 20
        c["sessions"][0]["turns"] = [{"input_tokens": 2, "output_tokens": 1},
                                        {"input_tokens": 1, "output_tokens": 1}]
        other = copy.deepcopy(c["sessions"][0])
        other.update(id="S2", access_edge_id="E2", execution_edge_id="E2",
                     turns=[{"input_tokens": 0, "output_tokens": 3}],
                     network={"wireless_down_bits_per_second": 8})
        c["sessions"].append(other)
        c["topology"]["edges"] = copy.deepcopy(c["edges"])
        sim = ServingSimulator(c); same = []
        for _ in range(300):
            event = sim.step()
            self.assertIsNotNone(event)
            if event[0] == 3.1:
                same.append(event[1])
                if event[1] == "mobility_check" and sim.mobility.sessions["S1"].mobility_check_count == 31:
                    break
        else:
            self.fail("Missing mobility check after KV recovery")
        self.assertIn("kv_retry", same[:-1])
        recovered = [e for e in sim.runtime.edges["E2"].kv.trace if e["reason"] == "PendingCommitRecovered"]
        self.assertEqual([e["time_s"] for e in recovered], [3.1])
        self.assertEqual(sim.runtime.sessions["S1"].current_turn.decode_done, 1)

    def test_zero_horizon_and_late_arrival_do_not_fabricate_sessions(self):
        c = moving(horizon=0); out = ServingSimulator(c).run()
        self.assertEqual(out["mobility"]["summary"]["mobility_checks"], 0)
        c["sessions"][0]["arrival_time"] = 1
        out = ServingSimulator(c).run()
        self.assertEqual(out["sessions"], []); self.assertEqual(out["mobility"]["sessions"], [])

    def test_multiturn_submission_does_not_reset_mobility_clock(self):
        c = moving(outputs=1, horizon=1.1)
        c["sessions"][0]["turns"] *= 2
        sim = ServingSimulator(c); sim.run()
        times = [e["time_s"] for e in sim.mobility.events if e["event"] == "mobility_check"]
        self.assertEqual(times, [0.15, 0.3, 0.45, 0.6, 0.75, 0.9, 1.05])
        self.assertEqual(sim.results()["turns"][1]["submitted_at"], 0.6)

    def test_advancing_beyond_mobility_horizon_is_rejected(self):
        sim = ServingSimulator(moving(horizon=0.3))
        with self.assertRaises(ValueError): sim.advance_to(0.4)

    def test_results_are_detached_snapshots(self):
        sim = ServingSimulator(moving()); sim.advance_to(0.3)
        out = sim.results(); out["mobility"]["sessions"][0]["pending_moves"].clear()
        self.assertEqual(len(sim.mobility.sessions["S1"].pending_moves), 2)
