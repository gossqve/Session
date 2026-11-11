"""Completed history may leave active bookkeeping, never the resource ledger."""
from dataclasses import asdict
import unittest
import test_network_runtime as fixtures


class HistoryTests(unittest.TestCase):
    def test_compact_transaction_restores_progress_and_mutable_boundaries(self):
        helper=fixtures.TransportTests();q,t,r=helper.wired(compact_history=True)
        helper.add(r,t,size=10,token='one')
        before=asdict(r.get_flow('f'));old_allocator=r.allocator;old_trace=list(r.trace)
        class FailAfterSupply:
            def allocate(self,flows,topology):
                if any(f.ready_bytes>10 for f in flows):raise ValueError('after producer mutation')
                return old_allocator.allocate(flows,topology)
        r.allocator=FailAfterSupply()
        with self.assertRaises(ValueError):r.supply('f',3,.01,token_id='two')
        self.assertEqual(asdict(r.get_flow('f')),before)
        self.assertEqual(r.trace,old_trace)
        self.assertEqual(r.time_s,0)
        self.assertTrue(any(r.is_current_event(q.pop()) for _ in range(len(q._heap))))
    def test_unchanged_future_boundary_keeps_single_valid_forecast(self):
        helper=fixtures.TransportTests();q,t,r=helper.wired(compact_history=True)
        helper.add(r,t,size=10);r.close('f',0)
        allocations=sum(row.get('kind')=='allocation' for row in r.trace)
        for i in range(1,20):r.advance(i/1000)
        queued=[]
        while q:queued.append(q.pop())
        self.assertEqual(len(queued),1)
        self.assertTrue(r.is_current_event(queued[0]))
        self.assertEqual(sum(row.get('kind')=='allocation' for row in r.trace),allocations)
    def test_archive_keeps_immutable_results_and_prevents_duplicate_ids(self):
        helper = fixtures.TransportTests(); q,t,r = helper.wired(compact_history=True)
        helper.add(r,t,size=2,token='one');r.close('f',0)
        helper.dispatch(q,r)
        before = asdict(r.get_flow('f'))
        r.archive_terminal()
        self.assertEqual(r._records,{})
        self.assertEqual(asdict(r.flows['f']),before)
        self.assertEqual(asdict(r.get_flow('f')),before)
        with self.assertRaises(ValueError): helper.add(r,t)

    def test_failed_change_rolls_back_reactivated_history(self):
        helper = fixtures.TransportTests();q,t,r = helper.wired(compact_history=True)
        helper.add(r,t,size=2);r.close('f',0);helper.dispatch(q,r);r.archive_terminal()
        before = asdict(r.get_flow('f'))
        with self.assertRaises(ValueError):r.supply('f',1,r.time_s)
        self.assertEqual(asdict(r.get_flow('f')),before)

    def test_compaction_preserves_actual_bytes_times_and_notices(self):
        results=[]
        for compact in [False,True]:
            helper=fixtures.TransportTests();q,t,r=helper.wired(compact_history=compact)
            now=0;notices=[]
            for i in range(8):
                fid=f'f{i}'
                r.create(fid,'response','s',i,now,path=t.paths['p12'])
                r.supply(fid,2,now,token_id=f't{i}');r.close(fid,now);r.start(fid,now)
                notices.extend(helper.dispatch(q,r));now=r.time_s;r.archive_terminal()
            flows=[asdict(f) for f in r.flows.values()]
            for f in flows:
                f.pop('event_version');f.pop('last_update_at')
            results.append((flows,notices))
        self.assertEqual(results[0],results[1])
