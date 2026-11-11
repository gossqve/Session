"""S2-B real Serving hand timelines and safety counterexamples."""
import copy
from dataclasses import asdict
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from replacement.simulation.serving import ServingSimulator
from test_serving import config


def remote(outputs=1):
    c=config();c["sessions"]=c["sessions"][:1];c["edges"][0]["area_id"]="A"
    e=copy.deepcopy(c["edges"][0]);e.update(id="E2",area_id="B");c["edges"].append(e)
    c["sessions"][0].update(execution_edge_id="E2",turns=[{"input_tokens":1,"output_tokens":outputs}])
    links=[]
    for lid,a,b in [("Ea","E","gA"),("ab","gA","gB"),("b2","gB","E2"),("2b","E2","gB"),("ba","gB","gA"),("aE","gA","E")]:
        links.append(dict(link_id=lid,source_node=a,target_node=b,capacity_bps=80))
    c["topology"]={"areas":[dict(area_id="A",boundary_node="gA"),dict(area_id="B",boundary_node="gB")],"edges":copy.deepcopy(c["edges"]),"links":links,
        "paths":[dict(path_id="up",source_node="E",target_node="E2",link_ids=["Ea","ab","b2"]),dict(path_id="down",source_node="E2",target_node="E",link_ids=["2b","ba","aE"])],
        "allowed_serving_pairs":[["E","E2"],["E","E"],["E2","E"]],"mobility_adjacency":{},"mobility_transitions":[]}
    return c

