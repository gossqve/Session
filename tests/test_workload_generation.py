import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import unittest
from replacement.core.workload_generation import (
    PoissonArrivalGenerator,
    workload_hash,
    workload_to_dict,
    workload_from_dict,
)
from replacement.core.workload import WorkloadPlan


class GeneratorTests(unittest.TestCase):
    def test_reproducible_and_window(self):
        a = PoissonArrivalGenerator(10, 10, 12).generate()
        self.assertEqual(a, PoissonArrivalGenerator(10, 10, 12).generate())
        self.assertTrue(all(0 < t <= 10 for t in a))

    def test_empty_invalid(self):
        self.assertEqual(PoissonArrivalGenerator(0, 10, 1).generate(), ())
        for x in [-1, float("inf"), True]:
            with self.assertRaises(ValueError):
                PoissonArrivalGenerator(x, 10, 1)

    def test_roundtrip(self):
        p = WorkloadPlan((), 42, "test")
        self.assertEqual(p, workload_from_dict(workload_to_dict(p)))
        self.assertEqual(len(workload_hash(p)), 64)

    def test_statistics(self):
        import statistics

        counts = [
            len(PoissonArrivalGenerator(4, 10, s).generate()) for s in range(1000)
        ]
        self.assertAlmostEqual(statistics.mean(counts), 40, delta=1)
        self.assertAlmostEqual(statistics.variance(counts), 40, delta=6)


from copy import deepcopy
import json
import statistics
from replacement.core.workload_generation import WorkloadGenerator


def config():
    return dict(
        seed=42,
        scenario="generated",
        observation_end_s=10,
        models=[
            dict(
                id="m",
                layers=1,
                kv_heads=1,
                head_dim=1,
                element_bytes=1,
                context_window_tokens=1,
                output_limit_per_turn=3,
                prefill_work_per_token=1,
                decode_work_per_token=1,
            )
        ],
        edges=[
            dict(id="b", deployed_models=["m"]),
            dict(id="a", deployed_models=["m"]),
            dict(id="z", deployed_models=[]),
        ],
        network=dict(
            wireless_up_bits_per_second=80,
            wireless_down_bits_per_second=40,
            text_bytes_per_token=2,
        ),
        workload=dict(
            mode="poisson",
            arrival_rate_per_s=30,
            arrival_horizon_s=10,
            model_id="m",
            turn_count=dict(min=1, max=3),
            input_tokens=dict(min=0, max=4),
            output_tokens=dict(min=0, max=3),
        ),
    )


