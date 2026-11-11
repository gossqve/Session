"""Explicit policy whitelist: frozen value DTOs without source object references."""
from dataclasses import dataclass, replace
from fractions import Fraction

from .runtime import RuntimeState


@dataclass(frozen=True, slots=True)
class TaskObservation:
    task_id: str
    session_id: str
    turn_index: int
    phase: str
    unit_index: int
    execution_edge_id: str
    remaining_work: float
    consumed_work: float
    status: str
    ready_time: float
    start_time: float | None
    queue_wait_s: float


@dataclass(frozen=True, slots=True)
class TurnObservation:
    index: int
    input_tokens: int
    prefill_done: int
    decode_done: int
    delivered: int
    submitted_at: float
    gpu_ready_time: float | None
    gpu_start_time: float | None
    received_at: float | None
    phase: str
    status: str
    wait_reason: str | None
    completion_reason: str | None
    generation_complete: bool
    remaining_gpu_work: float
    partial_work: float
    blocked_since: float | None
    blocked_time_s: float
    block_count: int
    gpu_queue_wait_s: float
    gpu_service_work: float
    generation_ended_at: float | None


@dataclass(frozen=True, slots=True)
class SessionObservation:
    session_id: str
    model_id: str
    arrival_time: float
    access_edge_id: str
    execution_edge_id: str
    context_tokens: int
    authoritative_kv_bytes: int
    status: str
    end_time: float | None
    termination_reason: str | None
    current_turn: TurnObservation | None


@dataclass(frozen=True, slots=True)
class EdgeObservation:
    edge_id: str
    deployed_models: tuple[str, ...]
    gpu_capacity: float
    gpu_slots: int
    kv_capacity_bytes: int
    authoritative_kv_bytes: int
    resident_session_ids: tuple[str, ...]
    running: tuple[TaskObservation, ...]
    ready: tuple[TaskObservation, ...]
    area_id: str | None


@dataclass(frozen=True, slots=True)
class OnlineObservation:
    time_s: float
    sessions: tuple[SessionObservation, ...]
    edges: tuple[EdgeObservation, ...]


@dataclass(frozen=True, slots=True)
class TransferObservation:
    flow_id: str
    session_id: str
    turn_index: int | None
    flow_type: str
    path_id: str | None
    link_ids: tuple[str, ...]
    ready_bytes: int
    transferred_bytes: float
    rate_bps: float
    status: str


@dataclass(frozen=True, slots=True)
class HandoverObservation:
    session_id: str
    draining: bool
    prompt_protected: bool
    wireless_busy: bool
    pending_depth: int
    last_actual_access_change_s: float | None
    migration_source_edge_id: str | None
    migration_target_edge_id: str | None


@dataclass(frozen=True, slots=True)
class ServingObservation(OnlineObservation):
    """Opt-in current transport/control values, never resource/controller objects."""
    network_transfers: tuple[TransferObservation, ...]
    wireless_transfers: tuple[TransferObservation, ...]
    handover_states: tuple[HandoverObservation, ...]


def _task(t):
    return TaskObservation(t.task_id, t.session_id, t.turn_index, t.phase.value,
                           t.unit_index, t.execution_edge_id, t.remaining_work,
                           t.consumed_work, t.status, t.ready_time, t.start_time,
                           t.queue_wait_s)


def observe(runtime: RuntimeState) -> OnlineObservation:
    sessions = []
    for _, session in sorted(runtime.sessions.items()):
        t = session.current_turn
        turn = None if t is None else TurnObservation(
            t.index, t.input_tokens, t.prefill_done, t.decode_done, t.delivered,
            t.submitted_at, t.gpu_ready_time, t.gpu_start_time, t.received_at,
            t.phase.value, t.status, t.wait_reason, t.completion_reason,
            t.generation_complete, t.remaining_gpu_work, t.partial_work,
            t.blocked_since, t.blocked_time_s + (runtime.time_s - t.blocked_since
                                                if t.blocked_since is not None else 0), t.block_count,
            t.gpu_queue_wait_s, t.gpu_service_work, t.generation_ended_at)
        sessions.append(SessionObservation(
            session.session_id, session.model_id, session.arrival_time,
            session.access_edge_id, session.execution_edge_id, session.context_tokens,
            session.authoritative_kv_bytes, session.status, session.end_time,
            session.termination_reason, turn))
    edges = tuple(EdgeObservation(
        edge.edge_id, tuple(sorted(edge.deployed_models)), edge.gpu_capacity,
        edge.gpu_slots, edge.kv_capacity_bytes, edge.authoritative_kv_bytes,
        edge.resident_session_ids, tuple(_task(t) for t in edge.running_tasks),
        tuple(_task(t) for t in edge.ready_queue), edge.area_id) for _, edge in sorted(runtime.edges.items()))
    return OnlineObservation(runtime.time_s, tuple(sessions), edges)


def project_service(current, runtime):
    """Value-only settlement of known current units, without mutating traces.

All due completions precede a mobility event. Thus a lagging lazy resource
clock can only have service inside its current already-known unit, never a
future Token/Turn. This is used only by the opt-in extended Serving DTO.
"""
    progress, edges = {}, []
    for edge in current.edges:
        scheduler = runtime.edges[edge.edge_id].compute.scheduler
        elapsed = Fraction(str(runtime.time_s)) - Fraction(str(scheduler.time_s))
        share = Fraction(str(edge.gpu_capacity)) / len(edge.running) if edge.running else Fraction(0)
        running = []
        for task in edge.running:
            amount = float(min(Fraction(str(task.remaining_work)), elapsed * share))
            progress[(task.session_id, task.turn_index)] = amount
            running.append(replace(task, remaining_work=round(task.remaining_work-amount,12),
                                   consumed_work=round(task.consumed_work+amount,12)))
        edges.append(replace(edge, running=tuple(running)))
    sessions = []
    for session in current.sessions:
        turn = session.current_turn
        if turn is not None:
            amount = progress.get((session.session_id,turn.index),0)
            turn = replace(turn, remaining_gpu_work=round(turn.remaining_gpu_work-amount,12),
                           partial_work=round(turn.partial_work+amount,12),
                           gpu_service_work=round(turn.gpu_service_work+amount,12))
        sessions.append(replace(session,current_turn=turn))
    return replace(current, sessions=tuple(sessions), edges=tuple(edges))
