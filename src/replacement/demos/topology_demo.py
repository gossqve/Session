"""Validate and display S2-A static topology, without transmitting any bytes."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path

from ..core.entities import EdgeState
from ..simulation.events import EventQueue
from ..network.topology import NetworkTopology


def run_demo(config):
    # Standalone fixture builds real existing EdgeState entities. A runtime
    # consumer instead passes its already-created Edges to from_config.
    queue = EventQueue()
    edges = [EdgeState(e["id"], e["gpu_work_per_second"], e["gpu_slots"],
                       e["kv_capacity_bytes"], frozenset(e["deployed_models"]), queue,
                       area_id=e["area_id"]) for e in config["edges"]]
    topology = NetworkTopology.from_config(config, edges=edges)
    serving = []
    for access, execution in topology.validate_serving_pairs():
        up, down = topology.validate_access_execution(access, execution)
        serving.append({"access_edge_id": access, "execution_edge_id": execution,
                        "uplink": asdict(up), "downlink": asdict(down), "valid": True})
    mobility = [{"old_access": source, "new_access": target,
                 "forwarding_path": asdict(topology.get_path(source, target)), "valid": True}
                for source, target in topology.validate_mobility_transitions()]
    return {"summary": {"stage": "S2-A", "scope": "static topology and reachability only",
                        "areas": len(topology.areas), "edges": len(topology.edges),
                        "links": len(topology.links), "paths": len(topology.paths),
                        "serving_pairs_checked": len(serving), "mobility_transitions_checked": len(mobility),
                        "scheduled_events": bool(queue)},
            "areas": [{**asdict(area), "edge_ids": topology.edges_in_area(area.area_id)}
                      for area in topology.areas.values()],
            "edges": [{"edge_id": e.edge_id, "area_id": e.area_id} for e in topology.edges.values()],
            "links": [asdict(link) for link in topology.links.values()],
            "paths": [asdict(path) for path in topology.paths.values()],
            "mobility_adjacency": {source: sorted(targets) for source, targets in topology.mobility_adjacency.items()},
            "serving_checks": serving, "mobility_checks": mobility}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, help="Optional NEW output directory")
    args = parser.parse_args()
    if args.out and args.out.exists():
        raise FileExistsError("Choose a new output directory")
    config = json.loads(args.config.read_text(encoding="utf8"))
    result = run_demo(config)
    if args.out:
        args.out.mkdir(parents=True, exist_ok=False)
        for name, value in (("topology", result), ("config", config)):
            (args.out / (name + ".json")).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
