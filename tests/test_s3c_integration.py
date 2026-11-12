"""Section III B/C/E oracles, derived independently of runtime output.

Fixture: 80 bit/s wired/radio, C=10, L=2, structural KV=4B/token.
Two remote prompts .1-.3, GPU shares 5 each .3-.9. Handover .8;
At .9 three Flows share a TOTAL 80bit/s link, EACH at80/3bit/s.
At absolute t=1.0 (.1s elapsed), each has (80/3)/8*.1=1/3B;
at1.2 (.3s elapsed), each has1B. Capacity80/3 is NOT the link total.
Receipts1.3/1.4; S1 zero-output second Turn and S3 finish1.6.
Work9, logical wired8B, radio9B, peakKV32B, final0. Only float
serialization/integral comparisons use1e-9 tolerance; literal clocks exact.
"""
import copy
from dataclasses import asdict, FrozenInstanceError
from fractions import Fraction
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from replacement.simulation.serving import ServingSimulator
from test_handover_completion import once
from test_handover import switching

ROOT=Path(__file__).resolve().parents[1]


def scenario():
    return json.loads((ROOT/'configs/s3c_hand_shared.json').read_text(encoding='utf-8'))


def check_resources(case,sim):
    """B2/C12/C17/C41: independent sums on actual per-event state."""
    owners=set()
    for edge in sim.runtime.edges.values():
        tasks=edge.running_tasks
        case.assertLessEqual(len(tasks),edge.gpu_slots)
        for task in tasks:
            key=task.session_id,task.turn_index
            case.assertNotIn(key,owners);owners.add(key)
            case.assertEqual(task.execution_edge_id,sim.runtime.sessions[task.session_id].execution_edge_id)
        rates=edge.compute.scheduler.rates
        if rates:
            case.assertTrue(all(abs(rate-edge.gpu_capacity/len(rates))<1e-9 for rate in rates.values()))
        total=0
        for sid in edge.resident_session_ids:
            session=sim.runtime.sessions[sid]
            m=sim.runtime.models[session.model_id]
            kv=2*m.layers*m.kv_heads*m.head_dim*m.element_bytes*session.context_tokens
            case.assertEqual(session.authoritative_kv_bytes,kv);total+=kv
            case.assertFalse(sid in sim._prompt_active and sid in sim._downlink_busy)
        case.assertEqual(edge.kv.used_bytes,total)
        case.assertLessEqual(total,edge.kv_capacity_bytes)
    loads={lid:Fraction(0) for lid in sim.topology.links}
    shares={}
    for f in sim.network.flows.values():
        case.assertTrue(0<=f.transferred_bytes<=f.ready_bytes)
        for lid in f.link_ids:loads[lid]+=Fraction(f.rate_bps)
        if f.rate_bps and f.flow_type in ('response','handover'):
            key=f.session_id,f.turn_index;shares[key]=shares.get(key,0)+1
    for lid,load in loads.items():case.assertLessEqual(load,Fraction(str(sim.topology.links[lid].capacity_bps)))
    case.assertTrue(all(n<=1 for n in shares.values()))


