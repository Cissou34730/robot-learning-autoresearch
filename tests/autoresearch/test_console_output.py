import json
import re
import subprocess
import sys
from io import StringIO

import pytest

from research import run_experiment, runner_console, runner_execution


def test_training_heartbeat_keeps_every_live_field(monkeypatch):
    monkeypatch.setattr(runner_console, "_console_width", lambda: 120)
    monkeypatch.setattr(
        runner_console,
        "scenario_progress_metric",
        lambda _record: "success 54%",
    )

    line = runner_console.training_heartbeat(
        "T3",
        101_000,
        120_000,
        357,
        68,
        357,
        {"ep_rew_mean": 163},
    )

    for fact in (
        "TRAIN T3",
        "84%",
        "101k/120k",
        "357 fps",
        "5m57s",
        "ETA 1m08s",
        "reward 163",
        "success 54%",
    ):
        assert fact in line


@pytest.mark.parametrize("width", [80, 120])
def test_training_heartbeat_render_preserves_fields_at_common_widths(
    monkeypatch, width
):
    class Tty(StringIO):
        def isatty(self):
            return True

    monkeypatch.setattr(runner_console, "_console_width", lambda: width)
    monkeypatch.setattr(
        runner_console,
        "scenario_progress_metric",
        lambda _record: "success 54%",
    )
    stream = Tty()
    progress = runner_console.LiveProgress(stream=stream, archive_seconds=999)

    progress.line(
        runner_console.training_heartbeat(
            "T3",
            101_000,
            120_000,
            357,
            68,
            357,
            {"ep_rew_mean": 163},
        )
    )

    rendered = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", stream.getvalue())
    line = rendered.replace("\r", "").strip()
    assert len(line) <= width
    for fact in (
        "T3",
        "84%",
        "101k/120k",
        "5m57s",
        "1m08s",
        "357",
        "163",
        "success 54%",
    ):
        assert fact in line


def test_training_checkpoints_show_reward_and_success_once(tmp_path, monkeypatch):
    pool = tmp_path / "candidate_pool"
    for steps, reward, success in (
        (10_240, -16.18, 0.25),
        (5_120, -18.35, 0.0),
    ):
        checkpoint = pool / f"checkpoint-{steps}"
        checkpoint.mkdir(parents=True)
        (checkpoint / "training_metrics.json").write_text(
            json.dumps({"ep_rew_mean": reward, "success_rate": success}),
            encoding="utf-8",
        )
    boundaries = []
    monkeypatch.setattr(
        runner_execution.console,
        "boundary",
        lambda scope, action, subject="", detail="": boundaries.append(
            (scope, action, subject, detail)
        ),
    )
    announced: set[str] = set()

    runner_execution.announce_training_checkpoints(tmp_path, "T3", announced)
    runner_execution.announce_training_checkpoints(tmp_path, "T3", announced)

    assert len(boundaries) == 1
    scope, action, subject, detail = boundaries[0]
    assert (scope, action, subject) == ("checkpoint", "TRAINING RESULTS", "T3")
    rows = detail.splitlines()
    assert len(rows) == 2
    assert "T3:checkpoint-5120" in rows[0]
    assert "reward -18.35" in rows[0]
    assert "success 0%" in rows[0]
    assert "T3:checkpoint-10240" in rows[1]
    assert "reward -16.18" in rows[1]
    assert "success 25%" in rows[1]


def test_progress_clips_one_line_without_exposing_a_tail(monkeypatch):
    class Tty(StringIO):
        def isatty(self):
            return True

    stream = Tty()
    monkeypatch.setattr(runner_console, "_console_width", lambda: 50)
    progress = runner_console.LiveProgress(stream=stream, archive_seconds=999)

    progress.line("TRAIN T1 | " + "x" * 100)

    rendered = stream.getvalue()
    assert "\n" in rendered
    assert "..." in rendered
    assert "x" * 60 not in rendered


def test_redirected_phase_boundary_is_a_spaced_card():
    detail = "strategic usage\n  prompt 12k   output 800 " + "x" * 160
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from research import runner_console; "
                "runner_console.boundary("
                f"'session', 'END', 'S4 goal review', {detail!r})"
            ),
        ],
        cwd=runner_console._ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    rendered = completed.stdout.splitlines()
    assert rendered[0] == ""
    assert "=== SESSION | END | S4 goal review ===" in rendered[1]
    assert rendered[2] == "  strategic usage"
    assert "prompt 12k output 800" in rendered[3]
    assert rendered[3].endswith("x" * 160)
    assert rendered[-1] == ""
    assert "\x1b[" not in completed.stdout


