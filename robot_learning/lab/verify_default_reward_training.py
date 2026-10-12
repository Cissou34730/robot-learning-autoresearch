"""Defect-sensitive check for the fresh default-reward training route.

This module is intended for the ``python_module`` instrument.  It uses
controlled simulator states and a small independent reward reference to check
the training route without training or evaluating a learned policy.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import mujoco
import numpy as np

from robot_learning.scenario.environment import (
    TwoJointArmReachEnv,
    make_evaluation_env,
)
from robot_learning.training.environment import (
    TRAINING_TARGET_RADIUS_RANGE,
    make_training_env,
)


EXPECTED_DIRECT_PROFILE = "direct"
EXPECTED_DEFAULT_REWARD_PROFILE = "default"
EXPECTED_TRAINING_RADIUS_RANGE = (0.06, 0.20)
EXPECTED_OFFICIAL_RADIUS_RANGE = (0.06, 0.20)
EXPECTED_SUCCESS_THRESHOLD = 0.01
EXPECTED_HOLD_STEPS = 100

TARGETED_COMPONENTS = {
    "braking_weight",
    "targeted_joint_velocity",
    "targeted_endpoint_velocity",
    "targeted_action_regulation",
}

UNCHECKED_SCOPE = [
    "learned-policy performance, PPO behavior, and official evaluation success",
    "whether default reward shaping improves acquisition or hold performance",
    "causal scientific validity of the reward or of the training route",
    "compiled dynamics and transitions outside the controlled states exercised here",
]

EXPECTED_CHECKS = {
    "fresh_training_route": {
        "control_profile": EXPECTED_DIRECT_PROFILE,
        "reward_profile": EXPECTED_DEFAULT_REWARD_PROFILE,
        "target_radius_range": list(EXPECTED_TRAINING_RADIUS_RANGE),
    },
    "evaluation_default_route": {
        "control_profile": EXPECTED_DIRECT_PROFILE,
        "reward_profile": EXPECTED_DEFAULT_REWARD_PROFILE,
        "target_radius_range": list(EXPECTED_OFFICIAL_RADIUS_RANGE),
    },
    "sampled_radius_bounds": list(EXPECTED_TRAINING_RADIUS_RANGE),
    "hold_steps": EXPECTED_HOLD_STEPS,
    "targeted_components_absent": sorted(TARGETED_COMPONENTS),
}


class VerificationFailure(AssertionError):
    """A controlled laboratory check failed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationFailure(message)


def _expected_clipped_action(action: np.ndarray) -> np.ndarray:
    """Independent reference for direct control: only actuator bounds apply."""
    action = np.asarray(action, dtype=np.float64)
    return np.minimum(np.maximum(action, -1.0), 1.0)


def _set_changed_state(
    env: TwoJointArmReachEnv,
    qpos: tuple[float, float],
    qvel: tuple[float, float],
    radius: float,
    angle: float,
) -> None:
    env.data.qpos[:2] = qpos
    env.data.qvel[:2] = qvel
    mujoco.mj_forward(env.model, env.data)
    env.data.mocap_pos[0] = [
        radius * np.cos(angle),
        radius * np.sin(angle),
        float(env.data.site("end_effector").xpos[2]),
    ]
    mujoco.mj_forward(env.model, env.data)


def _check_routes(observed: dict[str, Any]) -> None:
    training = make_training_env()
    try:
        route = {
            "control_profile": training.control_profile,
            "reward_profile": training.reward_profile,
            "target_radius_range": list(training.target_radius_range),
        }
        _require(
            training.control_profile == EXPECTED_DIRECT_PROFILE,
            "fresh training control profile is not direct",
        )
        _require(
            training.reward_profile == EXPECTED_DEFAULT_REWARD_PROFILE,
            "fresh training reward profile is not default",
        )
        _require(
            tuple(training.target_radius_range)
            == EXPECTED_TRAINING_RADIUS_RANGE,
            "fresh training target range changed",
        )
        observed["fresh_training_route"] = route
    finally:
        training.close()

    evaluation = make_evaluation_env()
    try:
        route = {
            "control_profile": evaluation.control_profile,
            "reward_profile": evaluation.reward_profile,
            "target_radius_range": list(evaluation.target_radius_range),
        }
        _require(
            evaluation.control_profile == EXPECTED_DIRECT_PROFILE,
            "evaluation default control profile changed",
        )
        _require(
            evaluation.reward_profile == EXPECTED_DEFAULT_REWARD_PROFILE,
            "evaluation default reward profile changed",
        )
        _require(
            tuple(evaluation.target_radius_range)
            == EXPECTED_OFFICIAL_RADIUS_RANGE,
            "evaluation target range changed",
        )
        observed["evaluation_default_route"] = route
    finally:
        evaluation.close()


