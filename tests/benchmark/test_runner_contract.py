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
    rank,
    select_tournament_winner,
    summarize_tournament,
    tournament_result_is_close,
    validate_reusable_candidate,
)


def evaluation(seed, success, failures, longest, inside, excess):
    return {
        "episodes": 200,
        "seed": seed,
        "success_percent": success,
        "failed_episode_progress": {
            "failed_episodes": failures,
            "longest_consecutive_steps_mean": longest,
            "best_window_inside_steps_mean": inside,
            "best_window_excess_cm_mean": excess,
            "required_steps": 100,
        },
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


def tournament(*evaluations):
    return summarize_tournament(list(evaluations))


def test_seeds_passing_precede_other_tournament_metrics():
    robust = tournament(
        evaluation(1000, 98.0, 4, 20, 80, 2),
        evaluation(3000, 98.0, 4, 20, 80, 2),
    )
    fragile = tournament(
        evaluation(1000, 100.0, 0, 100, 100, 0),
        evaluation(3000, 97.5, 5, 99, 99, 0.01),
    )
    assert rank(robust) > rank(fragile)


def test_worst_seed_precedes_pooled_success():
    balanced = tournament(
        evaluation(1000, 99.0, 2, 10, 20, 3),
        evaluation(3000, 99.0, 2, 10, 20, 3),
    )
    uneven = tournament(
        evaluation(1000, 100.0, 0, 100, 100, 0),
        evaluation(3000, 98.5, 3, 99, 99, 0.01),
    )
    assert rank(balanced) > rank(uneven)


def test_failed_hold_progress_breaks_a_success_tie():
    almost = tournament(evaluation(1000, 98.0, 4, 99, 99, 0.01))
    distant = tournament(evaluation(1000, 98.0, 4, 20, 80, 10.0))
    assert rank(almost) > rank(distant)


def test_close_tournament_result_requests_more_evidence():
    first = tournament(evaluation(1000, 98.5, 3, 99, 99, 0.01))
    second = tournament(evaluation(1000, 98.0, 4, 90, 95, 1.0))
    assert tournament_result_is_close(first, second)


def test_exact_tournament_tie_keeps_the_champion():
    summary = tournament(evaluation(1000, 98.5, 3, 99, 99, 0.01))
    winner = select_tournament_winner(
        [
            {"name": "candidate", "kind": "candidate", "summary": summary},
            {"name": "champion", "kind": "champion", "summary": summary},
        ]
    )

    assert winner["name"] == "champion"


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
