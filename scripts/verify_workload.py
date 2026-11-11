"""Real Poisson/Actual-Handover acceptance. Run historical verifiers separately."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    output = (args.out or ROOT / "runs" / ("pre_s3b_workload_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))).resolve()
    output.mkdir(parents=True,exist_ok=False)
    env = dict(os.environ, PYTHONPATH=str(ROOT/"src"), PYTHONIOENCODING="utf-8")
    evidence = dict(commands=[], output_directory=str(output))
    def invoke(label, arguments):
        command = [sys.executable,*arguments]
        result = subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,encoding="utf-8")
        for suffix,value in [("stdout",result.stdout),("stderr",result.stderr)]:
            (output/f"{label}.{suffix}.txt").write_text(value,encoding="utf-8")
        evidence["commands"].append(dict(label=label,command=command,exit_code=result.returncode))
        if result.returncode:raise RuntimeError(f"{label} failed; inspect {output}")
        print(label,"exit=0",flush=True)
    for name in ["workload_generation","generated_serving","handover","migration_guard","transport_history","compute_bookkeeping"]:
        invoke(name,["-m","unittest","discover","-s","tests","-p",f"test_{name}.py","-v"])
    target = output/"serving"
    invoke("poisson_cli",["-m","replacement.demos.serving_demo","--config","configs/poisson_session_smoke.json","--out",str(target)])
    def load(name):return json.loads((target/f"{name}.json").read_text(encoding="utf-8"))
    summary,workload,mobility,handover = (load(n) for n in ["summary","workload","mobility","handover"])
    turns,tokens,sessions,flows,wireless = (load(n) for n in ["turns","output_tokens","sessions","network_flows","wireless_transfers"])
    config=load("config")
    plan=workload["plan"]
    if summary["stage"]!="S3-B" or summary["observation_end_s"]!=config["observation_end_s"]:
        raise AssertionError("stage or cutoff")
    if any(not 0<s["arrival_time"]<=config["workload"]["arrival_horizon_s"] for s in sessions):
        raise AssertionError("arrival window")
    deployments={e["id"]:e["deployed_models"] for e in config["edges"]}
    initial={s["session_id"]:s for s in plan["sessions"]}
    for session in sessions:
        origin=initial[session["session_id"]]
        if (origin["access_edge_id"]!=origin["execution_edge_id"]
                or origin["model_id"] not in deployments[origin["access_edge_id"]]
                or session["execution_edge_id"]!=origin["execution_edge_id"]):
            raise AssertionError("binding/Execution changed")
    ids=[tuple(t["token_id"]) for t in tokens]
    if len(set(ids))!=len(ids):raise AssertionError("duplicate generated Token")
    delivered=[tuple(t["token_id"]) for t in tokens if t["delivered"]]
    logged=[]
    for line in (target/"events.jsonl").read_text(encoding="utf-8").splitlines():
        row=json.loads(line)
        if row["time_s"]>config["observation_end_s"]:raise AssertionError("event after cutoff")
        if row["event"]=="downlink_done":logged.append(tuple(row["token_id"]))
    if len(set(logged))!=len(logged) or set(logged)!=set(delivered):raise AssertionError("delivery identity accounting")
    for turn in turns:
        own=[t for t in tokens if t["session_id"]==turn["session_id"] and t["turn_index"]==turn["turn_index"]]
        if [t["output_index"] for t in own]!=list(range(1,turn["decode_done"]+1)):
            raise AssertionError("generated prefix")
        if [t["output_index"] for t in own if t["delivered"]]!=list(range(1,turn["delivered"]+1)):
            raise AssertionError("FIFO delivery prefix")
    for flow in flows+wireless:
        if not 0<=flow["transferred_bytes"]<=flow["ready_bytes"]:
            raise AssertionError("Byte conservation")
        if flow["status"]=="completed" and flow["transferred_bytes"]!=flow["ready_bytes"]:
            raise AssertionError("completed missing Byte")
    by_flow={f["flow_id"]:f for f in flows}
    allocation_records=0
    with (target/"network_events.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            row=json.loads(line)
            if row.get("kind")!="allocation":continue
            allocation_records+=1
            if any(not 0<=link["utilization"]<=1 for link in row["links"].values()):
                raise AssertionError("directed capacity")
            groups={}
            for fid in row["active_flow_ids"]:
                f=by_flow[fid]
                if f["flow_type"] in ("response","handover"):
                    key=f["session_id"],f["turn_index"]
                    groups[key]=groups.get(key,0)+1
            if any(count>1 for count in groups.values()):raise AssertionError("multiple wired response shares")
    minimum=config["mobility"]["min_inter_move_interval_s"]
    last={};actual=0
    for event in handover["events"]:
        if event["event"]!="handover_start":continue
        actual+=1;sid=event["session_id"]
        if sid in last and round(event["time_s"]-last[sid],12)<minimum:
            raise AssertionError("actual Handover interval")
        last[sid]=event["time_s"]
        if event["drain_end_s"] is not None and event["drain_duration_s"]!=round(event["drain_end_s"]-event["time_s"],12):
            raise AssertionError("drain duration")
    if not actual or not any(f["flow_type"]=="handover" for f in flows):
        raise AssertionError("scenario did not execute real Handover forwarding")
    if mobility["summary"]["markov_move_proposals"]!=mobility["summary"]["moves_rejected_min_interval"]+mobility["summary"]["accepted_planned_moves"]:
        raise AssertionError("proposal accounting")
    if mobility["summary"]["pending_moves_added"]!=actual+mobility["summary"]["pending_moves_cancelled"]+mobility["summary"]["pending_moves_at_observation_end"]:
        raise AssertionError("Pending added/consumed/cancelled accounting")
    stats=workload["statistics"]
    if stats["arrived_sessions"]!=stats["completed_sessions"]+stats["legally_terminated_sessions"]+stats["unfinished_sessions"]:
        raise AssertionError("Session lifecycle partition")
    if stats["context_limit_ratio"] is not None and stats["context_limit_ratio"]>=.05:
        raise AssertionError("Ordinary temporary parameters need explicit calibration")
    completed=[t["e2e_s"] for t in turns if t["status"]=="completed"]
    expected=round(statistics.mean(completed),12) if len(completed)==summary["planned_turns"] and completed else None
    if summary["mean_full_turn_e2e_s"]!=expected:raise AssertionError("full-denominator E2E")
    sys.path.insert(0,str(ROOT/"src"))
    from replacement.core.workload_generation import workload_from_dict, workload_hash, PoissonArrivalGenerator
    restored=workload_from_dict(plan)
    if workload_hash(restored)!=workload["workload_hash"]:raise AssertionError("plan roundtrip/hash")
    counts=[len(PoissonArrivalGenerator(.05,600,seed).generate()) for seed in range(1000)]
    if not abs(statistics.mean(counts)-30)<1 or not abs(statistics.variance(counts)-30)<6:
        raise AssertionError("Poisson count calibration")
    gaps=[s["arrival_time"]-(plan["sessions"][i-1]["arrival_time"] if i else 0) for i,s in enumerate(plan["sessions"])]
    inputs=[t["input_tokens"] for s in plan["sessions"] for t in s["turns"]]
    outputs=[t["hidden_output_tokens"] for s in plan["sessions"] for t in s["turns"]]
    def describe(values):return dict(count=len(values),minimum=min(values,default=None),maximum=max(values,default=None),mean=statistics.mean(values) if values else None)
    evidence.update(summary=summary,session_statistics=stats,mobility=mobility["summary"],handover=handover["summary"],
                    workload_hash=workload["workload_hash"],session_examples=plan["sessions"][:5],
                    arrival_gaps_s=describe(gaps),inputs=describe(inputs),outputs=describe(outputs),
                    poisson_multi_seed=dict(seeds=1000,expected=30,mean=statistics.mean(counts),variance=statistics.variance(counts)),
                    completed_subset_mean_e2e_s=statistics.mean(completed) if completed else None,
                    generated_tokens=len(tokens),delivered_tokens=len(delivered),allocation_records=allocation_records,
                    wired_bytes=sum(f["transferred_bytes"] for f in flows),wireless_bytes=sum(f["transferred_bytes"] for f in wireless),
                    handover_forward_bytes=sum(f["transferred_bytes"] for f in flows if f["flow_type"]=="handover"))
    (output/"verification.json").write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Evidence:",output/"verification.json",flush=True)


if __name__=="__main__":main()
