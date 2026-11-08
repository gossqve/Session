"""Exact byte transport, shared event queue, and staged allocator contracts."""
from dataclasses import FrozenInstanceError
from fractions import Fraction
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from replacement.simulation.events import EventQueue
from replacement.network.runtime import NetworkRuntime
from replacement.network.wireless import WirelessRuntime, resolve_wireless_rate
from replacement.network.allocator import S2CRequired, DisjointPathAllocator
from replacement.network.topology import NetworkTopology
from test_topology import fixture


class TransportTests(unittest.TestCase):
    def wired(self, **kwargs):
        q = EventQueue(); t = NetworkTopology(**fixture())
        return q, t, NetworkRuntime(q, t, **kwargs)

    def add(self, r, t, name='f', path='p12', size=10, token=None):
        r.create(name, 'response', 's', 0, 0, path=t.paths[path])
        r.supply(name, size, 0, token_id=token)
        return r.start(name, 0)

    def dispatch(self, q, r):
        result = []
        while q:
            result.extend(r.handle_event(q.pop()))
        return result

    def test_open_stream_boundaries_wait_resume_close(self):
        q,t,r=self.wired();self.add(r,t,size=2,token='t1')
        notices=self.dispatch(q,r)
        self.assertEqual([(n.kind,n.token_id,n.time_s) for n in notices], [('token_arrived','t1',.16)])
        self.assertEqual(r.flows['f'].status,'waiting_for_data')
        r.supply('f',3,.2,token_id='t2');r.close('f',.2)
        notices=self.dispatch(q,r)
        self.assertEqual([(n.kind,n.time_s) for n in notices],[('token_arrived',.44),('completed',.44)])
        self.assertEqual(r.flows['f'].transferred_bytes,5)
        self.assertEqual(r.close('f',.44),())
        with self.assertRaises(ValueError):r.supply('f',1,.44)

    def test_fractional_progress_cancel_and_immutable_snapshot(self):
        q,t,r=self.wired();self.add(r,t)
        r.advance(.1);self.assertEqual(r.flows['f'].transferred_bytes,Fraction(5,4))
        snap=r.flows['f'];r.cancel('f',.2);r.cancel('f',.3)
        self.assertEqual(r.flows['f'].transferred_bytes,Fraction(5,2))
        self.dispatch(q,r);self.assertEqual(r.time_s,.3)
        with self.assertRaises(FrozenInstanceError):snap.ready_bytes=100
        with self.assertRaises(TypeError):r.flows['x']=snap

    def test_conflicting_paths_rejected_atomically_reverse_disjoint_allowed(self):
        q,t,r=self.wired(allocator=DisjointPathAllocator());self.add(r,t)
        r.create('g','kv_copy','s',None,0,path=t.paths['p12']);r.supply('g',10,0)
        with self.assertRaises(S2CRequired):r.start('g',0)
        self.assertIsNone(r.flows['g'].started_at)
        self.add(r,t,'reverse','p21');r.close('f',0);r.close('reverse',0)
        self.dispatch(q,r);self.assertEqual(r.flows['f'].completed_at,.8)
        self.assertEqual(r.flows['reverse'].completed_at,1.)

    def test_multihop_is_one_end_to_end_transfer(self):
        q,t,r=self.wired();self.add(r,t,path='p13',size=15);r.close('f',0)
        self.dispatch(q,r);self.assertEqual(r.flows['f'].completed_at,2)

    def test_stale_forecast_and_pause_resume_settle_old_rate(self):
        q=EventQueue();r=WirelessRuntime(q)
        r.create('f','upload','s',0,0,rate_bps=80);r.supply('f',10,0);r.start('f',0);r.close('f',0)
        r.set_rate('f',0,.25);self.assertEqual(r.flows['f'].transferred_bytes,Fraction(5,2))
        self.dispatch(q,r);self.assertEqual(r.time_s,.25)
        r.set_rate('f',40,2);self.dispatch(q,r)
        self.assertEqual(r.flows['f'].completed_at,3.5)

    def test_tick_up_never_free_bytes_and_cannot_skip_boundary(self):
        q=EventQueue();r=WirelessRuntime(q)
        r.create('f','upload','s',0,0,rate_bps=1e16);r.supply('f',1,0);r.start('f',0);r.close('f',0)
        self.assertEqual(r.flows['f'].transferred_bytes,0)
        with self.assertRaises(ValueError):r.advance(1)
        notices=self.dispatch(q,r);self.assertEqual(notices[-1].time_s,1e-12)

    def test_zero_close_duplicate_token_and_supply_before_start(self):
        q,t,r=self.wired();r.create('f','prompt','s',0,0,path=t.paths['p12'])
        r.close('f',0);self.assertEqual(r.start('f',0)[0].kind,'completed')
        self.assertFalse(q)
        r.create('g','response','s',0,0,path=t.paths['p12']);r.supply('g',0,0,token_id='t')
        with self.assertRaises(ValueError):r.supply('g',1,0,token_id='t')
        self.assertEqual(r.start('g',0)[0].kind,'token_arrived')

    def test_allocator_validates_capacity_and_rates(self):
        class Allocator:
            def allocate(self, flows, topology):return {f.flow_id:101 for f in flows}
        q,t,r=self.wired(allocator=Allocator())
        with self.assertRaises(ValueError):self.add(r,t)
        self.assertIsNone(r.flows['f'].started_at)

    def test_formal_tuple_token_identity_is_preserved(self):
        q,t,r=self.wired(); token=('s',0,1)
        self.add(r,t,size=2,token=token)
        notices=self.dispatch(q,r)
        self.assertEqual(notices[0].token_id,token)
        self.assertEqual(r.flows['f'].token_boundaries[0].token_id,token)

    def test_wireless_config_effective_rate_and_shannon_are_exclusive(self):
        self.assertEqual(resolve_wireless_rate({'wireless_up_bits_per_second':80},'up'),80)
        self.assertEqual(resolve_wireless_rate({'wireless_down':{'bandwidth_hz':100,'efficiency':.5,'snr_linear':3}},'down'),100)
        with self.assertRaises(ValueError):resolve_wireless_rate({'wireless_up_bits_per_second':80,'wireless_up':{}},'up')

    def test_bad_path_and_scalar_inputs_are_rejected(self):
        from replacement.network.entities import FixedPath
        q,t,r=self.wired()
        for path in (None, 'p12', t.get_path('E1','E1'),
                     FixedPath('p12','E2','E1',('21',))):
            with self.subTest(path=path),self.assertRaises(ValueError):
                r.create('bad','prompt','s',0,0,path=path)
        self.add(r,t)
        for bad in (-1,True,1.5,float('nan'),'1'):
            with self.subTest(byte_count=bad),self.assertRaises(ValueError):r.supply('f',bad,0)
        for bad in (-1,True,float('inf'),float('nan'),'1'):
            with self.subTest(rate=bad),self.assertRaises(ValueError):r.set_rate('f',bad,0)
        with self.assertRaises(ValueError):r.set_rate('f',101,0)
        with self.assertRaises(ValueError):r.create('f','prompt','s',0,0,path=t.paths['p12'])
        with self.assertRaises(ValueError):r.start('missing',0)

    def test_zero_rate_wired_override_does_not_occupy_capacity(self):
        q,t,r=self.wired();self.add(r,t)
        r.set_rate('f',0,0)
        self.add(r,t,'g');r.close('g',0)
        self.dispatch(q,r)
        self.assertEqual(r.flows['g'].completed_at,.8)
        self.assertEqual(r.flows['f'].transferred_bytes,0)
        r.set_rate('f',100,.8);r.close('f',.8);self.dispatch(q,r)
        self.assertEqual(r.flows['f'].completed_at,1.6)

    def test_segmented_progress_matches_continuous_and_boundary_order(self):
        def run(checkpoints):
            q,t,r=self.wired();self.add(r,t,size=1,token='t1')
            r.supply('f',9,0,token_id='t2');r.close('f',0)
            for when in checkpoints:r.advance(when)
            notices=self.dispatch(q,r)
            return r.flows['f'],[(n.token_id,n.time_s) for n in notices if n.kind=='token_arrived']
        a,na=run([]);b,nb=run([.01,.025,.05,.079])
        self.assertEqual(a.transferred_bytes,b.transferred_bytes)
        self.assertEqual(a.completed_at,b.completed_at)
        self.assertEqual(na,nb);self.assertEqual(na,[('t1',.08),('t2',.8)])

    def test_allocator_can_be_replaced_without_replacing_kernel(self):
        class EqualTestAllocator:
            def allocate(self,flows,topology):
                return {f.flow_id:100/len(flows) for f in flows}
        q,t,r=self.wired(allocator=EqualTestAllocator())
        self.add(r,t,size=5);self.add(r,t,'g',size=10)
        r.close('f',0);r.close('g',0)
        self.dispatch(q,r)
        self.assertEqual(r.flows['f'].completed_at,.8)
        self.assertEqual(r.flows['g'].completed_at,1.2)

    def test_same_token_distinct_stages_have_independent_progress(self):
        q,t,r=self.wired();self.add(r,t,size=2,token=('s',0,1));r.close('f',0)
        self.dispatch(q,r)
        r.create('forward','handover','s',0,.16,path=t.paths['p21'],operation_id='synthetic')
        r.supply('forward',2,.16,token_id=('s',0,1));r.start('forward',.16);r.close('forward',.16)
        self.assertEqual(r.flows['forward'].transferred_bytes,0)
        self.dispatch(q,r)
        self.assertEqual(r.flows['forward'].completed_at,.36)

    def test_invalid_wireless_config_matrix(self):
        for key in ('bandwidth_hz','snr_linear','efficiency'):
            for value in (0,-1,True,float('inf'),float('nan'),'1'):
                row=dict(bandwidth_hz=100,snr_linear=3,efficiency=.5);row[key]=value
                with self.subTest(key=key,value=value),self.assertRaises(ValueError):
                    resolve_wireless_rate({'wireless_up':row},'up')
        with self.assertRaises(ValueError):
            resolve_wireless_rate({'wireless_up':dict(bandwidth_hz=1,snr_linear=1,efficiency=1.1)},'up')

    def test_wired_and_wireless_flow_types_are_separate(self):
        q,t,r=self.wired();w=WirelessRuntime(q)
        for kind in ('upload','download'):
            with self.assertRaises(ValueError):r.create(kind,kind,'s',0,0,path=t.paths['p12'])
        for kind in ('prompt','response','kv_copy','handover','input_handoff'):
            with self.assertRaises(ValueError):w.create(kind,kind,'s',0,0,rate_bps=80)

    def test_one_session_wireless_direction_cannot_duplicate_capacity(self):
        q=EventQueue();r=WirelessRuntime(q)
        for fid,kind in [('u','upload'),('u2','upload'),('d','download')]:
            r.create(fid,kind,'s',0,0,rate_bps=80);r.supply(fid,10,0)
        r.start('u',0);r.start('d',0)
        with self.assertRaises(ValueError):r.start('u2',0)
        r.close('u',0);r.close('d',0);self.dispatch(q,r)
        self.assertEqual(r.flows['u'].completed_at,1)
        self.assertEqual(r.flows['d'].completed_at,1)

    def test_tiny_snr_and_large_clock_forecasts_never_arrive_early(self):
        rate=resolve_wireless_rate({'wireless_up':dict(bandwidth_hz=100,snr_linear=1e-20,efficiency=1)},'up')
        self.assertGreater(rate,0)
        q=EventQueue();r=WirelessRuntime(q)
        r.create('f','upload','s',0,1e9,rate_bps=1e16);r.supply('f',1,1e9)
        r.start('f',1e9);r.close('f',1e9)
        notices=self.dispatch(q,r)
        self.assertGreater(Fraction(str(notices[-1].time_s)),Fraction(10**9)+Fraction(8,10**16))

    def test_rejected_mutation_at_boundary_preserves_one_shot_notices(self):
        q=EventQueue();r=WirelessRuntime(q)
        r.create('f','upload','s',0,0,rate_bps=80)
        r.supply('f',1,0,token_id='token');r.start('f',0);r.close('f',0)
        with self.assertRaises(ValueError):r.supply('f',1,.1)
        self.assertEqual(r.time_s,0)
        notices=self.dispatch(q,r)
        self.assertEqual([(n.kind,n.token_id,n.time_s) for n in notices],
                         [('token_arrived','token',.1),('completed',None,.1)])

    def test_allocator_failure_at_other_boundary_rolls_back_without_event_aliases(self):
        q,t,r=self.wired(allocator=DisjointPathAllocator());self.add(r,t,size=10,token='token');r.close('f',0)
        self.add(r,t,'h','p21',size=100)
        r.create('g','response','s',0,0,path=t.paths['p21']);r.supply('g',10,0)
        with self.assertRaises(S2CRequired):r.start('g',.8)
        self.assertEqual(r.time_s,0)
        r.cancel('h',0)
        r.start('g',0);r.close('g',0)
        notices=self.dispatch(q,r)
        self.assertEqual([(n.kind,n.time_s) for n in notices if n.flow_id=='f'],
                         [('token_arrived',.8),('completed',.8)])
        self.assertEqual([(n.kind,n.time_s) for n in notices if n.flow_id=='g'],[('completed',1.)])

if __name__=='__main__':unittest.main()

