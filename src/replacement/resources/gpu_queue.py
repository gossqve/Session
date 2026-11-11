"""S1-B admission slots and non-preemptive FCFS over the S1-A GPU engine.

Use this controller exclusively for its Edge: never mutate its underlying GPU
directly. Consume completions returned by ready/advance/cancel/handle_event.
All times describe the GPU Ready phase, not full Turn submission or delivery.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from fractions import Fraction
import math
from types import MappingProxyType
from typing import Mapping

from ..simulation.events import Event, EventQueue
from .gpu import EqualShareGPU, GPUCompletion


@dataclass(frozen=True)
class QueuedTaskSnapshot:
    task_id: str
    ready_time: float
    start_time: float | None
    completion_time: float | None
    queue_wait_s: float
    initial_work: float
    consumed_work: float
    remaining_work: float
    status: str
    cancelled_time: float | None


@dataclass
class _ReadyRecord:
    work: float
    ready_time: float
    sequence: int
    start_time: float | None = None
    completion_time: float | None = None
    cancelled_time: float | None = None
    retain_slot: bool = False


class GPUQueue:
    """One controller per Edge, with capacity C and independent positive slots L.

    Ready calls must follow simulation-time order. A deque then implements FCFS
    by (Ready time, explicit submission sequence). Historical records contain
    lifecycle timestamps, not a second running set or work-progress counter.
    Only the S1-A engine owns running state, work accounting and predictions.
    """

    def __init__(self, queue: EventQueue, edge_id: str, capacity: float, slots: int):
        if isinstance(slots, bool) or not isinstance(slots, int) or slots <= 0:
            raise ValueError("slots must be a positive integer")
        self._gpu = EqualShareGPU(queue, edge_id, capacity)
        self._slots = slots
        self._capacity = float(capacity)
        self._records: dict[str, _ReadyRecord] = {}
        self.fast_snapshots = False
        self._waiting: deque[str] = deque()
        self.trace: list[dict] = []

    @property
    def slots(self) -> int:
        return self._slots

    @property
    def capacity(self) -> float:
        return self._capacity

    @property
    def edge_id(self) -> str:
        return self._gpu.edge_id

    @property
    def time_s(self) -> float:
        return self._gpu.time_s

    @property
    def rates(self) -> dict[str, float]:
        return self._gpu.rates

    @property
    def waiting_ids(self) -> tuple[str, ...]:
        return tuple(self._waiting)

    @property
    def gpu_trace(self) -> list[dict]:
        """Copy of the underlying engine trace for diagnostics and demo output."""
        return [dict(event) for event in self._gpu.trace]

    @property
    def tasks(self) -> Mapping[str, QueuedTaskSnapshot]:
        """Immutable snapshots; waiting time accrues through the settled clock."""
        gpu_tasks = self._gpu.tasks
        snapshots = {}
        for task_id, record in sorted(self._records.items(), key=lambda item: item[1].sequence):
            task = gpu_tasks.get(task_id)
            if record.completion_time is not None:
                status = "completed"
            elif record.cancelled_time is not None:
                status = "cancelled"
            else:
                status = task.status if task is not None else "waiting"
            wait_end = record.start_time
            if wait_end is None:
                wait_end = record.cancelled_time if record.cancelled_time is not None else self.time_s
            wait = float(Fraction(str(wait_end)) - Fraction(str(record.ready_time)))
            snapshots[task_id] = QueuedTaskSnapshot(
                task_id, record.ready_time, record.start_time, record.completion_time,
                wait, task.initial_work if task else record.work,
                task.consumed_work if task else 0.0,
                task.remaining_work if task else record.work, status, record.cancelled_time)
        return MappingProxyType(snapshots)

    def task_snapshot(self, task_id):
        """Same values as tasks[task_id], with constant-size immutable copying."""
        record = self._records[task_id]
        task = self._gpu.task_snapshot(task_id)
        status = ("completed" if record.completion_time is not None else
                  "cancelled" if record.cancelled_time is not None else
                  task.status if task is not None else "waiting")
        wait_end = record.start_time
        if wait_end is None:
            wait_end = record.cancelled_time if record.cancelled_time is not None else self.time_s
        return QueuedTaskSnapshot(task_id, record.ready_time, record.start_time, record.completion_time,
                    float(Fraction(str(wait_end))-Fraction(str(record.ready_time))),
                    task.initial_work if task else record.work, task.consumed_work if task else 0.0,
                    task.remaining_work if task else record.work, status, record.cancelled_time)

    def _log(self, event: str, **detail) -> None:
        self.trace.append({"seq": len(self.trace), "time_s": self.time_s,
                           "edge_id": self.edge_id, "event": event,
                           "running_ids": list(self.rates), "waiting_ids": list(self._waiting),
                           **detail})

    def _completed(self, completions: tuple[GPUCompletion, ...]) -> None:
        for completion in completions:
            record = self._records[completion.task_id]
            if record.completion_time is not None:
                raise RuntimeError("GPU completion notified twice")
            if record.retain_slot:
                self._log("unit_complete", task_id=completion.task_id)
            else:
                record.completion_time = completion.time_s
                self._log("complete", task_id=completion.task_id)

    def _fill_slots(self) -> tuple[GPUCompletion, ...]:
        completed: tuple[GPUCompletion, ...] = ()
        while self._waiting and len(self.rates) < self.slots:
            task_id = self._waiting.popleft()
            record = self._records[task_id]
            record.start_time = self.time_s
            result = self._gpu.submit(task_id, record.work, self.time_s, retain_slot=record.retain_slot)
            self._log("start", task_id=task_id,
                      queue_wait_s=self.tasks[task_id].queue_wait_s, rates=self.rates)
            self._completed(result)
            completed += result
        return completed

    def ready(self, task_id: str, work: float, time_s: float, *, retain_slot=False) -> tuple[GPUCompletion, ...]:
        """Enter GPU Ready now. Existing waiters always get released slots first."""
        if not isinstance(task_id, str) or not task_id or task_id in self._records:
            raise ValueError("task_id must be a nonempty unique string")
        if (isinstance(work, bool) or not isinstance(work, (int, float))
                or not math.isfinite(work) or work < 0):
            raise ValueError("work must be finite and nonnegative")
        self._validate_clock_representation(time_s)
        completed = self._gpu.advance(time_s)  # validates clock before any queue mutation
        self._completed(completed)
        # Preserve integer/decimal input exactly for the Fraction-based engine.
        self._records[task_id] = _ReadyRecord(work, self.time_s, len(self._records), retain_slot=retain_slot)
        self._waiting.append(task_id)
        self._log("ready", task_id=task_id, work=float(work))
        return completed + self._fill_slots()

    def continue_task(self, task_id: str, work: float, time_s: float) -> tuple[GPUCompletion, ...]:
        self._validate_clock_representation(time_s)
        return self._gpu.continue_task(task_id, work, time_s)

    def release_turn(self, task_id: str, time_s: float) -> tuple[GPUCompletion, ...]:
        self._validate_clock_representation(time_s)
        self._gpu.release_turn(task_id, time_s)
        self._records[task_id].completion_time = time_s
        self._log("turn_release", task_id=task_id)
        return self._fill_slots()

    def advance(self, time_s: float) -> tuple[GPUCompletion, ...]:
        """Settle a checkpoint; pending GPU completion deadlines cannot be skipped."""
        self._validate_clock_representation(time_s)
        completed = self._gpu.advance(time_s)
        self._completed(completed)
        return completed + self._fill_slots()

    def cancel(self, task_id: str, time_s: float) -> tuple[GPUCompletion, ...]:
        """Cancel waiting or running work, retaining work and timestamps.

        Completions due now win the tie. Repeated cancellation of a known
        terminal task is harmless; unknown IDs are errors. A cancelled waiter
        cannot start even if a slot is released in this call. No resume is added.
        """
        if not isinstance(task_id, str) or task_id not in self._records:
            raise ValueError("Cannot cancel an unknown task_id")
        self._validate_clock_representation(time_s)
        completed = self._gpu.advance(time_s)
        self._completed(completed)
        record = self._records[task_id]
        if record.completion_time is None and record.cancelled_time is None:
            if record.start_time is None:
                self._waiting.remove(task_id)
            else:
                result = self._gpu.withdraw(task_id, self.time_s)
                self._completed(result)
                completed += result
            record.cancelled_time = self.time_s
            self._log("cancel", task_id=task_id)
        return completed + self._fill_slots()

    def handle_event(self, event: Event) -> tuple[GPUCompletion, ...]:
        """Let the existing GPU validate versions/ownership before scheduling."""
        completed = self._gpu.handle_event(event)
        if not completed:
            return ()
        self._completed(completed)
        return completed + self._fill_slots()

    def is_current_event(self, event: Event) -> bool:
        return self._gpu.is_current_event(event)

    @staticmethod
    def _validate_clock_representation(time_s: float) -> None:
        # Reject lossy integer clocks before settlement or queue mutation.
        if isinstance(time_s, int):
            try:
                represented = float(time_s)
            except OverflowError as exc:
                raise ValueError("Integer time is not representable by the event clock") from exc
            if not math.isfinite(represented) or Fraction(str(represented)) != time_s:
                raise ValueError("Integer time is not exactly representable by the event clock")