def _check_radius_sampling(observed: dict[str, Any]) -> None:
    env = make_training_env()
    try:
        _require(
            tuple(TRAINING_TARGET_RADIUS_RANGE)
            == EXPECTED_TRAINING_RADIUS_RANGE,
            "training radius constant changed",
        )
        samples = []
        for seed in (7, 19, 31, 43):
            env.reset(seed=seed)
            radius = float(np.linalg.norm(env.data.mocap_pos[0][:2]))
            _require(
                EXPECTED_TRAINING_RADIUS_RANGE[0]
                <= radius
                <= EXPECTED_TRAINING_RADIUS_RANGE[1],
                f"training reset sampled radius outside full range: {radius}",
            )
            samples.append({"seed": seed, "radius": radius})
        observed["full_radius_sampling"] = {
            "constant": list(TRAINING_TARGET_RADIUS_RANGE),
            "configured_range": list(env.target_radius_range),
            "samples": samples,
        }
    finally:
        env.close()


def _check_updates_and_resets(observed: dict[str, Any]) -> None:
    env = make_training_env()
    cases = (
        (
            "changed_state_one",
            (0.35, -0.20),
            (0.40, -0.30),
            0.12,
            -2.20,
            (1.40, -0.80),
        ),
        (
            "changed_state_two",
            (-0.80, 0.80),
            (-0.25, 0.60),
            0.16,
            0.70,
            (0.30, -1.45),
        ),
        (
            "changed_state_three",
            (1.10, -0.35),
            (1.10, -0.90),
            0.10,
            -2.50,
            (-1.20, 1.30),
        ),
    )
    records = []
    try:
        for seed, case in zip((11, 23, 37), cases):
            env.reset(seed=seed)
            _require(
                np.allclose(env.data.qpos[:2], 0.0)
                and np.allclose(env.data.qvel[:2], 0.0)
                and env._held_steps == 0
                and not env._outside_after_hold,
                f"reset {seed} did not restore qpos, qvel, and hold state",
            )
            label, qpos, qvel, radius, angle, raw_action = case
            _set_changed_state(env, qpos, qvel, radius, angle)
            env._held_steps = 7
            env._outside_after_hold = True
            action = np.asarray(raw_action, dtype=np.float64)
            transition = env.step(action)
            _require(
                np.allclose(
                    env.data.ctrl,
                    _expected_clipped_action(action),
                    atol=1.0e-12,
                ),
                f"{label} did not use independent direct clipping",
            )
            _require(
                not TARGETED_COMPONENTS.intersection(
                    transition[4]["reward_components"]
                ),
                f"{label} exposed targeted reward components",
            )
            observed_control = env.data.ctrl.copy()

            reset_seed = seed + 100
            env.reset(seed=reset_seed)
            _require(
                np.allclose(env.data.qpos[:2], 0.0)
                and np.allclose(env.data.qvel[:2], 0.0)
                and env._held_steps == 0
                and not env._outside_after_hold,
                f"repeated reset {reset_seed} did not restore simulator state",
            )
            records.append(
                {
                    "label": label,
                    "seed": seed,
                    "raw_action": action.tolist(),
                    "clipped_control": observed_control.tolist(),
                    "reward_components": transition[4]["reward_components"],
                    "reset_seed": reset_seed,
                    "reset_qpos": env.data.qpos[:2].tolist(),
                    "reset_qvel": env.data.qvel[:2].tolist(),
                    "reset_held_steps": env._held_steps,
                }
            )
        observed["changed_state_updates_and_repeated_resets"] = records
    finally:
        env.close()


