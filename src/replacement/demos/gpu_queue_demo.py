"""S1-B computation-only demo: GPU Ready, FCFS admission and Equal-Share."""
import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
from typing import Any

from ..simulation.events import EventQueue
from ..resources.gpu_queue import GPUQueue


def run_demo(config: dict[str, Any]) -> dict[str, Any]:
    queue = EventQueue()
    scheduler = GPUQueue(queue, config["edge_id"], config["capacity"], config["slots"])
    seen = set()
    for task in config["tasks"]:
        task_id = task["task_id"]
        if not isinstance(task_id, str) or not task_id or task_id in seen:
            raise ValueError("task_id must be a nonempty unique string")
        for name in ("work", "ready_time"):
            value = task[name]
            if (isinstance(value, bool) or not isinstance(value, (int, float))
                    or not math.isfinite(value) or value < 0):
                raise ValueError(f"{name} must be finite and nonnegative")
        seen.add(task_id)
        queue.schedule(task["ready_time"], "gpu_queue_demo_ready", priority=30,
                       task_id=task_id, work=task["work"])
    completions = []
    count = 0
    while queue:
        count += 1
        if count > 100000:
            raise RuntimeError("Demo event safety limit reached")
        event = queue.pop()
        if event.kind == "gpu_queue_demo_ready":
            result = scheduler.ready(event.payload["task_id"], event.payload["work"], event.time)
        else:
            result = scheduler.handle_event(event)
        completions.extend(asdict(c) for c in result)
    tasks = [asdict(task) for task in scheduler.tasks.values()]
    return {"summary": {"stage": "S1-B", "scope": "GPU computation only",
                        "edge_id": scheduler.edge_id, "capacity": scheduler.capacity,
                        "slots": scheduler.slots, "completed_tasks": len(completions),
                        "total_consumed_work": sum(t["consumed_work"] for t in tasks),
                        "last_completion_s": max((c["time_s"] for c in completions), default=0)},
            "tasks": tasks, "completions": completions,
            "scheduler_trace": scheduler.trace, "gpu_trace": scheduler.gpu_trace}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    print(json.dumps(run_demo(config), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
