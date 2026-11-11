"""Generated plans must execute in the existing resource/lifecycle engine."""
import copy
from dataclasses import asdict
from pathlib import Path
import sys
import unittest
sys.path[:0] = [str(Path(__file__).resolve().parents[1]/"src")]
from replacement.core.workload import WorkloadPlan, SessionPlan, TurnPlan
from replacement.simulation.serving import ServingSimulator
from test_serving import config


def generated():
    c = config(); c.pop("sessions")
    c["models"][0].update(output_limit_per_turn=3, context_window_tokens=100)
    c["observation_end_s"] = 3
    c["workload"] = dict(mode="poisson", arrival_rate_per_s=5, arrival_horizon_s=1,
                          model_id="m", turn_count=dict(min=1,max=3),
                          input_tokens=dict(min=0,max=2), output_tokens=dict(min=1,max=3))
    return c


def plan(c, turns, *, later=()):
    return WorkloadPlan((SessionPlan("known", "m", .1, "E", "E", tuple(turns)), *later), c["seed"], c.get("scenario", "unnamed"))


class GeneratedServingTests(unittest.TestCase):
    def test_real_plan_is_private_reusable_and_arrivals_stop(self):
        c = generated(); a = ServingSimulator(c); first = a.run()
        self.assertIn("workload", first)
        self.assertTrue(all(s["arrival_time"] <= 1 for s in first["sessions"]))
        self.assertEqual(first["summary"]["observation_end_s"], 3)
        from replacement.core.workload_generation import workload_from_dict
        shared = workload_from_dict(first["workload"]["plan"])
        self.assertEqual(first, ServingSimulator(c, workload_plan=shared).run())

    def test_zero_arrivals_no_division_and_no_post_cutoff_events(self):
        c = generated(); c["workload"]["arrival_rate_per_s"] = 0
        sim = ServingSimulator(c); out = sim.run()
        self.assertEqual(out["summary"]["planned_turns"], 0)
        self.assertEqual(out["sessions"], [])
        self.assertIsNone(out["summary"]["mean_full_turn_e2e_s"])
        self.assertEqual(sim.time_s, 3)
        self.assertIsNone(sim.step())

    def test_output_target_equals_cap_is_normal_and_context_exact(self):
        c = generated(); c["models"][0].update(context_window_tokens=201,output_limit_per_turn=200)
        c["workload"]["output_tokens"]["max"]=200
        c["edges"][0]["kv_capacity_bytes"]=1024
        c["observation_end_s"]=30
        out = ServingSimulator(c, workload_plan=plan(c,[TurnPlan(1,200)])).run()
        self.assertEqual(out["summary"]["completed_turns"], 1)
        self.assertIsNone(out["turns"][0]["reason"])
        self.assertEqual(out["turns"][0]["decode_done"],200)
        self.assertEqual(out["sessions"][0]["context_tokens"], 201)
        self.assertEqual(out["summary"]["final_kv_bytes"], 0)

    def test_static_over_cap_remains_output_length_limit(self):
        c = config(); c["models"][0]["output_limit_per_turn"] = 2
        c["sessions"][0]["turns"][0]["output_tokens"] = 3
        out = ServingSimulator(c).run()
        self.assertEqual(out["turns"][0]["decode_done"], 2)
        self.assertEqual(out["turns"][0]["reason"], "OutputLengthLimit")

    def test_context_is_checked_at_runtime_without_plan_trimming(self):
        c = generated(); c["models"][0]["context_window_tokens"] = 2
        p = plan(c,[TurnPlan(1,3)])
        out = ServingSimulator(c, workload_plan=p).run()
        self.assertEqual(out["workload"]["plan"]["sessions"][0]["turns"][0]["hidden_output_tokens"], 3)
        self.assertEqual(out["sessions"][0]["termination_reason"], "ContextLimit")
        self.assertEqual(out["sessions"][0]["context_tokens"], 2)
        self.assertEqual(out["summary"]["gpu_work"], 3)  # includes completed rejected next unit

    def test_kv_block_is_distinct_and_cutoff_retains_unfinished(self):
        c = generated(); c["edges"][0]["kv_capacity_bytes"] = 4
        out = ServingSimulator(c, workload_plan=plan(c,[TurnPlan(1,3)])).run()
        self.assertEqual(out["summary"]["blocked_sessions"], 1)
        self.assertEqual(out["workload"]["statistics"]["context_limit_sessions"], 0)
        self.assertEqual(out["workload"]["statistics"]["unfinished_sessions"], 1)
        self.assertIsNone(out["summary"]["mean_full_turn_e2e_s"])

    def test_arrival_window_does_not_end_session_or_later_turn(self):
        c = generated(); c["workload"]["arrival_horizon_s"] = .2
        out = ServingSimulator(c, workload_plan=plan(c,[TurnPlan(1,3),TurnPlan(1,2)])).run()
        self.assertEqual(out["summary"]["completed_turns"], 2)
        self.assertGreater(out["sessions"][0]["end_time"], .2)
        self.assertEqual(out["turns"][1]["submitted_at"],out["turns"][0]["received_at"])
        self.assertAlmostEqual(out["workload"]["statistics"]["session_lifetimes"][0]["lifetime_s"],out["sessions"][0]["end_time"]-.1)
        life = out["workload"]["statistics"]["session_lifetimes"][0]
        self.assertEqual(life["observed_lifetime_s"], life["lifetime_s"])

    def test_global_cutoff_also_applies_without_mobility(self):
        c = generated(); c["observation_end_s"] = c["workload"]["arrival_horizon_s"] = .15
        sim = ServingSimulator(c, workload_plan=plan(c,[TurnPlan(1,3)]))
        out = sim.run()
        self.assertEqual(out["summary"]["observation_end_s"], .15)
        self.assertEqual(out["summary"]["completed_turns"], 0)
        self.assertIsNone(sim.step());self.assertEqual(sim.time_s,.15)

    def test_future_plans_and_seeds_do_not_change_policy_snapshot(self):
        a = generated(); b = copy.deepcopy(a); b["seed"] = 99
        future = SessionPlan("future", "m", .9, "E", "E", (TurnPlan(2,3),))
        x = ServingSimulator(a, workload_plan=plan(a,[TurnPlan(1,2),TurnPlan(1,1)]))
        y = ServingSimulator(b, workload_plan=plan(b,[TurnPlan(1,3),TurnPlan(2,2)],later=(future,)))
        x.advance_to(.25);y.advance_to(.25)
        self.assertEqual(x.observation(),y.observation())
        self.assertEqual(x.events,y.events)
        encoded = str(asdict(y.observation()))
        for forbidden in ["hidden_output_tokens", "planned_turns", "future", "seed", "driver", "plan", "event_queue"]:
            self.assertNotIn(forbidden,encoded)
        def check_keys(value):
            if isinstance(value, dict):
                self.assertNotIn("queue", value)
                for item in value.values(): check_keys(item)
            elif isinstance(value, (tuple,list)):
                for item in value: check_keys(item)
        check_keys(asdict(y.observation()))
        self.assertEqual([s.session_id for s in y.observation().sessions], ["known"])
        self.assertEqual(y.observation().sessions[0].current_turn.input_tokens,1)

    def test_invalid_reused_plan_does_not_bypass_configuration(self):
        c = generated()
        for p in [plan(c,[TurnPlan(1,4)]),plan(c,[TurnPlan(9,2)])]:
            with self.assertRaises(ValueError): ServingSimulator(c,workload_plan=p)

    def test_observation_projects_only_current_byte_and_gpu_service_without_mutation(self):
        c=generated();c["workload"]["arrival_horizon_s"]=.5;c["observation_end_s"]=.5
        c["edges"][0]["area_id"]="A"
        c["topology"]=dict(areas=[dict(area_id="A",boundary_node="gA")],edges=copy.deepcopy(c["edges"]),
                            links=[],paths=[],allowed_serving_pairs=[["E","E"]],mobility_adjacency={},mobility_transitions=[])
        c["mobility"]=dict(check_interval_s=.05,transition_probabilities={"E":{"E":1}})
        sim=ServingSimulator(c,workload_plan=plan(c,[TurnPlan(1,3)]))
        for _ in range(30):
            if sim.step()==(.15,"mobility_check"):break
        self.assertEqual(sim.wireless.time_s,.1)
        trace=copy.deepcopy(sim.wireless.trace)
        self.assertEqual(sim.observation().wireless_transfers[0].transferred_bytes,.5)
        self.assertEqual(sim.wireless.trace,trace)
        for _ in range(30):
            if sim.step()==(.25,"mobility_check"):break
        observation=sim.observation()
        self.assertEqual(observation.edges[0].running[0].remaining_work,.5)
        self.assertEqual(observation.sessions[0].current_turn.partial_work,.5)
