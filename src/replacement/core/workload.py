"""Private immutable workload generation and offline evaluation data.

Never pass this driver, its plan or the full input config to an online policy.
Static sample validation here is offline; it does not forecast Context/KV fit.
"""
from dataclasses import dataclass

from .entities import SessionState, identifier, integer, number


@dataclass(frozen=True, slots=True)
class TurnPlan:
    input_tokens: int
    hidden_output_tokens: int


@dataclass(frozen=True, slots=True)
class SessionPlan:
    session_id: str
    model_id: str
    arrival_time: float
    access_edge_id: str
    execution_edge_id: str
    turns: tuple[TurnPlan, ...]
    wireless_up_bits_per_second: float = 80
    wireless_down_bits_per_second: float = 80
    text_bytes_per_token: int = 1


@dataclass(frozen=True, slots=True)
class WorkloadPlan:
    sessions: tuple[SessionPlan, ...]
    seed: int = 0
    scenario: str = "unnamed"


@dataclass(frozen=True, slots=True)
class RevealedRequest:
    input_tokens: int


class WorkloadDriver:
    def __init__(self, plan: WorkloadPlan):
        self._plan = plan
        self._sessions = {}
        for session in plan.sessions:
            for value in (session.session_id, session.model_id, session.access_edge_id, session.execution_edge_id):
                identifier(value)
            number(session.arrival_time)
            number(session.wireless_up_bits_per_second, positive=True)
            number(session.wireless_down_bits_per_second, positive=True)
            integer(session.text_bytes_per_token)
            if session.session_id in self._sessions or not session.turns:
                raise ValueError("Duplicate or empty Session plan")
            for turn in session.turns:
                integer(turn.input_tokens, minimum=0)
                integer(turn.hidden_output_tokens, minimum=0)
            self._sessions[session.session_id] = session

    @classmethod
    def from_s0_config(cls, config: dict):
        session = config["session"]
        cls._validate_turn_schema((session,))
        if "priority" in session:
            raise ValueError("Session priority was removed; remove the legacy field")
        turns = tuple(TurnPlan(t["input_tokens"], t["output_tokens"])
                      for t in session["turns"])
        net = config["network"]
        plan = SessionPlan(session["id"], session["model_id"], session.get("arrival_time", 0),
                           session["access_edge_id"], session["execution_edge_id"], turns,
                           net["wireless_up_bits_per_second"], net["wireless_down_bits_per_second"],
                           net["text_bytes_per_token"])
        return cls(WorkloadPlan((plan,), config.get("seed", 0), config.get("scenario", "unnamed")))

    @staticmethod
    def _validate_turn_schema(sessions):
        for session in sessions:
            for turn in session["turns"]:
                if "access_edge_id" in turn:
                    raise ValueError("per-Turn access_edge_id is forbidden; Access is a Session state")

    def arrival(self, session_id: str) -> SessionState:
        s = self._sessions[session_id]
        return SessionState(s.session_id, s.model_id, s.arrival_time, s.access_edge_id, s.execution_edge_id,
                            text_bytes_per_token=s.text_bytes_per_token)

    @classmethod
    def from_serving_config(cls, config):
        cls._validate_turn_schema(config["sessions"])
        plans = []
        for s in config["sessions"]:
            if "priority" in s:
                raise ValueError("Session priority was removed")
            net = {**config["network"], **s.get("network", {})}
            number(s.get("arrival_time", 0))
            plans.append(SessionPlan(
                s["id"], s["model_id"], round(s.get("arrival_time", 0), 12),
                s["access_edge_id"], s["execution_edge_id"],
                tuple(TurnPlan(t["input_tokens"], t["output_tokens"]) for t in s["turns"]),
                net["wireless_up_bits_per_second"], net["wireless_down_bits_per_second"], net["text_bytes_per_token"]))
        if not plans:
            raise ValueError("Serving workload needs at least one Session")
        return cls(WorkloadPlan(tuple(plans), config.get("seed", 0), config.get("scenario", "unnamed")))

    def arrival_events(self):
        """Private execution scheduling only; not an online interface."""
        return tuple((s.arrival_time, s.session_id) for s in self._plan.sessions)

    def network_at_arrival(self, session_id):
        s = self._sessions[session_id]
        return {"up": s.wireless_up_bits_per_second, "down": s.wireless_down_bits_per_second}

    def reveal_turn(self, session_id: str, index: int) -> RevealedRequest:
        """Reveal current input only; Mobility is an independent future process."""
        turn = self._sessions[session_id].turns[index - 1]
        return RevealedRequest(turn.input_tokens)

    def has_output(self, session_id: str, index: int, generated: int) -> bool:
        """Private generation-boundary decision, never a remaining-output count."""
        return generated < self._sessions[session_id].turns[index - 1].hidden_output_tokens

    def has_next_turn(self, session_id: str, index: int) -> bool:
        return index < len(self._sessions[session_id].turns)

    def evaluation_metadata(self) -> dict:
        """Offline final reporting only, never part of RuntimeState/observation."""
        return {"scenario": self._plan.scenario, "seed": self._plan.seed,
                "planned_turns": sum(len(s.turns) for s in self._plan.sessions)}
