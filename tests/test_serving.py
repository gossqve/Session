"""Independent hand calculations and unified S1-D integration contracts."""
import copy
from dataclasses import asdict
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from replacement.simulation.serving import ServingSimulator


def config(slots=1, capacity=256):
    return {"scenario": "hand", "seed": 7, "models": [
        {"id": "m", "layers": 1, "kv_heads": 1, "head_dim": 1, "element_bytes": 2,
         "context_window_tokens": 100, "output_limit_per_turn": 10,
         "prefill_work_per_token": 1, "decode_work_per_token": 1}],
        "edges": [{"id": "E", "gpu_work_per_second": 10, "gpu_slots": slots,
                   "kv_capacity_bytes": capacity, "deployed_models": ["m"]}],
        "network": {"text_bytes_per_token": 1, "wireless_up_bits_per_second": 80,
                    "wireless_down_bits_per_second": 80},
        "sessions": [{"id": name, "model_id": "m", "arrival_time": 0,
                      "access_edge_id": "E", "execution_edge_id": "E",
                      "turns": [{"input_tokens": 1, "output_tokens": 1}]} for name in ["S1", "S2"]]}


class ServingTests(unittest.TestCase):
    def test_summary_stage_without_topology_is_s1d(self):
        out = ServingSimulator(config()).run()
        self.assertEqual(out["summary"]["stage"], "S1-D")

    def test_a_two_session_hand_e2e_prefill_decode_retains_slot(self):
        sim = ServingSimulator(config())
        out = sim.run()
        rows = out["turns"]
        self.assertEqual([r["e2e_s"] for r in rows], [0.4, 0.6])
        self.assertEqual([r["gpu_ready_time"] for r in rows], [0.1, 0.1])
        self.assertEqual([r["gpu_start_time"] for r in rows], [0.1, 0.3])
        self.assertEqual([r["gpu_queue_wait_s"] for r in rows], [0, 0.2])
        self.assertEqual([r["generation_ended_at"] for r in rows], [0.3, 0.5])
        self.assertEqual(out["summary"]["mean_full_turn_e2e_s"], 0.5)

    def test_b_many_units_one_slot_no_insertion_between_tokens(self):
        c = config()
        c["sessions"][0]["turns"] = [{"input_tokens": 3, "output_tokens": 3}]
        c["sessions"][1].update(arrival_time=0.35, turns=[{"input_tokens": 0, "output_tokens": 1}])
        third = copy.deepcopy(c["sessions"][1])
        third.update(id="S3", arrival_time=0.4)
        c["sessions"].append(third)
        sim = ServingSimulator(c)
        out = sim.run()
        self.assertEqual([r["gpu_start_time"] for r in out["turns"]], [0.3, 0.9, 1.0])
        self.assertEqual([r["gpu_queue_wait_s"] for r in out["turns"]], [0, 0.55, 0.6])
        queue = sim.runtime.edges["E"].compute.scheduler
        self.assertEqual(len(queue.tasks), 3)  # six S1 units share ONE entry
        for event in out["events"]:
            if event["event"] == "resource_state":
                self.assertLessEqual(len(event["running_turns"]), 1)
                self.assertEqual(len(event["running_turns"]), len(set(event["running_turns"])))

    def test_c_two_turn_equal_share_then_full_capacity(self):
        c = config(slots=2)
        c["sessions"][1]["turns"][0]["output_tokens"] = 3
        sim = ServingSimulator(c)
        out = sim.run()
        shared = [e for e in out["events"] if e["event"] == "resource_state" and len(e["running_turns"]) == 2]
        self.assertTrue(shared)
        self.assertTrue(all(list(e["rates"].values()) == [5, 5] for e in shared))
        self.assertEqual([r["generation_ended_at"] for r in out["turns"]], [0.5, 0.7])
        self.assertEqual([r["e2e_s"] for r in out["turns"]], [0.6, 0.8])
        self.assertTrue(any(e["event"] == "resource_state" and e["rates"] == {"S2:1": 10}
                            for e in out["events"]))

    def test_d_multiturn_context_zero_idle_and_release(self):
        c = config()
        for s in c["sessions"]:
            s["turns"] *= 2
        out = ServingSimulator(c).run()
        self.assertEqual(out["summary"]["completed_turns"], 4)
        self.assertEqual(out["summary"]["mean_full_turn_e2e_s"], 0.45)
        for sid in ["S1", "S2"]:
            rows = [r for r in out["turns"] if r["session_id"] == sid]
            self.assertEqual(rows[1]["submitted_at"], rows[0]["received_at"])
            self.assertEqual([r["context_tokens"] for r in rows], [2, 4])
            self.assertEqual(sum(r["prefill_done"] for r in rows), 2)
        self.assertEqual([s["context_tokens"] for s in out["sessions"]], [4, 4])
        self.assertEqual(out["resources"][0]["final_kv_bytes"], 0)

    def test_e_distinct_models_work_and_kv(self):
        c = config(slots=2)
        second = copy.deepcopy(c["models"][0])
        second.update(id="m2", element_bytes=4, prefill_work_per_token=2, decode_work_per_token=3)
        c["models"].append(second)
        c["edges"][0]["deployed_models"].append("m2")
        c["sessions"][1]["model_id"] = "m2"
        out = ServingSimulator(c).run()
        self.assertEqual([r["gpu_service_work"] for r in out["turns"]], [2, 5])
        self.assertEqual([r["authoritative_kv_bytes"] for r in out["turns"]], [8, 16])
        self.assertEqual(out["summary"]["gpu_work"], 7)
        self.assertEqual([s["model_id"] for s in out["sessions"]], ["m", "m2"])

    def recovering(self):
        c = config(capacity=12)
        c["sessions"][0]["turns"] = [{"input_tokens": 2, "output_tokens": 1}]
        c["sessions"][1]["turns"] = [{"input_tokens": 0, "output_tokens": 1}]
        c["sessions"][1]["network"] = {"wireless_down_bits_per_second": 8}
        return c

    def test_f_natural_kv_block_recovery_no_recompute_e2e(self):
        sim = ServingSimulator(self.recovering())
        out = sim.run()
        a = out["turns"][0]
        self.assertEqual((a["block_count"], a["blocked_time_s"], a["gpu_queue_wait_s"]), (1, 0.6, 0))
        self.assertEqual(a["e2e_s"], 1.2)
        self.assertEqual(a["decode_done"], 1)
        self.assertEqual(a["delivered"], 1)
        self.assertEqual(out["summary"]["gpu_work"], 4)
        self.assertEqual(sum(len(e.compute.tasks) for e in sim.runtime.edges.values()), 4)
        self.assertEqual(out["summary"]["completed_turns"], 2)
        self.assertTrue(any(e["event"] == "pending_committed" for e in out["events"]))

    def test_g_permanent_block_and_context_failure_are_not_success(self):
        c = config(capacity=4)
        c["sessions"][0]["turns"][0]["input_tokens"] = 2
        out = ServingSimulator(c).run()
        self.assertEqual(out["summary"]["completed_turns"], 0)
        self.assertIsNone(out["summary"]["mean_full_turn_e2e_s"])
        self.assertEqual(out["summary"]["blocked_sessions"], 2)
        self.assertTrue(all(r["status"] == "blocked" for r in out["turns"]))
        c = config()
        c["models"][0]["context_window_tokens"] = 1
        out = ServingSimulator(c).run()
        self.assertEqual(out["summary"]["completed_turns"], 0)
        self.assertEqual(out["summary"]["blocked_sessions"], 0)
        self.assertTrue(all(s["termination_reason"] == "ContextLimit" for s in out["sessions"]))

    def test_h_streaming_fifo_overlap_waits_for_last_output(self):
        c = config()
        c["sessions"] = c["sessions"][:1]
        c["sessions"][0]["turns"][0]["output_tokens"] = 3
        c["network"]["wireless_down_bits_per_second"] = 8
        out = ServingSimulator(c).run()
        r = out["turns"][0]
        self.assertEqual((r["generation_ended_at"], r["received_at"], r["e2e_s"]), (0.5, 3.3, 3.3))
        delivered = [e["unit_index"] for e in out["events"] if e["event"] == "downlink_done"]
        self.assertEqual(delivered, [1, 2, 3])

    def test_i_deterministic_same_clock_and_obsolete_predictions(self):
        c = config(slots=2)
        third = copy.deepcopy(c["sessions"][0])
        third.update(id="S3", arrival_time=0.2)
        c["sessions"].append(third)
        a, b = ServingSimulator(c), ServingSimulator(copy.deepcopy(c))
        self.assertEqual(a.run(), b.run())
        self.assertGreater(a.ignored_predictions, 0)

    def test_j_same_prefix_different_future_is_causal(self):
        c = config()
        changed = copy.deepcopy(c)
        changed["sessions"][0]["turns"][0]["output_tokens"] = 9
        changed["sessions"][0]["turns"].append({"input_tokens": 99, "output_tokens": 99})
        future = copy.deepcopy(changed["sessions"][1])
        future.update(id="future", arrival_time=5)
        changed["sessions"].append(future)
        a, b = ServingSimulator(c), ServingSimulator(changed)
        a.advance_to(0.25)
        b.advance_to(0.25)
        self.assertEqual(a.observation(), b.observation())
        self.assertEqual(a.events, b.events)
        self.assertEqual(a.runtime.edges["E"].compute.scheduler.rates, b.runtime.edges["E"].compute.scheduler.rates)
        self.assertEqual(a.runtime.edges["E"].kv.can_fit(4), b.runtime.edges["E"].kv.can_fit(4))
        self.assertNotIn("future", a.runtime.sessions)
        self.assertNotIn("future", b.runtime.sessions)
        self.assertNotIn("hidden_output_tokens", str(asdict(a.observation())))

    def test_isolated_edges_and_late_arrivals(self):
        c = config()
        e = copy.deepcopy(c["edges"][0])
        e["id"] = "E2"
        c["edges"].append(e)
        c["sessions"][1].update(access_edge_id="E2", execution_edge_id="E2", arrival_time=1)
        sim = ServingSimulator(c)
        sim.advance_to(0.5)
        self.assertEqual(list(sim.runtime.sessions), ["S1"])
        out = sim.run()
        self.assertEqual([r["e2e_s"] for r in out["turns"]], [0.4, 0.4])
        self.assertEqual(out["summary"]["gpu_queue_wait_s"], 0)

    def test_output_cap_zero_reply_and_context_drains_legal_output(self):
        c = config()
        c["sessions"] = c["sessions"][:1]
        c["models"][0]["output_limit_per_turn"] = 1
        c["sessions"][0]["turns"] = [{"input_tokens": 1, "output_tokens": 9}, {"input_tokens": 0, "output_tokens": 0}]
        out = ServingSimulator(c).run()
        self.assertEqual(out["summary"]["completed_turns"], 2)
        self.assertEqual([r["decode_done"] for r in out["turns"]], [1, 0])
        c["models"][0].update(output_limit_per_turn=10, context_window_tokens=2)
        c["sessions"][0]["turns"] = [{"input_tokens": 1, "output_tokens": 3}]
        c["network"]["wireless_down_bits_per_second"] = 8
        out = ServingSimulator(c).run()
        self.assertEqual(out["summary"]["completed_turns"], 0)
        self.assertEqual(out["turns"][0]["delivered"], 1)
        self.assertEqual(out["turns"][0]["received_at"], 1.3)
        self.assertEqual(out["resources"][0]["final_kv_bytes"], 0)

    def test_checkpoint_processes_all_same_time_ready_events(self):
        sim = ServingSimulator(config(slots=2))
        sim.advance_to(0.1)
        self.assertEqual([s.current_turn.gpu_ready_time for s in sim.runtime.sessions.values()], [0.1, 0.1])
        self.assertEqual(list(sim.runtime.edges["E"].compute.scheduler.rates.values()), [5, 5])

    def test_recovery_next_unit_reenters_fcfs_excludes_blocked_time(self):
        c = config(capacity=16)
        c["sessions"][0]["turns"] = [{"input_tokens": 2, "output_tokens": 2}]
        c["sessions"][1]["turns"] = [{"input_tokens": 0, "output_tokens": 2}]
        c["sessions"][1]["network"] = {"wireless_down_bits_per_second": 8}
        slow = copy.deepcopy(c["models"][0])
        slow.update(id="slow", decode_work_per_token=2)
        c["models"].append(slow)
        c["edges"][0]["deployed_models"].append("slow")
        third = copy.deepcopy(c["sessions"][1])
        third.update(id="S3", model_id="slow", arrival_time=2,
                     turns=[{"input_tokens": 0, "output_tokens": 1}], network={})
        c["sessions"].append(third)
        sim = ServingSimulator(c)
        out = sim.run()
        row = out["turns"][0]
        self.assertEqual((row["gpu_queue_wait_s"], row["blocked_time_s"], row["e2e_s"]), (0.1, 1.6, 2.4))
        units = [t for t in sim.runtime.edges["E"].compute.tasks.values() if t.session_id == "S1"]
        self.assertEqual(len(units), 4)
        self.assertEqual(units[-1].start_time, 2.2)
        self.assertEqual(row["gpu_service_work"], 4)
