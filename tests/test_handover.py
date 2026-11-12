"""Actual III.B.3 Handover: immutable provenance and serial old-output draining."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from replacement.simulation.serving import ServingSimulator
from test_mobility import moving


def switching(outputs=6, interval=0.45, horizon=3):
    c = moving(outputs=outputs, interval=interval, horizon=horizon)
    c["handover"] = {"enabled": True}
    return c


class HandoverTests(unittest.TestCase):
    def test_prompt_is_protected_and_actual_access_changes_after_arrival(self):
        sim = ServingSimulator(switching(interval=0.15))
        sim.advance_to(0.15)
        self.assertEqual(sim.runtime.sessions["S1"].access_edge_id, "E")
        sim.advance_to(0.2)
        self.assertEqual(sim.runtime.sessions["S1"].access_edge_id, "E2")
        self.assertEqual(sim.runtime.sessions["S1"].execution_edge_id, "E2")

    def test_old_wired_then_extra_forward_then_wireless_pipeline(self):
        c = switching(outputs=2, horizon=1.2)
        # One effective planned move, E -> E2; no second Handover.
        c["mobility"]["transition_probabilities"]["E2"] = {"E2": 1}
        sim = ServingSimulator(c); out = sim.run()
        self.assertEqual(out["summary"]["stage"], "S3-B")
        self.assertEqual([t["access_edge_id"] for t in out["output_tokens"]], ["E", "E2"])
        self.assertEqual([t["received_at"] for t in out["output_tokens"]], [0.7, 0.8])
        forwarded = [f for f in out["network_flows"] if f["flow_type"] == "handover"]
        self.assertEqual(len(forwarded), 1)
        self.assertEqual((forwarded[0]["created_at"], forwarded[0]["ready_bytes"], forwarded[0]["transferred_bytes"]), (.5, 1, 1))
        self.assertEqual(out["summary"]["gpu_work"], 3)
        self.assertEqual(out["summary"]["final_kv_bytes"], 0)

    def test_inflight_wireless_token_finishes_before_switch(self):
        c = switching(outputs=4, interval=0.55, horizon=2)
        c["mobility"]["transition_probabilities"]["E2"] = {"E2": 1}
        out = ServingSimulator(c).run()
        handovers = [e for e in out["handover"]["events"] if e["event"] == "handover_start"]
        self.assertEqual([e["time_s"] for e in handovers], [0.6])
        self.assertEqual(out["output_tokens"][0]["received_at"], .6)
        self.assertEqual(sum(e["event"] == "downlink_start" and e["unit_index"] == 1 for e in out["events"]), 1)

    def test_draining_blocks_next_switch_and_preserves_fifo_edges(self):
        c = switching(outputs=6, interval=.2, horizon=3)
        c["network"]["wireless_down_bits_per_second"] = 8
        out = ServingSimulator(c).run()
        events = out["handover"]["events"]
        starts = [e for e in events if e["event"] == "handover_start"]
        ends = [e for e in events if e["event"] == "handover_drain_end"]
        self.assertEqual([(e["source_edge_id"], e["target_edge_id"]) for e in starts[:2]], [("E", "E2"), ("E2", "E3")])
        if len(starts) > 1:
            self.assertGreaterEqual(starts[1]["time_s"], ends[0]["time_s"])
        ids = [tuple(t["token_id"]) for t in out["output_tokens"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_actual_minimum_interval_and_planned_frequency_rejections(self):
        c = switching(outputs=10, interval=.1, horizon=2)
        c["mobility"]["min_inter_move_interval_s"] = .5
        out = ServingSimulator(c).run()
        self.assertGreater(out["mobility"]["summary"]["moves_rejected_min_interval"], 0)
        starts = [e["time_s"] for e in out["handover"]["events"] if e["event"] == "handover_start"]
        self.assertGreaterEqual(len(starts), 2)
        self.assertTrue(all(round(b-a, 12) >= .5 for a,b in zip(starts, starts[1:])))

    def test_session_ends_instead_of_spurious_handover_at_last_delivery(self):
        c = switching(outputs=1, interval=.6, horizon=1)
        out = ServingSimulator(c).run()
        self.assertEqual(out["summary"]["completed_turns"], 1)
        self.assertEqual(out["handover"]["summary"]["actual_handovers"], 0)

    def test_disabled_mode_keeps_original_s3a(self):
        c = switching(); c["handover"]["enabled"] = False
        a = ServingSimulator(c).run(); c.pop("handover")
        self.assertEqual(a, ServingSimulator(c).run())

    def test_enabled_handover_requires_mobility(self):
        c = switching(); c.pop("mobility")
        with self.assertRaises(ValueError): ServingSimulator(c)

    def test_zero_idle_next_turn_upload_uses_post_handover_access(self):
        c = switching(outputs=1, interval=.6, horizon=2)
        c["sessions"][0]["turns"] *= 2
        out = ServingSimulator(c).run()
        self.assertEqual(out["turns"][1]["submitted_at"], out["turns"][0]["received_at"])
        arrivals = [e for e in out["events"] if e["event"] == "upload_start" and e["turn_index"] == 2]
        self.assertEqual(arrivals[0]["time_s"], .6)
        self.assertEqual(out["sessions"][0]["execution_edge_id"], "E2")

    def test_cutoff_preserves_incomplete_drain_and_pending(self):
        c = switching(outputs=6, interval=.45, horizon=.6)
        out = ServingSimulator(c).run()
        self.assertEqual(out["summary"]["observation_end_s"], .6)
        self.assertEqual(out["summary"]["completed_turns"], 0)
        self.assertIsNone(out["summary"]["mean_full_turn_e2e_s"])
        self.assertTrue(out["handover"]["sessions"][0]["draining"])
        self.assertIsNone(out["handover"]["events"][0].get("drain_end_s"))

    def test_migration_guard_never_blocks_legal_access_handover(self):
        sim = ServingSimulator(switching(interval=.15)); sim.advance_to(0)
        lease = sim.migration_guard.try_begin("S1", "E2", "E3")
        self.assertIsNone(sim.migration_guard.try_begin("S1", "E2", "E"))
        sim.advance_to(.2)
        self.assertEqual(sim.runtime.sessions["S1"].access_edge_id, "E2")
        self.assertIs(sim.migration_guard.active["S1"], lease)
        self.assertEqual(sim.runtime.sessions["S1"].execution_edge_id, "E2")
        sim.run()
        self.assertNotIn("S1", sim.migration_guard.active)

    def test_policy_observation_has_current_frozen_transfers_not_controllers(self):
        from dataclasses import FrozenInstanceError, asdict
        sim = ServingSimulator(switching()); sim.advance_to(.46)
        observation = sim.observation()
        self.assertTrue(observation.network_transfers)
        self.assertTrue(observation.handover_states[0].draining)
        self.assertEqual(observation.sessions[0].access_edge_id,"E2")
        with self.assertRaises(FrozenInstanceError): observation.network_transfers[0].rate_bps = 0
        frozen = asdict(observation)
        sim.advance_to(.7)
        self.assertEqual(asdict(observation),frozen)
        encoded = str(frozen)
        for banned in ["hidden_output_tokens", "rng", "driver", "forecast", "event_version"]:
            self.assertNotIn(banned, encoded)

    def test_cyclic_pending_waits_for_drain_and_uses_one_wired_response_share(self):
        c=switching(outputs=6,interval=.2,horizon=8)
        c["mobility"]["transition_probabilities"]["E2"]={"E":1}
        c["topology"]["mobility_adjacency"]["E2"]=["E"]
        c["network"]["wireless_down_bits_per_second"]=8
        out=ServingSimulator(c).run()
        starts=[e for e in out["handover"]["events"] if e["event"]=="handover_start"]
        # B.3 step4 precedes a NEW radio start: at .4 move2 freezes Token1.
        # Forward .4-.5, UE .5-1.5; next five old Tokens wire1.5-2.0,
        # extra-forward2.0-2.5, radio starts2.1 and drains through7.1.
        self.assertEqual([e["time_s"] for e in starts],[.2,.4,1.5])
        self.assertEqual(starts[-1]["drain_end_s"],7.1)
        self.assertEqual([t["received_at"] for t in out["output_tokens"]],[1.5,3.1,4.1,5.1,6.1,7.1])
        self.assertEqual(out["summary"]["gpu_work"],7)
        self.assertEqual(sum(f['transferred_bytes'] for f in out['network_flows'] if f['flow_type']=='handover'),6)
        self.assertGreater(out["handover"]["summary"]["draining_delayed_moves"],0)
        self.assertEqual(out["turns"][0]["generation_ended_at"],.9)
        flows={f["flow_id"]:f for f in out["network_flows"]}
        for row in out["network_events"]:
            if row.get("kind")=="allocation":
                response=[fid for fid in row["active_flow_ids"] if flows[fid]["flow_type"] in ("response","handover")]
                self.assertLessEqual(len(response),1)
