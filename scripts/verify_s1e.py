"""Local S1-E acceptance: tests + eight real CLI regressions in a NEW directory.

Only standard library; no installs, Git writes or remote operations. Run from
the repository root: python scripts/verify_s1e.py [--out NEW_DIRECTORY].
"""
import argparse
from datetime import datetime
import importlib
import json
import os
from pathlib import Path
import pkgutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    output = args.out or ROOT / "runs" / ("s1e_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"), PYTHONIOENCODING="utf-8")
    evidence = {"python_version": sys.version.split()[0], "output_directory": str(output), "commands": []}

    def invoke(label, arguments):
        command = [sys.executable, *arguments]
        completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf8")
        (output / (label + ".stdout.txt")).write_text(completed.stdout, encoding="utf8")
        (output / (label + ".stderr.txt")).write_text(completed.stderr, encoding="utf8")
        evidence["commands"].append({"label": label, "argv": command, "exit_code": completed.returncode})
        if completed.returncode:
            raise RuntimeError(f"{label} failed; inspect {output}")
        print(label, "exit=0")
        return completed

    invoke("cleanup_tests", ["-m", "unittest", "discover", "-s", "tests", "-p", "test_cleanup.py", "-v"])
    invoke("new_tests", ["-m", "unittest", "discover", "-s", "tests", "-p", "test_s1e.py", "-v"])
    invoke("all_tests", ["-m", "unittest", "discover", "-s", "tests", "-v"])
    reference = json.loads((ROOT / "docs/s1d_verification.json").read_text(encoding="utf8"))
    legacy = {}
    target = output / "s0"
    invoke("s0", ["-m", "replacement.cli", "--config", "configs/s0_smoke.json", "--out", str(target)])
    legacy["S0"] = json.loads((target / "summary.json").read_text(encoding="utf8"))
    for key, label, module, config in (
        ("S1-A", "s1a", "replacement.demos.gpu_demo", "configs/s1a_gpu_smoke.json"),
        ("S1-B", "s1b", "replacement.demos.gpu_queue_demo", "configs/s1b_gpu_queue_smoke.json"),
        ("S1-C", "s1c", "replacement.demos.kv_demo", "configs/s1c_kv_smoke.json"),
    ):
        run = invoke(label, ["-m", module, "--config", config])
        legacy[key] = json.loads(run.stdout)["summary"]
    for key, result in legacy.items():
        if result != reference["legacy_smokes"][key]:
            raise AssertionError(f"{key} summary changed: {result}")
    evidence["legacy_smokes"] = legacy
    serving = {}
    for name in ("normal", "queue", "recover", "blocked"):
        target = output / name
        config = f"configs/s1d_{name}.json"
        invoke(name, ["-m", "replacement.demos.serving_demo", "--config", config, "--out", str(target)])
        summary = json.loads((target / "summary.json").read_text(encoding="utf8"))
        if summary != reference["serving_smokes"][name]["summary"]:
            raise AssertionError(f"{name} summary changed: {summary}")
        tokens = json.loads((target / "output_tokens.json").read_text(encoding="utf8"))
        turns = json.loads((target / "turns.json").read_text(encoding="utf8"))
        events = [json.loads(line) for line in (target / "events.jsonl").read_text(encoding="utf8").splitlines()]
        kv = json.loads((target / "kv_events.json").read_text(encoding="utf8"))
        recovery = sum(e["reason"] == "PendingCommitRecovered" for trace in kv.values() for e in trace)
        if recovery != (1 if name == "recover" else 0):
            raise AssertionError(f"{name} recovery count changed")
        ids = [tuple(t["token_id"]) for t in tokens]
        if len(set(ids)) != len(ids):
            raise AssertionError("Duplicate generated Token")
        delivered = [e for e in events if e["event"] == "downlink_done"]
        for row in turns:
            own = [t for t in tokens if (t["session_id"], t["turn_index"]) == (row["session_id"], row["turn_index"])]
            actual = [e for e in delivered if (e["session_id"], e["turn_index"]) == (row["session_id"], row["turn_index"])]
            if [t["output_index"] for t in own] != list(range(1, row["decode_done"] + 1)):
                raise AssertionError("Generated output does not match legal Decode commits")
            if [e["unit_index"] for e in actual] != list(range(1, row["delivered"] + 1)):
                raise AssertionError("Output is out of order or delivered twice")
            for token in own:
                if (token["execution_edge_id"] != row["execution_edge_id"]
                        or token["access_edge_id"] != row["submitted_access_edge_id"]):
                    raise AssertionError("Fixed-access provenance changed")
                if token["received_at"] is not None and token["received_at"] < token["generated_at"]:
                    raise AssertionError("Delivered before generation")
        serving[name] = {"summary": summary, "output_directory": str(target), "generated_tokens": len(tokens),
                         "delivered_tokens": len(delivered), "recovered_units": recovery, "fifo_once": True}
    evidence["serving_smokes"] = serving
    sys.path.insert(0, str(ROOT / "src"))
    package = importlib.import_module("replacement")
    modules = [m.name for m in pkgutil.walk_packages(package.__path__, "replacement.")]
    for name in modules:
        importlib.import_module(name)
    evidence["imported_module_count"] = len(modules)
    evidence["all_baselines_unchanged"] = True
    (output / "verification.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print("All S1 baselines unchanged. Evidence:", output / "verification.json")


if __name__ == "__main__":
    main()
