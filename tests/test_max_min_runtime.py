"""True shared-kernel event progression, not assigned completion times."""
from dataclasses import replace
from fractions import Fraction
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from replacement.network.runtime import NetworkRuntime
from replacement.network.topology import NetworkTopology
from replacement.simulation.events import EventQueue
from test_topology import fixture


def runtime(capacity=80, allocator=None):
    config=fixture()
    config['links']=[replace(l,capacity_bps=capacity) if l.link_id=='12' else l for l in config['links']]
    topology=NetworkTopology(**config);queue=EventQueue()
    return queue,topology,NetworkRuntime(queue,topology,allocator=allocator)


def add(r,t,f,when=0,size=10,close=True,token=None,rate=None,kind='response'):
    notices=list(r.create(f,kind,f,0,when,path=t.paths['p12'],rate_bps=rate))
    notices.extend(r.supply(f,size,when,token_id=token));notices.extend(r.start(f,when))
    if close:notices.extend(r.close(f,when))
    return notices


def dispatch(q,r):
    notices=[]
    while q:notices.extend(r.handle_event(q.pop()))
    return notices


class MaxMinRuntimeTests(unittest.TestCase):
    def test_multihop_kv_copy_competes_once_and_preserves_cancelled_bytes(self):
        q,t,r=runtime()
        for fid,kind in (("copy","kv_copy"),("prompt","prompt")):
            r.create(fid,kind,fid,None,0,path=t.paths['p13'],operation_id='synthetic')
            r.supply(fid,15,0);r.start(fid,0);r.close(fid,0)
        self.assertEqual(len(r.flows['copy'].link_ids),3)
        self.assertEqual([f.rate_bps for f in r.flows.values()],[30,30])
        r.cancel('copy',2)
        self.assertEqual(r.flows['copy'].transferred_bytes,Fraction(15,2))
        self.assertEqual(r.flows['prompt'].rate_bps,60)
        notices=dispatch(q,r)
        self.assertEqual([(n.flow_id,n.time_s) for n in notices],[('prompt',3.)])
        self.assertEqual(r.flows['prompt'].transferred_bytes,15)
        self.assertEqual(sum(f.transferred_bytes for f in r.flows.values()),Fraction(45,2))

    def test_dynamic_join_exact_bytes_forecast_and_finish(self):
        q,t,r=runtime();add(r,t,'f1');add(r,t,'f2',.5)
        self.assertEqual(r.flows['f1'].transferred_bytes,5)
        self.assertEqual([r.flows[f].rate_bps for f in ('f1','f2')],[40,40])
        r.advance(1)
        self.assertEqual([r.flows[f].transferred_bytes for f in ('f1','f2')],[Fraction(15,2),Fraction(5,2)])
        notices=dispatch(q,r)
        self.assertEqual([(n.flow_id,n.time_s) for n in notices],[('f1',1.5),('f2',2.)])
        self.assertEqual([f.transferred_bytes for f in r.flows.values()],[10,10])

    def test_positive_cap_reclaims_unused_capacity(self):
        q,t,r=runtime(100);add(r,t,'f1',rate=30);add(r,t,'f2')
        self.assertEqual([r.flows[f].rate_bps for f in ('f1','f2')],[30,70])
        self.assertEqual(r.flows['f1'].rate_limit_bps,30)
        r.set_rate('f1',10,0)
        self.assertEqual([r.flows[f].rate_bps for f in ('f1','f2')],[10,90])

    def test_thirds_capacity_exact_and_audit_serializable(self):
        q,t,r=runtime()
        for f in ('a','b','c'):add(r,t,f,size=1)
        self.assertEqual([f.rate_bps for f in r.flows.values()],[Fraction(80,3)]*3)
        notices=dispatch(q,r);self.assertEqual([n.time_s for n in notices],[.3]*3)
        json.dumps(r.trace)
        rows=[row for row in r.trace if row['kind']=='allocation']
        self.assertTrue(rows)
        row=next(row for row in rows if len(row['participants'])==3)
        self.assertEqual(row['links']['12']['load_bps'],80)
        self.assertEqual(row['links']['12']['residual_bps'],0)
        self.assertEqual(row['links']['12']['utilization'],1)
        self.assertTrue(row['links']['12']['saturated'])

    def test_pause_cancel_resume_preserve_progress(self):
        q,t,r=runtime();add(r,t,'a');add(r,t,'b')
        r.set_rate('a',0,.5)
        self.assertEqual(r.flows['a'].transferred_bytes,Fraction(5,2))
        self.assertEqual(r.flows['b'].rate_bps,80)
        r.cancel('b',.75);self.assertEqual(r.flows['b'].transferred_bytes,5)
        r.set_rate('a',80,.75)
        self.assertEqual([(n.flow_id,n.time_s) for n in dispatch(q,r)],[('a',1.5)])
        self.assertEqual(r.flows['b'].rate_bps,0)

    def test_stream_empty_resupply_keeps_identity_and_one_shot_tokens(self):
        q,t,r=runtime();add(r,t,'a',size=1,close=False,token='a1');add(r,t,'b',size=10)
        notices=[]
        while not notices:notices.extend(r.handle_event(q.pop()))
        self.assertEqual([(n.token_id,n.time_s) for n in notices],[('a1',.2)])
        self.assertEqual(r.flows['a'].rate_bps,0);self.assertEqual(r.flows['b'].rate_bps,80)
        r.supply('a',1,.3,token_id='a2');r.close('a',.3)
        notices.extend(dispatch(q,r))
        self.assertEqual([(n.token_id,n.time_s) for n in notices if n.kind=='token_arrived'],[('a1',.2),('a2',.5)])
        self.assertEqual([(n.flow_id,n.time_s) for n in notices if n.kind=='completed'],[('a',.5),('b',1.2)])

    def test_zero_allocator_result_remains_eligible_next_reallocation(self):
        class InitiallyZero:
            first=True
            def allocate(self,flows,topology):
                rates={f.flow_id:0 if self.first else 80/len(flows) for f in flows}
                if flows:self.first=False
                return rates
        q,t,r=runtime(allocator=InitiallyZero());add(r,t,'a',close=False)
        r.close('a',0)
        self.assertEqual([(n.flow_id,n.time_s) for n in dispatch(q,r)],[('a',1.)])

    def test_rejected_change_at_shared_boundary_does_not_swallow_notices(self):
        q,t,r=runtime();add(r,t,'a',size=1,token='a1');add(r,t,'b',size=1,token='b1')
        with self.assertRaises(ValueError):r.supply('a',1,.2)
        self.assertEqual(r.time_s,0)
        notices=dispatch(q,r)
        self.assertEqual([(n.flow_id,n.kind,n.time_s) for n in notices],
                         [('a','token_arrived',.2),('a','completed',.2),('b','token_arrived',.2),('b','completed',.2)])

    def test_kv_copy_same_fairness_and_cancel_retains_logical_bytes(self):
        q,t,r=runtime();add(r,t,'prompt',kind='prompt');add(r,t,'kv',kind='kv_copy')
        self.assertEqual(r.flows['kv'].rate_bps,40)
        r.cancel('kv',.5);self.assertEqual(r.flows['kv'].transferred_bytes,Fraction(5,2))
        self.assertEqual([(n.flow_id,n.time_s) for n in dispatch(q,r)],[('prompt',1.25)])

    def test_completion_join_tie_preserves_finished_notification(self):
        q,t,r=runtime();add(r,t,'a',size=1,token='a1');add(r,t,'b',size=1)
        notices=add(r,t,'c',when=.2,size=1)
        notices.extend(dispatch(q,r))
        self.assertEqual([(n.flow_id,n.kind,n.time_s) for n in notices],
                         [('a','token_arrived',.2),('a','completed',.2),('b','completed',.2),('c','completed',.3)])

    def test_cancel_and_pause_at_completion_leave_completion_once(self):
        for action in ('cancel','pause'):
            with self.subTest(action=action):
                q,t,r=runtime();add(r,t,'a',size=1);add(r,t,'b',size=1)
                notices=r.cancel('a',.2) if action=='cancel' else r.set_rate('a',0,.2)
                self.assertEqual([(n.flow_id,n.kind,n.time_s) for n in notices],
                                 [('a','completed',.2),('b','completed',.2)])
                self.assertEqual(dispatch(q,r),[])

    def test_empty_token_boundary_and_resupply_same_clock(self):
        q,t,r=runtime();add(r,t,'a',size=1,close=False,token='a1');add(r,t,'b')
        notices=list(r.supply('a',1,.2,token_id='a2'));r.close('a',.2)
        self.assertEqual(r.flows['a'].transferred_bytes,1)
        self.assertEqual(r.flows['a'].rate_bps,40)
        notices.extend(dispatch(q,r))
        self.assertEqual([(n.token_id,n.time_s) for n in notices if n.kind=='token_arrived'],
                         [('a1',.2),('a2',.4)])

    def test_segmented_advance_matches_single_dispatch_with_shared_fraction(self):
        def run(checkpoints):
            q,t,r=runtime(.1)
            for f in ('a','b','c'):add(r,t,f,size=1,token=f)
            for time in checkpoints:r.advance(time)
            notices=dispatch(q,r)
            return [(n.flow_id,n.kind,n.time_s) for n in notices],[(f.transferred_bytes,f.completed_at) for f in r.flows.values()]
        self.assertEqual(run([]),run([.1,.2,1,100,239.9]))
        self.assertEqual(run([])[1],[(1,240.)]*3)