def _reference_default_reward(
    previous_distance: float,
    current_distance: float,
    held_steps: int,
    previous_held_steps: int,
    *,
    outside: bool,
) -> dict[str, float]:
    """Reference values for the zero-action cases below, independent of calls."""
    progress = 10.0 * (previous_distance - current_distance)
    closeness = 4.0 * (
        np.exp(-current_distance / 0.05)
        - np.exp(-previous_distance / 0.05)
    )
    hold_progress = 0.5 * (held_steps - previous_held_steps)
    if held_steps == 0 and previous_held_steps > 0:
        hold_progress = 0.0
    outside_band = 0.0
    if outside and current_distance > EXPECTED_SUCCESS_THRESHOLD:
        outside_band = -0.1 * min(
            (current_distance - EXPECTED_SUCCESS_THRESHOLD) / 0.01,
            1.0,
        )
    return {
        "progress": float(progress),
        "closeness": float(closeness),
        "hold_progress": float(hold_progress),
        "outside_band": float(outside_band),
        "hold_complete": 0.0,
        "action_cost": 0.0,
    }


def _controlled_transition(
    env: TwoJointArmReachEnv,
    current_distance: float,
) -> tuple[np.ndarray, float, bool, bool, dict[str, Any]]:
    original_distance = env._distance_to_target
    env._distance_to_target = lambda: current_distance
    try:
        return env.step(np.zeros(2, dtype=np.float32))
    finally:
        env._distance_to_target = original_distance


def _check_reward_consequences(observed: dict[str, Any]) -> None:
    env = make_training_env()
    try:
        env.reset(seed=61)

        env._previous_distance = 0.08
        env._held_steps = 0
        env._outside_after_hold = False
        acquisition = _controlled_transition(env, 0.04)

        env._previous_distance = 0.008
        env._held_steps = 0
        env._outside_after_hold = False
        hold_update = _controlled_transition(env, 0.008)

        env._previous_distance = 0.008
        env._held_steps = 3
        env._outside_after_hold = False
        interruption = _controlled_transition(env, 0.02)

        cases = (
            (
                "acquisition",
                acquisition,
                _reference_default_reward(0.08, 0.04, 0, 0, outside=False),
            ),
            (
                "hold_update",
                hold_update,
                _reference_default_reward(0.008, 0.008, 1, 0, outside=False),
            ),
            (
                "interruption",
                interruption,
                _reference_default_reward(0.008, 0.02, 0, 3, outside=True),
            ),
        )
        records = {}
        for label, transition, expected in cases:
            components = transition[4]["reward_components"]
            _require(
                not TARGETED_COMPONENTS.intersection(components),
                f"{label} used targeted velocity/action reward terms",
            )
            for name, expected_value in expected.items():
                _require(
                    np.isclose(components[name], expected_value, atol=1.0e-12),
                    f"{label} {name} differs from independent reference",
                )
            expected_total = float(sum(expected.values()))
            _require(
                np.isclose(transition[1], expected_total, atol=1.0e-12),
                f"{label} total differs from independent reference",
            )
            records[label] = {
                "observed": {
                    "total": transition[1],
                    "components": components,
                    "held_steps": transition[4]["held_steps"],
                },
                "expected": {
                    "total": expected_total,
                    "components": expected,
                },
            }

        _require(
            acquisition[4]["held_steps"] == 0
            and acquisition[4]["reward_components"]["progress"] > 0.0,
            "acquisition did not produce progress without hold credit",
        )
        _require(
            hold_update[4]["held_steps"] == 1
            and hold_update[4]["reward_components"]["hold_progress"] == 0.5,
            "in-tolerance update did not produce the first hold increment",
        )
        _require(
            interruption[4]["held_steps"] == 0
            and not interruption[2]
            and interruption[4]["reward_components"]["outside_band"] < 0.0,
            "interruption did not reset hold without terminating",
        )
        observed["default_reward_consequences"] = records
    finally:
        env.close()


