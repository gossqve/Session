"""III.B.3 actual Access changes and serial response draining, without KV migration."""
from dataclasses import dataclass, field
from copy import deepcopy
from fractions import Fraction


@dataclass
class HandoverState:
    session_id: str
    active: bool = True
    draining: bool = False
    last_actual_at: float | None = None
    old_tokens: tuple = ()
    arrived: set = field(default_factory=set)
    buffered: list = field(default_factory=list)
    forward_flow_id: str | None = None
    source_edge_id: str | None = None
    target_edge_id: str | None = None
    changes: list = field(default_factory=list)
    draining_delayed: set = field(default_factory=set)


class HandoverRuntime:
    """Controller only. Host owns unique Session/Token/Flow/resource instances."""
    def __init__(self, host):
        if host.mobility is None:
            raise ValueError("Actual Handover requires MobilityRuntime")
        self.host = host
        self.sessions = {}
        self.events = []
        self._scheduled = {}

    def register(self, session):
        self.sessions[session.session_id] = HandoverState(session.session_id)

    def schedule_checks(self):
        now = self.host.time_s
        for sid, state in self.sessions.items():
            if state.active and self.host.mobility.sessions[sid].pending_moves and self._scheduled.get(sid) != now:
                self._scheduled[sid] = now
                self.host.queue.schedule(now, "handover_check", priority=80, session_id=sid)

    def current_event(self, event):
        state = self.sessions.get(event.payload.get("session_id"))
        return state is not None and state.active and self._scheduled.get(state.session_id) == event.time

    def handle_event(self, event):
        sid = event.payload["session_id"]
        self._scheduled.pop(sid, None)
        self.try_switch(sid)

    def hold_wireless(self, sid):
        state = self.sessions[sid]
        return not state.draining and bool(self.host.mobility.sessions[sid].pending_moves)

    def generated(self, token):
        state = self.sessions[token.session_id]
        if state.draining:
            state.buffered.append(token)
        else:
            self.host._send_response(token)

    def at_access(self, token):
        state = self.sessions[token.session_id]
        state.arrived.add(token.token_id)
        if state.draining and token in state.old_tokens:
            self._maybe_forward(state)
        else:
            self.host._queue_wireless(token)

    def forwarded(self, token):
        self.host._log("handover_forward_arrival", token.session_id, token_id=token.token_id)
        self.host._queue_wireless(token)

    def try_switch(self, sid):
        host = self.host
        state = self.sessions[sid]
        pending = host.mobility.sessions[sid].pending_moves
        if not state.active or not pending:
            return
        if state.draining:
            state.draining_delayed.add(pending[0].check_index)
            return
        now = host.time_s
        if state.last_actual_at == now or sid in host._prompt_active or sid in host._downlink_busy:
            return
        if (state.last_actual_at is not None
                and Fraction(str(now)) - Fraction(str(state.last_actual_at))
                < Fraction(str(host.mobility.min_inter_move_interval_s))):
            return
        session = host.runtime.sessions[sid]
        move = pending[0]
        if move.source_edge_id != session.access_edge_id:
            raise RuntimeError("Pending FIFO source differs from actual Access")
        if move.target_edge_id not in host.topology.mobility_adjacency.get(move.source_edge_id, ()):
            raise ValueError("Handover destination is not adjacent")
        host.topology.get_path(move.source_edge_id, move.target_edge_id)
        if (move.target_edge_id, session.execution_edge_id) not in host.topology.validate_serving_pairs():
            raise ValueError("Post-Handover serving pair is not permitted")
        host.topology.validate_access_execution(move.target_edge_id, session.execution_edge_id)
        turn = session.current_turn
        state.old_tokens = tuple(turn.output_tokens[turn.delivered:]) if turn else ()
        state.draining = True
        state.source_edge_id, state.target_edge_id = move.source_edge_id, move.target_edge_id
        state.forward_flow_id = None
        # Freeze the old original producer, preserving all its Byte/path progress.
        host._close_response(sid)
        host._response_flows.pop((sid, turn.index), None)
        host._downlink[sid].clear()
        pending.popleft()
        session.access_edge_id = move.target_edge_id
        state.last_actual_at = now
        record = dict(event="handover_start", time_s=now, session_id=sid,
                      check_index=move.check_index, planned_at=move.planned_at,
                      source_edge_id=move.source_edge_id, target_edge_id=move.target_edge_id,
                      old_token_ids=[t.token_id for t in state.old_tokens],
                      drain_end_s=None, drain_duration_s=None)
        state.changes.append(record)
        self.events.append(record)
        if not state.old_tokens:
            self._drain_end(state)
        else:
            self._maybe_forward(state)

    def _maybe_forward(self, state):
        if (not state.draining or state.forward_flow_id is not None
                or not all(t.token_id in state.arrived for t in state.old_tokens)):
            return
        host = self.host
        turn_index = state.old_tokens[0].turn_index
        key = f"handover:{state.session_id}:{turn_index}:{len(state.changes)}"
        state.forward_flow_id = key
        path = host.topology.get_path(state.source_edge_id, state.target_edge_id)
        found = list(host.network.create(key, "handover", state.session_id, turn_index,
                                        host.time_s, path=path, operation_id=key))
        for token in state.old_tokens:
            found.extend(host.network.supply(key, token.text_bytes, host.time_s, token_id=token.token_id))
        found.extend(host.network.close(key, host.time_s))
        found.extend(host.network.start(key, host.time_s))
        host._transport_notices(host.network, found)

    def delivered(self, token):
        state = self.sessions[token.session_id]
        if state.draining and state.old_tokens:
            turn = self.host.runtime.sessions[token.session_id].current_turn
            if all(t.output_index <= turn.delivered for t in state.old_tokens):
                self._drain_end(state)

    def _drain_end(self, state):
        host = self.host
        state.draining = False
        record = state.changes[-1]
        record["drain_end_s"] = host.time_s
        record["drain_duration_s"] = round(host.time_s - record["time_s"], 12)
        self.events.append(dict(event="handover_drain_end", time_s=host.time_s,
                                session_id=state.session_id))
        buffered, state.buffered = state.buffered, []
        for token in buffered:
            host._send_response(token)
        if host.runtime.sessions[state.session_id].current_turn.generation_complete:
            host._close_response(state.session_id)

    def end_session(self, sid):
        self.sessions[sid].active = False
        self._scheduled.pop(sid, None)

    def results(self):
        intervals = [round(b["time_s"] - a["time_s"], 12) for s in self.sessions.values()
                     for a, b in zip(s.changes, s.changes[1:])]
        return dict(summary=dict(actual_handovers=sum(len(s.changes) for s in self.sessions.values()),
                                 draining_delayed_moves=sum(len(s.draining_delayed) for s in self.sessions.values()),
                                 min_actual_move_interval_s=min(intervals, default=None)),
                    sessions=[dict(session_id=s.session_id, draining=s.draining, active=s.active,
                                   last_actual_at=s.last_actual_at,
                                   buffered_token_ids=[t.token_id for t in s.buffered],
                                   observed_unfinished_drain_s=round(self.host.time_s-s.last_actual_at,12)
                                   if s.draining else None)
                              for _,s in sorted(self.sessions.items())], events=deepcopy(self.events))