class NetworkServingTests(unittest.TestCase):
    def test_summary_stage_with_topology_is_s2c(self):
        out = ServingSimulator(remote()).run()
        self.assertEqual(out["summary"]["stage"], "S2-C")

    def test_remote_hand_timeline_and_logical_byte_counts(self):
        sim=ServingSimulator(remote());out=sim.run()
        self.assertEqual(out["turns"][0]["e2e_s"],0.6)
        self.assertEqual(out["turns"][0]["gpu_ready_time"],0.2)
        token=out["output_tokens"][0]
        self.assertEqual((token["generated_at"],token["wired_arrived_at"],token["wireless_started_at"],token["received_at"]),(0.4,0.5,0.5,0.6))
        self.assertEqual(sum(f["transferred_bytes"] for f in out["network_flows"]),2)
        self.assertEqual(out["summary"]["gpu_work"],2)
        self.assertEqual(out["summary"]["peak_kv_bytes"],8)

    def test_local_topology_has_no_wired_flow(self):
        c=remote();c["sessions"][0]["execution_edge_id"]="E"
        out=ServingSimulator(c).run()
        self.assertEqual(out["turns"][0]["e2e_s"],0.4)
        self.assertEqual(out["network_flows"],[])

    def test_streaming_one_persistent_response_flow_fifo_overlap(self):
        c=remote(3);c["network"]["wireless_down_bits_per_second"]=40
        out=ServingSimulator(c).run()
        self.assertEqual([t["generated_at"] for t in out["output_tokens"]],[0.4,0.5,0.6])
        self.assertEqual([t["wired_arrived_at"] for t in out["output_tokens"]],[0.5,0.6,0.7])
        self.assertEqual([t["wired_cumulative_bytes"] for t in out["output_tokens"]],[1,2,3])
        self.assertEqual(len({t["wired_flow_id"] for t in out["output_tokens"]}),1)
        self.assertEqual([t["received_at"] for t in out["output_tokens"]],[0.7,0.9,1.1])
        self.assertEqual(out["turns"][0]["e2e_s"],1.1)
        flows=[f for f in out["network_flows"] if f["flow_type"]=="response"]
        self.assertEqual(len(flows),1);self.assertEqual(flows[0]["ready_bytes"],3)

    def test_response_waits_for_future_data_then_finishes_once(self):
        c=remote(3);c["models"][0]["decode_work_per_token"]=3
        sim=ServingSimulator(c);sim.advance_to(0.7)
        self.assertIn("waiting_for_data",[f.status for f in sim.network.flows.values()])
        out=sim.run();self.assertEqual(out["summary"]["completed_turns"],1)
        self.assertTrue(all(f["status"]=="completed" for f in out["network_flows"]))

    def test_zero_input_zero_output_and_limits(self):
        for outputs in (0,1):
            c=remote(outputs);c["sessions"][0]["turns"][0]["input_tokens"]=0
            out=ServingSimulator(c).run();self.assertEqual(out["summary"]["completed_turns"],1)
        c=remote(5);c["models"][0]["context_window_tokens"]=2
        out=ServingSimulator(c).run();self.assertEqual(out["summary"]["completed_turns"],0)
        self.assertEqual(len(out["output_tokens"]),1);self.assertEqual(out["turns"][0]["delivered"],1)
        c=remote(5);c["models"][0]["output_limit_per_turn"]=1
        self.assertEqual(ServingSimulator(c).run()["turns"][0]["decode_done"],1)

    def test_kvblocked_token_not_supplied_and_finite_quiescence(self):
        c=remote(3);c["edges"][1]["kv_capacity_bytes"]=4
        c["topology"]["edges"]=copy.deepcopy(c["edges"])
        out=ServingSimulator(c).run();self.assertEqual(out["output_tokens"],[])
        self.assertIsNone(out["summary"]["mean_full_turn_e2e_s"])
        self.assertEqual(len(out["network_flows"]),1)
        self.assertEqual(out["summary"]["blocked_sessions"],1)

    def test_reachable_but_not_permitted_rejected_at_arrival(self):
        c=remote();c["topology"]["allowed_serving_pairs"]=[["E","E"]]
        with self.assertRaises(ValueError):ServingSimulator(c).run()
        c=remote();c["topology"]["paths"].pop()
        with self.assertRaises(ValueError):ServingSimulator(c)

    def test_bidirectional_disjoint_sessions_run_concurrently(self):
        c=remote();other=copy.deepcopy(c["sessions"][0]);other.update(id="S2",access_edge_id="E2",execution_edge_id="E");c["sessions"].append(other)
        out=ServingSimulator(c).run();self.assertEqual([r["e2e_s"] for r in out["turns"]],[0.6,0.6])
        self.assertEqual(sum(f["transferred_bytes"] for f in out["network_flows"]),4)

    def test_shared_link_conflict_never_produces_e2e(self):
        c=remote();other=copy.deepcopy(c["sessions"][0]);other["id"]="S2";c["sessions"].append(other)
        from replacement.network.allocator import DisjointPathAllocator
        with self.assertRaisesRegex(NotImplementedError,"S2-C"):
            ServingSimulator(c, network_allocator=DisjointPathAllocator()).run()

    def test_checkpoint_determinism_future_privacy_and_old_origins(self):
        c=remote(3);changed=copy.deepcopy(c);changed["sessions"][0]["turns"][0]["output_tokens"]=9
        a,b=ServingSimulator(c),ServingSimulator(changed)
        a.advance_to(0.45);b.advance_to(0.45)
        self.assertEqual(a.observation(),b.observation());self.assertEqual(a.events,b.events)
        self.assertEqual(a.network.trace,b.network.trace)
        self.assertEqual(a.network.time_s,a.time_s)
        self.assertEqual(a.wireless.time_s,a.time_s)
        self.assertEqual(ServingSimulator(c).run(),ServingSimulator(copy.deepcopy(c)).run())

    def test_wireless_update_settles_old_rate_without_reupload(self):
        c=remote();sim=ServingSimulator(c);sim.advance_to(0.05)
        sim.update_wireless_rate("S1","up",40)
        out=sim.run();self.assertEqual(out["turns"][0]["gpu_ready_time"],0.25)
        self.assertEqual(out["turns"][0]["e2e_s"],0.65)

    def test_same_area_remote_and_multiturn_zero_idle(self):
        c=remote();c["edges"][1]["area_id"]="A";c["topology"]["edges"]=copy.deepcopy(c["edges"])
        c["topology"]["links"]=[dict(link_id="up",source_node="E",target_node="E2",capacity_bps=80),dict(link_id="down",source_node="E2",target_node="E",capacity_bps=80)]
        c["topology"]["paths"]=[dict(path_id="up",source_node="E",target_node="E2",link_ids=["up"]),dict(path_id="down",source_node="E2",target_node="E",link_ids=["down"])]
        c["sessions"][0]["turns"]*=2
        out=ServingSimulator(c).run();self.assertEqual(out["summary"]["completed_turns"],2)
        self.assertEqual(out["turns"][1]["submitted_at"],out["turns"][0]["received_at"])

    def test_shannon_config_adapter_and_no_double_conversion(self):
        c=remote()
        for direction in ("up","down"):
            del c["network"][f"wireless_{direction}_bits_per_second"]
            c["network"][f"wireless_{direction}"]={"bandwidth_hz":80,"snr_linear":1,"efficiency":1}
        self.assertEqual(ServingSimulator(c).run()["turns"][0]["e2e_s"],0.6)
        c["network"]["wireless_up_bits_per_second"]=80
        with self.assertRaises(ValueError):ServingSimulator(c)

    def test_session_direction_override_can_change_rate_representation(self):
        c=remote()
        c["sessions"][0]["network"]={"wireless_up":{"bandwidth_hz":80,"snr_linear":1,"efficiency":1}}
        self.assertEqual(ServingSimulator(c).run()["turns"][0]["e2e_s"],0.6)
        c=remote();del c["network"]["wireless_down_bits_per_second"]
        c["network"]["wireless_down"]={"bandwidth_hz":80,"snr_linear":1,"efficiency":1}
        c["sessions"][0]["network"]={"wireless_down_bits_per_second":40}
        self.assertEqual(ServingSimulator(c).run()["turns"][0]["e2e_s"],0.7)

    def test_remote_pending_commit_recovery_no_recompute(self):
        c=remote();c["edges"][1]["kv_capacity_bytes"]=20
        c["sessions"][0]["turns"]=[{"input_tokens":2,"output_tokens":1},{"input_tokens":1,"output_tokens":1}]
        other=copy.deepcopy(c["sessions"][0]);other.update(id="S2",access_edge_id="E2",execution_edge_id="E2",
            turns=[{"input_tokens":0,"output_tokens":3}],network={"wireless_down_bits_per_second":8})
        c["sessions"].append(other);c["topology"]["edges"]=copy.deepcopy(c["edges"])
        c["topology"]["allowed_serving_pairs"].append(["E2","E2"])
        out=ServingSimulator(c).run()
        self.assertEqual(out["summary"]["completed_turns"],3)
        self.assertEqual(out["summary"]["gpu_work"],8)
        recovered=[e for e in out["kv_events"]["E2"] if e["reason"]=="PendingCommitRecovered"]
        self.assertEqual(len(recovered),1)
        token=next(t for t in out["output_tokens"] if tuple(t["token_id"])==("S1",1,1))
        self.assertEqual(token["generated_at"],recovered[0]["time_s"])
        self.assertGreater(token["wired_arrived_at"],token["generated_at"])

    def test_generated_source_not_rebound_by_later_current_access_field(self):
        sim=ServingSimulator(remote());sim.advance_to(0.45)
        # Component isolation check, not a Handover event/controller.
        sim.runtime.sessions["S1"].access_edge_id="E2"
        out=sim.run();token=out["output_tokens"][0]
        self.assertEqual(token["access_edge_id"],"E")
        response=next(f for f in out["network_flows"] if f["flow_type"]=="response")
        self.assertEqual(response["path"]["target_node"],"E")
        self.assertEqual(token["received_at"],0.6)
