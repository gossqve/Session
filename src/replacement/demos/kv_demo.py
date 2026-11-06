"""S1-C formal-entity, one-Turn-per-Session KV recovery validation.

This scripted fixture uses a fixed synthetic output delivery delay. It is not
the unified multi-Session workload/network/E2E executor reserved for S1-D.
"""
import argparse
import json
from pathlib import Path

from ..core.entities import ModelSpec, EdgeState, Phase, CommitResult, number
from ..core.runtime import RuntimeState
from ..core.workload import WorkloadDriver, WorkloadPlan, SessionPlan, TurnPlan
from ..simulation.events import EventQueue


def run_demo(config=None):
    if config is None:
        config = json.loads((Path(__file__).resolve().parents[3] / "configs/s1c_kv_smoke.json").read_text(encoding="utf-8"))
    model = ModelSpec.from_config(config["model"])
    e = config["edge"]
    queue = EventQueue()
    edge = EdgeState(e["id"], e["gpu_work_per_second"], e["gpu_slots"],
                     e["kv_capacity_bytes"], frozenset({model.model_id}), queue)
    runtime = RuntimeState({model.model_id: model}, {edge.edge_id: edge})
    plans, delays = [], {}
    for row in config["sessions"]:
        number(row["delivery_delay_s"])
        delays[row["id"]] = row["delivery_delay_s"]
        plans.append(SessionPlan(row["id"], model.model_id, 0, edge.edge_id, edge.edge_id,
                                 (TurnPlan(row["input_tokens"], row["output_tokens"]),)))
    driver = WorkloadDriver(WorkloadPlan(tuple(plans)))

    def maybe_finish(s):
        turn = s.current_turn
        if turn.generation_complete and turn.delivered == turn.decode_done and turn.status != "blocked":
            runtime.finish_turn(s.session_id, runtime.time_s)
            runtime.end_session(s.session_id, runtime.time_s,
                                "ContextLimit" if turn.status == "failed" else "completed")

    def next_unit(s):
        turn = s.current_turn
        if turn.prefill_done < turn.input_tokens:
            phase, unit = Phase.PREFILL, turn.prefill_done + 1
        elif turn.decode_done < model.output_limit_per_turn and driver.has_output(s.session_id, 1, turn.decode_done):
            phase, unit = Phase.DECODE, turn.decode_done + 1
        else:
            if turn.decode_done >= model.output_limit_per_turn:
                turn.completion_reason = "OutputLengthLimit"
            turn.generation_complete = True
            turn.phase = Phase.DELIVERY
            turn.wait_reason = "OutputDelivery" if turn.delivered < turn.decode_done else None
            maybe_finish(s)
            return
        done = edge.compute.submit(s, turn, model, phase, unit, runtime.time_s)
        for task in done:
            compute_done(task)

    def continue_committed(s, phase):
        if phase == Phase.DECODE:
            # Synthetic per-Token FIFO delivery events, not a network scheduler.
            key = s.session_id
            when = max(runtime.time_s, last_delivery.get(key, runtime.time_s)) + delays[key]
            last_delivery[key] = when
            queue.schedule(when, "kv_demo_delivery", session_id=key,
                           token_id=s.current_turn.output_tokens[-1].token_id)
        next_unit(s)

    def compute_done(task):
        s = runtime.sessions[task.session_id]
        result = runtime.commit_token(s.session_id)
        if result == CommitResult.COMMITTED:
            continue_committed(s, task.phase)
        elif result == CommitResult.CONTEXT_LIMIT:
            turn = s.current_turn
            if turn.prefill_done != turn.input_tokens:
                turn.status, turn.phase = "failed", Phase.END
                runtime.end_session(s.session_id, runtime.time_s, "ContextLimit")
            else:
                turn.generation_complete = True
                maybe_finish(s)

    last_delivery = {}
    for plan in plans:
        s = driver.arrival(plan.session_id)
        runtime.add_session(s)
        request = driver.reveal_turn(s.session_id, 1)
        runtime.submit_turn(s.session_id, request.input_tokens, 0)
        runtime.input_arrived(s.session_id)
        next_unit(s)
    event_count = 0
    while queue:
        event_count += 1
        if event_count > 10000:
            raise RuntimeError("KV demo event safety limit reached")
        event = queue.pop()
        runtime.time_s = event.time
        if event.kind == "gpu_completion":
            done = edge.compute.handle_event(event)
            if not done:
                done = edge.compute.advance(event.time)
            for task in done:
                compute_done(task)
        else:
            for task in edge.compute.advance(event.time):
                compute_done(task)
            if event.kind == "kv_retry":
                for token in runtime.handle_resource_event(event):
                    continue_committed(runtime.sessions[token.session_id], token.phase)
            elif event.kind == "kv_demo_delivery":
                s = runtime.sessions[event.payload["session_id"]]
                runtime.deliver_token(s.session_id, token_id=event.payload["token_id"])
                maybe_finish(s)
            else:
                raise RuntimeError("Unknown demo event")
        edge.kv.assert_consistent()
    tasks = list(edge.compute.tasks.values())
    units = [(t.session_id, t.turn_index, t.phase, t.unit_index) for t in tasks]
    summary = {"stage": "S1-C", "scope": "scripted formal-entity KV recovery validation",
               "peak_kv_bytes": edge.kv.peak_bytes, "final_kv_bytes": edge.kv.used_bytes,
               "total_gpu_work": sum(t.consumed_work for t in tasks), "gpu_units": len(tasks),
               "duplicate_compute": len(set(units)) != len(units),
               "recovered_units": sum(e["reason"] == "PendingCommitRecovered" for e in edge.kv.trace),
               "completed_turns": sum(s.current_turn.status == "completed" for s in runtime.sessions.values()),
               "blocked_sessions": [s.session_id for s in runtime.sessions.values() if s.status == "blocked"],
               "last_event_s": runtime.time_s}
    return {"summary": summary, "events": edge.kv.trace}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8")) if args.config else None
    print(json.dumps(run_demo(config), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
