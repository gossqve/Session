"""Section E22/35/37a/39: actual events, partial Byte and censoring oracles."""
import unittest
from test_s3c_integration import scenario
from test_handover_completion import once
from replacement.simulation.serving import ServingSimulator


class S3CEvaluationTests(unittest.TestCase):
    def test_partial_forward_is_half_byte_not_original_or_three_hops(self):
        out=ServingSimulator(once(outputs=4,interval=.45,horizon=.55)).run()
        e=out['evaluation']
        self.assertEqual(e['transport']['handover_forward_bytes'],.5)
        self.assertEqual(e['transport']['original_response_bytes'],1)
        self.assertEqual(e['transport']['wireless_download_bytes'],0)
        self.assertEqual(e['summary']['right_censored_turns'],1)
        self.assertEqual(e['unfinished_turns'][0]['right_censored_e2e_lower_bound_s'],.55)
        self.assertIsNone(e['summary']['mean_full_turn_e2e_s'])
        self.assertIsNone(e['summary']['mean_completed_full_turn_e2e_s'])

    def test_future_unsubmitted_count_has_no_fabricated_submission(self):
        c=once(outputs=6,interval=.45,horizon=.6)
        c['sessions'][0]['turns']*=3
        e=ServingSimulator(c).run()['evaluation']
        self.assertEqual((e['summary']['planned_turns'],e['summary']['submitted_turns'],e['summary']['unsubmitted_turns']),(3,1,2))
        self.assertEqual(len(e['unfinished_turns']),1)
        self.assertTrue(e['unfinished_turns'][0]['right_censored'])

    def test_terminated_failure_is_not_right_censored(self):
        c=once(outputs=3,interval=.45,horizon=2)
        c['models'][0]['context_window_tokens']=1
        e=ServingSimulator(c).run()['evaluation']
        self.assertEqual(e['summary']['failed_submitted_turns'],1)
        self.assertEqual(e['summary']['right_censored_turns'],0)
        self.assertIsNone(e['unfinished_turns'][0]['right_censored_e2e_lower_bound_s'])
        self.assertEqual(e['unfinished_turns'][0]['reason'],'ContextLimit')

    def test_kvblocked_work_is_preserved_and_separately_censored(self):
        c=once(outputs=4,interval=.45,horizon=.55)
        for edge in c['edges']:edge['kv_capacity_bytes']=4
        c['topology']['edges']=[dict(e) for e in c['edges']]
        out=ServingSimulator(c).run();e=out['evaluation']
        self.assertEqual(out['summary']['gpu_work'],2)
        self.assertEqual(e['unfinished_turns'][0]['reason'],'KVBlocked')
        self.assertEqual(e['summary']['right_censored_turns'],1)
        self.assertEqual(e['summary']['final_kv_bytes'],4)

    def test_complete_hand_fixture_uses_full_e2e_and_piecewise_service(self):
        e=ServingSimulator(scenario()).run()['evaluation']
        self.assertEqual(e['summary']['mean_full_turn_e2e_s'],.95)
        self.assertEqual(e['summary']['mean_completed_full_turn_e2e_s'],.95)
        self.assertEqual(e['summary']['p95_full_turn_e2e_s'],1.4)
        self.assertEqual(e['summary']['unsubmitted_turns'],0)
        self.assertEqual(e['unfinished_turns'],[])
        self.assertAlmostEqual(e['summary']['gpu_busy_edge_time_s'],.9)
        self.assertAlmostEqual(e['summary']['gpu_running_turn_time_s'],1.5)  #2*.6+.2+.1
        self.assertEqual(e['transport']['handover_forward_bytes'],2)

    def test_evaluation_is_detached_and_does_not_advance_resources(self):
        sim=ServingSimulator(once(outputs=4,interval=.45,horizon=2));sim.advance_to(.55)
        first=sim.results()['evaluation'];before=sim.observation()
        first['transport']['handover_forward_bytes']=-1
        self.assertEqual(sim.results()['evaluation']['transport']['handover_forward_bytes'],.5)
        self.assertEqual(before,sim.observation())

    def test_completed_subset_diagnostic_excludes_still_active_turns(self):
        """At1.5, only S1:T1/S2:T1 completed, each D=1.4; two live."""
        c=scenario();c['observation_end_s']=1.5
        out=ServingSimulator(c).run();e=out['evaluation']
        self.assertEqual(e['summary']['completed_turns'],2)
        self.assertEqual(e['summary']['mean_completed_full_turn_e2e_s'],1.4)
        self.assertEqual(e['summary']['g1_metric'],'mean_full_turn_e2e_s')
        self.assertIsNone(e['summary']['mean_full_turn_e2e_s'])
        self.assertEqual(len(e['active_turn_censoring_lower_bounds']),2)
        self.assertEqual(e['terminated_turns'],[])

    def test_completed_subset_diagnostic_excludes_context_failure(self):
        """S1 prompt .2/GPU .2-.4/wire .4-.5/radio .5-.6; S2 fails."""
        import copy
        c=once(outputs=1,interval=2,horizon=2)
        c['models'][0]['context_window_tokens']=2
        other=copy.deepcopy(c['sessions'][0]);other['id']='S2'
        other['turns']=[dict(input_tokens=3,output_tokens=1)]
        c['sessions'].append(other)
        out=ServingSimulator(c).run();e=out['evaluation']
        self.assertEqual(e['summary']['completed_turns'],1)
        self.assertEqual(e['summary']['mean_completed_full_turn_e2e_s'],.6)
        self.assertEqual(len(e['terminated_turns']),1)
        self.assertEqual(e['active_turn_censoring_lower_bounds'],[])
        self.assertEqual(out['sessions'][1]['termination_reason'],'ContextLimit')

    def test_full_mean_includes_legal_zero_output_completion(self):
        """Zero output ends after prompt0-.2 and Prefill.2-.3; D=.3."""
        out=ServingSimulator(once(outputs=0,interval=2,horizon=2)).run()
        self.assertEqual(out['output_tokens'],[])
        self.assertEqual(out['evaluation']['summary']['mean_completed_full_turn_e2e_s'],.3)
        self.assertEqual(out['evaluation']['summary']['p95_full_turn_e2e_s'],.3)
        self.assertEqual(out['evaluation']['summary']['mean_full_turn_e2e_s'],.3)

    def test_weighted_objective_has_no_default_weights_or_fabricated_shadow(self):
        e=ServingSimulator(scenario()).run()['evaluation']
        self.assertEqual(e['resource_overhead']['V_mig'],0)
        self.assertEqual(e['resource_overhead']['A_shadow'],0)
        self.assertEqual(e['resource_overhead']['V_HO'],2)
        self.assertIsNone(e['resource_overhead']['weighted_cost'])
        self.assertIsNone(e['summary']['weighted_objective_value'])

    def test_incomplete_workload_cannot_use_diagnostic_as_main_target(self):
        c=scenario();c['observation_end_s']=1.5
        e=ServingSimulator(c).run()['evaluation']
        self.assertEqual(e['summary']['mean_completed_full_turn_e2e_s'],1.4)
        self.assertIsNone(e['summary']['mean_full_turn_e2e_s'])
        self.assertEqual(e['summary']['g1_metric'],'mean_full_turn_e2e_s')


if __name__=='__main__':unittest.main()
