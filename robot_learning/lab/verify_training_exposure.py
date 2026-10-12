"""Executable checks for the training target-radius exposure correction."""

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from contracts.task_spec import (
    FRAME_SKIP,
    HOLD_SECONDS,
    MAX_EPISODE_STEPS,
    SUCCESS_THRESHOLD,
    TARGET_RADIUS_RANGE,
)
from robot_learning.scenario.environment import make_evaluation_env
from robot_learning.training.environment import make_training_env


RESET_COUNT = 256
NEAR_REGION_WIDTH = 0.01
SEED_START = 10_000


def _write_json(output: Path, payload: dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _target_radius(env: Any) -> float:
    target_xy = np.asarray(env.data.mocap_pos[0][:2], dtype=float)
    return float(np.linalg.norm(target_xy))


def _reset_observation_check(env: Any, seed: int) -> dict[str, Any]:
    observation, _ = env.reset(seed=seed)
    return {
        "observation_shape": list(observation.shape),
        "observation_finite": bool(np.isfinite(observation).all()),
        "step_count_after_reset": int(env._step_count),
        "held_steps_after_reset": int(env._held_steps),
    }


def _behavioral_check() -> dict[str, Any]:
    expected_low, expected_high = TARGET_RADIUS_RANGE
    training_env = make_training_env()
    evaluation_env = make_evaluation_env()
    try:
        configured_range = tuple(
            float(value) for value in training_env.target_radius_range
        )
        configured_range_passed = configured_range == TARGET_RADIUS_RANGE

        radii: list[float] = []
        reset_observations: list[dict[str, Any]] = []
        for offset in range(RESET_COUNT):
            reset_observations.append(
                _reset_observation_check(training_env, SEED_START + offset)
            )
            radii.append(_target_radius(training_env))

        within_interval = all(
            expected_low <= radius <= expected_high for radius in radii
        )
        near_lower_count = sum(
            radius <= expected_low + NEAR_REGION_WIDTH for radius in radii
        )
        near_upper_count = sum(
            radius >= expected_high - NEAR_REGION_WIDTH for radius in radii
        )
        exposure_passed = (
            len(radii) == RESET_COUNT
            and within_interval
            and near_lower_count > 0
            and near_upper_count > 0
            and all(
                reset["observation_finite"]
                and reset["step_count_after_reset"] == 0
                and reset["held_steps_after_reset"] == 0
                for reset in reset_observations
            )
        )

        transition_observation, transition_reward, terminated, truncated, info = (
            training_env.step(np.zeros(training_env.action_space.shape, dtype=np.float32))
        )
        transition = {
            "observation_shape": list(transition_observation.shape),
            "observation_finite": bool(np.isfinite(transition_observation).all()),
            "reward_finite": bool(np.isfinite(transition_reward)),
            "terminated_type": type(terminated).__name__,
            "truncated_type": type(truncated).__name__,
            "info_has_distance": "distance" in info,
            "step_count_after_one_step": int(training_env._step_count),
        }
        transition_passed = (
            transition["observation_shape"]
            == reset_observations[0]["observation_shape"]
            and transition["observation_finite"]
            and transition["reward_finite"]
            and transition["terminated_type"] == "bool"
            and transition["truncated_type"] == "bool"
            and transition["info_has_distance"]
            and transition["step_count_after_one_step"] == 1
            and training_env.frame_skip == FRAME_SKIP
            and training_env.max_episode_steps == MAX_EPISODE_STEPS
            and training_env.success_threshold == SUCCESS_THRESHOLD
        )

        reset_after_step = _reset_observation_check(training_env, SEED_START)
        reset_transition_passed = (
            reset_after_step["step_count_after_reset"] == 0
            and reset_after_step["held_steps_after_reset"] == 0
            and reset_after_step["observation_finite"]
        )

        evaluation_range = tuple(
            float(value) for value in evaluation_env.target_radius_range
        )
        expected_hold_steps = round(
            HOLD_SECONDS / (evaluation_env.model.opt.timestep * FRAME_SKIP)
        )
        evaluation_reset = _reset_observation_check(evaluation_env, SEED_START + 1)
        evaluation_radius = _target_radius(evaluation_env)
        (
            evaluation_transition_observation,
            _,
            evaluation_terminated,
            evaluation_truncated,
            evaluation_info,
        ) = evaluation_env.step(
            np.zeros(evaluation_env.action_space.shape, dtype=np.float32)
        )
        evaluation_semantics = {
            "range": evaluation_range,
            "max_episode_steps": int(evaluation_env.max_episode_steps),
            "frame_skip": int(evaluation_env.frame_skip),
            "success_threshold": float(evaluation_env.success_threshold),
            "hold_steps_required": int(evaluation_env.hold_steps_required),
            "reset_radius": evaluation_radius,
            "reset_observation_finite": evaluation_reset["observation_finite"],
            "transition_observation_finite": bool(
                np.isfinite(evaluation_transition_observation).all()
            ),
            "transition_types": [
                type(evaluation_terminated).__name__,
                type(evaluation_truncated).__name__,
            ],
            "transition_info_has_distance": "distance" in evaluation_info,
        }
        evaluation_passed = (
            evaluation_range == TARGET_RADIUS_RANGE
            and evaluation_env.max_episode_steps == MAX_EPISODE_STEPS
            and evaluation_env.frame_skip == FRAME_SKIP
            and evaluation_env.success_threshold == SUCCESS_THRESHOLD
            and evaluation_env.hold_steps_required == expected_hold_steps
            and expected_low <= evaluation_radius <= expected_high
            and evaluation_semantics["reset_observation_finite"]
            and evaluation_semantics["transition_observation_finite"]
            and evaluation_semantics["transition_types"] == ["bool", "bool"]
            and evaluation_semantics["transition_info_has_distance"]
        )

        checks = {
            "configured_training_interval": {
                "observed": configured_range,
                "expected": TARGET_RADIUS_RANGE,
                "passed": configured_range_passed,
            },
            "repeated_training_resets": {
                "observed": {
                    "reset_count": len(radii),
                    "minimum_radius": min(radii),
                    "maximum_radius": max(radii),
                    "near_lower_count": near_lower_count,
                    "near_upper_count": near_upper_count,
                    "all_radii_within_interval": within_interval,
                    "all_resets_reinitialized_counters": all(
                        reset["step_count_after_reset"] == 0
                        and reset["held_steps_after_reset"] == 0
                        for reset in reset_observations
                    ),
                },
                "expected": {
                    "reset_count": RESET_COUNT,
                    "interval": TARGET_RADIUS_RANGE,
                    "near_lower_region": [
                        expected_low,
                        expected_low + NEAR_REGION_WIDTH,
                    ],
                    "near_upper_region": [
                        expected_high - NEAR_REGION_WIDTH,
                        expected_high,
                    ],
                    "at_least_one_sample_in_each_near_region": True,
                },
                "passed": exposure_passed,
            },
            "training_transition_and_reset": {
                "observed": {
                    "one_step": transition,
                    "reset_after_step": reset_after_step,
                },
                "expected": {
                    "one_step_completed": True,
                    "observation_shape_unchanged": True,
                    "step_count_after_one_step": 1,
                    "reset_clears_step_and_hold_counters": True,
                    "frame_skip": FRAME_SKIP,
                    "max_episode_steps": MAX_EPISODE_STEPS,
                    "success_threshold": SUCCESS_THRESHOLD,
                },
                "passed": transition_passed and reset_transition_passed,
            },
            "evaluation_environment_separation": {
                "observed": evaluation_semantics,
                "expected": {
                    "range": TARGET_RADIUS_RANGE,
                    "max_episode_steps": MAX_EPISODE_STEPS,
                    "frame_skip": FRAME_SKIP,
                    "success_threshold": SUCCESS_THRESHOLD,
                    "hold_steps_required": expected_hold_steps,
                    "reset_and_one_step_complete": True,
                },
                "passed": evaluation_passed,
            },
        }
        if not all(check["passed"] for check in checks.values()):
            raise AssertionError("training exposure verification failed")
        return {
            "schema_version": 1,
            "mode": "behavioral_check",
            "status": "passed",
            "checks": checks,
            "checked_scope": [
                "exact training target-radius configuration",
                "256 controlled-seed training resets and independent target-position radii",
                "near-lower and near-upper exposure evidence",
                "training step transition followed by reset reinitialization",
                "separate evaluation construction, official range, timing, and success parameters",
                "evaluation reset and one-step production transition",
            ],
            "unchecked_scope": [
                "statistical uniformity beyond bounded reset coverage",
                "policy learning or performance under either distribution",
                "protected evaluator implementation and official 200-episode outcomes",
                "physical validity of the scenario model",
            ],
        }
    finally:
        training_env.close()
        evaluation_env.close()


def _compatibility_check() -> dict[str, Any]:
    env = make_training_env()
    try:
        observation, _ = env.reset(seed=SEED_START)
        next_observation, reward, terminated, truncated, info = env.step(
            np.zeros(env.action_space.shape, dtype=np.float32)
        )
        observed = {
            "configured_range": tuple(
                float(value) for value in env.target_radius_range
            ),
            "reset_observation_finite": bool(np.isfinite(observation).all()),
            "step_observation_finite": bool(np.isfinite(next_observation).all()),
            "reward_finite": bool(np.isfinite(reward)),
            "termination_types": [
                type(terminated).__name__,
                type(truncated).__name__,
            ],
            "step_info_has_distance": "distance" in info,
        }
        expected = {
            "configured_range": TARGET_RADIUS_RANGE,
            "reset_and_step_complete": True,
            "finite_observations_and_reward": True,
            "termination_types": ["bool", "bool"],
            "step_info_has_distance": True,
        }
        passed = (
            observed["configured_range"] == TARGET_RADIUS_RANGE
            and observed["reset_observation_finite"]
            and observed["step_observation_finite"]
            and observed["reward_finite"]
            and observed["termination_types"] == ["bool", "bool"]
            and observed["step_info_has_distance"]
        )
        if not passed:
            raise AssertionError("training environment compatibility check failed")
        return {
            "schema_version": 1,
            "mode": "compatibility_check",
            "status": "passed",
            "observed": observed,
            "expected": expected,
            "checked_scope": [
                "training environment construction through the production factory",
                "Gymnasium reset and one native environment step with controlled input",
            ],
            "unchecked_scope": [
                "repeated-reset exposure coverage",
                "separate evaluation semantics",
                "policy artifacts and long-horizon behavior",
            ],
        }
    finally:
        env.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("check", "compatibility"), default="check")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = (
            _behavioral_check()
            if args.mode == "check"
            else _compatibility_check()
        )
    except Exception as error:
        _write_json(
            args.output,
            {
                "schema_version": 1,
                "mode": f"{args.mode}_check",
                "status": "failed",
                "error_type": type(error).__name__,
                "error": str(error),
                "unchecked_scope": [
                    "checks after the first failed production-path operation"
                ],
            },
        )
        raise
    _write_json(args.output, payload)


if __name__ == "__main__":
    main()
