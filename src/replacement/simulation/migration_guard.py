"""Per-Session single-inflight admission; no KV Copy, cancellation policy or Cutover.

The caller must establish real completion/Cutover or a real failure before
releasing a lease. Rejected requests are not queued or replayed on release.
"""
from dataclasses import dataclass
from types import MappingProxyType
from ..core.entities import identifier


@dataclass(frozen=True, slots=True)
class MigrationLease:
    operation_id: int
    session_id: str
    source_edge_id: str
    target_edge_id: str


class MigrationAdmissionGuard:
    def __init__(self):
        self._active = {}
        self._sequence = 0
        self.rejected_duplicate_count = 0
        self.events = []

    @property
    def active(self):
        return MappingProxyType(dict(self._active))

    def try_begin(self, session_id, source_edge_id, target_edge_id):
        for value in (session_id, source_edge_id, target_edge_id):
            identifier(value)
        if source_edge_id == target_edge_id:
            raise ValueError("Migration requires distinct Source and Target")
        if session_id in self._active:
            self.rejected_duplicate_count += 1
            self.events.append(dict(event="duplicate_rejected", session_id=session_id))
            return None
        self._sequence += 1
        lease = MigrationLease(self._sequence, session_id, source_edge_id, target_edge_id)
        self._active[session_id] = lease
        self.events.append(dict(event="admitted", session_id=session_id, operation_id=lease.operation_id))
        return lease

    def _release(self, lease, event, reason=None):
        if not isinstance(lease, MigrationLease) or self._active.get(lease.session_id) is not lease:
            raise ValueError("Stale or foreign migration lease")
        del self._active[lease.session_id]
        self.events.append(dict(event=event, session_id=lease.session_id,
                                operation_id=lease.operation_id, reason=reason))

    def complete(self, lease):
        self._release(lease, "completed")

    def fail(self, lease, reason):
        identifier(reason)
        self._release(lease, "failed", reason)
