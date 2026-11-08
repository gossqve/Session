"""Unified causal multi-Session, multi-Turn serving over existing resources."""
from collections import deque
from dataclasses import asdict
import math

from ..core.entities import ModelSpec, EdgeState, Phase, CommitResult, number
from ..core.runtime import RuntimeState
from ..core.workload import WorkloadDriver
from ..core.observation import observe
from .events import EventQueue
from ..network.topology import NetworkTopology
from ..network.runtime import NetworkRuntime
from ..network.wireless import WirelessRuntime


class ServingSimulator:
    def __init__(self, config, *, network_allocator=None):
        self.queue = EventQueue()
        models = {}
        for spec in config["models"]:
            model = ModelSpec.from_config(spec)
            if model.model_id in models:
                raise ValueError("Duplicate model ID")
            models[model.model_id] = model
        edges = {}
        for spec in config["edges"]:
            edge = EdgeState(spec["id"], spec["gpu_work_per_second"], spec["gpu_slots"],
                             spec["kv_capacity_bytes"], frozenset(spec["deployed_models"]), self.queue,
                             area_id=spec.get("area_id"))
            if edge.edge_id in edges:
                raise ValueError("Duplicate Edge ID")
            edges[edge.edge_id] = edge
        self.runtime = RuntimeState(models, edges)
        self.topology = (NetworkTopology.from_config(config["topology"], edges=edges.values())
                         if "topology" in config else None)
        self.network = NetworkRuntime(self.queue, self.topology, allocator=network_allocator) if self.topology else None
        self.wireless = WirelessRuntime(self.queue)
        self._response_flows = {}
        self._driver = WorkloadDriver.from_serving_config(config)
        for time, sid in self._driver.arrival_events():
            self.queue.schedule(time, "serving_arrival", priority=30, session_id=sid)
        self._network = {}
        self._downlink = {}
        self._downlink_busy = set()
        self.events = []
        self.ignored_predictions = 0
        self._raw_events = 0
        self._max_events = 100000
        self._peak_kv = 0

    @property
    def time_s(self):
        return self.runtime.time_s

    def observation(self):
        return observe(self.runtime)

    def _log(self, event, sid=None, **detail):
        session = self.runtime.sessions.get(sid)
        turn = session.current_turn if session else None
        self.events.append({"seq": len(self.events), "time_s": self.time_s, "event": event,
                            "session_id": sid, "turn_index": turn.index if turn else None,
                            "model_id": session.model_id if session else None,
                            "execution_edge_id": session.execution_edge_id if session else None, **detail})

    def _edge(self, session):
        return self.runtime.edges[session.execution_edge_id]

    def _arrive(self, sid):
        session = self._driver.arrival(sid)
        if self.topology:
            pair = session.access_edge_id, session.execution_edge_id
            if pair not in self.topology.validate_serving_pairs():
                raise ValueError(f"Serving pair is not permitted: {pair}")
            self.topology.validate_access_execution(*pair)
        elif session.access_edge_id != session.execution_edge_id:
            raise ValueError("Remote Serving requires an explicit network topology")
        self.runtime.add_session(session)
        self._network[sid] = self._driver.network_at_arrival(sid)
        self._downlink[sid] = deque()
        self._log("session_arrival", sid)
        self._submit_turn(sid)

    def _submit_turn(self, sid):
        session = self.runtime.sessions[sid]
        index = session.current_turn.index + 1 if session.current_turn else 1
        request = self._driver.reveal_turn(sid, index)
        turn = self.runtime.submit_turn(sid, request.input_tokens, self.time_s)
        size = turn.input_tokens * session.text_bytes_per_token
        self._log("turn_submit", sid, input_tokens=turn.input_tokens)
        self._log("upload_start", sid, bytes=size)
        self._wireless_transfer(f"up:{sid}:{turn.index}", "upload", sid, size,
                                self._network[sid]["up"])

    def _wireless_transfer(self, flow_id, kind, sid, size, rate, token_id=None):
        notices = list(self.wireless.create(flow_id, kind, sid,
                       self.runtime.sessions[sid].current_turn.index, self.time_s, rate_bps=rate))
        notices.extend(self.wireless.supply(flow_id, size, self.time_s, token_id=token_id))
        notices.extend(self.wireless.close(flow_id, self.time_s))
        notices.extend(self.wireless.start(flow_id, self.time_s))
        self._transport_notices(self.wireless, notices)

    def _input_at_execution(self, sid):
        self.runtime.input_arrived(sid)
        self._log("upload_done", sid)
        self._continue(sid)

    def _enqueue_wireless(self, token):
        self._log("token_access_arrival", token.session_id, token_id=token.token_id)
        self._downlink[token.session_id].append(token)
        self._start_downlink(token.session_id)

    def _transport_notices(self, resource, notices):
        for notice in notices:
            flow = resource.flows[notice.flow_id]
            sid = flow.session_id
            if resource is self.network:
                if notice.kind == "token_arrived":
                    token = self.runtime.sessions[sid].current_turn.output_tokens[notice.token_id[2] - 1]
                    self._enqueue_wireless(token)
                elif notice.kind == "completed" and flow.flow_type == "prompt":
                    self._log("prompt_wired_arrival", sid, flow_id=flow.flow_id)
                    self._input_at_execution(sid)
            elif notice.kind == "completed":
                if flow.flow_type == "upload":
                    self._log("wireless_upload_done", sid)
                    session = self.runtime.sessions[sid]
                    if session.access_edge_id == session.execution_edge_id:
                        self._input_at_execution(sid)
                    else:
                        path = self.topology.get_path(session.access_edge_id, session.execution_edge_id)
                        key = f"prompt:{sid}:{flow.turn_index}"
                        found = list(self.network.create(key, "prompt", sid, flow.turn_index, self.time_s, path=path))
                        found.extend(self.network.supply(key, session.current_turn.input_tokens * session.text_bytes_per_token, self.time_s))
                        found.extend(self.network.close(key, self.time_s))
                        found.extend(self.network.start(key, self.time_s))
                        self._transport_notices(self.network, found)
                else:
                    turn = self.runtime.sessions[sid].current_turn
                    token = turn.output_tokens[turn.delivered]
                    self._downlink_busy.remove(sid)
                    self.runtime.deliver_token(sid, token_id=token.token_id)
                    self._log("downlink_done", sid, unit_index=token.output_index, token_id=token.token_id)
                    self._start_downlink(sid)
                    self._maybe_finish(sid)

    def update_wireless_rate(self, sid, direction, rate_bps):
        if direction not in ("up", "down"):
            raise ValueError("Wireless direction must be up/down")
        number(rate_bps)
        self._network[sid][direction] = rate_bps
        kind = "upload" if direction == "up" else "download"
        for key, flow in tuple(self.wireless.flows.items()):
            if flow.session_id == sid and flow.flow_type == kind and flow.status not in ("completed", "cancelled"):
                self._transport_notices(self.wireless, self.wireless.set_rate(key, rate_bps, self.time_s))

    def _continue(self, sid):
        session = self.runtime.sessions[sid]
        turn = session.current_turn
        model = self.runtime.models[session.model_id]
        if turn.prefill_done < turn.input_tokens:
            phase, unit = Phase.PREFILL, turn.prefill_done + 1
        elif turn.decode_done >= model.output_limit_per_turn:
            turn.completion_reason = "OutputLengthLimit"
            self._generation_end(sid)
            return
        elif self._driver.has_output(sid, turn.index, turn.decode_done):
            phase, unit = Phase.DECODE, turn.decode_done + 1
        else:
            self._generation_end(sid)
            return
        done = self._edge(session).compute.submit(session, turn, model, phase, unit, self.time_s, continuous=True)
        self._log("gpu_unit_submitted", sid, phase=phase.value, unit_index=unit,
                  resource_id=turn.compute_task.resource_id)
        for task in done:
            self._gpu_done(task)

    def _release_slot(self, sid):
        session = self.runtime.sessions[sid]
        for task in self._edge(session).compute.release_turn(sid, session.current_turn.index, self.time_s):
            self._gpu_done(task)

    def _gpu_done(self, task):
        sid = task.session_id
        turn = self.runtime.sessions[sid].current_turn
        if turn.compute_task is not task:
            raise RuntimeError("Completion is not owned by current Turn")
        self._log("gpu_compute_completed", sid, phase=task.phase.value, unit_index=task.unit_index)
        result = self.runtime.commit_token(sid)
        if result == CommitResult.COMMITTED:
            self._committed(sid, task.phase, task.unit_index)
        elif result == CommitResult.KV_BLOCKED:
            self._release_slot(sid)
            self._log("kv_blocked", sid, phase=task.phase.value, unit_index=task.unit_index)
        else:
            self._release_slot(sid)
            self._log("context_limit", sid)
            if turn.prefill_done != turn.input_tokens:
                turn.status, turn.phase, turn.wait_reason = "failed", Phase.END, None
                self._capture_turn_end(sid)
                self.runtime.end_session(sid, self.time_s, "ContextLimit")
                self._log("session_end", sid, reason="ContextLimit")
            else:
                self._generation_end(sid)

    def _committed(self, sid, phase, unit, *, recovered=False):
        self._peak_kv = max(self._peak_kv, sum(e.kv.used_bytes for e in self.runtime.edges.values()))
        self._log("pending_committed" if recovered else "token_committed", sid,
                  phase=phase.value, unit_index=unit,
                  context_tokens=self.runtime.sessions[sid].context_tokens,
                  authoritative_kv_bytes=self.runtime.sessions[sid].authoritative_kv_bytes)
        if phase == Phase.DECODE:
            token = self.runtime.sessions[sid].current_turn.output_tokens[unit - 1]
            if token.execution_edge_id == token.access_edge_id:
                self._enqueue_wireless(token)
            else:
                path = self.topology.get_path(token.execution_edge_id, token.access_edge_id)
                key = (sid, token.turn_index)
                if key not in self._response_flows:
                    flow_id = f"response:{sid}:{token.turn_index}"
                    self._response_flows[key] = flow_id
                    self._transport_notices(self.network, self.network.create(
                        flow_id, "response", sid, token.turn_index, self.time_s, path=path))
                    self._transport_notices(self.network, self.network.start(flow_id, self.time_s))
                flow_id = self._response_flows[key]
                if self.network.flows[flow_id].path != path:
                    raise NotImplementedError("Source/path changes need future S3/S4 stages")
                self._transport_notices(self.network, self.network.supply(
                    flow_id, token.text_bytes, self.time_s, token_id=token.token_id))
        self._continue(sid)

    def _generation_end(self, sid):
        turn = self.runtime.sessions[sid].current_turn
        self._release_slot(sid)
        turn.generation_complete = True
        turn.generation_ended_at = self.time_s
        turn.phase = Phase.DELIVERY
        turn.wait_reason = "OutputDelivery" if turn.delivered < turn.decode_done else None
        self._log("generation_end", sid)
        key = (sid, turn.index)
        if key in self._response_flows:
            self._transport_notices(self.network, self.network.close(self._response_flows[key], self.time_s))
        self._maybe_finish(sid)

    def _start_downlink(self, sid):
        if sid in self._downlink_busy or not self._downlink[sid]:
            return
        token = self._downlink[sid].popleft()
        self._downlink_busy.add(sid)
        turn = self.runtime.sessions[sid].current_turn
        self._log("downlink_start", sid, unit_index=token.output_index,
                  token_id=token.token_id, generation_access_edge_id=token.access_edge_id,
                  generation_execution_edge_id=token.execution_edge_id, bytes=token.text_bytes)
        self._wireless_transfer(f"down:{sid}:{turn.index}:{token.output_index}", "download", sid,
                                token.text_bytes, self._network[sid]["down"], token.token_id)

    def _capture_turn_end(self, sid):
        session = self.runtime.sessions[sid]
        session.current_turn.context_at_end = session.context_tokens
        session.current_turn.kv_at_end = session.authoritative_kv_bytes

    def _maybe_finish(self, sid):
        session = self.runtime.sessions[sid]
        turn = session.current_turn
        if turn.status == "blocked" or not turn.generation_complete or turn.delivered != turn.decode_done:
            return
        self.runtime.finish_turn(sid, self.time_s)
        self._capture_turn_end(sid)
        self._log("turn_complete" if turn.status == "completed" else "turn_failed", sid)
        if turn.status == "failed":
            self.runtime.end_session(sid, self.time_s, "ContextLimit")
            self._log("session_end", sid, reason="ContextLimit")
        elif self._driver.has_next_turn(sid, turn.index):
            self.queue.schedule(self.time_s, "serving_submit", priority=30, session_id=sid)
        else:
            self.runtime.end_session(sid, self.time_s)
            self._log("session_end", sid, reason="completed")

    def _resources_snapshot(self):
        for _, edge in sorted(self.runtime.edges.items()):
            rates = {f"{edge.compute.task_for_resource(k).session_id}:{edge.compute.task_for_resource(k).turn_index}": v
                     for k, v in edge.compute.scheduler.rates.items()}
            running = list(rates)
            if len(running) != len(edge.running_tasks) or len(running) > edge.gpu_slots:
                raise RuntimeError("Turn GPU slot invariant violated")
            if any(rate <= 0 for rate in rates.values()):
                raise RuntimeError("Unresolved zero-duration unit boundary at event checkpoint")
            if sum(rates.values()) > edge.gpu_capacity * (1 + 1e-12):
                raise RuntimeError("GPU service budget invariant violated")
            edge.kv.assert_consistent()
            self._log("resource_state", edge_id=edge.edge_id, running_turns=running,
                      rates=rates, ready_turns=[f"{t.session_id}:{t.turn_index}" for t in edge.ready_queue],
                      kv_used_bytes=edge.kv.used_bytes, kv_capacity_bytes=edge.kv_capacity_bytes)

    def step(self):
        while self.queue:
            self._raw_events += 1
            if self._raw_events > self._max_events:
                raise RuntimeError("Serving event safety limit reached")
            event = self.queue.pop()
            if event.kind == "gpu_completion":
                owner = self.runtime.edges[event.payload["edge_id"]]
                if not owner.compute.scheduler.is_current_event(event):
                    self.ignored_predictions += 1
                    continue  # obsolete predictions do not advance observation time
            transport = (self.network if event.kind == "network_completion" else
                         self.wireless if event.kind == "wireless_completion" else None)
            if transport is not None and not transport.is_current_event(event):
                continue
            break
        else:
            return None
        if event.time < self.time_s:
            raise RuntimeError("Time moved backwards")
        self.runtime.time_s = event.time
        arrivals = []
        for transport in (self.network, self.wireless):
            if transport is not None:
                arrivals.append((transport, transport.handle_event(event) if event.kind == transport.event_kind
                                 else transport.advance(event.time)))
        completed = []
        # Settle all resources first; simultaneous completions use Edge ID then
        # stable admission order. Resolve every zero-duration boundary now.
        for _, edge in sorted(self.runtime.edges.items()):
            if event.kind == "gpu_completion" and event.payload["edge_id"] == edge.edge_id:
                completed.extend(edge.compute.handle_event(event))
            else:
                completed.extend(edge.compute.advance(event.time))
        for transport, notices in arrivals:
            self._transport_notices(transport, notices)
        for task in completed:
            self._gpu_done(task)
        sid = event.payload.get("session_id")
        if event.kind == "serving_arrival":
            self._arrive(sid)
        elif event.kind == "serving_submit":
            self._submit_turn(sid)
        elif event.kind == "kv_retry":
            for token in self.runtime.handle_resource_event(event):
                self._committed(token.session_id, token.phase, token.unit_index, recovered=True)
        elif event.kind not in ("gpu_completion", "serving_checkpoint", "network_completion", "wireless_completion"):
            raise RuntimeError(f"Unknown serving event: {event.kind}")
        self._resources_snapshot()
        return event.time, event.kind

    def advance_to(self, time_s):
        number(time_s)
        time_s = round(time_s, 12)
        if time_s < self.time_s:
            raise ValueError("Checkpoint cannot move backwards")
        self.queue.schedule(time_s, "serving_checkpoint", priority=90)
        while True:
            result = self.step()
            if result is None or result == (time_s, "serving_checkpoint"):
                break

    def run(self, max_events=100000):
        self._max_events = max_events
        while self.queue:
            self.step()
        return self.results()

    def results(self):
        """Offline evaluator only: planned denominator is read here, never in scheduling."""
        rows, sessions, outputs = [], [], []
        # Offline join from existing unique delivery events; no mutable ledger.
        received = {tuple(e["token_id"]): e["time_s"] for e in self.events if e["event"] == "downlink_done"}
        wired = {tuple(e["token_id"]): e["time_s"] for e in self.events if e["event"] == "token_access_arrival"}
        wireless_started = {tuple(e["token_id"]): e["time_s"] for e in self.events if e["event"] == "downlink_start"}
        upload_done = {(e["session_id"], e["turn_index"]): e["time_s"] for e in self.events if e["event"] == "wireless_upload_done"}
        input_done = {(e["session_id"], e["turn_index"]): e["time_s"] for e in self.events if e["event"] == "upload_done"}
        wired_boundaries = {b.token_id: (f.flow_id, b.cumulative_bytes)
                            for f in (self.network.flows.values() if self.network else ())
                            for b in f.token_boundaries}
        for sid, session in sorted(self.runtime.sessions.items()):
            for turn in session.turns:
                outputs.extend({**asdict(token), "token_id": token.token_id,
                                "delivered": token.output_index <= turn.delivered,
                                "received_at": received.get(token.token_id), "delivered_at": received.get(token.token_id),
                                "wired_arrived_at": wired.get(token.token_id),
                                "wired_flow_id": wired_boundaries.get(token.token_id, (None, None))[0],
                                "wired_cumulative_bytes": wired_boundaries.get(token.token_id, (None, None))[1],
                                "wireless_started_at": wireless_started.get(token.token_id)} for token in turn.output_tokens)
                rows.append({"session_id": sid, "turn_index": turn.index, "model_id": session.model_id,
                             "submitted_access_edge_id": turn.submitted_access_edge_id,
                             "execution_edge_id": session.execution_edge_id,
                             "submitted_at": turn.submitted_at, "gpu_ready_time": turn.gpu_ready_time,
                             "wireless_upload_completed_at": upload_done.get((sid, turn.index)),
                             "prompt_arrived_at": input_done.get((sid, turn.index)),
                             "gpu_start_time": turn.gpu_start_time,
                             "gpu_queue_wait_s": round(turn.gpu_queue_wait_s, 12),
                             "gpu_service_work": turn.gpu_service_work, "input_tokens": turn.input_tokens,
                             "prefill_done": turn.prefill_done, "decode_done": turn.decode_done, "delivered": turn.delivered,
                             "context_tokens": turn.context_at_end if turn.context_at_end is not None else session.context_tokens,
                             "authoritative_kv_bytes": turn.kv_at_end if turn.kv_at_end is not None else session.authoritative_kv_bytes,
                             "block_count": turn.block_count,
                             "blocked_time_s": round(turn.blocked_time_s + (self.time_s - turn.blocked_since
                                                                           if turn.blocked_since is not None else 0), 12),
                             "generation_ended_at": turn.generation_ended_at, "received_at": turn.received_at,
                             "e2e_s": round(turn.received_at - turn.submitted_at, 12) if turn.received_at is not None else None,
                             "status": turn.status, "reason": turn.completion_reason or turn.wait_reason})
            sessions.append({"session_id": sid, "model_id": session.model_id, "arrival_time": session.arrival_time,
                             "access_edge_id": session.access_edge_id, "execution_edge_id": session.execution_edge_id,
                             "status": session.status, "end_time": session.end_time,
                             "termination_reason": session.termination_reason, "context_tokens": session.context_tokens,
                             "authoritative_kv_bytes": session.authoritative_kv_bytes})
        metadata = self._driver.evaluation_metadata()
        done = [r["e2e_s"] for r in rows if r["status"] == "completed"]
        resources = [{"edge_id": edge.edge_id, "peak_kv_bytes": edge.kv.peak_bytes,
                      "final_kv_bytes": edge.kv.used_bytes, "running_turns": len(edge.running_tasks),
                      "ready_turns": len(edge.ready_queue)} for _, edge in sorted(self.runtime.edges.items())]
        summary = {"stage": "S1-D", **metadata, "completed_turns": len(done),
                   "submitted_turns": len(rows), "unfinished_turns": metadata["planned_turns"] - len(done),
                   "completion_rate": len(done) / metadata["planned_turns"],
                   "mean_full_turn_e2e_s": round(sum(done) / len(done), 12) if len(done) == metadata["planned_turns"] else None,
                   "completed_turn_p95_e2e_s": sorted(done)[math.ceil(0.95 * len(done)) - 1] if done else None,
                   "p95_scope": "normally completed Turns; nearest-rank",
                   "gpu_work": sum(r["gpu_service_work"] for r in rows),
                   "gpu_queue_wait_s": round(sum(r["gpu_queue_wait_s"] for r in rows), 12),
                   "kv_blocked_time_s": round(sum(r["blocked_time_s"] for r in rows), 12),
                   "blocked_sessions": sum(s["status"] == "blocked" for s in sessions),
                   "peak_kv_bytes": self._peak_kv, "final_kv_bytes": sum(r["final_kv_bytes"] for r in resources),
                   "observation_end_s": self.time_s, "ignored_gpu_predictions": self.ignored_predictions}
        def snapshots(resource):
            if resource is None:
                return []
            from fractions import Fraction
            def values(value):
                if isinstance(value, Fraction): return float(value)
                if isinstance(value, dict): return {k: values(v) for k,v in value.items()}
                if isinstance(value, (list,tuple)): return [values(v) for v in value]
                return value
            return [values({**asdict(flow), "path_id": flow.path_id, "link_ids": flow.link_ids,
                            "pending_bytes": flow.pending_bytes}) for flow in resource.flows.values()]
        return {"network_flows": snapshots(self.network), "wireless_transfers": snapshots(self.wireless),
                "network_events": list(self.network.trace) if self.network else [],
                "wireless_events": list(self.wireless.trace), "summary": summary, "turns": rows, "sessions": sessions, "resources": resources,
                "output_tokens": outputs,
                "events": list(self.events),
                "gpu_events": {key: edge.compute.scheduler.gpu_trace for key, edge in sorted(self.runtime.edges.items())},
                "kv_events": {key: list(edge.kv.trace) for key, edge in sorted(self.runtime.edges.items())}}
