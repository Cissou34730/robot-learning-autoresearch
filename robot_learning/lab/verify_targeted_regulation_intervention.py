"""Executable checks for the training-only targeted regulation profile.

This is a laboratory check, not a scientific validity claim.  It uses
controlled reward inputs and small environment transition probes so that
velocity arguments, profile selection, and hold/reset semantics are tested
independently of a learned policy.
"""

import argparse
import json
from pathlib import Path

import numpy as np

from contracts.task_spec import (
    FRAME_SKIP,
    HOLD_SECONDS,
    MAX_EPISODE_STEPS,
    SUCCESS_THRESHOLD,
    TARGET_RADIUS_RANGE,
)
from robot_learning.scenario.environment import (
    TwoJointArmReachEnv,
    make_evaluation_env,
)
from robot_learning.training.environment import (
    TRAINING_TARGET_RADIUS_RANGE,
    make_training_env,
)
from robot_learning.training.reward import (
    BRAKING_DISTANCE,
    DEFAULT_REWARD_PROFILE,
    TARGETED_REGULATION_PROFILE,
    reach_reward,
)


class VerificationFailure(AssertionError):
    """A defect-sensitive laboratory check failed."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationFailure(message)


def _targeted(
    distance: float,
    *,
    joint_velocity: tuple[float, float] = (0.1, -0.1),
    endpoint_velocity: float = 0.01,
    action: tuple[float, float] = (0.2, -0.2),
    held_steps: int = 0,
    previous_held_steps: int = 0,
):
    return reach_reward(
        distance,
        distance,
        SUCCESS_THRESHOLD,
        np.asarray(action, dtype=np.float64),
        held_steps=held_steps,
        previous_held_steps=previous_held_steps,
        hold_steps_required=100,
        reward_profile=TARGETED_REGULATION_PROFILE,
        joint_velocity=np.asarray(joint_velocity, dtype=np.float64),
        endpoint_velocity=endpoint_velocity,
    )


def _check_velocity_sensitivity() -> dict:
    low = _targeted(
        0.03,
        joint_velocity=(0.01, -0.01),
        endpoint_velocity=0.001,
    )
    high = _targeted(
        0.03,
        joint_velocity=(8.0, -8.0),
        endpoint_velocity=1.0,
    )
    _require(high.total < low.total, "high velocity did not reduce targeted reward")
    _require(
        high.components["targeted_joint_velocity"]
        < low.components["targeted_joint_velocity"],
        "joint velocity argument was ignored",
    )
    _require(
        high.components["targeted_endpoint_velocity"]
        < low.components["targeted_endpoint_velocity"],
        "endpoint velocity argument was ignored",
    )
    return {
        "low_total": low.total,
        "high_total": high.total,
        "low_joint_penalty": low.components["targeted_joint_velocity"],
        "high_joint_penalty": high.components["targeted_joint_velocity"],
        "low_endpoint_penalty": low.components["targeted_endpoint_velocity"],
        "high_endpoint_penalty": high.components["targeted_endpoint_velocity"],
    }


def _reference_smoothstep(value: float) -> float:
    value = float(np.clip(value, 0.0, 1.0))
    return value * value * (3.0 - 2.0 * value)


def _check_braking_and_holding() -> dict:
    _require(
        BRAKING_DISTANCE > SUCCESS_THRESHOLD,
        "braking distance must be outside the success boundary",
    )
    midpoint = (BRAKING_DISTANCE + SUCCESS_THRESHOLD) / 2.0
    distances = (
        BRAKING_DISTANCE + 0.01,
        BRAKING_DISTANCE,
        midpoint,
        SUCCESS_THRESHOLD,
    )
    rewards = [_targeted(distance, endpoint_velocity=0.4) for distance in distances]
    observed_weights = [item.components["braking_weight"] for item in rewards]
    expected_weights = [
        _reference_smoothstep(
            (BRAKING_DISTANCE - distance)
            / (BRAKING_DISTANCE - SUCCESS_THRESHOLD)
        )
        for distance in distances
    ]
    _require(
        np.allclose(observed_weights, expected_weights, atol=1e-12),
        "braking weight did not follow the smooth distance reference",
    )
    _require(
        observed_weights[0] == 0.0
        and 0.0 < observed_weights[2] < observed_weights[3],
        "braking weighting was not inactive outside and active toward the target",
    )
    endpoint_penalties = [
        item.components["targeted_endpoint_velocity"] for item in rewards
    ]
    action_penalties = [
        item.components["targeted_action_regulation"] for item in rewards
    ]
    _require(
        endpoint_penalties[0] == 0.0
        and endpoint_penalties[-1] < endpoint_penalties[2] < endpoint_penalties[1],
        "endpoint regulation did not increase toward the target",
    )
    _require(
        action_penalties[0] == 0.0
        and action_penalties[-1] < action_penalties[2] < action_penalties[1],
        "action regulation did not increase toward the target",
    )

    held = [
        _targeted(
            SUCCESS_THRESHOLD / 2.0,
            endpoint_velocity=0.4,
            held_steps=held,
            previous_held_steps=held - 1,
        )
        for held in (1, 2, 99)
    ]
    _require(
        all(item.components["targeted_endpoint_velocity"] < 0.0 for item in held),
        "endpoint regulation was inactive during repeated held steps",
    )
    _require(
        all(item.components["targeted_action_regulation"] < 0.0 for item in held),
        "action regulation was inactive during repeated held steps",
    )
    return {
        "distances": list(distances),
        "observed_braking_weights": observed_weights,
        "expected_braking_weights": expected_weights,
        "endpoint_penalties": endpoint_penalties,
        "action_penalties": action_penalties,
        "held_endpoint_penalties": [
            item.components["targeted_endpoint_velocity"] for item in held
        ],
        "held_action_penalties": [
            item.components["targeted_action_regulation"] for item in held
        ],
    }


def _check_default_path_and_profiles() -> dict:
    action = np.asarray((0.3, -0.2), dtype=np.float64)
    default = reach_reward(
        0.08,
        0.04,
        SUCCESS_THRESHOLD,
        action,
        held_steps=1,
        previous_held_steps=0,
        hold_steps_required=100,
        joint_velocity=np.asarray((20.0, 20.0)),
        endpoint_velocity=5.0,
    )
    explicit_default = reach_reward(
        0.08,
        0.04,
        SUCCESS_THRESHOLD,
        action,
        held_steps=1,
        previous_held_steps=0,
        hold_steps_required=100,
        reward_profile=DEFAULT_REWARD_PROFILE,
        joint_velocity=np.asarray((20.0, 20.0)),
        endpoint_velocity=5.0,
    )
    _require(
        default == explicit_default,
        "default reward call changed when velocity inputs were supplied",
    )
    expected_total = (
        10.0 * (0.08 - 0.04)
        + 4.0 * (np.exp(-0.04 / 0.05) - np.exp(-0.08 / 0.05))
        + 50.0 / 100.0
        - 0.01 * (0.3**2 + 0.2**2)
    )
    _require(
        np.isclose(default.total, expected_total),
        "default reward no longer matches the baseline reference",
    )
    _require(
        not any(key.startswith("targeted_") for key in default.components),
        "default reward exposed targeted shaping components",
    )
    targeted = _targeted(0.04, endpoint_velocity=0.4)
    _require(
        targeted.total != default.total
        and "targeted_endpoint_velocity" in targeted.components,
        "targeted profile did not select the intervention",
    )

    evaluation = make_evaluation_env()
    training = make_training_env()
    try:
        _require(
            evaluation.reward_profile == DEFAULT_REWARD_PROFILE,
            "evaluation environment selected targeted shaping",
        )
        _require(
            training.reward_profile == TARGETED_REGULATION_PROFILE,
            "training environment did not select targeted shaping",
        )
        _require(
            evaluation.target_radius_range == TARGET_RADIUS_RANGE
            and training.target_radius_range == TRAINING_TARGET_RADIUS_RANGE,
            "environment target ranges changed",
        )
        sampled_radii = []
        sampled_angles = []
        for seed in range(64):
            evaluation.reset(seed=seed)
            target = evaluation.data.mocap_pos[0]
            sampled_radii.append(float(np.hypot(target[0], target[1])))
            sampled_angles.append(float(np.arctan2(target[1], target[0])))
        _require(
            min(sampled_radii) >= TARGET_RADIUS_RANGE[0]
            and max(sampled_radii) <= TARGET_RADIUS_RANGE[1]
            and min(sampled_angles) < -2.0
            and max(sampled_angles) > 2.0,
            "evaluation target sampling did not cover the official radial/angle range",
        )
        _require(
            evaluation.frame_skip == FRAME_SKIP
            and evaluation.success_threshold == SUCCESS_THRESHOLD
            and evaluation.hold_steps_required
            == round(HOLD_SECONDS / (evaluation.model.opt.timestep * FRAME_SKIP))
            and evaluation.max_episode_steps == MAX_EPISODE_STEPS,
            "official environment timing or termination settings changed",
        )

        def unexpected_endpoint_velocity() -> float:
            raise VerificationFailure(
                "default evaluation step requested endpoint velocity"
            )

        evaluation._endpoint_linear_velocity = unexpected_endpoint_velocity
        evaluation.reset(seed=7)
        _, _, _, _, evaluation_info = evaluation.step(
            np.zeros(2, dtype=np.float32)
        )
        _require(
            not any(
                key.startswith("targeted_")
                for key in evaluation_info["reward_components"]
            ),
            "default evaluation step selected targeted reward components",
        )
        training.reset(seed=7)
        observed_endpoint_velocity = training._endpoint_linear_velocity()
        _require(
            np.isfinite(observed_endpoint_velocity)
            and observed_endpoint_velocity >= 0.0,
            "MuJoCo endpoint linear velocity was not finite and nonnegative",
        )
        training._endpoint_linear_velocity = lambda: 0.0
        training.reset(seed=8)
        _, _, _, _, training_info = training.step(np.zeros(2, dtype=np.float32))
        _require(
            "targeted_endpoint_velocity"
            in training_info["reward_components"],
            "training step did not request targeted endpoint shaping",
        )
    finally:
        evaluation.close()
        training.close()
    return {
        "default_total": default.total,
        "baseline_reference_total": float(expected_total),
        "evaluation_profile": DEFAULT_REWARD_PROFILE,
        "training_profile": TARGETED_REGULATION_PROFILE,
        "evaluation_target_range": list(TARGET_RADIUS_RANGE),
        "training_target_range": list(TRAINING_TARGET_RADIUS_RANGE),
        "sampled_radius_bounds": [min(sampled_radii), max(sampled_radii)],
        "sampled_angle_bounds": [min(sampled_angles), max(sampled_angles)],
        "initial_training_endpoint_velocity": float(observed_endpoint_velocity),
    }


def _check_reset_and_hold_transitions() -> dict:
    env = TwoJointArmReachEnv()
    try:
        held_sequences = []
        outside_sequences = []
        for seed in (11, 12, 13):
            env.reset(seed=seed)
            _require(
                np.allclose(env.data.qpos, 0.0)
                and np.allclose(env.data.qvel, 0.0),
                "reset did not restore qpos=qvel=0",
            )
            distance_sequence = iter((0.005, 0.005, 0.02, 0.005))
            original_distance = env._distance_to_target
            env._distance_to_target = lambda: next(distance_sequence)
            try:
                transitions = [
                    env.step(np.zeros(2, dtype=np.float32)) for _ in range(4)
                ]
            finally:
                env._distance_to_target = original_distance
            held_sequences.append([item[4]["held_steps"] for item in transitions])
            outside_sequences.append(
                [
                    item[4]["reward_components"].get("outside_band", 0.0)
                    for item in transitions
                ]
            )
            _require(
                held_sequences[-1] == [1, 2, 0, 1],
                "hold counter did not reset on an interruption",
            )
            _require(
                transitions[2][2] is False
                and transitions[2][3] is False
                and transitions[2][4]["is_success"] is False
                and transitions[3][2] is False
                and transitions[3][4]["is_success"] is False,
                "an interrupted hold changed task termination semantics",
            )

        env.reset(seed=99)
        original_distance = env._distance_to_target
        env._distance_to_target = lambda: 0.005
        try:
            uninterrupted = [
                env.step(np.zeros(2, dtype=np.float32)) for _ in range(100)
            ]
        finally:
            env._distance_to_target = original_distance
        _require(
            not any(item[2] for item in uninterrupted[:-1])
            and uninterrupted[-1][2] is True
            and uninterrupted[-1][4]["is_success"] is True
            and uninterrupted[-1][4]["held_steps"] == 100,
            "hold did not require exactly 100 consecutive in-tolerance steps",
        )

        env.reset(seed=99)
        _require(
            env._held_steps == 0
            and env._outside_after_hold is False
            and np.allclose(env.data.qpos, 0.0)
            and np.allclose(env.data.qvel, 0.0),
            "repeated reset did not clear hold/interruption state",
        )
        return {
            "hold_steps_required": env.hold_steps_required,
            "held_sequences": held_sequences,
            "outside_band_components": outside_sequences,
            "reset_state": {
                "qpos": env.data.qpos.tolist(),
                "qvel": env.data.qvel.tolist(),
                "held_steps": env._held_steps,
                "outside_after_hold": env._outside_after_hold,
            },
        }
    finally:
        env.close()


def _run(output_path: Path) -> None:
    observed = {
        "velocity_sensitivity": _check_velocity_sensitivity(),
        "braking_and_holding": _check_braking_and_holding(),
        "default_path_and_profiles": _check_default_path_and_profiles(),
        "reset_and_hold_transitions": _check_reset_and_hold_transitions(),
    }
    artifact = {
        "passed": True,
        "observed": observed,
        "expected": {
            "high_velocity_is_more_punitive": True,
            "smooth_braking_reaches_full_weight_at_success_boundary": True,
            "targeted_penalties_remain_active_during_holding": True,
            "evaluation_uses_default_and_training_uses_targeted_profile": True,
            "reset_and_interruption_semantics_are_unchanged": True,
        },
        "checked_scope": [
            "targeted reward sensitivity to joint and endpoint velocity",
            "smooth braking and action regulation across the distance band",
            "repeated post-reach held-step shaping",
            "default reward and evaluation profile selection",
            "target distribution and official timing attributes",
            "repeated reset and synthetic hold-interruption transitions",
        ],
        "unchecked_scope": [
            "learned-policy performance or official evaluation success",
            "physical training outcomes under MuJoCo trajectories",
            "the live-versus-forward-qpos measurement discrepancy",
        ],
    }
    output_path.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    args = parser.parse_args()
    try:
        _run(args.artifact)
    except Exception as error:
        failure = {
            "passed": False,
            "failure": f"{type(error).__name__}: {error}",
            "observed": {},
            "expected": {
                "all_targeted_reward_and_environment_checks_pass": True,
            },
            "checked_scope": [
                "targeted reward, profile selection, and hold/reset checks up to failure"
            ],
            "unchecked_scope": [
                "checks after the first failure",
                "learned-policy performance or official evaluation success",
            ],
        }
        args.artifact.write_text(
            json.dumps(failure, indent=2) + "\n", encoding="utf-8"
        )
        raise


if __name__ == "__main__":
    main()
