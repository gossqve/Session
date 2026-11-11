"""Local S3-A acceptance, including unchanged core Serving at a common cutoff."""
import argparse
from copy import deepcopy
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="New output directory, never an existing run")
    args = parser.parse_args()
    output = args.out or ROOT / "runs" / ("s3a_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONIOENCODING="utf8")
    evidence = {"commands": [], "output_directory": str(output)}

    def invoke(label, arguments):
        command = [sys.executable, *arguments]
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf8")
        for suffix, text in (("stdout", result.stdout), ("stderr", result.stderr)):
            (output / f"{label}.{suffix}.txt").write_text(text, encoding="utf8")
        evidence["commands"].append(dict(label=label, argv=command, exit_code=result.returncode))
        if result.returncode:
            raise RuntimeError(f"{label} failed; inspect {output}")
        print(label, "exit=0", flush=True)
        return result

    invoke("mobility_tests", ["-m", "unittest", "discover", "-s", "tests", "-p", "test_mobility.py", "-v"])
    invoke("all_tests", ["-m", "unittest", "discover", "-s", "tests", "-v"])
    for label in ("s1e", "s2c"):
        result = invoke(label, [f"scripts/verify_{label}.py"])
        path = Path(result.stdout.strip().split("Evidence: ")[-1])
        evidence[label] = json.loads(path.read_text(encoding="utf8"))
    config = json.loads((ROOT / "configs/s3a_mobility_smoke.json").read_text(encoding="utf8"))
    cli = output / "smoke"
    invoke("smoke", ["-m", "replacement.demos.serving_demo", "--config", "configs/s3a_mobility_smoke.json", "--out", str(cli)])
    summary = json.loads((cli / "summary.json").read_text(encoding="utf8"))
    mobility = json.loads((cli / "mobility.json").read_text(encoding="utf8"))
    if summary["stage"] != "S3-A" or summary["completed_turns"] != 2:
        raise AssertionError(summary)
    counts = mobility["summary"]
    if (counts["planned_access_changes"] != 1 or counts["pending_moves_added"] != 1
            or counts["pending_moves_cancelled"] != 1 or counts["pending_moves_at_observation_end"] != 0
            or counts["max_pending_depth"] != 1 or counts["mobility_checks"] <= 0):
        raise AssertionError(counts)
    session = mobility["sessions"][0]
    if (session["planned_access_edge_id"], session["actual_access_edge_id"], session["execution_edge_id"]) != ("E2", "E1", "E3"):
        raise AssertionError(session)
    pending = [e for e in mobility["events"] if e["event"] == "mobility_pending_added"]
    if len(pending) != 1 or (pending[0]["source_edge_id"], pending[0]["target_edge_id"]) != ("E1", "E2"):
        raise AssertionError(pending)

    sys.path.insert(0, str(ROOT / "src"))
    from replacement.simulation.serving import ServingSimulator
    active = ServingSimulator(config).run()
    baseline_config = deepcopy(config)
    baseline_config.pop("mobility")
    baseline = ServingSimulator(baseline_config)
    baseline.advance_to(config["observation_end_s"])
    plain = baseline.results()
    for key, value in plain.items():
        if key != "summary" and active[key] != value:
            raise AssertionError(f"Core Serving changed: {key}")
    normalized = dict(active["summary"], stage="S2-C")
    if normalized != plain["summary"]:
        raise AssertionError("Core summary changed")
    for key in ("summary", "mobility", "turns", "output_tokens", "network_flows", "resources"):
        if json.loads((cli / f"{key}.json").read_text(encoding="utf8")) != json.loads(json.dumps(active[key])):
            raise AssertionError(f"CLI snapshot differs: {key}")
    tokens = active["output_tokens"]
    ids = [tuple(t["token_id"]) for t in tokens]
    if len(ids) != len(set(ids)) or len(tokens) != sum(t["delivered"] for t in active["turns"]):
        raise AssertionError("Duplicate or missing Token")
    if any((t["access_edge_id"], t["execution_edge_id"]) != ("E1", "E3") or not t["delivered"] for t in tokens):
        raise AssertionError("Token provenance or delivery changed")
    for flow in active["network_flows"]:
        if flow["ready_bytes"] != flow["transferred_bytes"] or flow["status"] != "completed":
            raise AssertionError("Wired Byte conservation")
    for flow in active["wireless_transfers"]:
        if flow["ready_bytes"] != flow["transferred_bytes"] or flow["status"] != "completed":
            raise AssertionError("Wireless Byte conservation")
    for turn in active["turns"]:
        own = sorted((t for t in tokens if t["turn_index"] == turn["turn_index"]), key=lambda t: t["output_index"])
        if [t["output_index"] for t in own] != list(range(1, turn["delivered"] + 1)):
            raise AssertionError("Token FIFO prefix")
    if summary["final_kv_bytes"] != 0 or summary["gpu_work"] != 8:
        raise AssertionError("KV/GPU accounting")
    (output / "baseline.json").write_text(json.dumps(plain, ensure_ascii=False, indent=2), encoding="utf8")
    evidence.update(summary=summary, mobility=mobility, core_results_identical=True,
                    token_count=len(tokens), wired_bytes=sum(f["transferred_bytes"] for f in active["network_flows"]),
                    wireless_bytes=sum(f["transferred_bytes"] for f in active["wireless_transfers"]))
    (output / "verification.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print("Evidence:", output / "verification.json", flush=True)


if __name__ == "__main__":
    main()
