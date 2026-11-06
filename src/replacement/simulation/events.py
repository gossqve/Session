"""Small shared discrete-event queue; later stages can reuse or extend it."""
from dataclasses import dataclass, field
import heapq
from typing import Any


@dataclass(order=True, frozen=True)
class Event:
    time: float
    priority: int
    sequence: int
    kind: str = field(compare=False)
    payload: dict[str, Any] = field(compare=False)


class EventQueue:
    def __init__(self) -> None:
        self._heap: list[Event] = []
        self._sequence = 0

    def schedule(self, when: float, kind: str, *, priority: int = 50, **payload: Any) -> None:
        # priority is a same-time EVENT PHASE, never Session H/L service priority.
        if when < 0:
            raise ValueError("Simulation time must be nonnegative")
        event = Event(round(when, 12), priority, self._sequence, kind, payload)
        self._sequence += 1
        heapq.heappush(self._heap, event)

    def pop(self) -> Event:
        return heapq.heappop(self._heap)

    def __bool__(self) -> bool:
        return bool(self._heap)
