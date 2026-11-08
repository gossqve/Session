"""Production allocator against a separate lexicographic vertex Oracle."""
from fractions import Fraction
from pathlib import Path
import random
import sys
from types import SimpleNamespace
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from max_min_oracle import vertex_oracle
from replacement.network.max_min import MaxMinAllocator


def allocate(paths, capacities):
    flows = [SimpleNamespace(flow_id=name, path=SimpleNamespace(link_ids=tuple(links)),
                             rate_limit_bps=None) for name, links in paths.items()]
    topology = SimpleNamespace(links={key: SimpleNamespace(capacity_bps=cap)
                                      for key, cap in capacities.items()})
    return MaxMinAllocator().allocate(flows, topology)


class MaxMinOracleTests(unittest.TestCase):
    def test_independent_oracle_hand_cases(self):
        for paths, caps, expected in (
            ({"f1": ["a"], "f2": ["a"]}, {"a": 80}, {"f1": 40, "f2": 40}),
            ({"f1": ["a", "b"], "f2": ["a"], "f3": ["b"]}, {"a": 12, "b": 6}, {"f1": 3, "f2": 9, "f3": 3}),
            ({"f1": ["a", "b"], "f2": ["a"]}, {"a": 100, "b": 30}, {"f1": 30, "f2": 70}),
        ):
            self.assertEqual(vertex_oracle(paths, caps), expected)
            self.assertEqual(allocate(paths, caps), expected)

    def test_fixed_seed_oracle_capacity_and_input_permutation(self):
        for seed in range(60):
            rng = random.Random(seed)
            links = ["a", "b", "c"]
            capacities = {link: rng.choice([0.1, 1, 3, 7, 11, 80]) for link in links}
            paths = {f"f{i}": rng.sample(links, rng.randint(1, 3)) for i in range(rng.randint(1, 4))}
            expected = vertex_oracle(paths, capacities)
            with self.subTest(seed=seed):
                actual = allocate(paths, capacities)
                self.assertEqual(actual, expected)
                self.assertEqual(allocate(dict(reversed(list(paths.items()))), capacities), expected)
                for link, cap in capacities.items():
                    self.assertLessEqual(sum(actual[f] for f in paths if link in paths[f]), Fraction(str(cap)))