def test_measurement_request_detail_names_reason_panels_and_comparison():
    pending = {
        "kind": "measurement",
        "request": {
            "measurement": {
                "description": "Check held-out complete-hold performance.",
                "rationale": "Training telemetry is not independent evidence.",
                "measurements": [
                    {
                        "instrument": "research_evaluation",
                        "candidate": "T1:checkpoint-120832",
                        "episodes": 100,
                        "seed": 1200,
                        "label": "independent hold diagnostics",
                    },
                    {
                        "instrument": "task_reference",
                        "candidate": "T1:checkpoint-120832",
                        "label": "task reference",
                    },
                ],
                "paired_comparisons": [
                    {
                        "candidate": "T1:checkpoint-120832",
                        "reference": "T1:checkpoint-115712",
                    }
                ],
            }
        },
    }

    detail = run_experiment._operation_request_detail(pending)

    for fact in (
        "Check held-out complete-hold performance.",
        "Training telemetry is not independent evidence.",
        "T1:checkpoint-120832",
        "100 episodes",
        "seed 1200",
        "task reference",
        "T1:checkpoint-115712",
    ):
        assert fact in detail


def test_usage_summary_aggregates_existing_durable_accounting(tmp_path, monkeypatch):
    campaign = "11111111-1111-1111-1111-111111111111"
    usage = tmp_path / "reports" / "session_usage"
    usage.mkdir(parents=True)
    rows = [
        {
            "session_id": "backend-session",
            "duration_seconds": 60,
            "input_tokens": 1_000,
            "cache_read_tokens": 800,
            "output_tokens": 50,
            "aiu": 0.25,
        },
        {
            "session_id": "backend-session",
            "duration_seconds": 30,
            "input_tokens": 500,
            "cache_read_tokens": 400,
            "output_tokens": 25,
            "reported_cost_usd": 0.1,
        },
        {
            "session_id": "another-session",
            "duration_seconds": 999,
            "input_tokens": 999,
        },
    ]
    (usage / f"{campaign}.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )
    monkeypatch.setattr(runner_console, "_ROOT", tmp_path)

    summary = runner_console.usage_summary(campaign, "backend-session")

    assert "1m30s" in summary
    assert "0.25 AIU" in summary
    assert "$0.1000 estimated" in summary
    assert "prompt 1.5k (80% cached)" in summary
    assert "output 75" in summary


def test_operation_subjects_use_human_lifecycle_identifiers():
    assert (
        run_experiment._operation_subject(
            {
                "id": "M2",
                "kind": "measurement",
                "data": {},
            }
        )
        == "M2 measurement"
    )
    assert (
        run_experiment._operation_subject(
            {
                "id": "E7",
                "kind": "inquiry",
                "data": {
                    "plan": {
                        "action": "reframe",
                        "inquiry_id": "I3",
                    }
                },
            }
        )
        == "I3 inquiry"
    )
    assert (
        run_experiment._operation_subject(
            {
                "id": "E8",
                "kind": "checkpoint",
                "data": {"plan": {"session_id": "S4"}},
            }
        )
        == "S4 checkpoint"
    )


def test_operation_execution_has_request_start_and_completion_boundaries(monkeypatch):
    pending = {
        "id": "M2",
        "kind": "measurement",
        "session_id": "S3",
        "inquiry_id": "I1",
        "request": {
            "measurement": {
                "description": "Measure the selected candidate.",
                "rationale": "Independent evidence informs the next decision.",
                "measurements": [],
            }
        },
        "request_fingerprint": "fingerprint",
        "progress": "accepted",
        "failure": None,
        "data": {"result": None},
    }
    state = {
        "pending_operation": pending,
        "scientific_session": {"backend_session_id": "backend-session"},
        "campaign": {"id": "campaign"},
    }
    boundaries = []

    monkeypatch.setattr(
        run_experiment.repository,
        "load_state",
        lambda **_kwargs: state,
    )
    monkeypatch.setattr(
        run_experiment, "_canonical_fingerprint", lambda _value: "fingerprint"
    )
    monkeypatch.setattr(
        run_experiment, "_write_accepted_request_handoff", lambda _pending: None
    )
    monkeypatch.setattr(
        run_experiment.console,
        "boundary",
        lambda scope, action, subject="", detail="": boundaries.append(
            (scope, action, subject, detail)
        ),
    )

    def execute(_state, operation):
        operation["data"]["result"] = {
            "status": "completed",
            "measurements": [],
            "paired_comparisons": [],
        }
        operation["progress"] = "completed"
        return 0

    monkeypatch.setattr(run_experiment, "execute_measurement", execute)

    assert run_experiment.execute_pending_operation() == 0
    assert [entry[1] for entry in boundaries] == ["REQUEST", "START", "COMPLETE"]
    assert all(entry[2] == "M2 measurement" for entry in boundaries)


def test_compact_path_hides_machine_specific_repository_prefix():
    absolute = (
        runner_console._ROOT
        / "research"
        / "evaluations"
        / "campaign"
        / "measurement.json"
    )

    rendered = runner_console.compact_path(absolute)

    assert rendered == "research/evaluations/campaign/measurement.json"
    assert str(runner_console._ROOT) not in rendered


@pytest.mark.parametrize(
    ("status", "model", "campaign_action", "campaign_subject"),
    [
        ("no_credible_route", None, "END", "no credible route"),
        (
            "official_assessment_requested",
            "T1:checkpoint-10",
            "DECISION",
            "official assessment requested",
        ),
    ],
)
def test_campaign_conclusion_pairs_session_end_with_campaign_boundary(
    monkeypatch,
    status,
    model,
    campaign_action,
    campaign_subject,
):
    boundaries = []
    request = {
        "campaign_conclusion": {
            "action": (
                "no_credible_route"
                if status == "no_credible_route"
                else "request_official_assessment"
            ),
            "reason": "The durable evidence supports this terminal decision.",
        }
    }
    pending = {
        "id": "E4",
        "kind": "campaign_conclusion",
        "session_id": "S4",
        "inquiry_id": None,
        "request": request,
        "request_fingerprint": run_experiment._canonical_fingerprint(request),
        "progress": "accepted",
        "failure": None,
        "supersedes": None,
        "data": {
            "plan": {
                "status": status,
                "reason": request["campaign_conclusion"]["reason"],
                "model": model,
            },
            "presentation": {
                "campaign_id": "11111111-1111-1111-1111-111111111111",
                "session_id": "S4",
                "session_kind": "goal_review",
                "backend_session_id": "backend-session",
                "session_usage": "session usage",
                "campaign_usage": "campaign usage",
            },
            "result": None,
        },
    }
    state = {
        "pending_operation": pending,
        "scientific_session": {
            "id": "S4",
            "kind": "goal_review",
            "backend_session_id": "backend-session",
        },
        "operation_events": [],
        "last_verdict": "goal review",
        "terminal_state": None,
        "campaign": {
            "id": "11111111-1111-1111-1111-111111111111",
        },
    }
    monkeypatch.setattr(
        run_experiment.repository, "load_state", lambda **_kwargs: state
    )
    monkeypatch.setattr(run_experiment.repository, "write_state", lambda _state: None)
    monkeypatch.setattr(
        run_experiment.repository, "upsert_operation_event", lambda _event: None
    )
    monkeypatch.setattr(
        run_experiment.repository, "commit_runner_memory", lambda _message: True
    )
    monkeypatch.setattr(
        run_experiment, "_write_accepted_request_handoff", lambda _pending: None
    )
    monkeypatch.setattr(
        run_experiment, "_consume_accepted_request_handoff", lambda _operation_id: True
    )
    monkeypatch.setattr(
        run_experiment.console,
        "boundary",
        lambda scope, action, subject="", detail="": boundaries.append(
            (scope, action, subject, detail)
        ),
    )
    assert run_experiment.execute_pending_operation() == 0

    assert boundaries[-2:] == [
        ("session", "END", "S4 goal review", "session usage"),
        ("campaign", campaign_action, campaign_subject, "campaign usage"),
    ]
    assert sum(entry[0:2] == ("session", "END") for entry in boundaries) == 1
    assert sum(entry[0:2] == ("campaign", campaign_action) for entry in boundaries) == 1


@pytest.mark.parametrize(
    ("pending", "expected"),
    [
        (
            {
                "id": "E2",
                "kind": "inquiry",
                "session_id": "S2",
                "inquiry_id": None,
                "request": {"inquiry": {"action": "open"}},
                "request_fingerprint": "fingerprint",
                "progress": "completed",
                "failure": None,
                "supersedes": None,
                "data": {
                    "plan": {},
                    "result": {
                        "status": "completed",
                        "action": "open",
                        "inquiry_id": "I2",
                    },
                },
            },
            [("inquiry", "OPEN", "I2", "")],
        ),
        (
            {
                "id": "E3",
                "kind": "checkpoint",
                "session_id": "S3",
                "inquiry_id": "I1",
                "request": {"checkpoint": {}},
                "request_fingerprint": "fingerprint",
                "progress": "completed",
                "failure": None,
                "supersedes": None,
                "data": {
                    "plan": {"session_id": "S3"},
                    "presentation": {
                        "campaign_id": "campaign",
                        "session_id": "S3",
                        "session_kind": "inquiry",
                        "backend_session_id": "backend-S3",
                        "session_usage": "session usage",
                        "campaign_usage": "campaign usage",
                    },
                    "result": {"status": "checkpointed", "session_id": "S3"},
                },
            },
            [
                ("checkpoint", "COMPLETE", "S3", ""),
                ("session", "END", "S3 inquiry", "session usage"),
            ],
        ),
        (
            {
                "id": "E4",
                "kind": "campaign_conclusion",
                "session_id": "S4",
                "inquiry_id": None,
                "request": {"campaign_conclusion": {"action": "no_credible_route"}},
                "request_fingerprint": "fingerprint",
                "progress": "completed",
                "failure": None,
                "supersedes": None,
                "data": {
                    "plan": {},
                    "presentation": {
                        "campaign_id": "campaign",
                        "session_id": "S4",
                        "session_kind": "goal_review",
                        "backend_session_id": "backend-S4",
                        "session_usage": "session usage",
                        "campaign_usage": "campaign usage",
                    },
                    "result": {"status": "no_credible_route", "model": None},
                },
            },
            [
                ("session", "END", "S4 goal review", "session usage"),
                ("campaign", "END", "no credible route", "campaign usage"),
            ],
        ),
        (
            {
                "id": "E5",
                "kind": "campaign_conclusion",
                "session_id": "S5",
                "inquiry_id": None,
                "request": {
                    "campaign_conclusion": {"action": "request_official_assessment"}
                },
                "request_fingerprint": "fingerprint",
                "progress": "completed",
                "failure": None,
                "supersedes": None,
                "data": {
                    "plan": {},
                    "presentation": {
                        "campaign_id": "campaign",
                        "session_id": "S5",
                        "session_kind": "goal_review",
                        "backend_session_id": "backend-S5",
                        "session_usage": "session usage",
                        "campaign_usage": "campaign usage",
                    },
                    "result": {
                        "status": "official_assessment_requested",
                        "model": "T1:checkpoint-10",
                    },
                },
            },
            [
                ("session", "END", "S5 goal review", "session usage"),
                (
                    "campaign",
                    "DECISION",
                    "official assessment requested",
                    "campaign usage",
                ),
            ],
        ),
    ],
)
def test_completed_pending_recovery_uses_the_shared_completion_presenter(
    monkeypatch, pending, expected
):
    pending["request_fingerprint"] = run_experiment._canonical_fingerprint(
        pending["request"]
    )
    state = {
        "pending_operation": pending,
        "scientific_session": None,
        "campaign": {"id": "campaign"},
    }
    boundaries = []
    monkeypatch.setattr(
        run_experiment.repository, "load_state", lambda **_kwargs: state
    )
    monkeypatch.setattr(run_experiment.repository, "write_state", lambda _state: None)
    monkeypatch.setattr(
        run_experiment.repository, "commit_runner_memory", lambda _message: True
    )
    monkeypatch.setattr(
        run_experiment, "_write_accepted_request_handoff", lambda _pending: None
    )
    monkeypatch.setattr(
        run_experiment, "_consume_accepted_request_handoff", lambda _operation_id: True
    )
    monkeypatch.setattr(
        run_experiment.console,
        "boundary",
        lambda scope, action, subject="", detail="": boundaries.append(
            (scope, action, subject, detail)
        ),
    )
    assert run_experiment.execute_pending_operation() == 0

    assert sum(entry[0:2] == ("operation", "COMPLETE") for entry in boundaries) == 1
    assert boundaries[-len(expected) :] == expected
