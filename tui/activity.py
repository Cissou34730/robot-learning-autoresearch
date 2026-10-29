"""Live progress, phase selection and presentation clocks without terminal dependencies."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from runner.event_contract import PREPARATION_SESSION
from tui.observations import Observation

Phase = Literal[
    "official", "training", "evaluating", "coding", "preparing", "pi", "none"
]
RUNNER_HEARTBEAT_SECONDS = 15.0
LIVENESS_SECONDS = 20 * RUNNER_HEARTBEAT_SECONDS
PROGRESS_STALE_SECONDS = 20 * RUNNER_HEARTBEAT_SECONDS


def _now() -> datetime:
    return datetime.now(tz=UTC)


def parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


@dataclass(frozen=True)
class TrainingProgress:
    operation_id: str
    attempt: str = "unknown"
    steps: int | None = None
    target: int | None = None
    elapsed_seconds: float | None = None
    reward: float | None = None
    success: float | str | None = None
    stale: bool = False
    eta_seconds: float | None = None


def training_eta_seconds(progress: dict, previous: dict | None = None) -> float | None:
    """Prefer the producer's ETA; estimate older feeds only from actual advancement."""

    def number(value):
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
        )

    eta = progress.get("eta_seconds")
    if number(eta) and eta >= 0:
        return float(eta)
    steps, target = progress.get("steps"), progress.get("target")
    if not number(steps) or not number(target) or target <= 0:
        return None
    if steps >= target:
        return 0.0
    previous = previous or {}
    if progress.get("operation_id") != previous.get("operation_id") or (
        progress.get("attempt") or "unknown"
    ) != (previous.get("attempt") or "unknown"):
        return None
    before, elapsed, prior_elapsed = (
        previous.get("steps"),
        progress.get("elapsed_seconds"),
        previous.get("elapsed_seconds"),
    )
    if (
        number(before)
        and number(elapsed)
        and number(prior_elapsed)
        and steps > before
        and elapsed > prior_elapsed
    ):
        return (target - steps) * (elapsed - prior_elapsed) / (steps - before)
    return None


@dataclass(frozen=True)
class EvaluationProgress:
    operation_id: str
    instrument: str = ""
    official: bool = False
    panel_index: int | None = None
    panel_total: int | None = None
    completed_panels: int = 0
    episode_label: str | None = None
    episodes: int | None = None
    episodes_total: int | None = None
    elapsed_seconds: float | None = None
    stale: bool = False


