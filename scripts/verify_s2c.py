"""S2-C exact Oracle, dynamic tests and actual multi-Area Serving acceptance."""
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / "runs" / ("s2c_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    output.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONIOENCODING="utf8")
    evidence = {"output_directory": str(output), "commands": [], "scenarios": {}}

    def invoke(label, arguments):
        command = [sys.executable, *arguments]
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf8")
        for suffix, text in (("stdout", result.stdout), ("stderr", result.stderr)):
            (output / f"{label}.{suffix}.txt").write_text(text, encoding="utf8")
        evidence["commands"].append({"label": label, "argv": command, "exit_code": result.returncode})
        if result.returncode:
            raise RuntimeError(f"{label} failed; inspect {output}")
        print(label, "exit=0", flush=True)
        return result

    invoke("max_min_tests", ["-m", "unittest", "discover", "-s", "tests", "-p", "test_max_min*.py", "-v"])
    oracle = invoke("oracle", ["scripts/audit_s2c.py"])
    evidence["independent_oracle"] = json.loads(oracle.stdout)
    invoke("all_tests", ["-m", "unittest", "discover", "-s", "tests", "-v"])
    previous = invoke("s2b_verifier", ["scripts/verify_s2b.py"])
    evidence["historical_regression"] = json.loads(Path(previous.stdout.strip().split("Evidence: ")[-1]).read_text(encoding="utf8"))
    for name, config in (("baseline", "configs/s2b_remote.json"),
                         ("shared", "configs/s2c_maxmin_shared.json"),
                         ("pipeline", "configs/s2c_maxmin_pipeline.json"),
                         ("three_area", "configs/s2c_maxmin_three_area.json"),
                         ("wide", "configs/s2c_maxmin_wide.json")):
        target = output / name
        invoke(name, ["-m", "replacement.demos.serving_demo", "--config", config, "--out", str(target)])
        summary = json.loads((target / "summary.json").read_text(encoding="utf8"))
        turns = json.loads((target / "turns.json").read_text(encoding="utf8"))
        tokens = json.loads((target / "output_tokens.json").read_text(encoding="utf8"))
        flows = json.loads((target / "network_flows.json").read_text(encoding="utf8"))
        allocations = [json.loads(line) for line in (target / "network_events.jsonl").read_text(encoding="utf8").splitlines()
                       if json.loads(line).get("kind") == "allocation"]
        if summary["completed_turns"] != summary["planned_turns"]:
            raise AssertionError((name, summary))
        if not allocations:
            raise AssertionError("No real allocation trace")
        for row in allocations:
            for detail in row["links"].values():
                if not 0 <= detail["utilization"] <= 1:
                    raise AssertionError((name, row))
        # Offline projections of the SAME authoritative runtime trace.
        for filename, field in (("flow_rates.jsonl", "rates_bps"), ("link_utilization.jsonl", "links"),
                                ("flow_bytes.jsonl", "flows")):
            with (target / filename).open("w", encoding="utf8") as stream:
                for row in allocations:
                    stream.write(json.dumps({"time_s": row["time_s"], "reason": row["reason"],
                                             field: row[field]}, ensure_ascii=False) + "\n")
        maxima = {link: max(row["links"][link]["utilization"] for row in allocations)
                  for link in allocations[0]["links"]}
        computed = round(sum(round(row["received_at"] - row["submitted_at"], 12) for row in turns) / len(turns), 12)
        if computed != summary["mean_full_turn_e2e_s"]:
            raise AssertionError((name, computed, summary))
        evidence["scenarios"][name] = {"summary": summary, "turns": turns, "output_tokens": tokens,
            "flows": flows, "allocation_records": len(allocations), "max_link_utilization": maxima,
            "mean_e2e_recomputed_s": computed, "mean_metric_error_s": computed - summary["mean_full_turn_e2e_s"],
            "output_directory": str(target)}
    if evidence["scenarios"]["baseline"]["summary"]["mean_full_turn_e2e_s"] != 0.6:
        raise AssertionError("S2-B baseline changed")
    (output / "verification.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print("Evidence:", output / "verification.json", flush=True)


if __name__ == "__main__":
    main()
