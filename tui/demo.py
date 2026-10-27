"""Synthetic campaign material for the report demo and headless tests.

Nothing here reads or writes campaign files. The fixtures mirror the
publication shapes of `research_state.json`, `results.jsonl` and
`session_usage/*.jsonl`, so the projection logic is exercised against the
recorded schema rather than hand-built display rows.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tui.observations import Observation

DEMO_CAMPAIGN_ID = "90c9d0aa-demo-campaign-id-4aa2b8d0b6fb"


def demo_clock() -> tuple[datetime, datetime, datetime]:
    """anchor, service announced attach note in (anchor, session start, now)."""
    now = datetime.now(tz=UTC)
    started = now - timedelta(hours=2, minutes=14)
    stage_start = now - timedelta(minutes=18)
    return started, stage_start, now


def demo_state(now: datetime, started: datetime) -> dict:
    return {
        "schema_version": 6,
        "campaign": {
            "id": DEMO_CAMPAIGN_ID,
            "started_at": started.isoformat(),
            "max_inquiries": 15,
        },
        "human_goal": (
            "Reach at least 196 successes on the official 200-episode panel (98%), "
            "with an uninterrupted 100-step hold per success."
        ),
        "scientific_model": {"status": "active"},
        "active_inquiry": "I3",
        "counters": {
            "session": 7,
            "inquiry": 3,
            "training": 4,
            "measurement": 5,
            "event": 13,
        },
        "scientific_session": {
            "id": "S7",
            "kind": "inquiry",
            "inquiry_id": "I3",
            "backend_session_id": "9d2c-demo-backend-session-id-772c400a91e0",
        },
        "pi_checkpoint": {
            "session_id": "S6",
            "current_synthesis": (
                "The policy reaches the target, but its hold behavior remains "
                "unreliable. The existing measurements do not establish whether "
                "slower convergence or limited control authority explains the "
                "remaining failures."
            ),
            "next_question": "",
        },
        "model_roles": {
            "best_known": "T2:checkpoint-90000",
            "working": "T4:checkpoint-120000",
            "retained": {"baseline": "T1:checkpoint-60000"},
        },
        "candidates": {
            f"T{n}:checkpoint-{steps}": {
                "id": f"T{n}:checkpoint-{steps}",
                "training_steps": steps,
            }
            for n, steps in ((2, 90000), (4, 120000), (1, 60000))
        },
        "operation_events": [],
        "pending_operation": {
            "id": "M6",
            "kind": "measurement",
            "session_id": "S7",
            "inquiry_id": "I3",
            "request": {
                "measurements": [
                    {"candidate": "T4:checkpoint-120000", "episodes": 100},
                ]
            },
            "progress": None,
        },
        "terminal_state": None,
        "official_assessment": None,
        "last_verdict": None,
    }


def demo_records(now: datetime) -> list[dict]:
    def at(minutes_ago: int) -> str:
        return (now - timedelta(minutes=minutes_ago)).isoformat()

    T4_id = "T4"
    return [
        {
            "id": T4_id,
            "kind": "training",
            "status": "completed",
            "session_id": "S6",
            "inquiry_id": "I2",
            "completed_at": at(152),
            "error": None,
            "request": {"steps": 120000, "initialization": "continue", "seed": 21},
            "result": {
                "completed_steps": 120832,
                "requested_steps": 120000,
                "candidates": ["T4:checkpoint-120000", "T4:checkpoint-100000"],
                "learning_dynamics": [
                    {
                        "candidate": "T4:checkpoint-120000",
                        "ep_rew_mean": 86.3,
                        "training_steps": 120000,
                        "training_success": 0.97,
                    },
                    {
                        "candidate": "T4:checkpoint-100000",
                        "ep_rew_mean": 84.1,
                        "training_steps": 100000,
                        "training_success": 0.94,
                    },
                ],
            },
        },
        {
            "id": "M5",
            "kind": "measurement",
            "status": "completed",
            "session_id": "S6",
            "inquiry_id": "I2",
            "completed_at": at(96),
            "error": None,
            "request": {},
            "result": {
                "instrument": "task_reference",
                "measurements": [
                    {
                        "candidate_id": "T2:checkpoint-90000",
                        "instrument": "task_reference",
                        "metrics": {
                            "success_percent": 94.0,
                            "episodes": 160,
                            "episodes_total": 160,
                            "official_benchmark": False,
                        },
                    },
                    {
                        "candidate_id": "T1:checkpoint-60000",
                        "instrument": "task_reference",
                        "metrics": {
                            "success_percent": 89.0,
                            "episodes": 160,
                            "episodes_total": 160,
                            "official_benchmark": False,
                        },
                    },
                ],
            },
        },
        {
            "id": "E12",
            "kind": "model_role",
            "status": "completed",
            "session_id": "S6",
            "completed_at": at(94),
            "error": None,
            "request": {
                "action": "set_best_known",
                "candidate": "T2:checkpoint-90000",
                "evidence": ["T2", "M5"],
            },
            "result": {"status": "assigned"},
        },
        {
            "id": "E13",
            "kind": "checkpoint",
            "status": "completed",
            "session_id": "S6",
            "completed_at": at(93),
            "error": None,
            "request": {},
            "result": {"status": "checkpointed"},
        },
        {
            "id": "E14",
            "kind": "inquiry",
            "status": "completed",
            "session_id": "S7",
            "inquiry_id": "I3",
            "completed_at": at(21),
            "error": None,
            "request": {
                "action": "open",
                "question": (
                    "Does longer settling improve hold stability, or do the "
                    "remaining failures require a different control intervention?"
                ),
            },
            "result": {"inquiry_id": "I3", "status": "completed"},
        },
    ]


def demo_usage_rows(now: datetime) -> list[dict]:
    def recorded(minutes_ago: int) -> str:
        return (now - timedelta(minutes=minutes_ago)).isoformat()

    return [
        {
            "campaign_id": DEMO_CAMPAIGN_ID,
            "role": "pi",
            "provider": "github-copilot",
            "session_id": "4100-demo-earlier-session-1a2b3c4d5e6f",
            "phase": "inquiry",
            "recorded_at": recorded(150),
            "input_tokens": 4_200_000,
            "output_tokens": 143_000,
            "aiu": 4.2,
        },
        {
            "campaign_id": DEMO_CAMPAIGN_ID,
            "role": "scientific_coder",
            "provider": "github-copilot",
            "session_id": "4100-demo-earlier-session-1a2b3c4d5e6f",
            "phase": "inquiry",
            "recorded_at": recorded(120),
            "input_tokens": 900_000,
            "output_tokens": 61_000,
            "aiu": 1.4,
        },
        {
            "campaign_id": DEMO_CAMPAIGN_ID,
            "role": "scientific_reviewer",
            "provider": "github-copilot",
            "session_id": "4100-demo-earlier-session-1a2b3c4d5e6f",
            "phase": "inquiry",
            "recorded_at": recorded(119),
            "input_tokens": 210_000,
            "output_tokens": 12_000,
            "aiu": 0.7,
        },
        {
            "campaign_id": DEMO_CAMPAIGN_ID,
            "role": "validation",
            "provider": "external",
            "session_id": "4100-demo-earlier-session-1a2b3c4d5e6f",
            "phase": "inquiry",
            "recorded_at": recorded(90),
            "input_tokens": 80_000,
            "output_tokens": 4_000,
            "aiu": None,
        },
    ]


_PI_MESSAGE = (
    "The working candidate's remaining hold failures look consistent with slow "
    "convergence after entry, not a control authority limit.\n\n"
    "I will measure T4:checkpoint-120000 and the retained T1 baseline on the same "
    "task reference panel. A higher training reward alone does not establish "
    "better development performance, so the measurement decides the comparison."
)


def _past_events(started: datetime, now: datetime) -> list[Observation]:
    """The demo campaign's earlier journal: preparation, a closed session S6 with
    its inquiry and operations, and the open session S7 with a pending
    measurement. It tells the same story as ``demo_state``."""
    counter = iter(range(1, 1000))

    def ago(minutes: float) -> datetime:
        return now - timedelta(minutes=minutes)

    def event(kind: str, stamp: datetime, /, **identity_and_fields) -> Observation:
        identity = {
            name: identity_and_fields.pop(name)
            for name in ("session_id", "operation_id", "inquiry_id", "attempt", "actor")
            if name in identity_and_fields
        }
        return Observation(
            kind,
            stamp,
            identity_and_fields,
            event_id=f"demo-past:{next(counter)}",
            **identity,
        )

    long_ago = started + timedelta(minutes=1)
    return [
        event("campaign_started", started, summary="goal-centered research"),
        event(
            "session_start",
            long_ago,
            session_id="preparation",
            attempt="prep-1",
            stage="campaign preparation",
        ),
        event(
            "scientific_model_validated",
            long_ago + timedelta(minutes=9),
            session_id="preparation",
            path="pi_workspace/scientific_model.md",
        ),
        event("session_started", ago(170), session_id="S6", id="S6", kind="inquiry"),
        event(
            "inquiry_opened",
            ago(169),
            session_id="S6",
            inquiry_id="I2",
            question="Which candidate converges fastest?",
        ),
        event(
            "operation_completed",
            ago(152),
            session_id="S6",
            inquiry_id="I2",
            operation_id="T4",
            kind="training",
            status="completed",
        ),
        event(
            "operation_completed",
            ago(96),
            session_id="S6",
            inquiry_id="I2",
            operation_id="M5",
            kind="measurement",
            status="completed",
        ),
        event(
            "role_assigned",
            ago(94),
            session_id="S6",
            operation_id="E12",
            candidate="T2:checkpoint-90000",
            role="best known",
        ),
        event(
            "checkpoint_saved",
            ago(93),
            session_id="S6",
            inquiry_id="I2",
            current_synthesis="The policy reaches the target; hold is unreliable.",
        ),
        event(
            "session_ended", ago(92), session_id="S6", summary="Checkpointed after M5."
        ),
        event("session_started", ago(22), session_id="S7", id="S7", kind="inquiry"),
        event(
            "inquiry_opened",
            ago(21),
            session_id="S7",
            inquiry_id="I3",
            question=(
                "Does longer settling improve hold stability, or do the remaining "
                "failures require a different control intervention?"
            ),
        ),
        event(
            "operation_requested",
            ago(20),
            session_id="S7",
            inquiry_id="I3",
            operation_id="M6",
            kind="measurement",
            status="requested",
        ),
    ]


def demo_schedule() -> list[tuple[float, Observation]]:
    """Scripted demo observations on relative seconds.

    The earlier journal is replayed first, at second zero. Times deliberately
    include a training execution that ends before the measurement starts, so
    the demo exercises the training/evaluation progress switch and the
    operation-end removal of the progress area.
    """
    started, stage_start, now = demo_clock()
    first_pi = stage_start + timedelta(seconds=0.5)

    def event(
        seconds: float,
        event_kind: str,
        /,
        *,
        at: datetime | None = None,
        **fields,
    ) -> tuple[float, Observation]:
        stamp = at
        if stamp is None:
            stamp = (
                now
                if event_kind == "liveness"
                else stage_start + timedelta(seconds=seconds)
            )
        # The envelope names the owners; the payload keeps its own copies, as
        # the real emitters do.
        identity = {
            name: fields[name]
            for name in ("session_id", "operation_id", "inquiry_id")
            if name in fields
        }
        if event_kind not in {"liveness", "notice"}:
            identity.setdefault("session_id", "S7")
        return seconds, Observation(event_kind, stamp, fields, **identity)

    return [
        *[(0.0, past) for past in _past_events(started, now)],
        event(0.0, "liveness"),
        event(
            0.1,
            "session_start",
            session_id="S7",
            stage_started_at=stage_start.isoformat(),
        ),
        event(0.3, "notice", scope="activity", text="M6 measurement accepted"),
        event(0.5, "pi_message", session_id="S7", text=_PI_MESSAGE, at=first_pi),
        event(
            0.8,
            "pi_message",
            session_id="S7",
            text=_PI_MESSAGE,
            at=first_pi,
        ),  # replay duplicate
        event(
            1.2,
            "tool",
            agent="pi",
            name="artifact_evidence_query",
            detail="M5 | artifact 0",
        ),
        event(1.6, "activity", label="T5 training"),
        event(
            1.7,
            "training_progress",
            operation_id="T5",
            attempt=1,
            steps=0,
            target=80000,
        ),
        event(
            2.0,
            "training_progress",
            operation_id="T5",
            attempt=1,
            steps=24000,
            target=80000,
            elapsed_seconds=720,
        ),
        event(
            2.4,
            "training_progress",
            operation_id="T5",
            attempt=1,
            steps=52000,
            target=80000,
            elapsed_seconds=1560,
        ),
        event(
            2.8,
            "training_progress",
            operation_id="T5",
            attempt=1,
            steps=80000,
            target=80000,
            elapsed_seconds=2400,
        ),
        event(
            3.0,
            "operation_completed",
            operation_id="T5",
            id="T5",
            kind="training",
            status="completed",
        ),
        event(3.2, "activity", label="M6 measurement"),
        event(
            3.4,
            "eval_progress",
            operation_id="M6",
            instrument="task reference",
            episodes=0,
            episodes_total=100,
            panel_index=1,
            panel_total=3,
            completed_panels=0,
            elapsed_seconds=12,
        ),
        event(
            3.8,
            "eval_progress",
            operation_id="M6",
            instrument="task reference",
            episodes=44,
            episodes_total=100,
            panel_index=1,
            panel_total=3,
            completed_panels=0,
            elapsed_seconds=96,
        ),
        event(
            4.2,
            "eval_progress",
            operation_id="M6",
            instrument="official assessment",
            official=True,
            episodes=140,
            episodes_total=200,
            elapsed_seconds=420,
        ),
        event(
            4.6,
            "operation_completed",
            operation_id="M6",
            id="M6",
            kind="measurement",
            status="completed",
        ),
        event(5.0, "activity", label="publication"),
    ]


def demo_snapshot_args() -> tuple[dict, list[dict], list[dict]]:
    started, _, now = demo_clock()
    return (
        demo_state(now, started),
        demo_records(now),
        demo_usage_rows(now),
    )
