"""S0 execution on Foundation entities and the existing GPU/FCFS engine.

The private workload driver owns hidden output lengths and future Turns.
Online policies receive observation() values only, never this simulator.
"""
from __future__ import annotations

from collections import deque
from types import MappingProxyType
from typing import Any

from ..core.runtime import RuntimeState
from ..core.entities import ModelSpec, EdgeState, TurnState, OutputToken, Phase, CommitResult, integer, number
from .events import EventQueue
from ..core.observation import observe
from ..core.workload import WorkloadDriver


class S0Simulator:
    def __init__(self, config: dict[str, Any]):
        self.model = ModelSpec.from_config(config["model"])
        e, n, s = config["edge"], config["network"], config["session"]
        if s["model_id"] != self.model.model_id:
            raise ValueError("Fixed session model must match deployed model")
        if s["access_edge_id"] != e["id"] or s["execution_edge_id"] != e["id"]:
            raise ValueError("S0 only supports same access and execution edge")
        for key in ("wireless_up_bits_per_second", "wireless_down_bits_per_second"):
            number(n[key], positive=True)
        integer(n["text_bytes_per_token"])
        self.net = MappingProxyType(dict(n))
        self.queue = EventQueue()
        self.edge = EdgeState(e["id"], e["gpu_work_per_second"], e["gpu_slots"],
                              e["kv_capacity_bytes"], frozenset(e["deployed_models"]), self.queue,
                              area_id=e.get("area_id"))
        self.runtime = RuntimeState({self.model.model_id: self.model}, {self.edge.edge_id: self.edge})
        self._driver = WorkloadDriver.from_s0_config(config)
        self._session_id = s["id"]
        arrival = self._driver.arrival(self._session_id)
        self.queue.schedule(arrival.arrival_time, "session_arrival", priority=30)
        self.peak_kv_bytes = 0
        self.finished_turns: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.downlink_pending: deque[OutputToken] = deque()
        self.downlink_busy = False

    @property
    def time(self):
        return self.runtime.time_s

    @property
    def session(self):
        return self.runtime.sessions[self._session_id]

    @property
    def active_turn(self):
        session = self.runtime.sessions.get(self._session_id)
        return session.current_turn if session else None

    @property
    def context_tokens(self):
        return self.session.context_tokens if self._session_id in self.runtime.sessions else 0

    @property
    def authoritative_kv_bytes(self):
        return self.edge.authoritative_kv_bytes

    def observation(self):
        return observe(self.runtime)

    def _log(self, kind: str, **detail):
        self.events.append({"seq": len(self.events), "time_s": round(self.time, 12),
                            "event": kind, "session_id": self._session_id, **detail})

    @property
    def _turn(self) -> TurnState:
        assert self.active_turn is not None
        return self.active_turn

    def _arrive(self):
        self.runtime.add_session(self._driver.arrival(self._session_id))
        self._log("session_arrival", model_id=self.session.model_id)
        self.queue.schedule(self.time, "submit_turn", priority=30, index=1)

    def _submit_turn(self, index):
        request = self._driver.reveal_turn(self._session_id, index)
        turn = self.runtime.submit_turn(self._session_id, request.input_tokens, self.time)
        self._log("turn_submit", turn=turn.index)
        size = request.input_tokens * self.session.text_bytes_per_token
        self._log("upload_start", turn=turn.index, bytes=size)
        self.queue.schedule(self.time + size * 8 / self.net["wireless_up_bits_per_second"], "upload_done")

    def _upload_done(self):
        self.runtime.input_arrived(self._session_id)
        self._log("upload_done", turn=self._turn.index)
        self._schedule_prefill_or_decode()

    def _start_gpu(self, phase, unit):
        completed = self.edge.compute.submit(self.session, self._turn, self.model, phase, unit, self.time)
        for task in completed:
            self._gpu_done(task)

    def _schedule_prefill_or_decode(self):
        t = self._turn
        if t.prefill_done < t.input_tokens:
            self._start_gpu(Phase.PREFILL, t.prefill_done + 1)
        else:
            self._log("prefill_complete", turn=t.index)
            self._schedule_decode_or_finish()

    def _schedule_decode_or_finish(self):
        t = self._turn
        if t.decode_done >= self.model.output_limit_per_turn:
            t.completion_reason = "OutputLengthLimit"
            self._generation_end()
        elif self._driver.has_output(self._session_id, t.index, t.decode_done):
            self._start_gpu(Phase.DECODE, t.decode_done + 1)
        else:
            self._generation_end()

    def _gpu_done(self, task):
        t = self._turn
        if t.compute_task is not task:
            raise RuntimeError("GPU completion is not owned by the active Turn")
        result = self.runtime.commit_token(self._session_id)
        if result == CommitResult.KV_BLOCKED:
            self._log("kv_blocked", turn=t.index, partial_work=t.partial_work,
                      context_tokens=self.context_tokens, authoritative_kv_bytes=self.authoritative_kv_bytes)
            return
        if result == CommitResult.CONTEXT_LIMIT:
            self._log("context_limit", turn=t.index, context_tokens=self.context_tokens)
            if t.prefill_done != t.input_tokens:
                t.status, t.phase, t.wait_reason = "failed", Phase.END, None
                self._end_session("ContextLimit")
            else:
                self._generation_end()
            return
        self._token_committed(task.phase)

    def _token_committed(self, phase):
        """Shared continuation for first commits and recovered pending units."""
        t = self._turn
        if phase == Phase.PREFILL:
            self._log("prefill_token_done", turn=t.index, number=t.prefill_done)
        else:
            self._log("decode_token_done", turn=t.index, number=t.decode_done)
        self.peak_kv_bytes = max(self.peak_kv_bytes, self.authoritative_kv_bytes)
        self._log("kv_commit", origin=phase.value, context_tokens=self.context_tokens,
                  authoritative_kv_bytes=self.authoritative_kv_bytes)
        if phase == Phase.PREFILL:
            self._schedule_prefill_or_decode()
        else:
            self.downlink_pending.append(t.output_tokens[-1])
            self._try_start_downlink()
            self._schedule_decode_or_finish()

    def _generation_end(self):
        t = self._turn
        t.generation_complete = True
        t.phase = Phase.DELIVERY
        t.wait_reason = "OutputDelivery" if t.delivered < t.decode_done else None
        self._log("decode_complete", turn=t.index)
        if t.delivered == t.decode_done:
            self._finish_turn()

    def _try_start_downlink(self):
        if self.downlink_busy or not self.downlink_pending:
            return
        token = self.downlink_pending.popleft()
        num = token.output_index
        self.downlink_busy = True
        self._log("downlink_start", turn=self._turn.index, number=num, token_id=token.token_id)
        delay = 8 * token.text_bytes / self.net["wireless_down_bits_per_second"]
        self.queue.schedule(self.time + delay, "downlink_done", number=num, token_id=token.token_id)

    def _downlink_done(self, num, token_id):
        self.downlink_busy = False
        self.runtime.deliver_token(self._session_id, token_id=token_id)
        t = self._turn
        self._log("downlink_done", turn=t.index, number=num, token_id=token_id)
        if t.generation_complete and t.delivered == t.decode_done and t.status != "blocked":
            self._finish_turn()
        else:
            self._try_start_downlink()

    def _finish_turn(self):
        t = self._turn
        self.runtime.finish_turn(self._session_id, self.time)
        latency = round(self.time - t.submitted_at, 12)
        self.finished_turns.append({"session_id": self._session_id, "turn": t.index,
                                    "submitted_at_s": t.submitted_at, "received_at_s": self.time,
                                    "e2e_s": latency, "input_tokens": t.input_tokens,
                                    "output_tokens": t.decode_done, "status": t.status})
        if t.status == "failed":
            self._log("turn_failed", turn=t.index, reason=t.completion_reason)
            self._end_session("ContextLimit")
        else:
            self._log("turn_complete", turn=t.index, e2e_s=latency)
            if self._driver.has_next_turn(self._session_id, t.index):
                self.queue.schedule(self.time, "submit_turn", priority=30, index=t.index + 1)
            else:
                self._end_session("completed")

    def _end_session(self, reason):
        self._log("session_end", final_context_tokens=self.context_tokens,
                  final_authoritative_kv_bytes=self.authoritative_kv_bytes, reason=reason)
        self.runtime.end_session(self._session_id, self.time, reason)
        self._log("kv_release", authoritative_kv_bytes=self.authoritative_kv_bytes)

    def step(self):
        """Execution/test checkpoint, not an interface handed to online policies."""
        if not self.queue:
            return None
        event = self.queue.pop()
        if event.time < self.time:
            raise RuntimeError("Time moved backwards")
        self.runtime.time_s = event.time
        if event.kind == "gpu_completion":
            completed = self.edge.compute.handle_event(event)
            if not completed:
                completed = self.edge.compute.advance(event.time)
            for task in completed:
                self._gpu_done(task)
            return event.time, event.kind
        # Delivery/upload events also settle current GPU service before a
        # same-clock observation; they must not leave stale remaining work.
        for task in self.edge.compute.advance(event.time):
            self._gpu_done(task)
        if event.kind == "session_arrival":
            self._arrive()
        elif event.kind == "submit_turn":
            self._submit_turn(event.payload["index"])
        elif event.kind == "upload_done":
            self._upload_done()
        elif event.kind == "downlink_done":
            self._downlink_done(event.payload["number"], event.payload["token_id"])
        elif event.kind == "kv_retry":
            for token in self.runtime.handle_resource_event(event):
                if token.session_id != self._session_id:
                    raise RuntimeError("S0 continuation supports only its single Session")
                self._token_committed(token.phase)
        else:
            raise RuntimeError(f"Unknown event {event.kind}")
        return event.time, event.kind

    def run(self, max_events=100000):
        count = 0
        while self.queue:
            if count >= max_events:
                raise RuntimeError("Event safety limit reached")
            self.step()
            count += 1
        metadata = self._driver.evaluation_metadata()
        planned = metadata["planned_turns"]
        finished = [t for t in self.finished_turns if t["status"] == "completed"]
        reason = self.session.termination_reason or self._turn.wait_reason
        summary = {"stage": "S0", **metadata, "completed_turns": len(finished),
                   "completion_rate": len(finished) / planned,
                   "mean_full_turn_e2e_s": (round(sum(t["e2e_s"] for t in finished) / planned, 12)
                                             if len(finished) == planned else None),
                   "observation_end_s": round(self.time, 12), "final_context_tokens": self.context_tokens,
                   "peak_authoritative_kv_bytes": self.peak_kv_bytes,
                   "released_authoritative_kv_bytes": self.authoritative_kv_bytes,
                   "migration_kv_bytes": 0, "shadow_byte_seconds": 0,
                   "status": self.session.status, "termination_reason": reason,
                   "unfinished_turns": planned - len(finished)}
        return summary, self.finished_turns, self.events