class FullGeneratorTests(unittest.TestCase):
    def test_json_representation(self):
        p = WorkloadGenerator(config()).generate()
        d = workload_to_dict(p)
        self.assertIsInstance(d["sessions"], list)
        self.assertEqual(p, workload_from_dict(json.loads(json.dumps(d))))
        self.assertEqual(workload_hash(p), workload_hash(workload_from_dict(d)))
        c = config()
        c["seed"] = 43
        self.assertNotEqual(
            workload_hash(p), workload_hash(WorkloadGenerator(c).generate())
        )

    def test_bounds_binding_and_reproducibility(self):
        c = config()
        p = WorkloadGenerator(c).generate()
        self.assertEqual(p, WorkloadGenerator(c).generate())
        self.assertEqual({s.access_edge_id for s in p.sessions}, {"a", "b"})
        for s in p.sessions:
            self.assertEqual(s.access_edge_id, s.execution_edge_id)
            self.assertEqual(s.model_id, "m")
            self.assertEqual(
                (
                    s.wireless_up_bits_per_second,
                    s.wireless_down_bits_per_second,
                    s.text_bytes_per_token,
                ),
                (80, 40, 2),
            )
        self.assertEqual({len(s.turns) for s in p.sessions}, {1, 2, 3})
        self.assertEqual(
            {t.input_tokens for s in p.sessions for t in s.turns}, set(range(5))
        )
        self.assertEqual(
            {t.hidden_output_tokens for s in p.sessions for t in s.turns}, set(range(4))
        )
        self.assertEqual(len({s.session_id for s in p.sessions}), len(p.sessions))
        # Context window deliberately smaller than generated context: no cropping.
        self.assertTrue(
            any(sum(t.input_tokens for t in s.turns) > 1 for s in p.sessions)
        )

    def test_stream_independence(self):
        c = config()
        p = WorkloadGenerator(c).generate()
        for field in ["input_tokens", "output_tokens", "turn_count"]:
            changed = deepcopy(c)
            changed["workload"][field]["min"] = changed["workload"][field]["max"]
            q = WorkloadGenerator(changed).generate()
            for s, t in zip(p.sessions, q.sessions):
                self.assertEqual(
                    (s.arrival_time, s.access_edge_id),
                    (t.arrival_time, t.access_edge_id),
                )
                if field != "turn_count":
                    self.assertEqual(len(s.turns), len(t.turns))
                for a, b in zip(s.turns, t.turns):
                    if field != "input_tokens":
                        self.assertEqual(a.input_tokens, b.input_tokens)
                    if field != "output_tokens":
                        self.assertEqual(a.hidden_output_tokens, b.hidden_output_tokens)
        changed = deepcopy(c)
        changed["edges"].reverse()
        self.assertEqual(p, WorkloadGenerator(changed).generate())

    def test_invalid_config(self):
        mutations = [("observation_end_s", float("inf")), ("observation_end_s", 9)]
        for key, value in mutations:
            c = config()
            c[key] = value
            with self.assertRaises(ValueError):
                WorkloadGenerator(c).generate()
        for field in ["turn_count", "input_tokens", "output_tokens"]:
            for value in [True, 1.5, -1, 10]:
                c = config()
                c["workload"][field]["min"] = value
                with self.assertRaises(ValueError):
                    WorkloadGenerator(c).generate()
        for field, value in [
            ("mode", "bad"),
            ("model_id", "missing"),
            ("arrival_rate_per_s", -1),
            ("arrival_horizon_s", float("nan")),
        ]:
            c = config()
            c["workload"][field] = value
            with self.assertRaises(ValueError):
                WorkloadGenerator(c).generate()
        c = config()
        c["workload"]["output_tokens"]["max"] = 2
        with self.assertRaises(ValueError):
            WorkloadGenerator(c).generate()
        c = config()
        c["edges"] = []
        with self.assertRaises(ValueError):
            WorkloadGenerator(c).generate()
        c = config()
        c["models"][0]["layers"] = 0
        with self.assertRaises(ValueError):
            WorkloadGenerator(c).generate()

    def test_empty_windows_and_ties(self):
        for field in ["arrival_rate_per_s", "arrival_horizon_s"]:
            c = config()
            c["workload"][field] = 0
            self.assertEqual(WorkloadGenerator(c).generate().sessions, ())
        for value in [-1, True, float("inf"), float("nan")]:
            with self.assertRaises(ValueError):
                PoissonArrivalGenerator(1, value, 0)
        times = PoissonArrivalGenerator(1e14, 1e-12, 3).generate()
        self.assertTrue(all(0 < t <= 1e-12 for t in times))
        self.assertLess(len(set(times)), len(times))
        self.assertEqual(tuple(sorted(times)), times)

    def test_exponential_moments(self):
        # First interarrival across independent seeds avoids horizon censoring.
        values = [PoissonArrivalGenerator(2, 20, s).generate()[0] for s in range(3000)]
        self.assertAlmostEqual(statistics.mean(values), 0.5, delta=0.04)
        self.assertAlmostEqual(statistics.variance(values), 0.25, delta=0.05)

    def test_validate_and_seed(self):
        from unittest.mock import patch

        with patch.object(
            PoissonArrivalGenerator,
            "generate",
            side_effect=AssertionError("must not sample"),
        ):
            self.assertIsNone(WorkloadGenerator(config()).validate())
        for seed in [True, 1.5, "42"]:
            c = config()
            c["seed"] = seed
            with self.assertRaises(ValueError):
                WorkloadGenerator(c).validate()
            with self.assertRaises(ValueError):
                PoissonArrivalGenerator(1, 1, seed)
        c = config()
        c["edges"] = [dict(id="new", deployed_models=["m"])]
        a = WorkloadGenerator(config()).generate()
        b = WorkloadGenerator(c).generate()
        self.assertEqual([s.turns for s in a.sessions], [s.turns for s in b.sessions])


class ArrivalBoundaryTests(unittest.TestCase):
    def test_rounding_preserves_in_window_arrival(self):
        from unittest.mock import Mock, patch

        source = Mock()
        source.expovariate.side_effect = [1.55e-12, 1e-12]
        with patch("replacement.core.workload_generation._rng", return_value=source):
            self.assertEqual(
                PoissonArrivalGenerator(1, 1.6e-12, 0).generate(), (1e-12,)
            )
