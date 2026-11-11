"""Private, on-demand Section III.B.3 mobility plans; no actual Handover.

Resource settlement remains lazy: planning never changes an activity set or
reads partial service. Due resource events precede mobility at priority 80.
"""
from collections import deque
from copy import deepcopy
from dataclasses import dataclass, field, asdict
from fractions import Fraction
import hashlib
import json

from ..core.entities import number


@dataclass(frozen=True, slots=True)
class PendingMove:
    check_index: int
    source_edge_id: str
    target_edge_id: str
    planned_at: float


@dataclass(slots=True)
class MobilitySessionState:
    session_id: str
    initial_access_edge_id: str
    planned_access_edge_id: str
    arrival_time: float
    next_check_index: int = 1
    mobility_check_count: int = 0
    planned_change_count: int = 0
    pending_moves: deque[PendingMove] = field(default_factory=deque)
    max_pending_depth: int = 0
    pending_moves_cancelled: int = 0
    active: bool = True
    last_accepted_move_at: float | None = None
    markov_move_proposals: int = 0
    moves_rejected_min_interval: int = 0


class MobilityRuntime:
    event_kind = "mobility_check"

    def __init__(self, queue, topology, config):
        if topology is None:
            raise ValueError("Mobility requires NetworkTopology")
        spec = config["mobility"]
        if not isinstance(spec, dict):
            raise ValueError("mobility must be an object")
        interval = spec.get("check_interval_s")
        horizon = config.get("observation_end_s")
        number(interval, positive=True)
        number(horizon)
        self._interval = Fraction(str(interval))
        self.frequency_control = "min_inter_move_interval_s" in spec
        minimum = spec.get("min_inter_move_interval_s", 0)
        number(minimum)
        self.min_inter_move_interval_s = minimum
        if self._interval < Fraction(1, 10**12):
            raise ValueError("Mobility interval is below EventQueue's 1e-12 s resolution")
        self.observation_end_s = round(horizon, 12)
        self._horizon = Fraction(str(self.observation_end_s))
        self._seed = config.get("seed", 0)
        if isinstance(self._seed, bool) or not isinstance(self._seed, int):
            raise ValueError("Mobility seed must be an integer")
        self.queue = queue
        self.sessions = {}
        self.events = []
        self._matrix = self._validate_matrix(topology, spec.get("transition_probabilities"))
        self._validate_sessions(topology, config["sessions"])

    @staticmethod
    def _validate_matrix(topology, matrix):
        if not isinstance(matrix, dict) or set(matrix) != set(topology.edges):
            raise ValueError("Mobility matrix sources must cover exactly all registered Edges")
        result = {}
        for source in sorted(matrix):
            row = matrix[source]
            if not isinstance(row, dict) or not set(row).issubset(topology.edges):
                raise ValueError("Mobility targets must be registered Edges")
            probabilities = {}
            for target, value in sorted(row.items()):
                number(value)
                p = Fraction(str(value))
                probabilities[target] = p
                if p > 0 and target != source:
                    if target not in topology.mobility_adjacency.get(source, ()):
                        raise ValueError(f"Mobility {source}->{target}: not a legal neighbor")
                    topology.get_path(source, target)
            if sum(probabilities.values(), Fraction(0)) != 1:
                raise ValueError(f"Mobility {source}: probability sum must equal exactly 1")
            result[source] = probabilities
        return result

    def _validate_sessions(self, topology, sessions):
        allowed = set(topology.validate_serving_pairs())
        for session in sessions:
            initial, execution = session["access_edge_id"], session["execution_edge_id"]
            if initial not in topology.edges or execution not in topology.edges:
                raise ValueError("Session Access/Execution must be registered")
            todo, reached = [initial], set()
            while todo:
                access = todo.pop()
                if access in reached:
                    continue
                reached.add(access)
                if (access, execution) not in allowed:
                    raise ValueError(f"Reachable Serving pair is not permitted: {access}/{execution}")
                topology.validate_access_execution(access, execution)
                todo.extend(target for target, p in self._matrix[access].items() if p > 0)
            arrival = round(session.get("arrival_time", 0), 12)
            number(arrival)
            # Reject unrepresentable progress instead of scheduling a zero-time loop.
            when = Fraction(str(arrival)) + self._interval
            if when <= self._horizon and round(float(when), 12) <= arrival:
                raise ValueError("Mobility check cannot advance the clock at this arrival")

    @staticmethod
    def draw(seed, session_id, check_index):
        """Exact [0,1) sample: compact UTF-8 JSON [seed,id,index], SHA-256 prefix."""
        data = json.dumps([seed, session_id, check_index], ensure_ascii=False,
                          separators=(",", ":")).encode("utf-8")
        return Fraction(int.from_bytes(hashlib.sha256(data).digest()[:8], "big"), 2**64)

    def _next_time(self, state):
        exact = Fraction(str(state.arrival_time)) + state.next_check_index * self._interval
        return round(float(exact), 12) if exact <= self._horizon else None

    def _schedule(self, state):
        when = self._next_time(state)
        if when is not None:
            self.queue.schedule(when, self.event_kind, priority=80,
                                session_id=state.session_id, check_index=state.next_check_index)

    def register(self, session):
        if session.session_id in self.sessions:
            raise ValueError("Mobility Session is already registered")
        state = MobilitySessionState(session.session_id, session.initial_access_edge_id,
                                     session.initial_access_edge_id, session.arrival_time)
        self.sessions[session.session_id] = state
        self._schedule(state)

    def is_current_event(self, event):
        state = self.sessions.get(event.payload.get("session_id"))
        return (event.kind == self.event_kind and state is not None and state.active
                and event.payload.get("check_index") == state.next_check_index
                and event.time == self._next_time(state))

    def handle_event(self, event):
        if not self.is_current_event(event):
            return
        state = self.sessions[event.payload["session_id"]]
        source = state.planned_access_edge_id
        value = self.draw(self._seed, state.session_id, state.next_check_index)
        total = Fraction(0)
        for target, probability in self._matrix[source].items():
            total += probability
            if value < total:
                break
        proposed = target
        rejected = False
        if target != source:
            state.markov_move_proposals += 1
            rejected = (state.last_accepted_move_at is not None
                        and Fraction(str(event.time)) - Fraction(str(state.last_accepted_move_at))
                        < Fraction(str(self.min_inter_move_interval_s)))
            if rejected:
                state.moves_rejected_min_interval += 1
                target = source
        state.planned_access_edge_id = target
        state.mobility_check_count += 1
        self.events.append(dict(event="mobility_check", time_s=event.time,
                                session_id=state.session_id, check_index=state.next_check_index,
                                source_edge_id=source, target_edge_id=target))
        if rejected:
            self.events.append(dict(event="mobility_move_rejected", time_s=event.time,
                                    session_id=state.session_id, check_index=state.next_check_index,
                                    source_edge_id=source, proposed_target_edge_id=proposed,
                                    reason="MinInterMoveInterval"))
        if target != source:
            state.last_accepted_move_at = event.time
            move = PendingMove(state.next_check_index, source, target, event.time)
            state.pending_moves.append(move)
            state.planned_change_count += 1
            state.max_pending_depth = max(state.max_pending_depth, len(state.pending_moves))
            self.events.append(dict(event="mobility_pending_added", time_s=event.time,
                                    session_id=state.session_id, **asdict(move)))
        state.next_check_index += 1
        self._schedule(state)

    def end_session(self, session_id, time_s):
        state = self.sessions[session_id]
        if not state.active:
            return
        state.active = False  # invalidates the sole scheduled check, before clock advancement
        count = len(state.pending_moves)
        state.pending_moves_cancelled += count
        state.pending_moves.clear()
        self.events.append(dict(event="mobility_session_end", time_s=time_s, session_id=session_id))
        self.events.append(dict(event="mobility_pending_cleared", time_s=time_s,
                                session_id=session_id, cancelled=count))

    def results(self, runtime):
        states = list(self.sessions.values())
        summary = dict(mobility_checks=sum(s.mobility_check_count for s in states),
                       planned_access_changes=sum(s.planned_change_count for s in states),
                       pending_moves_added=sum(s.planned_change_count for s in states),
                       pending_moves_cancelled=sum(s.pending_moves_cancelled for s in states),
                       max_pending_depth=max((s.max_pending_depth for s in states), default=0),
                       pending_moves_at_observation_end=sum(len(s.pending_moves) for s in states))
        if self.frequency_control:
            summary.update(markov_move_proposals=sum(s.markov_move_proposals for s in states),
                           moves_rejected_min_interval=sum(s.moves_rejected_min_interval for s in states),
                           accepted_planned_moves=sum(s.planned_change_count for s in states))
        rows = []
        for sid, state in sorted(self.sessions.items()):
            session = runtime.sessions[sid]
            rows.append(dict(session_id=sid, initial_access_edge_id=state.initial_access_edge_id,
                             planned_access_edge_id=state.planned_access_edge_id,
                             actual_access_edge_id=session.access_edge_id,
                             execution_edge_id=session.execution_edge_id,
                             arrival_time=state.arrival_time, active=state.active,
                             next_check_index=state.next_check_index,
                             mobility_check_count=state.mobility_check_count,
                             planned_change_count=state.planned_change_count,
                             max_pending_depth=state.max_pending_depth,
                             pending_moves_cancelled=state.pending_moves_cancelled,
                             pending_moves=[asdict(p) for p in state.pending_moves]))
        return dict(summary=summary, sessions=rows, events=deepcopy(self.events))
