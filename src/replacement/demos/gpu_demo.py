"""S1-A computation-only multi-session demo, using S0's event engine."""
from dataclasses import asdict
import argparse
import json
import math
from pathlib import Path
from typing import Any

from ..simulation.events import EventQueue
from ..resources.gpu import EqualShareGPU


def run_demo(config: dict[str, Any]) -> tuple[dict, list[dict]]:
    queue = EventQueue()
    gpu = EqualShareGPU(queue, config["edge_id"], config["capacity"])
    seen = set()
    for task in config["tasks"]:
        task_id, arrival, work = task["task_id"], task["arrival_s"], task["work"]
        if not isinstance(task_id, str) or not task_id or task_id in seen:
            raise ValueError("Demo task IDs must be nonempty and unique")
        for name, value in [("arrival", arrival), ("work", work)]:
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or value < 0):
                raise ValueError(f"{name} must be finite and nonnegative")
        seen.add(task_id)
        queue.schedule(arrival, "gpu_demo_arrival", priority=30, task_id=task_id, work=work)
    completions = []
    event_count = 0
    while queue:
        event_count += 1
        if event_count > 100000:
            raise RuntimeError("Demo event safety limit reached")
        event = queue.pop()
        if event.kind == "gpu_demo_arrival":
            result = gpu.submit(event.payload["task_id"], event.payload["work"], event.time)
        else:
            result = gpu.handle_event(event)
        completions.extend(asdict(c) for c in result)
    summary = {"stage": "S1-A", "scope": "GPU computation only", "edge_id": gpu.edge_id,
               "completed_tasks": len(completions), "completions": completions,
               "last_completion_s": max((c["time_s"] for c in completions), default=0),
               "total_consumed_work": sum(t.consumed_work for t in gpu.tasks.values())}
    return summary, gpu.trace


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    summary, trace = run_demo(json.loads(args.config.read_text(encoding="utf-8")))
    print(json.dumps({"summary": summary, "trace": trace}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
