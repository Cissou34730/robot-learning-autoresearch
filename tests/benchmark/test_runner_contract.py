import json

import pytest

from research.run_experiment import (
    IMMUTABLE_PATHS,
    MUTABLE_CODE_PATHS,
    MUTABLE_PATHS,
    append_result,
    assert_research_surface,
    format_duration,
    latest_training_steps,
    load_state,
    rank,
    validate_reusable_candidate,
)


def metrics(success, hold_median, hold_mean, closest):
    return {
        "success_percent": success,
        "consecutive_hold_steps": {
            "median": hold_median,
            "mean": hold_mean,
            "required": 100,
        },
        "closest_distance_cm": {"median": closest},
    }


def test_research_and_benchmark_surfaces_are_disjoint():
    assert set(IMMUTABLE_PATHS).isdisjoint(MUTABLE_PATHS)
    assert "robot_learning/environments/reach_env.py" in IMMUTABLE_PATHS
    assert "tests/benchmark" in IMMUTABLE_PATHS
    assert "tests/research" in MUTABLE_PATHS
    assert "research/current_params.json" in MUTABLE_PATHS
    assert "research/current_params.json" not in MUTABLE_CODE_PATHS


def test_direct_parameter_file_edit_is_a_research_change(monkeypatch):
    monkeypatch.setattr(
        "research.run_experiment.status_paths",
        lambda _paths: ["research/current_params.json"],
    )

    assert assert_research_surface() == ["research/current_params.json"]


def test_success_precedes_distance():
    assert rank(metrics(80.0, 10.0, 10.0, 4.0)) > rank(
        metrics(79.0, 100.0, 100.0, 1.0)
    )


def test_hold_median_precedes_hold_mean_and_distance():
    assert rank(metrics(80.0, 90.0, 90.0, 4.0)) > rank(
        metrics(80.0, 89.0, 100.0, 1.0)
    )


def test_hold_mean_precedes_distance():
    assert rank(metrics(80.0, 90.0, 95.0, 4.0)) > rank(
        metrics(80.0, 90.0, 94.0, 1.0)
    )


def test_distance_breaks_a_complete_metric_tie():
    assert rank(metrics(80.0, 90.0, 95.0, 1.0)) > rank(
        metrics(80.0, 90.0, 95.0, 2.0)
    )


def test_training_progress_reads_latest_complete_snapshot(tmp_path):
    log = tmp_path / "train.log"
    log.write_text(
        "|    total_timesteps      | 1024        |\n"
        "|    total_timesteps      | 2048        |\n",
        encoding="utf-8",
    )
    assert latest_training_steps(log) == 2048


def test_duration_is_compact_and_human_readable():
    assert format_duration(15) == "15s"
    assert format_duration(125) == "2m05s"
    assert format_duration(3720) == "1h02m"


def test_fresh_baseline_can_start_without_an_accepted_artifact(
    monkeypatch, tmp_path
):
    state_path = tmp_path / "research_state.json"
    state_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "accepted_artifact": "missing-checkpoint",
                "accepted_metrics": None,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("research.run_experiment.STATE_PATH", state_path)
    monkeypatch.setattr("research.run_experiment.ROOT", tmp_path)

    state = load_state(allow_unmeasured=True, allow_missing_artifact=True)
    assert state["accepted_metrics"] is None
    with pytest.raises(RuntimeError, match="accepted artifact is incomplete"):
        load_state(allow_unmeasured=True)


def test_experiment_rows_remain_one_line(monkeypatch, tmp_path):
    log_path = tmp_path / "EXPERIMENTS.md"
    results_path = tmp_path / "results.jsonl"
    log_path.write_text("header\n", encoding="utf-8")
    monkeypatch.setattr("research.run_experiment.LOG_PATH", log_path)
    monkeypatch.setattr("research.run_experiment.RESULTS_PATH", results_path)

    append_result(
        {
            "index": 1,
            "change": "line one\nline two",
            "hypothesis": "safe | table",
            "verdict": "error:\ntraceback",
        }
    )

    assert log_path.read_text(encoding="utf-8").count("\n") == 2
    assert "line one line two" in log_path.read_text(encoding="utf-8")
    assert "safe / table" in log_path.read_text(encoding="utf-8")


def test_reusable_candidate_must_match_experiment(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "model.zip").touch()
    (candidate / "vecnormalize.pkl").touch()
    (candidate / "artifact.json").write_text(
        '{"algorithm":"ppo","seed":0,"timesteps":1000,'
        '"n_envs":1,"parameters":{"n_steps":1024},"policy":{},'
        '"resumed_from":null}',
        encoding="utf-8",
    )
    config = {
        "algorithm": {"name": "ppo"},
        "training": {"n_envs": 1},
        "ppo": {"n_steps": 1024},
        "policy": {},
    }

    with pytest.raises(ValueError, match="timesteps"):
        validate_reusable_candidate(
            candidate,
            timesteps=120_000,
            resume=None,
            config=config,
        )