class S3CIntegrationTests(unittest.TestCase):
    def test_kvblocked_recovers_after_two_handovers_without_recomputing(self):
        """C13/18/21: wire prompts .1-.3; FCFS S1 units .3-.5,
        S2 .5-.7. KV12 blocks S2 Decode at.7. S1 radio .6-1.6
        releases8B; retry commits once1.6 at Actual E3 after .65/1.3
        empty handovers; final response wire1.6-1.7/radio1.7-1.8.
        """
        c=switching(outputs=1,interval=.65,horizon=2)
        for e in c['edges']:e['kv_capacity_bytes']=12
        c['topology']['edges']=copy.deepcopy(c['edges'])
        c['sessions'][0]['network']={'wireless_down_bits_per_second':8}
        other=copy.deepcopy(c['sessions'][0]);other['id']='S2';other.pop('network')
        c['sessions'].append(other)
        sim=ServingSimulator(c);sim.advance_to(1.4)
        turn=sim.runtime.sessions['S2'].current_turn
        self.assertEqual(turn.status,'blocked')
        self.assertEqual(turn.partial_work,1)
        self.assertEqual(turn.gpu_service_work,2)
        self.assertEqual(sim.runtime.sessions['S2'].access_edge_id,'E3')
        out=sim.run();own=out['turns'][1]
        self.assertEqual(own['block_count'],1)
        self.assertEqual(own['blocked_time_s'],.9)
        self.assertEqual(own['received_at'],1.8)
        token=next(t for t in out['output_tokens'] if t['session_id']=='S2')
        self.assertEqual((token['generated_at'],token['access_edge_id'],token['execution_edge_id']),(1.6,'E3','E2'))
        self.assertEqual(out['summary']['gpu_work'],4)
        self.assertEqual(out['summary']['peak_kv_bytes'],12)
        self.assertEqual(out['summary']['final_kv_bytes'],0)
        self.assertEqual(sum(e['event']=='gpu_compute_completed' and e['session_id']=='S2' and e.get('phase')=='decode' for e in out['events']),1)
        self.assertEqual(sum(e['event']=='pending_committed' and e['session_id']=='S2' for e in out['events']),1)

    def test_final_old_token_drain_end_precedes_same_clock_session_cleanup(self):
        """One output: old wire .4-.5, extra .5-.6, UE .6-.7; end=.7."""
        out=ServingSimulator(once(outputs=1,interval=.4,horizon=.8)).run()
        self.assertEqual(out['handover']['events'][0]['drain_end_s'],.7)
        self.assertEqual(out['sessions'][0]['end_time'],.7)
        self.assertFalse(out['handover']['sessions'][0]['draining'])
        self.assertFalse(out['handover']['sessions'][0]['active'])
        self.assertEqual(out['summary']['final_kv_bytes'],0)
        self.assertEqual(out['mobility']['summary']['mobility_checks'],1)
        self.assertEqual(out['handover']['summary']['actual_handovers'],1)

    def test_drain_end_and_due_move_at_cutoff_keep_exact_seven_step_order(self):
        """HO2 .4, forward .4-.5, UE1 .5-.6; move3 then freezes2,3 at .6."""
        c=switching(outputs=6,interval=.2,horizon=.6)
        c['mobility']['transition_probabilities']['E2']={'E':1}
        c['topology']['mobility_adjacency']['E2']=['E']
        out=ServingSimulator(c).run()
        starts=[e for e in out['handover']['events'] if e['event']=='handover_start']
        self.assertEqual([e['time_s'] for e in starts],[.2,.4,.6])
        self.assertEqual(starts[1]['drain_end_s'],.6)
        self.assertEqual(starts[2]['old_token_ids'],[('S1',1,2),('S1',1,3)])
        self.assertIsNone(starts[2]['drain_end_s'])
        self.assertEqual(out['turns'][0]['delivered'],1)
        self.assertEqual(out['summary']['final_kv_bytes'],16)
        self.assertEqual(out['handover']['summary']['incomplete_draining_count'],1)

    def test_kvblocked_during_drain_keeps_computed_unit_and_authority(self):
        """KV20 fits first5 commits, blocks S2 Decode2 (.9) at work3, KV8."""
        c=scenario()
        for edge in c['edges']:edge['kv_capacity_bytes']=20
        c['topology']['edges']=copy.deepcopy(c['edges'])
        sim=ServingSimulator(c);sim.advance_to(1.)
        session=sim.runtime.sessions['S2'];turn=session.current_turn
        self.assertTrue(sim.handover.sessions['S2'].draining)
        self.assertEqual(turn.status,'blocked')
        self.assertEqual(turn.partial_work,1)
        self.assertEqual(turn.gpu_service_work,3)
        self.assertEqual(session.authoritative_kv_bytes,8)
        self.assertEqual(session.execution_edge_id,'E2')
        self.assertNotIn('S2:1',[f'{t.session_id}:{t.turn_index}' for t in sim.runtime.edges['E2'].running_tasks])
        out=sim.run()
        self.assertEqual(out['summary']['gpu_work'],8)
        self.assertEqual(out['summary']['final_kv_bytes'],20)
        self.assertIsNone(out['summary']['mean_full_turn_e2e_s'])
        own=[e for e in out['events'] if e['event']=='gpu_compute_completed' and e['session_id']=='S2' and e.get('phase')=='decode' and e.get('unit_index')==2]
        self.assertEqual(len(own),1)

    def test_direct_step_cutoff_also_applies_without_topology_or_mobility(self):
        from test_serving import config
        c=config();c['observation_end_s']=.15
        sim=ServingSimulator(c)
        while sim.step() is not None: pass
        self.assertEqual(sim.time_s,.15)
        self.assertTrue(all(s.end_time is None for s in sim.runtime.sessions.values()))
        self.assertIsNone(sim.step())

    def test_cutoff_exact_drain_end_releases_buffer_without_fake_delivery(self):
        out=ServingSimulator(once(outputs=2,interval=.45,horizon=.7)).run()
        self.assertEqual(out['handover']['events'][0]['drain_end_s'],.7)
        self.assertFalse(out['handover']['sessions'][0]['draining'])
        self.assertEqual(out['turns'][0]['delivered'],1)
        self.assertFalse(out['output_tokens'][1]['delivered'])
        self.assertEqual(out['output_tokens'][1]['wireless_started_at'],.7)
        self.assertEqual(out['summary']['final_kv_bytes'],12)

    def test_due_move_precedes_next_wireless_start_at_same_clock(self):
        """B3 seven steps: .6 UE1 done, move, then future sends; freeze2,3."""
        out=ServingSimulator(once(outputs=4,interval=.6,horizon=2)).run()
        start=out['handover']['events'][0]
        self.assertEqual(start['time_s'],.6)
        self.assertEqual(start['old_token_ids'],[('S1',1,2),('S1',1,3)])
        self.assertEqual([t['received_at'] for t in out['output_tokens']],[.6,.9,1.,1.1])
        self.assertEqual(start['drain_end_s'],1.)
        self.assertEqual(out['summary']['gpu_work'],5)
        self.assertEqual(sum(f['transferred_bytes'] for f in out['network_flows'] if f['flow_type']=='handover'),2)

    def test_direct_step_cannot_cross_global_cutoff(self):
        """Tobs=.55 clips a real 1B forwarding stage at exactly .5B."""
        sim=ServingSimulator(once(outputs=4,interval=.45,horizon=.55))
        for _ in range(1000):
            if sim.step() is None:break
        else:self.fail('finite progress')
        self.assertEqual(sim.time_s,.55)
        self.assertIsNone(sim.step())
        self.assertEqual(sum(float(f.transferred_bytes) for f in sim.network.flows.values() if f.flow_type=='handover'),.5)
        self.assertTrue(sim.handover.sessions['S1'].draining)
        self.assertGreater(sim.runtime.sessions['S1'].authoritative_kv_bytes,0)

    def test_three_session_shared_handover_literal_timeline(self):
        sim=ServingSimulator(scenario());out=sim.run()
        self.assertEqual([r['received_at'] for r in out['turns']],[1.4,1.6,1.4,1.6])
        self.assertEqual([r['submitted_at'] for r in out['turns']],[0,1.4,0,.8])
        self.assertEqual(out['summary']['gpu_work'],9)
        self.assertEqual(out['summary']['peak_kv_bytes'],32)
        self.assertEqual(out['summary']['final_kv_bytes'],0)
        self.assertEqual(out['summary']['completed_turns'],4)
        self.assertEqual(out['summary']['mean_full_turn_e2e_s'],.95)  # (1.4+.2+1.4+.8)/4
        self.assertEqual(sum(f['transferred_bytes'] for f in out['network_flows']),8)
        self.assertEqual(sum(f['transferred_bytes'] for f in out['wireless_transfers']),9)
        starts=[e for e in out['handover']['events'] if e['event']=='handover_start']
        self.assertEqual([(e['session_id'],e['time_s']) for e in starts],[('S1',.8),('S2',.8)])

    def test_mixed_protection_and_three_way_fraction_sharing(self):
        sim=ServingSimulator(scenario());sim.advance_to(.85)
        self.assertIn('S3',sim._prompt_active)
        for sid in ('S1','S2'):
            state=sim.handover.sessions[sid]
            self.assertTrue(state.draining)
            self.assertEqual(sim.runtime.sessions[sid].authoritative_kv_bytes,8)
        sim.advance_to(1.)
        # Absolute clock1.0 minus start.9 is .1s, not one second or .3s.
        active=[f for f in sim.network.flows.values() if f.rate_bps]
        self.assertEqual(len(active),3)
        self.assertEqual(sorted(f.flow_type.value for f in active),['handover','handover','prompt'])
        self.assertTrue(all(f.rate_bps==Fraction(80,3) for f in active))
        self.assertTrue(all(f.transferred_bytes==Fraction(1,3) for f in active))
        for sid in ('S1','S2'):
            self.assertEqual([t.output_index for t in sim.handover.sessions[sid].buffered],[2])
            self.assertEqual(sim.runtime.sessions[sid].authoritative_kv_bytes,12)
        check_resources(self,sim)

    def test_all_intermediate_states_conserve_resources_and_authority(self):
        sim=ServingSimulator(scenario())
        for _ in range(2000):
            result=sim.step()
            if result is None:break
            check_resources(self,sim)
        else:self.fail('event progress')
        self.assertEqual(sim.time_s,2)
        self.assertTrue(all(s.status=='ended' for s in sim.runtime.sessions.values()))

    def test_independent_gpu_piecewise_integral_and_slots(self):
        sim=ServingSimulator(scenario());sim.advance_to(.4)
        e=sim.runtime.edges['E2']
        self.assertEqual(list(e.compute.scheduler.rates.values()),[5,5])
        self.assertEqual(len(e.running_tasks),2)
        # Two .1s intervals at5work/s give .5 work per Turn; total1.
        self.assertAlmostEqual(sum(t.gpu_service_work for s in sim.runtime.sessions.values() for t in s.turns),1)
        sim.advance_to(1.25)
        self.assertEqual(list(e.compute.scheduler.rates.values()),[10])
        self.assertLess(len(e.running_tasks),e.gpu_slots)  # full C still free slot
        out=sim.run()
        trace=out['gpu_events']['E2']
        work=sum(r['consumed_work'] for r in trace if r['event']=='service')
        busy=sum(r['elapsed_s'] for r in trace if r['event']=='service' and r['running_count'])
        self.assertAlmostEqual(work,10*(.6+.2+.1))
        self.assertAlmostEqual(busy,.9)

    def test_zero_output_turn_has_no_fake_token_and_cumulative_context(self):
        out=ServingSimulator(scenario()).run()
        row=out['turns'][1]
        self.assertEqual((row['prefill_done'],row['decode_done'],row['delivered']),(1,0,0))
        self.assertEqual((row['context_tokens'],row['authoritative_kv_bytes']),(4,16))
        self.assertEqual(row['received_at'],row['generation_ended_at'])
        self.assertFalse(any(t['session_id']=='S1' and t['turn_index']==2 for t in out['output_tokens']))

    def test_causal_prefix_during_draining_hides_all_future_variants(self):
        a=once(outputs=6,interval=.45,horizon=3)
        a['sessions'][0]['turns'].append(dict(input_tokens=1,output_tokens=1))
        b=copy.deepcopy(a);b['seed']=19;b['observation_end_s']=4
        b['sessions'][0]['turns']=[dict(input_tokens=1,output_tokens=8),dict(input_tokens=2,output_tokens=3),dict(input_tokens=0,output_tokens=0)]
        b['mobility']['transition_probabilities']['E2']={'E3':1}
        x,y=ServingSimulator(a),ServingSimulator(b)
        x.advance_to(.65);y.advance_to(.65)
        self.assertTrue(x.handover.sessions['S1'].draining)
        self.assertEqual(x.observation(),y.observation())
        self.assertEqual(x.events,y.events)
        self.assertEqual(x.network.trace,y.network.trace)
        self.assertEqual(x.wireless.trace,y.wireless.trace)
        for edge in x.runtime.edges:
            self.assertEqual(x.runtime.edges[edge].compute.scheduler.gpu_trace,y.runtime.edges[edge].compute.scheduler.gpu_trace)
            self.assertEqual(x.runtime.edges[edge].kv.trace,y.runtime.edges[edge].kv.trace)
        observation=x.observation();encoded=asdict(observation)
        self.assertEqual(set(encoded),{'time_s','sessions','edges','network_transfers','wireless_transfers','handover_states'})
        with self.assertRaises(FrozenInstanceError):observation.time_s=99
        x.advance_to(.7);self.assertEqual(asdict(observation),encoded)

    def test_empty_drain_does_not_consume_multiple_pending_same_timestamp(self):
        c=switching(outputs=0,interval=.1,horizon=2)
        c['sessions'][0]['turns'][0]['input_tokens']=10
        c['mobility']['transition_probabilities']['E2']={'E':1}
        c['topology']['mobility_adjacency']['E2']=['E']
        out=ServingSimulator(c).run()
        starts=[e for e in out['handover']['events'] if e['event']=='handover_start']
        self.assertEqual(len(starts),1)
        self.assertEqual((starts[0]['time_s'],starts[0]['drain_duration_s']),(2,0))
        self.assertEqual(out['mobility']['summary']['pending_moves_at_observation_end'],19)
        self.assertEqual(out['summary']['completed_turns'],0)

    def test_configured_interval_exact_boundary_not_hardcoded(self):
        c=switching(outputs=8,interval=.2,horizon=.6)
        c['mobility']['min_inter_move_interval_s']=.4
        out=ServingSimulator(c).run()
        starts=[e['time_s'] for e in out['handover']['events'] if e['event']=='handover_start']
        self.assertEqual(starts,[.2,.6])
        self.assertEqual(out['mobility']['summary']['moves_rejected_min_interval'],1)

    def test_cutoff_same_clock_drain_delivery_then_natural_end(self):
        c=once(outputs=2,interval=.45,horizon=.8)
        out=ServingSimulator(c).run()
        self.assertEqual(out['handover']['events'][0]['drain_end_s'],.7)
        self.assertEqual(out['sessions'][0]['end_time'],.8)
        self.assertFalse(out['handover']['sessions'][0]['active'])
        self.assertEqual(out['summary']['final_kv_bytes'],0)


if __name__=='__main__':unittest.main()
