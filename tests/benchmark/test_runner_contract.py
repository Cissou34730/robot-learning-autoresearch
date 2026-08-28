import json

import pytest

from research.run_experiment import (
    IMMUTABLE_PATHS,
    MUTABLE_CODE_PATHS,
    MUTABLE_PATHS,
    append_result,
    assert_research_surface,
    finalist_directories,
    format_duration,
    latest_training_steps,
    load_state,
    validate_reusable_candidate,
)


def test_research_and_benchmark_surfaces_are_disjoint():
    assert set(IMMUTABLE_PATHS).isdisjoint(MUTABLE_PATHS)
    assert "robot_learning/environments/reach_env.py" in IMMUTABLE_PATHS
    assert "robot_learning/evaluate.py" in IMMUTABLE_PATHS
    assert "robot_learning/benchmark/spec.py" in IMMUTABLE_PATHS
    assert "tests/benchmark/test_task_contract.py" in IMMUTABLE_PATHS
    assert "tests" in MUTABLE_PATHS
    assert "research" in MUTABLE_PATHS
    assert "research/current_params.json" not in MUTABLE_CODE_PATHS


def test_fixed_objective_change_is_rejected_even_under_broad_code_surface(
    monkeypatch,
):
    monkeypatch.setattr(
        "research.run_experiment.status_paths",
        lambda _paths: ["robot_learning/benchmark/spec.py"],
    )

    with pytest.raises(ValueError, match="fixed objective"):
        assert_research_surface()


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
        resume=None,
        config=config,
    )


def test_finalist_manifest_exposes_three_complete_artifacts(tmp_path):
    finalists = []
    for number in range(3):
        relative = f"finalists/checkpoint-{number}"
        artifact_dir = tmp_path / relative
        artifact_dir.mkdir(parents=True)
        for filename in ("model.zip", "vecnormalize.pkl", "artifact.json"):
            (artifact_dir / filename).touch()
        finalists.append({"path": relative})
    (tmp_path / "selection_manifest.json").write_text(
        json.dumps({"finalists": finalists}), encoding="utf-8"
    )

    assert finalist_directories(tmp_path) == [
        tmp_path / item["path"] for item in finalists
    ]


def test_researcher_may_submit_more_than_three_finalists(tmp_path):
    finalists = []
    for number in range(5):
        relative = f"finalists/checkpoint-{number}"
        artifact_dir = tmp_path / relative
        artifact_dir.mkdir(parents=True)
        for filename in ("model.zip", "vecnormalize.pkl", "artifact.json"):
            (artifact_dir / filename).touch()
        finalists.append({"path": relative})
    (tmp_path / "selection_manifest.json").write_text(
        json.dumps({"finalists": finalists}), encoding="utf-8"
    )

    assert len(finalist_directories(tmp_path)) == 5
