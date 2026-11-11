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
        self._generated = False
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
    def from_serving_config(cls, config, *, plan=None):
        spec = config.get("workload", {})
        if not isinstance(spec, dict) or spec.get("mode", "static") not in ("static", "poisson"):
            raise ValueError("workload.mode must be static or poisson")
        if spec.get("mode") == "poisson":
            if "sessions" in config:
                raise ValueError("Poisson input cannot also declare static sessions")
            from .workload_generation import WorkloadGenerator
            generator = WorkloadGenerator(config)
            generator.validate()
            plan = generator.generate() if plan is None else plan
            if not isinstance(plan, WorkloadPlan) or plan.seed != config.get("seed", 0):
                raise ValueError("Reusable WorkloadPlan must use the common seed")
            driver = cls(plan)
            eligible = {e["id"] for e in config["edges"] if spec["model_id"] in e["deployed_models"]}
            for session in plan.sessions:
                if (session.model_id != spec["model_id"] or session.access_edge_id not in eligible
                        or session.execution_edge_id != session.access_edge_id
                        or not 0 < session.arrival_time <= spec["arrival_horizon_s"]):
                    raise ValueError("Reusable Session has invalid initial binding or arrival")
                if not spec["turn_count"]["min"] <= len(session.turns) <= spec["turn_count"]["max"]:
                    raise ValueError("Reusable Session Turn count is outside configured bounds")
                for turn in session.turns:
                    if (not spec["input_tokens"]["min"] <= turn.input_tokens <= spec["input_tokens"]["max"]
                            or not spec["output_tokens"]["min"] <= turn.hidden_output_tokens <= spec["output_tokens"]["max"]):
                        raise ValueError("Reusable Turn lengths are outside configured bounds")
            driver._generated = True
            return driver
        if plan is not None:
            raise ValueError("Explicit reusable plans require poisson workload mode")
        cls._validate_turn_schema(config["sessions"])
        plans = []
        for s in config["sessions"]:
            if "priority" in s:
                raise ValueError("Session priority was removed")
            overrides = s.get("network", {})
            net = {**config["network"], **overrides}
            # A per-Session direction can replace the global representation;
            # two representations in the same scope remain an error.
            for direction in ("up", "down"):
                effective = f"wireless_{direction}_bits_per_second"
                physical = f"wireless_{direction}"
                if effective in config["network"] and physical in config["network"]:
                    raise ValueError("Global wireless direction has two rate representations")
                if physical in overrides and effective not in overrides:
                    net.pop(effective, None)
                if effective in overrides and physical not in overrides:
                    net.pop(physical, None)
            from ..network.wireless import resolve_wireless_rate
            net["wireless_up_bits_per_second"] = resolve_wireless_rate(net, "up")
            net["wireless_down_bits_per_second"] = resolve_wireless_rate(net, "down")
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

    @property
    def generated(self):
        return self._generated

    def mobility_initial_states(self):
        """Private static reachability validation, not an online observation."""
        return tuple(dict(id=s.session_id, arrival_time=s.arrival_time,
                          access_edge_id=s.access_edge_id, execution_edge_id=s.execution_edge_id)
                     for s in self._plan.sessions)

    def evaluation_workload(self, runtime):
        """Offline report only. Never pass this full plan or statistics to policy."""
        from .workload_generation import workload_to_dict, workload_hash
        sessions = list(runtime.sessions.values())
        ended = [s for s in sessions if s.status == "ended"]
        context = [s for s in sessions if s.termination_reason == "ContextLimit"]
        failed = [s for s in sessions if s.status == "failed"]
        exceeded = sum(sum(t.input_tokens + t.hidden_output_tokens for t in s.turns)
                       > runtime.models[s.model_id].context_window_tokens for s in self._plan.sessions)
        lifetimes = [dict(session_id=s.session_id, arrival_time=s.arrival_time,
                          end_time=s.end_time, lifetime_s=round(s.end_time-s.arrival_time,12)
                          if s.end_time is not None else None,
                          observed_lifetime_s=round((s.end_time if s.end_time is not None
                                                   else runtime.time_s)-s.arrival_time,12),
                          context_tokens=s.context_tokens, termination_reason=s.termination_reason)
                     for s in sessions]
        total = len(sessions)
        return dict(plan=workload_to_dict(self._plan), workload_hash=workload_hash(self._plan),
                    statistics=dict(planned_sessions=len(self._plan.sessions), arrived_sessions=total,
                                    completed_sessions=len(ended), legally_terminated_sessions=len(failed),
                                    unfinished_sessions=total-len(ended)-len(failed),
                                    planned_context_exceedances=exceeded, context_limit_sessions=len(context),
                                    context_limit_ratio=len(context)/total if total else None,
                                    completed_session_ratio=len(ended)/total if total else None,
                                    kv_blocked_ratio=sum(any(t.block_count for t in s.turns) for s in sessions)/total if total else None,
                                    planned_token_totals=[dict(session_id=s.session_id,
                                        tokens=sum(t.input_tokens+t.hidden_output_tokens for t in s.turns))
                                        for s in self._plan.sessions], session_lifetimes=lifetimes))
