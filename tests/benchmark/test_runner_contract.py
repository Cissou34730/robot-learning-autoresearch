import json
from pathlib import Path

import pytest

from research.run_experiment import (
    append_result,
    assert_research_surface,
    candidate_directories,
    commit_and_push,
    format_duration,
    latest_training_steps,
    load_state,
    validate_reusable_candidate,
)
from robot_learning.evaluate import write_progress


def test_research_surface_has_no_file_whitelist(monkeypatch):
    monkeypatch.setattr(
        "research.run_experiment.status_paths",
        lambda _paths: [
            "robot_learning/benchmark/spec.py",
            "robot_learning/evaluate.py",
            "research/run_experiment.py",
        ],
    )

    assert assert_research_surface() == [
        "robot_learning/benchmark/spec.py",
        "robot_learning/evaluate.py",
        "research/run_experiment.py",
    ]


def test_direct_parameter_file_edit_is_a_research_change(monkeypatch):
    monkeypatch.setattr(
        "research.run_experiment.status_paths",
        lambda _paths: ["research/current_params.json"],
    )

    assert assert_research_surface() == ["research/current_params.json"]


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


def test_evaluation_progress_is_best_effort(monkeypatch, tmp_path):
    progress = tmp_path / "evaluation.progress"
    assert write_progress(progress, 80, 200)
    assert json.loads(progress.read_text(encoding="utf-8")) == {
        "completed": 80,
        "total": 200,
    }

    def deny_write(_path, *_args, **_kwargs):
        raise PermissionError("simulated Windows reader lock")

    monkeypatch.setattr(Path, "write_text", deny_write)
    assert not write_progress(progress, 81, 200)


def test_automatic_commit_is_immediately_pushed(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "research.run_experiment.git",
        lambda *args: calls.append(args) or "",
    )

    commit_and_push("record result")

    assert calls == [
        ("commit", "-m", "record result"),
        ("push", "origin", "HEAD"),
    ]


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
            seed=0,
            resume=None,
            config=config,
        )


def test_interrupted_candidate_can_resume_its_remaining_budget(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    for filename in ("model.zip", "vecnormalize.pkl"):
        (candidate / filename).touch()
    (candidate / "artifact.json").write_text(
        '{"algorithm":"ppo","seed":0,"timesteps":50000,'
        '"requested_timesteps":120000,"completed":false,'
        '"n_envs":1,"parameters":{"n_steps":1024},"policy":{},'
        '"resumed_from":"a prior recovery checkpoint"}',
        encoding="utf-8",
    )
    config = {
        "algorithm": {"name": "ppo"},
        "training": {"n_envs": 1},
        "ppo": {"n_steps": 1024},
        "policy": {},
    }

    validate_reusable_candidate(
        candidate,
        timesteps=120_000,
        seed=0,
        resume=None,
        config=config,
    )


def test_candidate_manifest_exposes_all_complete_artifacts(tmp_path):
    finalists = []
    for number in range(3):
        relative = f"finalists/checkpoint-{number}"
        artifact_dir = tmp_path / relative
        artifact_dir.mkdir(parents=True)
        for filename in ("model.zip", "vecnormalize.pkl", "artifact.json"):
            (artifact_dir / filename).touch()
        finalists.append({"path": relative})
    (tmp_path / "candidate_manifest.json").write_text(
        json.dumps({"candidates": finalists}), encoding="utf-8"
    )

    assert candidate_directories(tmp_path) == [
        tmp_path / item["path"] for item in finalists
    ]


def test_candidate_manifest_is_not_limited_to_three_artifacts(tmp_path):
    finalists = []
    for number in range(5):
        relative = f"finalists/checkpoint-{number}"
        artifact_dir = tmp_path / relative
        artifact_dir.mkdir(parents=True)
        for filename in ("model.zip", "vecnormalize.pkl", "artifact.json"):
            (artifact_dir / filename).touch()
        finalists.append({"path": relative})
    (tmp_path / "candidate_manifest.json").write_text(
        json.dumps({"candidates": finalists}), encoding="utf-8"
    )

    assert len(candidate_directories(tmp_path)) == 5
