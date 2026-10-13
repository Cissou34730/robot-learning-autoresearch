"""Artifact-independent verification for the hold-reward intervention."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from contracts.task_spec import TARGET_RADIUS_RANGE
from robot_learning.training.environment import make_training_env
from robot_learning.training.reward import (
    ACTION_COST_COEFFICIENT,
    HOLD_ACTION_COST_COEFFICIENT,
    HOLD_EXIT_FORFEIT_FRACTION,
    HOLD_PROGRESS_BONUS,
    reach_reward,
)

HOLD_STEPS_REQUIRED = 100
ACTION = np.asarray([0.5, -0.25], dtype=np.float64)
ACTION_SQUARED_SUM = float(np.sum(np.square(ACTION)))


def _write_report(artifact: str, report: dict[str, Any]) -> None:
    Path(artifact).write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _assert_close(actual: float, expected: float, label: str) -> None:
    assert np.isclose(actual, expected), (
        f"{label} mismatch: {actual!r} != {expected!r}"
    )


def _verify_reward_terms(artifact: str) -> None:
    no_hold = reach_reward(
        0.02,
        0.02,
        0.01,
        ACTION,
        held_steps=0,
        previous_held_steps=0,
        hold_steps_required=HOLD_STEPS_REQUIRED,
    )
    _assert_close(no_hold.components["hold_action_cost"], 0.0, "no-hold cost")

    hold_step = reach_reward(
        0.02,
        0.02,
        0.01,
        ACTION,
        held_steps=2,
        previous_held_steps=1,
        hold_steps_required=HOLD_STEPS_REQUIRED,
    )
    expected_hold_action_cost = -HOLD_ACTION_COST_COEFFICIENT * ACTION_SQUARED_SUM
    _assert_close(
        hold_step.components["hold_action_cost"],
        expected_hold_action_cost,
        "hold-step action cost",
    )

    exit_step = reach_reward(
        0.02,
        0.02,
        0.01,
        ACTION,
        held_steps=0,
        previous_held_steps=3,
        hold_steps_required=HOLD_STEPS_REQUIRED,
    )
    expected_hold_forfeiture = -(
        HOLD_EXIT_FORFEIT_FRACTION
        * HOLD_PROGRESS_BONUS
        * (3 / HOLD_STEPS_REQUIRED)
    )
    _assert_close(
        exit_step.components["hold_progress"],
        expected_hold_forfeiture,
        "exit hold-progress forfeiture",
    )
    _assert_close(
        exit_step.components["hold_action_cost"],
        expected_hold_action_cost,
        "exit-step action cost",
    )
    _assert_close(
        exit_step.components["action_cost"],
        -ACTION_COST_COEFFICIENT * ACTION_SQUARED_SUM,
        "general action cost",
    )
    _assert_close(
        exit_step.total,
        sum(exit_step.components.values()),
        "exit total attribution",
    )

    _write_report(
        artifact,
        {
            "check": "hold_reward_terms",
            "artifact_independent": True,
            "hold_exit_forfeit_fraction": float(HOLD_EXIT_FORFEIT_FRACTION),
            "hold_action_cost_coefficient": float(HOLD_ACTION_COST_COEFFICIENT),
            "action_squared_sum": ACTION_SQUARED_SUM,
            "no_hold_action_cost": no_hold.components["hold_action_cost"],
            "hold_step_action_cost": hold_step.components["hold_action_cost"],
            "exit_hold_progress": exit_step.components["hold_progress"],
            "exit_hold_action_cost": exit_step.components["hold_action_cost"],
            "general_action_cost_unchanged": True,
        },
    )


def _target_radius(env: Any) -> float:
    target = np.asarray(env.data.mocap_pos[0], dtype=np.float64)
    return float(np.linalg.norm(target[:2]))


def _verify_production_path_compatibility(artifact: str) -> None:
    """Exercise the training builder and Gym reset/step path without an artifact."""
    training_env = make_training_env()
    try:
        expected_range = tuple(float(value) for value in TARGET_RADIUS_RANGE)
        training_range = tuple(float(value) for value in training_env.target_radius_range)
        assert training_range == expected_range, (
            "training target distribution must be the full official range: "
            f"{training_range!r} != {expected_range!r}"
        )

        sampled_radii = []
        for seed in range(8):
            reset_observation, reset_info = training_env.reset(seed=seed)
            assert training_env.observation_space.contains(reset_observation)
            assert reset_info == {}
            sampled_radii.append(_target_radius(training_env))

            step_result = training_env.step(
                np.zeros(training_env.action_space.shape, dtype=np.float32)
            )
            assert len(step_result) == 5
            assert training_env.observation_space.contains(step_result[0])

        assert all(
            expected_range[0] <= radius <= expected_range[1]
            for radius in sampled_radii
        ), "a reset target fell outside the configured training range"

        _write_report(
            artifact,
            {
                "check": "production_path_compatibility",
                "artifact_independent": True,
                "training_target_radius_range": [
                    float(expected_range[0]),
                    float(expected_range[1]),
                ],
                "sample_count": len(sampled_radii),
                "sample_seed_range": [0, len(sampled_radii) - 1],
                "sampled_radius_min": min(sampled_radii),
                "sampled_radius_max": max(sampled_radii),
                "training_reset_and_step_api": "compatible",
                "all_samples_within_training_range": True,
            },
        )
    finally:
        training_env.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--compatibility", action="store_true")
    args = parser.parse_args()

    if args.compatibility:
        _verify_production_path_compatibility(args.artifact)
    else:
        _verify_reward_terms(args.artifact)


if __name__ == "__main__":
    main()
