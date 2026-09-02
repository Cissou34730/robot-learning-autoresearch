"""Human-owned contract tests for preserved raw training log access."""

from __future__ import annotations

from argparse import Namespace

import pytest

from research import query_training_log as query
from research import runner_execution as execution
from research.run_experiment import run_training_experiment
from research.runner_protocol import is_protected_source


def write_log(path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_training_attempts_isolate_experiments_and_resume_or_restart(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.TRAINING_LOG_DIR", tmp_path)
    write_log(tmp_path / "experiment-1-attempt-1.log", "first")
    write_log(tmp_path / "experiment-1-attempt-2.log", "second")
    write_log(tmp_path / "experiment-2-attempt-1.log", "other")

    assert execution.training_attempt(1, recoverable_continuation=True) == 2
    assert execution.training_attempt(1, recoverable_continuation=False) == 3
    assert execution.training_attempt(2, recoverable_continuation=False) == 2
    assert execution.training_attempt(3, recoverable_continuation=False) == 1


def test_recoverable_continuation_requires_an_existing_attempt(monkeypatch, tmp_path):
    monkeypatch.setattr("research.runner_paths.TRAINING_LOG_DIR", tmp_path)

    with pytest.raises(RuntimeError, match="no training log"):
        execution.training_attempt(1, recoverable_continuation=True)


def test_recoverable_continuation_appends_and_live_progress_reads_active_log(
    monkeypatch, tmp_path
):
    log = tmp_path / "experiment-1-attempt-1.log"
    write_log(log, "interrupted output\n")
    observed_records = []

    class WritingProcess:
        returncode = 0

        def __init__(self, *args, stdout, **kwargs):
            del args, kwargs
            stdout.write("| time/ |\n| total_timesteps | 200 |\n")
            stdout.flush()
            self.polls = 0

        def poll(self):
            self.polls += 1
            return None if self.polls == 1 else 0

        def wait(self, timeout):
            del timeout
            return 0

    output_dir = tmp_path / "candidate"
    output_dir.mkdir()
    for filename in ("model.zip", "artifact.json"):
        (output_dir / filename).touch()
    monkeypatch.setattr("research.runner_execution.subprocess.Popen", WritingProcess)
    monkeypatch.setattr(
        "research.runner_execution.console.training_progress_suffix",
        lambda record: observed_records.append(record) or "",
    )

    attempt = execution.training_attempt(1, recoverable_continuation=True)
    execution.train_candidate(
        output_dir, 100, 0, None, execution.training_log_path(1, attempt),
        continue_timesteps=True, target_timesteps=200,
    )

    assert log.read_text(encoding="utf-8").startswith("interrupted output\n")
    assert observed_records == [{"total_timesteps": 200.0}]


@pytest.mark.parametrize(
    ("restart", "expected_name"),
    [(False, "experiment-2-attempt-1.log"), (True, "experiment-2-attempt-2.log")],
)
def test_runner_passes_the_correct_active_attempt_to_training(
    monkeypatch, tmp_path, restart, expected_name
):
    training_logs = tmp_path / "training_logs"
    write_log(training_logs / "experiment-1-attempt-9.log", "other experiment\n")
    if restart:
        interrupted = training_logs / "experiment-2-attempt-1.log"
        write_log(interrupted, "interrupted output\n")
    else:
        interrupted = None
    restart_pending = tmp_path / "RESTART_PENDING"
    if restart:
        restart_pending.touch()
    captured_logs = []
    state = {"last_experiment": 1, "last_allocated_experiment": 1}

    monkeypatch.setattr("research.runner_paths.TRAINING_LOG_DIR", training_logs)
    monkeypatch.setattr("research.runner_paths.RESTART_PENDING_PATH", restart_pending)
    monkeypatch.setattr("research.runner_repository.load_state", lambda **kwargs: state)
    monkeypatch.setattr("research.runner_repository.anchor_scientific_parent", lambda state: "parent")
    monkeypatch.setattr("research.runner_repository.atomic_write_json", lambda *args: None)
    monkeypatch.setattr("research.runner_repository.scientific_delta", lambda parent: [])
    monkeypatch.setattr("research.runner_repository.archive_candidates", lambda *args: [])
    monkeypatch.setattr("research.runner_protocol.next_experiment_index", lambda state: 2)
    monkeypatch.setattr("research.runner_protocol.resumed_experiment_index", lambda *args: 2)
    monkeypatch.setattr("research.runner_protocol.training_parent", lambda *args: ("", tmp_path, 0))
    monkeypatch.setattr("research.runner_protocol.validate_experiment_semantics", lambda *args: None)
    monkeypatch.setattr("research.runner_protocol.validation_test_paths", lambda *args, **kwargs: ())
    monkeypatch.setattr("research.runner_execution.validate_active_configuration", lambda: {})
    monkeypatch.setattr("research.runner_execution.training_budget", lambda *args: 10)
    monkeypatch.setattr("research.runner_execution.candidate_directories", lambda path: [])
    monkeypatch.setattr("research.runner_execution.remove_candidate_dir", lambda path: None)
    monkeypatch.setattr("research.runner_console.render_experiment_card", lambda result: "")
    monkeypatch.setattr("research.runner_console.render_training_summary_card", lambda *args, **kwargs: "")
    monkeypatch.setattr("research.runner_execution.train_candidate", lambda *args, **kwargs: captured_logs.append(args[4]) or 0.0)

    proposal = {
        "change": "exercise training log wiring",
        "hypothesis": "the selected attempt is passed to training",
        "kind": "training",
        "family": "training.logs",
        "initialization": "fresh",
    }
    assert run_training_experiment(proposal, Namespace(timesteps=10, reuse_candidate=None)) == 0

    assert captured_logs == [training_logs / expected_name]
    if interrupted is not None:
        assert interrupted.read_text(encoding="utf-8") == "interrupted output\n"


def test_query_tool_is_a_protected_runner_source():
    assert is_protected_source("research/query_training_log.py")


def test_query_returns_inclusive_range_attempts_metrics_and_missing_values(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("research.runner_paths.TRAINING_LOG_DIR", tmp_path)
    write_log(
        tmp_path / "experiment-3-attempt-1.log",
        "| rollout/ |\n| ep_rew_mean | 0 |\n| time/ |\n| total_timesteps | 100 |\n"
        "| rollout/ |\n| success_rate | 0.5 |\n| time/ |\n| total_timesteps | 200 |\n",
    )
    write_log(
        tmp_path / "experiment-3-attempt-2.log",
        "| rollout/ |\n| ep_rew_mean | 2 |\n| time/ |\n| total_timesteps | 200 |\n",
    )

    assert query.main(["--experiment", "3", "--from-step", "100", "--to-step", "200"]) == 0
    output = capsys.readouterr().out
    assert "| attempt | total_timesteps | ep_rew_mean | success_rate |" in output
    assert "| 1 | 100 | 0 |  |" in output
    assert "| 1 | 200 |  | 0.5 |" in output
    assert "| 2 | 200 | 2 |  |" in output


def test_query_supports_exact_step_and_empty_valid_ranges(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("research.runner_paths.TRAINING_LOG_DIR", tmp_path)
    write_log(
        tmp_path / "experiment-1-attempt-1.log",
        "| time/ |\n| total_timesteps | 100 |\n",
    )

    assert query.main(["--experiment", "1", "--from-step", "100", "--to-step", "100"]) == 0
    assert "| 1 | 100 |" in capsys.readouterr().out
    assert query.main(["--experiment", "1", "--from-step", "101", "--to-step", "200"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "| attempt | total_timesteps |",
        "| --- | --- |",
    ]


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["--experiment", "1", "--from-step", "2"],
        ["--experiment", "1", "--from-step", "2", "--to-step", "1"],
        ["--experiment", "0", "--from-step", "0", "--to-step", "1"],
    ],
)
def test_query_requires_valid_arguments(arguments):
    with pytest.raises(SystemExit, match="2"):
        query.parse_arguments(arguments)


def test_query_reports_an_unknown_experiment(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr("research.runner_paths.TRAINING_LOG_DIR", tmp_path)

    assert query.main(["--experiment", "1", "--from-step", "0", "--to-step", "1"]) == 1
    assert "no training logs found" in capsys.readouterr().err