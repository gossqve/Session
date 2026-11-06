"""Typed Session/Turn/unit bindings over the existing S1-B GPUQueue."""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TYPE_CHECKING

from ..core.entities import Phase, integer, number
from .gpu_queue import GPUQueue

if TYPE_CHECKING:
    from ..core.entities import EdgeState, SessionState, TurnState, ModelSpec
    from ..simulation.events import Event, EventQueue


@dataclass(slots=True)
class _UnitTiming:
    work: float
    ready: float
    start: float | None = None
    completed: float | None = None


@dataclass(frozen=True, slots=True)
class GPUComputeTask:
    task_id: str
    session_id: str
    turn_index: int
    phase: Phase
    unit_index: int
    execution_edge_id: str
    _scheduler: GPUQueue = field(repr=False, compare=False)
    _resource_id: str | None = field(default=None, repr=False)
    _timing: _UnitTiming | None = field(default=None, repr=False, compare=False)

    @property
    def resource_id(self):
        return self._resource_id or self.task_id

    @property
    def _snapshot(self):
        return self._scheduler.tasks[self.resource_id]

    @property
    def remaining_work(self):
        return 0.0 if self._timing and self._timing.completed is not None else self._snapshot.remaining_work

    @property
    def consumed_work(self):
        if self._timing:
            return self._timing.work if self._timing.completed is not None else self._timing.work - self.remaining_work
        return self._snapshot.consumed_work

    @property
    def status(self):
        return "completed" if self._timing and self._timing.completed is not None else self._snapshot.status

    @property
    def ready_time(self):
        return self._timing.ready if self._timing else self._snapshot.ready_time

    @property
    def start_time(self):
        return self._timing.start if self._timing else self._snapshot.start_time

    @property
    def completion_time(self):
        return self._timing.completed if self._timing else self._snapshot.completion_time

    @property
    def queue_wait_s(self):
        if self._timing and self._snapshot.ready_time != self._timing.ready:
            return 0.0  # continuation, not a new Ready interval
        return self._snapshot.queue_wait_s


class ComputeRegistry:
    def __init__(self, edge: EdgeState, queue: EventQueue):
        self.edge = edge
        self.scheduler = GPUQueue(queue, edge.edge_id, edge.gpu_capacity, edge.gpu_slots)
        self._tasks: dict[str, GPUComputeTask] = {}
        self._turns: dict[str, TurnState] = {}
        self._runtime = None
        self._lease_units: dict[str, str] = {}
        self._lease_owners: dict[str, tuple[str, int]] = {}

    def bind_runtime(self, runtime):
        if self._runtime is not None and self._runtime is not runtime:
            raise ValueError("An Edge compute registry belongs to one runtime")
        self._runtime = runtime

    @property
    def tasks(self):
        return MappingProxyType(self._tasks)

    def _sync(self, completions):
        resolved = []
        for completion in completions:
            task = self.task_for_resource(completion.task_id)
            if task._timing:
                task._timing.completed = completion.time_s
            resolved.append(task)
        for key, task in self._tasks.items():
            if task._timing and task._timing.start is None:
                task._timing.start = task._snapshot.start_time
            turn = self._turns[key]
            if turn.gpu_start_time is None and task.start_time is not None:
                turn.gpu_start_time = task.start_time
            if turn.compute_task is task and turn.status not in ("blocked", "completed", "failed"):
                turn.wait_reason = "GPUQueue" if task.status == "waiting" else None
        return tuple(resolved)

    def task_for_resource(self, resource_id):
        return self._tasks[self._lease_units.get(resource_id, resource_id)]

    def _active_lease(self, session_id, turn_index):
        keys = [key for key, owner in self._lease_owners.items() if owner == (session_id, turn_index)
                and self.scheduler.tasks[key].status not in ("completed", "cancelled")]
        if len(keys) > 1:
            raise RuntimeError("Turn owns multiple active GPU slots")
        return keys[0] if keys else None

    def queue_wait(self, session_id, turn_index):
        return sum(self.scheduler.tasks[key].queue_wait_s for key, owner in self._lease_owners.items()
                   if owner == (session_id, turn_index))

    def service_work(self, session_id, turn_index):
        return sum(t.consumed_work for t in self._tasks.values()
                   if (t.session_id, t.turn_index) == (session_id, turn_index))

    def release_turn(self, session_id, turn_index, time_s):
        key = self._active_lease(session_id, turn_index)
        return self._sync(self.scheduler.release_turn(key, time_s)) if key else ()

    def submit(self, session: SessionState, turn: TurnState, model: ModelSpec,
               phase: Phase, unit_index: int, time_s: float, *, continuous=False):
        if (session.session_id != turn.session_id or session.current_turn is not turn
                or self.edge._residents.get(session.session_id) is not session
                or session.execution_edge_id != self.edge.edge_id
                or session.model_id != model.model_id or model.model_id not in self.edge.deployed_models):
            raise ValueError("Compute binding must match Session, Turn, model and Execution Edge")
        if self._runtime is None or self._runtime.models.get(session.model_id) is not model:
            raise ValueError("Compute must use the runtime's canonical ModelSpec")
        number(time_s)
        if time_s != self._runtime.time_s or time_s < turn.submitted_at:
            raise ValueError("GPU Ready must use the current runtime clock after Turn submission")
        if (session.status != "active" or turn.compute_task is not None or turn.generation_complete
                or turn.phase not in (Phase.PREFILL, Phase.DECODE)):
            raise ValueError("Turn is not eligible for a new GPU unit")
        integer(unit_index)
        if phase == Phase.PREFILL:
            valid = unit_index == turn.prefill_done + 1 and unit_index <= turn.input_tokens
            work = model.prefill_work_per_token
        elif phase == Phase.DECODE:
            valid = (turn.prefill_done == turn.input_tokens and unit_index == turn.decode_done + 1
                     and unit_index <= model.output_limit_per_turn)
            work = model.decode_work_per_token
        else:
            raise ValueError("Only Prefill/Decode units receive GPU service")
        if not valid:
            raise ValueError("Illegal current compute unit index")
        task_id = f"{self.edge.edge_id}:gpu:{len(self._tasks)}"
        # GPUQueue validates before mutation; publish metadata only after success.
        lease = self._active_lease(session.session_id, turn.index)
        if lease is not None and not continuous:
            raise ValueError("A retained Turn must continue its existing slot, not submit an atomic task")
        continued = lease is not None
        if continuous:
            resource_id = lease or f"{self.edge.edge_id}:turn:{len(self.scheduler.tasks)}"
            completions = (self.scheduler.continue_task(resource_id, work, time_s) if continued else
                           self.scheduler.ready(resource_id, work, time_s, retain_slot=True))
            timing = _UnitTiming(work, time_s, time_s if continued else None)
        else:
            resource_id, timing = task_id, None
            completions = self.scheduler.ready(task_id, work, time_s)
        task = GPUComputeTask(task_id, session.session_id, turn.index, phase, unit_index,
                              self.edge.edge_id, self.scheduler, resource_id, timing)
        self._tasks[task_id] = task
        self._turns[task_id] = turn
        if continuous:
            self._lease_units[resource_id] = task_id
            self._lease_owners[resource_id] = (session.session_id, turn.index)
            turn._compute_registry = self
        turn.compute_task = task
        turn.phase = phase
        if turn.gpu_ready_time is None:
            turn.gpu_ready_time = task.ready_time
        return self._sync(completions)

    def handle_event(self, event: Event):
        return self._sync(self.scheduler.handle_event(event))

    def advance(self, time_s: float):
        return self._sync(self.scheduler.advance(time_s))
