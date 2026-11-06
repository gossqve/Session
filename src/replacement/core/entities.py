"""Formal configuration/runtime entities. No future workload belongs here."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import TYPE_CHECKING

from ..simulation.events import EventQueue

if TYPE_CHECKING:
    from ..resources.compute import ComputeRegistry, GPUComputeTask
    from ..resources.kv import KVResource, PendingCommit


def identifier(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("ID must be a nonempty string")


def integer(value: int, *, minimum: int = 1) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"Expected integer >= {minimum}")


def number(value: float, *, positive: bool = False) -> None:
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or value < 0 or (positive and value == 0)):
        raise ValueError("Expected finite positive/nonnegative number")


@dataclass(frozen=True, slots=True)
class ModelSpec:
    model_id: str
    layers: int
    kv_heads: int
    head_dim: int
    element_bytes: int
    context_window_tokens: int
    output_limit_per_turn: int
    prefill_work_per_token: float
    decode_work_per_token: float

    def __post_init__(self):
        identifier(self.model_id)
        for value in (self.layers, self.kv_heads, self.head_dim, self.element_bytes,
                      self.context_window_tokens, self.output_limit_per_turn):
            integer(value)
        number(self.prefill_work_per_token, positive=True)
        number(self.decode_work_per_token, positive=True)

    @property
    def kv_bytes_per_token(self) -> int:
        return 2 * self.layers * self.kv_heads * self.head_dim * self.element_bytes

    @classmethod
    def from_config(cls, config: dict) -> ModelSpec:
        if "kv_bytes_per_token" in config:
            raise ValueError("Use structural KV parameters, not fixed kv_bytes_per_token")
        return cls(model_id=config["id"], **{k: config[k] for k in (
            "layers", "kv_heads", "head_dim", "element_bytes", "context_window_tokens",
            "output_limit_per_turn", "prefill_work_per_token", "decode_work_per_token")})


class Phase(str, Enum):
    UPLOAD = "upload"
    PREFILL = "prefill"
    DECODE = "decode"
    DELIVERY = "delivery"
    END = "end"


class CommitResult(str, Enum):
    COMMITTED = "committed"
    CONTEXT_LIMIT = "ContextLimit"
    KV_BLOCKED = "KVBlocked"


@dataclass(frozen=True, slots=True)
class OutputToken:
    """One legally committed Decode output; provenance never follows locations.

    Delivery is owned by TurnState.delivered (the FIFO prefix), not by another
    mutable flag here. token_id also identifies its unique delivery event.
    """
    session_id: str
    turn_index: int
    output_index: int
    generated_at: float
    execution_edge_id: str
    access_edge_id: str
    text_bytes: int

    def __post_init__(self):
        for value in (self.session_id, self.execution_edge_id, self.access_edge_id):
            identifier(value)
        for value in (self.turn_index, self.output_index, self.text_bytes):
            integer(value)
        number(self.generated_at)

    @property
    def token_id(self) -> tuple[str, int, int]:
        return self.session_id, self.turn_index, self.output_index


@dataclass(slots=True)
class TurnState:
    session_id: str
    index: int
    input_tokens: int
    submitted_at: float
    prefill_done: int = 0
    decode_done: int = 0
    delivered: int = 0
    gpu_ready_time: float | None = None
    gpu_start_time: float | None = None
    received_at: float | None = None
    phase: Phase = Phase.UPLOAD
    status: str = "active"
    wait_reason: str | None = "InputUpload"
    completion_reason: str | None = None
    generation_complete: bool = False
    committed_work: float = 0.0
    compute_task: GPUComputeTask | None = field(default=None, repr=False)
    pending_commit: PendingCommit | None = field(default=None, repr=False)
    block_count: int = 0
    blocked_time_s: float = 0.0
    _compute_registry: ComputeRegistry | None = field(default=None, repr=False)
    generation_ended_at: float | None = None
    context_at_end: int | None = None
    kv_at_end: int | None = None
    submitted_access_edge_id: str | None = None
    _output_tokens: list[OutputToken] = field(default_factory=list, init=False, repr=False)

    @property
    def output_tokens(self) -> tuple[OutputToken, ...]:
        """Only actual successful commits, no future outputs or delivery copy."""
        return tuple(self._output_tokens)

    @property
    def gpu_queue_wait_s(self):
        return self._compute_registry.queue_wait(self.session_id, self.index) if self._compute_registry else 0.0

    @property
    def gpu_service_work(self):
        return (self._compute_registry.service_work(self.session_id, self.index) if self._compute_registry
                else self.committed_work + self.partial_work)

    def __post_init__(self):
        identifier(self.session_id)
        integer(self.index)
        integer(self.input_tokens, minimum=0)
        number(self.submitted_at)

    @property
    def remaining_gpu_work(self) -> float:
        return self.compute_task.remaining_work if self.compute_task else 0.0

    @property
    def blocked_since(self) -> float | None:
        return self.pending_commit.blocked_at if self.pending_commit else None

    @property
    def partial_work(self) -> float:
        return self.compute_task.consumed_work if self.compute_task else 0.0


@dataclass(slots=True)
class SessionState:
    session_id: str
    model_id: str
    arrival_time: float
    access_edge_id: str
    execution_edge_id: str
    text_bytes_per_token: int = 1
    initial_access_edge_id: str = field(init=False)
    context_tokens: int = field(default=0, init=False)
    authoritative_kv_bytes: int = field(default=0, init=False)
    status: str = field(default="active", init=False)
    end_time: float | None = field(default=None, init=False)
    termination_reason: str | None = field(default=None, init=False)
    turns: list[TurnState] = field(default_factory=list, init=False, repr=False)

    def __setattr__(self, name, value):
        if name in ("session_id", "model_id", "arrival_time", "initial_access_edge_id",
                    "text_bytes_per_token") and hasattr(self, name):
            raise AttributeError(f"Session {name} is fixed at arrival")
        object.__setattr__(self, name, value)

    def __post_init__(self):
        for value in (self.session_id, self.model_id, self.access_edge_id, self.execution_edge_id):
            identifier(value)
        number(self.arrival_time)
        integer(self.text_bytes_per_token)
        self.initial_access_edge_id = self.access_edge_id

    @property
    def current_turn(self) -> TurnState | None:
        return self.turns[-1] if self.turns else None


@dataclass(slots=True)
class EdgeState:
    edge_id: str
    gpu_capacity: float
    gpu_slots: int
    kv_capacity_bytes: int
    deployed_models: frozenset[str]
    event_queue: EventQueue = field(repr=False)
    # None is explicitly legacy/unspecified, never a fabricated real Area.
    area_id: str | None = None
    compute: ComputeRegistry = field(init=False, repr=False)
    kv: KVResource = field(init=False, repr=False)
    _residents: dict[str, SessionState] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self):
        from ..resources.compute import ComputeRegistry
        from ..resources.kv import KVResource
        identifier(self.edge_id)
        if self.area_id is not None:
            identifier(self.area_id)
        number(self.gpu_capacity, positive=True)
        integer(self.gpu_slots)
        integer(self.kv_capacity_bytes, minimum=0)
        self.deployed_models = frozenset(self.deployed_models)
        for value in self.deployed_models:
            identifier(value)
        self.compute = ComputeRegistry(self, self.event_queue)
        self.kv = KVResource(self)

    def __setattr__(self, name, value):
        if name in ("edge_id", "area_id", "gpu_capacity", "gpu_slots", "deployed_models") and hasattr(self, "compute"):
            raise AttributeError("Edge GPU configuration/deployment is fixed")
        object.__setattr__(self, name, value)

    @property
    def authoritative_kv_bytes(self) -> int:
        return sum(s.authoritative_kv_bytes for s in self._residents.values())

    @property
    def resident_session_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._residents))

    @property
    def running_tasks(self) -> tuple[GPUComputeTask, ...]:
        return tuple(self.compute.task_for_resource(key) for key in self.compute.scheduler.rates)

    @property
    def ready_queue(self) -> tuple[GPUComputeTask, ...]:
        return tuple(self.compute.task_for_resource(key) for key in self.compute.scheduler.waiting_ids)

