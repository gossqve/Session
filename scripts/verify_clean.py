"""Run the full suite in a fresh, reviewed-file-only system temporary copy.

The source workspace and all prior runs are preserved. Logs, copied input hashes,
random seeds and any new failure artifacts survive cleanup in a NEW evidence dir.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time

from prepare_release import read_files


ROOT = Path(__file__).resolve().parents[1]
TEMP_PREFIX = "session_clean_"


def copy_inputs(workspace, names):
    """Copy explicit reviewed inputs to a new directory, without walking source."""
    workspace.mkdir(exist_ok=False)
    manifest = []
    for name in names:
        source, target = ROOT / name, workspace / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        manifest.append({"path": name,
                         "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    if (workspace / "runs").exists():
        raise AssertionError("Fresh test workspace must start without runs/")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="New evidence directory; existing paths are refused")
    parser.add_argument("--seed", type=int, help="Master seed; default SESSION_TEST_SEED or fresh entropy")
    parser.add_argument("--cases", type=int, help="Random cases; default SESSION_TEST_CASES or 50")
    args = parser.parse_args()
    seed = (args.seed if args.seed is not None else
            int(os.environ["SESSION_TEST_SEED"]) if "SESSION_TEST_SEED" in os.environ else
            secrets.randbits(64))
    cases = args.cases if args.cases is not None else int(os.environ.get("SESSION_TEST_CASES", "50"))
    if cases < 1:
        parser.error("--cases must be positive")
    names = read_files("github")
    if names != read_files("server"):
        raise ValueError("Review and synchronize both release lists before clean verification")
    output = (args.out or ROOT / "runs" /
              ("clean_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))).resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = {"status": "FAIL", "source_root": str(ROOT), "output_directory": str(output),
              "python_executable": sys.executable, "python_version": sys.version,
              "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "master_seed": seed, "case_count": cases, "copied_input_count": len(names)}
    started = time.perf_counter()
    temporary = tempfile.TemporaryDirectory(prefix=TEMP_PREFIX)
    owned_root = Path(temporary.name).resolve()
    system_temp = Path(tempfile.gettempdir()).resolve()
    workspace = owned_root / "repo"
    try:
        if owned_root.parent != system_temp or not owned_root.name.startswith(TEMP_PREFIX):
            raise AssertionError("Temporary workspace is outside the owned system-temp boundary")
        manifest = copy_inputs(workspace, names)
        (output / "input_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report.update(workspace=str(workspace), runs_absent_before_tests=not (workspace / "runs").exists())
        env = dict(os.environ, PYTHONPATH=str(workspace / "src"), PYTHONNOUSERSITE="1",
                   PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1",
                   SESSION_TEST_SEED=str(seed), SESSION_TEST_CASES=str(cases))
        for key in ("PYTHONHOME", "PYTHONSTARTUP", "PYTHONUSERBASE", "PYTHONPYCACHEPREFIX"):
            env.pop(key, None)
        report["environment_overrides"] = {key: env[key] for key in (
            "PYTHONPATH", "PYTHONNOUSERSITE", "PYTHONIOENCODING", "PYTHONDONTWRITEBYTECODE",
            "SESSION_TEST_SEED", "SESSION_TEST_CASES")}
        command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]
        report["argv"] = command
        print(f"Clean workspace: {workspace}\nMaster seed: {seed}; cases: {cases}", flush=True)
        with (output / "unittest.stdout.txt").open("x", encoding="utf-8") as stdout, \
                (output / "unittest.stderr.txt").open("x", encoding="utf-8") as stderr:
            completed = subprocess.run(command, cwd=workspace, env=env, stdout=stdout, stderr=stderr)
        report["exit_code"] = completed.returncode
        text = (output / "unittest.stderr.txt").read_text(encoding="utf-8")
        count = re.search(r"^Ran (\d+) tests? in ([\d.]+)s$", text, re.MULTILINE)
        if count:
            report.update(test_count=int(count.group(1)), unittest_duration_s=float(count.group(2)))
        for line in text.splitlines():
            if line.startswith('{"random_summary":'):
                report["random_summary"] = json.loads(line)["random_summary"]
        report["status"] = "PASS" if completed.returncode == 0 else "FAIL"
        return completed.returncode
    except Exception as error:
        report["error"] = repr(error)
        raise
    finally:
        # Only this process's new temp tree is cleaned; preserve new test failures first.
        try:
            generated = workspace / "runs"
            if generated.exists():
                if not generated.resolve().is_relative_to(owned_root):
                    raise AssertionError("Generated test runs escaped the owned workspace")
                shutil.copytree(generated, output / "clone_runs")
                report["generated_artifacts"] = "clone_runs"
        except Exception as error:
            report.update(status="FAIL", error=repr(error))
            raise
        finally:
            try:
                if (owned_root.parent != system_temp or not owned_root.name.startswith(TEMP_PREFIX)
                        or owned_root == ROOT or not workspace.resolve().is_relative_to(owned_root)):
                    raise AssertionError("Refusing cleanup outside the owned temporary directory")
                temporary.cleanup()
                report["temporary_workspace_removed"] = not owned_root.exists()
            except Exception as error:
                report.update(status="FAIL", cleanup_error=repr(error))
                raise
            finally:
                report["elapsed_s"] = time.perf_counter() - started
                (output / "verification.json").write_text(
                    json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print(f"{report['status']}; evidence: {output / 'verification.json'}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
