import json

import pytest

from research.run_experiment import (
    IMMUTABLE_PATHS,
    MUTABLE_PATHS,
    append_result,
    format_duration,
    latest_training_steps,
    load_state,
    no_regression,
    rank,
    train_candidate_curriculum,
    validate_reusable_candidate,
)


def metrics(rates, closest):
    return {
        "stage_success_percent": rates,
        "closest_distance_cm": {"median": closest},
    }


def test_research_and_benchmark_surfaces_are_disjoint():
    assert set(IMMUTABLE_PATHS).isdisjoint(MUTABLE_PATHS)
    assert "robot_learning/environments/reach_env.py" in IMMUTABLE_PATHS
    assert "tests/benchmark" in IMMUTABLE_PATHS
    assert "tests/research" in MUTABLE_PATHS


def test_current_stage_success_precedes_distance():
    assert rank(metrics([80.0, 0.0], 4.0), 0) > rank(
        metrics([79.0, 0.0], 1.0), 0
    )


def test_previous_stage_regression_blocks_candidate():
    accepted = metrics([100.0, 70.0, 0.0], 2.0)
    candidate = metrics([99.0, 80.0, 0.0], 1.0)
    assert not no_regression(candidate, accepted, stage_index=1)


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
                "current_stage": 0,
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
            "stage_index": 0,
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
        '{"algorithm":"ppo","stage_index":1,"seed":0,"timesteps":120000,'
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

    try:
        validate_reusable_candidate(
            candidate,
            stage_index=0,
            timesteps=120_000,
            resume=None,
            config=config,
        )
    except ValueError as error:
        assert "stage" in str(error)
    else:
        raise AssertionError("mismatched candidate was accepted")


def test_curriculum_continues_one_candidate_across_stages(monkeypatch, tmp_path):
    candidate_root = tmp_path / "candidates"
    candidate_root.mkdir()
    output_dir = candidate_root / "experiment-1"
    calls = []

    def fake_train(output, stage, timesteps, seed, resume, **kwargs):
        calls.append((stage, timesteps, str(resume) if resume else None))
        output.mkdir()
        (output / "model.zip").touch()
        (output / "vecnormalize.pkl").touch()
        (output / "artifact.json").write_text(
            '{"algorithm":"ppo","timesteps":1}', encoding="utf-8"
        )

    monkeypatch.setattr("research.run_experiment.CANDIDATE_ROOT", candidate_root)
    monkeypatch.setattr("research.run_experiment.train_candidate", fake_train)

    train_candidate_curriculum(
        output_dir,
        [(0, 30_000), (1, 90_000)],
        seed=0,
        resume=None,
        baseline=False,
    )

    assert calls == [
        (0, 30_000, None),
        (1, 90_000, str(candidate_root / "experiment-1-part-1" / "model.zip")),
    ]
    artifact = json.loads(
        (output_dir / "artifact.json").read_text(encoding="utf-8")
    )
    assert artifact["timesteps"] == 120_000
    assert artifact["training_curriculum"] == [
        {"stage_index": 0, "timesteps": 30_000},
        {"stage_index": 1, "timesteps": 90_000},
    ]
    assert not (candidate_root / "experiment-1-part-1").exists()
