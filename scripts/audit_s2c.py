"""Small exact independent Oracle comparisons, emitted as auditable JSON."""
import json
from pathlib import Path
import random
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from max_min_oracle import vertex_oracle
from test_max_min_oracle import allocate
from test_max_min_runtime import runtime, add, dispatch


def main():
    rows = []
    for seed in range(60):
        rng = random.Random(seed)
        links = ["a", "b", "c"]
        caps = {link: rng.choice([0.1, 1, 3, 7, 11, 80]) for link in links}
        paths = {f"f{i}": rng.sample(links, rng.randint(1, 3)) for i in range(rng.randint(1, 4))}
        expected = vertex_oracle(paths, caps)
        actual = allocate(paths, caps)
        if actual != expected:
            raise AssertionError((seed, expected, actual))
        rows.append({"seed": seed, "paths": paths, "capacities_bps": caps,
                     "oracle_exact": {k: str(v) for k, v in expected.items()},
                     "actual_exact": {k: str(v) for k, v in actual.items()}, "exact_match": True})
    queue, topology, transport = runtime(80)
    def point():
        return {"time_s": transport.time_s,
                "flows": {key: {"transferred_bytes": float(flow.transferred_bytes),
                                  "rate_bps": float(flow.rate_bps), "status": flow.status.value}
                          for key, flow in transport.flows.items()}}
    add(transport, topology, "f1")
    timeline = [point()]
    add(transport, topology, "f2", .5)
    timeline.append(point())
    transport.advance(1)
    timeline.append(point())
    notices = []
    while transport.flows["f1"].completed_at is None:
        notices.extend(transport.handle_event(queue.pop()))
    timeline.append(point())
    notices.extend(dispatch(queue, transport))
    timeline.append(point())
    actual = [(notice.flow_id, notice.time_s) for notice in notices]
    if actual != [("f1", 1.5), ("f2", 2.0)]:
        raise AssertionError(actual)
    print(json.dumps({"method": "rational ordered-region vertex enumeration, no progressive filling",
                      "cases": rows, "all_exact": True,
                      "dynamic_join": {"timeline": timeline, "completions": actual,
                                       "network_trace": transport.trace}}, indent=2))


if __name__ == "__main__":
    main()
