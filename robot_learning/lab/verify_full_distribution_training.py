"""Verify that training exposes the complete official target-radius range.

This is a focused Runner-check module.  It checks the training construction
against the contract independently of the training module's alias, then uses
seeded resets and short transitions to exercise the affected sampling and
environment lifecycle.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from contracts import task_spec
from robot_learning.training.environment import make_training_env


FORMER_TRAINING_LOWER_BOUND = 0.14
RESET_SAMPLE_COUNT = 256
TRANSITION_EPISODES = 8
TRANSITIONS_PER_EPISODE = 6


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _target_radius(env: Any) -> float:
    target = np.asarray(env.data.mocap_pos[0], dtype=np.float64)
    return float(np.linalg.norm(target[:2]))


def _check_observation(observation: Any, expected_shape: tuple[int, ...]) -> None:
    array = np.asarray(observation)
    _require(array.shape == expected_shape, "observation shape changed")
    _require(bool(np.all(np.isfinite(array))), "observation contains non-finite values")


def _check_reset(
    env: Any, seed: int, expected_shape: tuple[int, ...]
) -> tuple[np.ndarray, float]:
    observation, info = env.reset(seed=seed)
    _check_observation(observation, expected_shape)
    _require(isinstance(info, dict), "reset did not return an info mapping")
    return observation, _target_radius(env)


def _check_transition(
    env: Any, observation: np.ndarray, expected_shape: tuple[int, ...]
) -> np.ndarray:
    del observation
    action = np.zeros(env.action_space.shape, dtype=np.float32)
    _require(bool(env.action_space.contains(action)), "controlled action is invalid")
    next_observation, reward, terminated, truncated, info = env.step(action)
    _check_observation(next_observation, expected_shape)
    _require(bool(np.isfinite(reward)), "transition reward is non-finite")
    _require(
        isinstance(terminated, (bool, np.bool_))
        and isinstance(truncated, (bool, np.bool_)),
        "transition termination flags are not boolean",
    )
    _require(isinstance(info, dict), "transition did not return an info mapping")
    return next_observation


def run_check() -> dict[str, Any]:
    """Run the focused construction, sampling, reset, and transition checks."""
    expected_range = tuple(float(value) for value in task_spec.TARGET_RADIUS_RANGE)
    _require(len(expected_range) == 2, "official radius range is malformed")
    _require(expected_range[0] < expected_range[1], "official radius range is empty")

    env = make_training_env()
    try:
        configured_range = tuple(float(value) for value in env.target_radius_range)
        _require(
            configured_range == expected_range,
            "training environment does not use the official radius range",
        )

        expected_shape = tuple(env.observation_space.shape)
        radii: list[float] = []
        for seed in range(RESET_SAMPLE_COUNT):
            _, radius = _check_reset(env, seed, expected_shape)
            _require(
                expected_range[0] - 1e-12
                <= radius
                <= expected_range[1] + 1e-12,
                "reset sampled a radius outside the official bounds",
            )
            radii.append(radius)

        below_former_boundary = [
            radius for radius in radii if radius < FORMER_TRAINING_LOWER_BOUND
        ]
        at_or_above_former_boundary = [
            radius for radius in radii if radius >= FORMER_TRAINING_LOWER_BOUND
        ]
        _require(
            below_former_boundary,
            "seeded resets did not observe a radius below the former 14 cm boundary",
        )
        _require(
            at_or_above_former_boundary,
            "seeded resets did not observe a radius at or above the former boundary",
        )

        deterministic_reset_count = 0
        for seed in (0, RESET_SAMPLE_COUNT // 2, RESET_SAMPLE_COUNT - 1):
            first_observation, first_radius = _check_reset(
                env, seed, expected_shape
            )
            second_observation, second_radius = _check_reset(
                env, seed, expected_shape
            )
            _require(
                np.array_equal(first_observation, second_observation)
                and first_radius == second_radius,
                "identical reset seeds did not reproduce the reset state",
            )
            deterministic_reset_count += 1

        transition_count = 0
        reset_count = RESET_SAMPLE_COUNT + 2 * deterministic_reset_count
        for episode in range(TRANSITION_EPISODES):
            observation, _ = _check_reset(
                env, RESET_SAMPLE_COUNT + episode, expected_shape
            )
            reset_count += 1
            for _ in range(TRANSITIONS_PER_EPISODE):
                observation = _check_transition(env, observation, expected_shape)
                transition_count += 1

        return {
            "scope": "training environment target-radius construction and lifecycle",
            "expected": {
                "official_target_radius_range": list(expected_range),
                "former_training_lower_boundary": FORMER_TRAINING_LOWER_BOUND,
                "reset_sample_count": RESET_SAMPLE_COUNT,
                "transition_episodes": TRANSITION_EPISODES,
                "transitions_per_episode": TRANSITIONS_PER_EPISODE,
            },
            "observed": {
                "configured_target_radius_range": list(configured_range),
                "minimum_sampled_radius": min(radii),
                "maximum_sampled_radius": max(radii),
                "sampled_below_former_boundary": len(below_former_boundary),
                "sampled_at_or_above_former_boundary": len(
                    at_or_above_former_boundary
                ),
                "deterministic_reset_checks": deterministic_reset_count,
                "resets_checked": reset_count,
                "transitions_checked": transition_count,
            },
            "checked_scope": [
                "training construction range exactly matches contracts.task_spec.TARGET_RADIUS_RANGE",
                "repeated seeded reset samples remain within both official bounds",
                "seeded samples occur below and at or above the former 14 cm lower boundary",
                "repeated identical seeds reproduce reset observations and target radii",
                "short zero-action transitions return finite observations, finite rewards, boolean flags, and mappings",
            ],
            "unchecked_scope": [
                "uniformity beyond the sampled reset panel",
                "PPO learning behavior and candidate performance",
                "official evaluator outcomes and protected task mechanics",
                "target-angle coverage and between-observation dynamics",
            ],
        }
    finally:
        env.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="write the compact JSON check artifact to this path",
    )
    args = parser.parse_args(argv)

    artifact = run_check()
    if args.output is not None:
        args.output.write_text(
            json.dumps(artifact, separators=(",", ":"), sort_keys=True),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
