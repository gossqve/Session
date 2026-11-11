"""S1-A generic eq-work Processor Sharing on the existing event queue.

No admission limits, policy observations, task priorities or preemption.
Dispatch the global queue chronologically. Consume completion notifications
returned by *every* mutating call (including submit/advance/withdraw).
Snapshots are simulator state, not information exposed to an online policy.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import math
from types import MappingProxyType
from typing import Mapping

from ..simulation.events import Event, EventQueue


@dataclass(frozen=True)
class TaskSnapshot:
    task_id: str
    initial_work: float
    consumed_work: float
    remaining_work: float
    status: str


@dataclass(frozen=True)
class GPUCompletion:
    task_id: str
    time_s: float


@dataclass
class _Task:
    initial: Fraction
    remaining: Fraction
    order: int
    status: str = "running"
    retain_slot: bool = False


class EqualShareGPU:
    """One resource per Edge; edge_id must be unique on the shared queue.

    Work and capacity use eq-work and eq-work/s. Accounting uses rational
    decimal inputs. Completion predictions round UP to the EventQueue's
    1e-12 s grid (at most one tick late at ordinary simulation magnitudes).
    Completed work is capped by remaining work, never by a fixed epsilon.
    Return values are one-shot completion notifications in admission order.
    """

    event_kind = "gpu_completion"
    _ticks = 10**12

    def __init__(self, queue: EventQueue, edge_id: str, capacity: float):
        self._capacity = self._number(capacity, "capacity", positive=True)
        if not isinstance(edge_id, str) or not edge_id:
            raise ValueError("edge_id must be a nonempty string")
        self.queue = queue
        self.edge_id = edge_id
        self._time = Fraction(0)
        self._tasks: dict[str, _Task] = {}
        self._version = 0
        self._deadline: float | None = None
        self.trace: list[dict] = []

    @staticmethod
    def _number(value: float, name: str, *, positive: bool = False) -> Fraction:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} must be a finite number")
        if not math.isfinite(value) or value < 0 or (positive and value == 0):
            raise ValueError(f"{name} must be finite and {'positive' if positive else 'nonnegative'}")
        return Fraction(str(value))

    @property
    def time_s(self) -> float:
        return float(self._time)

    @property
    def tasks(self) -> Mapping[str, TaskSnapshot]:
        """Read-only snapshots at the last settlement time, including history."""
        return MappingProxyType({key: TaskSnapshot(key, float(t.initial),
                                 float(t.initial - t.remaining), float(t.remaining), t.status)
                                 for key, t in self._ordered()})

    def task_snapshot(self, task_id):
        """Read one immutable task view without rebuilding all historical views."""
        task = self._tasks.get(task_id)
        return None if task is None else TaskSnapshot(task_id, float(task.initial),
                    float(task.initial-task.remaining), float(task.remaining), task.status)

    @property
    def rates(self) -> dict[str, float]:
        active = [(key, t) for key, t in self._ordered() if t.status in ("running", "awaiting_unit")]
        rate = float(self._capacity / len(active)) if active else 0.0
        return {key: rate if t.status == "running" else 0.0 for key, t in active}

    def _ordered(self) -> list[tuple[str, _Task]]:
        return sorted(self._tasks.items(), key=lambda item: item[1].order)

    def _running(self) -> list[tuple[str, _Task]]:
        return [(key, task) for key, task in self._ordered() if task.status == "running"]

    def _log(self, event: str, **detail) -> None:
        self.trace.append({"seq": len(self.trace), "time_s": self.time_s,
                           "edge_id": self.edge_id, "event": event, **detail})

    def _check_time(self, time_s: float) -> Fraction:
        now = self._number(time_s, "time")
        if now < self._time:
            raise ValueError("GPU time cannot move backwards")
        if now > self._time and any(t.status == "awaiting_unit" for t in self._tasks.values()):
            raise ValueError("Resolve retained unit boundaries at the same clock before advancing")
        if self._deadline is not None and now > Fraction(str(self._deadline)):
            raise ValueError("Dispatch pending GPU completion before advancing past its deadline")
        return now

    def _settle(self, now: Fraction) -> tuple[GPUCompletion, ...]:
        running = self._running()
        elapsed = now - self._time
        used = Fraction(0)
        if running:
            share = elapsed * self._capacity / len(running)
            for _, task in running:
                work = min(task.remaining, share)
                task.remaining -= work
                used += work
        self._time = now
        if elapsed:
            self._log("service", elapsed_s=float(elapsed), consumed_work=float(used),
                      running_count=len(running))
        return self._finish_ready()

    def _finish_ready(self) -> tuple[GPUCompletion, ...]:
        completed = []
        for key, task in self._running():
            if task.remaining == 0:
                task.status = "awaiting_unit" if task.retain_slot else "completed"
                completed.append(GPUCompletion(key, self.time_s))
                self._log("complete", task_id=key)
        return tuple(completed)

    def _predict(self) -> None:
        self._version += 1
        self._deadline = None
        running = self._running()
        if running and not any(t.status == "awaiting_unit" for t in self._tasks.values()):
            exact = self._time + min(t.remaining for _, t in running) * len(running) / self._capacity
            ticks = math.ceil(exact * self._ticks)
            deadline = round(ticks / self._ticks, 12)
            # Float spacing can exceed one tick at large absolute times.
            while math.isfinite(deadline) and (Fraction(str(deadline)) < exact or deadline <= self.time_s):
                deadline = round(math.nextafter(deadline, math.inf), 12)
                if deadline <= self.time_s:
                    deadline = round((ticks + 1) / self._ticks, 12)
                    ticks += 1
            if not math.isfinite(deadline):
                raise ValueError("GPU completion time is not representable")
            self._deadline = deadline
            self.queue.schedule(deadline, self.event_kind, priority=20,
                                edge_id=self.edge_id, version=self._version)
        self._log("shares", rates=self.rates, version=self._version,
                  predicted_completion_s=self._deadline)

    def submit(self, task_id: str, work: float, time_s: float, *, retain_slot=False) -> tuple[GPUCompletion, ...]:
        """Admit a generic task now; task IDs remain unique for this resource's life."""
        amount = self._number(work, "work")
        now = self._check_time(time_s)
        if not isinstance(task_id, str) or not task_id or task_id in self._tasks:
            raise ValueError("task_id must be nonempty and unique")
        completed = self._settle(now)
        self._tasks[task_id] = _Task(amount, amount, len(self._tasks), retain_slot=retain_slot)
        self._log("submit", task_id=task_id, initial_work=float(amount))
        completed += self._finish_ready()
        self._predict()
        return completed

    def continue_task(self, task_id: str, work: float, time_s: float) -> tuple[GPUCompletion, ...]:
        amount = self._number(work, "work", positive=True)
        now = self._check_time(time_s)
        task = self._tasks.get(task_id)
        if task is None or task.status != "awaiting_unit" or not task.retain_slot or now != self._time:
            raise ValueError("Continue requires a retained completed unit at the current clock")
        task.initial += amount
        task.remaining = amount
        task.status = "running"
        self._log("continue", task_id=task_id, unit_work=float(amount))
        self._predict()
        return ()

    def release_turn(self, task_id: str, time_s: float) -> None:
        now = self._check_time(time_s)
        task = self._tasks.get(task_id)
        if task is None or task.status != "awaiting_unit" or not task.retain_slot or now != self._time:
            raise ValueError("Release requires a retained completed unit at the current clock")
        task.status = "completed"
        self._log("release_turn", task_id=task_id)
        self._predict()

    def advance(self, time_s: float) -> tuple[GPUCompletion, ...]:
        """Settle progress at a checkpoint; never skip a pending completion."""
        completed = self._settle(self._check_time(time_s))
        if completed:
            self._predict()
        return completed

    def withdraw(self, task_id: str, time_s: float) -> tuple[GPUCompletion, ...]:
        """Explicit resource exit hook; no scheduling policy invokes it automatically.

        Work is preserved for accounting; withdrawn tasks receive no completion.
        A task finishing exactly at the exit time completes normally instead.
        """
        now = self._check_time(time_s)
        if task_id not in self._tasks or self._tasks[task_id].status != "running":
            raise ValueError("Only a running task can exit")
        completed = self._settle(now)
        task = self._tasks[task_id]
        if task.status == "running":
            task.status = "withdrawn"
            self._log("withdraw", task_id=task_id, remaining_work=float(task.remaining))
        self._predict()
        return completed

    def handle_event(self, event: Event) -> tuple[GPUCompletion, ...]:
        """Ignore foreign/stale predictions BEFORE any clock or work mutation."""
        if not self.is_current_event(event):
            return ()
        completed = self._settle(self._check_time(event.time))
        self._predict()
        return completed

    def is_current_event(self, event: Event) -> bool:
        return (event.kind == self.event_kind and event.payload.get("edge_id") == self.edge_id
                and event.payload.get("version") == self._version and self._deadline == event.time)
