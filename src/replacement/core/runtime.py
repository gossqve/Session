"""Execution-owned runtime and lifecycle transitions."""
from __future__ import annotations
from types import MappingProxyType
from .entities import ModelSpec, EdgeState, SessionState, TurnState, Phase, CommitResult, number

class RuntimeState:
    """Execution-owned state; policies receive observe(runtime), never this object."""

    def __init__(self, models: dict[str, ModelSpec], edges: dict[str, EdgeState]):
        self.models = MappingProxyType(dict(models))
        self.edges = dict(edges)
        self.sessions: dict[str, SessionState] = {}
        self.time_s = 0.0
        for key, model in self.models.items():
            if key != model.model_id:
                raise ValueError("Model registry ID mismatch")
        for key, edge in self.edges.items():
            if key != edge.edge_id or not edge.deployed_models.issubset(self.models):
                raise ValueError("Edge deployment registry mismatch")
        for edge in self.edges.values():
            edge.compute.bind_runtime(self)
            edge.kv.bind_runtime(self)

    def add_session(self, session: SessionState) -> None:
        if session.session_id in self.sessions or session.arrival_time > self.time_s:
            raise ValueError("Duplicate or not-yet-arrived Session")
        if session.model_id not in self.models or session.access_edge_id not in self.edges:
            raise ValueError("Unknown model or Access Edge")
        edge = self.edges.get(session.execution_edge_id)
        if edge is None or session.model_id not in edge.deployed_models:
            raise ValueError("Session model is not deployed at Execution Edge")
        edge.compute.bind_runtime(self)
        edge.kv.bind_runtime(self)
        self.sessions[session.session_id] = session
        edge._residents[session.session_id] = session

    def submit_turn(self, session_id: str, input_tokens: int, time_s: float) -> TurnState:
        session = self.sessions[session_id]
        if session.status != "active" or (session.current_turn and session.current_turn.status != "completed"):
            raise RuntimeError("Session may have only one unfinished Turn")
        number(time_s)
        if time_s < session.arrival_time or time_s != self.time_s:
            raise ValueError("Submit at the current runtime clock after arrival")
        turn = TurnState(session_id, len(session.turns) + 1, input_tokens, time_s,
                         submitted_access_edge_id=session.access_edge_id)
        session.turns.append(turn)
        return turn

    def input_arrived(self, session_id: str) -> None:
        session = self.sessions[session_id]
        turn = session.current_turn
        if session.status != "active" or turn is None or turn.phase != Phase.UPLOAD:
            raise RuntimeError("Input arrival requires the current uploading Turn")
        turn.phase = Phase.PREFILL
        turn.wait_reason = None

    def commit_token(self, session_id: str) -> CommitResult:
        session = self.sessions[session_id]
        return self.edges[session.execution_edge_id].kv.try_commit(session_id)

    def handle_resource_event(self, event):
        edge = self.edges.get(event.payload.get("edge_id"))
        return edge.kv.handle_event(event) if edge else ()

    def deliver_token(self, session_id: str, *, token_id: tuple[str, int, int]) -> None:
        turn = self.sessions[session_id].current_turn
        if turn is None or turn.delivered >= turn.decode_done:
            raise RuntimeError("Cannot deliver an uncommitted output Token")
        token = turn.output_tokens[turn.delivered]
        if token_id != token.token_id:
            raise RuntimeError("Out-of-order, foreign or duplicate output Token identity")
        turn.delivered += 1
        session = self.sessions[session_id]
        self.edges[session.execution_edge_id].kv.record_event(
            "token_delivered", session_id, phase=Phase.DECODE, unit=turn.delivered)

    def finish_turn(self, session_id: str, time_s: float) -> None:
        turn = self.sessions[session_id].current_turn
        if (turn is None or turn.status in ("completed", "failed", "blocked")
                or not turn.generation_complete or turn.delivered != turn.decode_done
                or turn.prefill_done != turn.input_tokens):
            raise RuntimeError("Turn requires legal generation end and full delivery")
        number(time_s)
        if time_s < turn.submitted_at:
            raise ValueError("Delivery precedes submission")
        turn.received_at = time_s
        turn.status = "failed" if turn.completion_reason == "ContextLimit" else "completed"
        turn.phase = Phase.END
        turn.wait_reason = None
        session = self.sessions[session_id]
        self.edges[session.execution_edge_id].kv.record_event(
            "turn_completed" if turn.status == "completed" else "turn_failed", session_id,
            reason=turn.completion_reason)

    def end_session(self, session_id: str, time_s: float, reason: str = "completed") -> int:
        session = self.sessions[session_id]
        edge = self.edges[session.execution_edge_id]
        if session.status in ("ended", "failed"):
            return 0
        if time_s != self.time_s:
            raise ValueError("End Session at the current runtime clock")
        if any(t.session_id == session_id for t in (*edge.running_tasks, *edge.ready_queue)):
            raise RuntimeError("Cannot release a Session with live GPU work")
        if reason == "completed" and (not session.current_turn or session.current_turn.status != "completed"):
            raise RuntimeError("Natural end requires completed final Turn")
        number(time_s)
        session.status = "ended" if reason == "completed" else "failed"
        session.end_time = time_s
        session.termination_reason = reason
        return edge.kv.release_session(session_id)
