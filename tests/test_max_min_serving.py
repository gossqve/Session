"""S2-C formal Serving integration, with literal independent hand timelines.

These tests exercise actual Session/Turn traffic and the existing event engine;
no fixture rate is calculated by the allocator under test.
"""
import copy
from dataclasses import asdict
import json
from pathlib import Path
import random
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from replacement.simulation.serving import ServingSimulator


def scenario(name='shared'):
    return json.loads((ROOT / 'configs' / f's2c_maxmin_{name}.json').read_text(encoding='utf-8'))


def link_capacity(config, link_id, capacity):
    next(row for row in config['topology']['links'] if row['link_id'] == link_id)['capacity_bps'] = capacity


def sync_edges(config):
    config['topology']['edges'] = copy.deepcopy(config['edges'])


class MaxMinServingTests(unittest.TestCase):
    def assert_capacity(self, sim):
        """Independent sums over real runtime Flow fixed paths at a checkpoint."""
        loads = {lid: 0 for lid in sim.topology.links}
        for flow in sim.network.flows.values():
            self.assertGreaterEqual(flow.rate_bps, 0)
            self.assertGreaterEqual(flow.transferred_bytes, 0)
            self.assertLessEqual(flow.transferred_bytes, flow.ready_bytes)
            if flow.rate_bps:
                self.assertGreater(flow.pending_bytes, 0)
                self.assertIsNotNone(flow.started_at)
                self.assertIsNone(flow.completed_at)
                self.assertIsNone(flow.cancelled_at)
            for lid in flow.link_ids:
                loads[lid] += flow.rate_bps
        for lid, load in loads.items():
            self.assertLessEqual(load, sim.topology.links[lid].capacity_bps + 1e-8, lid)
        self.assertEqual(sim.network.time_s, sim.time_s)
        self.assertEqual(sim.wireless.time_s, sim.time_s)
        for edge in sim.runtime.edges.values():
            edge.kv.assert_consistent()
            self.assertLessEqual(edge.kv.used_bytes, edge.kv_capacity_bytes)

    def run_checked(self, config):
        sim = ServingSimulator(config)
        steps = 0
        while sim.queue:
            old = sim.time_s
            sim.step()
            self.assertGreaterEqual(sim.time_s, old)
            self.assert_capacity(sim)
            steps += 1
            self.assertLess(steps, 10000, 'finite event progress')
        return sim, sim.results()

    def assert_completed_accounting(self, config, out):
        planned = sum(len(s['turns']) for s in config['sessions'])
        self.assertEqual(out['summary']['completed_turns'], planned)
        self.assertEqual(out['summary']['final_kv_bytes'], 0)
        self.assertEqual(out['summary']['unfinished_turns'], 0)
        model_by_id = {m['id']: m for m in config['models']}
        for row in out['turns']:
            self.assertEqual(row['status'], 'completed')
            self.assertEqual(row['delivered'], row['decode_done'])
            self.assertEqual(row['prefill_done'], row['input_tokens'])
            model = model_by_id[row['model_id']]
            kv_per_token = 2 * model['layers'] * model['kv_heads'] * model['head_dim'] * model['element_bytes']
            self.assertEqual(row['authoritative_kv_bytes'], row['context_tokens'] * kv_per_token)
            self.assertAlmostEqual(row['gpu_service_work'], row['prefill_done'] * model['prefill_work_per_token'] + row['decode_done'] * model['decode_work_per_token'])
            self.assertEqual(row['gpu_ready_time'], row['prompt_arrived_at'])
            self.assertGreaterEqual(row['gpu_ready_time'], row['wireless_upload_completed_at'])
            tokens = [t for t in out['output_tokens'] if t['session_id'] == row['session_id'] and t['turn_index'] == row['turn_index']]
            if tokens:
                self.assertEqual(row['received_at'], tokens[-1]['received_at'])
                self.assertEqual(len({t['wired_flow_id'] for t in tokens}), 1)
                self.assertEqual([t['output_index'] for t in tokens], list(range(1, len(tokens) + 1)))
                for token in tokens:
                    self.assertLessEqual(token['generated_at'], token['wired_arrived_at'])
                    self.assertLessEqual(token['wired_arrived_at'], token['wireless_started_at'])
                    self.assertLessEqual(token['wireless_started_at'], token['received_at'])
                    committed = [e for e in out['events'] if e['event'] in ('token_committed', 'pending_committed') and e.get('session_id') == token['session_id'] and e.get('turn_index') == token['turn_index'] and e.get('phase') == 'decode' and e.get('unit_index') == token['output_index']]
                    self.assertEqual(len(committed), 1)
                    self.assertEqual(committed[0]['time_s'], token['generated_at'])
        for s in config['sessions']:
            rows = [r for r in out['turns'] if r['session_id'] == s['id']]
            cumulative = 0
            for index, row in enumerate(rows):
                cumulative += row['prefill_done'] + row['decode_done']
                self.assertEqual(row['context_tokens'], cumulative)
                if index:
                    self.assertEqual(row['submitted_at'], rows[index - 1]['received_at'])
        for flow in out['network_flows']:
            self.assertEqual(flow['status'], 'completed')
            self.assertEqual(flow['transferred_bytes'], flow['ready_bytes'])
            self.assertEqual(flow['pending_bytes'], 0)
            self.assertEqual(flow['rate_bps'], 0)
        token_ids = [tuple(t['token_id']) for t in out['output_tokens']]
        self.assertEqual(len(token_ids), len(set(token_ids)))
        received = [tuple(e['token_id']) for e in out['events'] if e['event'] == 'downlink_done']
        self.assertEqual(sorted(token_ids), sorted(received))

    def test_default_shared_formal_serving_literal_hand_timeline(self):
        c = scenario()
        sim = ServingSimulator(c)
        sim.advance_to(.1)
        prompts = [f for f in sim.network.flows.values() if f.flow_type == 'prompt']
        self.assertEqual(len(prompts), 2)
        self.assertEqual([f.rate_bps for f in prompts], [40, 40])
        self.assertTrue(all('A_B' in f.link_ids for f in prompts))
        self.assert_capacity(sim)
        sim.advance_to(.2)
        self.assertEqual([float(f.transferred_bytes) for f in sim.network.flows.values()], [.5, .5])
        self.assertTrue(all(s.current_turn.gpu_ready_time is None for s in sim.runtime.sessions.values()))
        out = sim.run()
        self.assertEqual([r['gpu_ready_time'] for r in out['turns']], [.3, .3])
        self.assertEqual([t['generated_at'] for t in out['output_tokens']], [.5, .5])
        self.assertEqual([t['wired_arrived_at'] for t in out['output_tokens']], [.7, .7])
        self.assertEqual([t['received_at'] for t in out['output_tokens']], [.8, .8])
        self.assertEqual([r['e2e_s'] for r in out['turns']], [.8, .8])
        self.assertEqual(out['summary']['gpu_work'], 4)
        self.assertEqual(sum(f['transferred_bytes'] for f in out['network_flows']), 4)
        self.assert_completed_accounting(c, out)

    def test_allocation_audit_matches_real_path_loads_and_eligible_flows(self):
        c = scenario('three_area')
        out = ServingSimulator(c).run()
        records = [r for r in out['network_events'] if r['kind'] == 'allocation']
        self.assertTrue(records)
        flow_types = {f['flow_id']: f['flow_type'] for f in out['network_flows']}
        mixed = False
        for r in records:
            self.assertEqual(r['participants'], sorted(r['participants']))
            loads = {lid: 0 for lid in r['links']}
            for fid, f in r['flows'].items():
                self.assertEqual(f['rate_bps'], r['rates_bps'][fid])
                if fid in r['participants']:
                    self.assertGreater(f['pending_bytes'], 0)
                    self.assertNotIn(f['status'], ('completed', 'cancelled', 'created', 'paused'))
                for lid in f['link_ids']:
                    loads[lid] += f['rate_bps']
            for lid, link in r['links'].items():
                self.assertAlmostEqual(loads[lid], link['load_bps'])
                self.assertAlmostEqual(loads[lid], r['link_loads_bps'][lid])
                self.assertLessEqual(loads[lid], link['capacity_bps'] + 1e-8)
                self.assertAlmostEqual(link['capacity_bps'] - loads[lid], link['residual_bps'])
                types = {flow_types[fid] for fid in r['participants'] if lid in r['flows'][fid]['link_ids']}
                mixed |= lid == 'B_A' and types >= {'prompt', 'response'}
        self.assertTrue(mixed)

    def test_reverse_direction_independent_actual_prompt_paths(self):
        c = scenario()
        c['sessions'][1].update(access_edge_id='E3', execution_edge_id='E1')
        sim = ServingSimulator(c)
        sim.advance_to(.15)
        prompts = [f for f in sim.network.flows.values() if f.flow_type == 'prompt']
        self.assertEqual([f.rate_bps for f in prompts], [80, 80])
        self.assertEqual([float(f.transferred_bytes) for f in prompts], [.5, .5])
        self.assertEqual(set(prompts[0].link_ids) & set(prompts[1].link_ids), set())
        self.assert_capacity(sim)

    def test_actual_path_bottleneck_reclaims_residual_literal_30_70(self):
        c = scenario()
        link_capacity(c, 'A_B', 100)
        link_capacity(c, 'E1_gA', 30)
        sim = ServingSimulator(c)
        sim.advance_to(.1)
        prompts = [f for f in sim.network.flows.values() if f.flow_type == 'prompt']
        self.assertEqual([f.rate_bps for f in prompts], [30, 70])
        self.assert_capacity(sim)
        out = sim.run()
        self.assertEqual([r['gpu_ready_time'] for r in out['turns']], [.366666666667, .214285714286])
        self.assert_completed_accounting(c, out)

    def test_three_areas_topology_and_real_mixed_type_competition(self):
        c = scenario('three_area')
        sim = ServingSimulator(c)
        self.assertEqual(len(sim.topology.areas), 3)
        self.assertEqual(len(sim.topology.edges), 6)
        cross = [l for l in sim.topology.links.values() if l.source_node.startswith('g') and l.target_node.startswith('g')]
        self.assertEqual(len(cross), 6)
        self.assertEqual(len({l.capacity_bps for l in cross}), 6)
        mixed = []
        used = set()
        while sim.queue:
            sim.step()
            self.assert_capacity(sim)
            active = [f for f in sim.network.flows.values() if f.rate_bps > 0]
            used.update(l for f in active for l in f.link_ids)
            for lid in sim.topology.links:
                flows = [f for f in active if lid in f.link_ids]
                if {f.flow_type for f in flows} >= {'prompt', 'response'}:
                    mixed.append((sim.time_s, lid, flows))
        self.assertTrue(any(lid == 'B_A' for _, lid, _ in mixed))
        for _, lid, flows in mixed:
            # The competing types use a single directed capacity constraint.
            self.assertLessEqual(sum(f.rate_bps for f in flows), sim.topology.links[lid].capacity_bps + 1e-8)
        self.assertTrue({'A_B', 'B_A', 'A_C', 'C_A', 'C_B', 'B_C', 'E5_E6', 'E6_E5'} <= used)
        out = sim.results()
        self.assert_completed_accounting(c, out)
        self.assertTrue(any(f['flow_type'] == 'prompt' and f['link_ids'] == ['E5_E6'] for f in out['network_flows']))
        self.assertTrue(any(f['flow_type'] == 'response' and f['link_ids'] == ['E6_E5'] for f in out['network_flows']))

    def test_independent_area_pair_does_not_get_fictional_area_pool(self):
        c = scenario()
        other = copy.deepcopy(c['sessions'][0])
        other.update(id='S3', execution_edge_id='E5')
        c['sessions'].append(other)
        sim = ServingSimulator(c)
        sim.advance_to(.1)
        rates = {f.session_id: f.rate_bps for f in sim.network.flows.values() if f.flow_type == 'prompt'}
        self.assertEqual(rates, {'S1': 40, 'S2': 40, 'S3': 80})
        self.assert_capacity(sim)

    def test_streaming_persistent_response_wait_resupply_and_overlap(self):
        c = scenario('pipeline')
        sim = ServingSimulator(c)
        waiting = set()
        shared = False
        while sim.queue:
            sim.step()
            self.assert_capacity(sim)
            responses = [f for f in sim.network.flows.values() if f.flow_type == 'response']
            waiting.update(f.flow_id for f in responses if f.status == 'waiting_for_data')
            shared |= sum(f.rate_bps > 0 for f in responses) >= 2
        out = sim.results()
        self.assertTrue(shared)
        self.assertTrue(waiting)
        self.assert_completed_accounting(c, out)
        responses = [f for f in out['network_flows'] if f['flow_type'] == 'response']
        self.assertEqual(len(responses), 2)
        self.assertTrue(waiting <= {f['flow_id'] for f in responses})
        for row in out['turns']:
            tokens = [t for t in out['output_tokens'] if t['session_id'] == row['session_id']]
            self.assertGreaterEqual(len(tokens), 3)
            self.assertEqual([t['wired_cumulative_bytes'] for t in tokens], list(range(1, len(tokens) + 1)))
            self.assertLess(tokens[0]['wireless_started_at'], row['generation_ended_at'])
            self.assertGreater(row['received_at'], row['generation_ended_at'])

    def test_wide_changes_only_interarea_capacities_measured_sensitivity(self):
        c, wide = scenario('three_area'), scenario('wide')
        normalized = copy.deepcopy(wide)
        normalized['scenario'] = c['scenario']
        for base, changed in zip(c['topology']['links'], normalized['topology']['links']):
            if base['source_node'].startswith('g') and base['target_node'].startswith('g'):
                self.assertEqual(changed['capacity_bps'], base['capacity_bps'] * 4)
                changed['capacity_bps'] = base['capacity_bps']
        self.assertEqual(c, normalized)
        _, narrow_out = self.run_checked(c)
        _, wide_out = self.run_checked(wide)
        self.assert_completed_accounting(c, narrow_out)
        self.assert_completed_accounting(wide, wide_out)
        self.assertNotEqual([t['received_at'] for t in narrow_out['output_tokens']], [t['received_at'] for t in wide_out['output_tokens']])
        self.assertLess(wide_out['summary']['mean_full_turn_e2e_s'], narrow_out['summary']['mean_full_turn_e2e_s'])

    def test_causal_prefix_different_hidden_output_future_turns_arrivals(self):
        c = scenario('pipeline')
        changed = copy.deepcopy(c)
        changed['sessions'][0]['turns'][0]['output_tokens'] = 19
        changed['sessions'][0]['turns'].append(dict(input_tokens=99, output_tokens=20))
        future = copy.deepcopy(changed['sessions'][0])
        future.update(id='future', arrival_time=20)
        changed['sessions'].append(future)
        a, b = ServingSimulator(c), ServingSimulator(changed)
        a.advance_to(.55)
        b.advance_to(.55)
        self.assertEqual(a.observation(), b.observation())
        self.assertEqual(a.events, b.events)
        self.assertEqual(a.network.trace, b.network.trace)
        self.assertEqual(a.network.flows, b.network.flows)
        self.assertNotIn('future', b.runtime.sessions)
        payload = json.dumps(asdict(a.observation()))
        for private in ('hidden_output_tokens', 'remaining_output', 'future', 'turns'):
            self.assertNotIn(private, payload)

    def test_determinism_checkpoints_do_not_change_delivery_or_byte_results(self):
        c = scenario('three_area')
        uninterrupted = ServingSimulator(c).run()
        self.assertEqual(uninterrupted, ServingSimulator(copy.deepcopy(c)).run())
        sim = ServingSimulator(c)
        for time in (.1, .3, .5, .7, 1, 1.15, 1.5, 2, 3):
            sim.advance_to(time)
            self.assert_capacity(sim)
        checkpointed = sim.run()
        for key in ('turns', 'sessions', 'output_tokens', 'network_flows', 'wireless_transfers', 'resources'):
            expected, actual = copy.deepcopy(uninterrupted[key]), copy.deepcopy(checkpointed[key])
            if key in ('network_flows', 'wireless_transfers'):
                # Forecast generation IDs are deliberately renewed by checkpoints.
                # Compare all physical state, excluding only that event bookkeeping.
                for flow in expected + actual:
                    flow.pop('event_version', None)
            self.assertEqual(expected, actual, key)

    def test_same_clock_shared_boundaries_exactly_once(self):
        c = scenario()
        for session in c['sessions']:
            session['turns'] = [dict(input_tokens=1, output_tokens=4)] * 2
        sim, out = self.run_checked(c)
        self.assert_completed_accounting(c, out)
        tokens = out['output_tokens']
        self.assertEqual(len(tokens), 16)
        self.assertEqual(len({tuple(t['token_id']) for t in tokens}), 16)
        # Every response's boundary is immutable and unique even at reallocations.
        for f in sim.network.flows.values():
            if f.flow_type == 'response':
                self.assertEqual(len(f.token_boundaries), 4)
                self.assertEqual(len({b.token_id for b in f.token_boundaries}), 4)

    def test_seeded_multivariable_actual_serving_conservation_and_limits(self):
        rng = random.Random(20261108)
        blocked_cases = context_cases = 0
        for case in range(30):
            with self.subTest(case=case):
                c = scenario()
                for l in c['topology']['links']:
                    l['capacity_bps'] = rng.choice([24, 40, 80, 120, 160])
                for e in c['edges']:
                    e['gpu_work_per_second'] = rng.choice([5, 10, 20])
                    e['gpu_slots'] = rng.choice([1, 2])
                for s in c['sessions']:
                    s['arrival_time'] = rng.choice([0, .05, .3])
                    s['model_id'] = rng.choice(['m4', 'm8'])
                    s['network'] = dict(wireless_up_bits_per_second=rng.choice([40, 80, 160]), wireless_down_bits_per_second=rng.choice([24, 80, 160]))
                    s['turns'] = [dict(input_tokens=rng.randint(0, 3), output_tokens=rng.randint(1, 4)) for _ in range(rng.randint(1, 3))]
                if case % 5 == 0:
                    for e in c['edges']:
                        e['kv_capacity_bytes'] = 4
                elif case % 5 == 1:
                    for m in c['models']:
                        m['context_window_tokens'] = 2
                sync_edges(c)
                sim, out = self.run_checked(c)
                self.assertEqual(out, ServingSimulator(copy.deepcopy(c)).run())
                self.assertEqual(out['summary']['completed_turns'] + out['summary']['unfinished_turns'], out['summary']['planned_turns'])
                for f in out['network_flows']:
                    self.assertLessEqual(f['transferred_bytes'], f['ready_bytes'])
                    if f['status'] == 'completed':
                        self.assertEqual(f['transferred_bytes'], f['ready_bytes'])
                for row in out['turns']:
                    self.assertLessEqual(row['delivered'], row['decode_done'])
                    if row['status'] == 'completed':
                        self.assertEqual(row['delivered'], row['decode_done'])
                blocked_cases += out['summary']['blocked_sessions'] > 0
                context_cases += any(s['termination_reason'] == 'ContextLimit' for s in out['sessions'])
        self.assertGreater(blocked_cases, 0)
        self.assertGreater(context_cases, 0)


if __name__ == '__main__':
    unittest.main()
