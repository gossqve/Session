"""Run the unified S1-D workload; optional artifact directory must be new."""
import argparse
import csv
import json
from pathlib import Path

from ..simulation.serving import ServingSimulator


def run_demo(config):
    return ServingSimulator(config).run()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.out and args.out.exists():
        raise FileExistsError("Choose a new --out directory to preserve existing results")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    result = run_demo(config)
    if args.out:
        args.out.mkdir(parents=True, exist_ok=False)
        for name in ("summary", "sessions", "resources", "gpu_events", "kv_events", "output_tokens"):
            (args.out / (name + ".json")).write_text(json.dumps(result[name], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        # Offline reproducibility config is not handed to an online policy.
        (args.out / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (args.out / "turns.json").write_text(json.dumps(result["turns"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        with (args.out / "turns.csv").open("w", encoding="utf-8", newline="") as stream:
            if result["turns"]:
                writer = csv.DictWriter(stream, fieldnames=list(result["turns"][0]))
                writer.writeheader()
                writer.writerows(result["turns"])
        with (args.out / "events.jsonl").open("w", encoding="utf-8") as stream:
            for event in result["events"]:
                stream.write(json.dumps(event, ensure_ascii=False) + "\n")
        print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
        print(f"Saved: {args.out}")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
