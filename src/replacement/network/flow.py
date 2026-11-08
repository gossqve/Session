"""Read-only transfer views. Runtime alone owns byte progress."""
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction
from .entities import FixedPath


class FlowType(str, Enum):
    PROMPT = 'prompt'
    RESPONSE = 'response'
    HANDOVER = 'handover'
    INPUT_HANDOFF = 'input_handoff'
    KV_COPY = 'kv_copy'
    UPLOAD = 'upload'
    DOWNLOAD = 'download'


class FlowStatus(str, Enum):
    CREATED = 'created'
    ACTIVE = 'active'
    WAITING_FOR_DATA = 'waiting_for_data'
    PAUSED = 'paused'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'


@dataclass(frozen=True, slots=True)
class TokenBoundary:
    token_id: str | tuple[str, int, int]
    cumulative_bytes: int
    arrived_at: float | None = None


@dataclass(frozen=True, slots=True)
class TransferNotice:
    flow_id: str
    kind: str
    time_s: float
    token_id: str | tuple[str, int, int] | None = None


@dataclass(frozen=True, slots=True)
class Flow:
    flow_id: str
    flow_type: FlowType
    session_id: str
    turn_index: int | None
    operation_id: str | None
    path: FixedPath | None
    ready_bytes: int
    transferred_bytes: Fraction
    producer_closed: bool
    status: FlowStatus
    created_at: float
    started_at: float | None
    last_update_at: float
    completed_at: float | None
    cancelled_at: float | None
    rate_bps: Fraction | float
    event_version: int
    token_boundaries: tuple[TokenBoundary, ...]
    rate_limit_bps: float | None = None

    @property
    def pending_bytes(self):
        return self.ready_bytes - self.transferred_bytes

    @property
    def path_id(self):
        return self.path.path_id if self.path else None

    @property
    def link_ids(self):
        return self.path.link_ids if self.path else ()
