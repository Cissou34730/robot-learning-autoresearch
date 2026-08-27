from research.run_experiment import (
    IMMUTABLE_PATHS,
    MUTABLE_PATHS,
    format_duration,
    latest_training_steps,
    no_regression,
    rank,
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
