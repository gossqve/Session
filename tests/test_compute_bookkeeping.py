"""Pruning finished metadata sync work must not prune computation history."""
import copy
import json
from pathlib import Path
import unittest
from test_serving import config
from replacement.simulation.serving import ServingSimulator


class ComputeBookkeepingTests(unittest.TestCase):
    def test_compact_sync_retains_every_unit_and_exact_serving_results(self):
        c=config(slots=2,capacity=1024);c["models"][0]["output_limit_per_turn"]=80
        for s in c["sessions"]:s["turns"]=[dict(input_tokens=3,output_tokens=60)]
        runs=[]
        for compact in [False,True]:
            sim=ServingSimulator(copy.deepcopy(c))
            for edge in sim.runtime.edges.values():
                edge.compute.compact_sync=compact
                edge.compute.scheduler.fast_snapshots=compact
            result=sim.run()
            tasks={t.task_id:(t.start_time,t.completion_time,t.status,t.consumed_work,t.remaining_work)
                   for e in sim.runtime.edges.values() for t in e.compute.tasks.values()}
            runs.append((result,tasks))
        self.assertEqual(runs[0],runs[1]);self.assertEqual(len(runs[1][1]),126)

    def test_compact_metadata_with_kv_block_recovery_is_identical(self):
        root=Path(__file__).resolve().parents[1]
        c=json.loads((root/'configs/s1d_recover.json').read_text(encoding='utf-8'))
        a,b=ServingSimulator(c),ServingSimulator(copy.deepcopy(c))
        for edge in b.runtime.edges.values():
            edge.compute.compact_sync=True
            edge.compute.scheduler.fast_snapshots=True
        self.assertEqual(a.run(),b.run())

    def test_direct_snapshot_matches_full_mapping_in_all_queue_phases(self):
        sim=ServingSimulator(config())
        while sim.step() is not None:
            for edge in sim.runtime.edges.values():
                queue=edge.compute.scheduler
                for key,value in queue.tasks.items():
                    self.assertEqual(queue.task_snapshot(key),value)
