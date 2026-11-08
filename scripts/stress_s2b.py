"""Deterministic small remote workloads; conservation and lifecycle audit."""
from collections import Counter
import copy
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from replacement.simulation.serving import ServingSimulator


def main():
    base = json.loads((ROOT / "configs/s2b_remote.json").read_text(encoding="utf8"))
    outcomes = Counter()
    generated = delivered = 0
    for seed in range(200):
        rng = random.Random(seed)
        config = copy.deepcopy(base)
        config["sessions"][0]["turns"] = [dict(input_tokens=rng.randrange(4), output_tokens=rng.randrange(6))
                                           for _ in range(rng.randint(1, 3))]
        config["edges"][1]["kv_capacity_bytes"] = rng.choice([0, 4, 8, 20, 100])
        config["topology"]["edges"] = copy.deepcopy(config["edges"])
        config["models"][0]["context_window_tokens"] = rng.choice([2, 5, 100])
        config["models"][0]["decode_work_per_token"] = rng.choice([0.3, 1, 2])
        config["network"]["wireless_up_bits_per_second"] = rng.choice([8, 40, 80])
        config["network"]["wireless_down_bits_per_second"] = rng.choice([8, 40, 80])
        sim = ServingSimulator(config)
        result = sim.run()
        for resource in (sim.network, sim.wireless):
            for f in resource.flows.values():
                assert 0 <= f.transferred_bytes <= f.ready_bytes, (seed, f)
                if f.status == "completed":
                    assert f.producer_closed and f.pending_bytes == 0, (seed, f)
                if result["sessions"][0]["status"] in ("ended", "failed"):
                    assert f.status in ("completed", "cancelled"), (seed, f)
        ids = [tuple(t["token_id"]) for t in result["output_tokens"]]
        assert len(ids) == len(set(ids)), seed
        for t in result["output_tokens"]:
            if t["received_at"] is not None:
                assert t["generated_at"] <= t["wired_arrived_at"] <= t["wireless_started_at"] <= t["received_at"], (seed, t)
        for previous, current in zip(result["turns"], result["turns"][1:]):
            assert current["submitted_at"] == previous["received_at"], seed
        outcomes[result["sessions"][0]["status"]] += 1
        generated += len(ids)
        delivered += sum(t["delivered"] for t in result["output_tokens"])
    print(json.dumps({"seeds": [0, 199], "scenarios": 200, "outcomes": outcomes,
                      "generated_tokens": generated, "delivered_tokens": delivered,
                      "conservation_lifecycle_fifo_zero_idle": True}, indent=2))


if __name__ == "__main__":
    main()
