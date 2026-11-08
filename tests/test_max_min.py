"""Hand-derived progressive filling cases (algorithm-level path views)."""
from fractions import Fraction
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))


def allocate(paths, capacities, limits=None):
    from replacement.network.max_min import MaxMinAllocator
    flows = [NS(flow_id=f, path=NS(link_ids=links), rate_limit_bps=(limits or {}).get(f))
             for f, links in paths.items()]
    topology = NS(links={l:NS(capacity_bps=c) for l,c in capacities.items()})
    return MaxMinAllocator().allocate(flows, topology)


class MaxMinTests(unittest.TestCase):
    def test_hand_cases(self):
        for paths,caps,want in [
            ({'a':['x']}, {'x':80}, {'a':80}),
            ({'a':['x'],'b':['x']}, {'x':80}, {'a':40,'b':40}),
            ({'a':['x','y'],'b':['x'],'c':['y']}, {'x':12,'y':6}, {'a':3,'b':9,'c':3}),
            ({'a':['x','y'],'b':['x']}, {'x':100_000_000,'y':30_000_000}, {'a':30_000_000,'b':70_000_000}),
            ({'a':['forward'],'b':['back']}, {'forward':80,'back':90}, {'a':80,'b':90}),
            ({'a':['x','y'],'b':['x','y'],'c':['z']}, {'x':80,'y':80,'z':7}, {'a':40,'b':40,'c':7}),
            ({}, {'x':80}, {}),
        ]:
            with self.subTest(paths=paths):self.assertEqual(allocate(paths,caps),want)

    def test_exact_thirds_and_decimal_capacity_order_independent(self):
        paths={'a':['x'],'b':['x'],'c':['x']}
        for cap in (80,0.1):
            want={f:Fraction(str(cap))/3 for f in paths}
            self.assertEqual(allocate(paths,{'x':cap}),want)
            self.assertEqual(allocate(dict(reversed(list(paths.items()))),{'x':cap}),want)

    def test_rate_limit_recycles_capacity_as_virtual_constraint(self):
        self.assertEqual(allocate({'a':['x'],'b':['x']},{'x':100},{'a':30}),{'a':30,'b':70})
        self.assertEqual(allocate({'a':['x'],'b':['x']},{'x':100},{'a':0}),{'a':0,'b':100})

    def test_invalid_paths_and_duplicate_ids_are_rejected(self):
        for paths in ({'a':[]},{'a':['missing']},{'a':['x','x']}):
            with self.subTest(paths=paths),self.assertRaises(ValueError):allocate(paths,{'x':80})
