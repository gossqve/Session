"""S0 only: one edge, one session, zero idle, serial GPU computation.

No mobility, wired transfer, GPU competition, KV migration, SLA, or policy.
The planned future workload is private to the simulator, not a policy observation.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

from .events import EventQueue


@dataclass
class TurnState:
    idx: int
    input_tokens: int
    output_tokens: int
    submitted_at: float
    prefill_done: int = 0
    decode_done: int = 0
    delivered: int = 0
    decoding_complete: bool = False
    received_at: float | None = None


class S0Simulator:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self._validate(config)
        self.edge = config["edge"]
        self.model = config["model"]
        self.net = config["network"]
        self.session = config["session"]
        self.queue = EventQueue()
        self.time = 0.0
        self.context_tokens = 0
        self.authoritative_kv_bytes = 0
        self.peak_kv_bytes = 0
        self.active_turn: TurnState | None = None
        self.finished_turns: list[dict[str, Any]] = []
        self.events: list[dict[str, Any]] = []
        self.downlink_pending: deque[int] = deque()
        self.downlink_busy = False
        self.completed = False
        self.queue.schedule(0, "submit_turn", priority=30, index=0)

    @staticmethod
    def _validate(c: dict[str, Any]) -> None:
        for key in ("edge", "model", "network", "session"):
            if key not in c:
                raise ValueError(f"Missing {key}")
        e, m, n, s = c["edge"], c["model"], c["network"], c["session"]
        if s["model_id"] != m["id"]:
            raise ValueError("Fixed session model must match deployed model")
        if s["access_edge_id"] != e["id"] or s["execution_edge_id"] != e["id"]:
            raise ValueError("S0 only supports same access and execution edge")
        if s["priority"] not in ("H", "L"):
            raise ValueError("Session priority must be H or L")
        for value in (e["gpu_work_per_second"], n["wireless_up_bits_per_second"],
                      n["wireless_down_bits_per_second"]):
            if value <= 0:
                raise ValueError("Rates must be positive")
        for value in (m["prefill_work_per_token"], m["decode_work_per_token"]):
            if value <= 0:
                raise ValueError("Token work must be positive")
        for value in (e["kv_capacity_bytes"], m["kv_bytes_per_token"],
                      m["context_window_tokens"], m["output_limit_per_turn"],
                      n["text_bytes_per_token"]):
            if not isinstance(value, int) or value <= 0:
                raise ValueError("Capacity, token limits, and bytes/token must be positive integers")
        if not s.get("turns"):
            raise ValueError("S0 needs at least one turn")
        total_context = 0
        for t in s["turns"]:
            ni, no = t["input_tokens"], t["output_tokens"]
            if (not isinstance(ni, int) or not isinstance(no, int)
                    or ni < 0 or no < 0 or no > m["output_limit_per_turn"]):
                raise ValueError("S0 expects nonnegative integer tokens within output limit")
            total_context += ni + no
        # S0 normal-run testing only. Later stages will implement runtime ContextLimit/KVBlocked.
        if total_context > m["context_window_tokens"]:
            raise ValueError("S0 workload exceeds cumulative context window")
        if total_context * m["kv_bytes_per_token"] > e["kv_capacity_bytes"]:
            raise ValueError("S0 workload exceeds fixed KV capacity")

    def _log(self, kind: str, **detail: Any) -> None:
        self.events.append({"seq": len(self.events), "time_s": round(self.time, 12),
                            "event": kind, "session_id": self.session["id"], **detail})

    def _duration_gpu(self, work_per_token: float) -> float:
        return work_per_token / self.edge["gpu_work_per_second"]

    def _commit_kv(self, origin: str) -> None:
        self.context_tokens += 1
        self.authoritative_kv_bytes += self.model["kv_bytes_per_token"]
        self.peak_kv_bytes = max(self.peak_kv_bytes, self.authoritative_kv_bytes)
        assert self.context_tokens <= self.model["context_window_tokens"]
        assert self.authoritative_kv_bytes <= self.edge["kv_capacity_bytes"]
        self._log("kv_commit", origin=origin, context_tokens=self.context_tokens,
                  authoritative_kv_bytes=self.authoritative_kv_bytes)

    def _submit_turn(self, index: int) -> None:
        plan = self.session["turns"][index]
        self.active_turn = TurnState(index, plan["input_tokens"], plan["output_tokens"], self.time)
        self._log("turn_submit", turn=index + 1)
        duration = plan["input_tokens"] * self.net["text_bytes_per_token"] * 8 / self.net["wireless_up_bits_per_second"]
        self._log("upload_start", turn=index + 1, bytes=plan["input_tokens"] * self.net["text_bytes_per_token"])
        self.queue.schedule(self.time + duration, "upload_done", turn=index + 1)

    def _upload_done(self) -> None:
        turn = self._turn
        self._log("upload_done", turn=turn.idx + 1)
        self._schedule_prefill_or_decode()

    @property
    def _turn(self) -> TurnState:
        assert self.active_turn is not None
        return self.active_turn

    def _schedule_prefill_or_decode(self) -> None:
        t = self._turn
        if t.prefill_done < t.input_tokens:
            self.queue.schedule(self.time + self._duration_gpu(self.model["prefill_work_per_token"]),
                                "prefill_token_done")
        else:
            self._log("prefill_complete", turn=t.idx + 1)
            self._schedule_decode_or_finish()

    def _prefill_token_done(self) -> None:
        t = self._turn
        t.prefill_done += 1
        self._log("prefill_token_done", turn=t.idx + 1, number=t.prefill_done)
        self._commit_kv("prefill")
        self._schedule_prefill_or_decode()

    def _schedule_decode_or_finish(self) -> None:
        t = self._turn
        if t.decode_done < t.output_tokens:
            self.queue.schedule(self.time + self._duration_gpu(self.model["decode_work_per_token"]),
                                "decode_token_done")
        else:
            t.decoding_complete = True
            self._log("decode_complete", turn=t.idx + 1)
            if t.output_tokens == 0 or t.delivered == t.output_tokens:
                self._finish_turn()

    def _decode_token_done(self) -> None:
        t = self._turn
        t.decode_done += 1
        self._log("decode_token_done", turn=t.idx + 1, number=t.decode_done)
        self._commit_kv("decode")
        self.downlink_pending.append(t.decode_done)
        self._try_start_downlink()
        self._schedule_decode_or_finish()

    def _try_start_downlink(self) -> None:
        if self.downlink_busy or not self.downlink_pending:
            return
        num = self.downlink_pending.popleft()
        self.downlink_busy = True
        t = self._turn
        self._log("downlink_start", turn=t.idx + 1, number=num)
        delay = 8 * self.net["text_bytes_per_token"] / self.net["wireless_down_bits_per_second"]
        self.queue.schedule(self.time + delay, "downlink_done", number=num)

    def _downlink_done(self, number: int) -> None:
        t = self._turn
        self.downlink_busy = False
        t.delivered += 1
        self._log("downlink_done", turn=t.idx + 1, number=number)
        if t.decoding_complete and t.delivered == t.output_tokens:
            self._finish_turn()
        else:
            self._try_start_downlink()

    def _finish_turn(self) -> None:
        t = self._turn
        if t.received_at is not None:
            raise RuntimeError("Turn finished twice")
        if t.delivered != t.output_tokens or not t.decoding_complete:
            raise RuntimeError("Cannot finish until all output tokens arrive at UE")
        t.received_at = self.time
        latency = round(self.time - t.submitted_at, 12)
        self.finished_turns.append({"session_id": self.session["id"], "turn": t.idx + 1,
                                    "submitted_at_s": round(t.submitted_at, 12),
                                    "received_at_s": round(self.time, 12),
                                    "e2e_s": latency, "input_tokens": t.input_tokens,
                                    "output_tokens": t.output_tokens, "status": "completed"})
        self._log("turn_complete", turn=t.idx + 1, e2e_s=latency)
        next_index = t.idx + 1
        self.active_turn = None
        if next_index == len(self.session["turns"]):
            self._log("session_end", final_context_tokens=self.context_tokens,
                      final_authoritative_kv_bytes=self.authoritative_kv_bytes)
            self.authoritative_kv_bytes = 0
            self._log("kv_release", authoritative_kv_bytes=0)
            self.completed = True
        else:
            # The new Turn submits at exactly the time the previous response reaches the UE.
            self.queue.schedule(self.time, "submit_turn", priority=30, index=next_index)

    def run(self, max_events: int = 100000) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
        handlers = {
            "submit_turn": lambda p: self._submit_turn(p["index"]),
            "upload_done": lambda p: self._upload_done(),
            "prefill_token_done": lambda p: self._prefill_token_done(),
            "decode_token_done": lambda p: self._decode_token_done(),
            "downlink_done": lambda p: self._downlink_done(p["number"]),
        }
        count = 0
        while self.queue:
            if count >= max_events:
                raise RuntimeError("Event safety limit reached")
            e = self.queue.pop()
            if e.time < self.time:
                raise RuntimeError("Time moved backwards")
            self.time = e.time
            handlers[e.kind](e.payload)
            count += 1
        planned = len(self.session["turns"])
        finished = len(self.finished_turns)
        summary = {
            "stage": "S0", "scenario": self.config.get("scenario", "unnamed"),
            "seed": self.config.get("seed", 0),
            "planned_turns": planned, "completed_turns": finished,
            "completion_rate": finished / planned,
            "mean_full_turn_e2e_s": (round(sum(t["e2e_s"] for t in self.finished_turns) / planned, 12)
                                     if finished == planned else None),
            "observation_end_s": round(self.time, 12),
            "final_context_tokens": self.context_tokens,
            "peak_authoritative_kv_bytes": self.peak_kv_bytes,
            "released_authoritative_kv_bytes": self.authoritative_kv_bytes,
            "migration_kv_bytes": 0, "shadow_byte_seconds": 0,
        }
        return summary, self.finished_turns, self.events
