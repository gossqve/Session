"""S3-B completion: real network, event collisions and interval-based metrics."""
import unittest
from test_handover import switching
from replacement.simulation.serving import ServingSimulator


def once(**kw):
    c = switching(**kw)
    c['mobility']['transition_probabilities']['E2'] = {'E2': 1}
    return c


class HandoverCompletionTests(unittest.TestCase):
    def test_one_pending_overlaps_multiple_positive_drains(self):
        c=switching(outputs=20,interval=.1,horizon=12)
        c['mobility']['transition_probabilities']['E2']={'E':1}
        c['topology']['mobility_adjacency']['E2']=['E']
        c['network']['wireless_down_bits_per_second']=8
        out=ServingSimulator(c).run()
        move=next(r for r in out['handover']['moves'] if r['check_index']==5)
        self.assertEqual(move['draining_wait_intervals'],[dict(start_s=.5,end_s=1.6),dict(start_s=1.6,end_s=10.7)])
        self.assertEqual(move['draining_wait_s'],10.2)
        self.assertEqual(move['status'],'cancelled')
        self.assertIsNone(move['handover_delay_s'])

    def test_enabled_self_transition_only_produces_no_false_handover(self):
        c=once(outputs=3)
        c['mobility']['transition_probabilities']['E']={'E':1}
        out=ServingSimulator(c).run()
        self.assertEqual(out['handover']['summary']['actual_handovers'],0)
        self.assertEqual(out['handover']['moves'],[])
        self.assertFalse(any(f['flow_type']=='handover' for f in out['network_flows']))

    def test_multi_token_forwarding_streams_before_batch_finishes(self):
        out=ServingSimulator(once(outputs=4,interval=.55,horizon=2)).run()
        forward=next(f for f in out['network_flows'] if f['flow_type']=='handover')
        self.assertEqual(len(forward['token_boundaries']),2)
        first=next(t for t in out['output_tokens'] if t['output_index']==2)
        self.assertLess(first['wireless_started_at'],forward['completed_at'])
        self.assertEqual(first['wireless_started_at'],forward['token_boundaries'][0]['arrived_at'])

    def test_next_turn_upload_rebinds_after_same_clock_handover(self):
        c=once(outputs=1,interval=.6,horizon=2)
        c['sessions'][0]['turns'] *= 2
        out=ServingSimulator(c).run()
        self.assertEqual(out['turns'][1]['submitted_at'],.6)
        self.assertEqual(out['turns'][1]['prompt_arrived_at'],.7)
        self.assertFalse(any(f['flow_type']=='prompt' and f['turn_index']==2 for f in out['network_flows']))
        self.assertEqual(sum(e['event']=='turn_submit' for e in out['events']),2)
        self.assertEqual(out['summary']['final_kv_bytes'],0)

    def test_forwarding_competes_on_shared_link_at_exact_half_rate(self):
        sim=ServingSimulator(once(outputs=1,interval=.45,horizon=2))
        sim.advance_to(.5)
        path=sim.topology.get_path('E','E2')
        sim.network.create('competitor','response','background',1,.5,path=path)
        sim.network.supply('competitor',1,.5)
        sim.network.close('competitor',.5)
        sim.network.start('competitor',.5)
        forward=next(f for f in sim.network.flows.values() if f.flow_type=='handover')
        self.assertEqual(sim.network.get_flow(forward.flow_id).rate_bps,40)
        self.assertEqual(sim.network.get_flow('competitor').rate_bps,40)
        # Both completions run on Serving's real shared event queue.
        out=sim.run()
        self.assertEqual(sim.network.get_flow(forward.flow_id).transferred_bytes,1)
        self.assertEqual(sim.network.get_flow('competitor').transferred_bytes,1)
        self.assertEqual(sim.network.get_flow(forward.flow_id).completed_at,.7)
        self.assertEqual(out['output_tokens'][0]['received_at'],.8)

    def test_wait_intersections_across_drains_and_cancellation(self):
        c=switching(outputs=6,interval=.2,horizon=8)
        c['mobility']['transition_probabilities']['E2']={'E':1}
        c['topology']['mobility_adjacency']['E2']=['E']
        c['network']['wireless_down_bits_per_second']=8
        out=ServingSimulator(c).run(); moves=out['handover']['moves']
        second=next(r for r in moves if r['check_index']==2)
        # Due move2 at .4 precedes first radio start, so no radio-only delay.
        self.assertEqual(second['actual_handover_time_s'],.4)
        self.assertEqual(second['handover_delay_s'],0)
        self.assertEqual(second['draining_wait_s'],0)
        third=next(r for r in moves if r['check_index']==3)
        self.assertEqual(third['actual_handover_time_s'],1.5)
        self.assertEqual(third['draining_wait_s'],.9)
        fourth=next(r for r in moves if r['check_index']==4)
        self.assertEqual(fourth['status'],'cancelled')
        self.assertEqual(fourth['first_draining_blocked_at'],.8)
        self.assertEqual(fourth['draining_wait_s'],6.3)
        self.assertIsNone(fourth['handover_delay_s'])
        self.assertEqual(out['handover']['summary']['completed_handover_count'],3)
        self.assertEqual(out['handover']['summary']['completed_draining_count'],3)

    def test_delay_uses_actual_switch_not_poll_count(self):
        out = ServingSimulator(once(outputs=4, interval=.55, horizon=2)).run()
        h = out['handover']; s = h['summary']
        self.assertEqual(s['completed_handover_count'], 1)
        for key in ('mean','p95','max','min'):
            self.assertAlmostEqual(s[key+'_handover_delay_s'], .05)
        self.assertEqual(h['moves'][0]['status'], 'completed')
        self.assertEqual(h['moves'][0]['actual_handover_time_s'], .6)

    def test_all_pending_moves_overlap_draining_without_double_counting(self):
        c = switching(outputs=8, interval=.2, horizon=2)
        c['mobility']['transition_probabilities']['E2'] = {'E': 1}
        c['topology']['mobility_adjacency']['E2'] = ['E']
        c['network']['wireless_down_bits_per_second'] = 8
        sim = ServingSimulator(c); out = sim.run(); h = out['handover']
        pending = [r for r in h['moves'] if r['status']=='pending']
        self.assertGreater(len(pending), 2)
        self.assertTrue(all(r['draining_wait_s']>0 for r in pending if r['planned_at']<2))
        self.assertTrue(all(r['handover_delay_s'] is None for r in pending))
        for r in h['moves']:
            intervals = r['draining_wait_intervals']
            self.assertAlmostEqual(r['draining_wait_s'], sum(i['end_s']-i['start_s'] for i in intervals))
        self.assertEqual(h['summary']['draining_delayed_moves'],sum(r['draining_wait_s']>0 for r in h['moves']))
        self.assertEqual(h, sim.handover.results())

    def test_cutoff_incomplete_drain_not_a_completed_duration(self):
        h = ServingSimulator(once(outputs=6,interval=.45,horizon=.6)).run()['handover']
        self.assertEqual(h['summary']['completed_draining_count'],0)
        self.assertEqual(h['summary']['incomplete_draining_count'],1)
        self.assertIsNone(h['summary']['mean_draining_duration_s'])
        self.assertAlmostEqual(h['sessions'][0]['observed_unfinished_drain_s'],.15)

    def test_partial_original_flow_keeps_progress_and_competes_for_forwarding(self):
        c = once(outputs=3,interval=.45,horizon=3)
        sim = ServingSimulator(c); sim.advance_to(.44)
        original = next(f for f in sim.network.flows.values() if f.flow_type=='response')
        self.assertAlmostEqual(float(original.transferred_bytes),.4)
        sim.advance_to(.45)
        closed = sim.network.get_flow(original.flow_id)
        self.assertAlmostEqual(float(closed.transferred_bytes),.5)
        self.assertEqual(closed.path,original.path)
        self.assertTrue(closed.producer_closed)
        self.assertNotEqual(closed.status,'cancelled')
        self.assertAlmostEqual(float(closed.pending_bytes),.5)
        out = sim.run(); flows = {f['flow_id']:f for f in out['network_flows']}
        final = flows[original.flow_id]
        self.assertEqual(final['transferred_bytes'],1)
        self.assertEqual(final['ready_bytes'],1)
        fwd = [f for f in flows.values() if f['flow_type']=='handover']
        self.assertEqual(len(fwd),1)
        self.assertEqual((fwd[0]['path']['source_node'],fwd[0]['path']['target_node']),('E','E2'))
        self.assertEqual(fwd[0]['transferred_bytes'],1)
        self.assertEqual(len(fwd[0]['token_boundaries']),1)
        self.assertEqual(tuple(fwd[0]['token_boundaries'][0]['token_id']),('S1',1,1))
        self.assertEqual([t['output_index'] for t in out['output_tokens'] if t['delivered']],[1,2,3])
        for row in out['network_events']:
            if row.get('kind')=='allocation':
                self.assertLessEqual(sum(flows[f]['flow_type'] in ('response','handover') for f in row['active_flow_ids']),1)

    def test_prompt_complete_same_clock_then_switch(self):
        out=ServingSimulator(once(interval=.2)).run()
        start=next(e for e in out['handover']['events'] if e['event']=='handover_start')
        self.assertEqual(start['time_s'],.2)
        self.assertEqual(sum(e['event']=='upload_start' for e in out['events']),1)
        self.assertEqual(sum(e['event']=='upload_done' for e in out['events']),1)

    def test_wireless_delivery_same_clock_excluded_from_old_set(self):
        out=ServingSimulator(once(outputs=4,interval=.55,horizon=2)).run()
        start=out['handover']['events'][0]
        self.assertEqual(start['time_s'],.6)
        self.assertNotIn(('S1',1,1),start['old_token_ids'])
        done=[e for e in out['events'] if e['event']=='downlink_done']
        self.assertEqual(len(done),4)
        self.assertEqual(done[0]['time_s'],.6)

    def test_original_arrival_same_clock_retained_and_forwarded(self):
        out=ServingSimulator(once(outputs=3,interval=.55,horizon=2)).run()
        start=out['handover']['events'][0]
        self.assertIn(('S1',1,2),start['old_token_ids'])
        self.assertEqual(start['time_s'],.6)
        self.assertTrue(all(t['delivered'] for t in out['output_tokens']))
        self.assertEqual(next(f for f in out['network_flows'] if f['flow_type']=='handover')['created_at'],.7)

    def test_decode_same_clock_commits_before_frozen_set(self):
        out=ServingSimulator(once(outputs=4,interval=.4,horizon=2)).run()
        start=out['handover']['events'][0]
        self.assertEqual(start['old_token_ids'],[('S1',1,1)])
        self.assertEqual(out['output_tokens'][0]['generated_at'],.4)
        self.assertEqual(out['output_tokens'][0]['access_edge_id'],'E')
        self.assertEqual(out['summary']['gpu_work'],5)

    def test_turn_end_same_clock_cancels_useless_pending_and_releases_kv(self):
        out=ServingSimulator(once(outputs=1,interval=.6,horizon=1)).run()
        self.assertEqual(out['handover']['summary']['actual_handovers'],0)
        self.assertEqual(out['summary']['final_kv_bytes'],0)
        self.assertEqual(sum(e['event']=='turn_complete' for e in out['events']),1)

    def test_multi_resource_collision_is_deterministic_and_fifo(self):
        c=once(outputs=4,interval=.55,horizon=2)
        a=ServingSimulator(c).run(); b=ServingSimulator(c).run()
        self.assertEqual(a,b)
        for event in ('gpu_compute_completed','token_access_arrival','downlink_done'):
            self.assertTrue(any(e['event']==event and e['time_s']==.6 for e in a['events']),event)
        self.assertEqual(a['handover']['events'][0]['time_s'],.6)
        same=[e['event'] for e in a['events'] if e['time_s']==.6]
        self.assertLess(same.index('token_committed'),same.index('token_access_arrival'))
        self.assertLess(same.index('token_access_arrival'),same.index('downlink_done'))
        self.assertEqual([t['output_index'] for t in a['output_tokens'] if t['delivered']],[1,2,3,4])


if __name__=='__main__': unittest.main()
