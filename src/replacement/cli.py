"""CLI: python -m replacement.cli --config configs/s0_smoke.json --out runs/s0."""
import argparse
import csv
import json
from pathlib import Path

from .s0 import S0Simulator


def run_cli() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic S0 smoke simulation")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    summary, turns, events = S0Simulator(config).run()
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (args.out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with (args.out / "turns.csv").open("w", newline="", encoding="utf-8") as fp:
        writer = csv.DictWriter(fp, fieldnames=["session_id", "turn", "submitted_at_s",
                                                 "received_at_s", "e2e_s", "input_tokens",
                                                 "output_tokens", "status"])
        writer.writeheader()
        writer.writerows(turns)
    with (args.out / "events.jsonl").open("w", encoding="utf-8") as fp:
        for evt in events:
            fp.write(json.dumps(evt, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Saved: {args.out}")


if __name__ == "__main__":
    run_cli()
