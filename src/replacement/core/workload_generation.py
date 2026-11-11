"""Private seeded offline workload generation; never expose plans to policies."""
from dataclasses import asdict
from fractions import Fraction
import hashlib
import json
import random
from .entities import ModelSpec, identifier, integer, number
from .workload import WorkloadPlan, SessionPlan, TurnPlan, WorkloadDriver


def _rng(seed, purpose):
    return random.Random(
        int.from_bytes(
            hashlib.sha256(
                json.dumps([seed, purpose], separators=(",", ":")).encode()
            ).digest(),
            "big",
        )
    )


class PoissonArrivalGenerator:
    def __init__(self, rate, horizon, seed):
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise ValueError("seed must be an integer")
        number(rate)
        number(horizon)
        if 0 < horizon < 1e-12:
            raise ValueError("Positive horizon must be at least one clock tick")
        self.rate, self.horizon, self.seed = rate, horizon, seed

    def generate(self):
        if not self.rate or not self.horizon:
            return ()
        # Quantize inside the window without dropping a sampled arrival.
        tick = Fraction("1e-12")
        last_tick = int(Fraction(str(self.horizon)) // tick)
        last_time = float(last_tick * tick)
        rng = _rng(self.seed, "arrivals")
        times = []
        elapsed = 0.0
        while True:
            elapsed += rng.expovariate(self.rate)
            if elapsed > self.horizon:
                break
            timestamp = max(1e-12, round(elapsed, 12))
            times.append(min(timestamp, last_time))
        return tuple(times)


class WorkloadGenerator:
    def __init__(self, config):
        self.config = config

    def validate(self):
        """Validate configuration without drawing any arrivals or attributes."""
        self._validated_parameters()

    def _validated_parameters(self):
        c = self.config
        w = c["workload"]
        if w["mode"] != "poisson":
            raise ValueError("Expected poisson workload mode")
        number(c["observation_end_s"])
        arrivals = PoissonArrivalGenerator(
            w["arrival_rate_per_s"], w["arrival_horizon_s"], c.get("seed", 0)
        )
        if c["observation_end_s"] < w["arrival_horizon_s"]:
            raise ValueError("observation_end_s must cover arrival horizon")
        bounds = {}
        for name in ("turn_count", "input_tokens", "output_tokens"):
            lo, hi = w[name]["min"], w[name]["max"]
            integer(lo, minimum=1 if name == "turn_count" else 0)
            integer(hi, minimum=1 if name == "turn_count" else 0)
            if lo > hi:
                raise ValueError("Invalid inclusive bounds")
            bounds[name] = (lo, hi)
        models = [ModelSpec.from_config(m) for m in c["models"]]
        matching = [m for m in models if m.model_id == w["model_id"]]
        if (
            len(matching) != 1
            or bounds["output_tokens"][1] != matching[0].output_limit_per_turn
        ):
            raise ValueError("Output maximum must equal selected model output limit")
        edges = sorted(
            e["id"] for e in c["edges"] if w["model_id"] in e["deployed_models"]
        )
        if not edges:
            raise ValueError("No eligible deployed Edge")
        from ..network.wireless import resolve_wireless_rate

        net = c["network"]
        up, down = resolve_wireless_rate(net, "up"), resolve_wireless_rate(net, "down")
        integer(net["text_bytes_per_token"])
        identifier(c.get("scenario", "unnamed"))
        for edge in edges:
            identifier(edge)
        if len(edges) != len(set(edges)):
            raise ValueError("Duplicate eligible Edge ID")
        return arrivals, bounds, edges, up, down

    def generate(self):
        arrivals, bounds, edges, up, down = self._validated_parameters()
        c = self.config
        w = c["workload"]
        net = c["network"]
        sessions = []
        seed = c.get("seed", 0)
        for i, t in enumerate(arrivals.generate()):

            def stream(name):
                return _rng(seed, f"session:{i}:{name}")

            edge = stream("edge").choice(edges)
            n = stream("turn_count").randint(*bounds["turn_count"])
            inputs, outputs = stream("input_tokens"), stream("output_tokens")
            turns = tuple(
                TurnPlan(
                    inputs.randint(*bounds["input_tokens"]),
                    outputs.randint(*bounds["output_tokens"]),
                )
                for _ in range(n)
            )
            sessions.append(
                SessionPlan(
                    f"session_{i:08d}",
                    w["model_id"],
                    t,
                    edge,
                    edge,
                    turns,
                    up,
                    down,
                    net["text_bytes_per_token"],
                )
            )
        plan = WorkloadPlan(tuple(sessions), seed, c.get("scenario", "unnamed"))
        WorkloadDriver(plan)
        return plan


def workload_to_dict(plan):
    return json.loads(json.dumps(asdict(plan), allow_nan=False))


def workload_from_dict(data):
    sessions = []
    for raw in data["sessions"]:
        s = dict(raw)
        s["turns"] = tuple(TurnPlan(**t) for t in s["turns"])
        sessions.append(SessionPlan(**s))
    plan = WorkloadPlan(
        tuple(sessions), data.get("seed", 0), data.get("scenario", "unnamed")
    )
    WorkloadDriver(plan)
    return plan


def workload_hash(plan):
    return hashlib.sha256(
        json.dumps(
            workload_to_dict(plan),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()
