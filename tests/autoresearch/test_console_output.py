import json
import re
from io import StringIO

import pytest

from research import run_experiment, runner_console


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
        "request": {"measurement": {"measurements": []}},
        "request_fingerprint": "fingerprint",
        "progress": "accepted",
        "failure": None,
        "data": {"result": None},
    }
    state = {
        "pending_operation": pending,
        "scientific_session": {"backend_session_id": "backend-session"},
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


def test_no_credible_route_has_one_runner_owned_campaign_end(monkeypatch):
    boundaries = []
    state = {
        "scientific_session": {
            "id": "S4",
        },
        "campaign": {
            "id": "11111111-1111-1111-1111-111111111111",
        },
    }
    pending = {
        "kind": "campaign_conclusion",
        "data": {
            "result": {
                "status": "no_credible_route",
            }
        },
    }
    monkeypatch.setattr(
        run_experiment.console,
        "boundary",
        lambda scope, action, subject="", detail="": boundaries.append(
            (scope, action, subject, detail)
        ),
    )
    monkeypatch.setattr(
        run_experiment.console,
        "usage_summary",
        lambda *_args: "usage",
    )
    monkeypatch.setattr(
        run_experiment.repository,
        "current_campaign_id",
        lambda _state: state["campaign"]["id"],
    )

    run_experiment._announce_consequential_completion(state, pending, "session usage")

    assert boundaries == [
        ("session", "END", "S4", "session usage"),
        ("campaign", "END", "no credible route", "usage"),
    ]
