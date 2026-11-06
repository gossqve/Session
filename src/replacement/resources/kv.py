"""Authoritative Session KV commits, pending units and release-triggered retries.

Occupancy is derived from resident Sessions. No future workload, reservations,
polling, GPU cancellation or repeated compute is used for pending commits.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import TYPE_CHECKING

from ..core.entities import CommitResult, Phase, OutputToken, integer

if TYPE_CHECKING:
    from ..core.entities import EdgeState
    from ..core.runtime import RuntimeState
    from ..simulation.events import Event


@dataclass(frozen=True, slots=True)
class PendingCommit:
    session_id: str
    turn_index: int
    task_id: str
    phase: Phase
    unit_index: int
    blocked_at: float
    sequence: int


@dataclass(frozen=True, slots=True)
class TokenCommitted:
    session_id: str
    turn_index: int
    task_id: str
    phase: Phase
    unit_index: int
    execution_edge_id: str
    time_s: float


class KVResource:
    event_kind = "kv_retry"

    def __init__(self, edge: EdgeState):
        self.edge = edge
        self._runtime: RuntimeState | None = None
        self._pending: dict[str, PendingCommit] = {}
        self._sequence = 0
        self._retry_generation = 0
        self._retry_scheduled = False
        self._committed: set[str] = set()
        self._computed: set[str] = set()
        self.peak_bytes = 0
        self.trace: list[dict] = []

    def bind_runtime(self, runtime: RuntimeState):
        if self._runtime is not None and self._runtime is not runtime:
            raise ValueError("KV resource belongs to one runtime")
        self._runtime = runtime

    @property
    def used_bytes(self) -> int:
        return self.edge.authoritative_kv_bytes

    @property
    def free_bytes(self) -> int:
        return self.edge.kv_capacity_bytes - self.used_bytes

    @property
    def pending(self) -> tuple[PendingCommit, ...]:
        return tuple(sorted(self._pending.values(), key=lambda p: (p.sequence, p.session_id)))

    def can_fit(self, additional_bytes: int) -> bool:
        """Net-capacity gate; future commitment logic can extend this one gate."""
        integer(additional_bytes, minimum=0)
        return self.used_bytes + additional_bytes <= self.edge.kv_capacity_bytes

    def assert_consistent(self):
        if self._runtime is None:
            raise RuntimeError("KV resource is not bound")
        for session in self.edge._residents.values():
            expected = self._runtime.models[session.model_id].kv_bytes_per_token * session.context_tokens
            if session.authoritative_kv_bytes != expected or session.execution_edge_id != self.edge.edge_id:
                raise RuntimeError("Session Context/KV/authority invariant violated")
        if not 0 <= self.used_bytes <= self.edge.kv_capacity_bytes:
            raise RuntimeError("Edge net KV capacity invariant violated")

    def record_event(self, kind, session_id, *, before=None, reason=None, phase=None, unit=None):
        session = self._runtime.sessions[session_id]
        turn = session.current_turn
        task = turn.compute_task if turn else None
        self.trace.append({
            "seq": len(self.trace), "time_s": self._runtime.time_s, "event": kind,
            "session_id": session_id, "turn_index": turn.index if turn else None,
            "model_id": session.model_id, "execution_edge_id": self.edge.edge_id,
            "phase": (phase or (task.phase if task else turn.phase)).value if turn else None,
            "unit_index": unit if unit is not None else (task.unit_index if task else None),
            "session_kv_before": session.authoritative_kv_bytes if before is None else before,
            "session_kv_after": session.authoritative_kv_bytes,
            "edge_used_bytes": self.used_bytes, "capacity_bytes": self.edge.kv_capacity_bytes,
            "reason": reason, "gpu_running_count": len(self.edge.running_tasks),
            "gpu_running_ids": list(self.edge.compute.scheduler.rates), "repeat_compute": False})

    def _clear_pending(self, session_id):
        pending = self._pending.pop(session_id, None)
        if pending is not None:
            turn = self._runtime.sessions[session_id].current_turn
            turn.blocked_time_s += float(Fraction(str(self._runtime.time_s)) - Fraction(str(pending.blocked_at)))
            turn.pending_commit = None

    def try_commit(self, session_id: str) -> CommitResult:
        session = self._runtime.sessions[session_id]
        turn = session.current_turn
        task = turn.compute_task if turn else None
        if (self.edge._residents.get(session_id) is not session or session.status not in ("active", "blocked")
                or task is None or task.status != "completed" or task.task_id in self._committed
                or task.session_id != session_id or task.turn_index != turn.index
                or task.execution_edge_id != self.edge.edge_id):
            raise RuntimeError("Commit requires the current completed, uncommitted resident GPU unit")
        if task.completion_time > self._runtime.time_s:
            raise ValueError("Cannot commit before actual GPU completion")
        model = self._runtime.models[session.model_id]
        if task.phase == Phase.PREFILL:
            expected = turn.prefill_done + 1
            if expected > turn.input_tokens:
                raise RuntimeError("Prefill exceeds revealed input")
        elif task.phase == Phase.DECODE:
            expected = turn.decode_done + 1
            if turn.prefill_done != turn.input_tokens or expected > model.output_limit_per_turn:
                raise RuntimeError("Illegal Decode commit")
        else:
            raise RuntimeError("Unknown Token phase")
        if task.unit_index != expected:
            raise RuntimeError("Duplicate or out-of-order Token commit")
        if task.task_id not in self._computed:
            self._computed.add(task.task_id)
            self.record_event("gpu_compute_completed", session_id)
        if session.context_tokens + 1 > model.context_window_tokens:
            turn.completion_reason = CommitResult.CONTEXT_LIMIT.value
            self._clear_pending(session_id)
            self.record_event("context_limit", session_id, reason="ContextLimit")
            return CommitResult.CONTEXT_LIMIT
        if not self.can_fit(model.kv_bytes_per_token):
            if session_id not in self._pending:
                pending = PendingCommit(session_id, turn.index, task.task_id, task.phase, task.unit_index,
                                        self._runtime.time_s, self._sequence)
                self._sequence += 1
                self._pending[session_id] = pending
                turn.pending_commit = pending
                turn.block_count += 1
                self.record_event("kv_blocked", session_id, reason="InsufficientNetKV")
            turn.status = session.status = "blocked"
            turn.wait_reason = "KVBlocked"
            return CommitResult.KV_BLOCKED
        before = session.authoritative_kv_bytes
        recovering = session_id in self._pending
        output = None
        if task.phase == Phase.DECODE:
            if len(turn.output_tokens) != turn.decode_done:
                raise RuntimeError("Output records disagree with committed Decode prefix")
            output = OutputToken(session_id, turn.index, task.unit_index, self._runtime.time_s,
                                 session.execution_edge_id, session.access_edge_id,
                                 session.text_bytes_per_token)
        # All validation precedes this atomic event-state transition.
        session.context_tokens += 1
        session.authoritative_kv_bytes += model.kv_bytes_per_token
        if task.phase == Phase.PREFILL:
            turn.prefill_done += 1
        else:
            turn.decode_done += 1
            turn._output_tokens.append(output)
        turn.committed_work += task.consumed_work
        self._committed.add(task.task_id)
        self._clear_pending(session_id)
        turn.compute_task = None
        turn.status = session.status = "active"
        turn.wait_reason = None
        self.peak_bytes = max(self.peak_bytes, self.used_bytes)
        self.record_event("token_committed", session_id, before=before, phase=task.phase, unit=task.unit_index,
                          reason="PendingCommitRecovered" if recovering else "ComputedUnit")
        self.assert_consistent()
        return CommitResult.COMMITTED

    def release_session(self, session_id: str) -> int:
        session = self.edge._residents.get(session_id)
        if session is None:
            return 0
        if session.status not in ("ended", "failed"):
            raise RuntimeError("Release requires a terminal Session lifecycle transition")
        if any(t.session_id == session_id for t in (*self.edge.running_tasks, *self.edge.ready_queue)):
            raise RuntimeError("Cannot release KV while GPU work is live")
        amount = session.authoritative_kv_bytes
        self._clear_pending(session_id)
        session.authoritative_kv_bytes = 0
        del self.edge._residents[session_id]
        self.record_event("kv_release", session_id, before=amount, reason=session.termination_reason)
        if amount and self._pending and not self._retry_scheduled:
            self._retry_generation += 1
            self._retry_scheduled = True
            self.edge.event_queue.schedule(self._runtime.time_s, self.event_kind, priority=25,
                                           edge_id=self.edge.edge_id, generation=self._retry_generation)
        self.assert_consistent()
        return amount

    def handle_event(self, event: Event) -> tuple[TokenCommitted, ...]:
        if (event.kind != self.event_kind or event.payload.get("edge_id") != self.edge.edge_id
                or event.payload.get("generation") != self._retry_generation or not self._retry_scheduled):
            return ()
        if event.time != self._runtime.time_s:
            raise ValueError("KV retry must use the current runtime clock")
        self._retry_scheduled = False
        committed = []
        for pending in self.pending:
            if self.try_commit(pending.session_id) == CommitResult.COMMITTED:
                committed.append(TokenCommitted(pending.session_id, pending.turn_index, pending.task_id,
                                                pending.phase, pending.unit_index, self.edge.edge_id,
                                                self._runtime.time_s))
        return tuple(committed)
