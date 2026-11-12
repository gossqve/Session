"""Fixed regression contracts plus at least 50 new-seed legal scenarios by default."""
import json
import random
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from random_serving import assert_result, case_seed, digest, make_case, run_cases, settings
from replacement.simulation.serving import ServingSimulator
from test_serving import config


class RandomServingTests(unittest.TestCase):
    def test_oracle_accepts_check_before_zero_turn_end_at_same_clock(self):
        c=make_case(339005402618853528801423281470299864121,210)
        sim=ServingSimulator(c);out=sim.run()
        events=[e for e in out['mobility']['events'] if e['session_id']=='S3']
        check=next(i for i,e in enumerate(events) if e['event']=='mobility_check' and e['time_s']==.8)
        end=next(i for i,e in enumerate(events) if e['event']=='mobility_session_end')
        self.assertLess(check,end)
        self.assertEqual(sim.runtime.sessions['S3'].end_time,.8)
        assert_result(sim,c)

    def test_oracle_accepts_real_delivered_context_limit_prefix_without_g1_credit(self):
        for down_rate in (80,8000):
            with self.subTest(wireless_down_bits_per_second=down_rate):
                c=config();c['sessions']=c['sessions'][:1];c['observation_end_s']=3
                c['network']['wireless_down_bits_per_second']=down_rate
                c['models'][0]['context_window_tokens']=5
                c['sessions'][0]['turns']=[dict(input_tokens=1,output_tokens=3),dict(input_tokens=0,output_tokens=3)]
                sim=ServingSimulator(c);out=sim.run();failed=out['turns'][1]
                self.assertEqual((failed['status'],failed['reason'],failed['decode_done'],failed['delivered']),('failed','ContextLimit',1,1))
                self.assertIsNotNone(failed['received_at'])
                self.assertIsNone(out['summary']['mean_full_turn_e2e_s'])
                self.assertEqual(out['summary']['completed_turns'],1)
                last=out['output_tokens'][-1]['received_at']
                self.assertEqual(failed['received_at'],max(last,failed['generation_ended_at']))
                if down_rate==8000:self.assertLess(last,failed['received_at'])
                assert_result(sim,c)

    def test_oracle_rejects_forged_full_population_denominator(self):
        c=make_case(1729,0);sim=ServingSimulator(c);out=sim.run()
        corrupt=deepcopy(out)
        corrupt['summary']['planned_turns']=out['summary']['completed_turns']
        completed=[t['received_at']-t['submitted_at'] for t in out['turns'] if t['status']=='completed']
        corrupt['summary']['mean_full_turn_e2e_s']=round(sum(completed)/len(completed),12)
        # Corrupt only a serialized report from a real run, never the engine.
        with patch.object(sim,'results',return_value=corrupt), self.assertRaises(AssertionError):
            assert_result(sim,c)

    def test_oracle_rejects_out_of_order_ue_identity_with_same_token_set(self):
        c=config();c['sessions']=c['sessions'][:1]
        c['sessions'][0]['turns'][0]['output_tokens']=3;c['observation_end_s']=3
        sim=ServingSimulator(c);out=sim.run();corrupt=deepcopy(out)
        deliveries=[e for e in corrupt['events'] if e['event']=='downlink_done']
        deliveries[0]['token_id'],deliveries[1]['token_id']=deliveries[1]['token_id'],deliveries[0]['token_id']
        for field in ('received_at','delivered_at'):
            a,b=corrupt['output_tokens'][:2]
            a[field],b[field]=b[field],a[field]
        with patch.object(sim,'results',return_value=corrupt), self.assertRaises(AssertionError):
            assert_result(sim,c)

    def test_serialization_failure_preserves_case_and_propagates(self):
        with TemporaryDirectory(prefix='s3_random_failure_control_') as tmp:
            with patch('random_serving.ROOT',Path(tmp)), patch('random_serving.make_case',return_value={'scenario':'control'}), patch('random_serving.exercise',return_value=({'diagnostic':float('nan')},{})):
                with self.assertRaises(ValueError):run_cases(1729,1,emit=lambda value:None)
            failures=list((Path(tmp)/'runs').glob('random_failure_*'))
            self.assertEqual(len(failures),1)
            metadata=json.loads((failures[0]/'failure.json').read_text(encoding='utf-8'))
            self.assertEqual((metadata['master_seed'],metadata['case_index'],metadata['case_seed']),(1729,0,case_seed(1729,0)))
            self.assertTrue((failures[0]/'config.json').is_file())
            self.assertIn('ValueError',(failures[0]/'error.txt').read_text(encoding='utf-8'))

    def test_daily_generated_legal_scenarios(self):
        master,count=settings()
        result=run_cases(master,count,emit=lambda value:print(value,file=sys.stderr,flush=True))
        self.assertEqual(result['passed'],count)
        self.assertEqual(result['failed'],0)
        print(json.dumps(dict(random_summary={k:v for k,v in result.items() if k!='cases'})),file=sys.stderr,flush=True)

    def test_seed_derivation_and_local_rng_are_stable(self):
        first=[digest(make_case(1729,i)) for i in range(8)]
        saved=random.getstate()
        try:
            random.seed(123);[random.random() for _ in range(20)]
            self.assertEqual(first,[digest(make_case(1729,i)) for i in range(8)])
        finally:random.setstate(saved)
        self.assertEqual(len({case_seed(1729,i) for i in range(50)}),50)