def _check_complete_hold_and_interruption(observed: dict[str, Any]) -> None:
    env = make_training_env()
    try:
        env.reset(seed=71)
        original_distance = env._distance_to_target
        distances = iter([0.005] * EXPECTED_HOLD_STEPS)
        env._distance_to_target = lambda: next(distances)
        hold_transitions = []
        try:
            for index in range(EXPECTED_HOLD_STEPS):
                transition = env.step(np.zeros(2, dtype=np.float32))
                hold_transitions.append(transition)
                if index < EXPECTED_HOLD_STEPS - 1:
                    _require(
                        not transition[2],
                        "uninterrupted hold terminated before its final step",
                    )
                _require(
                    not TARGETED_COMPONENTS.intersection(
                        transition[4]["reward_components"]
                    ),
                    "uninterrupted hold used targeted reward components",
                )
        finally:
            env._distance_to_target = original_distance

        final_transition = hold_transitions[-1]
        _require(
            final_transition[2]
            and final_transition[4]["held_steps"] == EXPECTED_HOLD_STEPS,
            "complete uninterrupted hold did not terminate at 100 steps",
        )

        env.reset(seed=72)
        _require(
            np.allclose(env.data.qpos[:2], 0.0)
            and np.allclose(env.data.qvel[:2], 0.0)
            and env._held_steps == 0,
            "reset after completed hold did not restore state",
        )
        original_distance = env._distance_to_target
        distances = iter((0.005, 0.02))
        env._distance_to_target = lambda: next(distances)
        try:
            first_hold = env.step(np.zeros(2, dtype=np.float32))
            interrupted = env.step(np.zeros(2, dtype=np.float32))
        finally:
            env._distance_to_target = original_distance
        _require(
            first_hold[4]["held_steps"] == 1 and not first_hold[2],
            "post-reset in-tolerance transition did not start a hold",
        )
        _require(
            interrupted[4]["held_steps"] == 0
            and not interrupted[2]
            and interrupted[4]["reward_components"]["outside_band"] < 0.0,
            "post-reset interruption did not reset hold state",
        )
        _require(
            not TARGETED_COMPONENTS.intersection(
                interrupted[4]["reward_components"]
            ),
            "post-reset interruption used targeted reward components",
        )

        env.data.qpos[:2] = (0.4, -0.3)
        env.data.qvel[:2] = (0.2, -0.1)
        env._held_steps = 8
        env._outside_after_hold = True
        mujoco.mj_forward(env.model, env.data)
        env.reset(seed=73)
        _require(
            np.allclose(env.data.qpos[:2], 0.0)
            and np.allclose(env.data.qvel[:2], 0.0)
            and env._held_steps == 0
            and not env._outside_after_hold,
            "reset after interruption did not clear qpos, qvel, and hold state",
        )
        observed["complete_hold_then_interruption_reset"] = {
            "complete_hold": {
                "steps": EXPECTED_HOLD_STEPS,
                "final_held_steps": final_transition[4]["held_steps"],
                "terminated": final_transition[2],
            },
            "interruption": {
                "held_steps": interrupted[4]["held_steps"],
                "terminated": interrupted[2],
                "outside_band": interrupted[4]["reward_components"][
                    "outside_band"
                ],
            },
            "final_reset": {
                "qpos": env.data.qpos[:2].tolist(),
                "qvel": env.data.qvel[:2].tolist(),
                "held_steps": env._held_steps,
                "outside_after_hold": env._outside_after_hold,
            },
        }
    finally:
        env.close()


def run_checks() -> dict[str, Any]:
    observed: dict[str, Any] = {}
    _check_routes(observed)
    _check_radius_sampling(observed)
    _check_updates_and_resets(observed)
    _check_reward_consequences(observed)
    _check_complete_hold_and_interruption(observed)
    return {
        "status": "passed",
        "observed_vs_expected": observed,
        "expected": EXPECTED_CHECKS,
        "checked_scope": [
            "fresh full-radius training target sampling bounds",
            "fresh training direct control and default reward route",
            "evaluation direct/default route and official target range",
            "repeated changed-state training updates with independently clipped actions",
            "repeated qpos, qvel, and hold-state resets",
            "default acquisition, hold, and interruption reward consequences",
            "complete uninterrupted 100-step hold followed by interruption and reset",
        ],
        "unchecked_scope": UNCHECKED_SCOPE,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    args = parser.parse_args(argv)

    try:
        report = run_checks()
    except Exception as error:
        report = {
            "status": "failed",
            "observed_vs_expected": {
                "error_type": type(error).__name__,
                "error": str(error),
            },
            "expected": EXPECTED_CHECKS,
            "checked_scope": [
                "default-reward training-route checks up to the first failure"
            ],
            "unchecked_scope": [
                "checks after the first failure",
                *UNCHECKED_SCOPE,
            ],
        }
        args.artifact.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        raise VerificationFailure(str(error))

    args.artifact.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
