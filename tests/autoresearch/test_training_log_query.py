"""Human-owned contract tests for preserved raw training log access."""

from __future__ import annotations

import pytest

from research import query_training_log as query
from research import runner_execution as execution
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