class LiveActivity:
    def __init__(self, clock: Callable[[], datetime] = _now) -> None:
        self.clock = clock
        self.training: dict | None = None
        self.evaluation: dict | None = None
        self.stage_started: datetime | None = None
        self.last_activity = ""
        self.last_liveness: datetime | None = None
        self.process_running: bool | None = None
        self.paused_at: datetime | None = None
        self.paused_intervals: list[tuple[datetime, datetime]] = []
        self.ended_at: datetime | None = None
        self._finished: set[str] = set()

    def ingest(self, event: Observation) -> None:
        kind, fields = event.kind, event.fields
        operation = event.operation_id or str(
            fields.get("operation_id") or fields.get("id") or ""
        )
        if kind == "liveness":
            self.last_liveness = event.ts or self.clock()
        elif kind == "session_start":
            self.stage_started = (
                parse_timestamp(fields.get("stage_started_at")) or event.ts
            )
        elif kind == "activity" and fields.get("label"):
            self.last_activity = str(fields["label"]).replace("\r", "")
        elif kind in {"operation_completed", "operation_failed"}:
            if fields.get("status") != "interrupted":
                self._finished.add(operation)
            if self.training and self.training.get("operation_id") == operation:
                self.training = None
            if self.evaluation and self.evaluation.get("operation_id") == operation:
                self.evaluation = None
        elif kind == "training_progress" and operation not in self._finished:
            if self._older(event, self.training):
                return
            sample = {**fields, "operation_id": operation}
            self.training = {
                **sample,
                "attempt": fields.get("attempt") or "unknown",
                "eta_seconds": training_eta_seconds(sample, self.training),
                "reward": fields.get("ep_rew_mean"),
                "success": fields.get("scenario_metric")
                or fields.get("training_success"),
                "last_ts": event.ts or self.clock(),
            }
        elif kind == "eval_progress" and operation not in self._finished:
            if self._older(event, self.evaluation):
                return
            self.evaluation = {
                **fields,
                "operation_id": operation,
                "last_ts": event.ts or self.clock(),
            }

    @staticmethod
    def _older(event: Observation, previous: dict | None) -> bool:
        return bool(
            previous
            and previous.get("operation_id") == event.operation_id
            and event.ts is not None
            and isinstance(previous.get("last_ts"), datetime)
            and event.ts < previous["last_ts"]
        )

    def phase(
        self,
        operation_id: str,
        kind: str,
        status: str,
        session_id: str,
        session_closed: bool,
        coding_open: bool,
    ) -> Phase:
        if self.evaluation and self.evaluation.get("official"):
            return "official"
        if status in {"running", "requested"}:
            if operation_id == "official":
                return "official"
            if kind == "training":
                return "training"
            if kind == "measurement":
                return "evaluating"
        if coding_open:
            return "coding"
        if session_id and not session_closed:
            return "preparing" if session_id == PREPARATION_SESSION else "pi"
        return "none"

    def process_observed(self) -> bool:
        stamp = self.last_liveness
        if stamp is None:
            return False
        return (self.clock() - stamp).total_seconds() <= LIVENESS_SECONDS

    def clock_end(
        self, started_at: datetime | None, ended_at: datetime | None = None
    ) -> datetime:
        end = ended_at or self.ended_at or self.paused_at or self.clock()
        if started_at is None:
            return end
        paused = sum(
            max(0.0, (min(stop, end) - max(start, started_at)).total_seconds())
            for start, stop in self.paused_intervals
        )
        return end - timedelta(seconds=paused)

    def advance(self, state: dict) -> float:
        """Seconds the Runner has worked since its last sample.

        The Runner publishes counters, not a clock; elapsed time and ETA run
        locally between samples. Nothing advances while the process is paused
        or the samples are stale.
        """
        last = state.get("last_ts")
        if (
            not isinstance(last, datetime)
            or self.paused_at is not None
            or self.progress_stale(state)
        ):
            return 0.0
        return float(int(max(0.0, (self.clock_end(last) - last).total_seconds())))

    def training_progress(self) -> TrainingProgress | None:
        state = self.training
        if not state:
            return None
        advance = self.advance(state)
        elapsed = state.get("elapsed_seconds")
        if isinstance(elapsed, (int, float)) and not isinstance(elapsed, bool):
            elapsed += advance
        eta = state.get("eta_seconds")
        if isinstance(eta, (int, float)) and not isinstance(eta, bool):
            eta = max(0.0, eta - advance)
        return TrainingProgress(
            operation_id=state.get("operation_id") or "training",
            attempt=str(state.get("attempt") or "unknown"),
            steps=state.get("steps"),
            target=state.get("target"),
            elapsed_seconds=elapsed,
            reward=state.get("reward"),
            success=state.get("success"),
            stale=self.progress_stale(state),
            eta_seconds=eta
            if self.paused_at is None and not self.progress_stale(state)
            else None,
        )

    def evaluation_progress(self) -> EvaluationProgress | None:
        state = self.evaluation
        if not state:
            return None
        elapsed = state.get("elapsed_seconds")
        if isinstance(elapsed, (int, float)) and not isinstance(elapsed, bool):
            elapsed += self.advance(state)
        return EvaluationProgress(
            operation_id=state.get("operation_id") or "evaluation",
            instrument=state.get("instrument") or "",
            official=bool(state.get("official")),
            panel_index=state.get("panel_index"),
            panel_total=state.get("panel_total"),
            completed_panels=state.get("completed_panels") or 0,
            episodes=state.get("episodes"),
            episodes_total=state.get("episodes_total"),
            elapsed_seconds=elapsed,
            stale=self.progress_stale(state),
        )

    def progress_stale(self, state: dict) -> bool:
        last = state.get("last_ts")
        if not isinstance(last, datetime):
            return True
        return (self.clock() - last).total_seconds() > PROGRESS_STALE_SECONDS

    def set_process_running(self, running: bool) -> bool:
        """Presentation-only clock state, supplied by the owning controller."""
        if running == self.process_running or (
            not running and self.process_running is None
        ):
            return False
        now = self.clock()
        if running:
            if self.paused_at is not None:
                self.paused_intervals.append((self.paused_at, now))
                self.training = None
                self.evaluation = None
            self.paused_at = None
        elif self.process_running is True:
            self.paused_at = now
        self.process_running = running
        return True
