"""Negative controls: real CLI artifacts must fail audit after physical corruption.

No permanent fixture or prior run is read. Temporary evidence is owned by this class.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from verify_s3c import audit


class S3CAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary=tempfile.TemporaryDirectory(prefix='s3c_audit_controls_')
        # unittest runs class cleanups even if the subprocess below fails in setup.
        cls.addClassCleanup(temporary.cleanup)
        cls.output=Path(temporary.name)
        cls.valid=cls.output/'valid'
        result=subprocess.run([sys.executable,'-m','replacement.demos.serving_demo','--config','configs/s3c_hand_shared.json','--out',str(cls.valid)],
                              cwd=ROOT,env=dict(os.environ,PYTHONPATH=str(ROOT/'src')),capture_output=True,text=True)
        if result.returncode:raise AssertionError(result.stderr)

    def mutate(self,filename,change):
        directory=self.output/self._testMethodName
        shutil.copytree(self.valid,directory)
        path=directory/filename
        value=json.loads(path.read_text(encoding='utf-8'));change(value)
        path.write_text(json.dumps(value),encoding='utf-8')
        with self.assertRaises(AssertionError):audit(directory,oracle=True)

    def test_rejects_full_e2e_not_matching_delivery_events(self):
        self.mutate('summary.json',lambda d:d.update(mean_full_turn_e2e_s=1))

    def test_rejects_completed_subset_diagnostic_not_matching_ue_events(self):
        self.mutate('evaluation.json',lambda d:d['summary'].update(mean_completed_full_turn_e2e_s=99))

    def test_rejects_kv_commit_not_matching_structural_formula(self):
        def corrupt(d):
            record=next(r for r in d['E2'] if r['event']=='token_committed')
            record['session_kv_after']+=4
        self.mutate('kv_events.json',corrupt)

    def test_rejects_drain_end_not_matching_last_ue_delivery(self):
        def corrupt(d):
            record=next(r for r in d['events'] if r['event']=='handover_start')
            record['drain_end_s']+=.1
        self.mutate('handover.json',corrupt)

    def test_rejects_final_flow_snapshot_disagreeing_with_byte_trace(self):
        def corrupt(rows):
            record=next(r for r in rows if r['flow_type']=='response')
            record['transferred_bytes']=0
        self.mutate('network_flows.json',corrupt)

    def test_rejects_byte_progress_not_matching_previous_rate(self):
        directory=self.output/self._testMethodName;shutil.copytree(self.valid,directory)
        path=directory/'network_events.jsonl'
        rows=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
        record=next(r for r in rows if r['kind']=='progress')
        record['transferred_bytes']+=.01
        path.write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
        with self.assertRaises(AssertionError):audit(directory,oracle=True)


if __name__=='__main__':unittest.main()
