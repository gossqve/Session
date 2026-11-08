"""S2-B tests, historical regression and five actual Serving CLI experiments."""
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / "runs" / ("s2b_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    output.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONIOENCODING="utf8")
    evidence = {"output_directory": str(output), "commands": [], "scenarios": {}}

    def invoke(label, args, *, reject=False):
        result = subprocess.run([sys.executable, *args], cwd=ROOT, env=env,
                                capture_output=True, text=True, encoding="utf8")
        for suffix, value in (("stdout", result.stdout), ("stderr", result.stderr)):
            (output / f"{label}.{suffix}.txt").write_text(value, encoding="utf8")
        evidence["commands"].append({"label": label, "argv": [sys.executable, *args], "exit_code": result.returncode})
        if reject:
            if not result.returncode or "S2-C" not in result.stderr:
                raise RuntimeError(f"Expected shared-link S2-C rejection, inspect {output}")
        elif result.returncode:
            raise RuntimeError(f"{label} failed, inspect {output}")
        print(label, "expected S2-C rejection" if reject else "exit=0")
        return result

    invoke("network_tests", ["-m", "unittest", "discover", "-s", "tests", "-p", "test_network*.py", "-v"])
    invoke("all_tests", ["-m", "unittest", "discover", "-s", "tests", "-v"])
    previous = invoke("s1_verifier", ["scripts/verify_s1e.py"])
    previous_path = Path(previous.stdout.strip().split("Evidence: ")[-1])
    evidence["historical_regression"] = json.loads(previous_path.read_text(encoding="utf8"))
    invoke("topology", ["-m", "replacement.demos.topology_demo", "--config", "configs/s2a_topology_smoke.json"])
    stress = invoke("stress", ["scripts/stress_s2b.py"])
    evidence["stress_audit"] = json.loads(stress.stdout)
    for name, expected in (("local", 0.4), ("remote", 0.6), ("pipeline", 1.1), ("disjoint", 0.6)):
        target = output / name
        invoke(name, ["-m", "replacement.demos.serving_demo", "--config", f"configs/s2b_{name}.json", "--out", str(target)])
        summary = json.loads((target / "summary.json").read_text(encoding="utf8"))
        if summary["mean_full_turn_e2e_s"] != expected:
            raise AssertionError((name, summary))
        evidence["scenarios"][name] = {"summary": summary, "expected_mean_e2e_s": expected,
            "error_s": summary["mean_full_turn_e2e_s"] - expected,
            "output_tokens": json.loads((target / "output_tokens.json").read_text(encoding="utf8")),
            "flows": json.loads((target / "network_flows.json").read_text(encoding="utf8"))}
    invoke("conflict", ["-m", "replacement.demos.serving_demo", "--config", "configs/s2b_conflict.json", "--allocator", "disjoint"], reject=True)
    evidence["scenarios"]["conflict"] = {"rejected_requires_s2c": True, "e2e_reported": False}
    (output / "verification.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print("Evidence:", output / "verification.json")


if __name__ == "__main__":
    main()
